#!/usr/bin/env python3
"""Change analysis (pipeline stage "Run change analysis"): which C++ entities each PR changes, whether they are
public or private, and, for private ones, which public functions reach them.

Usage:  python3 pipeline/changes.py <target> [--pr N ...] [--force] [--jobs 2]
        (also: python3 -m pipeline.changes <target> ...)

For each PR in data/<t>/prs.jsonl (from collect.py):
  1. The library sources at the parent commit (old) and the merge commit (new) are exported with `git archive` to
     cache/analysis/<t>/<sha>/ (the upstream clone is only read).
  2. libclang parses each version: one translation unit including every `analysis_entries` header that exists at
     that commit (default: smoke_header), which reaches every header the library's users see; a changed file the entries do not reach
     (for example a .cpp of a compiled library) is parsed on its own. -I: include_dirs plus `analysis_include_dirs`
     (headers only the library's own sources use); exported paths: `analysis_paths` (default include_dirs).
  3. Every changed line of the -U0 diff (removed lines on the old side, added lines on the new side) is mapped to the
     innermost declaration around it: function, method, constructor, template, class, type alias, enum, variable
     or macro. Lines outside any declaration (includes, blank space between declarations) are counted as unmapped.
     Lines inside a preprocessor branch that is off by default (#if JSON_DIAGNOSTICS) are not in the parse; they
     are mapped again with each flag set of `analysis_variants`, and entities found that way carry
     "requires_flags". Lines still unmapped are listed with the #if conditions around them.
  4. Access: private if inside a `private_namespaces` namespace (default detail/details/impl/internal), an anonymous
     namespace, a private/protected class member at any level, or with internal linkage; otherwise public.
  5. For private entities, a reverse-reference walk over the whole translation unit (calls, type and template
     references, up to 15 levels, nearest first) finds the public functions that use them: the entry points a test has to call.

Writes data/<t>/changes/<pr>.json, which generate.py reads:
  {"pr", "sha_old", "sha_new", "functions": [{"name", "kind", "access", "private_because", "member", "status",
   "file", "lines_changed", "reached_via": [{"name", "member"}], "requires_flags"?}], "unmapped_lines",
   "unmapped": [{"file", "lines", "inside_conditions"}], "parse_errors", "files", "tool"}
"functions" holds every changed entity (types and macros too); the key name is what generate.py expects.

Needs the libclang Python package (`pip install libclang`) and clang's builtin headers (stddef.h etc.), which that
package does not ship. They are found, in order, from: $PRH_CLANG_RESOURCE_DIR, `analysis_resource_dir` in
target.toml, `clang -print-resource-dir` of a clang on PATH. Run it on Linux (apt install clang) or macOS (Xcode
command line tools): on Windows clang also needs Visual Studio's C++ standard library headers, and without them every
parse stops at a fatal error (changes.py refuses to write results then).
"""
import argparse
import ctypes
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import Target, git, read_jsonl, write_text  # noqa: E402

FUNCTION_KINDS = {"FUNCTION_DECL", "CXX_METHOD", "CONSTRUCTOR", "DESTRUCTOR", "CONVERSION_FUNCTION",
                  "FUNCTION_TEMPLATE"}
TYPE_KINDS = {"CLASS_DECL", "STRUCT_DECL", "UNION_DECL", "CLASS_TEMPLATE", "CLASS_TEMPLATE_PARTIAL_SPECIALIZATION",
              "TYPE_ALIAS_DECL", "TYPE_ALIAS_TEMPLATE_DECL", "TYPEDEF_DECL", "ENUM_DECL", "CONCEPT_DECL"}
VALUE_KINDS = {"VAR_DECL", "FIELD_DECL", "ENUM_CONSTANT_DECL"}
MACRO_KINDS = {"MACRO_DEFINITION"}
ENTITY_KINDS = FUNCTION_KINDS | TYPE_KINDS | VALUE_KINDS | MACRO_KINDS
SCOPE_KINDS = {"NAMESPACE"} | TYPE_KINDS | FUNCTION_KINDS
DEFAULT_PRIVATE_NAMESPACES = ["detail", "details", "impl", "internal"]
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
MAX_REACH_DEPTH = 15
CLIMB_TO_CLASS = {"CXX_METHOD", "FUNCTION_TEMPLATE", "CONVERSION_FUNCTION", "CONSTRUCTOR", "DESTRUCTOR",
                  "FIELD_DECL", "VAR_DECL"}
