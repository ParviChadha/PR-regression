#!/usr/bin/env python3
"""Test generation (pipeline stage "Generate tests"): ask the LLM for standalone C++ programs that probe one PR.

Usage:  python3 pipeline/generate.py <target> --pr N [--n 20] [--model gemini-3.5-flash-lite] [--dry-run]
                                      [--force] [--refine [--docker]] [--refine-only [--docker]] [--refine-n 5]
Needs GEMINI_API_KEY (in .env at the repo root, or exported) (not for --dry-run or when every response is cached).

One request returns --n programs (structured JSON: name, intent, code). They are written to
data/<target>/tests/<pr>/gen_01.cpp, gen_02.cpp, ... with a manifest generated.json and the exact prompt in
generate.prompt.txt; run.py then compiles and runs everything in that folder. Re-running regenerates the same files
from the cache (stale gen_*.cpp from an earlier prompt are removed).

Only information available when the PR merged goes into the prompt: title, description, commit message, linked
issues, comments created before merged_at, and the diff. Later discussion (for example a follow-up PR reporting the
regression) would leak the answer and is dropped.

Inputs:
  data/<t>/prs.jsonl, data/<t>/github/<pr>.json     collect.py
  data/<t>/changes/<pr>.json                        optional, from changes.py: {"functions": [{"name": ..., "access": "public"|"private"}]};
                                                    without it the git hunk headers are used as a rougher hint
  data/<t>/context/<pr>.txt                         optional, from context.py: upstream tests that call the changed functions (plain text)
  targets/<t>/target.toml  prompt_notes             library-specific rules (include line, determinism pitfalls)

--refine runs the coverage loop (coverage_loop.py) after generation: it measures which changed lines the tests
reach and makes ONE more request, with the uncovered lines and surrounding source, for --refine-n extra programs.
--refine-only does that step alone for a PR that already has programs (batch.py's "refine" stage). Why it matters:
generated programs can be well aimed and still never reach the change (for example UBJSON byte strings missing the
opening '[' are rejected identically by both versions), which looks like "no difference" but is really "not tested".
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from pipeline.common import Target, git, read_jsonl, write_text  # noqa: E402
import llm  # noqa: E402

CAP = {"body": 4000, "comment": 1200, "comments": 6, "issue": 2000, "issues": 3, "diff": 24000, "context": 8000}

SYSTEM = """You write test programs that probe a C++ library for behavioral changes made by one pull request.
Each program is compiled and run twice, once against the library before the change and once after, and the two
outputs are compared. Your job is to produce programs whose output reveals whether the change altered behavior,
including side effects the author did not intend.

Rules for every program:
- It is standalone: one file with its own int main(), compiled as C++17, printing results to stdout.
- Use only the library's documented public API. Never include internal headers or use detail/impl namespaces,
  private members or undocumented macros.
- Do not judge results (no assert, no expected-value comparisons): just print what the library returns. Print
  enough to make differences visible, one fact per line.
- Output must be deterministic. Never print pointers or addresses, uninitialized data, the order of
  hash-based containers, timings, thread ids, random values, file paths or environment data. Print floating point
  values with an explicit precision. No input, files, network, threads, clocks or randomness.
- Wrap calls that may throw in try/catch and print the exception's type and message, so an exception is an
  observable result. Do not crash on purpose.
- Aim at the code the diff changes. Prefer calls that compile against both the old and the new library; one or two
  programs may use an API the PR adds. Cover ordinary inputs and edge cases (empty, minimum and maximum values,
  boundaries, special values, nesting, unusual types) and also neighbouring behavior the change could disturb.
- When the diff changes which types or inputs an API accepts or rejects (constraints, overloads, traits,
  conversions), test it with the detection idiom (std::void_t or requires) and `if constexpr`, so the program
  compiles against both versions, prints whether the expression is well-formed, and exercises it when it is.
  Accepting an input is not enough: also use it through every entry point that should follow (const and
  non-const, read, write, insert, erase, lookup, nested use), because a change that admits new inputs can leave
  later code unable to handle them.
- If the changed code is internal (a detail, impl or internal namespace, a trait, a helper), do not name it in the
  program. Reach it through the public API that depends on it, using detection (as above) where needed.
- Use the exact types and values the diff is about (the new trait's argument types, the new overload's
  parameters), not stand-ins.
- Spread the programs over distinct public entry points and overloads, one main idea per program. Do not write
  several programs that only rename a type or change a literal.
