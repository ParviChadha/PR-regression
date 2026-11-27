"""Tests for the basic-vs-improved comparison (variant "baseline") and for stale run results (source hashes).
No network, no LLM. Run:  python3 -m unittest pipeline.test_baseline"""
import argparse
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from pipeline.common import Target, tests_dir  # noqa: E402
import batch  # noqa: E402
import fix  # noqa: E402
import generate  # noqa: E402
import llm  # noqa: E402
import report  # noqa: E402
from test_batch import make_pr  # noqa: E402

RUN = {"exit": 0, "timeout": False, "sha256": "h", "stdout": "x"}
SIDE = {"compile_ok": True, "compile_stderr": "", "stable": True, "runs": [RUN]}
SAME = {"status": "same", "compile_failed_on": None, "old": SIDE, "new": SIDE}

ADDED = ("## Changed functions", "## Existing upstream tests")


def real_json_target():
    t = Target("nlohmann-json")
    if not (t.repo / ".git").exists() or not (t.data / "context" / "4958.txt").is_file():
        raise unittest.SkipTest("needs repos/nlohmann-json and data/nlohmann-json/context")
    return t


class Prompts(unittest.TestCase):
    def test_baseline_generation_prompt_drops_only_the_two_added_sections(self):
        t = real_json_target()
        rec, gh = generate.load_pr(t, 4958)
        s_main, p_main, _ = generate.build_generate_prompt(t, rec, gh, 20)
        s_base, p_base, _ = generate.build_generate_prompt(t, rec, gh, 20, "baseline")
        self.assertEqual(s_main, s_base)                                  # same rules
        for h in ADDED:
            self.assertIn(h, p_main)
            self.assertNotIn(h, p_base)
        for h in ("## Description", "## Diff of the library source", "# Task"):
            self.assertIn(h, p_base)
        self.assertEqual(p_main, generate.build_generate_prompt(t, rec, gh, 20, "main")[1])   # main unchanged

    def test_fix_follows_the_variant_and_classify_always_sees_the_full_pr(self):
        t = real_json_target()
        rec, gh = generate.load_pr(t, 4958)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "gen_01.cpp").write_text("int main() {}\n")
            items = [{"file": "gen_01.cpp", "intent": "x", "kind": "compile", "errors": "e"}]
            _, base = fix.build_prompt(t, rec, gh, d, items, "baseline")
            _, main = fix.build_prompt(t, rec, gh, d, items)
        self.assertNotIn(ADDED[0], base)
        self.assertIn(ADDED[0], main)
        section, _ = generate.pr_section(t, rec, gh)                       # what classify.build_prompt uses
        self.assertIn(ADDED[0], section)

    def test_tests_dir(self):
        t = SimpleNamespace(data=Path("/d"))
        self.assertEqual(tests_dir(t, 5), Path("/d/tests/5"))
        self.assertEqual(tests_dir(t, 5, "baseline"), Path("/d/baseline/5"))


class Commands(unittest.TestCase):
    def test_baseline_commands(self):
        a = argparse.Namespace(model="m", classify_model=None, docker=True, baseline=True)
        ref = batch.command("refine", "t", 5, a)
        self.assertEqual(Path(ref[1]).name, "coverage_loop.py")           # measure only, no request
        self.assertNotIn("--refine-only", ref)
        self.assertIn("--docker", ref)
        for st in batch.STAGES:
            self.assertEqual(batch.command(st, "t", 5, a)[-2:], ["--variant", "baseline"])
        a.baseline = False
        for st in batch.STAGES:
            self.assertNotIn("--variant", batch.command(st, "t", 5, a))
        self.assertEqual(Path(batch.command("refine", "t", 5, a)[1]).name, "generate.py")


class BaselineBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        self.t = SimpleNamespace(name="t", repo=Path(self.tmp.name), data=self.data, get=lambda k, d=None: d)
        self.args = argparse.Namespace(redo="", limit=None, max_failures=5, dry_run=False, model="m", classify_model=None,
                                       docker=False, skip_commit_check=True, no_refine=False, baseline=True)
        for p in (mock.patch.object(llm, "calls_today", return_value=0), mock.patch.object(llm, "limits", return_value=(15, 500))):
            p.start()
            self.addCleanup(p.stop)

    def test_uses_the_baseline_folder_and_counts_no_refine_request(self):
        make_pr(self.data, 1)                                              # the main run of PR 1 is complete
        lines, calls = [], []
        batch.batch(self.t, [{"pr": 1}], self.args, runner=lambda st, *a: calls.append(st) or 0, say=lines.append,
                    data_dir=self.data, log_dir=Path(self.tmp.name) / "logs")
        self.assertEqual(calls, ["generate", "refine", "run", "classify"])   # baseline not done yet
        self.assertIn("[baseline]", lines[0])
        self.assertIn("at most 4 LLM requests", lines[0] + " ".join(lines))  # 1 generate + 2 fix + 1 classify
        calls.clear()
        make_pr(self.data / "baseline_root", 1)                            # unrelated folder: nothing changes
        self.args.baseline = False
        batch.batch(self.t, [{"pr": 1}], self.args, runner=lambda st, *a: calls.append(st) or 0, say=lines.append,
                    data_dir=self.data, log_dir=Path(self.tmp.name) / "logs")
        self.assertEqual(calls, [])                                        # the main run is untouched