MAX_REACHED = 10


# ---------- pure functions (unit-tested in pipeline/test_changes.py) ----------

def changed_lines(diff_text):
    """{path: {"old": set(lines), "new": set(lines), "old_path": path}} from a -U0 unified diff, keyed by the new
    path (the old path for a deleted file); "old_path" differs from the key for a renamed file.

    A pure insertion also marks the old line it follows, and a pure deletion the new line it precedes, so a change
    that only adds or only removes lines is still placed inside its enclosing declaration on both sides."""
    out, path, old_path = {}, None, None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            path = old_path = None
            continue
        if line.startswith("--- "):
            p = line[4:].strip()
            old_path = None if p == "/dev/null" else (p[2:] if p.startswith("a/") else p)
            continue
        if line.startswith("+++ "):
            p = line[4:].strip()
            new_path = None if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
            path = new_path or old_path
            if path is not None:
                out.setdefault(path, {"old": set(), "new": set(), "old_path": old_path or path})
            continue
        m = HUNK_RE.match(line)
        if m and path is not None:
            o_start, o_len = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            n_start, n_len = int(m.group(3)), int(m.group(4) if m.group(4) is not None else 1)
            rec = out[path]
            rec["old"].update(range(o_start, o_start + o_len))
            rec["new"].update(range(n_start, n_start + n_len))
            if o_len == 0 and o_start > 0:
                rec["old"].add(o_start)       # insertion after old line o_start
            if n_len == 0 and n_start > 0:
                rec["new"].add(n_start)       # deletion after new line n_start
    return out


def innermost(entities, line):
    """The entity with the smallest extent containing `line`; functions win ties against the types around them."""
    best = None
    for e in entities:
        if e["start"] <= line <= e["end"]:
            size = e["end"] - e["start"]
            rank = (size, 0 if e["kind"] == "function" else 1)
            if best is None or rank < best[0]:
                best = (rank, e)
    return best[1] if best else None


def classify_access(scopes, own_access, linkage, private_namespaces):
    """('public'|'private', reason or None) from the chain of enclosing scopes (outermost first).

    scopes: [(kind, name, access)] with kind 'namespace' or 'class'; access is the member's access specifier
    inside its class ('public'/'protected'/'private'/None)."""
    priv = {n.lower() for n in private_namespaces}
    for kind, name, access in scopes:
        if kind == "namespace" and (name == "" or name.lower() in priv):
            return "private", f"namespace {name or '(anonymous)'}"
        if kind == "class" and access in ("private", "protected"):
            return "private", f"{access} member {name}"
    if own_access in ("private", "protected"):
        return "private", f"{own_access} member"
    if linkage == "internal":
        return "private", "internal linkage"
    return "public", None


def shorten_templates(name, limit=40):
    """Collapse template argument lists longer than `limit` characters to <...>, innermost first, so a name like
    merge_diff(const basic_json<ObjectType, ArrayType, ... CustomBaseClass> &) stays readable in a prompt."""
    while True:
        best = None
        depth_start = []
        for i, ch in enumerate(name):
            if ch == "<":
                depth_start.append(i)
            elif ch == ">" and depth_start:
                j = depth_start.pop()
                if i - j - 1 > limit and name[j + 1:i] != "...":
                    best = (j, i)
                    break
        if best is None:
            return name
        j, i = best
        name = name[:j] + "<...>" + name[i + 1:]


def merge_sides(old, new):
    """Combine per-side entity hits ({key: entity}) into one list with status added/removed/modified."""
    out = []
    for key in list(new) + [k for k in old if k not in new]:
        o, n = old.get(key), new.get(key)
        e = dict(n or o)
        e["status"] = "modified" if (o and n) else ("added" if n else "removed")
        e["lines_changed"] = (o or {}).get("lines_changed", 0) + (n or {}).get("lines_changed", 0)
        out.append(e)
    order = {"modified": 0, "added": 1, "removed": 2}
    out.sort(key=lambda e: (e["access"] != "private", order[e["status"]], -e["lines_changed"], e["name"]))
    return out


# ---------- libclang side ----------

