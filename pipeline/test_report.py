"""Tests for report.py on small hand-made PR folders. Run:  python3 -m unittest pipeline.test_report"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import report  # noqa: E402


def ok(out, stable=True):
    return {"compile_ok": True, "compile_stderr": "", "stable": stable,
            "runs": [{"exit": 0, "timeout": False, "sha256": out, "stdout": out}]}


def bad(err="x.cpp:1:1: error: boom"):
    return {"compile_ok": False, "compile_stderr": err, "stable": True, "runs": []}


def res(status, old, new, failed=None):
    return {"status": status, "compile_failed_on": failed, "old": old, "new": new}


def write_pr(root, pr, entries, results, classification=None, coverage=None, wall=10.0):
    d = Path(root) / "tests" / str(pr)
    d.mkdir(parents=True)
    (d / "generated.json").write_text(json.dumps({"pr": pr, "model": "m", "tests": entries}))
    (d / "results.json").write_text(json.dumps({"pr": pr, "wall_seconds": wall, "tests": results}))
    if classification:
        (d / "classification.json").write_text(json.dumps(classification))
    if coverage:
        (d / "coverage.json").write_text(json.dumps(coverage))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # PR 1: gen_01 fails on old (repaired by gen_04), gen_02 invalid (repaired by gen_05, round 2 -> still invalid),
        # gen_03 fails on new only.  Live: gen_03, gen_04, gen_05.
        entries = [{"file": "gen_01.cpp", "round": 0, "superseded_by": "gen_04.cpp"},
                   {"file": "gen_02.cpp", "round": 0, "superseded_by": "gen_05.cpp"},
                   {"file": "gen_03.cpp", "round": 0},
                   {"file": "gen_04.cpp", "round": 1, "fixes": "gen_01.cpp", "kind": "detect"},
                   {"file": "gen_05.cpp", "round": 1, "fixes": "gen_02.cpp", "kind": "compile"}]
        results = {"gen_01.cpp": res("compile_diff", bad(), ok("1\n"), "old"),
                   "gen_02.cpp": res("invalid", bad(), bad()),
                   "gen_03.cpp": res("compile_diff", ok("1\n"), bad("h:2:3: error: no match for call"), "new"),
                   "gen_04.cpp": res("output_diff", ok("supported: 0\n"), ok("supported: 1\n")),
                   "gen_05.cpp": res("invalid", bad(), bad())}
        cls = {"model": "m", "clusters": [
            {"id": "C1", "status": "output_diff", "failed_on": None, "programs": ["gen_04.cpp"], "verdict": "intended", "confidence": "high", "reason": "r1"},
            {"id": "C2", "status": "compile_diff", "failed_on": "new", "programs": ["gen_03.cpp"], "verdict": "unintended", "confidence": "high", "reason": "r2"}],
            "pr_verdict": {"regression_candidate": True, "unintended_clusters": ["C2"]}}
        cov = {"history": [{"exec_coverage": 0.5}, {"exec_coverage": 0.75}], "summary": {"changed": 30, "covered": 6, "uncovered": 2}}
        write_pr(self.root, 1, entries, results, cls, cov, wall=12.5)
        # PR 2: two clean programs, nothing differs, never classified
        write_pr(self.root, 2, [{"file": "gen_01.cpp", "round": 0}, {"file": "gen_02.cpp", "round": 0}],
                 {"gen_01.cpp": res("same", ok("a"), ok("a")), "gen_02.cpp": res("flaky", ok("a", False), ok("a"))}, wall=3.5)
        (self.root / "seeded.json").write_text(json.dumps({"seeded": [
            {"pr": 1, "expected": "unintended", "note": "n1"}, {"pr": 2, "expected": "intended"}, {"pr": 99, "expected": "unintended"}]}))


class ReportTests(Fixture):
    def test_collect_pr_counts_raw_versus_final_and_estimates_calls(self):
        p = report.collect_pr(self.root / "tests" / "1")
        self.assertEqual((p["generated"], p["in_use"], p["repairs"]), (3, 3, 2))
        # as generated: gen_01 fails new? no: new ok. gen_02 fails both. gen_03 fails new.  -> new 1/3, both 0/3
        self.assertEqual((p["raw_compile_new"], p["raw_compile_both"]), (1, 0))
        # in use: gen_03 (new fails), gen_04 (both ok), gen_05 (both fail) -> new 1/3, both 1/3
        self.assertEqual((p["final_compile_new"], p["final_compile_both"]), (1, 1))
        self.assertEqual(p["status"], {"compile_diff": 1, "output_diff": 1, "invalid": 1})
        self.assertEqual(p["differing"], 2)
        self.assertEqual((p["deterministic"], p["compiled_both_in_use"]), (1, 1))
        self.assertEqual(p["llm_calls_est"], 1 + 1 + 1)  # generation + fix round 1 + classification
        self.assertEqual(p["coverage"], {"first": 0.5, "last": 0.75, "rounds": 2, "changed": 30, "measurable": 8})
        c2 = p["classification"]["clusters"][1]
        self.assertTrue(c2["old"].startswith("output: 1") and c2["new"].startswith("compile error: no match for call"))

    def test_pr_without_results_is_skipped_and_flaky_is_not_deterministic(self):
        (self.root / "tests" / "3").mkdir()
        self.assertIsNone(report.collect_pr(self.root / "tests" / "3"))
        p2 = report.collect_pr(self.root / "tests" / "2")
        self.assertEqual((p2["deterministic"], p2["compiled_both_in_use"], p2["differing"]), (1, 2, 0))
        self.assertIsNone(p2["classification"])

    def test_summary_and_seeded_recall(self):
        recs, s = report.build("t", self.root, self.root / "out")
        self.assertEqual(s["prs_checked"], 2)
        self.assertEqual(s["generated"], 5)
        # as generated: PR 1 compiles on both for 0 of 3, PR 2 for 2 of 2; new version: 1 of 3 and 2 of 2
        self.assertEqual(s["compile_success"]["raw_new"], 60.0)       # 3 / 5
        self.assertEqual(s["compile_success"]["raw_both"], 40.0)      # 2 / 5
        # in use: PR 1 gen_03 (new fails), gen_04 (ok), gen_05 (both fail)
        self.assertEqual(s["compile_success"]["final_new"], 60.0)     # (1 + 2) / 5
        self.assertEqual(s["compile_success"]["final_both"], 60.0)    # (1 + 2) / 5
        self.assertEqual(s["deterministic"], {"programs": 2, "of_compiled_both": 3, "pct": 66.7})
        self.assertEqual(s["prs_with_difference"], {"count": 1, "pct": 50.0})
        self.assertEqual(s["regression_candidates"], [1])
        self.assertEqual(s["verdicts"]["clusters"], {"intended": 1, "unintended": 1})
        self.assertEqual(s["coverage"], {"prs": 1, "first_mean": 50.0, "last_mean": 75.0})
        self.assertEqual(s["llm_calls"]["total_est"], 3 + 1)
        self.assertEqual(s["wall_seconds_total"], 16.0)
        rows = {r["pr"]: r for r in s["seeded"]["rows"]}
        self.assertTrue(rows[1]["checked"] and rows[1]["correct"])
        self.assertFalse(rows[2]["checked"])        # PR 2 was never classified: not counted as correct or wrong
        self.assertFalse(rows[99]["checked"])       # PR not run at all
        self.assertEqual(s["seeded"]["recall"], "1/1")

    def test_a_missed_seeded_regression_lowers_recall(self):
        d = self.root / "tests" / "1" / "classification.json"
        c = json.loads(d.read_text())
        c["pr_verdict"] = {"regression_candidate": False, "unintended_clusters": []}
        d.write_text(json.dumps(c))
        _, s = report.build("t", self.root, self.root / "out")
        self.assertEqual(s["seeded"]["recall"], "0/1")

    def test_markdown_has_tables_and_the_finding(self):
        report.build("t", self.root, self.root / "out")
        md = (self.root / "out" / "report.md").read_text()
        self.assertIn("| Compile success, as generated (new / both versions) | 60.0% / 40.0% |", md)
        self.assertIn("| Compile success, after fix.py (new / both versions) | 60.0% / 60.0% |", md)
        self.assertIn("### Finding: PR #1 C2 (unintended, high)", md)
        self.assertIn("- New version: compile error: no match for call", md)
        self.assertIn("Recall on seeded regressions: 1/1", md)
        self.assertIn("REGRESSION CANDIDATE", md)
        self.assertEqual(json.loads((self.root / "out" / "report.json").read_text())["summary"]["prs_checked"], 2)

    def test_clean_results_are_inconclusive_without_coverage(self):
        base = {"classification": {"regression_candidate": False, "unintended_clusters": [], "clusters": []}}
        self.assertEqual(report.verdict_text({"classification": None, "coverage": None}), "not classified")
        flagged = {"classification": {"regression_candidate": True}, "coverage": None}
        self.assertEqual(report.verdict_text(flagged), "REGRESSION CANDIDATE")
        self.assertIn("INCONCLUSIVE: coverage not measured", report.verdict_text({**base, "coverage": None}))
        low = {**base, "coverage": {"first": 0.2, "last": 0.545}}
        self.assertIn("INCONCLUSIVE: only 55% of changed lines reached", report.verdict_text(low))
        self.assertEqual(report.verdict_text({**base, "coverage": {"first": 0.8, "last": 0.9}}), "no regression flagged")
        self.assertIn("no measurable changed lines", report.verdict_text({**base, "coverage": {"first": None, "last": None}}))

    def test_summary_lists_inconclusive_prs(self):
        _, s = report.build("t", self.root, self.root / "out")
        self.assertEqual(s["coverage_measured"], {"prs": 1, "of": 2, "at_least_80": 0})  # PR 1 reached 75%
        self.assertEqual(s["inconclusive_prs"], [])  # PR 2 was never classified, PR 1 is a candidate
        md = (self.root / "out" / "report.md").read_text()
        self.assertIn("| Changed-line coverage measured | 1 of 2 PRs; at least 80% reached for 0 |", md)

    def test_percentages_handle_empty(self):
        self.assertIsNone(report.pct(0, 0))
        self.assertEqual(report.fmt_pct(None), "n/a")
        s = report.summarize([], [])
        self.assertEqual(s["prs_checked"], 0)
        self.assertIsNone(s["seeded"]["recall"])


class LabelsSection(unittest.TestCase):
    def test_section(self):
        ev = {"items_scored": 4, "stale_labels_skipped": ["1-C1"], "accuracy_raw": 0.75,
              "unintended_raw": {"precision": 0.5, "recall": 1.0}, "unintended_weighted": {"precision": None, "recall": 0.9},
              "pr_level": {"caught": 1, "true_regressions": 1, "flagged": 2, "prs": 3}, "labeler_kappa": 0.556, "labeler_pairs": 4}
        text = "\n".join(report.labels_section(ev))
        self.assertIn("0.50 / n/a", text)
        self.assertIn("1/1 / 2 / 3", text)
        self.assertIn("0.56", text)
        self.assertEqual(report.labels_section(None), [])


if __name__ == "__main__":
    unittest.main()
