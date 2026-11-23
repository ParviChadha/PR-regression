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


# ---------- git side ----------

def test_files(t, sha):
    paths = t.get("test_paths", ["tests", "test"])
    out = git(t.repo, "ls-tree", "-r", "--name-only", sha, "--", *paths)
    return [p for p in out.splitlines() if Path(p).suffix.lower() in TEST_EXT]


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


# ---------- per PR ----------

def build_context(t, rec, changes, budget):
    terms = search_terms(changes)
    meta = {"pr": rec["pr"], "tests_at": rec["sha_old"], "terms": terms, "blocks": []}
    if not terms:
        meta["skipped"] = "no searchable names (only operators or nothing mapped)"
        return None, meta
    block_re = re.compile(t.get("test_block_re", DEFAULT_TEST_BLOCK_RE))
    files = test_files(t, rec["sha_old"])
    texts = read_blobs(t, rec["sha_old"], files)
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
    if not any(hits.values()):
        meta["skipped"] = "no upstream test uses the changed code's names"
        return None, meta

    w = {term["name"]: weight(term["hits"]) * (1.5 if term["role"].startswith("changed") else 1.0)
         for term in terms}
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
        score = sum(w[n] for n in b["names"]) + file_affinity(path, [x for x in terms if x["name"] in b["names"]])
        out_blocks.append({"file": path, "start": s + 1, "end": e + 1, "names": sorted(b["names"]),
                           "score": round(score, 3), "text": text})
    searched = ", ".join(f"{x['name']} ({x['hits']})" for x in terms)
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