def _clang():
    try:
        import clang.cindex as ci
    except ImportError:
        sys.exit("changes.py needs the libclang Python package: pip install libclang")
    return ci


def resource_dir(t):
    cands = [os.environ.get("PRH_CLANG_RESOURCE_DIR"), t.get("analysis_resource_dir")]
    exes = ["clang", "clang-18", "clang-19", "clang-20", "clang-17"]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")):
        if base:                                      # the LLVM installer for Windows does not always add itself to PATH
            exes.append(str(Path(base) / "LLVM" / "bin" / "clang.exe"))
    for exe in exes:
        if shutil.which(exe):
            r = subprocess.run([exe, "-print-resource-dir"], capture_output=True, text=True)
            if r.returncode == 0:
                cands.append(r.stdout.strip())
    for c in cands:
        if c and (Path(c) / "include" / "stddef.h").is_file():
            return c
    sys.exit("changes.py: clang's builtin headers (stddef.h) not found. Install clang (Windows: winget install "
             "LLVM.LLVM; macOS: xcode-select --install; Linux: apt install clang) or set PRH_CLANG_RESOURCE_DIR.")


def export_sources(t, sha, paths):
    """Library sources of `sha` under cache/analysis/<t>/<sha>/ (pure Python, works on every OS)."""
    dest = t.cache / "analysis" / t.name / sha
    if (dest / ".prh-ok").is_file():
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    data = subprocess.run(["git", "-C", str(t.repo), "archive", "--format=tar", sha, "--", *paths],
                          capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest, filter="data")
    write_text(dest / ".prh-ok", sha + "\n")
    return dest


def _is_inline_ns(ci, cursor):
    f = ci.conf.lib.clang_Cursor_isInlineNamespace
    f.argtypes, f.restype = [ci.Cursor], ctypes.c_uint
    return bool(f(cursor))