- Make the programs differ from each other: different inputs, different entry points, different features."""

SCHEMA = {"type": "OBJECT", "properties": {"tests": {"type": "ARRAY", "items": {
    "type": "OBJECT",
    "properties": {"name": {"type": "STRING"}, "intent": {"type": "STRING"}, "code": {"type": "STRING"}},
    "required": ["name", "intent", "code"]}}}, "required": ["tests"]}


def die(msg):
    sys.exit(f"generate.py: {msg}")


def clip(text, n):
    text = (text or "").replace("\r\n", "\n").strip()
    return text if len(text) <= n else text[:n] + f"\n[... truncated, {len(text) - n} more characters]"


# ---------------------------------------------------------------- inputs
def load_pr(t, pr):
    rec = next((r for r in read_jsonl(t.data / "prs.jsonl") if r["pr"] == pr), None)
    if rec is None:
        die(f"PR #{pr} is not in {t.data / 'prs.jsonl'}")
    gh_path = t.data / "github" / f"{pr}.json"
    gh = json.loads(gh_path.read_text(encoding="utf-8")) if gh_path.is_file() else None
    return rec, gh


def merge_time_comments(gh):
    """-> (kept comments, number dropped for being created after the merge)."""
    if not gh:
        return [], 0
    merged = gh.get("merged_at") or "9999"
    allc = (gh.get("comments") or []) + (gh.get("review_comments") or [])
    kept = [c for c in allc if (c.get("created_at") or "") <= merged]
    return kept, len(allc) - len(kept)


def source_diff(t, rec):
    files, per_file = rec["main_files"], max(CAP["diff"] // max(len(rec["main_files"]), 1), 2000)
    parts = []
    for f in files:
        d = git(t.repo, "diff", "-U3", "--no-color", rec["sha_old"], rec["sha_new"], "--", f)
        parts.append(clip(d, per_file))
    return "\n".join(parts)


def changed_functions(t, rec):
    p = t.data / "changes" / f"{rec['pr']}.json"
    if p.is_file():
        funcs = json.loads(p.read_text(encoding="utf-8")).get("functions", [])
        return [f"{f['name']}" + (f" ({f['access']})" if f.get("access") else "") for f in funcs], "changes.py"
    seen = []
    for c in rec.get("hunk_contexts", []):
        if c and c not in seen:
            seen.append(c)
    return seen, "git hunk headers (rough hint)"


def pr_section(t, rec, gh):
    kept, dropped = merge_time_comments(gh)
    funcs, src = changed_functions(t, rec)
    out = [f"# Pull request #{rec['pr']}: {(gh or {}).get('title') or rec.get('title') or rec['subject']}"]
    if gh and gh.get("body"):
        out += ["", "## Description", clip(gh["body"], CAP["body"])]
    out += ["", "## Commit message", clip(rec.get("message", ""), 2000)]
    for issue in (gh or {}).get("linked_issues", [])[:CAP["issues"]]:
        out += ["", f"## Linked issue #{issue['number']}: {issue.get('title', '')}", clip(issue.get("body", ""), CAP["issue"])]
    if kept:
        out += ["", "## Discussion before merge"]
        out += [f"- {c.get('user', {}).get('login', '?')}: {clip(c.get('body', ''), CAP['comment'])}" for c in kept[:CAP["comments"]]]
    out += ["", f"## Changed functions (from {src})"] + [f"- {f}" for f in funcs] if funcs else []
    out += ["", "## Diff of the library source (before -> after)", "```diff", source_diff(t, rec), "```"]
    ctx = t.data / "context" / f"{rec['pr']}.txt"
    if ctx.is_file():
        out += ["", "## Existing upstream tests that call the changed code (for style and API usage)",
                clip(ctx.read_text(encoding="utf-8"), CAP["context"])]
    return "\n".join(out), {"comments_kept": len(kept), "comments_dropped_after_merge": dropped}


def system_prompt(t):
    notes = (t.get("prompt_notes", "") or "").strip()
    return SYSTEM + (f"\n\nRules specific to this library:\n{notes}" if notes else "")


def build_generate_prompt(t, rec, gh, n):
    section, stats = pr_section(t, rec, gh)
    return system_prompt(t), (
        f"{section}\n\n# Task\nWrite {n} test programs for this pull request. Return JSON with a \"tests\" array; each "
        f"item has \"name\" (short snake_case), \"intent\" (one sentence: what behavior it probes) and \"code\" "
        f"(the complete C++ program)."), stats


def build_refine_prompt(t, rec, gh, existing, context, k):
    section, _ = pr_section(t, rec, gh)
    have = "\n".join(f"- {e['file']}: {e['intent']}" for e in existing)
    return system_prompt(t), (
        f"{section}\n\n# Programs written so far\n{have}\n\n# Changed lines that no program reached\n"
        f"Lines marked >> are changed by the PR and were never executed by the programs above (\"NOT RUN\"), or have no "
        f"generated code at all (\"NO CODE / NOT INSTANTIATED\": for example a template that no program instantiated, or a "
        f"macro body). For each marked line work out what input or call reaches it. Some earlier programs may have used "
        f"malformed input (a binary or text format with a missing marker, wrong length or wrong order) and been rejected "
        f"before they reached the changed code; when you build such input, check every byte or token against the "
        f"format's specification and make sure the program prints what happened.\n\n```\n{context}\n```\n\n"
        f"# Task\nWrite {k} NEW programs, different from those already written, that execute the marked lines. Return JSON "
        f"with a \"tests\" array; each item has \"name\", \"intent\" and \"code\".")


# ---------------------------------------------------------------- output
def unflatten(code):
    """Models occasionally double-escape: the whole program arrives on ONE line with a literal backslash-n between
    lines (seen from Flash-Lite in fix.py). If there is no real newline but literal `\\n` sequences, turn the ones
    outside string and char literals back into newlines (and `\\t` into tabs); escapes inside literals stay as C++."""
    if "\n" in code.strip() or "\\n" not in code:
        return code
    out, i, quote = [], 0, None
    while i < len(code):
        c = code[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < len(code):
                out.append(code[i + 1])
                i += 1
            elif c == quote:
                quote = None
        elif c == '"' or (c == "'" and (code[i + 2:i + 3] == "'" or (code[i + 1:i + 2] == "\\" and code[i + 3:i + 4] == "'"))):
            quote = c  # an apostrophe in a comment ("don't") is not a char literal
            out.append(c)
        elif c == "\\" and code[i + 1:i + 2] == "n":
            out.append("\n")
            i += 1
        elif c == "\\" and code[i + 1:i + 2] == "t":
            out.append("\t")
            i += 1
        else:
            out.append(c)
        i += 1
    return "".join(out)


def parse_tests(text):
    """-> (programs, number of items dropped as unusable)."""
    try:
        items = json.loads(text)["tests"]
    except (ValueError, KeyError, TypeError):
        die(f"model did not return the expected JSON: {text[:300]!r}")
    progs, dropped, seen = [], 0, set()
    for it in items:
        code = unflatten(re.sub(r"^```[a-z+]*\n|\n```\s*$", "", (it.get("code") or "").strip())).strip() + "\n"
        if not re.search(r"\bint\s+main\s*\(", code) or code in seen:
            dropped += 1
            continue
        seen.add(code)
        progs.append({"name": re.sub(r"\W+", "_", it.get("name", "")).strip("_") or "test",
                      "intent": " ".join((it.get("intent") or "").split()), "code": code})
    return progs, dropped


def write_tests(tests_dir, progs, start, model, pr, round_no):
    entries = []
    for i, p in enumerate(progs, start):
        fname = f"gen_{i:02d}.cpp"
        header = f"// generated by {model} for PR #{pr} (round {round_no}): {p['name']}\n// intent: {p['intent']}\n"
        write_text(tests_dir / fname, header + p["code"])
        entries.append({"file": fname, "name": p["name"], "intent": p["intent"], "round": round_no})
    return entries


def save_manifest(tests_dir, manifest):
    write_text(tests_dir / "generated.json", json.dumps(manifest, indent=2) + "\n")


def remove_stale(tests_dir, keep):
    for f in tests_dir.glob("gen_*.cpp"):
        if f.name not in keep:
            try:
                f.unlink()
            except OSError as e:
                print(f"generate.py: could not remove stale {f.name}: {e}", file=sys.stderr)


# ---------------------------------------------------------------- steps
def generate(t, pr, args, tests_dir=None):
    rec, gh = load_pr(t, pr)
    tests_dir = Path(tests_dir or t.data / "tests" / str(pr))
    tests_dir.mkdir(parents=True, exist_ok=True)
    system, prompt, stats = build_generate_prompt(t, rec, gh, args.n)
    write_text(tests_dir / "generate.prompt.txt", f"[system]\n{system}\n\n[user]\n{prompt}\n")
    print(f"PR #{pr}: prompt {len(system) + len(prompt)} chars (~{(len(system) + len(prompt)) // 4} tokens); "
          f"comments kept {stats['comments_kept']}, dropped as post-merge {stats['comments_dropped_after_merge']}")
    if args.dry_run:
        print(f"dry run: prompt written to {tests_dir / 'generate.prompt.txt'}")
        return None
    r = llm.call(prompt, system=system, schema=SCHEMA, model=args.model, force=args.force)
    progs, dropped = parse_tests(r["text"])
    if not progs:
        die("the model returned no usable program")
    entries = write_tests(tests_dir, progs, 1, r["model"], pr, 0)
    remove_stale(tests_dir, {e["file"] for e in entries})
    manifest = {"target": t.name, "pr": pr, "model": r["model"], "prompt_sha256": hashlib.sha256(
        (system + prompt).encode()).hexdigest(), "n_requested": args.n, "dropped": dropped,
        "usage": r.get("usage"), "tests": entries}
    save_manifest(tests_dir, manifest)
    print(f"wrote {len(entries)} programs to {tests_dir} ({'cache' if r['cached'] else 'API'}; {dropped} unusable dropped; "
          f"{llm.calls_today(r['model'])}/{llm.limits(r['model'])[1]} requests used today)")
    return tests_dir, manifest, (rec, gh)


def make_refine(t, rec, gh, args, tests_dir, manifest):
    """The `refine` callable for coverage_loop.loop: one request for --refine-n programs aimed at uncovered lines."""
    def refine(context, remaining, tests_dir_):
        system, prompt = build_refine_prompt(t, rec, gh, manifest["tests"], context, args.refine_n)
        r = llm.call(prompt, system=system, schema=SCHEMA, model=args.model, force=args.force)
        progs, dropped = parse_tests(r["text"])
        rounds = 1 + max((e["round"] for e in manifest["tests"]), default=0)
        entries = write_tests(Path(tests_dir_), progs, 1 + len(manifest["tests"]), r["model"], rec["pr"], rounds)
        manifest["tests"] += entries
        save_manifest(Path(tests_dir_), manifest)
        print(f"refine round {rounds}: wrote {len(entries)} programs ({'cache' if r['cached'] else 'API'}; {dropped} dropped)")
        return [e["file"] for e in entries]
    return refine


def refine_round(t, args, tests_dir, manifest, rec, gh):
    """Measure changed-line coverage of everything in tests_dir and make ONE refine request aimed at the uncovered lines."""
    from env import prepare
    import coverage_loop
    env = prepare(t.name, args.pr, docker=args.docker)
    rep = coverage_loop.loop(env, tests_dir, args, refine=make_refine(t, rec, gh, args, tests_dir, manifest), rounds=1)
    write_text(tests_dir / "coverage.json", json.dumps(rep, indent=2) + "\n")
    for h in rep["history"]:
        print(f"coverage round {h['round']}: tests={h['tests']} covered={h['covered']} uncovered={h['uncovered']} "
              f"macro={h['macro']} no_code={h['no_code']} exec_coverage={h['exec_coverage']}")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--n", type=int, default=20, help="programs requested in the generation call")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL)
    ap.add_argument("--dry-run", action="store_true", help="build and save the prompt, make no request")
    ap.add_argument("--force", action="store_true", help="ignore the response cache (costs a request)")
    ap.add_argument("--refine", action="store_true", help="then run one coverage-guided refine round")
    ap.add_argument("--refine-only", action="store_true",
                    help="skip generation: run the coverage loop and one refine round on the programs already in the folder")
    ap.add_argument("--refine-n", type=int, default=5)
    ap.add_argument("--docker", action="store_true", help="with --refine/--refine-only: build/measure in the container")
    ap.add_argument("--std", default="c++17")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--compile-timeout", type=float, default=180)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    t = Target(args.target)
    try:
        if args.refine_only:
            tests_dir = t.data / "tests" / str(args.pr)
            if not (tests_dir / "generated.json").is_file():
                die(f"{tests_dir / 'generated.json'} is missing; generate first")
            manifest = json.loads((tests_dir / "generated.json").read_text())
            rec, gh = load_pr(t, args.pr)
            refine_round(t, args, tests_dir, manifest, rec, gh)
            return
        res = generate(t, args.pr, args)
        if res and args.refine:
            tests_dir, manifest, (rec, gh) = res
            refine_round(t, args, tests_dir, manifest, rec, gh)
    except llm.QuotaExhausted as e:
        print(f"generate.py: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
