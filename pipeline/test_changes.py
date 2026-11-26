"""Unit tests for changes.py. Run: python3 -m unittest pipeline.test_changes

The libclang tests parse a small synthetic header and are skipped when libclang or clang's builtin headers are not
installed; the rest need nothing."""
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.changes import changed_lines, classify_access, conditions_at, innermost, merge_sides, shorten_templates

DIFF = """diff --git a/include/a.hpp b/include/a.hpp
--- a/include/a.hpp
+++ b/include/a.hpp
@@ -10,2 +10,3 @@ int f()
-    return 1;
-    // x
+    return 2;
+    // y
+    // z
@@ -30,0 +32,4 @@ struct S
+    int g();
+    int h();
+    int i();
+    int j();
@@ -50 +55,0 @@ int k()
-    k_body();
diff --git a/include/gone.hpp b/include/gone.hpp
deleted file mode 100644
--- a/include/gone.hpp
+++ /dev/null
@@ -1,2 +0,0 @@
-int gone();
-int gone2();
"""


class ChangedLines(unittest.TestCase):
    def setUp(self):
        self.cl = changed_lines(DIFF)

    def test_replacement_marks_both_sides(self):
        self.assertTrue({10, 11} <= self.cl["include/a.hpp"]["old"])
        self.assertTrue({10, 11, 12} <= self.cl["include/a.hpp"]["new"])

    def test_pure_insertion_anchors_on_old_side(self):
        self.assertIn(30, self.cl["include/a.hpp"]["old"])
        self.assertTrue(set(range(32, 36)) <= self.cl["include/a.hpp"]["new"])

    def test_pure_deletion_anchors_on_new_side(self):
        self.assertIn(50, self.cl["include/a.hpp"]["old"])
        self.assertIn(55, self.cl["include/a.hpp"]["new"])

    def test_deleted_file(self):
        self.assertEqual(self.cl["include/gone.hpp"]["old"], {1, 2})
        self.assertEqual(self.cl["include/gone.hpp"]["new"], set())

    def test_renamed_file_keeps_old_path(self):
        d = changed_lines("diff --git a/x/old.hpp b/x/new.hpp\nsimilarity index 90%\nrename from x/old.hpp\n"
                          "rename to x/new.hpp\n--- a/x/old.hpp\n+++ b/x/new.hpp\n@@ -3 +3 @@\n-a\n+b\n")
        self.assertEqual(d["x/new.hpp"]["old_path"], "x/old.hpp")
        self.assertEqual((d["x/new.hpp"]["old"], d["x/new.hpp"]["new"]), ({3}, {3}))


class Conditions(unittest.TestCase):
    SRC = ["#if A", "x", "#else", "y", "#endif", "#ifdef B", "  #if C", "z", "  #endif", "#endif", "w"]

    def test_stack(self):
        self.assertEqual(conditions_at(self.SRC, 2), ["if A"])
        self.assertEqual(conditions_at(self.SRC, 4), ["!(if A)"])
        self.assertEqual(conditions_at(self.SRC, 8), ["ifdef B", "if C"])
        self.assertEqual(conditions_at(self.SRC, 11), [])


class Innermost(unittest.TestCase):
    ENTS = [{"start": 1, "end": 100, "kind": "type", "id": "class"},
            {"start": 10, "end": 20, "kind": "function", "id": "method"},
            {"start": 10, "end": 20, "kind": "type", "id": "nested"},
            {"start": 12, "end": 14, "kind": "type", "id": "local"}]

    def test_smallest_wins(self):
        self.assertEqual(innermost(self.ENTS, 13)["id"], "local")

    def test_function_wins_tie(self):
        self.assertEqual(innermost(self.ENTS, 18)["id"], "method")

    def test_outer(self):
        self.assertEqual(innermost(self.ENTS, 50)["id"], "class")

    def test_none(self):
        self.assertIsNone(innermost(self.ENTS, 101))


class Access(unittest.TestCase):
    PRIV = ["detail", "impl"]

    def test_public(self):
        self.assertEqual(classify_access([("namespace", "lib", None), ("class", "C", None)], "public", None,
                                         self.PRIV), ("public", None))

    def test_detail_namespace(self):
        self.assertEqual(classify_access([("namespace", "lib", None), ("namespace", "detail", None)], None, None,
                                         self.PRIV)[0], "private")

    def test_anonymous_namespace(self):
        self.assertEqual(classify_access([("namespace", "", None)], None, None, self.PRIV)[1],
                         "namespace (anonymous)")

    def test_private_member_and_enclosing_private_class(self):
        self.assertEqual(classify_access([("class", "C", None)], "private", None, self.PRIV)[0], "private")
        self.assertEqual(classify_access([("class", "C", None), ("class", "Inner", "protected")], "public", None,
                                         self.PRIV)[0], "private")

    def test_internal_linkage(self):
        self.assertEqual(classify_access([], None, "internal", self.PRIV), ("private", "internal linkage"))


class Shorten(unittest.TestCase):
    def test_long_lists_collapse_short_stay(self):
        long = "const basic_json<ObjectType, ArrayType, StringType, BooleanType, NumberIntegerType> &"
        self.assertEqual(shorten_templates(f"lib::merge_diff({long}, {long})"),
                         "lib::merge_diff(const basic_json<...> &, const basic_json<...> &)")
        self.assertEqual(shorten_templates("lib::get<std::string>()"), "lib::get<std::string>()")
        self.assertEqual(shorten_templates("f(std::map<std::string, std::vector<int>>)"),
                         "f(std::map<std::string, std::vector<int>>)")


