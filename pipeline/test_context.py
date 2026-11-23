"""Unit tests for context.py (no git, no network). Run: python3 -m unittest pipeline.test_context"""
import re
import unittest

from pipeline.context import (DEFAULT_TEST_BLOCK_RE, FILE_BONUS, block_around, file_affinity, operator_symbol,
                              search_terms, select_blocks, simple_name, term_regex)


class SimpleName(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(simple_name("lib::Box::at(KeyType &&)"), "at")
        self.assertEqual(simple_name("lib::detail::is_key"), "is_key")
        self.assertEqual(simple_name("parse"), "parse")
        self.assertIsNone(simple_name("lib::operator==(const_reference, const_reference)"))
        self.assertIsNone(simple_name("lib::Box::operator[](KeyType &&)"))
        self.assertIsNone(simple_name("lib::Box::~Box()"))


CHANGES = {"functions": [
    {"name": "lib::detail::is_key", "kind": "type", "access": "private", "member": False,
     "reached_via": [{"name": "lib::Box::at(K) const", "member": True},
                     {"name": "lib::Box::operator[](K)", "member": True},
                     {"name": "lib::parse(const char *)", "member": False}]},
    {"name": "lib::Box::size() const", "kind": "function", "access": "public", "member": True, "reached_via": []},
    {"name": "LIB_DEFINE", "kind": "macro", "access": None, "reached_via": []},
]}


class Terms(unittest.TestCase):
    def test_order_roles_and_operator_skipped(self):
        got = [(x["name"], x["kind"], x["role"]) for x in search_terms(CHANGES)]
        self.assertEqual(got, [("size", "member", "changed public function"),
                               ("LIB_DEFINE", "macro", "changed macro"),
                               ("at", "member", "public entry point"),
                               ("parse", "function", "public entry point"),
                               ("operator[]", "title", "operator: test titles"),
                               ("is_key", "type", "changed private type")])

    def test_operator_symbols(self):
        self.assertEqual(operator_symbol("lib::operator==(const T &, const T &)"), "==")
        self.assertEqual(operator_symbol("lib::Box::operator[](K)"), "[]")
        self.assertEqual(operator_symbol("lib::Box::operator()(int)"), "()")
        self.assertEqual(operator_symbol("lib::operator<=>(const T &, const T &)"), "<=>")
        self.assertIsNone(operator_symbol("lib::Box::operator bool()"))
        self.assertIsNone(operator_symbol("lib::Box::size()"))


class Regex(unittest.TestCase):
    def rx(self, name, kind):
        return term_regex({"name": name, "kind": kind})

    def test_member_needs_dot_or_arrow(self):
        r = self.rx("at", "member")
        self.assertTrue(r.search('CHECK(j.at("key") == 1);'))
        self.assertTrue(r.search("p->at<int>(0)"))
        self.assertFalse(r.search("// look at(this)"))
        self.assertFalse(r.search("format(x)"))

    def test_free_function(self):
        r = self.rx("parse", "function")
        self.assertTrue(r.search('auto j = json::parse("[]");'))
        self.assertTrue(r.search('parse(s)'))
        self.assertFalse(r.search('reparse(s)'))

    def test_file_affinity(self):
        eq = [{"name": "operator==", "kind": "title"}]
        self.assertEqual(file_affinity("tests/src/unit-comparison.cpp", eq), FILE_BONUS)
        self.assertEqual(file_affinity("tests/src/unit-algorithms.cpp", eq), 0.0)
        self.assertEqual(file_affinity("tests/src/unit-contains.cpp", [{"name": "contains", "kind": "member"}]),
                         FILE_BONUS)
        self.assertEqual(file_affinity("tests/src/unit-meta.cpp", [{"name": "at", "kind": "member"}]), 0.0)

    def test_operator_title(self):
        r = term_regex({"name": "operator==", "kind": "title"})
        self.assertTrue(r.search('    SECTION("comparison operators")'))
        self.assertTrue(r.search('TEST_CASE("equality of numbers")'))
        self.assertFalse(r.search('    CHECK(a == b);'))
        self.assertFalse(r.search('    SECTION("dump")'))

    def test_type_any_use(self):
        r = self.rx("value_t", "type")
        self.assertTrue(r.search("json::value_t::object"))
        self.assertFalse(r.search("my_value_t x"))


TEST_FILE = """TEST_CASE("element access")
{
    SECTION("object")
    {
        json j = {{"a", 1}};
        SECTION("at")
        {
            CHECK(j.at("a") == 1);
            CHECK_THROWS(j.at("b"));
        }
        SECTION("size")
        {
            CHECK(j.size() == 1);
        }
    }
}
""".splitlines()


class Blocks(unittest.TestCase):
    RE = re.compile(DEFAULT_TEST_BLOCK_RE)

    def test_innermost_section_with_closing_brace(self):
        i = TEST_FILE.index('            CHECK(j.at("a") == 1);')
        s, e = block_around(TEST_FILE, i, self.RE)
        self.assertEqual(TEST_FILE[s].strip(), 'SECTION("at")')
        self.assertEqual(TEST_FILE[e].strip(), "}")
        self.assertEqual(e - s, 4)

    def test_preprocessor_line_does_not_close_block(self):
        lines = ['    SECTION("s")', "    {", "        int a = 1;", "#if X", "        use(a);", "#endif", "    }"]
        self.assertEqual(block_around(lines, 4, self.RE), (0, 6))

    def test_no_block_gives_window(self):
        lines = ["int x;"] * 40
        self.assertEqual(block_around(lines, 20, self.RE), (8, 32))

    def test_select_respects_budget_overlap_and_per_file(self):
        b = lambda f, s, e, sc, n=10: {"file": f, "start": s, "end": e, "score": sc, "text": "x" * n}  # noqa: E731
        blocks = [b("a", 1, 10, 3), b("a", 5, 12, 2.5), b("a", 20, 30, 2), b("a", 40, 50, 1.9),
                  b("b", 1, 5, 1), b("c", 1, 5, 0.5, n=10_000)]
        got = [(x["file"], x["start"]) for x in select_blocks(blocks, budget=400)]
        self.assertEqual(got, [("a", 1), ("a", 20), ("b", 1)])


if __name__ == "__main__":
    unittest.main()
