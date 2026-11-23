"""Collect a target's merged PRs from git history and apply Testora's PR filters, adapted to C++.

Usage:
    python3 -m pipeline.collect <target> [--checked N] [--github] [--refresh-github]

Reads the full-history clone in repos/<target>/ (scripts/fetch.sh makes it). Walks the
default branch's first-parent history newest-first. Every commit whose subject names a PR
("... (#123)" for squash merges, "Merge pull request #123" for merge commits) is one PR:
old = the commit's first parent, new = the commit itself.

Filters, in order (the first that fails is the PR's verdict):
    bot                  author or subject is a dependency/CI bot
    doc_title            title starts with "DOC" (Testora)
    no_main_source       no C++ file changed under `main_source` (tests, docs, CI, generated files excluded:
                         `generated_paths`, and with `generated_marker` any file whose first 20 lines match it)
    too_many_main_files  more than `max_main_files` main source files changed (Testora: 3)
    comment_only         every changed line in main source files is blank or a comment
PRs passing all filters are "checked". PRs in `seed_prs` are always collected, whatever their verdict.

Writes:
    data/<target>/prs_scanned.jsonl   every PR looked at, with its verdict (for the Table-3-style summary)
    data/<target>/prs.jsonl           the checked PRs plus seeded PRs: the pipeline's input
    data/<target>/collect_summary.json
With --github, also fetches PR title/body/comments/linked issues (pipeline/github.py) into
data/<target>/github/<pr>.json, and checks that GitHub's merge commit for each PR is the
commit this script took as `new` (a mismatch means the PR-number heuristic picked the wrong commit).

`collect_head` in target.toml pins the commit whose history is sampled, so reruns after a
`git fetch` select the same PRs.
"""
import argparse
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # also runnable as python3 pipeline/collect.py
from pipeline.common import Target, git, write_jsonl, write_text  # noqa: E402

CPP_EXT = {".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp", ".hxx", ".h++",
           ".ipp", ".inl", ".tcc", ".tpp"}

SQUASH_RE = re.compile(r"\(#(\d+)\)\s*$")
MERGE_RE = re.compile(r"^Merge pull request #(\d+)\b")
BOT_AUTHOR_RE = re.compile(r"\[bot\]|dependabot|github-actions|pre-commit-ci|renovate", re.I)
BOT_SUBJECT_RE = re.compile(r"^(build|chore)\(deps|^bump |^\[pre-commit|pre-commit autoupdate|"
                            r"^update pre-commit", re.I)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@ ?(.*)$")

GENERATED_MARKER_LINES = 20

FIELD = "\x1f"
RECORD = "\x1e"


# ---------- pure functions (unit-tested in pipeline/test_collect.py) ----------

def pr_number(subject):
    """PR number from a squash-merge or merge-commit subject, else None."""
    m = SQUASH_RE.search(subject) or MERGE_RE.match(subject)
    return int(m.group(1)) if m else None


def is_main_source(path, main_source, generated_paths):
    """True for a C++ file under a main_source path, outside generated paths and anything test-like."""
    p = pathlib.PurePosixPath(path)
    if p.suffix.lower() not in CPP_EXT:
        return False
    if any(path == g or path.startswith(g.rstrip("/") + "/") for g in generated_paths):
        return False
    if not any(path == m or path.startswith(m.rstrip("/") + "/") for m in main_source):
        return False
    return not any("test" in part.lower() for part in p.parts)   # Testora: ignore paths containing "test"


def is_trivial_line(line):
    """A changed line that cannot change behavior: blank or a comment line.

    Conservative: only whole-line comments count. A line like `*p = 1;` is code, so a leading
    '*' counts as a comment continuation only when followed by a space, '/' or end of line.
    """
    s = line.strip()
    if not s or s.startswith("//") or s.startswith("/*") or s.startswith("*/"):
        return True
    return s == "*" or s.startswith("* ") or s.startswith("*/")


