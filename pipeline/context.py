#!/usr/bin/env python3
"""Test context (pipeline stage "Test context", the ChaCo idea): existing upstream tests that exercise the code a PR
changes, given to the test generator as examples of how the library is called.

Usage:  python3 pipeline/context.py <target> [--pr N ...] [--budget 7000]
        (also: python3 -m pipeline.context <target> ...)

For each PR with data/<t>/changes/<pr>.json (from changes.py):
  1. Search names: each changed public function or type, the public functions that reach each changed private
     entity (changes.py "reached_via"), changed macros, and the private entities' own names (some upstream tests
     test internals directly). Operator calls cannot be searched (`==` or `[]` are on nearly every test line), so a
     changed or reaching operator instead selects test blocks whose TITLE names it (OPERATOR_TITLE_WORDS), e.g.
     operator== -> SECTION("comparison operators").
  2. Upstream tests are read at the PR's PARENT commit, so tests the PR itself adds (which would describe the new
     behavior) never leak into the prompt.
  3. A test file line counts as a use when the name appears in call or use position: `.at(`, `->find(`,
     `contains(`, `json::value_t`, `NLOHMANN_DEFINE_TYPE_INTRUSIVE(`. Member functions need `.` or `->` before
     them, so a short name like `at` or `count` does not match prose or unrelated free functions.
  4. Each use is widened to its innermost test block (a line matching `test_block_re`: doctest/Catch SECTION and
     TEST_CASE, gtest TEST/TEST_F, Boost BOOST_AUTO_TEST_CASE) and closed at the brace that ends it; blocks longer
     than 50 lines are cut to the block's first line plus the lines around the use.
  5. Blocks are scored by the distinct names they use, rarer names counting more, plus a small bonus when the test
     file is named after what is searched (unit-comparison.cpp for operator==), and taken best first until the
     character budget (generate.py truncates context at 8000), at most 2 blocks per test file.

SQL tests (targets with `sql_test_ext`, e.g. duckdb, whose tests are mostly sqllogictest scripts test/sql/**/*.test):
  6. A changed or reaching C++ entity inside a struct that declares `static constexpr const char *Name = "avg"` (duckdb's
     function and setting registry: AvgFun, ThreadsSetting) names the SQL function or setting it implements; aliases
     (`using ALIAS = AvgFun;` in MeanFun -> "mean") count too. The structs are read at the parent commit from
     `sql_name_paths`. Each SQL name is searched in the .test files (a call `avg(` for functions, the word for settings).
  7. A use is widened to its sqllogictest record (the lines between blank lines: `statement ok` / `query I` with its
     SQL and expected result), and the CREATE / INSERT statements earlier in the file that define the tables, views,
     sequences, macros or types it uses are put in front, so the example runs on its own.
  8. Files that `require` an extension the build leaves out (`sql_missing_requires`, e.g. parquet, json, icu) are
     skipped: their examples would fail for reasons unrelated to the PR.
     The PR title adds names too: calls ("contains(list_column, '')"), snake_case SQL names ("struct_update"),
     UPPER_SNAKE type and option names ("TIMESTAMPTZ_NS", "NEW_LINE"): authors often name what the PR changes.
  9. When no SQL name is found or used (optimizer, storage and planner PRs implement no named function), records are
     taken from the test files whose path shares the most words with the changed files' paths (cte_filter_pusher.cpp
     -> test/optimizer/cte/...); the .json says "fallback": "path". C++ test files (Catch) are searched as before.

Writes data/<t>/context/<pr>.txt (what generate.py reads) and data/<t>/context/<pr>.json (names searched, hits per
name, blocks chosen and why). A PR whose changed code no test uses gets no .txt, and the .json says why.
"""
import argparse
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import Target, git, read_jsonl, write_text  # noqa: E402

DEFAULT_TEST_BLOCK_RE = (r"^\s*(TEST_CASE|SECTION|SUBCASE|TEST|TEST_F|TEST_P|TYPED_TEST|BOOST_AUTO_TEST_CASE|"
                         r"BOOST_FIXTURE_TEST_CASE|SCENARIO|GIVEN|WHEN|THEN)\s*\(")
TEST_EXT = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl"}
MAX_BLOCK_LINES = 50
AROUND = 12
MAX_PER_FILE = 2
DEFAULT_BUDGET = 7000