class StaleResults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def with_hash(self, d):
        res = json.loads((d / "results.json").read_text())
        for name, r in res["tests"].items():
            r["source_sha256"] = batch.source_sha256(d / name)
        (d / "results.json").write_text(json.dumps(res))
        h = hashlib.sha256((d / "results.json").read_bytes()).hexdigest()   # keep classification current
        doc = json.loads((d / "classification.json").read_text())
        (d / "classification.json").write_text(json.dumps({**doc, "results_sha256": h}))

    def test_a_program_rewritten_after_it_ran_makes_run_stale(self):
        d = make_pr(self.tmp.name, 1)
        self.with_hash(d)
        self.assertEqual(batch.pending_stages(d), [])
        (d / "gen_01.cpp").write_text("int main() { return 1; }\n")     # regenerated outside batch.py
        self.assertEqual(batch.pending_stages(d), ["run", "fix", "classify"])

    def test_results_without_hashes_are_trusted(self):
        d = make_pr(self.tmp.name, 2)
        (d / "gen_01.cpp").write_text("int main() { return 1; }\n")
        self.assertEqual(batch.pending_stages(d), [])

    def test_run_and_fix_record_the_hash(self):
        import run
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "gen_01.cpp"
            p.write_bytes(b"int main() {}\n")
            self.assertEqual(run.source_sha256(p), hashlib.sha256(b"int main() {}\n").hexdigest())
            q = Path(d) / "crlf.cpp"
            q.write_bytes(b"int main() {}\r\n")                         # a Windows checkout of the same file
            self.assertEqual(run.source_sha256(q), run.source_sha256(p))
            self.assertEqual(batch.source_sha256(q), run.source_sha256(p))
            side = SAME["old"]
            with mock.patch.object(run, "run_batch", return_value={"gen_01.cpp": side}):
                out = fix.evaluate(None, Path(d), ["gen_01.cpp"], argparse.Namespace())
            self.assertEqual(out["gen_01.cpp"]["source_sha256"], run.source_sha256(p))


def write(root, folder, pr, progs, coverage=None, verdict=False, differing=0):
    d = Path(root) / folder / str(pr)
    d.mkdir(parents=True)
    entries = [{"file": f"gen_{i:02d}.cpp", "round": 0} for i in range(1, progs + 1)]
    diff = dict(SAME, status="output_diff")
    tests = {e["file"]: (diff if i < differing else SAME) for i, e in enumerate(entries)}
    (d / "generated.json").write_text(json.dumps({"pr": pr, "tests": entries}))
    (d / "results.json").write_text(json.dumps({"pr": pr, "wall_seconds": 1, "tests": tests}))
    clusters = [{"id": "C1", "status": "output_diff", "failed_on": None, "programs": ["gen_01.cpp"],
                 "verdict": "unintended" if verdict else "intended", "confidence": "high", "reason": "r"}] if differing else []
    (d / "classification.json").write_text(json.dumps({"model": "m", "clusters": clusters,
        "pr_verdict": {"regression_candidate": verdict, "unintended_clusters": ["C1"] if verdict else []}}))
    if coverage:
        hist = [{"round": i, "exec_coverage": c} for i, c in enumerate(coverage)]
        (d / "coverage.json").write_text(json.dumps({"history": hist, "summary": {"changed": 10, "covered": 8, "uncovered": 2}}))


class Comparison(unittest.TestCase):
    def test_comparison_table_and_coverage_split(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "baseline", 1, 10, coverage=[0.4], differing=0)
            write(root, "tests", 1, 20, coverage=[0.6, 0.9], verdict=True, differing=2)
            write(root, "baseline", 2, 10, coverage=[0.8], differing=1)
            write(root, "tests", 2, 20, coverage=[0.8, 0.8], differing=1)
            write(root, "tests", 3, 20, coverage=[1.0])                      # main only: not compared
            (Path(root) / "seeded.json").write_text(json.dumps({"seeded": [{"pr": 1, "expected": "unintended"}]}))
            doc = report.compare("x", root, Path(root) / "out")
            md = (Path(root) / "out" / "comparison.md").read_text()
        self.assertEqual(doc["prs"], 2)
        self.assertEqual(doc["coverage"], {"prs": 2, "basic": 60.0, "improved_before_loop": 70.0, "improved_after_loop": 85.0})
        self.assertIn("| Mean changed-line coverage | 60.0% | 70.0% | 85.0% |", md)
        self.assertIn("| Regression candidates | 0: none | 1: #1 |", md)
        self.assertIn("| Seeded regressions found | 0/1 | 1/1 |", md)
        self.assertIn("| #1 | 40% | 60% -> 90% | 0 | 2 |", md)
        self.assertNotIn("| #3 |", md)

    def test_no_baseline_means_no_comparison(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "tests", 1, 5)
            self.assertIsNone(report.compare("x", root, Path(root) / "out"))

    def test_baseline_report_goes_to_its_own_folder(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "baseline", 1, 5, differing=1, verdict=True)
            recs, s = report.build("x", root, Path(root) / "out", variant="baseline")
            md = (Path(root) / "out" / "report.md").read_text()
        self.assertEqual(s["prs_checked"], 1)
        self.assertIn("# Report: x (baseline pipeline)", md)
        self.assertIn("`data/x/baseline/1/gen_01.cpp`", md)


if __name__ == "__main__":
    unittest.main()