class Analyzer:
    """Parses one version of the library and answers questions about declarations in it."""

    def __init__(self, t, root, resdir, extra_flags=()):
        self.ci = _clang()
        self.t, self.root, self.resdir = t, Path(root), resdir
        # analysis_include_dirs: extra -I dirs (relative to the export) that only the library's own .cpp files need,
        # e.g. duckdb's third_party/*/include; generated tests do not see them, so they are not in include_dirs.
        inc = list(t.get("include_dirs", t.get("main_source", ["include"]))) + list(t.get("analysis_include_dirs", []))
        self.args = (["-x", "c++", f"-std={t.get('analysis_std', 'c++17')}", "-resource-dir", resdir]
                     + [f"-I{self.root / d}" for d in inc] + list(t.get("analysis_flags", [])) + list(extra_flags))
        self.index = self.ci.Index.create()
        self.tus = {}
        self.errors = 0

    def _parse(self, key, path, unsaved=None, header=False):
        if key in self.tus:
            return self.tus[key]
        args = list(self.args)
        if header:
            args[1] = "c++-header"
        opts = self.ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        tu = self.index.parse(path, args=args, unsaved_files=unsaved, options=opts)
        fatal = [d for d in tu.diagnostics if d.severity >= 4]
        if fatal:
            # a fatal error (usually a header not found) stops the parse early, and everything after it is missing:
            # the results would look normal but be partial. Seen on Windows without a C++ standard library for clang.
            raise RuntimeError(f"fatal parse error in {path}: {fatal[0]} (install the C++ standard library headers "
                               f"clang needs, or run on Linux/macOS; see NOTES.md)")
        self.errors += sum(1 for d in tu.diagnostics if d.severity >= 3)
        self.tus[key] = tu
        return tu

    def entry_tu(self):
        entries = self.t.get("analysis_entries") or [self.t.get("smoke_header", "")]
        # __has_include: an entry header may not exist yet at an older commit
        src = "".join(f"#if __has_include(<{e}>)\n#include <{e}>\n#endif\n" for e in entries if e)
        return self._parse("__entry__", "prh_entry.cpp", [("prh_entry.cpp", src)])

    def tu_for(self, relpath):
        """A translation unit that contains declarations from `relpath`."""
        tu = self.entry_tu()
        full = _norm(self.root / relpath)
        if any(_norm(f.include.name) == full for f in tu.get_includes()):
            return tu
        if not (self.root / relpath).is_file():
            return None
        return self._parse(relpath, full, header=Path(relpath).suffix.lower() in
                           {".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl", ".tcc", ".tpp"})

    # ----- naming and access

    def scopes(self, c):
        """Enclosing scopes outermost first, as (kind, name, access) for classify_access, and display parts."""
        chain, cur = [], c.semantic_parent
        while cur is not None and cur.kind != self.ci.CursorKind.TRANSLATION_UNIT:
            chain.append(cur)
            cur = cur.semantic_parent
        chain.reverse()
        scopes, parts = [], []
        for i, s in enumerate(chain):
            if s.kind == self.ci.CursorKind.NAMESPACE:
                scopes.append(("namespace", s.spelling, None))
                if not _is_inline_ns(self.ci, s):
                    parts.append(s.spelling or "(anonymous)")
            else:
                scopes.append(("class", s.spelling, _access(s)))
                parts.append(s.spelling)
        return scopes, parts

    def describe(self, c):
        kind = self.kind_of(c)
        scopes, parts = self.scopes(c)
        own = c.spelling if kind in ("type", "variable", "macro") else c.displayname
        name = shorten_templates("::".join(parts + [own]) if kind != "macro" else own)
        if kind == "macro":
            access, why = None, None
        else:
            linkage = c.linkage.name.lower() if c.linkage else None
            access, why = classify_access(scopes, _access(c), "internal" if linkage == "internal" else None,
                                          self.t.get("private_namespaces", DEFAULT_PRIVATE_NAMESPACES))
        member = any(k == "class" for k, _, _ in scopes)
        return {"name": name, "kind": kind, "access": access, "private_because": why, "member": member,
                "usr": c.get_usr() or name}

    @staticmethod
    def kind_of(c):
        k = c.kind.name
        return ("function" if k in FUNCTION_KINDS else "type" if k in TYPE_KINDS else
                "macro" if k in MACRO_KINDS else "variable")

    # ----- declarations in a file

    def entities_in(self, relpath):
        tu = self.tu_for(relpath)
        if tu is None:
            return []
        full = _norm(self.root / relpath)
        out = []
        for c in tu.cursor.walk_preorder():
            if c.kind.name not in ENTITY_KINDS:
                continue
            f = c.location.file
            if f is None or _norm(f.name) != full:
                continue
            if c.kind.name in VALUE_KINDS and c.semantic_parent is not None and \
                    c.semantic_parent.kind.name in FUNCTION_KINDS:
                continue                      # a local variable belongs to its function
            if c.kind.name == "TYPE_ALIAS_DECL" and c.semantic_parent.kind.name == "TYPE_ALIAS_TEMPLATE_DECL":
                continue                      # the template already covers it
            out.append({"cursor": c, "start": c.extent.start.line, "end": c.extent.end.line,
                        "kind": self.kind_of(c)})
        return out

    # ----- reverse references (who uses an entity)

    def users_graph(self, relpath=None):
        """{usr: {user usr}} over the entry TU, plus the TU of `relpath` when that file is parsed on its own (a .cpp
        of a compiled library: its private helpers are used only by functions in that same file), restricted to
        declarations in the exported library sources."""
        if not hasattr(self, "_graphs"):
            self._graphs = {}
        base = self._graph_of("__entry__", self.entry_tu())
        tu = self.tu_for(relpath) if relpath else None
        if tu is None or tu is self.tus.get("__entry__"):
            return base
        if relpath not in self._graphs:
            g2, i2 = self._graph_of("__file__" + relpath, tu)
            graph = defaultdict(set, {k: set(v) for k, v in base[0].items()})
            for k, v in g2.items():
                graph[k] |= v
            self._graphs[relpath] = (graph, {**i2, **base[1]})
        return self._graphs[relpath]

    def _graph_of(self, key, tu):
        if key in self._graphs:
            return self._graphs[key]
        root = _norm(self.root)
        graph, info = defaultdict(set), {}

        def visit(c, owner):
            k = c.kind.name
            # Namespace- and class-scope variables own references too: libraries often call through function
            # objects (nlohmann's `constexpr const auto& from_json = static_const<from_json_fn>::value`), and the
            # chain breaks at the variable otherwise. Local variables stay part of their function.
            is_owner = k in FUNCTION_KINDS or k in TYPE_KINDS or (
                k == "VAR_DECL" and (owner is None or owner.kind.name not in FUNCTION_KINDS))
            if is_owner:
                f = c.location.file
                if f is not None and _norm(f.name).startswith(root):
                    owner = c
                    u = c.get_usr()
                    if u and u not in info:
                        info[u] = c
            if owner is not None and (c.kind.is_reference() or k in ("DECL_REF_EXPR", "MEMBER_REF_EXPR",
                                                                      "CALL_EXPR", "OVERLOADED_DECL_REF")):
                targets = []
                if k == "OVERLOADED_DECL_REF":
                    targets = _overloads(self.ci, c)
                elif c.referenced is not None:
                    targets = [c.referenced]
                ou = owner.get_usr()
                for r in targets:
                    # a call with explicit template arguments (f<Real, X>(...)) references the instantiation,
                    # whose USR differs from the template the PR changed: count it for the template too
                    tmpl = _template_of(self.ci, r) if r.kind.name in FUNCTION_KINDS else None
                    for ru in {r.get_usr(), tmpl.get_usr() if tmpl is not None else None}:
                        if ru and ou and ru != ou:
                            graph[ru].add(ou)
            for ch in c.get_children():
                visit(ch, owner)

        visit(tu.cursor, None)
        self._graphs[key] = (graph, info)
        return graph, info

    def reached_via(self, usr, relpath=None):
        """Public functions within MAX_REACH_DEPTH reverse-reference hops of `usr`, nearest first, as
        {"name", "member"} (member: a class member, so tests call it as obj.name(...))."""
        graph, info = self.users_graph(relpath)
        seen, frontier, found = {usr}, [usr], []
        for _ in range(MAX_REACH_DEPTH):
            nxt = []
            for u in frontier:
                users = set(graph.get(u, ()))
                c = info.get(u)
                if c is not None and c.kind.name in CLIMB_TO_CLASS \
                        and c.semantic_parent is not None and c.semantic_parent.kind.name in TYPE_KINDS \
                        and (c.spelling == "operator()" or not users or _access(c) == "public"):
                    # a member is reached through its class when nobody names it (a function object's operator(),
                    # a constructor run by std::vector::emplace_back, a destructor, a field set by aggregate
                    # initialisation) or when it is the class's public interface: calls on it from templates are
                    # often unresolved (`binary_writer<...>(o).write_cbor(j)` in basic_json::to_cbor). Whoever
                    # uses the class can call them.
                    pu = c.semantic_parent.get_usr()
                    if pu:
                        users.add(pu)
                        info.setdefault(pu, c.semantic_parent)
                if c is not None and c.kind.name in ("CXX_METHOD", "DESTRUCTOR"):
                    # an override is called wherever the method it overrides is (virtual dispatch:
                    # Calendar::isBusinessDay -> impl_->isBusinessDay -> Serbia::BseImpl::isBusinessDay)
                    for base in _overridden(self.ci, c):
                        bu = base.get_usr()
                        if bu:
                            users.add(bu)
                            info.setdefault(bu, base)
                if c is not None and c.kind.name in ("CLASS_TEMPLATE_PARTIAL_SPECIALIZATION", "CLASS_DECL",
                                                     "STRUCT_DECL"):
                    # code names the primary template, never a (partial) specialization of it, so the
                    # specialization is used wherever the primary template is
                    prim = _primary_template(self.ci, c)
                    if prim is not None and prim.get_usr():
                        users.add(prim.get_usr())
                        info.setdefault(prim.get_usr(), prim)
                for user in sorted(users):
                    if user in seen:
                        continue
                    seen.add(user)
                    c = info.get(user)
                    if c is None:
                        continue
                    d = self.describe(c)
                    if d["access"] == "public" and d["kind"] == "function":
                        if all(f["name"] != d["name"] for f in found):
                            found.append({"name": d["name"], "member": d["member"]})
                    else:
                        nxt.append(user)      # keep climbing through private users and types
            if len(found) >= MAX_REACHED or not nxt:
                break
            frontier = nxt
        return found[:MAX_REACHED]


