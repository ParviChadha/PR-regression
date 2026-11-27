#!/usr/bin/env python3
"""Scale driver: run the whole pipeline (generate -> refine -> run -> fix -> classify, then report) over many PRs, resumably.

Usage:  python3 pipeline/batch.py <target> (--all | --prs N [N ...]) [--limit K] [--docker] [--dry-run] [--baseline]
                                  [--model M] [--classify-model M] [--redo generate,refine,run,fix,classify]
                                  [--max-failures 5] [--no-refine] [--no-report]
Needs GEMINI_API_KEY (in .env or exported). Run it in a terminal you can leave open; it prints one line per stage.

Resumable: a stage is skipped when its output is current, so rerunning after a quota stop, a crash or a Ctrl-C continues
where it stopped (LLM responses are also cached by request, so an interrupted stage costs nothing to repeat).
  generate  done when generated.json exists
  refine    done when coverage.json exists. Measures changed-line coverage of the generated programs and makes ONE more
            request for programs aimed at the lines nobody reached (no request if everything measurable is covered).
            Without it a PR whose programs never reach the change looks like "no difference"; #6078's did. Skipped for
            cmake targets without `coverage_cmake_args` (no coverage build of the library: duckdb) and with --no-refine.
  run       done when results.json covers every *.cpp in the PR folder, with the C++ standard and the source text each
            program ran with (a program regenerated outside batch.py makes it stale)
  fix       done when fix.py has run (manifest "fix") or made repairs, or nothing is left to repair
  classify  done when classification.json was made from the current results.json (fingerprint match)
Once any stage actually runs for a PR, every later stage for that PR runs too (its input changed).
C++ standard: chosen per PR by common.pr_std (C++20 when every changed entity exists only under -std=c++20, else the
target's default_std, c++17). Each stage script picks it itself; generated.json, coverage.json and results.json record
it, and a stage made with a different standard counts as not done, so a PR whose standard changes is redone from
generate (its programs were written for the other standard).

Each stage runs as its own process (pipeline/<stage>.py), so one PR's failure cannot take the batch down; its output goes
to cache/logs/<target>/<pr>.log (tail -f it to watch the 503 retries). Exit code 3 from a stage means the daily LLM
quota is spent: the batch stops there (quotas reset at midnight Pacific) and still writes the report for what is done.
A PR that fails any other way is recorded, skipped, and retried on the next run; --max-failures stops a run that is
failing systematically before it spends the day's quota.

Order: seeded PRs first (they have a known answer), then prs.jsonl order. --limit K stops after K PRs that needed work.
--redo generate also redoes everything after it (it deletes repairs); --redo refine/run/fix/classify redo that stage
and, because its output changed, the ones after it.
Requests per PR: 1 generate + 1 refine + up to 2 fix + 1 classify = at most 5 (the plan's 10 to 25 was a guess).

--baseline runs the basic pipeline of the proposal's comparison (common.VARIANTS) into data/<t>/baseline/<pr>: the
generation and fix prompts leave out the changed functions and the upstream tests, and "refine" only MEASURES coverage
(coverage_loop.py, no request), so at most 4 requests per PR. Classification is the same as in the main pipeline. It
writes results/<t>/baseline/report.md and results/<t>/comparison.md (basic vs improved on the PRs both have run).
Run it on a subset, e.g. --limit 30 (seeded PRs first, then prs.jsonl order, as for the main run).
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from pipeline.common import VARIANTS, Target, pr_std, read_jsonl  # noqa: E402
import fix  # noqa: E402
import llm  # noqa: E402

STAGES = ("generate", "refine", "run", "fix", "classify")
LLM_STAGES = {"generate": 1, "refine": 1, "fix": 2, "classify": 1}  # worst-case requests per PR


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- what is done
def same_std(doc, std):
    """True when `doc` (generated.json, coverage.json or results.json) was made with C++ standard `std`. Files from
    before the standard was chosen per PR carry no "std" and were all made as C++17. std None: do not check."""
    return std is None or (doc or {}).get("std", "c++17") == std


def source_sha256(path):
    """As run.source_sha256 (CRLF counts as LF); not imported from run.py, which is also a container worker."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sources_unchanged(d, results):
    """True unless a program was rewritten after it ran: results.json records each program's source hash (run.py), and
    a mismatch means its results describe text that no longer exists. Results from before hashes were recorded carry
    none and are trusted (rerun them with --redo run if their programs were regenerated outside batch.py)."""
    for name, r in results["tests"].items():
        h = r.get("source_sha256")
        if h and (not (d / name).is_file() or source_sha256(d / name) != h):
            return False
    return True


