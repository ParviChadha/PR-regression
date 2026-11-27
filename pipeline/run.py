#!/usr/bin/env python3
"""Run + compare (pipeline stage "Run both"): compile each generated test against the old and new
environment from env.py, run it N times under a timeout, and classify the pair.

Input:  data/<target>/tests/<key>/*.cpp   standalone programs; key = PR number (or merge SHA[:12] with --merge)
Output: data/<target>/tests/<key>/results.json, plus a summary on stdout.

Per-test status:
  same          compiles on both, stable on both, identical stdout + exit code
  output_diff   compiles on both, stable on both, outputs differ        -> candidate behavioral change
  compile_diff  compiles on exactly one side (compile_failed_on says which), or fails on both sides with a different
                first compiler error (compile_failed_on = "both") -> candidate API change;
                fix.py should not "repair" it, the failure is the signal
  flaky         outputs differ between reruns on the same version       -> dropped
  invalid       fails to compile on both, or times out on both          -> dropped (fix.py may repair compile errors)

CLI:  python3 pipeline/run.py <target> (--pr N | --merge SHA) [--parent SHA] [--docker]
          [--std STD] [--runs 3] [--timeout 10] [--compile-timeout 180] [--jobs 4] [--tests-dir DIR]
--docker runs each version's batch in its own container (image prh-<target>, no network, memory-limited);
without it the batch runs on the host with host g++ (cmake targets such as duckdb need --docker: their library is built
in the container, and generated tests link against it). The same file runs inside the container as the worker
(`--worker`, internal), so both modes share one code path. Flaky detection compares (timeout, exit code,
sha256 of stdout); stderr is kept (first run) for fix.py but not compared.
"""
import argparse, hashlib, json, os, re, signal, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KEEP = 20_000  # bytes of stdout kept per test (hashes cover the full output)


def die(msg):
    sys.exit(f"run.py: {msg}")


# ---------------------------------------------------------------- worker: compile + run one batch
def _read_capped(path):
    h, n, head = hashlib.sha256(), 0, b""
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
            n += len(chunk)
            if len(head) < KEEP:
                head += chunk[:KEEP - len(head)]
    return h.hexdigest(), n, head.decode("utf-8", "replace")


def _run_once(exe, cwd, timeout, extra_env=None):
    out, err = Path(cwd) / ".stdout", Path(cwd) / ".stderr"
    t0, timed_out = time.time(), False
    with open(out, "wb") as fo, open(err, "wb") as fe:
        # ulimit caps file output so a runaway print loop cannot fill the disk; new session so a timeout kills children too
        p = subprocess.Popen(["sh", "-c", 'ulimit -f 131072; exec "$0"', str(exe)], stdin=subprocess.DEVNULL,
                             stdout=fo, stderr=fe, cwd=cwd, start_new_session=True,
                             env={**os.environ, **extra_env} if extra_env else None)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            rc, timed_out = None, True
    sha, nbytes, text = _read_capped(out)
    return {"exit": rc, "timeout": timed_out, "sha256": sha, "bytes": nbytes,
            "seconds": round(time.time() - t0, 3), "stdout": text, "stderr": _read_capped(err)[2][:2000]}


def _compile_errors(err, limit=4000):
    """Compiler output for the record: the first `error:` lines (each clipped, template dumps are huge) so the root
    cause survives; falls back to the tail when the text has no `error:` line (linker errors, crashes)."""
    lines = [l[:400] for l in err.splitlines() if "error" in l.lower()]
    text = "\n".join(lines)
    return text[:limit] if text else err[-limit:]


def _compile(src, exe, flags, std, timeout, extra=(), link=()):
    t0 = time.time()
    try:
        cp = subprocess.run(["g++", f"-std={std}", "-O0", *flags, *extra, str(src), "-o", str(exe), *link],
                            capture_output=True, text=True, timeout=timeout)
        ok, err = cp.returncode == 0, cp.stderr
    except subprocess.TimeoutExpired:
        ok, err = False, f"compile timed out after {timeout}s"
    return ok, _compile_errors(err), round(time.time() - t0, 2)


def worker(a):
    def one(name):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "t"
            ok, err, secs = _compile(Path(a.tests) / name, exe, a.flag, a.std, a.compile_timeout, link=a.link_flag)
            res = {"compile_ok": ok, "compile_seconds": secs, "compile_stderr": "" if ok else err,
                   "stable": True, "runs": []}
            if ok:
                runs = [_run_once(exe, td, a.timeout) for _ in range(a.runs)]
                res["stable"] = len({(r["timeout"], r["exit"], r["sha256"]) for r in runs}) == 1
                for r in runs[1:]:
                    del r["stdout"], r["stderr"]  # first run keeps the text
                res["runs"] = runs
            if not ok:
                msg = "compile FAILED"
            else:
                r0 = res["runs"][0]
                msg = "compile ok, " + ("timed out" if r0["timeout"] else f"exit {r0['exit']}") \
                    + ("" if res["stable"] else ", output differs between reruns")
            print(f"[{a.tag}] {name}: {msg}", file=sys.stderr, flush=True)
            return name, res
    with ThreadPoolExecutor(a.jobs) as ex:
        json.dump(dict(ex.map(one, a.names)), sys.stdout)


# ---------------------------------------------------------------- host: orchestrate + classify
def error_signature(stderr):
    """First compiler error with the location, quoted names and numbers removed, so only its kind is compared."""
    for line in stderr.splitlines():
        if "error" in line.lower():
            msg = line.split("error:", 1)[-1]
            msg = re.sub(r"‘[^’]*’|'[^']*'|\"[^\"]*\"", "''", msg)
            return re.sub(r"\d+", "N", msg).strip()
    return ""


