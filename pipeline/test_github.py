"""Unit tests for github.py (no network). Run: python3 -m unittest pipeline.test_github"""
import unittest

from pipeline.github import build_record, fetch_one, linked_issues, referenced_numbers

REPO = "nlohmann/json"


class LinkedIssues(unittest.TestCase):
    def test_closing_keywords(self):
        self.assertEqual(linked_issues("Fixes #12. Also closes #34 and resolved #56", REPO), [12, 34, 56])

    def test_case_colon_and_dedup(self):
        self.assertEqual(linked_issues("FIXES: #7\nfix #7", REPO), [7])

    def test_same_repo_qualified_and_url(self):
        text = "Closes nlohmann/json#8, fixes https://github.com/nlohmann/json/issues/9"
        self.assertEqual(linked_issues(text, REPO), [8, 9])

    def test_other_repo_ignored(self):
        self.assertEqual(linked_issues("Fixes fmtlib/fmt#100", REPO), [])

    def test_plain_mention_is_not_a_link(self):
        self.assertEqual(linked_issues("Related to #77; see #78", REPO), [])

    def test_empty(self):
        self.assertEqual(linked_issues(None, REPO), [])


class Referenced(unittest.TestCase):
    def test_bare_refs_not_html_entities_or_urls(self):
        self.assertEqual(referenced_numbers("Since #4958 ... see a/b#3 and &#39; #4958"), [4958])


class FetchOne(unittest.TestCase):
    """fetch_one against a fake transport shaped like the GitHub REST API."""

    def fake_get(self, path):
        self.calls.append(path)
        base = path.split("?")[0]
        if base == f"repos/{REPO}/pulls/4958":
            return {"number": 4958, "title": "support string_view keys", "body": "Fixes #4950, see #4900",
                    "user": {"login": "alice", "type": "User", "id": 1}, "labels": [{"name": "bug"}],
                    "state": "closed", "merged_at": "2025-10-01T00:00:00Z", "merge_commit_sha": "abc",
                    "base": {"ref": "develop", "sha": "b1"}, "head": {"sha": "h1"}}
        if base == f"repos/{REPO}/issues/4958/comments":
            return [{"user": {"login": "bob", "type": "User"}, "body": "LGTM", "created_at": "t"}]
        if base == f"repos/{REPO}/pulls/4958/comments":
            return []
        if base == f"repos/{REPO}/issues/4950":
            return {"title": "keys broken", "body": "repro", "labels": [], "state": "closed"}
        raise AssertionError(f"unexpected call {path}")

    def setUp(self):
        self.calls = []

    def test_record(self):
        rec = fetch_one(self.fake_get, REPO, 4958, "fake")
        self.assertEqual(rec["title"], "support string_view keys")
        self.assertEqual(rec["labels"], ["bug"])
        self.assertEqual(rec["user"], {"login": "alice", "type": "User"})
        self.assertEqual(rec["comments"][0]["body"], "LGTM")
        self.assertEqual([i["number"] for i in rec["linked_issues"]], [4950])
        self.assertEqual(rec["referenced_numbers"], [4950, 4900])
        self.assertEqual(rec["merge_commit_sha"], "abc")
        self.assertEqual(len(self.calls), 4)

    def test_link_to_a_pr_is_dropped(self):
        def get(path):
            if path.startswith(f"repos/{REPO}/issues/4950"):
                return {"title": "a PR", "pull_request": {}, "labels": []}
            return self.fake_get(path)
        self.assertEqual(fetch_one(get, REPO, 4958, "fake")["linked_issues"], [])

    def test_missing_pr(self):
        self.assertIsNone(fetch_one(lambda p: None, REPO, 1, "fake"))


class Paging(unittest.TestCase):
    def test_follows_full_pages(self):
        from pipeline.github import paged, PER_PAGE
        pages = {1: [{}] * PER_PAGE, 2: [{}] * 3}
        got = paged(lambda p: pages[int(p.rsplit("page=", 1)[1])], "x")
        self.assertEqual(len(got), PER_PAGE + 3)


if __name__ == "__main__":
    unittest.main()