def stage_done(stage, tests_dir, std=None):
    """std: the C++ standard this PR's programs must use (common.pr_std). A stage done with another standard is not
    done: the programs were written for, or compiled as, the wrong language version."""
    d = Path(tests_dir)
    manifest, results = load(d / "generated.json"), load(d / "results.json")
    if stage == "generate":
        return manifest is not None and same_std(manifest, std)
    if stage == "refine":
        cov = load(d / "coverage.json")
        return bool(manifest and cov and cov.get("history")) and same_std(cov, std)
    if stage == "run":
        return (bool(manifest and results) and {p.name for p in d.glob("*.cpp")} <= set(results["tests"])
                and same_std(results, std) and sources_unchanged(d, results))
    if stage == "fix":
        if not (manifest and results):
            return False
        if manifest.get("fix") or any(e.get("fixes") for e in manifest["tests"]):
            return True
        return not fix.pick(manifest, results["tests"], 1)
    if stage == "classify":
        doc = load(d / "classification.json")
        if not (doc and results):
            return False
        now = hashlib.sha256((d / "results.json").read_bytes()).hexdigest()
        if "results_sha256" in doc:
            return doc["results_sha256"] == now
        return (d / "classification.json").stat().st_mtime >= (d / "results.json").stat().st_mtime  # older files
    raise ValueError(stage)


def nothing_to_fix(tests_dir):
    manifest, results = load(Path(tests_dir) / "generated.json"), load(Path(tests_dir) / "results.json")
    return not (manifest and results) or not fix.pick(manifest, results["tests"], 1)


def pending_stages(tests_dir, redo=(), stages=STAGES, std=None):
    """Stages that must run for this PR, in order (each stage that runs makes all later ones run)."""
    redo, out, forced = set(redo), [], False
    if "generate" in redo:
        redo |= set(STAGES)
    for st in stages:
        if forced or st in redo or not stage_done(st, tests_dir, std):
            out.append(st)
            forced = True
    return out


# ---------------------------------------------------------------- selection
def select_prs(rows, wanted=None, seeded_first=True):
    rows = [r for r in rows if r.get("verdict", "checked") == "checked" and (not wanted or r["pr"] in wanted)]
    if seeded_first:
        rows = [r for r in rows if r.get("seeded")] + [r for r in rows if not r.get("seeded")]
    return rows


def commits_present(repo, rec):
    for k in ("sha_old", "sha_new"):
        if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{rec[k]}^{{commit}}"], capture_output=True).returncode:
            return False
    return True


# ---------------------------------------------------------------- running
def variant_of(args):
    return "baseline" if getattr(args, "baseline", False) else "main"


def command(stage, target, pr, args):
    py = sys.executable
    variant = variant_of(args)
    base = {"generate": ["generate.py", "--model", args.model],
            "refine": ["generate.py", "--refine-only", "--model", args.model], "run": ["run.py"],
            "fix": ["fix.py", "--model", args.model],
            "classify": ["classify.py", "--model", args.classify_model or args.model]}[stage]
    if variant != "main" and stage == "refine":
        base = ["coverage_loop.py"]          # the basic pipeline only measures coverage: no refine request
    cmd = [py, str(HERE / base[0]), target, "--pr", str(pr), *base[1:]]
    if args.docker and stage in ("refine", "run", "fix"):
        cmd.append("--docker")
    if variant != "main":
        cmd += ["--variant", variant]
    return cmd