# ---------- pure functions (unit-tested in pipeline/test_context.py) ----------

# Words that test authors put in the titles of tests for each operator (matched case-insensitively in the
# title line of a test block, e.g. SECTION("comparison operators")). Calls to operators cannot be searched for
# usefully: `==` or `[]` occur on nearly every line of a test file.
OPERATOR_TITLE_WORDS = {
    "==": ["==", "equal", "compar"], "!=": ["!=", "equal", "compar"],
    "<": ["<", "less", "compar", "order", "sort"], ">": [">", "greater", "compar", "order"],
    "<=": ["<=", "less", "compar", "order"], ">=": [">=", "greater", "compar", "order"],
    "<=>": ["<=>", "three-way", "spaceship", "compar", "order"],
    "[]": ["[]", "operator[]", "element access", "subscript"],
    "<<": ["<<", "serializ", "output", "stream"], ">>": [">>", "deserializ", "input", "stream"],
    "=": ["assign"], "+=": ["+=", "append", "push_back"], "+": ["operator+", "append", "concatenat"],
    "()": ["operator()", "call"], "*": ["dereferenc", "operator*"], "->": ["operator->", "dereferenc"],
    "++": ["increment", "++"], "--": ["decrement", "--"], "!": ["negat"],
}
OPERATOR_RE = re.compile(r"operator\s*(\(\)|\[\]|<=>|[^\w\s(]+)\s*\(")


def operator_symbol(qualified):
    """'lib::operator==(const T&, const T&)' -> '=='; None for non-operators and conversion operators."""
    m = OPERATOR_RE.search(qualified)
    return m.group(1) if m else None


def simple_name(qualified):
    """'nlohmann::basic_json::at(KeyType &&)' -> 'at'; operators -> None (not searchable)."""
    head = qualified.split("(", 1)[0] if "operator" not in qualified else qualified
    last = head.rsplit("::", 1)[-1].strip()
    if not last or last.startswith("operator") or last.startswith("~") or last == "(anonymous)":
        return None
    last = re.sub(r"<.*$", "", last)            # partial specialisation spelling
    return last if re.fullmatch(r"[A-Za-z_]\w*", last) else None


def search_terms(changes):
    """[(name, role, pattern_kind, source entity)] from a changes.py record, deduplicated by name."""
    terms, seen = [], set()

    def add(name, role, kind, src):
        if name and name not in seen:
            seen.add(name)
            terms.append({"name": name, "role": role, "kind": kind, "from": src})

    for f in changes.get("functions", []):
        kind = f.get("kind")
        if kind == "macro":
            add(simple_name(f["name"]) or f["name"], "changed macro", "macro", f["name"])
        elif f.get("access") == "public":
            add(simple_name(f["name"]), "changed public " + kind,
                "member" if kind == "function" and f.get("member") else kind, f["name"])
    for f in changes.get("functions", []):
        for via in f.get("reached_via", []):
            add(simple_name(via["name"]), "public entry point", "member" if via.get("member") else "function",
                f["name"])
    ops = []
    for f in changes.get("functions", []):
        cands = ([f["name"]] if f.get("access") == "public" else []) + [v["name"] for v in f.get("reached_via", [])]
        for name in cands:
            sym = operator_symbol(name)
            if sym and sym not in ops:
                ops.append(sym)
                add(f"operator{sym}", "operator: test titles", "title", name)
    for f in changes.get("functions", []):
        if f.get("access") == "private" and f.get("kind") != "macro":
            kind = "member" if f.get("kind") == "function" and f.get("member") else f.get("kind", "function")
            add(simple_name(f["name"]), "changed private " + f.get("kind", ""), kind, f["name"])
    return terms


def term_regex(term, block_re=None):
    if term["kind"] == "title":
        words = OPERATOR_TITLE_WORDS.get(term["name"][len("operator"):], [])
        if not words:
            return re.compile(r"(?!x)x")                    # matches nothing
        title = re.compile("|".join(re.escape(w) for w in words), re.I)
        head = block_re or re.compile(DEFAULT_TEST_BLOCK_RE)

        class _Title:                                      # a test block title line that mentions the operator
            @staticmethod
            def search(line):
                if not head.match(line):
                    return None
                q = re.findall(r'"([^"]*)"', line)
                return title.search(" ".join(q)) if q else None
        return _Title
    n = re.escape(term["name"])
    if term["kind"] == "member":
        return re.compile(r"(?:\.|->)\s*" + n + r"\s*(?:<[^;()]*>)?\s*\(")
    if term["kind"] == "function":
        return re.compile(r"(?<![\w.>])" + n + r"\s*(?:<[^;()]*>)?\s*\(|(?:\.|->|::)\s*" + n + r"\s*(?:<[^;()]*>)?\s*\(")
    return re.compile(r"(?<!\w)" + n + r"(?!\w)")          # types, variables, macros: any use