class MergeSides(unittest.TestCase):
    def test_status_and_order(self):
        e = lambda n, a, k: {"name": n, "access": a, "lines_changed": k}  # noqa: E731
        out = merge_sides({"x": e("x", "public", 2), "gone": e("gone", "public", 1)},
                          {"x": e("x", "public", 3), "new": e("new", "private", 4)})
        self.assertEqual([(o["name"], o["status"], o["lines_changed"]) for o in out],
                         [("new", "added", 4), ("x", "modified", 5), ("gone", "removed", 1)])


HEADER = """#pragma once
namespace lib {
namespace detail {
template<typename T> struct is_key { static constexpr bool value = true; };
inline int helper(int x) { return x + 1; }
}  // namespace detail
class Box {
  public:
    template<typename K, typename = typename std::enable_if<detail::is_key<K>::value>::type>
    int at(K k) const { return detail::helper(static_cast<int>(k)); }
    int size() const { return n; }
  private:
    int grow() { return ++n; }
    int n = 0;
};
class Shape {
  public:
    double area() const { return impl_->area(); }
  protected:
    struct Impl { virtual ~Impl() = default; virtual double area() const = 0; };
    Impl* impl_ = nullptr;
};
class Square : public Shape {
    struct SquareImpl : Shape::Impl { double area() const override { return 4.0; } };
};
}  // namespace lib
"""


def _clang_ready():
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return any(shutil.which(c) for c in ("clang", "clang-18")) or False


@unittest.skipUnless(_clang_ready(), "libclang or clang not installed")
class WithLibclang(unittest.TestCase):
    """Parse a tiny library and check naming, access and reverse references end to end."""

    @classmethod
    def setUpClass(cls):
        from pipeline.changes import Analyzer, resource_dir
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "include" / "lib").mkdir(parents=True)
        (cls.tmp / "include" / "lib" / "box.hpp").write_text("#include <type_traits>\n" + HEADER)

        class T:  # the parts of pipeline.common.Target the Analyzer reads
            name = "unit"
            cfg = {"include_dirs": ["include"], "smoke_header": "lib/box.hpp"}

            def get(self, k, d=None):
                return self.cfg.get(k, d)

        cls.an = Analyzer(T(), cls.tmp, resource_dir(T()))
        cls.ents = cls.an.entities_in("include/lib/box.hpp")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def at_line(self, text):
        n = ("#include <type_traits>\n" + HEADER).splitlines().index(text) + 1
        return self.an.describe(innermost(self.ents, n)["cursor"])

    def test_no_parse_errors(self):
        self.an.entry_tu()
        self.assertEqual(self.an.errors, 0)

    def test_private_helper_and_its_public_callers(self):
        d = self.at_line("inline int helper(int x) { return x + 1; }")
        self.assertEqual((d["name"], d["access"], d["private_because"]),
                         ("lib::detail::helper(int)", "private", "namespace detail"))
        self.assertEqual(self.an.reached_via(d["usr"]), [{"name": "lib::Box::at(K)", "member": True}])

    def test_trait_reached_through_template_constraint(self):
        d = self.at_line("template<typename T> struct is_key { static constexpr bool value = true; };")
        self.assertEqual(d["access"], "private")
        self.assertIn("lib::Box::at(K)", [v["name"] for v in self.an.reached_via(d["usr"])])

    def test_override_reached_through_virtual_call(self):
        d = self.at_line("    struct SquareImpl : Shape::Impl { double area() const override { return 4.0; } };")
        self.assertEqual(d["access"], "private")
        self.assertIn("lib::Shape::area()", [v["name"] for v in self.an.reached_via(d["usr"])])

    def test_fatal_parse_error_stops_instead_of_partial_results(self):
        from pipeline.changes import Analyzer
        (self.tmp / "include" / "lib" / "broken.hpp").write_text("#include <no_such_header.hpp>\nint f();\n")
        an = Analyzer(self.an.t, self.tmp, self.an.resdir)
        with self.assertRaisesRegex(RuntimeError, "fatal parse error"):
            an.entities_in("include/lib/broken.hpp")

    def test_analysis_include_dirs_reach_headers_only_library_sources_use(self):
        """A compiled library's .cpp includes vendored headers (duckdb: third_party/fmt/include) that are not in
        include_dirs; analysis_include_dirs makes them reachable, so the .cpp parses without a fatal error."""
        from pipeline.changes import Analyzer
        (self.tmp / "vendor" / "inc").mkdir(parents=True, exist_ok=True)
        (self.tmp / "vendor" / "inc" / "vend.hpp").write_text("inline int vend() { return 7; }\n")
        (self.tmp / "src").mkdir(exist_ok=True)
        (self.tmp / "src" / "impl.cpp").write_text('#include "vend.hpp"\n#include <lib/box.hpp>\nint impl_fn() { return vend(); }\n')
        without = Analyzer(self.an.t, self.tmp, self.an.resdir)
        with self.assertRaisesRegex(RuntimeError, "fatal parse error"):
            without.entities_in("src/impl.cpp")

        class T2:
            name = "unit"
            cfg = {**self.an.t.cfg, "analysis_include_dirs": ["vendor/inc"]}

            def get(self, k, d=None):
                return self.cfg.get(k, d)

        an = Analyzer(T2(), self.tmp, self.an.resdir)
        self.assertEqual([a for a in an.args if a.startswith("-I")],
                         [f"-I{self.tmp / 'include'}", f"-I{self.tmp / 'vendor' / 'inc'}"])
        self.assertIn("impl_fn()", [an.describe(e["cursor"])["name"] for e in an.entities_in("src/impl.cpp")])

    def test_public_and_private_members(self):
        self.assertEqual(self.at_line("    int size() const { return n; }")["access"], "public")
        d = self.at_line("    int grow() { return ++n; }")
        self.assertEqual((d["access"], d["member"]), ("private", True))


if __name__ == "__main__":
    unittest.main()
