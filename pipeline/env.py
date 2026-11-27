#!/usr/bin/env python3
"""Old/new environments for one PR (pipeline stage "Build both").

For a PR with parent commit A and merge commit B, make source exports of both under
cache/worktrees/<target>/<sha>/ and describe how to compile (and link) a test against either.

build_mode in targets/<t>/target.toml:
  header-only  the environment is the export of include_dirs; no build. (nlohmann/json)
  cmake        the export of export_paths is built inside the prh-<t> container: the library at the parent commit,
               then incrementally at the merge commit, in one persistent build volume (prh-<t>-build) with ccache
               (prh-<t>-ccache). Each commit's shared library is copied to <export>/lib/. Needs docker. (duckdb)
               With coverage=True (coverage_loop.py) and `coverage_cmake_args` in target.toml, the merge commit is also
               built with coverage instrumentation in a tree of its own (/build/cov-src -> /build/cov) and its library
               copied to <export>/lib-cov/. The .gcno notes stay in /build/cov, which holds the last commit built
               there (/build/cov/.prh-commit), so the coverage build is redone whenever another commit was built in
               between; it is incremental and shares ccache. (QuantLib; not set up for duckdb, whose build is too slow.)

Commits are exported with `git archive`, so the upstream clone in repos/<t> is only read, never written.
Exports are idempotent: an export with a .prh-ok marker is reused; a partial one is redone. A built library has a
.prh-built marker. Between commits the build tree is updated with `rsync --checksum` without preserving mtimes, so
ninja only rebuilds files whose content changed.

CLI:   python3 pipeline/env.py <target> (--pr N | --merge SHA) [--parent SHA] [--check] [--docker] [--std c++17]
       prints the Env as JSON on stdout; --check also compiles `smoke_source` (or `#include <smoke_header>`) against
       old and new; for cmake targets it links and runs it. cmake targets need --docker (they build in the container).
Python: from env import prepare, compile_check   (run.py uses these)
        JOBS=<n> sets parallel compile jobs for cmake builds (default 4: duckdb unity TUs are memory-hungry).

How the merge commit is found for --pr N: data/<t>/prs.jsonl if it has a record with "pr" == N and
"sha_new" (the merge commit; "sha_old" is its parent), as written by pipeline/collect.py; otherwise a squash-merge subject ending in "(#N)" in the clone's history.
"""
import argparse, json, os, shlex, shutil, subprocess, sys
from dataclasses import dataclass, asdict
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def die(msg):
    sys.exit(f"env.py: {msg}")