def parse_diff(diff_text):
    """From a -U0 diff: added/removed counts, whether every changed line is trivial, hunk contexts."""
    added = removed = 0
    all_trivial = True
    contexts = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        m = HUNK_RE.match(line)
        if m:
            ctx = m.group(1).strip()
            if ctx and ctx not in contexts:
                contexts.append(ctx)
            continue
        if line.startswith("+") or line.startswith("-"):
            if line.startswith("+"):
                added += 1
            else:
                removed += 1
            if not is_trivial_line(line[1:]):
                all_trivial = False
    return {"lines_added": added, "lines_removed": removed,
            "comment_only": all_trivial and (added + removed) > 0, "hunk_contexts": contexts}


def verdict(subject, author, main_files, diff_info, max_main_files):
    """First failing filter, or 'checked'."""
    if BOT_AUTHOR_RE.search(author) or BOT_SUBJECT_RE.search(subject):
        return "bot"
    if subject.upper().startswith("DOC"):
        return "doc_title"
    if not main_files:
        return "no_main_source"
    if len(main_files) > max_main_files:
        return "too_many_main_files"
    if diff_info["comment_only"]:
        return "comment_only"
    return "checked"


# ---------- git side ----------

def pr_commits(repo, head="HEAD"):
    """Yield one dict per PR-bearing commit on head's first-parent history, newest first."""
    fmt = FIELD.join(["%H", "%P", "%an", "%ae", "%aI", "%s", "%b"]) + RECORD
    out = git(repo, "log", "--first-parent", f"--format={fmt}", head)
    for rank, rec in enumerate(r for r in out.split(RECORD) if r.strip()):
        sha, parents, an, ae, date, subject, body = rec.lstrip("\n").split(FIELD)
        n = pr_number(subject)
        if n is None or not parents:
            continue
        parents = parents.split()
        yield {"pr": n, "sha_new": sha, "sha_old": parents[0],
               "merge_kind": "merge" if len(parents) > 1 else "squash",
               "author": f"{an} <{ae}>", "date": date, "subject": subject,
               "message": body.strip(), "history_rank": rank}


def cpp_attributes(t):
    """A git attributes file that turns on git's built-in C++ hunk-header rules, so each
    hunk's context names the enclosing function more often. Lives in cache/ (git-ignored)."""
    path = t.cache / "gitattributes-cpp"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, "".join(f"*{e} diff=cpp\n" for e in sorted(CPP_EXT)))
    return path


def changed_files(repo, old, new):
    """[{'status','path'}] for old..new, renames detected."""
    files = []
    for line in git(repo, "diff", "--name-status", "-M", old, new).splitlines():
        parts = line.split("\t")
        files.append({"status": parts[0], "path": parts[-1]})
    return files


def is_generated_text(text, marker_re, lines=GENERATED_MARKER_LINES):
    """True when the file's first `lines` lines carry a "this file is generated" marker."""
    return bool(marker_re.search("\n".join(text.splitlines()[:lines])))


def generated_by_marker(t, c, paths):
    """The `paths` whose content (at the new commit, or the old one for a deleted file) starts with the target's
    `generated_marker`. Generated registries (duckdb's enum_util.cpp is rewritten by ~60% of PRs) are not what a PR
    changes by hand and would push most PRs over max_main_files."""
    pattern = t.get("generated_marker")
    if not pattern or not paths:
        return set()
    rx = re.compile(pattern, re.I)
    out = set()
    for f in paths:
        sha = c["sha_old"] if f["status"][0] == "D" else c["sha_new"]
        text = git(t.repo, "show", f"{sha}:{f['path']}", check=False)
        if is_generated_text(text, rx, t.get("generated_marker_lines", GENERATED_MARKER_LINES)):
            out.add(f["path"])
    return out


