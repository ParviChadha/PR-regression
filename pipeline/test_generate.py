"""Tests for llm.py and generate.py with a fake transport: no network, no API key, no quota used.
Run:  python3 -m unittest pipeline.test_generate
"""
import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import generate  # noqa: E402
import llm  # noqa: E402
from pipeline.common import Target  # noqa: E402

OK_BODY = json.dumps({"candidates": [{"content": {"parts": [{"text": '{"tests": []}'}]}, "finishReason": "STOP"}],
                      "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3}})
PROG = "#include <iostream>\nint main() { std::cout << 1 << \"\\n\"; }\n"


def canned(*codes):
    return {"text": json.dumps({"tests": [{"name": f"t {i}", "intent": f"probe {i}", "code": c}
                                          for i, c in enumerate(codes)]}),
            "usage": {}, "model": "m", "cached": False}


class LlmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # never let a test see the real .env (or its key): point it at a file that does not exist
        p = mock.patch.object(llm, "ENV_FILE", Path(self.tmp.name) / "no.env")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(llm, "CACHE", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "SECRET-KEY-123"})
        p.start()
        self.addCleanup(p.stop)

    def test_cache_hit_makes_no_second_request_and_never_stores_the_key(self):
        with mock.patch.object(llm, "_post", return_value=(200, OK_BODY)) as post:
            a = llm.call("p", model="gemini-3.5-flash-lite")
            b = llm.call("p", model="gemini-3.5-flash-lite")
        self.assertEqual(post.call_count, 1)
        self.assertFalse(a["cached"])
        self.assertTrue(b["cached"])
        stored = "".join(f.read_text() for f in Path(self.tmp.name).rglob("*.json"))
        self.assertNotIn("SECRET-KEY-123", stored)
        self.assertEqual(llm.calls_today("gemini-3.5-flash-lite"), 1)

    def test_cached_response_works_without_a_key(self):
        with mock.patch.object(llm, "_post", return_value=(200, OK_BODY)):
            llm.call("p")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(llm.call("p")["cached"])
            with self.assertRaises(SystemExit):
                llm.call("a different prompt")

    def test_daily_budget_stops_before_any_request(self):
        with mock.patch.dict(os.environ, {"PRH_LLM_RPD": "2"}), \
                mock.patch.object(llm, "_post", return_value=(200, OK_BODY)) as post:
            llm.call("one")
            llm.call("two")
            with self.assertRaises(llm.QuotaExhausted):
                llm.call("three")
        self.assertEqual(post.call_count, 2)

    def test_per_day_429_raises_quota_exhausted_without_retrying(self):
        body = json.dumps({"error": {"code": 429, "message": "Quota exceeded for GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})
        with mock.patch.object(llm, "_post", return_value=(429, body)) as post:
            with self.assertRaises(llm.QuotaExhausted):
                llm.call("p")
        self.assertEqual(post.call_count, 1)

    def test_per_minute_429_is_waited_out_then_retried(self):
        body = json.dumps({"error": {"code": 429, "details": [{"retryDelay": "7s"}]}})
        with mock.patch.object(llm, "_post", side_effect=[(429, body), (200, OK_BODY)]) as post, \
                mock.patch.object(llm.time, "sleep") as sleep:
            llm.call("p")
        self.assertEqual(post.call_count, 2)
        sleep.assert_any_call(8.0)

    def test_503_and_timeout_are_retried_and_503_not_charged_to_daily_budget(self):
        busy = json.dumps({"error": {"code": 503, "message": "The model is overloaded."}})
        with mock.patch.object(llm, "_post", side_effect=[(503, busy), (0, "TimeoutError: timed out"),
                                                          (200, OK_BODY)]) as post, \
                mock.patch.object(llm.time, "sleep") as sleep:
            llm.call("p", model="gemini-3.8-flash")
        self.assertEqual(post.call_count, 3)
        sleep.assert_any_call(30)
        sleep.assert_any_call(60)
        self.assertEqual(llm.calls_today("gemini-3.8-flash"), 2)  # the timeout and the success

    def test_rpm_spacing_waits(self):
        clock = [1000.0]
        slept = []

        def fake_sleep(s):
            slept.append(s)
            clock[0] += s

        with mock.patch.dict(os.environ, {"PRH_LLM_RPM": "1"}), \
                mock.patch.object(llm, "_post", return_value=(200, OK_BODY)), \
                mock.patch.object(llm.time, "time", side_effect=lambda: clock[0]), \
                mock.patch.object(llm.time, "sleep", side_effect=fake_sleep):
            llm.call("one")
            llm.call("two")
        self.assertEqual(len(slept), 1)
        self.assertGreater(slept[0], 30)


def setUpModule():
    p = mock.patch.object(llm, "ENV_FILE", Path(tempfile.gettempdir()) / "prh-test-absent.env")
    p.start()
    unittest.addModuleCleanup(p.stop)
    r = mock.patch.dict(os.environ)          # a real Agent Platform setup in the shell must not reach these tests
    r.start()
    for name in llm.ROUTE_NAMES:
        os.environ.pop(name, None)
    unittest.addModuleCleanup(r.stop)
    q = mock.patch.object(llm.urllib.request, "urlopen", side_effect=AssertionError("tests must not use the network"))
    q.start()
    unittest.addModuleCleanup(q.stop)


class AgentPlatformRouteTests(unittest.TestCase):
    """GOOGLE_GENAI_USE_ENTERPRISE + GOOGLE_CLOUD_PROJECT: calls go to Agent Platform with a sign-in token, not the key."""
    ENV = {"GOOGLE_GENAI_USE_ENTERPRISE": "true", "GOOGLE_CLOUD_PROJECT": "proj-1", "GEMINI_API_KEY": "SECRET-KEY-123"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(llm, "CACHE", Path(self.tmp.name)), mock.patch.dict(os.environ, self.ENV),
                  mock.patch.object(llm, "access_token", side_effect=lambda refresh=False: "TOK2" if refresh else "TOK1")):
            p.start()
            self.addCleanup(p.stop)

    def test_route_endpoint_and_headers(self):
        self.assertEqual(llm.route(), ("agent_platform", "proj-1", "global"))
        self.assertEqual(llm.endpoint("gemini-3.5-flash-lite"), "https://aiplatform.googleapis.com/v1/projects/proj-1/"
                         "locations/global/publishers/google/models/gemini-3.5-flash-lite:generateContent")
        self.assertEqual(llm.auth_headers(), {"Authorization": "Bearer TOK1"})       # the key is not used
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_LOCATION": "us-central1"}):
            self.assertTrue(llm.endpoint("m").startswith("https://us-central1-aiplatform.googleapis.com/v1/projects/proj-1/locations/us-central1/"))
        with mock.patch.dict(os.environ, {"GOOGLE_GENAI_USE_ENTERPRISE": "false"}):
            self.assertEqual(llm.route()[0], "api_key")
            self.assertEqual(llm.auth_headers(), {"x-goog-api-key": "SECRET-KEY-123"})

    def test_route_settings_can_come_from_dotenv(self):
        f = Path(self.tmp.name) / ".env"
        f.write_text("GOOGLE_GENAI_USE_ENTERPRISE=true\nGOOGLE_CLOUD_PROJECT=from-file\n")
        with mock.patch.object(llm, "ENV_FILE", f), mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm.route(), ("agent_platform", "from-file", "global"))

    def test_call_uses_the_token_refreshes_on_401_and_records_tokens(self):
        body = json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                           "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200, "thoughtsTokenCount": 50}})
        with mock.patch.object(llm, "_post", side_effect=[(401, "expired"), (200, body)]) as post:
            llm.call("p", model="gemini-3.5-flash-lite")
        self.assertEqual(post.call_args_list[0].args[2], {"Authorization": "Bearer TOK1"})
        self.assertEqual(post.call_args_list[1].args[2], {"Authorization": "Bearer TOK2"})
        self.assertEqual(llm.tokens_today("gemini-3.5-flash-lite"), (1000, 250))
        stored = "".join(f.read_text() for f in Path(self.tmp.name).rglob("*.json"))
        self.assertNotIn("TOK", stored)
        self.assertNotIn("SECRET-KEY-123", stored)

    def test_limits_on_the_paid_route(self):
        self.assertEqual(llm.limits("gemini-3.5-flash-lite"), (60, 2000))
        with mock.patch.dict(os.environ, {"PRH_LLM_RPD": "300"}):
            self.assertEqual(llm.limits("gemini-3.5-flash-lite"), (60, 300))


class EnvFileTests(unittest.TestCase):
    def key_from(self, text, env=None):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            if text is not None:
                f.write_text(text)
            with mock.patch.object(llm, "ENV_FILE", f), mock.patch.dict(os.environ, env or {}, clear=True):
                return llm.api_key()

    def test_reads_only_the_gemini_key_from_dotenv(self):
        self.assertEqual(self.key_from("OTHER=x\nGEMINI_API_KEY=abc123\n"), "abc123")
        self.assertEqual(self.key_from('export GEMINI_API_KEY="q uoted"  \n'), "q uoted")
        self.assertEqual(self.key_from("# GEMINI_API_KEY=commented\nGEMINI_API_KEY=k # note\n"), "k")

    def test_environment_wins_and_missing_file_or_key_is_none(self):
        self.assertEqual(self.key_from("GEMINI_API_KEY=file", {"GEMINI_API_KEY": "env"}), "env")
        self.assertIsNone(self.key_from(None))
        self.assertIsNone(self.key_from("GEMINI_API_KEY=\nOTHER=1\n"))

    def test_dotenv_does_not_leak_other_variables_into_the_environment(self):
        self.key_from("GEMINI_API_KEY=k\nPRH_LLM_RPD=1\n")
        self.assertNotIn("PRH_LLM_RPD", os.environ)


class RefineOnlyTests(unittest.TestCase):
    def test_refine_only_needs_existing_programs_and_makes_no_generation_request(self):
        with mock.patch.object(sys, "argv", ["generate.py", "nlohmann-json", "--pr", "999999", "--refine-only"]), \
                mock.patch.object(llm, "call") as call:
            with self.assertRaises(SystemExit):
                generate.main()
        call.assert_not_called()

    def test_refine_prompt_warns_about_malformed_inputs(self):
        t = Target("nlohmann-json")
        rec, gh = generate.load_pr(t, 4958)
        _, prompt = generate.build_refine_prompt(t, rec, gh, [{"file": "gen_01.cpp", "intent": "x"}], ">> 1 foo", 5)
        self.assertIn("malformed input", prompt)
        self.assertIn("NOT RUN", prompt)


class RunErrorsTests(unittest.TestCase):
    def test_compile_errors_keep_the_root_cause_under_a_template_dump(self):
        import run
        root = "a.cpp:9:3: error: no match for call to 'less<void>'"
        noise = "\n".join("note: " + "x" * 300 for _ in range(60))
        out = run._compile_errors(noise + "\n" + root + "\n" + "y" * 100 + " error: second\n" + noise)
        self.assertTrue(out.startswith(root))
        self.assertLess(len(out), 4001)
        self.assertEqual(run._compile_errors("undefined reference to foo"), "undefined reference to foo")

    def test_classify_both_fail_with_different_errors_is_a_compile_diff(self):
        import run
        def res(err):
            return {"compile_ok": False, "compile_stderr": err, "stable": True, "runs": []}
        clean = "t.cpp:15:24: error: no match for \u2018operator[]\u2019 (operand types are \u2018json\u2019 and \u2018MyView\u2019)"
        hard = "stl_tree.h:1303:53: error: no match for call to \u2018(const std::less<void>) (const MyView&)\u2019"
        self.assertEqual(run.classify(res(clean), res(hard)), ("compile_diff", "both"))
        # same kind of error, different line numbers and type names: still a broken test
        other = clean.replace("15:24", "99:1").replace("MyView", "Other")
        self.assertEqual(run.classify(res(clean), res(other)), ("invalid", None))
        ok = {"compile_ok": True, "compile_stderr": "", "stable": True,
              "runs": [{"timeout": False, "exit": 0, "sha256": "x"}]}
        self.assertEqual(run.classify(res(clean), ok), ("compile_diff", "old"))

    def test_coverage_refuses_to_report_zeros_when_gcov_produced_nothing(self):
        import coverage_loop
        bad = {"a.cpp": {"compiled": True, "exit": 0, "timeout": False, "covered": {}, "uncovered": {},
                         "gcda": 0, "gcov_files": 0}}
        env = argparse.Namespace(flags=lambda w: [], new_dir="/x")
        a = argparse.Namespace(std="c++17", timeout=1, compile_timeout=1, jobs=1, docker=False)
        with mock.patch("run.launch_worker", return_value=bad):
            with self.assertRaises(SystemExit) as cm:
                coverage_loop.measure(env, Path("/t"), ["a.cpp"], {}, a)
        self.assertIn("--docker", str(cm.exception))
        good = {"a.cpp": {**bad["a.cpp"], "gcda": 1, "gcov_files": 3}}
        with mock.patch("run.launch_worker", return_value=good):
            self.assertEqual(coverage_loop.measure(env, Path("/t"), ["a.cpp"], {}, a), good)

    def test_system_prompt_asks_for_detection_idiom_and_distinct_entry_points(self):
        self.assertIn("detection idiom", generate.SYSTEM)
        self.assertIn("distinct public entry points", generate.SYSTEM)


class ParseTests(unittest.TestCase):
    def test_drops_programs_without_main_and_duplicates_and_strips_fences(self):
        r = canned("```cpp\n" + PROG + "```", "int helper() { return 1; }", PROG)
        progs, dropped = generate.parse_tests(r["text"])
        self.assertEqual(len(progs), 1)
        self.assertEqual(dropped, 2)
        self.assertNotIn("```", progs[0]["code"])
        self.assertEqual(progs[0]["name"], "t_0")

    def test_bad_json_is_an_error(self):
        with self.assertRaises(SystemExit):
            generate.parse_tests("not json")

    def test_merge_time_filter(self):
        gh = {"merged_at": "2026-01-11T20:45:22Z", "comments": [
            {"created_at": "2026-01-01T00:00:00Z", "body": "before"},
            {"created_at": "2026-03-01T00:00:00Z", "body": "after: broke lookups"}], "review_comments": []}
        kept, dropped = generate.merge_time_comments(gh)
        self.assertEqual([c["body"] for c in kept], ["before"])
        self.assertEqual(dropped, 1)


class GenerateTests(unittest.TestCase):
    """End to end on the real data for json #5459, with the model faked."""

    def setUp(self):
        self.t = Target("nlohmann-json")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.args = argparse.Namespace(n=3, model="m", dry_run=False, force=False, refine_n=2)

    def test_prompt_contents_and_no_post_merge_text(self):
        rec, gh = generate.load_pr(self.t, 4958)
        _, prompt, stats = generate.build_generate_prompt(self.t, rec, gh, 20)
        self.assertIn("is_usable_as_basic_json_key_type", prompt)
        self.assertIn("```diff", prompt)
        self.assertIn("Write 20 test programs", prompt)
        self.assertNotIn("5689", prompt)
        self.assertGreaterEqual(stats["comments_dropped_after_merge"], 0)
        self.assertIn("nlohmann/json.hpp", generate.system_prompt(self.t))

    def test_extra_header_only_for_prs_that_touch_matching_files(self):
        rec, gh = generate.load_pr(self.t, 6084)
        _, prompt, _ = generate.build_generate_prompt(self.t, rec, gh, 5)
        self.assertIn("## Headers the programs must include", prompt)
        self.assertIn("#include <nlohmann/json_view.hpp>", prompt)
        rec, gh = generate.load_pr(self.t, 4958)
        _, prompt, _ = generate.build_generate_prompt(self.t, rec, gh, 5)
        self.assertNotIn("json_view.hpp>", prompt)
        self.assertNotIn("Headers the programs must include", prompt)

    def test_generate_writes_files_manifest_and_removes_stale(self):
        (self.dir / "gen_09.cpp").write_text("stale")
        with mock.patch.object(llm, "call", return_value=canned(PROG, PROG.replace("1", "2"), "no main here")):
            tests_dir, manifest, _ = generate.generate(self.t, 5459, self.args, tests_dir=self.dir)
        self.assertEqual(sorted(p.name for p in self.dir.glob("gen_*.cpp")), ["gen_01.cpp", "gen_02.cpp"])
        self.assertEqual(manifest["dropped"], 1)
        saved = json.loads((self.dir / "generated.json").read_text())
        self.assertEqual([e["file"] for e in saved["tests"]], ["gen_01.cpp", "gen_02.cpp"])
        self.assertIn("intent: probe 0", (self.dir / "gen_01.cpp").read_text())
        self.assertTrue((self.dir / "generate.prompt.txt").is_file())

    def test_refine_continues_numbering_and_updates_manifest(self):
        with mock.patch.object(llm, "call", return_value=canned(PROG)):
            tests_dir, manifest, (rec, gh) = generate.generate(self.t, 5459, self.args, tests_dir=self.dir)
        refine = generate.make_refine(self.t, rec, gh, self.args, self.dir, manifest)
        with mock.patch.object(llm, "call", return_value=canned(PROG.replace("1", "3"), PROG.replace("1", "4"))) as call:
            names = refine(">> 145  return f;   // NOT RUN", {}, self.dir)
        self.assertEqual(names, ["gen_02.cpp", "gen_03.cpp"])
        self.assertIn("return f;", call.call_args[0][0])
        self.assertIn("gen_01.cpp: probe 0", call.call_args[0][0])
        self.assertEqual([e["round"] for e in json.loads((self.dir / "generated.json").read_text())["tests"]], [0, 1, 1])

    def test_dry_run_makes_no_request(self):
        self.args.dry_run = True
        with mock.patch.object(llm, "call") as call:
            self.assertIsNone(generate.generate(self.t, 5459, self.args, tests_dir=self.dir))
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
