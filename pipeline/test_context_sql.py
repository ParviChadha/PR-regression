"""Unit tests for context.py's SQL (sqllogictest) mode, used for duckdb. No git, no network, except the last test, which
runs on the real duckdb clone when repos/duckdb and data/duckdb/changes exist. Run: python3 -m unittest pipeline.test_context_sql"""
import json
import unittest
from types import SimpleNamespace

from pipeline import context
from pipeline.common import Target, read_jsonl
from pipeline.context import (path_words, scope_parts, sql_blocks, sql_name_map, sql_record_around, sql_records,
                              sql_search_terms, sql_setup, sql_skipped, sql_term_regex)

HEADER = '''
struct AvgFun {
	static constexpr const char *Name = "avg";
	static constexpr const char *Parameters = "x";
	static AggregateFunctionSet GetFunctions();
};

struct MeanFun {
	using ALIAS = AvgFun;

	static constexpr const char *Name = "mean";
};

struct ThreadsSetting {
	using RETURN_TYPE = int64_t;
	static constexpr const char *Name = "threads";
};

struct NoNameHere {
	int x;
};
'''

SQL = """# name: test/sql/aggregate/test_avg.test
# group: [aggregate]

statement ok
CREATE TABLE integers(i INTEGER);

statement ok
INSERT INTO integers VALUES (1), (2), (3)

statement ok
CREATE TABLE unrelated(j INTEGER);

statement ok
CREATE VIEW v AS SELECT i FROM integers;

query R
SELECT AVG(i) FROM v
----
2

# avg in a comment: avg(x) is not a use
query I
SELECT 42
----
42
"""


class FakeTarget(SimpleNamespace):
    def get(self, key, default=None):
        return self.cfg.get(key, default)


T = FakeTarget(name="fake", cfg={"sql_test_ext": [".test"], "sql_missing_requires": ["parquet", "icu"]})


class NameMap(unittest.TestCase):
    def test_struct_names_and_aliases(self):
        m = sql_name_map({"a.hpp": HEADER})
        self.assertEqual(m["AvgFun"], ["avg", "mean"])          # the alias's SQL name belongs to what it aliases
        self.assertEqual(m["MeanFun"], ["mean"])
        self.assertEqual(m["ThreadsSetting"], ["threads"])
        self.assertNotIn("NoNameHere", m)

    def test_name_does_not_leak_across_structs(self):
        text = "struct A {\n int x;\n};\nstruct B {\n static constexpr const char *Name = \"b\";\n};\n"
        self.assertEqual(sql_name_map({"x": text}), {"B": ["b"]})

    def test_scope_parts(self):
        self.assertEqual(scope_parts("duckdb::AvgFun::GetFunctions()"), ["duckdb", "AvgFun", "GetFunctions"])
        self.assertEqual(scope_parts("duckdb::(anonymous)::Op<T>::Combine(const STATE &, STATE &)"),
                         ["duckdb", "(anonymous)", "Op", "Combine"])


class Terms(unittest.TestCase):
    def test_terms_from_changed_and_reaching_entities(self):
        m = sql_name_map({"a.hpp": HEADER})
        changes = {"functions": [
            {"name": "duckdb::(anonymous)::TimestampNSAverageOperation::Combine(const STATE &)", "access": "private",
             "reached_via": [{"name": "duckdb::AvgFun::GetFunctions()", "member": True}]},
            {"name": "duckdb::ThreadsSetting::SetGlobal(DatabaseInstance *)", "access": "public", "reached_via": []},
        ]}
        terms = sql_search_terms(changes, m)
        self.assertEqual([(x["name"], x["kind"]) for x in terms], [("avg", "sql"), ("mean", "sql"), ("threads", "setting")])
        self.assertIn("reached", terms[0]["role"])
        self.assertIn("changed", terms[2]["role"])

    def test_regex_call_for_functions_word_for_settings(self):
        f = sql_term_regex({"name": "avg", "kind": "sql"})
        self.assertTrue(f.search("SELECT AVG (i) FROM t"))
        self.assertFalse(f.search("SELECT avg_price FROM t"))
        self.assertFalse(f.search("SELECT t.avg(1)"))
        s = sql_term_regex({"name": "threads", "kind": "setting"})
        self.assertTrue(s.search("SET threads=4"))
        self.assertTrue(s.search("SELECT current_setting('threads')"))
        self.assertFalse(s.search("SET threads_x=1"))