def _norm(path):
    """A path in one canonical spelling. On Windows clang reports an included file as the -I directory joined to the
    #include text, mixing \\ and / (C:\\repo\\include/nlohmann/json.hpp); compared raw, nothing would match."""
    return os.path.normcase(os.path.normpath(str(path)))


def _overloads(ci, c):
    """Candidate declarations of an unresolved overloaded name (calls in templates often look like this)."""
    n_f, get_f = ci.conf.lib.clang_getNumOverloadedDecls, ci.conf.lib.clang_getOverloadedDecl
    n_f.argtypes, n_f.restype = [ci.Cursor], ctypes.c_uint
    get_f.argtypes, get_f.restype = [ci.Cursor, ctypes.c_uint], ci.Cursor
    get_f.errcheck = ci.Cursor.from_result
    return [get_f(c, i) for i in range(n_f(c))]


def _overridden(ci, c):
    """The base-class methods that method `c` overrides (libclang's clang_getOverriddenCursors)."""
    f = ci.conf.lib.clang_getOverriddenCursors
    f.argtypes = [ci.Cursor, ctypes.POINTER(ctypes.POINTER(ci.Cursor)), ctypes.POINTER(ctypes.c_uint)]
    f.restype = None
    arr, num = ctypes.POINTER(ci.Cursor)(), ctypes.c_uint(0)
    f(c, ctypes.byref(arr), ctypes.byref(num))
    out = []
    for i in range(num.value):
        cur = arr[i]
        cur._tu = c._tu                      # keep the translation unit alive for the copied cursor
        out.append(cur)
    if num.value:
        d = ci.conf.lib.clang_disposeOverriddenCursors
        d.argtypes, d.restype = [ctypes.POINTER(ci.Cursor)], None
        d(arr)
    return out