def block_around(lines, idx, block_re):
    """(start, end) 0-based inclusive: the innermost test block around line `idx`, or a window if none/too long."""
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    start = None
    for i in range(idx, -1, -1):
        s = lines[i]
        if block_re.match(s) and (len(s) - len(s.lstrip()) < indent or i == idx):
            start = i
            break
    if start is None:
        return max(0, idx - AROUND), min(len(lines) - 1, idx + AROUND)
    base = len(lines[start]) - len(lines[start].lstrip())
    first = start + 1
    if first < len(lines) and lines[first].strip() == "{":
        first += 1                                 # the block's own opening brace on its own line
    end = None
    for j in range(first, len(lines)):
        s = lines[j]
        if s.strip() and not s.lstrip().startswith("#") and len(s) - len(s.lstrip()) <= base:
            end = j if s.strip().startswith("}") else j - 1
            break
    if end is None:
        end = len(lines) - 1
    if end < idx:                                  # unusual layout: fall back to a window around the use
        return max(start, idx - AROUND), min(len(lines) - 1, idx + AROUND)
    if end - start + 1 > MAX_BLOCK_LINES:
        return max(start, idx - AROUND), min(end, idx + AROUND)
    return start, end


FILE_BONUS = 0.15


def file_affinity(path, terms):
    """FILE_BONUS when the test file is named after what is searched (unit-comparison.cpp for operator==,
    unit-element_access.cpp for at): test files are usually named after the feature they test."""
    stem = Path(path).stem.lower()
    words = set()
    for t in terms:
        if t["kind"] == "title":
            words.update(w for w in OPERATOR_TITLE_WORDS.get(t["name"][len("operator"):], []) if w.isalpha())
        elif len(t["name"]) >= 4:
            words.add(t["name"].lower())
    return FILE_BONUS if any(len(w) >= 4 and w.lower() in stem for w in words) else 0.0


def weight(hits):
    """Rarer names say more about which tests matter."""
    return 1.0 / math.log2(2 + hits)


def select_blocks(blocks, budget, per_file=MAX_PER_FILE):
    """Best-scoring, non-overlapping blocks within the character budget."""
    chosen, used, per = [], 0, defaultdict(int)
    for b in sorted(blocks, key=lambda b: (-b["score"], b["file"], b["start"])):
        if per[b["file"]] >= per_file:
            continue
        if any(c["file"] == b["file"] and not (b["end"] < c["start"] or b["start"] > c["end"]) for c in chosen):
            continue
        size = len(b["text"]) + len(b["file"]) + 40 + sum(len(n) + 2 for n in b.get("names", []))
        if used + size > budget:
            continue
        chosen.append(b)
        used += size
        per[b["file"]] += 1
    return chosen


# ---------- SQL (sqllogictest) tests ----------

SQL_NAME_RE = re.compile(r'struct\s+(\w+)\s*(?:final\s*)?\{(?P<body>(?:(?!\bstruct\b).){0,600}?)'
                         r'static\s+constexpr\s+const\s+char\s*\*\s*Name\s*=\s*"([^"]+)"', re.S)
ALIAS_RE = re.compile(r"using\s+ALIAS\s*=\s*(\w+)\s*;")
SQL_DEF_RE = re.compile(r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW|SEQUENCE|MACRO|TYPE)\s+"
                        r"(?:IF\s+NOT\s+EXISTS\s+)?|INSERT\s+(?:OR\s+\w+\s+)?INTO\s+)([\w.\"]+)", re.I)
SQL_SETUP_BUDGET = 1200
PATH_STOP = {"src", "include", "duckdb", "common", "main", "function", "functions", "core", "extension", "test", "sql",
             "core_functions", "cpp", "hpp", "scalar", "aggregate", "table", "types", "util", "utils", "the", "and",
             "operator", "impl", "helper", "helpers", "base", "data", "info"}


