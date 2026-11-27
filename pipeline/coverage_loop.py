#!/usr/bin/env python3
"""Changed-line coverage and the refine loop (pipeline stage "Coverage loop", the DiffTestGen idea).

1. changed lines  = lines added or modified by the PR in the new version, in the target's `coverage_paths` (default
                    include_dirs) (git diff parent..merge, whitespace-only and blank-line changes ignored).
2. measure        = compile every generated test against the NEW environment with --coverage, run it, read gcov JSON,
                    keep only the changed lines. cmake targets (QuantLib, with `coverage_cmake_args`): the test links the
                    merge commit's coverage-instrumented library (env.py, <export>/lib-cov) and runs with GCOV_PREFIX
                    set to its own temp dir, so parallel runs do not share .gcda files; gcov then reads the library
                    objects compiled from a file with a changed file's name (serbia.cpp.gcda for serbia.cpp/.hpp), with
                    their .gcno notes from the build volume, plus the test's own object (header code it instantiated).
3. union          = a changed line is covered if any test ran it. Remaining changed lines are
                      uncovered  executable code that no test ran,
                      macro      line of a #define body: gcov attributes that code to the expansion site, so it cannot be measured here,
                      no_code    other code-like lines gcov has no data for (uninstantiated template, declaration),
                      trivial    blank, comment-only, brace-only, template<...> or preprocessor lines (never a target).
4. loop           = loop(..., refine=fn, rounds=1): give fn the uncovered lines as prompt context, measure the tests it
                    returns, stop when the union stops growing or after `rounds`. fn is injected so this file makes no LLM
                    calls; generate.py supplies it:  fn(context: str, remaining: dict, tests_dir: Path) -> [new test file names].

Input/output: data/<target>/tests/<key>/*.cpp  ->  coverage.json next to them (same key rule as run.py).
Only the new version is measured, so a PR that only deletes lines has no changed lines (reported as n/a).

CLI:  python3 pipeline/coverage_loop.py <target> (--pr N | --merge SHA) [--parent SHA] [--docker] [--std STD]
          [--timeout 10] [--compile-timeout 180] [--jobs 4] [--tests-dir DIR] [--context]
      --context also prints the refine prompt context. Runs in the same container as run.py with --docker (gcov from the image).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
TRIVIAL = re.compile(r"^\s*(//.*|/\*.*|\*.*|[{}();,]*|#\s*\w+.*|template\s*<.*)$")


def die(msg):
    sys.exit(f"coverage_loop.py: {msg}")


def comment_mask(src):
    """1-based line numbers inside a /* */ block comment (interior lines, and first/last lines with no code on them)."""
    inside, mask = False, set()
    for i, line in enumerate(src, 1):
        t = line.strip()
        if inside:
            if "*/" in t:
                inside = False
                if not t.split("*/", 1)[1].strip():
                    mask.add(i)
            else:
                mask.add(i)
        elif t.startswith("/*"):
            if "*/" not in t:
                inside = True
                mask.add(i)
            elif t.endswith("*/"):
                mask.add(i)
    return mask


# ---------------------------------------------------------------- changed lines
def changed_lines(repo, parent, merge, paths):
    """{file: sorted line numbers in the new version} for lines the PR added or modified under `paths`."""
    out = subprocess.run(["git", "-C", str(repo), "diff", "-U0", "--no-color", "-w", "--ignore-blank-lines",
                          parent, merge, "--", *paths], capture_output=True, text=True, check=True).stdout
    changed, cur, in_hunk = {}, None, False
    for line in out.splitlines():
        if line.startswith("diff --git"):
            cur, in_hunk = None, False
        elif not in_hunk and line.startswith("+++ "):
            cur = None if line == "+++ /dev/null" else line[6:]  # strip "+++ b/"
        elif m := HUNK.match(line):
            in_hunk = True
            start, n = int(m[1]), 1 if m[2] is None else int(m[2])
            if cur and n:
                changed.setdefault(cur, []).extend(range(start, start + n))
    return {f: sorted(set(ls)) for f, ls in changed.items()}


# ---------------------------------------------------------------- worker: compile with --coverage, run, read gcov
def worker(a):
    from run import _compile, _run_once  # run.py sits next to this file (mounted at /pipeline in the container)
    changed = {f: set(ls) for f, ls in json.loads(a.changed_json).items()}

    stems = {Path(f).stem for f in changed}
    prefixes = a.prefix if isinstance(a.prefix, list) else [a.prefix]

    def gcda_files(td):
        """.gcda files to read: next to the test (header-only) or, with GCOV_PREFIX, under <td>/gcda: the test's own and
        the library objects compiled from a file named like a changed file. Each gets its .gcno copied next to it."""
        if not a.gcov_prefix:
            return list(Path(td).glob("*.gcda"))
        root, out = Path(td) / "gcda", []
        for g in root.rglob("*.gcda"):
            orig = "/" + str(g.relative_to(root))
            own = orig.startswith(str(td) + "/")
            if not own and g.name.split(".")[0] not in stems:
                continue
            note = Path(orig[:-len(".gcda")] + ".gcno")
            if note.is_file():
                shutil.copyfile(note, g.with_suffix(".gcno"))
                out.append(g)
        return out

    def one(name):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "t"
            ok, err, _ = _compile(Path(a.tests) / name, exe, a.flag, a.std, a.compile_timeout, extra=["--coverage"],
                                  link=a.link_flag)
            res = {"compiled": ok, "exit": None, "timeout": False, "covered": {}, "uncovered": {}, "gcda": 0, "gcov_files": 0}
            if ok:
                run_env = {"GCOV_PREFIX": str(Path(td) / "gcda"), "GCOV_PREFIX_STRIP": "0"} if a.gcov_prefix else None
                r = _run_once(exe, td, a.timeout, run_env)
                res["exit"], res["timeout"] = r["exit"], r["timeout"]  # killed/aborted runs leave no .gcda: no coverage
                cov, unc = {}, {}
                for gcda in gcda_files(td):
                    res["gcda"] += 1
                    cp = subprocess.run(["gcov", "--json-format", "--stdout", str(gcda)], cwd=str(gcda.parent),
                                        capture_output=True, text=True)
                    for doc in filter(None, cp.stdout.split("\n")):
                        try:
                            data = json.loads(doc)
                        except ValueError:
                            continue  # not GNU gcov JSON (e.g. Apple's llvm gcov): counted as no usable data below
                        for f in data.get("files", []):
                            res["gcov_files"] += 1
                            path = os.path.normpath(os.path.join(data.get("current_working_directory", td), f["file"]))
                            rel = next((path[len(p):] for p in prefixes if path.startswith(p)), None)
                            if rel not in changed:
                                continue
                            for ln in f["lines"]:
                                n = ln["line_number"]
                                if n in changed[rel]:
                                    (cov if ln["count"] > 0 else unc).setdefault(rel, set()).add(n)
                res["covered"] = {f: sorted(v) for f, v in cov.items()}
                res["uncovered"] = {f: sorted(v - cov.get(f, set())) for f, v in unc.items()}
            print(f"[cov] {name}: " + (f"compile FAILED" if not ok else
                  f"{sum(map(len, res['covered'].values()))} changed lines covered"), file=sys.stderr, flush=True)
            return name, res
    with ThreadPoolExecutor(a.jobs) as ex:
        json.dump(dict(ex.map(one, a.names)), sys.stdout)


# ---------------------------------------------------------------- host: measure, aggregate, context, loop
def measure(env, tests_dir, names, changed, a):
    from run import launch_worker
    from env import COV_SRC
    wargs = ["--worker", "--tag", "new", *[f"--flag={f}" for f in env.flags("new")], "--tests", str(tests_dir),
             "--std", a.std, "--timeout", str(a.timeout), "--compile-timeout", str(a.compile_timeout),
             "--jobs", str(a.jobs), "--prefix", env.new_dir + "/", "--changed-json", json.dumps(changed),
             "--names", *names]
    volumes = ()
    if getattr(env, "new_lib", None):    # cmake target: link the coverage library, read its notes from the build volume
        if not getattr(env, "cov_lib", None):
            die(f"{env.target}: no coverage library (prepare the environment with coverage=True)")
        wargs[1:1] = [*[f"--link-flag={f}" for f in env.cov_link_flags()], "--prefix", COV_SRC + "/", "--gcov-prefix"]
        volumes = (f"prh-{env.target}-build:/build:ro",)
    per_test = launch_worker(env, "new", tests_dir, "coverage_loop.py", wargs, a.docker, volumes)
    ran = [r for r in per_test.values() if r["compiled"] and not r["timeout"] and r["exit"] == 0]
    if ran and not any(r["gcov_files"] for r in ran):
        sys.exit("coverage_loop.py: " + str(len(ran)) + " programs ran cleanly but none produced usable gcov data "
                 "(" + ("no .gcda files were written" if not any(r["gcda"] for r in ran) else "gcov output unreadable") +
                 "). The host compiler/gcov is probably not GNU (Apple clang on macOS); rerun with --docker.")
    return per_test


def aggregate(env, changed, per_test):
    """Union over tests -> {covered, uncovered, macro, no_code, trivial: {file: [lines]}} for the changed lines."""
    cov, unc = {}, {}
    for res in per_test.values():
        for f, ls in res["covered"].items():
            cov.setdefault(f, set()).update(ls)
        for f, ls in res["uncovered"].items():
            unc.setdefault(f, set()).update(ls)
    out = {k: {} for k in ("covered", "uncovered", "macro", "no_code", "trivial")}
    for f, lines in changed.items():
        src = (Path(env.new_dir) / f).read_text(errors="replace").splitlines()
        mask = comment_mask(src)
        for ln in lines:
            if ln in cov.get(f, ()):
                kind = "covered"
            elif ln in unc.get(f, ()):
                kind = "uncovered"
            elif ln in mask or TRIVIAL.match(src[ln - 1]):
                kind = "trivial"
            elif src[ln - 1].rstrip().endswith("\\"):
                kind = "macro"
            else:
                kind = "no_code"
            out[kind].setdefault(f, []).append(ln)
    return out


def counts(union):
    c = {k: sum(map(len, v.values())) for k, v in union.items()}
    execs = c["covered"] + c["uncovered"]
    c["changed"] = sum(c.values())
    c["exec_coverage"] = round(c["covered"] / execs, 3) if execs else None  # covered / (covered + uncovered)
    return c


def uncovered_context(env, union, ctx=3):
    """Prompt text for the refine round: each changed line no test reached, with surrounding source. '>>' marks a target."""
    mark = {}
    for kind, tag in (("uncovered", "NOT RUN"), ("macro", "MACRO BODY, coverage not measurable"),
                      ("no_code", "NO CODE / NOT INSTANTIATED")):
        for f, ls in union[kind].items():
            for ln in ls:
                mark[(f, ln)] = tag
    parts = []
    for f in sorted({f for f, _ in mark}):
        src = (Path(env.new_dir) / f).read_text(errors="replace").splitlines()
        targets = sorted(ln for (g, ln) in mark if g == f)
        show = sorted({i for t in targets for i in range(max(1, t - ctx), min(len(src), t + ctx) + 1)})
        lines, prev = [f"// {f}"], None
        for i in show:
            if prev is not None and i != prev + 1:
                lines.append("   ...")
            tag = mark.get((f, i))
            lines.append(f"{'>>' if tag else '  '} {i:5d}  {src[i - 1]}" + (f"   // {tag}" if tag else ""))
            prev = i
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def loop(env, tests_dir, a, refine=None, rounds=1):
    """Measure all tests in tests_dir, then (if refine given) up to `rounds` refine rounds. -> coverage report dict."""
    from env import load_cfg
    repo = ROOT / "repos" / env.target
    changed = changed_lines(repo, env.parent, env.merge, load_cfg(env.target).get("coverage_paths") or env.include_dirs)
    names = sorted(p.name for p in Path(tests_dir).glob("*.cpp"))
    if not names:
        die(f"no *.cpp tests in {tests_dir}")
    t0 = time.time()
    per_test = measure(env, tests_dir, names, changed, a) if changed else {}
    union = aggregate(env, changed, per_test)
    history = [{"round": 0, "tests": len(names), **counts(union)}]
    for r in range(1, rounds + 1):
        if refine is None or not (union["uncovered"] or union["macro"] or union["no_code"]):
            break
        added = refine(uncovered_context(env, union), {k: union[k] for k in ("uncovered", "macro", "no_code")}, Path(tests_dir))
        if not added:
            break
        per_test.update(measure(env, tests_dir, added, changed, a))
        union = aggregate(env, changed, per_test)
        history.append({"round": r, "tests": len(per_test), "added": added, **counts(union)})
        if history[-1]["covered"] <= history[-2]["covered"]:
            break  # union stopped growing
    return {"target": env.target, "pr": env.pr, "parent": env.parent, "merge": env.merge, "std": a.std,
            "docker": a.docker, "wall_seconds": round(time.time() - t0, 1), "changed": changed,
            "summary": counts(union), "union": union, "history": history,
            "per_test": {n: {"compiled": t["compiled"], "exit": t["exit"], "timeout": t["timeout"],
                             "covered": sum(map(len, t["covered"].values()))} for n, t in per_test.items()}}


def default_std(target, pr):
    """The per-PR C++ standard (pipeline/common.pr_std). Imported here, not at the top: workers run this file inside
    the container, where only pipeline/ is mounted and no target config is needed."""
    sys.path.insert(0, str(ROOT))
    from pipeline.common import Target, pr_std
    return pr_std(Target(target), pr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--merge")
    ap.add_argument("--parent")
    ap.add_argument("--docker", action="store_true")
    ap.add_argument("--std", help="C++ standard (default: chosen per PR, see common.pr_std)")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--compile-timeout", type=float, default=180)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tests-dir")
    ap.add_argument("--variant", choices=["main", "baseline"], default="main",
                    help="baseline: data/<t>/baseline/<pr> (the basic pipeline); ignored with --tests-dir")
    ap.add_argument("--context", action="store_true", help="print the refine prompt context")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--tag", default="", help=argparse.SUPPRESS)
    ap.add_argument("--flag", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--tests", help=argparse.SUPPRESS)
    ap.add_argument("--prefix", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--link-flag", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--gcov-prefix", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--changed-json", help=argparse.SUPPRESS)
    ap.add_argument("--names", nargs="+", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        return worker(a)
    if not a.target or not (a.pr or a.merge):
        ap.error("need <target> and --pr or --merge")
    a.std = a.std or default_std(a.target, a.pr)
    from env import prepare
    env = prepare(a.target, a.pr, a.merge, a.parent, a.docker, coverage=True)
    key = str(env.pr) if env.pr else env.merge[:12]
    tests_dir = Path(a.tests_dir or ROOT / "data" / a.target / ("tests" if a.variant == "main" else a.variant) / key).resolve()
    rep = loop(env, tests_dir, a)
    (tests_dir / "coverage.json").write_text(json.dumps(rep, indent=2) + "\n")
    s = rep["summary"]
    print(f"{a.target} {key}: changed lines in {', '.join(rep['changed']) or '(none)'} "
          f"({rep['wall_seconds']}s, {'docker' if a.docker else 'host'})")
    for n, t in rep["per_test"].items():
        print(f"  {t['covered']:>4} covered  {n}" + ("" if t["compiled"] else "  (compile FAILED)"))
    print(f"changed={s['changed']} covered={s['covered']} uncovered={s['uncovered']} macro={s['macro']} no_code={s['no_code']} "
          f"trivial={s['trivial']} exec_coverage={s['exec_coverage'] if s['exec_coverage'] is not None else 'n/a'}")
    if a.context:
        print("\n" + uncovered_context(env, rep["union"]))
    print(f"wrote {tests_dir / 'coverage.json'}")


if __name__ == "__main__":
    main()
