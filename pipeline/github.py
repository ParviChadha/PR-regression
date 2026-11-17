"""Fetch PR metadata from GitHub for `collect.py --github`.

Per PR it stores the title, description, labels, discussion comments, review comments and
the issues the PR says it closes, in data/<target>/github/<pr>.json (committed, so the
experiment never depends on GitHub again). Files already on disk are not refetched.

Transport, picked once per run:
  * `gh api` when the GitHub CLI is installed and logged in. gh holds the credential;
    this code never reads, stores or passes a token (CLAUDE.md: no credentials).
  * otherwise unauthenticated HTTPS: 60 requests/hour, enough for ~15-20 PRs an hour.
Cost: 3 requests per PR (PR, discussion comments, review comments) + 1 per linked issue,
more only for PRs with over 100 comments.

On a rate limit the run stops cleanly: everything fetched so far is on disk, and rerunning
the same command continues where it stopped.
"""
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
PER_PAGE = 100

# GitHub's closing keywords: https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue
CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?:https?://github\.com/)?(?P<repo>[\w.-]+/[\w.-]+)(?:#|/issues/))?#?(?P<num>\d+)",
    re.I)
REF_RE = re.compile(r"(?<![\w/&])#(\d+)\b")


class RateLimited(Exception):
    pass


# ---------- pure functions (unit-tested in pipeline/test_github.py) ----------

def linked_issues(text, repo):
    """Issue numbers in `repo` that `text` says it closes ("Fixes #12", "closes owner/repo#12", URLs)."""
    out = []
    for m in CLOSING_RE.finditer(text or ""):
        if m.group("repo") and m.group("repo").lower() != repo.lower():
            continue
        n = int(m.group("num"))
        if n not in out:
            out.append(n)
    return out


def referenced_numbers(text):
    """Every bare #N in `text` (issues or PRs; not fetched, kept for context)."""
    out = []
    for m in REF_RE.finditer(text or ""):
        n = int(m.group(1))
        if n not in out:
            out.append(n)
    return out


def slim_user(u):
    return {"login": (u or {}).get("login"), "type": (u or {}).get("type")}


def build_record(repo, pr, comments, review_comments, issues, transport):
    """The JSON stored per PR, from raw API responses."""
    body = pr.get("body") or ""
    return {
        "repo": repo,
        "number": pr["number"],
        "title": pr.get("title"),
        "body": body,
        "user": slim_user(pr.get("user")),
        "labels": [l["name"] for l in pr.get("labels", [])],
        "state": pr.get("state"),
        "created_at": pr.get("created_at"),
        "merged_at": pr.get("merged_at"),
        "merge_commit_sha": pr.get("merge_commit_sha"),
        "base_ref": (pr.get("base") or {}).get("ref"),
        "base_sha": (pr.get("base") or {}).get("sha"),
        "head_sha": (pr.get("head") or {}).get("sha"),
        "comments": [{"user": slim_user(c.get("user")), "created_at": c.get("created_at"),
                      "body": c.get("body") or ""} for c in comments],
        "review_comments": [{"user": slim_user(c.get("user")), "created_at": c.get("created_at"),
                             "path": c.get("path"), "line": c.get("line") or c.get("original_line"),
                             "diff_hunk": c.get("diff_hunk"), "body": c.get("body") or ""}
                            for c in review_comments],
        "linked_issues": issues,
        "referenced_numbers": [n for n in referenced_numbers(body) if n != pr["number"]],
        "transport": transport,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------- transport ----------

def gh_ready():
    if not shutil.which("gh"):
        return False
    return subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


def get_gh(path):
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip()
        if "rate limit" in err.lower() or "HTTP 429" in err:
            raise RateLimited(err)
        if "HTTP 404" in err:
            return None
        raise RuntimeError(f"gh api {path}: {err}")
    return json.loads(r.stdout)


def get_https(path):
    req = urllib.request.Request(f"{API}/{path}", headers={
        "Accept": "application/vnd.github+json", "User-Agent": "pr-regression-research"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            reset = e.headers.get("X-RateLimit-Reset")
            when = time.strftime("%H:%M", time.localtime(int(reset))) if reset else "later"
            raise RateLimited(f"unauthenticated limit (60/hour) reached; resets at {when}")
        raise RuntimeError(f"GET {path}: HTTP {e.code} {e.reason}") from e


def paged(get, path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        batch = get(f"{path}{sep}per_page={PER_PAGE}&page={page}") or []
        out.extend(batch)
        if len(batch) < PER_PAGE:
            return out
        page += 1


def fetch_one(get, repo, n, transport):
    pr = get(f"repos/{repo}/pulls/{n}")
    if pr is None:
        return None
    comments = paged(get, f"repos/{repo}/issues/{n}/comments")
    review_comments = paged(get, f"repos/{repo}/pulls/{n}/comments")
    issues = []
    for i in linked_issues(pr.get("body") or "", repo):
        it = get(f"repos/{repo}/issues/{i}")
        if it is None or "pull_request" in it:       # a "Fixes #N" that points at a PR, not an issue
            continue
        issues.append({"number": i, "title": it.get("title"), "body": it.get("body") or "",
                       "labels": [l["name"] for l in it.get("labels", [])], "state": it.get("state")})
    return build_record(repo, pr, comments, review_comments, issues, transport)


def fetch_all(t, prs, refresh=False):
    """Fetch metadata for PR numbers `prs` of target `t`. Returns {pr: record or None}."""
    repo = t["github_repo"]
    out_dir = t.data / "github"
    out_dir.mkdir(parents=True, exist_ok=True)
    if gh_ready():
        get, transport = get_gh, "gh"
    else:
        get, transport = get_https, "https-unauthenticated"
        print("github: gh CLI not logged in; using unauthenticated API (60 requests/hour)", file=sys.stderr)

    results, todo = {}, []
    for n in prs:
        path = out_dir / f"{n}.json"
        if path.exists() and not refresh:
            results[n] = json.loads(path.read_text())
        else:
            todo.append(n)
    print(f"github: {len(results)} cached, {len(todo)} to fetch via {transport}", file=sys.stderr)

    for i, n in enumerate(todo, 1):
        try:
            rec = fetch_one(get, repo, n, transport)
        except RateLimited as e:
            print(f"github: stopped at PR #{n} ({i - 1}/{len(todo)} fetched): {e}. "
                  f"Rerun the same command to continue.", file=sys.stderr)
            break
        results[n] = rec
        if rec is not None:
            (out_dir / f"{n}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        if i % 10 == 0:
            print(f"github: {i}/{len(todo)}", file=sys.stderr)
    return results