class Records(unittest.TestCase):
    def test_records_and_record_around(self):
        lines = SQL.splitlines()
        recs = sql_records(lines)
        self.assertEqual(lines[recs[0][0]], "# name: test/sql/aggregate/test_avg.test")
        i = next(n for n, l in enumerate(lines) if "AVG(i)" in l)
        s, e = sql_record_around(lines, i)
        self.assertEqual(lines[s], "query R")
        self.assertEqual(lines[e], "2")

    def test_setup_takes_only_what_the_record_uses_view_brings_its_table(self):
        lines = SQL.splitlines()
        i = next(n for n, l in enumerate(lines) if "AVG(i)" in l)
        s, e = sql_record_around(lines, i)
        setup = sql_setup(lines, s, e)
        self.assertIn("CREATE VIEW v", setup)
        self.assertIn("CREATE TABLE integers", setup)              # through the view (second pass)
        self.assertIn("INSERT INTO integers", setup)
        self.assertNotIn("unrelated", setup)
        self.assertLess(setup.index("CREATE TABLE integers"), setup.index("CREATE VIEW v"))   # file order

    def test_files_needing_a_missing_extension_are_skipped(self):
        self.assertEqual(sql_skipped(T, "# x\nrequire parquet\n\nquery I\nSELECT 1\n"), "parquet")
        self.assertIsNone(sql_skipped(T, "require skip_reload\nrequire vector_size 2048\n"))

    def test_title_terms(self):
        known = {"struct_update", "contains"}
        got = lambda title: [(x["name"], x["kind"]) for x in context.title_terms(title, known)]
        self.assertEqual(got("Fix #28562: contains(list_column, '') returns true"), [("contains", "sql"), ("list_column", "word")])
        self.assertEqual(got("Keep the fields struct_update writes"), [("struct_update", "sql")])
        self.assertEqual(got("Compare TIMESTAMPTZ_NS with TIMESTAMPTZ"), [("TIMESTAMPTZ_NS", "word")])
        self.assertEqual(got("SUMMARIZE over types (TIMESTAMP_NS)"), [("TIMESTAMP_NS", "word")])   # "types (" is prose
        self.assertEqual(got("fix(join-condition): keep the same execution order"), [])
        self.assertEqual(got("Make `GetConstraints` const and `new_line` work"), [("new_line", "word")])
        self.assertEqual([x["name"] for x in context.title_terms("contains(x)", known, ["CONTAINS"])], [])  # already searched

    def test_path_words(self):
        self.assertEqual(path_words("src/optimizer/cte_filter_pusher.cpp"), {"optimizer", "cte", "filter", "pusher"})


class Blocks(unittest.TestCase):
    def test_named_function_blocks_with_setup(self):
        m = sql_name_map({"a.hpp": HEADER})
        changes = {"functions": [{"name": "duckdb::AvgFun::GetFunctions()", "access": "public", "reached_via": []}]}
        texts = {"test/sql/aggregate/test_avg.test": SQL, "test/sql/x/needs_parquet.test": "require parquet\n\nquery I\nSELECT avg(1)\n----\n1\n"}
        blocks, terms, fallback = sql_blocks(T, {"pr": 1, "main_files": []}, changes, texts, m)
        self.assertIsNone(fallback)
        self.assertEqual(len(blocks), 1)                              # the comment and the parquet file do not count
        self.assertEqual(blocks[0]["names"], {"avg"})
        self.assertTrue(blocks[0]["text"].startswith("statement ok\nCREATE TABLE integers"))
        self.assertTrue(blocks[0]["text"].endswith("query R\nSELECT AVG(i) FROM v\n----\n2"))
        self.assertEqual({t["name"]: t["hits"] for t in terms}, {"avg": 1, "mean": 0})

    def test_path_fallback_when_no_name_matches(self):
        changes = {"functions": [{"name": "duckdb::CTEFilterPusher::Optimize()", "access": "public", "reached_via": []}],
                   "files": ["src/optimizer/cte_filter_pusher.cpp"]}
        texts = {"test/optimizer/cte/cte_filter.test": "statement ok\nCREATE TABLE t(i INT);\n\nquery I\nWITH c AS (SELECT * FROM t) SELECT * FROM c WHERE i > 1\n----\n",
                 "test/sql/other/thing.test": "query I\nSELECT 1\n----\n1\n"}
        blocks, terms, fallback = sql_blocks(T, {"pr": 2}, changes, texts, {})
        self.assertEqual(fallback, "path")
        self.assertEqual([b["file"] for b in blocks], ["test/optimizer/cte/cte_filter.test"])
        self.assertIn("CREATE TABLE t", blocks[0]["text"])
        self.assertTrue(all(n.startswith("path:") for n in blocks[0]["names"]))


class RealDuckdb(unittest.TestCase):
    def test_avg_pr_gets_avg_examples(self):
        try:
            t = Target("duckdb")
        except SystemExit:
            self.skipTest("no duckdb target")
        cp = t.data / "changes" / "27903.json"
        if not (t.repo / ".git").exists() or not cp.is_file():
            self.skipTest("needs repos/duckdb and data/duckdb/changes/27903.json")
        rec = next(r for r in read_jsonl(t.data / "prs.jsonl") if r["pr"] == 27903)
        text, meta = context.build_context(t, rec, json.loads(cp.read_text()), 7000)
        self.assertIsNotNone(text)
        self.assertIn("avg", [x["name"] for x in meta["sql_terms"]])
        self.assertNotIn("fallback", meta)
        self.assertRegex(text, r"(?i)\bavg\s*\(|approx_quantile\s*\(|\bmean\s*\(")
        self.assertLessEqual(len(text), 7000)


if __name__ == "__main__":
    unittest.main()