def sql_name_map(texts):
    """{C++ struct name: [SQL names]} from headers declaring `static constexpr const char *Name = "..."`, with each
    alias struct's name (`using ALIAS = AvgFun;` in MeanFun) added to the struct it aliases."""
    own, alias_of = {}, {}
    for text in texts.values():
        for m in SQL_NAME_RE.finditer(text):
            struct, body, name = m.group(1), m.group("body"), m.group(3)
            a = ALIAS_RE.search(body)
            if a:
                alias_of.setdefault(a.group(1), []).append(name)
            own.setdefault(struct, []).append(name)
    out = {}
    for struct, names in own.items():
        out[struct] = list(dict.fromkeys(names + alias_of.get(struct, [])))
    return out


def scope_parts(qualified):
    """'duckdb::AvgFun::GetFunctions()' -> ['duckdb', 'AvgFun', 'GetFunctions']."""
    q = qualified.replace("(anonymous)", "\0anon\0")          # not the start of the argument list
    head = q.split("(", 1)[0] if "operator" not in q else re.sub(r"\(.*$", "", q)
    return [re.sub(r"<.*$", "", p).strip().replace("\0anon\0", "(anonymous)") for p in head.split("::") if p.strip()]


def sql_search_terms(changes, name_map):
    """SQL names implemented by the changed code: [{name, role, kind ('sql' or 'setting'), from}]."""
    terms, seen = [], set()
    for f in changes.get("functions", []):
        for q, role in [(f["name"], "changed")] + [(v["name"], "reached") for v in f.get("reached_via", [])]:
            for part in scope_parts(q):
                for name in name_map.get(part, []):
                    if name.lower() not in seen:
                        seen.add(name.lower())
                        terms.append({"name": name, "role": f"SQL name of {part} ({role})",
                                      "kind": "setting" if part.endswith("Setting") else "sql", "from": f["name"]})
    return terms


TITLE_CALL_RE = re.compile(r"(?<![\w.])([a-z_][a-z0-9_]*)\(")     # no space: "types (TIMESTAMP_NS)" is prose
COMMIT_PREFIXES = {"fix", "feat", "chore", "refactor", "perf", "test", "tests", "docs", "ci", "build", "style", "revert"}
TITLE_SNAKE_RE = re.compile(r"(?<![\w.])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![\w(])")
TITLE_UPPER_RE = re.compile(r"(?<![\w.])([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(?!\w)")
TITLE_TICK_RE = re.compile(r"`([A-Za-z_][\w ]{1,40}?)`")


def title_terms(title, known, have=()):
    """SQL names the PR title spells out: calls ("contains(list, '')"), snake_case names ("struct_update"),
    UPPER_SNAKE type or option names ("TIMESTAMPTZ_NS", "NEW_LINE") and `backticked` lowercase words. Calls and known
    SQL function names are searched as calls, the rest as words. `known`: every SQL name of the registry (lowercase)."""
    terms, seen = [], {h.lower() for h in have}

    def add(name, kind):
        if name.lower() not in seen and len(name) >= 3:
            seen.add(name.lower())
            terms.append({"name": name, "role": "named in the PR title", "kind": kind, "from": "title"})

    for m in TITLE_CALL_RE.finditer(title or ""):
        if m.group(1) not in COMMIT_PREFIXES:                   # "fix(join-condition): ..." is a commit-style prefix
            add(m.group(1), "sql")
    for m in TITLE_SNAKE_RE.finditer(title or ""):
        add(m.group(1), "sql" if m.group(1) in known else "word")
    for m in TITLE_UPPER_RE.finditer(title or ""):
        add(m.group(1), "word")
    for m in TITLE_TICK_RE.finditer(title or ""):
        w = m.group(1).strip()
        if w.islower() and " " not in w:
            add(w, "sql" if w in known else "word")
    return terms


def sql_term_regex(term):
    n = re.escape(term["name"])
    if term["kind"] in ("setting", "word"):
        return re.compile(r"(?<![\w.])" + n + r"(?!\w)", re.I)
    return re.compile(r"(?<![\w.])" + n + r"\s*\(", re.I)


