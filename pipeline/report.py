#!/usr/bin/env python3
"""Report (pipeline stage "Report"): Testora-style tables from what the earlier stages left on disk. No LLM calls.

Usage:  python3 pipeline/report.py <target> [--prs 4958 5459] [--out-dir results/<target>]

Reads, per PR in data/<t>/tests/<pr>/: generated.json, results.json, and when present classification.json and
coverage.json. Optional data/<t>/seeded.json lists PRs with a known answer (used ONLY here, never in any prompt):
    {"seeded": [{"pr": 4958, "expected": "unintended", "note": "later regression reported in #5689"},
                {"pr": 5459, "expected": "intended",   "note": "intended change"}]}
If data/<t>/labels/eval.json exists (labels.py eval), a "Classifier vs hand labels" section is added.
Writes results/<t>/report.md (tables + one finding per regression candidate) and results/<t>/report.json.

Definitions (so the numbers can be defended):
  generated programs   every generated.json entry that is not a repair (round 0 plus coverage-refine rounds)
  compile success      the program compiles on the new version / on both versions. "Raw" counts the programs as first
                       generated; "after fix" counts the program in use (the repair when fix.py made one). A failure on
                       one side only is a legitimate API difference, so both numbers are shown.
  in use               entries that are not superseded by a repair
  deterministic        in use, compiles on both versions, and is neither flaky nor a runtime timeout on both
  behavioral difference an in-use program with status output_diff or compile_diff
  regression candidate classify.py judged at least one cluster unintended
  inconclusive         no regression flagged, but changed-line coverage is missing or below 80%: the programs may never
                       have reached the change (a clean result is only trusted when they did)
  LLM calls            estimated from the files: 1 generation + one per refine round + one per fix round + 1 classification
  wall time            run.py's wall time for its last run (fix.py's re-runs are not added)
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from pipeline.common import Target, write_text  # noqa: E402


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


COVERAGE_OK = 0.8  # below this, "no difference found" does not mean "no regression": the programs did not reach the change


def verdict_text(p):
    """One cell for the per-PR table. A clean result is only called clean when the programs reached the changed lines."""
    cls, cov = p["classification"], p["coverage"]
    if not cls:
        return "not classified"
    if cls["regression_candidate"]:
        return "REGRESSION CANDIDATE"
    if cov is None:
        return "no regression flagged, INCONCLUSIVE: coverage not measured"
    if cov["last"] is None:
        return "no regression flagged (no measurable changed lines)"
    if cov["last"] < COVERAGE_OK:
        return f"no regression flagged, INCONCLUSIVE: only {100 * cov['last']:.0f}% of changed lines reached"
    return "no regression flagged"


def pct(num, den):
    return None if not den else round(100.0 * num / den, 1)


def fmt_pct(v):
    return "n/a" if v is None else f"{v:.1f}%"


def outcome(side):
    """One line for what a program did on one version."""
    if not side["compile_ok"]:
        errs = [l for l in side["compile_stderr"].splitlines() if "error" in l.lower()]
        return "compile error: " + (errs[0].split("error:", 1)[-1].strip()[:140] if errs else "?")
    out = (side["runs"][0].get("stdout") or "").strip().replace("\n", " | ")
    return f"output: {out[:140]}" if out else f"exit {side['runs'][0]['exit']}, no output"


def collect_pr(tests_dir):
    """Everything the report needs about one PR, or None if the PR has not been through generate + run."""
    tests_dir = Path(tests_dir)
    manifest, res_doc = load(tests_dir / "generated.json"), load(tests_dir / "results.json")
    if not manifest or not res_doc:
        return None
    results, entries = res_doc["tests"], [e for e in manifest["tests"] if e["file"] in res_doc["tests"]]
    original = [e for e in entries if not e.get("fixes")]
    live = [e for e in entries if not e.get("superseded_by")]

    def compiled(es, both):
        return sum(1 for e in es if results[e["file"]]["new"]["compile_ok"] and
                   (not both or results[e["file"]]["old"]["compile_ok"]))

    status = {}
    for e in live:
        status[results[e["file"]]["status"]] = status.get(results[e["file"]]["status"], 0) + 1
    both_ok = [e for e in live if results[e["file"]]["new"]["compile_ok"] and results[e["file"]]["old"]["compile_ok"]]
    det = [e for e in both_ok if results[e["file"]]["status"] in ("same", "output_diff")]
    cls, cov = load(tests_dir / "classification.json"), load(tests_dir / "coverage.json")
    fix_rounds = {e["round"] for e in entries if e.get("fixes")}
    refine_rounds = {e["round"] for e in entries if not e.get("fixes") and e.get("round", 0) >= 1}
    rec = {"pr": res_doc.get("pr") or manifest.get("pr"), "model": manifest.get("model"),
           "generated": len(original), "raw_compile_new": compiled(original, False), "raw_compile_both": compiled(original, True),
           "in_use": len(live), "final_compile_new": compiled(live, False), "final_compile_both": compiled(live, True),
           "deterministic": len(det), "compiled_both_in_use": len(both_ok), "status": status,
           "differing": status.get("output_diff", 0) + status.get("compile_diff", 0),
           "repairs": sum(1 for e in entries if e.get("fixes")),
           "llm_calls_est": 1 + len(fix_rounds) + len(refine_rounds) + (1 if cls and cls.get("model") else 0),
           "wall_seconds": res_doc.get("wall_seconds"), "std": res_doc.get("std", "c++17"),
           "classification": None, "coverage": None}
    if cls:
        rec["classification"] = {"clusters": [{k: c[k] for k in ("id", "status", "failed_on", "programs", "verdict", "confidence", "reason")}
                                              for c in cls["clusters"]],
                                 "regression_candidate": cls["pr_verdict"]["regression_candidate"],
                                 "unintended_clusters": cls["pr_verdict"]["unintended_clusters"]}
        for c in rec["classification"]["clusters"]:
            r0 = results.get(c["programs"][0])
            if r0:
                c["old"], c["new"] = outcome(r0["old"]), outcome(r0["new"])
    if cov and cov.get("history"):
        h = cov["history"]
        rec["coverage"] = {"first": h[0].get("exec_coverage"), "last": h[-1].get("exec_coverage"), "rounds": len(h),
                           "changed": cov["summary"]["changed"], "measurable": cov["summary"]["covered"] + cov["summary"]["uncovered"]}
    return rec


def summarize(prs, seeded):
    sum_ = lambda k: sum(p[k] for p in prs)  # noqa: E731
    classified = [p for p in prs if p["classification"]]
    verdict_clusters, verdict_programs = {}, {}
    for p in classified:
        for c in p["classification"]["clusters"]:
            verdict_clusters[c["verdict"]] = verdict_clusters.get(c["verdict"], 0) + 1
            verdict_programs[c["verdict"]] = verdict_programs.get(c["verdict"], 0) + len(c["programs"])
    cov = [p["coverage"] for p in prs if p["coverage"] and p["coverage"]["first"] is not None]
    inconclusive = [p["pr"] for p in classified if not p["classification"]["regression_candidate"]
                    and verdict_text(p).startswith("no regression flagged, INCONCLUSIVE")]
    by_pr = {p["pr"]: p for p in prs}
    seed_rows = []
    for s in seeded:
        p = by_pr.get(s["pr"])
        flagged = None if not p or not p["classification"] else p["classification"]["regression_candidate"]
        seed_rows.append({**s, "checked": p is not None and flagged is not None, "flagged": flagged,
                          "correct": None if flagged is None else (flagged == (s["expected"] == "unintended"))})
    seeded_bad = [r for r in seed_rows if r["expected"] == "unintended" and r["checked"]]
    return {
        "prs_checked": len(prs),
        "generated": sum_("generated"),
        "compile_success": {
            "raw_new": pct(sum_("raw_compile_new"), sum_("generated")), "raw_both": pct(sum_("raw_compile_both"), sum_("generated")),
            "final_new": pct(sum_("final_compile_new"), sum_("in_use")), "final_both": pct(sum_("final_compile_both"), sum_("in_use"))},
        "in_use": sum_("in_use"), "repairs": sum_("repairs"),
        "deterministic": {"programs": sum_("deterministic"), "of_compiled_both": sum_("compiled_both_in_use"),
                          "pct": pct(sum_("deterministic"), sum_("compiled_both_in_use"))},
        "prs_with_difference": {"count": sum(1 for p in prs if p["differing"]), "pct": pct(sum(1 for p in prs if p["differing"]), len(prs))},
        "verdicts": {"clusters": verdict_clusters, "programs": verdict_programs, "prs_classified": len(classified)},
        "regression_candidates": [p["pr"] for p in classified if p["classification"]["regression_candidate"]],
        "coverage_measured": {"prs": sum(1 for p in prs if p["coverage"]), "of": len(prs),
                              "at_least_80": sum(1 for p in prs if p["coverage"] and p["coverage"]["last"] is not None
                                                 and p["coverage"]["last"] >= COVERAGE_OK)},
        "inconclusive_prs": inconclusive,
        "coverage": None if not cov else {"prs": len(cov), "first_mean": round(100 * sum(c["first"] for c in cov) / len(cov), 1),
                                          "last_mean": round(100 * sum(c["last"] for c in cov) / len(cov), 1)},
        "llm_calls": {"total_est": sum_("llm_calls_est"), "per_pr_mean": round(sum_("llm_calls_est") / len(prs), 1) if prs else None},
        "wall_seconds_total": round(sum(p["wall_seconds"] or 0 for p in prs), 1),
        "std": {k: sum(1 for p in prs if p.get("std", "c++17") == k) for k in sorted({p.get("std", "c++17") for p in prs})},
        "seeded": {"rows": seed_rows, "recall": None if not seeded_bad else
                   f"{sum(1 for r in seeded_bad if r['flagged'])}/{len(seeded_bad)}"},
    }


def labels_section(ev):
    """Markdown lines for data/<t>/labels/eval.json (written by labels.py eval); empty when there is none."""
    if not ev:
        return []
    f = lambda v: "n/a" if v is None else f"{v:.2f}"
    raw, wt, pr = ev["unintended_raw"], ev["unintended_weighted"], ev["pr_level"]
    return ["## Classifier vs hand labels", "",
            f"{ev['items_scored']} clusters scored against reconciled hand labels ({len(ev['stale_labels_skipped'])} stale labels skipped). "
            "Intended clusters were subsampled, so weighted figures correct for that; raw accuracy is biased.", "",
            "| Measure | Value |", "|---|---|",
            f"| Precision of \"unintended\" (raw / weighted) | {f(raw['precision'])} / {f(wt['precision'])} |",
            f"| Recall of \"unintended\" (raw / weighted) | {f(raw['recall'])} / {f(wt['recall'])} |",
            f"| Accuracy (raw) | {f(ev['accuracy_raw'])} |",
            f"| PR level: true regressions caught / flagged PRs / fully labeled PRs | {pr['caught']}/{pr['true_regressions']} / {pr['flagged']} / {pr['prs']} |",
            f"| Inter-labeler Cohen's kappa ({ev['labeler_pairs']} items) | {f(ev['labeler_kappa'])} |", ""]


def render(target, prs, s, ev=None):
    L = [f"# Report: {target}", "",
         f"{s['prs_checked']} PR(s) checked, {s['generated']} programs generated, {s['in_use']} in use "
         f"({s['repairs']} repaired by fix.py). Numbers come only from the files on disk; see the module docstring of "
         f"pipeline/report.py for each definition.", "", "## Summary", "", "| Measure | Value |", "|---|---|",
         f"| PRs checked | {s['prs_checked']} |",
         f"| Compile success, as generated (new / both versions) | {fmt_pct(s['compile_success']['raw_new'])} / {fmt_pct(s['compile_success']['raw_both'])} |",
         f"| Compile success, after fix.py (new / both versions) | {fmt_pct(s['compile_success']['final_new'])} / {fmt_pct(s['compile_success']['final_both'])} |",
         f"| Deterministic on both versions | {s['deterministic']['programs']} of {s['deterministic']['of_compiled_both']} compiled-on-both programs ({fmt_pct(s['deterministic']['pct'])}) |",
         f"| PRs with at least one behavioral difference | {s['prs_with_difference']['count']} of {s['prs_checked']} ({fmt_pct(s['prs_with_difference']['pct'])}) |"]
    v = s["verdicts"]
    if v["prs_classified"]:
        L.append("| Differences by verdict (clusters / programs) | " + ", ".join(
            f"{k} {v['clusters'].get(k, 0)} / {v['programs'].get(k, 0)}" for k in ("intended", "unintended", "unclear")) + " |")
        L.append(f"| Regression candidates | {len(s['regression_candidates'])} of {v['prs_classified']} classified: "
                 f"{', '.join('#' + str(p) for p in s['regression_candidates']) or 'none'} |")
    cm = s["coverage_measured"]
    L.append(f"| Changed-line coverage measured | {cm['prs']} of {cm['of']} PRs; at least {int(100 * COVERAGE_OK)}% reached for {cm['at_least_80']} |")
    if s["inconclusive_prs"]:
        L.append(f"| Clean results that are INCONCLUSIVE (coverage missing or low) | {len(s['inconclusive_prs'])}: "
                 f"{', '.join('#' + str(p) for p in s['inconclusive_prs'])} |")
    if s["coverage"]:
        L.append(f"| Changed-line coverage before / after the loop (mean over {s['coverage']['prs']} PRs) | "
                 f"{s['coverage']['first_mean']}% / {s['coverage']['last_mean']}% |")
    if len(s.get("std", {})) > 1:
        L.append("| C++ standard the programs were compiled with | "
                 + ", ".join(f"{k}: {n} PR(s)" for k, n in s["std"].items()) + " |")
    L += [f"| LLM calls (estimated) | {s['llm_calls']['total_est']} total, {s['llm_calls']['per_pr_mean']} per PR |",
          f"| Wall time of the run.py stage | {s['wall_seconds_total']} s |", ""]
    by_pr_cov = {p["pr"]: p["coverage"] for p in prs}
    if s["seeded"]["rows"]:
        L += ["## Seeded PRs with a known answer", "", "A small set; recall here is not a general estimate.", "",
              "| PR | Expected | Pipeline | Match | Note |", "|---|---|---|---|---|"]
        for r in s["seeded"]["rows"]:
            pipe = "not checked" if not r["checked"] else ("unintended found" if r["flagged"] else "no regression flagged")
            if r["checked"] and not r["flagged"] and by_pr_cov.get(r["pr"]) is None:
                pipe += " (coverage not measured)"
            L.append(f"| #{r['pr']} | {r['expected']} | {pipe} | {'yes' if r['correct'] else ('no' if r['correct'] is False else 'n/a')} | {r.get('note', '')} |")
        L += ["", f"Recall on seeded regressions: {s['seeded']['recall'] or 'n/a'}", ""]
    L += labels_section(ev)
    L += ["## Per PR", "", "| PR | Programs (in use) | Compile new / both | Status counts | Differing | Verdict | Coverage | Calls |",
          "|---|---|---|---|---|---|---|---|"]
    for p in sorted(prs, key=lambda p: p["pr"]):
        cls = p["classification"]
        verdict = verdict_text(p)
        cov = "n/a" if not p["coverage"] or p["coverage"]["last"] is None else f"{100 * p['coverage']['last']:.0f}% of {p['coverage']['measurable']} lines"
        counts = ", ".join(f"{k} {n}" for k, n in sorted(p["status"].items()))
        std = "" if p.get("std", "c++17") == "c++17" else f" ({p['std']})"
        L.append(f"| #{p['pr']}{std} | {p['generated']} ({p['in_use']}) | {p['final_compile_new']}/{p['in_use']} / {p['final_compile_both']}/{p['in_use']} | "
                 f"{counts} | {p['differing']} | {verdict} | {cov} | {p['llm_calls_est']} |")
    for p in sorted(prs, key=lambda p: p["pr"]):
        cls = p["classification"]
        if not cls:
            continue
        L += ["", f"## PR #{p['pr']}: clusters", "", "| Cluster | Programs | Verdict | Reason |", "|---|---|---|---|"]
        for c in cls["clusters"]:
            kind = c["status"] + (f" [{c['failed_on']}]" if c["failed_on"] else "")
            L.append(f"| {c['id']} {kind} | {len(c['programs'])} | {c['verdict']} ({c['confidence']}) | {c['reason']} |")
        for c in cls["clusters"]:
            if c["verdict"] == "unintended":
                L += ["", f"### Finding: PR #{p['pr']} {c['id']} ({c['verdict']}, {c['confidence']})", "", c["reason"], "",
                      f"- Example program: `data/{target}/tests/{p['pr']}/{c['programs'][0]}` ({len(c['programs'])} in cluster)",
                      f"- Old version: {c.get('old', 'n/a')}", f"- New version: {c.get('new', 'n/a')}"]
    return "\n".join(L) + "\n"


def build(target_name, data_dir, out_dir, prs=None):
    data_dir = Path(data_dir)
    names = [str(p) for p in prs] if prs else sorted((d.name for d in (data_dir / "tests").iterdir() if d.is_dir()), key=lambda n: (len(n), n))
    recs = [r for r in (collect_pr(data_dir / "tests" / n) for n in names) if r]
    seeded_doc = load(data_dir / "seeded.json")
    s = summarize(recs, (seeded_doc or {}).get("seeded", []))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_text(out_dir / "report.md", render(target_name, recs, s, load(data_dir / "labels" / "eval.json")))
    write_text(out_dir / "report.json", json.dumps({"target": target_name, "summary": s, "prs": recs}, indent=2) + "\n")
    return recs, s


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target")
    ap.add_argument("--prs", type=int, nargs="+")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    t = Target(a.target)
    out = a.out_dir or ROOT / "results" / a.target
    recs, s = build(a.target, t.data, out, a.prs)
    if not recs:
        sys.exit("report.py: no PR in data/<t>/tests has both generated.json and results.json")
    print(f"{s['prs_checked']} PR(s); regression candidates: {s['regression_candidates'] or 'none'}; "
          f"seeded recall: {s['seeded']['recall'] or 'n/a'}\nwrote {out}/report.md and report.json")


if __name__ == "__main__":
    main()
