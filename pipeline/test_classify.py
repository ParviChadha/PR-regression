"""Tests for classify.py with a fake model: no network, no key, no quota.
Run:  python3 -m unittest pipeline.test_classify
"""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import classify  # noqa: E402
import llm  # noqa: E402
from pipeline.common import Target  # noqa: E402

MAIN = "#include <iostream>\nint main() { std::cout << 1 << \"\\n\"; }\n"
NOMATCH = "/Users/me/x/{f}:15:24: error: no match for \u2018operator[]\u2019 (operand types are \u2018json\u2019 and \u2018K\u2019)"
HARD = "/usr/include/c++/14/bits/stl_tree.h:1303:53: error: no match for call to \u2018(const std::less<void>) (const K&)\u2019"


def ok(out, code=0):
    return {"compile_ok": True, "compile_stderr": "", "stable": True,
            "runs": [{"exit": code, "timeout": False, "sha256": out, "stdout": out}]}


def bad(err):
    return {"compile_ok": False, "compile_stderr": err, "stable": True, "runs": []}


def res(status, old, new, failed=None):
    return {"status": status, "compile_failed_on": failed, "old": old, "new": new}


def fixtures():
    results = {
        "gen_01.cpp": res("output_diff", ok("supported: 0\n"), ok("supported: 1\n42\n")),
        "gen_02.cpp": res("output_diff", ok("supported: 0\n"), ok("supported: 1\n99\n")),
        "gen_03.cpp": res("output_diff", ok("supported: 0\n"), ok("supported: 1\n[err]\n")),
        "gen_04.cpp": res("output_diff", ok("false\n"), ok("true\n")),
        "gen_05.cpp": res("compile_diff", bad(NOMATCH.format(f="gen_05.cpp")), ok("1\n"), "old"),
        "gen_06.cpp": res("compile_diff", ok("1\n"), bad(HARD), "new"),
        "gen_07.cpp": res("compile_diff", bad(NOMATCH.format(f="gen_07.cpp")), bad(HARD), "both"),
        "gen_08.cpp": res("same", ok("1\n"), ok("1\n")),
        "gen_09.cpp": res("invalid", bad("x.cpp:1:1: error: boom"), bad("x.cpp:1:1: error: boom")),
        "gen_10.cpp": res("flaky", ok("1\n"), ok("1\n")),
        "gen_11.cpp": res("output_diff", ok("a\n"), ok("a\n", 1)),  # same text, exit code changed
        "gen_12.cpp": res("compile_diff", bad(NOMATCH.format(f="gen_12.cpp")), ok("1\n"), "old"),  # superseded
    }
    manifest = {"tests": [{"file": f, "name": f, "intent": "i", "round": 0} for f in results]}
    manifest["tests"][-1]["superseded_by"] = "gen_13.cpp"
    return manifest, results


