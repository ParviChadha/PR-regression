"""Tests for batch.py with a fake stage runner: no subprocess, no network, no key. Run:  python3 -m unittest pipeline.test_batch"""
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
import batch  # noqa: E402
import llm  # noqa: E402

SAME = {"status": "same", "compile_failed_on": None,
        "old": {"compile_ok": True, "compile_stderr": "", "stable": True, "runs": []},
        "new": {"compile_ok": True, "compile_stderr": "", "stable": True, "runs": []}}
BROKEN = {"status": "invalid", "compile_failed_on": None,
          "old": {"compile_ok": False, "compile_stderr": "x.cpp:1: error: boom", "stable": True, "runs": []},
          "new": {"compile_ok": False, "compile_stderr": "x.cpp:1: error: boom", "stable": True, "runs": []}}


def make_pr(data, pr, stages=("generate", "run", "fix", "classify"), broken=False, fixed=False):
    d = Path(data) / "tests" / str(pr)
    d.mkdir(parents=True, exist_ok=True)
    if "generate" in stages:
        entries = [{"file": "gen_01.cpp", "round": 0}]
        (d / "gen_01.cpp").write_text("int main(){}\n")
        manifest = {"tests": entries}
        if fixed:
            manifest["fix"] = {"rounds_max": 2}
        (d / "generated.json").write_text(json.dumps(manifest))
    if "run" in stages:
        (d / "results.json").write_text(json.dumps({"tests": {"gen_01.cpp": BROKEN if broken else SAME}}))
    if "classify" in stages:
        h = hashlib.sha256((d / "results.json").read_bytes()).hexdigest()
        (d / "classification.json").write_text(json.dumps({"results_sha256": h, "clusters": [],
                                                           "pr_verdict": {"regression_candidate": False, "unintended_clusters": []}}))
    return d


class DoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)

    def test_fresh_and_complete(self):
        d = make_pr(self.data, 1, stages=())
        self.assertEqual(batch.pending_stages(d), ["generate", "run", "fix", "classify"])
        d = make_pr(self.data, 2)
        self.assertEqual(batch.pending_stages(d), [])

    def test_a_new_cpp_file_means_run_again_and_later_stages_follow(self):
        d = make_pr(self.data, 3)
        (d / "gen_02.cpp").write_text("int main(){}\n")
        self.assertEqual(batch.pending_stages(d), ["run", "fix", "classify"])

    def test_changed_results_make_classification_stale_only(self):
        d = make_pr(self.data, 4)
        (d / "results.json").write_text(json.dumps({"tests": {"gen_01.cpp": SAME}, "wall_seconds": 99}))
        self.assertEqual(batch.pending_stages(d), ["classify"])

    def test_fix_is_pending_only_when_something_can_be_repaired_and_has_not_run(self):
        d = make_pr(self.data, 5, stages=("generate", "run"), broken=True)
        self.assertEqual(batch.pending_stages(d), ["fix", "classify"])
        d = make_pr(self.data, 6, broken=True, fixed=True)           # fix.py already ran: do not spend requests again
        self.assertEqual(batch.pending_stages(d), [])
        d = make_pr(self.data, 7, stages=("generate", "run", "classify"))  # nothing to repair
        self.assertEqual(batch.pending_stages(d), [])

    def test_redo(self):
        d = make_pr(self.data, 8)
        self.assertEqual(batch.pending_stages(d, ["classify"]), ["classify"])
        self.assertEqual(batch.pending_stages(d, ["run"]), ["run", "fix", "classify"])
        self.assertEqual(batch.pending_stages(d, ["generate"]), ["generate", "run", "fix", "classify"])

    def test_legacy_classification_without_fingerprint_uses_mtime(self):
        d = make_pr(self.data, 9)
        doc = json.loads((d / "classification.json").read_text())
        del doc["results_sha256"]
        (d / "classification.json").write_text(json.dumps(doc))
        self.assertEqual(batch.pending_stages(d), [])