def _template_of(ci, c):
    """The template that `c` is a specialization or instantiation of (class or function), or None."""
    f = ci.conf.lib.clang_getSpecializedCursorTemplate
    f.argtypes, f.restype = [ci.Cursor], ci.Cursor
    f.errcheck = ci.Cursor.from_result
    r = f(c)
    return r if r is not None and r.kind.name in ("CLASS_TEMPLATE", "CLASS_TEMPLATE_PARTIAL_SPECIALIZATION",
                                                  "FUNCTION_TEMPLATE") else None


def _primary_template(ci, c):
    """The class template that `c` specializes, or None."""
    r = _template_of(ci, c)
    return r if r is not None and r.kind.name != "FUNCTION_TEMPLATE" else None


def _access(c):
    a = c.access_specifier.name.lower()
    return a if a in ("public", "protected", "private") else None


# ---------- per PR ----------

def conditions_at(source_lines, line):
    """The preprocessor conditions (#if/#ifdef/#ifndef text, `!` prefix in an #else branch) around 1-based `line`."""
    stack = []
    for text in source_lines[:line - 1]:
        d = text.strip()
        if not d.startswith("#"):
            continue
        d = d[1:].strip()
        if d.startswith(("if ", "ifdef ", "ifndef ", "if(")):
            stack.append(d)
        elif d.startswith(("elif", "else")) and stack:
            stack[-1] = "!(" + stack[-1] + ")" + (" " + d if d.startswith("elif") else "")
        elif d.startswith("endif") and stack:
            stack.pop()
    return stack