class CollectTests(unittest.TestCase):
    def test_clusters_by_first_difference_and_counts_the_rest(self):
        manifest, results = fixtures()
        clusters, counts = classify.collect(manifest, results)
        by_first = {c["programs"][0]: c for c in clusters}
        self.assertEqual(by_first["gen_01.cpp"]["programs"], ["gen_01.cpp", "gen_02.cpp", "gen_03.cpp"])  # "supported: 0 -> 1"
        self.assertEqual(clusters[0]["id"], "C1")  # biggest first
        self.assertEqual(by_first["gen_04.cpp"]["programs"], ["gen_04.cpp"])
        self.assertEqual(by_first["gen_05.cpp"]["failed_on"], "old")
        self.assertEqual(by_first["gen_06.cpp"]["failed_on"], "new")
        self.assertEqual(by_first["gen_07.cpp"]["failed_on"], "both")
        self.assertEqual(by_first["gen_11.cpp"]["status"], "output_diff")  # exit-code-only difference is still a cluster
        all_in = [p for c in clusters for p in c["programs"]]
        self.assertNotIn("gen_12.cpp", all_in)  # superseded
        self.assertNotIn("gen_08.cpp", all_in)
        self.assertEqual((counts["same"], counts["invalid"], counts["flaky"], counts["superseded"]), (1, 1, 1, 1))

    def test_system_prompt_separates_invalid_programs_from_regressions(self):
        flat = " ".join(classify.SYSTEM.split())  # the prompt wraps lines
        for phrase in ("not the program's own mistake", "without its namespace", "detection probe written incorrectly",
                       "valid code that uses the documented public API", "fails deep inside library code",
                       "even though the program fails to compile on both versions"):
            self.assertIn(phrase, flat)
        self.assertIn("verdict is unclear", flat)

    def test_error_site_tells_program_mistakes_from_library_failures(self):
        progs = {"gen_02.cpp": 1}
        own = "/w/tests/4958/gen_02.cpp:11:5: error: 'json' was not declared in this scope\n"
        std = "In file included from x.cpp\n/usr/include/c++/14/bits/stl_tree.h:780:5: error: no match for call to 'std::less<void>'\n"
        lib = "/w/cache/worktrees/x/include/nlohmann/json.hpp:100:3: error: static assertion failed\n"
        self.assertEqual(classify.error_site(own, progs), "the program's own code")
        self.assertEqual(classify.error_site(std, progs), "the standard library headers")
        self.assertEqual(classify.error_site(lib, progs), "the library headers")
        self.assertIsNone(classify.error_site("no diagnostics here", progs))
        self.assertIsNone(classify.error_site("", progs))

    def test_describe_states_where_the_first_error_is_reported(self):
        side = lambda err: {"compile_ok": False, "compile_stderr": err, "runs": []}
        err_old = "/w/t/gen_01.cpp:3:1: error: 'x' was not declared in this scope\n"
        err_new = "/usr/include/c++/14/bits/stl_tree.h:1:1: error: no match for call\n"
        results = {"gen_01.cpp": {"status": "compile_diff", "compile_failed_on": "both", "old": side(err_old), "new": side(err_new)}}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "gen_01.cpp").write_text("#include <nlohmann/json.hpp>\nint main() {}\n")
            text = classify.describe({"id": "C1", "status": "compile_diff", "failed_on": "both", "programs": ["gen_01.cpp"]}, results, d)
        self.assertIn("Compiler errors on old (the first error is reported in the program's own code)", text)
        self.assertIn("Compiler errors on new (the first error is reported in the standard library headers)", text)

    def test_first_diff_variants(self):
        self.assertEqual(classify.first_diff(ok("a\nb\n"), ok("a\nc\n")), ("b", "c"))
        self.assertEqual(classify.first_diff(ok("a\n"), ok("a\nextra\n")), ("", "extra"))
        self.assertEqual(classify.first_diff(ok("a\n"), ok("a\n", 3)), ("exit 0", "exit 3"))