class SelectTests(unittest.TestCase):
    def test_seeded_first_filter_and_verdict(self):
        rows = [{"pr": 1, "verdict": "checked"}, {"pr": 2, "verdict": "bot"}, {"pr": 3, "verdict": "checked", "seeded": True},
                {"pr": 4, "verdict": "checked"}]
        self.assertEqual([r["pr"] for r in batch.select_prs(rows)], [3, 1, 4])
        self.assertEqual([r["pr"] for r in batch.select_prs(rows, {4, 2})], [4])

    def test_command_line(self):
        a = argparse.Namespace(model="m1", classify_model="m2", docker=True)
        self.assertEqual(batch.command("classify", "t", 5, a)[-2:], ["--model", "m2"])
        self.assertNotIn("--docker", batch.command("generate", "t", 5, a))
        self.assertIn("--docker", batch.command("run", "t", 5, a))
        self.assertIn("--docker", batch.command("fix", "t", 5, a))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        self.logs = Path(self.tmp.name) / "logs"
        self.t = SimpleNamespace(name="t", repo=Path(self.tmp.name) / "no-repo", data=self.data)
        self.args = argparse.Namespace(redo="", limit=None, max_failures=5, dry_run=False, model="m", classify_model=None,
                                       docker=False, skip_commit_check=True)
        self.calls, self.lines = [], []
        p = mock.patch.object(llm, "calls_today", return_value=0)
        q = mock.patch.object(llm, "limits", return_value=(15, 500))
        p.start(), q.start()
        self.addCleanup(p.stop)
        self.addCleanup(q.stop)

    def rows(self, *prs):
        for pr in prs:
            (self.data / "tests" / str(pr)).mkdir(parents=True)
        return [{"pr": pr, "sha_old": "a", "sha_new": "b"} for pr in prs]

    def runner(self, codes=None):
        codes = codes or {}

        def run(stage, target, pr, args, log_dir):
            self.calls.append((pr, stage))
            return codes.get((pr, stage), 0)
        return run

    def go(self, rows, **kw):
        self.args.__dict__.update(kw)
        return batch.batch(self.t, rows, self.args, runner=self.runner(self._codes), say=self.lines.append,
                           data_dir=self.data, log_dir=self.logs)

    _codes = {}

    def test_runs_every_pending_stage_in_order_for_every_pr(self):
        out = self.go(self.rows(1, 2))
        self.assertEqual(self.calls, [(1, "generate"), (1, "run"), (1, "classify"), (2, "generate"), (2, "run"), (2, "classify")])
        # fix is skipped here: the fake runner writes no results, so there is nothing to repair
        self.assertEqual(out["ok"], [1, 2])

    def test_a_failing_pr_is_recorded_and_the_batch_continues(self):
        self._codes = {(1, "run"): 1}
        out = self.go(self.rows(1, 2))
        self.assertEqual(out["failed"], {1: "run"})
        self.assertEqual(out["ok"], [2])
        self.assertNotIn((1, "classify"), self.calls)

    def test_quota_exit_stops_everything_after_that_stage(self):
        self._codes = {(1, "generate"): 3}
        out = self.go(self.rows(1, 2, 3))
        self.assertTrue(out["quota_stop"])
        self.assertEqual(self.calls, [(1, "generate")])
        self.assertEqual(out["ok"], [])

    def test_max_failures_and_limit_and_dry_run(self):
        self._codes = {(p, "generate"): 1 for p in (1, 2, 3, 4)}
        out = self.go(self.rows(1, 2, 3, 4), max_failures=2)
        self.assertEqual(sorted(out["failed"]), [1, 2])
        self.assertIn("stopping", " ".join(self.lines))
        self.calls.clear(), self.lines.clear()
        self._codes = {}
        out = self.go([{"pr": p, "sha_old": "a", "sha_new": "b"} for p in (1, 2, 3, 4)], max_failures=5, limit=1)
        self.assertEqual({c[0] for c in self.calls}, {1})
        self.calls.clear()
        self.go([{"pr": 1, "sha_old": "a", "sha_new": "b"}], limit=None, dry_run=True)
        self.assertEqual(self.calls, [])
        self.assertTrue(any("would run generate" in l for l in self.lines))

    def test_finished_prs_cost_nothing_and_missing_commits_are_skipped(self):
        make_pr(self.data, 7)
        out = self.go([{"pr": 7, "sha_old": "a", "sha_new": "b"}])
        self.assertEqual(self.calls, [])
        self.assertIn("0 need work", self.lines[0])
        self.args.skip_commit_check = False
        out = self.go([{"pr": 8, "sha_old": "a", "sha_new": "b"}], skip_commit_check=False)
        self.assertEqual(list(out["skipped"]), [8])
        self.assertEqual(self.calls, [])

    def test_header_reports_worst_case_requests(self):
        self.go(self.rows(1, 2), dry_run=True)
        self.assertIn("at most 8 LLM requests", self.lines[0])  # (1 generate + 2 fix + 1 classify) x 2


if __name__ == "__main__":
    unittest.main()