def analyze(t, c):
    """Fill in files, main files, diff stats and the verdict for one PR commit."""
    files = changed_files(t.repo, c["sha_old"], c["sha_new"])
    cand = [f for f in files if is_main_source(f["path"], t["main_source"], t.get("generated_paths", []))]
    generated = generated_by_marker(t, c, cand)
    main = [f["path"] for f in cand if f["status"][0] != "D" and f["path"] not in generated]
    deleted_main = [f["path"] for f in cand if f["status"][0] == "D" and f["path"] not in generated]
    paths = main + deleted_main
    diff = git(t.repo, "-c", f"core.attributesFile={cpp_attributes(t).as_posix()}", "diff", "-U0", "-M",
               c["sha_old"], c["sha_new"], "--", *paths) if paths else ""
    info = parse_diff(diff)
    c.update(files=files, main_files=main, deleted_main_files=deleted_main, n_files=len(files),
             n_main=len(main), **info)
    if generated:
        c["generated_files"] = sorted(generated)
    c["verdict"] = verdict(c["subject"], c["author"], main + deleted_main, info, t["max_main_files"])
    return c


def collect(t, checked_target):
    seeds = set(t.get("seed_prs", []))
    scanned, by_pr = [], {}
    n_checked = 0
    commits = list(pr_commits(t.repo, t.get("collect_head", "HEAD")))
    for c in commits:
        by_pr.setdefault(c["pr"], c)
    for c in commits:
        if n_checked >= checked_target:
            break
        analyze(t, c)
        scanned.append(c)
        n_checked += c["verdict"] == "checked"
    seen = {c["pr"] for c in scanned}
    missing_seeds = []
    for n in sorted(seeds):
        if n in seen:
            continue
        if n in by_pr:
            scanned.append(analyze(t, by_pr[n]))     # outside the sampling window; kept, marked seeded
        else:
            missing_seeds.append(n)
    for c in scanned:
        c["seeded"] = c["pr"] in seeds
        c["in_sample"] = c["pr"] in seen
    return scanned, missing_seeds


def summarize(t, scanned, missing_seeds):
    sample = [c for c in scanned if c["in_sample"]]
    counts = Counter(c["verdict"] for c in sample)
    prs = [c["pr"] for c in sample]
    return {
        "target": t.name,
        "head_sha": scanned[0]["sha_new"] if scanned else None,
        "prs_scanned": len(sample),
        "pr_range": [min(prs), max(prs)] if prs else None,
        "date_range": [sample[-1]["date"], sample[0]["date"]] if sample else None,
        "verdicts": dict(sorted(counts.items())),
        "checked": counts["checked"],
        "seeded": sorted(c["pr"] for c in scanned if c["seeded"]),
        "seeded_verdicts": {c["pr"]: c["verdict"] for c in scanned if c["seeded"]},
        "missing_seeds": missing_seeds,
        "merge_kinds": dict(Counter(c["merge_kind"] for c in sample)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target")
    ap.add_argument("--checked", type=int, help="stop after this many PRs pass the filters "
                    "(default: sample_checked from target.toml)")
    ap.add_argument("--github", action="store_true", help="also fetch PR metadata from GitHub")
    ap.add_argument("--refresh-github", action="store_true", help="refetch metadata already on disk")
    a = ap.parse_args(argv)

    t = Target(a.target)
    if not (t.repo / ".git").exists():
        sys.exit(f"{t.repo} missing: run scripts/fetch.sh {t.name} first")

    scanned, missing = collect(t, a.checked or t["sample_checked"])
    selected = [c for c in scanned if c["verdict"] == "checked" or c["seeded"]]
    summary = summarize(t, scanned, missing)

    if a.github:
        from pipeline import github
        meta = github.fetch_all(t, [c["pr"] for c in selected], refresh=a.refresh_github)
        mismatched = []
        for c in selected:
            m = meta.get(c["pr"])
            c["github_metadata"] = m is not None
            if m is not None:
                c["title"] = m["title"]
                c["sha_matches_github"] = m["merge_commit_sha"] == c["sha_new"]
                if not c["sha_matches_github"]:
                    mismatched.append(c["pr"])
        summary["github_metadata_fetched"] = sum(c["github_metadata"] for c in selected)
        summary["github_merge_sha_mismatches"] = mismatched

    write_jsonl(t.data / "prs_scanned.jsonl", scanned)
    write_jsonl(t.data / "prs.jsonl", selected)
    write_text(t.data / "collect_summary.json", json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {len(selected)} PRs to {t.data / 'prs.jsonl'}")
    if missing:
        print(f"WARNING: seed PRs not found in history: {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
