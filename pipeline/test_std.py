"""Tests for choosing the C++ standard per PR (common.pr_std) and its use in generate, batch and report.
Run:  python3 -m unittest pipeline.test_std"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from pipeline.common import Target, pr_std  # noqa: E402
import batch  # noqa: E402
import generate  # noqa: E402
import report  # noqa: E402
from test_batch import make_pr  # noqa: E402

C20 = ["-std=c++20"]


class FakeTarget(SimpleNamespace):
    def get(self, key, default=None):
        return self.cfg.get(key, default)


def target_with(changes, cfg=None):
    """A target whose data/changes/<pr>.json holds the given function lists."""
    tmp = tempfile.TemporaryDirectory()
    data = Path(tmp.name)
    (data / "changes").mkdir()
    for pr, funcs in changes.items():
        (data / "changes" / f"{pr}.json").write_text(json.dumps({"pr": pr, "functions": funcs}))
    return FakeTarget(data=data, cfg=cfg or {}, _tmp=tmp)


def fn(name, flags=None):
    f = {"name": name, "access": "public", "lines_changed": 1}
    if flags:
        f["requires_flags"] = flags
    return f


class PrStdTests(unittest.TestCase):
    def target(self, changes, cfg=None):
        t = target_with(changes, cfg)
        self.addCleanup(t._tmp.cleanup)
        return t

    def test_every_entity_cpp20_means_cpp20(self):
        t = self.target({1: [fn("a", C20), fn("b", C20)]})
        self.assertEqual(pr_std(t, 1), "c++20")

    def test_mixed_or_unflagged_or_missing_keeps_the_default(self):
        t = self.target({2: [fn("a", C20), fn("b")], 3: [fn("a")], 4: [],
                         5: [fn("a", ["-DJSON_DIAGNOSTICS=1"])]})   # a define is not a standard
        for pr in (2, 3, 4, 5, 99, None):
            self.assertEqual(pr_std(t, pr), "c++17", pr)

    def test_target_default_std(self):
        t = self.target({1: [fn("a")]}, {"default_std": "c++20"})
        self.assertEqual(pr_std(t, 1), "c++20")
        self.assertEqual(pr_std(t, None), "c++20")

    def test_real_nlohmann_json_prs(self):
        t = Target("nlohmann-json")
        if not (t.data / "changes" / "6075.json").is_file():
            self.skipTest("no change analysis for nlohmann-json")
        self.assertEqual(pr_std(t, 6075), "c++20")   # every change is under JSON_HAS_CPP_20 (char8_t strings)
        self.assertEqual(pr_std(t, 6081), "c++17")   # 1 of 15 entities is C++20-only: keep the default
        self.assertEqual(pr_std(t, 4958), "c++17")


class GeneratePromptTests(unittest.TestCase):
    def test_cpp17_prompt_is_unchanged_and_cpp20_names_cpp20(self):
        t = FakeTarget(cfg={"prompt_notes": "- note"})
        self.assertEqual(generate.system_prompt(t), generate.SYSTEM + "\n\nRules specific to this library:\n- note")
        self.assertEqual(generate.system_prompt(t, "c++17"), generate.system_prompt(t))
        p20 = generate.system_prompt(t, "c++20")
        self.assertIn("compiled as C++20", p20)
        self.assertNotIn("C++17", p20)

    def test_real_pr_prompts(self):
        t = Target("nlohmann-json")
        if not (t.repo / ".git").exists() or not (t.data / "changes" / "6075.json").is_file():
            self.skipTest("needs repos/nlohmann-json and its change analysis")
        rec, gh = generate.load_pr(t, 6075)
        system, _, _ = generate.build_generate_prompt(t, rec, gh, 5)
        self.assertIn("compiled as C++20", system)
        rec, gh = generate.load_pr(t, 4958)
        system, _, _ = generate.build_generate_prompt(t, rec, gh, 5)
        self.assertIn("compiled as C++17", system)


class BatchStdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)

    def test_files_without_std_count_as_cpp17(self):
        d = make_pr(self.data, 1)
        self.assertEqual(batch.pending_stages(d, std="c++17"), [])
        self.assertEqual(batch.pending_stages(d), [])   # no std given: not checked

    def test_a_pr_that_needs_cpp20_is_redone_from_generate(self):
        d = make_pr(self.data, 2)    # everything done, as C++17 (no "std" recorded)
        self.assertEqual(batch.pending_stages(d, std="c++20"), list(batch.STAGES))

    def test_only_the_stages_made_with_the_wrong_standard_and_later_ones_rerun(self):
        d = make_pr(self.data, 3)
        for name in ("generated.json", "coverage.json"):
            doc = json.loads((d / name).read_text())
            (d / name).write_text(json.dumps({**doc, "std": "c++20"}))
        self.assertEqual(batch.pending_stages(d, std="c++20"), ["run", "fix", "classify"])   # results.json is C++17
        doc = json.loads((d / "results.json").read_text())
        (d / "results.json").write_text(json.dumps({**doc, "std": "c++20"}))
        self.assertIn("run", batch.pending_stages(d, std="c++17"))
        self.assertEqual(batch.pending_stages(d, std="c++20"), ["classify"])   # results.json changed: fingerprint is stale


class ReportStdTests(unittest.TestCase):
    def test_report_shows_the_standard_only_when_prs_differ(self):
        with tempfile.TemporaryDirectory() as root:
            same = {"status": "same", "compile_failed_on": None,
                    "old": {"compile_ok": True, "compile_stderr": "", "stable": True, "runs": []},
                    "new": {"compile_ok": True, "compile_stderr": "", "stable": True, "runs": []}}
            for pr, std in ((1, None), (2, "c++20")):
                d = Path(root) / "tests" / str(pr)
                d.mkdir(parents=True)
                (d / "generated.json").write_text(json.dumps({"pr": pr, "tests": [{"file": "gen_01.cpp", "round": 0}]}))
                res = {"pr": pr, "wall_seconds": 1, "tests": {"gen_01.cpp": same}}
                if std:
                    res["std"] = std
                (d / "results.json").write_text(json.dumps(res))
            prs = [report.collect_pr(Path(root) / "tests" / str(pr)) for pr in (1, 2)]
            s = report.summarize(prs, [])
            self.assertEqual(s["std"], {"c++17": 1, "c++20": 1})
            md = report.render("x", prs, s)
            self.assertIn("c++17: 1 PR(s), c++20: 1 PR(s)", md)
            self.assertIn("| #2 (c++20) |", md)
            self.assertIn("| #1 |", md)
            s1 = report.summarize(prs[:1], [])
            self.assertNotIn("C++ standard the programs", report.render("x", prs[:1], s1))


if __name__ == "__main__":
    unittest.main()
