"""Changed-line coverage through a coverage-instrumented shared library (cmake targets such as QuantLib), on a tiny
library built here with g++ --coverage: no docker, no network. Run:  python3 -m unittest pipeline.test_coverage_cmake"""
import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_loop  # noqa: E402

HPP = """#pragma once
namespace lib {
int twice(int x);
inline int inline_helper(int x) {
    if (x > 100)
        return -1;
    return x;
}
}
"""
CPP = """#include "lib/cal.hpp"
namespace lib {
int twice(int x) {
    if (x < 0)
        return 0;
    return 2 * x;
}
}
"""
TEST_POS = '#include <lib/cal.hpp>\n#include <cstdio>\nint main() { std::printf("%d %d\\n", lib::twice(3), lib::inline_helper(5)); }\n'
TEST_NEG = '#include <lib/cal.hpp>\n#include <cstdio>\nint main() { std::printf("%d\\n", lib::twice(-3)); }\n'


def tools():
    return all(shutil.which(x) for x in ("g++", "gcov")) and \
        subprocess.run(["gcov", "--help"], capture_output=True, text=True).stdout.count("json") > 0


@unittest.skipUnless(tools(), "needs GNU g++ and gcov with --json-format")
class LibraryCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        src, obj, exp = cls.tmp / "cov-src", cls.tmp / "cov", cls.tmp / "export"
        for root in (src, exp):
            (root / "lib").mkdir(parents=True)
            (root / "lib" / "cal.hpp").write_text(HPP)
        (src / "lib" / "cal.cpp").write_text(CPP)
        (obj / "lib").mkdir(parents=True)
        (cls.tmp / "lib-cov").mkdir()
        o = obj / "lib" / "cal.cpp.o"     # cmake-style object name, compiled from the coverage source tree
        subprocess.run(["g++", "-std=c++17", "-O0", "--coverage", "-fPIC", f"-I{src}", "-c", str(src / "lib" / "cal.cpp"),
                        "-o", str(o)], check=True, cwd=obj)
        subprocess.run(["g++", "-shared", "--coverage", str(o), "-o", str(cls.tmp / "lib-cov" / "libcal.so")], check=True)
        tests = cls.tmp / "tests"
        tests.mkdir()
        (tests / "gen_01.cpp").write_text(TEST_POS)
        (tests / "gen_02.cpp").write_text(TEST_NEG)
        changed = {"lib/cal.cpp": [3, 4, 5, 6], "lib/cal.hpp": [4, 5, 6, 7]}
        lib = cls.tmp / "lib-cov"
        a = argparse.Namespace(changed_json=json.dumps(changed), tests=str(tests), flag=[f"-I{exp}"], std="c++17",
                               compile_timeout=120, timeout=20, jobs=2, names=["gen_01.cpp", "gen_02.cpp"],
                               prefix=[str(exp) + "/", str(src) + "/"], gcov_prefix=True,
                               link_flag=[f"-L{lib}", "-lcal", f"-Wl,-rpath,{lib}"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            coverage_loop.worker(a)
        cls.res = json.loads(buf.getvalue())
        cls.obj = obj

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_library_lines_are_measured_per_test(self):
        pos, neg = self.res["gen_01.cpp"], self.res["gen_02.cpp"]
        self.assertTrue(pos["compiled"] and neg["compiled"])
        self.assertEqual(pos["covered"]["lib/cal.cpp"], [3, 4, 6])        # x >= 0: the early return is not run
        self.assertEqual(pos["uncovered"]["lib/cal.cpp"], [5])
        self.assertEqual(neg["covered"]["lib/cal.cpp"], [3, 4, 5])        # separate .gcda: counts do not mix
        self.assertEqual(neg["uncovered"]["lib/cal.cpp"], [6])

    def test_header_code_instantiated_by_the_test_counts(self):
        self.assertEqual(self.res["gen_01.cpp"]["covered"]["lib/cal.hpp"], [4, 5, 7])
        self.assertEqual(self.res["gen_01.cpp"]["uncovered"]["lib/cal.hpp"], [6])
        self.assertNotIn("lib/cal.hpp", self.res["gen_02.cpp"]["covered"])

    def test_the_build_tree_is_left_alone(self):
        self.assertEqual(sorted(p.name for p in (self.obj / "lib").iterdir()), ["cal.cpp.gcno", "cal.cpp.o"])

    def test_union(self):
        env = argparse.Namespace(new_dir=str(self.tmp / "cov-src"))
        u = coverage_loop.aggregate(env, {"lib/cal.cpp": [3, 4, 5, 6]}, self.res)
        self.assertEqual(u["covered"], {"lib/cal.cpp": [3, 4, 5, 6]})
        self.assertEqual(coverage_loop.counts(u)["exec_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()


class Wiring(unittest.TestCase):
    def test_env_link_flags_for_the_coverage_library(self):
        from env import Env
        e = Env("quantlib", 1, "a", "b", "/x/a", "/x/b", ["."], "/x/a/lib", "/x/b/lib", "QuantLib")
        self.assertEqual(e.cov_link_flags(), [])
        e.cov_lib = "/x/b/lib-cov"
        self.assertEqual(e.cov_link_flags(), ["-L/x/b/lib-cov", "-lQuantLib", "-Wl,-rpath,/x/b/lib-cov"])

    def test_refine_runs_for_cmake_targets_with_a_coverage_build_only(self):
        import batch
        from types import SimpleNamespace
        from unittest import mock
        import llm
        for cfg, expect in (({"build_mode": "cmake", "coverage_cmake_args": ["-DX"]}, True),   # QuantLib
                            ({"build_mode": "cmake"}, False),                                   # duckdb
                            ({"build_mode": "header-only"}, True)):
            with tempfile.TemporaryDirectory() as d:
                t = SimpleNamespace(name="t", repo=Path(d), data=Path(d), get=lambda k, dflt=None, c=cfg: c.get(k, dflt))
                (Path(d) / "tests" / "1").mkdir(parents=True)
                calls = []
                args = argparse.Namespace(redo="", limit=None, max_failures=5, dry_run=False, model="m",
                                          classify_model=None, docker=False, skip_commit_check=True, no_refine=False)
                with mock.patch.object(llm, "calls_today", return_value=0), mock.patch.object(llm, "limits", return_value=(15, 500)):
                    batch.batch(t, [{"pr": 1}], args, runner=lambda st, *x: calls.append(st) or 0, say=lambda *_: None,
                                data_dir=Path(d), log_dir=Path(d) / "logs")
                self.assertEqual("refine" in calls, expect, cfg)

    def test_quantlib_config_measures_ql_with_a_debug_coverage_build(self):
        sys.path.insert(0, str(HERE.parent))
        from pipeline.common import Target
        t = Target("quantlib")
        self.assertEqual(t.get("coverage_paths"), ["ql"])
        self.assertIn("-DCMAKE_BUILD_TYPE=Debug", t.get("coverage_cmake_args"))
        self.assertIsNone(Target("duckdb").get("coverage_cmake_args"))
