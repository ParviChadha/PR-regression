#!/usr/bin/env python3
"""Scale driver: run the whole pipeline (generate -> run -> fix -> classify, then report) over many PRs, resumably.

Usage:  python3 pipeline/batch.py <target> (--all | --prs N [N ...]) [--limit K] [--docker] [--dry-run]
                                  [--model M] [--classify-model M] [--redo generate,run,fix,classify]
                                  [--max-failures 5] [--no-report]
Needs GEMINI_API_KEY (in .env or exported). Run it in a terminal you can leave open; it prints one line per stage.

Resumable: a stage is skipped when its output is current, so rerunning after a quota stop, a crash or a Ctrl-C continues
where it stopped (LLM responses are also cached by request, so an interrupted stage costs nothing to repeat).
  generate  done when generated.json exists
  run       done when results.json covers every *.cpp in the PR folder
  fix       done when fix.py has run (manifest "fix") or made repairs, or nothing is left to repair
  classify  done when classification.json was made from the current results.json (fingerprint match)
Once any stage actually runs for a PR, every later stage for that PR runs too (its input changed).

Each stage runs as its own process (pipeline/<stage>.py), so one PR's failure cannot take the batch down; its output goes
to cache/logs/<target>/<pr>.log (tail -f it to watch the 503 retries). Exit code 3 from a stage means the daily LLM
quota is spent: the batch stops there (quotas reset at midnight Pacific) and still writes the report for what is done.
A PR that fails any other way is recorded, skipped, and retried on the next run; --max-failures stops a run that is
failing systematically before it spends the day's quota.

Order: seeded PRs first (they have a known answer), then prs.jsonl order. --limit K stops after K PRs that needed work.
--redo generate also redoes everything after it (it deletes repairs); --redo run/fix/classify redo just that stage.
Requests per PR: 1 generate + up to 2 fix + 1 classify = at most 4 (the plan's 10 to 25 was a guess).
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
from pipeline.common import Target, read_jsonl  # noqa: E402
import fix  # noqa: E402
import llm  # noqa: E402

STAGES = ("generate", "run", "fix", "classify")
LLM_STAGES = {"generate": 1, "fix": 2, "classify": 1}  # worst-case requests per PR


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- what is done
def stage_done(stage, tests_dir):
    d = Path(tests_dir)
    manifest, results = load(d / "generated.json"), load(d / "results.json")
    if stage == "generate":
        return manifest is not None
    if stage == "run":
        return bool(manifest and results) and {p.name for p in d.glob("*.cpp")} <= set(results["tests"])
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


def pending_stages(tests_dir, redo=()):
    """Stages that must run for this PR, in order (each stage that runs makes all later ones run)."""
    redo, out, forced = set(redo), [], False
    if "generate" in redo:
        redo |= {"run", "fix", "classify"}
    for st in STAGES:
        if forced or st in redo or not stage_done(st, tests_dir):
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
def command(stage, target, pr, args):
    py = sys.executable
    base = {"generate": ["generate.py", "--model", args.model], "run": ["run.py"], "fix": ["fix.py", "--model", args.model],
            "classify": ["classify.py", "--model", args.classify_model or args.model]}[stage]
    cmd = [py, str(HERE / base[0]), target, "--pr", str(pr), *base[1:]]
    if args.docker and stage in ("run", "fix"):
        cmd.append("--docker")
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
    redo = [s for s in (args.redo or "").split(",") if s]
    plan = []
    for r in rows:
        td = data_dir / "tests" / str(r["pr"])
        if not args.skip_commit_check and not commits_present(t.repo, r):
            out["skipped"][r["pr"]] = "commit missing locally: git -C repos/<target> fetch origin"
            continue
        st = pending_stages(td, redo)
        if st:
            plan.append((r["pr"], td, st))
    if args.limit:
        plan = plan[:args.limit]
    worst = sum(LLM_STAGES.get(s, 0) for _, _, st in plan for s in st)
    left = None
    try:
        left = llm.limits(args.model)[1] - llm.calls_today(args.model)
    except Exception:  # noqa: BLE001  (quota info is advisory)
        pass
    say(f"{len(rows)} PRs selected, {len(plan)} need work, {len(out['skipped'])} skipped; at most {worst} LLM requests"
        + (f" (about {left} left today for {args.model})" if left is not None else ""))
    for pr, why in out["skipped"].items():
        say(f"  #{pr}: skipped, {why}")
    if args.dry_run:
        for pr, _, st in plan:
            say(f"  #{pr}: would run {', '.join(st)}")
        return out
    for pr, td, st in plan:
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
            say(f"#{pr}: {', '.join(done)} | {verdict_line(td)} ({time.time() - t0:.0f}s)")
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
    ap.add_argument("--redo", help="comma list of stages to redo: generate,run,fix,classify")
    ap.add_argument("--max-failures", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true", help="show what would run, run nothing")
    ap.add_argument("--no-report", action="store_true")
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
        recs, s = report.build(t.name, t.data, ROOT / "results" / t.name)
        print(f"report: {s['prs_checked']} PRs with results; regression candidates {s['regression_candidates'] or 'none'}; "
              f"calls est {s['llm_calls']['total_est']}; wrote results/{t.name}/report.md")
    if not a.dry_run:
        print(f"done: {len(out['ok'])} ok, {len(out['failed'])} failed, {len(out['skipped'])} skipped"
              + (", stopped by quota" if out["quota_stop"] else ""))
    sys.exit(3 if out["quota_stop"] else (1 if out["failed"] else 0))


if __name__ == "__main__":
    main()