def load_cfg(target):
    path = ROOT / "targets" / target / "target.toml"
    if not path.is_file():
        die(f"unknown target '{target}': {path} not found")
    return tomllib.loads(path.read_text())


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        die(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


@dataclass
class Env:
    target: str
    pr: int | None
    parent: str
    merge: str
    old_dir: str
    new_dir: str
    include_dirs: list  # relative to each export
    old_lib: str | None = None  # directory holding the built shared library (cmake mode), else None
    new_lib: str | None = None
    lib_name: str | None = None  # e.g. "duckdb" for -lduckdb
    cov_lib: str | None = None  # cmake + coverage: directory holding the merge commit's coverage-instrumented library

    def flags(self, which):
        """-I flags to compile a test against 'old' (parent) or 'new' (merge)."""
        base = {"old": self.old_dir, "new": self.new_dir}[which]
        return [f"-I{base}/{d}" for d in self.include_dirs]

    def link_flags(self, which):
        """Flags that go AFTER the source file when linking (empty for header-only targets)."""
        lib = {"old": self.old_lib, "new": self.new_lib}[which]
        return [f"-L{lib}", f"-l{self.lib_name}", f"-Wl,-rpath,{lib}"] if lib else []

    def cov_link_flags(self):
        """Link flags for the coverage-instrumented library of the merge commit (empty unless prepared with coverage)."""
        return [f"-L{self.cov_lib}", f"-l{self.lib_name}", f"-Wl,-rpath,{self.cov_lib}"] if self.cov_lib else []


def _from_prs_jsonl(target, pr):
    path = ROOT / "data" / target / "prs.jsonl"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        rec = json.loads(line) if line.strip() else {}
        if rec.get("pr") == pr and rec.get("sha_new"):
            return rec
    return None


def _from_subject(repo, pr):
    out = git(repo, "log", "--format=%H%x09%s", f"--grep=(#{pr})", "--fixed-strings")
    hits = [l.split("\t")[0] for l in out.splitlines() if l.endswith(f"(#{pr})")]
    if len(hits) != 1:
        die(f"PR #{pr}: expected exactly one squash-merge commit with subject ending '(#{pr})', found {len(hits)}; pass --merge")
    return {"sha_new": hits[0]}


def resolve_commits(target, repo, pr=None, merge=None, parent=None):
    """-> (parent_sha, merge_sha), both full SHAs."""
    if merge is None:
        if pr is None:
            die("need pr or merge")
        rec = _from_prs_jsonl(target, pr) or _from_subject(repo, pr)
        merge, parent = rec["sha_new"], parent or rec.get("sha_old")
    merge = git(repo, "rev-parse", "--verify", f"{merge}^{{commit}}")
    if parent is None:
        parents = git(repo, "rev-list", "--parents", "-n", "1", merge).split()[1:]
        if len(parents) != 1:
            die(f"{merge[:9]} has {len(parents)} parents (not a squash/rebase merge); pass --parent")
        parent = parents[0]
    return git(repo, "rev-parse", "--verify", f"{parent}^{{commit}}"), merge


def export(target, repo, sha, paths):
    """Export `paths` of commit `sha` to cache/worktrees/<target>/<sha>; reuse a finished export."""
    dest = ROOT / "cache" / "worktrees" / target / sha
    if (dest / ".prh-ok").is_file():
        return dest
    tmp = dest.with_name(sha + ".tmp")
    for d in (tmp, dest):
        if d.exists():
            shutil.rmtree(d)  # leftovers of an interrupted export (inside git-ignored cache/)
    tmp.mkdir(parents=True)
    arc = subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", sha, "--", *paths],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(tmp)], stdin=arc.stdout, check=True)
    arc.stdout.close()
    err = arc.stderr.read().decode()
    if arc.wait():
        die(f"git archive {sha[:9]} failed: {err.strip()}")
    (tmp / ".prh-ok").write_text(sha + "\n")
    tmp.rename(dest)
    return dest


def build_libraries(target, cfg, parent_dir, merge_dir):
    """cmake mode: build the shared library for each commit (parent first, then merge incrementally) in the
    prh-<target> container; skip commits that already have a .prh-built marker. Serialized by flock on the build volume."""
    todo = [d for d in (Path(parent_dir), Path(merge_dir)) if not (d / ".prh-built").is_file()]
    if not todo:
        return
    base = Path(parent_dir).parent
    lib = cfg["library"]
    args = " ".join(shlex.quote(a) for a in cfg["cmake_args"])
    script = "\n".join([
        "set -e",
        "exec 9>/build/.prh-lock; flock 9",
        "cd /build",
    ] + [
        "\n".join([
            f"echo '== {d.name[:9]}'",
            f"rsync -rlpgoD --checksum --delete --exclude=/lib --exclude=/.prh-ok --exclude=/.prh-built {shlex.quote(str(d))}/ /build/src/",
            f"cmake -S /build/src -B /build/obj {args}",
            f"cmake --build /build/obj --target {shlex.quote(cfg['build_target'])} --parallel \"${{JOBS:-4}}\"",
            f"mkdir -p {shlex.quote(str(d))}/lib && cp /build/obj/{shlex.quote(lib)} {shlex.quote(str(d))}/lib/ && touch {shlex.quote(str(d))}/.prh-built",
        ]) for d in todo])
    cmd = ["docker", "run", "--rm", "--name", f"prh-{target}-env-{os.getpid()}",
           "-v", f"{base}:{base}", "-v", f"prh-{target}-build:/build", "-v", f"prh-{target}-ccache:/ccache",
           "-e", "CCACHE_DIR=/ccache", "-e", "CCACHE_MAXSIZE=5G", "-e", f"JOBS={os.environ.get('JOBS', '4')}",
           f"prh-{target}", "bash", "-c", script]
    print(f"env.py: building {', '.join(d.name[:9] for d in todo)} in prh-{target} (cold builds take a long time)", file=sys.stderr)
    if subprocess.run(cmd).returncode:
        die("library build failed (see output above)")


COV_SRC, COV_OBJ = "/build/cov-src", "/build/cov"   # coverage build tree in the prh-<target>-build volume


def build_coverage_library(target, cfg, merge_dir):
    """cmake mode: the merge commit's library with coverage instrumentation, for coverage_loop.py. Built in its own
    tree so the normal build tree (/build/src, /build/obj) is untouched; cmake_args then coverage_cmake_args (later
    -D values win, e.g. CMAKE_BUILD_TYPE=Debug). A no-op when /build/cov already holds this commit. -> lib-cov dir."""
    d = Path(merge_dir)
    sha = d.name
    lib = cfg["library"]
    args = " ".join(shlex.quote(a) for a in [*cfg["cmake_args"], *cfg["coverage_cmake_args"]])
    out = shlex.quote(str(d / "lib-cov"))
    script = "\n".join([
        "set -e",
        "exec 9>/build/.prh-lock; flock 9",
        f"if [ \"$(cat {COV_OBJ}/.prh-commit 2>/dev/null)\" = {sha} ] && [ -f {out}/{shlex.quote(Path(lib).name)} ]; then exit 0; fi",
        f"echo '== coverage build {sha[:9]}'",
        f"mkdir -p {COV_SRC} {COV_OBJ}",
        f"rsync -rlpgoD --checksum --delete --exclude=/lib --exclude=/lib-cov --exclude=/.prh-ok --exclude=/.prh-built "
        f"{shlex.quote(str(d))}/ {COV_SRC}/",
        f"cmake -S {COV_SRC} -B {COV_OBJ} {args}",
        f"cmake --build {COV_OBJ} --target {shlex.quote(cfg['build_target'])} --parallel \"${{JOBS:-4}}\"",
        f"mkdir -p {out} && cp {COV_OBJ}/{shlex.quote(lib)} {out}/",
        f"echo {sha} > {COV_OBJ}/.prh-commit",
    ])
    base = d.parent
    cmd = ["docker", "run", "--rm", "--name", f"prh-{target}-cov-{os.getpid()}",
           "-v", f"{base}:{base}", "-v", f"prh-{target}-build:/build", "-v", f"prh-{target}-ccache:/ccache",
           "-e", "CCACHE_DIR=/ccache", "-e", "CCACHE_MAXSIZE=5G", "-e", f"JOBS={os.environ.get('JOBS', '4')}",
           f"prh-{target}", "bash", "-c", script]
    if subprocess.run(cmd).returncode:
        die("coverage library build failed (see output above)")
    return str(d / "lib-cov")


def prepare(target, pr=None, merge=None, parent=None, docker=False, coverage=False):
    cfg = load_cfg(target)
    mode = cfg.get("build_mode")
    if mode not in ("header-only", "cmake"):
        die(f"{target}: build_mode {mode!r} not implemented (header-only, cmake)")
    if mode == "cmake" and not docker:
        die(f"{target}: build_mode 'cmake' builds in the container; pass --docker")
    repo = ROOT / "repos" / target
    if not (repo / ".git").exists():
        die(f"{repo} missing; run scripts/fetch.sh {target}")
    parent, merge = resolve_commits(target, repo, pr, merge, parent)
    inc = cfg["include_dirs"]
    paths = cfg.get("export_paths", inc)
    old_dir, new_dir = export(target, repo, parent, paths), export(target, repo, merge, paths)
    env = Env(target, pr, parent, merge, str(old_dir), str(new_dir), inc)
    if mode == "cmake":
        build_libraries(target, cfg, old_dir, new_dir)
        env.old_lib, env.new_lib = str(old_dir / "lib"), str(new_dir / "lib")
        env.lib_name = Path(cfg["library"]).name.removeprefix("lib").split(".")[0]
        if coverage:
            if not cfg.get("coverage_cmake_args"):
                die(f"{target}: changed-line coverage needs coverage_cmake_args in target.toml (no coverage build set up)")
            env.cov_lib = build_coverage_library(target, cfg, new_dir)
    return env


def smoke_source(target):
    cfg = load_cfg(target)
    return cfg.get("smoke_source") or f"#include <{cfg['smoke_header']}>\nint main() {{}}\n"


def compile_check(env, which, source, std="c++17", docker=False, extra=(), run=False):
    """Compile C++ `source` (a string) against the old or new environment. -> CompletedProcess (returncode 0 = ok).
    Default is a syntax-only compile; run=True links (cmake targets: against that commit's library) and runs the program.
    docker=True runs in the prh-<target> image, with the exports mounted read-only and no network."""
    gxx = ["g++", f"-std={std}", "-x", "c++", "-", *env.flags(which), *extra]
    if run:
        cmd = ["sh", "-c", 'g++ "$@" -o /tmp/prh-smoke && /tmp/prh-smoke', "sh", *gxx[1:], *env.link_flags(which)]
    else:
        cmd = [*gxx[:1], "-fsyntax-only", *gxx[1:]]
    if docker:
        base = Path(env.old_dir).parent
        cmd = ["docker", "run", "--rm", "-i", "--network", "none", "-v", f"{base}:{base}:ro",
               f"prh-{env.target}", *cmd]
    return subprocess.run(cmd, input=source, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--merge", help="merge/squash commit SHA (instead of --pr)")
    ap.add_argument("--parent", help="override parent SHA")
    ap.add_argument("--check", action="store_true", help="smoke-compile against old and new (cmake targets: link and run)")
    ap.add_argument("--docker", action="store_true", help="compile in the prh-<target> container (required for cmake targets)")
    ap.add_argument("--std", default="c++17")
    a = ap.parse_args()
    if not (a.pr or a.merge):
        ap.error("need --pr or --merge")
    env = prepare(a.target, a.pr, a.merge, a.parent, a.docker)
    print(json.dumps(asdict(env), indent=2))
    if a.check:
        src, bad = smoke_source(a.target), 0
        for which in ("old", "new"):
            r = compile_check(env, which, src, a.std, a.docker, run=env.old_lib is not None)
            print(f"check {which}: {'ok' if r.returncode == 0 else 'FAILED'}", file=sys.stderr)
            if r.returncode:
                print(r.stderr[-2000:], file=sys.stderr)
                bad += 1
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