def classify(old, new):
    """-> (status, compile_failed_on or None) for one test's old/new worker results."""
    if not old["compile_ok"] and not new["compile_ok"]:
        # same failure on both sides is a broken test; a different first error means the change altered what the
        # compiler reports for this program (e.g. a clean "no match" before, a hard error inside the library after)
        if error_signature(old["compile_stderr"]) != error_signature(new["compile_stderr"]):
            return "compile_diff", "both"
        return "invalid", None
    if old["compile_ok"] != new["compile_ok"]:
        return "compile_diff", "old" if not old["compile_ok"] else "new"
    if not (old["stable"] and new["stable"]):
        return "flaky", None
    o, n = old["runs"][0], new["runs"][0]
    if o["timeout"] and n["timeout"]:
        return "invalid", None
    same = (o["timeout"], o["exit"], o["sha256"]) == (n["timeout"], n["exit"], n["sha256"])
    return ("same" if same else "output_diff"), None


def launch_worker(env, which, tests_dir, script, wargs, docker, volumes=()):
    """Run `pipeline/<script> --worker <wargs>` on the host or in the prh-<target> container (no network, memory-limited;
    exports, tests and pipeline/ mounted read-only at the same absolute paths); -> parsed JSON from its stdout."""
    if docker:
        base = Path(env.old_dir).parent  # exports mounted at the same absolute path, so Env paths work unchanged
        cmd = ["docker", "run", "--rm", "--name", f"prh-{env.target}-{Path(script).stem}-{which}-{os.getpid()}",
               "--network", "none", "--memory", "3g", "--pids-limit", "1024",
               "-v", f"{base}:{base}:ro", "-v", f"{tests_dir}:{tests_dir}:ro", "-v", f"{HERE}:/pipeline:ro",
               *[x for v in volumes for x in ("-v", v)],
               f"prh-{env.target}", "python3", f"/pipeline/{script}", *wargs]
    else:
        cmd = [sys.executable, str(HERE / script), *wargs]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    if r.returncode:
        die(f"{script} {which} batch failed (exit {r.returncode})")
    return json.loads(r.stdout)


def run_batch(env, which, tests_dir, names, a):
    wargs = ["--worker", "--tag", which, *[f"--flag={f}" for f in env.flags(which)],
             *[f"--link-flag={f}" for f in env.link_flags(which)], "--tests", str(tests_dir),
             "--std", a.std, "--runs", str(a.runs), "--timeout", str(a.timeout),
             "--compile-timeout", str(a.compile_timeout), "--jobs", str(a.jobs), "--names", *names]
    return launch_worker(env, which, tests_dir, "run.py", wargs, a.docker)


def source_sha256(path):
    """Hash of a program's source as it was compiled. batch.py compares it with the file on disk: a program rewritten
    after it ran (regenerated with generate.py outside batch.py) makes the run stage stale instead of keeping results
    that belong to the old text. CRLF counts as LF, so a Windows checkout (core.autocrlf) matches a Mac/Linux one."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_pr(a):
    sys.path.insert(0, str(HERE))
    from env import prepare
    env = prepare(a.target, a.pr, a.merge, a.parent, a.docker)
    key = str(env.pr) if env.pr else env.merge[:12]
    tests_dir = Path(a.tests_dir or ROOT / "data" / a.target / ("tests" if a.variant == "main" else a.variant) / key).resolve()
    names = sorted(p.name for p in tests_dir.glob("*.cpp"))
    if not names:
        die(f"no *.cpp tests in {tests_dir}")
    t0 = time.time()
    with ThreadPoolExecutor(2) as ex:
        fo, fn = (ex.submit(run_batch, env, w, tests_dir, names, a) for w in ("old", "new"))
        old, new = fo.result(), fn.result()
    tests, counts = {}, {}
    for n in names:
        status, failed_on = classify(old[n], new[n])
        tests[n] = {"status": status, "compile_failed_on": failed_on, "source_sha256": source_sha256(tests_dir / n),
                    "old": old[n], "new": new[n]}
        counts[status] = counts.get(status, 0) + 1
    out = {"target": a.target, "pr": env.pr, "parent": env.parent, "merge": env.merge, "std": a.std,
           "runs": a.runs, "timeout": a.timeout, "docker": a.docker, "wall_seconds": round(time.time() - t0, 1),
           "summary": counts, "tests": tests}
    (tests_dir / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"{a.target} {key}: old={env.parent[:9]} new={env.merge[:9]} std={a.std} runs={a.runs} "
          f"({out['wall_seconds']}s, {'docker' if a.docker else 'host'})")
    for n, t in tests.items():
        extra = f" (fails on {t['compile_failed_on']})" if t["compile_failed_on"] else ""
        print(f"  {t['status']:<13}{n}{extra}")
    print(f"summary: {counts}\nwrote {tests_dir / 'results.json'}")


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
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--compile-timeout", type=float, default=180)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tests-dir")
    ap.add_argument("--variant", choices=["main", "baseline"], default="main",
                    help="baseline: data/<t>/baseline/<pr> (the basic pipeline); ignored with --tests-dir")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--tag", default="", help=argparse.SUPPRESS)
    ap.add_argument("--flag", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--link-flag", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--tests", help=argparse.SUPPRESS)
    ap.add_argument("--names", nargs="+", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        return worker(a)
    if not a.target or not (a.pr or a.merge):
        ap.error("need <target> and --pr or --merge")
    a.std = a.std or default_std(a.target, a.pr)
    run_pr(a)


if __name__ == "__main__":
    main()
