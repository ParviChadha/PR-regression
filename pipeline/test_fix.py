"""Tests for fix.py with a fake model and fake compile/run: no network, no key, no quota.
Run:  python3 -m unittest pipeline.test_fix
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
import fix  # noqa: E402
import generate  # noqa: E402
import llm  # noqa: E402
from pipeline.common import Target  # noqa: E402

NOMATCH = "/Users/me/repo/data/x/tests/4958/{f}:15:24: error: no match for \u2018operator[]\u2019 (operand types are \u2018json\u2019 and \u2018K\u2019)"
HARD = "/usr/include/c++/14/bits/stl_tree.h:1303:53: error: no match for call to \u2018(const std::less<void>) (const K&)\u2019"
NOHDR = "{f}:5:10: fatal error: nlohmann/ordered_json.hpp: No such file or directory"
MAIN = "#include <iostream>\nint main() { std::cout << 1 << \"\\n\"; }\n"


def side(ok, err="", out="1\n"):
    s = {"compile_ok": ok, "compile_stderr": err, "stable": True, "runs": []}
    if ok:
        s["runs"] = [{"exit": 0, "timeout": False, "sha256": out, "stdout": out}]
    return s


def entry(status, old, new, failed_on=None):
    return {"status": status, "compile_failed_on": failed_on, "old": old, "new": new}


def results_for():
    return {
        "gen_01.cpp": entry("compile_diff", side(False, NOMATCH.format(f="gen_01.cpp")), side(True), "old"),
        "gen_02.cpp": entry("compile_diff", side(False, NOMATCH.format(f="gen_02.cpp")), side(True), "old"),
        "gen_03.cpp": entry("compile_diff", side(True), side(False, HARD), "new"),
        "gen_04.cpp": entry("compile_diff", side(False, NOMATCH.format(f="gen_04.cpp")), side(False, HARD), "both"),
        "gen_05.cpp": entry("invalid", side(False, NOHDR.format(f="gen_05.cpp")), side(False, NOHDR.format(f="gen_05.cpp"))),
        "gen_06.cpp": entry("output_diff", side(True, out="a"), side(True, out="b")),
        "gen_07.cpp": entry("invalid", side(True), side(True)),  # both time out at run time: not a compile problem
        "gen_08.cpp": entry("compile_diff", side(False, NOMATCH.format(f="gen_08.cpp")), side(True), "old"),
    }


def manifest_for():
    return {"target": "nlohmann-json", "pr": 4958, "model": "m", "tests": [
        {"file": f"gen_{i:02d}.cpp", "name": f"n{i}", "intent": f"probe {i}", "round": 0} for i in range(1, 9)]}


class PickTests(unittest.TestCase):
    def test_selects_only_repairable_programs(self):
        got = {i["file"]: i["kind"] for i in fix.pick(manifest_for(), results_for(), 99)}
        self.assertEqual(got, {"gen_01.cpp": "detect", "gen_02.cpp": "detect", "gen_05.cpp": "compile",
                               "gen_08.cpp": "detect"})  # never: new-only, both, output_diff, runtime invalid

    def test_per_signature_cap_limits_detect_duplicates_but_not_compile_fixes(self):
        got = [i["file"] for i in fix.pick(manifest_for(), results_for(), 99, per_signature=2)]
        self.assertEqual(got, ["gen_01.cpp", "gen_02.cpp", "gen_05.cpp"])

    def test_superseded_and_limit(self):
        m = manifest_for()
        m["tests"][0]["superseded_by"] = "gen_09.cpp"
        self.assertNotIn("gen_01.cpp", [i["file"] for i in fix.pick(m, results_for(), 99)])
        self.assertEqual(len(fix.pick(manifest_for(), results_for(), 2)), 2)

    def test_errors_have_no_host_paths(self):
        e = fix.errors_of(NOMATCH.format(f="gen_01.cpp") + "\n" + HARD)
        self.assertNotIn("/Users", e)
        self.assertNotIn("/usr/include", e)
        self.assertIn("stl_tree.h:1303:53", e)
        self.assertNotIn("c++stl_tree", e)
        self.assertIn("gen_01.cpp:15:24: error: no match", e)


class PromptTextTests(unittest.TestCase):
    def test_detect_instructions_require_a_function_template(self):
        t = fix.KIND_TEXT["detect"]
        self.assertIn("function template", t)
        self.assertIn("main() does NOT", t)
        self.assertIn("std::void_t", t)


class UnflattenTests(unittest.TestCase):
    def test_double_escaped_one_line_program_is_restored(self):
        flat = ('#include <iostream>\\n// don\'t break on this apostrophe\\nint main() {\\n  std::cout << "a\\n" << \'\\n\';\\n}')
        code = generate.unflatten(flat)
        self.assertEqual(code.count("\n"), 4)
        self.assertIn('"a\\n"', code)       # escape inside a string literal is kept
        self.assertIn("'\\n'", code)         # and inside a char literal
        self.assertTrue(code.splitlines()[1].startswith("// don't"))

    def test_normal_programs_are_untouched(self):
        self.assertEqual(generate.unflatten(MAIN), MAIN)
        one_line = 'int main() { return 0; }'
        self.assertEqual(generate.unflatten(one_line), one_line)
        self.assertEqual(generate.unflatten('int main() { std::cout << "x\\n"; }'), 'int main() { std::cout << "x\\n"; }')

    def test_parse_fixes_accepts_a_double_escaped_response(self):
        flat = "#include <iostream>\\nint main() { std::cout << 1 << \\\"\\\\n\\\"; }"
        doc = json.dumps({"fixes": [{"file": "gen_01.cpp", "code": flat}]})
        got = fix.parse_fixes(doc, {"gen_01.cpp"})
        self.assertIn("gen_01.cpp", got)
        self.assertEqual(got["gen_01.cpp"].splitlines()[0], "#include <iostream>")


class ParseTests(unittest.TestCase):
    def test_parse_fixes(self):
        doc = {"fixes": [
            {"file": "gen_01.cpp", "code": "```cpp\n// generated by m for PR #1 (round 0): x\n// intent: y\n" + MAIN + "```"},
            {"file": "gen_01.cpp", "code": MAIN + "// duplicate answer is ignored\n"},
            {"file": "gen_09.cpp", "code": MAIN},          # not asked for
            {"file": "gen_02.cpp", "code": "int f();"}]}    # no main
        got = fix.parse_fixes(json.dumps(doc), {"gen_01.cpp", "gen_02.cpp"})
        self.assertEqual(list(got), ["gen_01.cpp"])
        self.assertNotIn("generated by", got["gen_01.cpp"])
        self.assertNotIn("```", got["gen_01.cpp"])
        with self.assertRaises(SystemExit):
            fix.parse_fixes("nope", set())


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.t = Target("nlohmann-json")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for i in range(1, 9):
            (self.dir / f"gen_{i:02d}.cpp").write_text(f"// generated by m for PR #4958 (round 0): n{i}\n// intent: probe {i}\n{MAIN}")
        (self.dir / "generated.json").write_text(json.dumps(manifest_for()))
        res = results_for()
        (self.dir / "results.json").write_text(json.dumps({"target": "nlohmann-json", "pr": 4958, "tests": res, "summary": {}}))
        self.args = argparse.Namespace(rounds=2, max_per_round=15, per_signature=4, model="m", dry_run=False, force=False,
                                       docker=False, std="c++17", runs=3, timeout=10, compile_timeout=10, jobs=1)
        for p in (mock.patch.object(llm, "calls_today", return_value=1), mock.patch.object(llm, "limits", return_value=(15, 500))):
            p.start()
            self.addCleanup(p.stop)

    def model_reply(self, files):
        return {"text": json.dumps({"fixes": [{"file": f, "code": MAIN} for f in files]}), "model": "m", "cached": False,
                "usage": {}}

    def test_round_writes_new_files_links_them_and_merges_results(self):
        evaluated = {}

        def fake_eval(env, tests_dir, names, args):
            evaluated["names"] = names
            return {n: entry("output_diff", side(True, out="not supported\n"), side(True, out="ok\n")) for n in names}

        with mock.patch.object(llm, "call", return_value=self.model_reply(["gen_01.cpp", "gen_02.cpp", "gen_05.cpp", "gen_08.cpp"])) as call, \
                mock.patch.object(fix, "evaluate", side_effect=fake_eval):
            manifest = fix.fix(self.t, 4958, self.args, tests_dir=self.dir, env=object())
        self.assertEqual(call.call_count, 1)  # round 1 repairs; round 2 finds nothing left, so no second request
        self.assertEqual(evaluated["names"], ["gen_09.cpp", "gen_10.cpp", "gen_11.cpp", "gen_12.cpp"])
        new = {e["file"]: e for e in manifest["tests"] if e.get("fixes")}
        self.assertEqual({e["fixes"] for e in new.values()}, {"gen_01.cpp", "gen_02.cpp", "gen_05.cpp", "gen_08.cpp"})
        self.assertEqual({e["kind"] for e in new.values()}, {"detect", "compile"})
        self.assertEqual(next(e for e in manifest["tests"] if e["file"] == "gen_01.cpp")["superseded_by"], "gen_09.cpp")
        self.assertTrue((self.dir / "gen_01.cpp").is_file())  # originals are kept
        self.assertIn("intent: probe 1", (self.dir / "gen_09.cpp").read_text())
        saved = json.loads((self.dir / "results.json").read_text())
        self.assertEqual(saved["summary"]["output_diff"], 5)
        self.assertEqual(json.loads((self.dir / "generated.json").read_text()), manifest)
        prompt = (self.dir / "fix.round1.prompt.txt").read_text()
        self.assertNotIn("/Users", prompt)
        self.assertIn("gen_05.cpp (compile)", prompt)

    def test_a_repair_that_still_fails_is_retried_once_then_rounds_run_out(self):
        bad = lambda env, d, names, args: {n: entry("invalid", side(False, NOHDR.format(f=n)), side(False, NOHDR.format(f=n))) for n in names}
        replies = [self.model_reply(["gen_05.cpp"]), self.model_reply(["gen_09.cpp"])]
        self.args.per_signature = 0
        with mock.patch.object(llm, "call", side_effect=replies) as call, mock.patch.object(fix, "evaluate", side_effect=bad):
            manifest = fix.fix(self.t, 4958, self.args, tests_dir=self.dir, env=object())
        self.assertEqual(call.call_count, 2)
        chain = {e["file"]: e.get("superseded_by") for e in manifest["tests"] if e["file"] in ("gen_05.cpp", "gen_09.cpp", "gen_10.cpp")}
        self.assertEqual(chain, {"gen_05.cpp": "gen_09.cpp", "gen_09.cpp": "gen_10.cpp", "gen_10.cpp": None})

    def test_dry_run_makes_no_request_and_writes_only_the_prompt(self):
        self.args.dry_run = True
        with mock.patch.object(llm, "call") as call:
            fix.fix(self.t, 4958, self.args, tests_dir=self.dir)
        call.assert_not_called()
        self.assertTrue((self.dir / "fix.round1.prompt.txt").is_file())
        self.assertEqual(len(list(self.dir.glob("gen_*.cpp"))), 8)

    def test_missing_inputs_are_an_error(self):
        (self.dir / "results.json").unlink()
        with self.assertRaises(SystemExit):
            fix.fix(self.t, 4958, self.args, tests_dir=self.dir)


if __name__ == "__main__":
    unittest.main()