def run_stage(stage, target, pr, args, log_dir):
    """-> exit code. Output (stdout and stderr) is appended to cache/logs/<target>/<pr>.log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{pr}.log", "a", encoding="utf-8") as log:
        log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {stage} =====\n")
        log.flush()
        return subprocess.run(command(stage, target, pr, args), stdout=log, stderr=subprocess.STDOUT).returncode


def verdict_line(tests_dir):
    doc = load(Path(tests_dir) / "classification.json")
    if not doc:
        return "not classified"
    v = doc["pr_verdict"]
    return ("REGRESSION CANDIDATE " + ",".join(v["unintended_clusters"])) if v["regression_candidate"] else \
        ("no difference" if not doc["clusters"] else "differences all intended/unclear")


def batch(t, rows, args, runner=run_stage, say=print, data_dir=None, log_dir=None):
    """Process `rows`; -> {"ok": [...], "failed": {pr: stage}, "skipped": {pr: why}, "quota_stop": bool, "calls_needed": n}."""
    data_dir = Path(data_dir or t.data)
    log_dir = Path(log_dir or ROOT / "cache" / "logs" / t.name)
    out = {"ok": [], "failed": {}, "skipped": {}, "quota_stop": False, "ran": 0}
    variant = variant_of(args)
    redo = [s for s in (args.redo or "").split(",") if s]
    no_cov = t.get("build_mode") == "cmake" and not t.get("coverage_cmake_args")   # duckdb: no coverage build
    stages = tuple(st for st in STAGES if st != "refine" or not (args.no_refine or no_cov))
    plan = []
    for r in rows:
        td = data_dir / VARIANTS[variant] / str(r["pr"])
        if not args.skip_commit_check and not commits_present(t.repo, r):
            out["skipped"][r["pr"]] = "commit missing locally: git -C repos/<target> fetch origin"
            continue
        std = pr_std(t, r["pr"])
        st = pending_stages(td, redo, stages, std)
        if st:
            plan.append((r["pr"], td, st, std))
    if args.limit:
        plan = plan[:args.limit]
    per_stage = dict(LLM_STAGES, **({"refine": 0} if variant != "main" else {}))
    worst = sum(per_stage.get(s, 0) for _, _, st, _ in plan for s in st)
    left = None
    try:
        left = llm.limits(args.model)[1] - llm.calls_today(args.model)
    except Exception:  # noqa: BLE001  (quota info is advisory)
        pass
    say(("[baseline] " if variant != "main" else "") + f"{len(rows)} PRs selected, {len(plan)} need work, {len(out['skipped'])} skipped; at most {worst} LLM requests"
        + (f" (about {left} left today for {args.model})" if left is not None else ""))
    for pr, why in out["skipped"].items():
        say(f"  #{pr}: skipped, {why}")
    if args.dry_run:
        for pr, _, st, std in plan:
            say(f"  #{pr}: would run {', '.join(st)}" + (f" (as {std})" if std != t.get("default_std", "c++17") else ""))
        return out
    for pr, td, st, std in plan:
        if len(out["failed"]) >= args.max_failures:
            say(f"stopping: {len(out['failed'])} PRs failed (see cache/logs); fix the cause and rerun")
            break
        t0, done = time.time(), []
        for stage in st:
            if stage == "fix" and nothing_to_fix(td):
                done.append("fix(nothing to repair)")
                continue
            s0 = time.time()
            code = runner(stage, t.name, pr, args, log_dir)
            if code == 3:
                out["quota_stop"] = True
                say(f"#{pr}: {stage} hit the daily LLM quota. Stopping; rerun after midnight Pacific to continue.")
                break
            if code:
                out["failed"][pr] = stage
                say(f"#{pr}: {stage} FAILED (exit {code}); see {log_dir / (str(pr) + '.log')}")
                break
            done.append(f"{stage} {time.time() - s0:.0f}s")
        else:
            out["ok"].append(pr)
            say(f"#{pr}: {', '.join(done)} | {verdict_line(td)} ({time.time() - t0:.0f}s"
                + (f", {std}" if std != t.get("default_std", "c++17") else "") + ")")
        out["ran"] += 1
        if out["quota_stop"]:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target")
    ap.add_argument("--all", action="store_true", help="every PR in data/<t>/prs.jsonl")
    ap.add_argument("--prs", type=int, nargs="+")
    ap.add_argument("--limit", type=int, help="stop after this many PRs that needed work")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL, help="generation and fix model")
    ap.add_argument("--classify-model", help="model for classify.py (default: --model)")
    ap.add_argument("--docker", action="store_true", help="compile and run in the prh-<target> container")
    ap.add_argument("--redo", help="comma list of stages to redo: generate,refine,run,fix,classify")
    ap.add_argument("--max-failures", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true", help="show what would run, run nothing")
    ap.add_argument("--no-refine", action="store_true", help="skip the coverage/refine stage (saves 1 request per PR)")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--baseline", action="store_true",
                    help="run the basic pipeline (no changed functions, no upstream tests, no refine) into data/<t>/baseline/")
    ap.add_argument("--skip-commit-check", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if not (a.all or a.prs):
        ap.error("need --all or --prs")
    bad = set((a.redo or "").split(",")) - set(STAGES) - {""}
    if bad:
        ap.error(f"unknown stage in --redo: {sorted(bad)}")
    t = Target(a.target)
    rows = select_prs(read_jsonl(t.data / "prs.jsonl"), set(a.prs or []) or None)
    if not rows:
        sys.exit("batch.py: no matching PRs in prs.jsonl")
    out = batch(t, rows, a)
    if not a.dry_run and not a.no_report:
        import report
        if a.baseline:
            recs, s = report.build(t.name, t.data, ROOT / "results" / t.name / "baseline", variant="baseline")
            print(f"report: {s['prs_checked']} baseline PRs with results; wrote results/{t.name}/baseline/report.md")
            cmp = report.compare(t.name, t.data, ROOT / "results" / t.name)
            if cmp:
                print(f"comparison: {cmp['prs']} PRs run by both pipelines; wrote results/{t.name}/comparison.md")
        else:
            recs, s = report.build(t.name, t.data, ROOT / "results" / t.name)
            print(f"report: {s['prs_checked']} PRs with results; regression candidates {s['regression_candidates'] or 'none'}; "
                  f"calls est {s['llm_calls']['total_est']}; wrote results/{t.name}/report.md")
    if not a.dry_run:
        print(f"done: {len(out['ok'])} ok, {len(out['failed'])} failed, {len(out['skipped'])} skipped"
              + (", stopped by quota" if out["quota_stop"] else ""))
    sys.exit(3 if out["quota_stop"] else (1 if out["failed"] else 0))


if __name__ == "__main__":
    main()