def analyze_pr(t, rec, resdir):
    """Map one PR's changed lines to entities, first with the default configuration, then, for lines that are
    compiled out (inside #if FEATURE_FLAG), with each `analysis_variants` flag set from target.toml. Entities found
    only under a variant carry "requires_flags": the defines a test needs to reach them."""
    paths = rec["main_files"] + rec.get("deleted_main_files", [])
    diff = git(t.repo, "diff", "-U0", "-M", rec["sha_old"], rec["sha_new"], "--", *paths)
    lines = changed_lines(diff)
    export_paths = t.get("analysis_paths") or t.get("include_dirs") or t["main_source"]
    variants = [()] + [tuple(v) for v in t.get("analysis_variants", [])]
    sides, errors, leftover = {}, {}, {}
    for side, sha in (("old", rec["sha_old"]), ("new", rec["sha_new"])):
        root = export_sources(t, sha, export_paths)
        hits, todo = {}, {path: set(ln[side]) for path, ln in lines.items() if ln[side]}
        errors[side] = {}
        for flags in variants:
            if not any(todo.values()):
                break
            an = Analyzer(t, root, resdir, flags)
            found_here = []
            for path in list(todo):
                ents = an.entities_in(lines[path]["old_path"] if side == "old" else path)
                for line in sorted(todo[path]):
                    e = innermost(ents, line)
                    if e is None:
                        continue
                    todo[path].discard(line)
                    d = an.describe(e["cursor"])
                    key = d["usr"]
                    if key not in hits:
                        hits[key] = dict(d, file=path, lines_changed=0)
                        if flags:
                            hits[key]["requires_flags"] = list(flags)
                        found_here.append(key)
                    hits[key]["lines_changed"] += 1
            for key in found_here:
                h = hits[key]
                if h["access"] == "private" and h["kind"] != "macro":
                    src = h["file"] if side == "new" else lines[h["file"]]["old_path"]
                    h["reached_via"] = an.reached_via(key, src)
            errors[side][" ".join(flags) or "default"] = an.errors
        sides[side] = hits
        leftover[side] = todo
    ents = merge_sides(sides["old"], sides["new"])
    for e in ents:
        e.pop("usr", None)
        e.setdefault("reached_via", [])
    unmapped = []
    for path, left in leftover["new"].items():
        if not left:
            continue
        src = git(t.repo, "show", f"{rec['sha_new']}:{path}").splitlines()
        conds = sorted({" && ".join(conditions_at(src, ln)) for ln in left} - {""})
        unmapped.append({"file": path, "lines": sorted(left), "inside_conditions": conds})
    import clang.cindex as ci
    return {"pr": rec["pr"], "sha_old": rec["sha_old"], "sha_new": rec["sha_new"], "functions": ents,
            "unmapped_lines": sum(len(u["lines"]) for u in unmapped), "unmapped": unmapped,
            "parse_errors": errors, "files": sorted(lines), "tool": _clang_version(ci)}


def _clang_version(ci):
    f = ci.conf.lib.clang_getClangVersion
    f.restype = ci._CXString
    f.errcheck = ci._CXString.from_result
    return f()


def _work(args):
    target, pr, force = args
    t = Target(target)
    out = t.data / "changes" / f"{pr}.json"
    if out.is_file() and not force:
        return pr, "cached", None
    rec = next(r for r in read_jsonl(t.data / "prs.jsonl") if r["pr"] == pr)
    t0 = time.time()
    try:
        res = analyze_pr(t, rec, resource_dir(t))
    except Exception as e:  # one bad PR must not stop a batch; the error is reported and nothing is written
        return pr, "error", f"{type(e).__name__}: {e}"
    res["seconds"] = round(time.time() - t0, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_text(out, json.dumps(res, indent=1, sort_keys=True) + "\n")
    return pr, "ok", res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target")
    ap.add_argument("--pr", type=int, nargs="*", help="only these PRs (default: all of prs.jsonl)")
    ap.add_argument("--force", action="store_true", help="redo PRs that already have data/<t>/changes/<pr>.json")
    ap.add_argument("--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    a = ap.parse_args(argv)
    t = Target(a.target)
    if not (t.repo / ".git").exists():
        sys.exit(f"{t.repo} missing: clone the library there first (see NOTES.md)")
    resource_dir(t)  # fail early with install instructions
    prs = a.pr or [r["pr"] for r in read_jsonl(t.data / "prs.jsonl")]
    jobs = [(t.name, p, a.force) for p in prs]
    counts = defaultdict(int)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for i, (pr, status, res) in enumerate(pool.map(_work, jobs), 1):
            counts[status] += 1
            if status == "error":
                print(f"#{pr}: ERROR {res}", file=sys.stderr)
            elif status == "ok":
                fs = res["functions"]
                priv = sum(f["access"] == "private" for f in fs)
                flagged = sum(1 for f in fs if f.get("requires_flags"))
                errs = sum(n for side in res["parse_errors"].values() for n in side.values())
                print(f"#{pr}: {len(fs)} entities ({priv} private, {flagged} need flags), unmapped lines "
                      f"{res['unmapped_lines']}, parse errors {errs}, {res['seconds']}s", file=sys.stderr)
            if i % 10 == 0:
                print(f"changes: {i}/{len(jobs)} ({time.time() - t0:.0f}s)", file=sys.stderr)
    print(json.dumps(dict(counts)))
    if counts["error"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