class VerdictTests(unittest.TestCase):
    def test_parse_verdicts_normalizes_and_fills_gaps(self):
        shown = [{"id": "C1"}, {"id": "C2"}, {"id": "C3"}]
        doc = {"clusters": [{"id": "C1", "verdict": "Intended ", "confidence": "HIGH", "reason": "matches\nthe PR"},
                            {"id": "C1", "verdict": "unintended", "confidence": "low", "reason": "duplicate id ignored"},
                            {"id": "C2", "verdict": "maybe", "confidence": "", "reason": "dunno"}]}
        got = classify.parse_verdicts(json.dumps(doc), shown)
        self.assertEqual(got["C1"], {"verdict": "intended", "confidence": "high", "reason": "matches the PR"})
        self.assertEqual(got["C2"]["verdict"], "unclear")
        self.assertIn("maybe", got["C2"]["reason"])
        self.assertEqual(got["C3"]["verdict"], "unclear")
        with self.assertRaises(SystemExit):
            classify.parse_verdicts("nope", shown)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.t = Target("nlohmann-json")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        manifest, results = fixtures()
        for f in results:
            (self.dir / f).write_text(f"// generated by m for PR #4958 (round 0): n\n// intent: i\n{MAIN}")
        (self.dir / "generated.json").write_text(json.dumps(manifest))
        (self.dir / "results.json").write_text(json.dumps({"tests": results}))
        self.args = argparse.Namespace(model="m", dry_run=False, force=False)
        for p in (mock.patch.object(llm, "calls_today", return_value=1), mock.patch.object(llm, "limits", return_value=(15, 500))):
            p.start()
            self.addCleanup(p.stop)

    def reply(self, verdicts):
        items = [{"id": i, "verdict": v, "confidence": "high", "reason": f"because {i}"} for i, v in verdicts.items()]
        return {"text": json.dumps({"clusters": items}), "model": "m", "cached": False, "usage": {}}

    def test_end_to_end_writes_classification_and_flags_regression_candidates(self):
        with mock.patch.object(llm, "call", return_value=self.reply({"C1": "intended", "C2": "unintended", "C3": "intended"})) as call:
            doc = classify.classify(self.t, 4958, self.args, tests_dir=self.dir)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.kwargs["temperature"], 0.0)
        self.assertTrue(doc["pr_verdict"]["regression_candidate"])
        self.assertEqual(doc["pr_verdict"]["unintended_clusters"], ["C2"])
        saved = json.loads((self.dir / "classification.json").read_text())
        self.assertEqual(saved["clusters"][0]["programs"], ["gen_01.cpp", "gen_02.cpp", "gen_03.cpp"])
        self.assertEqual(saved["clusters"][0]["verdict"], "intended")
        self.assertEqual(saved["clusters"][1]["reason"], "because C2")
        self.assertEqual(saved["clusters"][1]["verdict"], "unintended")
        prompt = (self.dir / "classify.prompt.txt").read_text()
        self.assertNotIn("/Users", prompt)
        self.assertNotIn("/usr/include", prompt)
        self.assertIn("compile_diff (fails to compile on old)", prompt)
        self.assertIn("compile_diff (fails to compile on new)", prompt)
        self.assertIn("compile_diff (fails to compile on both)", prompt)
        self.assertIn("`supported: 0` -> `supported: 1`", prompt)
        self.assertNotIn("generated by m", prompt)  # header comments are stripped from the sources shown

    def test_all_intended_is_not_a_regression_candidate(self):
        with mock.patch.object(llm, "call", return_value=self.reply({f"C{i}": "intended" for i in range(1, 9)})):
            doc = classify.classify(self.t, 4958, self.args, tests_dir=self.dir)
        self.assertFalse(doc["pr_verdict"]["regression_candidate"])

    def test_nothing_differing_makes_no_request(self):
        results = {f: res("same", ok("1\n"), ok("1\n")) for f in ("gen_01.cpp", "gen_02.cpp")}
        (self.dir / "results.json").write_text(json.dumps({"tests": results}))
        (self.dir / "generated.json").write_text(json.dumps({"tests": [{"file": f} for f in results]}))
        with mock.patch.object(llm, "call") as call:
            doc = classify.classify(self.t, 4958, self.args, tests_dir=self.dir)
        call.assert_not_called()
        self.assertFalse(doc["pr_verdict"]["regression_candidate"])

    def test_dry_run_and_missing_inputs(self):
        self.args.dry_run = True
        with mock.patch.object(llm, "call") as call:
            self.assertIsNone(classify.classify(self.t, 4958, self.args, tests_dir=self.dir))
        call.assert_not_called()
        self.assertTrue((self.dir / "classify.prompt.txt").is_file())
        (self.dir / "results.json").unlink()
        with self.assertRaises(SystemExit):
            classify.classify(self.t, 4958, self.args, tests_dir=self.dir)

    def test_prompt_excludes_post_merge_discussion(self):
        # real PR data: comments created after merged_at must not reach the model
        rec, gh = classify.generate.load_pr(self.t, 4958)
        manifest, results = fixtures()
        clusters, counts = classify.collect(manifest, results)
        _, prompt, _ = classify.build_prompt(self.t, rec, gh, self.dir, clusters, counts, results)
        late = [c["body"] for c in gh["comments"] if c["created_at"] > gh["merged_at"]]
        self.assertTrue(late)
        for body in late:
            self.assertNotIn(body.strip()[:60], prompt)


if __name__ == "__main__":
    unittest.main()