def is_sql_test(t, path):
    return any(path.endswith(e) for e in t.get("sql_test_ext", []))


def sql_skipped(t, text):
    """The `require`d extension that rules this file out, or None."""
    missing = set(t.get("sql_missing_requires", []))
    for line in text.splitlines():
        m = re.match(r"\s*require\s+(\w+)", line)
        if m and m.group(1) in missing:
            return m.group(1)
    return None


def sql_record_around(lines, idx):
    """(start, end) 0-based inclusive: the sqllogictest record (between blank lines) around line idx."""
    s = idx
    while s > 0 and lines[s - 1].strip():
        s -= 1
    e = idx
    while e + 1 < len(lines) and lines[e + 1].strip():
        e += 1
    if e - s + 1 > MAX_BLOCK_LINES:
        return max(s, idx - AROUND), min(e, idx + AROUND)
    return s, e


def sql_records(lines):
    """[(start, end)] of every record in a sqllogictest file."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip():
            s, e = i, i
            while e + 1 < len(lines) and lines[e + 1].strip():
                e += 1
            out.append((s, e))
            i = e + 1
        else:
            i += 1
    return out


def sql_setup(lines, start, end):
    """The `statement ok` records before `start` that create or fill a table/view/sequence/macro/type the record at
    start..end uses (two passes, so a view's table comes along), joined, within SQL_SETUP_BUDGET characters."""
    body = "\n".join(lines[start:end + 1]).lower()
    defs = []
    for s, e in sql_records(lines[:start]):
        if not lines[s].lstrip().startswith("statement ok"):
            continue
        rec = "\n".join(lines[s:e + 1])
        names = [m.group(1).strip('"').split(".")[-1].lower() for m in SQL_DEF_RE.finditer(rec)]
        if names:
            defs.append((rec, names))
    keep, wanted = [], body
    for _ in range(2):
        for rec, names in defs:
            if rec not in keep and any(re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", wanted) for n in names):
                keep.append(rec)
        wanted = body + "\n" + "\n".join(keep).lower()
    keep = [rec for rec, _ in defs if rec in keep]             # file order
    out, used = [], 0
    for rec in keep:
        if used + len(rec) > SQL_SETUP_BUDGET:
            break
        out.append(rec)
        used += len(rec) + 2
    return "\n\n".join(out)


def path_words(path):
    words = set()
    for part in re.split(r"[/_.\-]+", path.lower()):
        if len(part) >= 3 and part not in PATH_STOP and not part.isdigit():
            words.add(part)
    return words


def sql_blocks(t, rec, changes, sql_texts, name_map):
    """Candidate blocks from SQL test files: (blocks, terms, fallback or None). Blocks have file/start/end (0-based)/
    names/text like the C++ ones, text already including the setup the record needs."""
    terms = sql_search_terms(changes, name_map)
    known = {n.lower() for names in name_map.values() for n in names}
    terms += title_terms(rec.get("title") or rec.get("subject") or "", known, [x["name"] for x in terms])
    usable = {p: x for p, x in sql_texts.items() if not sql_skipped(t, x)}
    hits = defaultdict(list)
    regs = [(term, sql_term_regex(term)) for term in terms]
    for path, text in usable.items():
        for i, line in enumerate(text.splitlines()):
            if line.lstrip().startswith("#"):
                continue
            for term, rx in regs:
                if rx.search(line):
                    hits[term["name"]].append((path, i))
    for term in terms:
        term["hits"] = len(hits[term["name"]])
    blocks = {}
    for name, locs in hits.items():
        for path, i in locs:
            lines = usable[path].splitlines()
            s, e = sql_record_around(lines, i)
            b = blocks.setdefault((path, s, e), {"file": path, "start": s, "end": e, "names": set()})
            b["names"].add(name)
    fallback = None
    if not blocks:
        changed = [w for f in changes.get("files", []) or rec.get("main_files", []) for w in path_words(f)]
        want = set(changed)
        scored = sorted(((len(want & path_words(p)), p) for p in usable if want & path_words(p)),
                        key=lambda x: (-x[0], x[1]))[:4]
        for n, path in scored:
            lines = usable[path].splitlines()
            got = 0
            for s, e in sql_records(lines):
                if lines[s].lstrip().startswith("query") and got < MAX_PER_FILE and e - s + 1 <= MAX_BLOCK_LINES:
                    words = sorted(want & path_words(path))
                    blocks[(path, s, e)] = {"file": path, "start": s, "end": e,
                                            "names": {"path:" + w for w in words}, "path_score": n}
                    got += 1
        if blocks:
            fallback = "path"
    out = []
    for (path, s, e), b in blocks.items():
        lines = usable[path].splitlines()
        setup = sql_setup(lines, s, e)
        text = (setup + "\n\n" if setup else "") + "\n".join(lines[s:e + 1])
        out.append({**b, "text": text})
    return out, terms, fallback


# ---------- git side ----------

def test_files(t, sha):
    paths = t.get("test_paths", ["tests", "test"])
    out = git(t.repo, "ls-tree", "-r", "--name-only", sha, "--", *paths)
    sql_ext = tuple(t.get("sql_test_ext", []))
    return [p for p in out.splitlines() if Path(p).suffix.lower() in TEST_EXT or (sql_ext and p.endswith(sql_ext))]


def name_headers(t, sha):
    """{path: text} of the headers under `sql_name_paths` at `sha` (SQL function/setting registry)."""
    paths = t.get("sql_name_paths", [])
    if not paths:
        return {}
    out = git(t.repo, "ls-tree", "-r", "--name-only", sha, "--", *paths)
    return read_blobs(t, sha, [p for p in out.splitlines() if p.endswith((".hpp", ".h"))])


def read_blobs(t, sha, paths):
    """{path: text} for many files of one commit in a single `git cat-file --batch`."""
    req = "".join(f"{sha}:{p}\n" for p in paths).encode()
    out = subprocess.run(["git", "-C", str(t.repo), "cat-file", "--batch"], input=req,
                         capture_output=True, check=True).stdout
    res, pos = {}, 0
    for p in paths:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if len(header) < 3 or header[1] == b"missing":
            pos = nl + 1
            continue
        size = int(header[2])
        res[p] = out[nl + 1: nl + 1 + size].decode("utf-8", errors="replace")
        pos = nl + 1 + size + 1
    return res


_NAME_MAPS = {}


def name_map(t, sha):
    if (t.name, sha) not in _NAME_MAPS:
        _NAME_MAPS[(t.name, sha)] = sql_name_map(name_headers(t, sha))
    return _NAME_MAPS[(t.name, sha)]


# ---------- per PR ----------

def build_context(t, rec, changes, budget):
    terms = search_terms(changes)
    sql_mode = bool(t.get("sql_test_ext"))
    meta = {"pr": rec["pr"], "tests_at": rec["sha_old"], "terms": terms, "blocks": []}
    if not terms and not sql_mode:
        meta["skipped"] = "no searchable names (only operators or nothing mapped)"
        return None, meta
    block_re = re.compile(t.get("test_block_re", DEFAULT_TEST_BLOCK_RE))
    files = test_files(t, rec["sha_old"])
    texts = read_blobs(t, rec["sha_old"], files)
    sql_texts = {p: x for p, x in texts.items() if is_sql_test(t, p)}
    texts = {p: x for p, x in texts.items() if p not in sql_texts}
    regs = [(term, term_regex(term, block_re)) for term in terms]
    hits = defaultdict(list)                    # name -> [(file, line index)]
    for path, text in texts.items():
        for i, line in enumerate(text.splitlines()):
            if line.lstrip().startswith("//"):
                continue
            for term, rx in regs:
                if rx.search(line):
                    hits[term["name"]].append((path, i))
    for term in terms:
        term["hits"] = len(hits[term["name"]])
    sblocks, sterms, fallback = ([], [], None)
    if sql_mode:
        sblocks, sterms, fallback = sql_blocks(t, rec, changes, sql_texts, name_map(t, rec["sha_old"]))
        meta["sql_terms"] = sterms
        meta["sql_files"] = len(sql_texts)
        if fallback:
            meta["fallback"] = fallback
    if not any(hits.values()) and not sblocks:
        meta["skipped"] = ("no upstream test uses the changed code's names"
                           + (" or the SQL names it implements, and no SQL test file matches its path" if sql_mode else ""))
        return None, meta

    cpp_w = float(t.get("cpp_term_weight", 1.0))   # duckdb: 0.5, C++ names like Read/Optimize say less than SQL names
    w = {term["name"]: weight(term["hits"]) * (1.5 if term["role"].startswith("changed") else 1.0) * cpp_w
         for term in terms}
    w.update({term["name"]: weight(term["hits"]) * 1.5 for term in sterms})   # a named SQL entry point is direct evidence
    blocks = {}
    for name, locs in hits.items():
        for path, i in locs:
            lines = texts[path].splitlines()
            s, e = block_around(lines, i, block_re)
            b = blocks.setdefault((path, s, e), {"file": path, "start": s, "end": e, "names": set()})
            b["names"].add(name)
    out_blocks = []
    for (path, s, e), b in blocks.items():
        lines = texts[path].splitlines()
        text = "\n".join(lines[s:e + 1])
        score = sum(w[n] for n in b["names"]) + cpp_w * file_affinity(path, [x for x in terms if x["name"] in b["names"]])
        out_blocks.append({"file": path, "start": s + 1, "end": e + 1, "names": sorted(b["names"]),
                           "score": round(score, 3), "text": text})
    for b in sblocks:
        if b.get("path_score") is not None:
            score = 0.2 + 0.1 * b["path_score"]                    # weaker than any name match
        else:
            score = sum(w[n] for n in b["names"])
        out_blocks.append({"file": b["file"], "start": b["start"] + 1, "end": b["end"] + 1, "names": sorted(b["names"]),
                           "score": round(score, 3), "text": b["text"]})
    searched = ", ".join(f"{x['name']} ({x['hits']})" for x in terms + sterms)
    if fallback:
        searched += "; no SQL name matched, so SQL tests were picked by the changed files' paths"
    parts = [f"// Upstream tests at the PR's parent commit {rec['sha_old'][:9]} that use the changed code.",
             f"// Names searched (test lines using each): {searched}"]
    header = len("\n".join(parts))
    chosen = select_blocks(out_blocks, budget - header)      # the whole file stays within the budget
    chosen.sort(key=lambda b: (-b["score"], b["file"], b["start"]))
    meta["blocks"] = [{k: b[k] for k in ("file", "start", "end", "names", "score")} for b in chosen]
    meta["candidate_blocks"] = len(out_blocks)
    if not chosen:
        meta["skipped"] = "every matching test block is larger than the budget"
        return None, meta
    for b in chosen:
        parts += ["", f"// ---- {b['file']}:{b['start']}-{b['end']}  (uses: {', '.join(b['names'])})", b["text"]]
    return "\n".join(parts) + "\n", meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target")
    ap.add_argument("--pr", type=int, nargs="*", help="only these PRs (default: every PR with changes.py output)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="characters of test code per PR")
    a = ap.parse_args(argv)
    t = Target(a.target)
    if not (t.repo / ".git").exists():
        sys.exit(f"{t.repo} missing: clone the library there first (see NOTES.md)")
    recs = {r["pr"]: r for r in read_jsonl(t.data / "prs.jsonl")}
    chg_dir, out_dir = t.data / "changes", t.data / "context"
    prs = a.pr or sorted(int(p.stem) for p in chg_dir.glob("*.json"))
    if not prs:
        sys.exit(f"no {chg_dir}/<pr>.json yet: run pipeline/changes.py {t.name} first")
    out_dir.mkdir(parents=True, exist_ok=True)
    n_ok = n_none = 0
    for pr in prs:
        cp = chg_dir / f"{pr}.json"
        if pr not in recs or not cp.is_file():
            print(f"#{pr}: skipped (no prs.jsonl record or no changes.py output)", file=sys.stderr)
            continue
        text, meta = build_context(t, recs[pr], json.loads(cp.read_text(encoding="utf-8")), a.budget)
        txt = out_dir / f"{pr}.txt"
        if text:
            write_text(txt, text)
            n_ok += 1
        else:
            if txt.exists():
                txt.unlink()                      # a stale context from an earlier run must not be used
            n_none += 1
        write_text(out_dir / f"{pr}.json", json.dumps(meta, indent=1, sort_keys=True) + "\n")
        detail = (f"{len(meta['blocks'])} blocks, {len(text)} chars" if text else meta.get("skipped"))
        print(f"#{pr}: {detail}", file=sys.stderr)
    print(json.dumps({"with_context": n_ok, "without_context": n_none}))


if __name__ == "__main__":
    main()
