#!/usr/bin/env python3
"""Hand labels (pipeline stage "Labels"): two people label differences independently, reconcile, and score the classifier.

Workflow (each step is a subcommand):
  export <target> [--labelers dennis parvi] [--intended-sample 20] [--seed 1] [--out-dir DIR]
      Picks the clusters to label from data/<t>/tests/*/classification.json: ALL clusters the classifier called unintended or
      unclear, plus a seeded random sample of the intended ones (--intended-sample, spread over all of them). Writes
      data/<t>/labels/items.json (machine copy, with the sampling fractions), items.md (the evidence, WITHOUT the classifier's
      verdict or reason, in a shuffled order) and one blank labels_<name>.csv per labeler. Refuses to overwrite a CSV that
      already holds labels.
  check <target>
      Progress per labeler and invalid entries.
  reconcile <target>
      Merges the labelers' CSVs into reconciled.csv: agreement, Cohen's kappa, and the disagreements to discuss. Fill the
      `final` column for disagreements (agreeing rows are prefilled). Re-running keeps every `final` and `note` you typed.
  eval <target>
      Scores the classifier against `final`: confusion matrix, accuracy, precision and recall of "unintended", the PR-level
      regression call, and the labelers' kappa. Writes data/<t>/labels/eval.json (report.py shows it).

How to label (both of you, independently, using only what the PR said at merge time, the same standard the classifier gets):
  intended    the PR's title, description, linked issue or diff states or clearly implies this change.
  unintended  it contradicts the PR's goal, breaks something that worked or was documented before, or is a side effect the PR
              never mentions (including a feature the PR claims but only partly delivers).
  unclear     you cannot tell, or the test program itself looks unreliable (undefined behavior, environment dependence).
Do not use later knowledge (for example a follow-up PR reporting the regression). Do not read the other person's CSV, or
results/*/report.md and classification.json, until you have finished. Write a short `note` for anything you were unsure about.

Items are keyed "<pr>-<cluster id>" and carry a fingerprint of the cluster's programs; if the pipeline is rerun and the clusters
change, eval skips (and counts) labels whose fingerprint no longer matches instead of scoring them against the wrong thing.
Sampling caveat: intended clusters are subsampled, so raw accuracy is biased; eval also reports weighted precision and recall
(each item weighted by available/exported clusters of its classifier verdict).
"""
import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from pipeline.common import Target, write_text  # noqa: E402
import classify  # noqa: E402
import fix  # noqa: E402
import generate  # noqa: E402
import report  # noqa: E402

LABELS = ("intended", "unintended", "unclear")
FIELDS = ["key", "pr", "cluster", "fingerprint", "label", "note"]


def die(msg):
    sys.exit(f"labels.py: {msg}")


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fingerprint(c):
    return hashlib.sha1(f"{c['status']}|{c['failed_on']}|{','.join(sorted(c['programs']))}".encode()).hexdigest()[:10]


def all_clusters(data_dir):
    """-> [{"pr", "id", "key", "fingerprint", ...cluster fields incl. classifier verdict}] from every classification.json."""
    out = []
    tests = Path(data_dir) / "tests"
    for d in sorted((p for p in tests.iterdir() if p.is_dir()), key=lambda p: (len(p.name), p.name)) if tests.is_dir() else []:
        doc = load(d / "classification.json")
        if not doc:
            continue
        for c in doc["clusters"]:
            out.append({**c, "pr": int(d.name), "key": f"{d.name}-{c['id']}", "fingerprint": fingerprint(c), "dir": d})
    return out


# ---------------------------------------------------------------- sampling and evidence
def pick(clusters, intended_sample, seed):
    """-> (chosen clusters, strata {classifier verdict: {"available", "exported"}}). All non-intended, a seeded sample of intended."""
    rng = random.Random(seed)
    intended = sorted((c for c in clusters if c["verdict"] == "intended"), key=lambda c: c["key"])
    rest = [c for c in clusters if c["verdict"] != "intended"]
    sampled = intended if len(intended) <= intended_sample else rng.sample(intended, intended_sample)
    chosen = rest + sampled
    strata = {}
    for v in LABELS:
        avail = sum(1 for c in clusters if c["verdict"] == v)
        strata[v] = {"available": avail, "exported": sum(1 for c in chosen if c["verdict"] == v)}
    rng.shuffle(chosen)  # presentation order carries no information about the classifier's verdict
    return chosen, strata


def evidence(t, c):
    """Markdown block for one cluster: PR link, what differs, old/new behavior, a representative program. No verdict."""
    d, pr = Path(c["dir"]), c["pr"]
    rec, gh = generate.load_pr(t, pr)
    results = load(d / "results.json")["tests"]
    repo = t.get("github_repo")
    title = (gh or {}).get("title") or rec.get("title") or rec.get("subject", "")
    kind = c["status"] + (f" (fails to compile on {c['failed_on']})" if c["failed_on"] else "")
    prog = c["programs"][0]
    r0 = results[prog]
    lines = [f"## {c['key']}: PR #{pr}, {title}", ""]
    if repo:
        lines += [f"- PR: https://github.com/{repo}/pull/{pr}"]
    lines += [f"- Changed library files: {', '.join(rec.get('main_files', []))}",
              f"- Cluster: {kind}, {len(c['programs'])} program(s): {', '.join(c['programs'][:6])}"]
    if c["status"] == "output_diff":
        a, b = classify.first_diff(r0["old"], r0["new"])
        lines += [f"- First difference (old -> new): `{a}` -> `{b}`"]
    lines += [f"- Old version: {report.outcome(r0['old'])}", f"- New version: {report.outcome(r0['new'])}", "",
              f"Representative program `{prog}`:", "", "```cpp",
              generate.clip(fix.strip_header((d / prog).read_text(encoding="utf-8")), 2500), "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- csv helpers
def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def norm(label):
    return (label or "").strip().lower()


def kappa(pairs):
    """Cohen's kappa for two labelers over LABELS; None when undefined (no pairs, or chance agreement is 1)."""
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum((sum(1 for a, _ in pairs if a == k) / n) * (sum(1 for _, b in pairs if b == k) / n) for k in LABELS)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


# ---------------------------------------------------------------- commands
def cmd_export(t, a, data_dir=None):
    data_dir = Path(data_dir or t.data)
    out = Path(a.out_dir or data_dir / "labels")
    clusters = all_clusters(data_dir)
    if not clusters:
        die("no classification.json with clusters yet; run batch.py (or classify.py) first")
    existing = [out / f"labels_{n}.csv" for n in a.labelers if (out / f"labels_{n}.csv").is_file()]
    if any(norm(r["label"]) for p in existing for r in read_csv(p)) and not a.force:
        die("a labeler CSV already holds labels; refusing to overwrite (use --force only if you mean it)")
    chosen, strata = pick(clusters, a.intended_sample, a.seed)
    out.mkdir(parents=True, exist_ok=True)
    items = [{"key": c["key"], "pr": c["pr"], "cluster": c["id"], "fingerprint": c["fingerprint"]} for c in chosen]
    write_text(out / "items.json", json.dumps({"target": t.name, "seed": a.seed, "intended_sample": a.intended_sample,
                                               "labelers": a.labelers, "strata": strata, "items": items}, indent=2) + "\n")
    md = [f"# Labeling sheet: {t.name}", "", f"{len(chosen)} clusters to label. Label each as intended, unintended or unclear "
          f"in your own `labels_<name>.csv` (columns key, label, note). See the top of pipeline/labels.py for the rules. "
          f"Use only what the PR said at merge time. Do not look at the other labeler's file or at classification.json.", ""]
    md += [evidence(t, c) for c in chosen]
    write_text(out / "items.md", "\n".join(md) + "\n")
    for n in a.labelers:
        write_csv(out / f"labels_{n}.csv", FIELDS, [{**i, "label": "", "note": ""} for i in items])
    strata_txt = ", ".join(f"{v}: {s['exported']}/{s['available']}" for v, s in strata.items())
    print(f"{len(chosen)} items ({strata_txt} exported/available)")
    print(f"wrote {out}/items.md, items.json and one labels_<name>.csv per labeler ({', '.join(a.labelers)})")


def cmd_check(t, a, data_dir=None):
    out = Path(data_dir or t.data) / "labels"
    meta = load(out / "items.json") or die("run `export` first")
    keys = {i["key"] for i in meta["items"]}
    for n in meta["labelers"]:
        rows = read_csv(out / f"labels_{n}.csv")
        done = [r for r in rows if norm(r["label"])]
        bad = [r["key"] for r in done if norm(r["label"]) not in LABELS]
        unknown = [r["key"] for r in rows if r["key"] not in keys]
        print(f"{n}: {len(done)}/{len(rows)} labeled" + (f"; INVALID label on {bad}" if bad else "") +
              (f"; unknown keys {unknown}" if unknown else ""))


def cmd_reconcile(t, a, data_dir=None):
    out = Path(data_dir or t.data) / "labels"
    meta = load(out / "items.json") or die("run `export` first")
    by = {n: {r["key"]: r for r in read_csv(out / f"labels_{n}.csv")} for n in meta["labelers"]}
    old = {r["key"]: r for r in read_csv(out / "reconciled.csv")} if (out / "reconciled.csv").is_file() else {}
    rows, pairs, pending = [], [], []
    for it in meta["items"]:
        labs = {n: norm(by[n].get(it["key"], {}).get("label")) for n in meta["labelers"]}
        for n, v in labs.items():
            if v and v not in LABELS:
                die(f"{n} has an invalid label {v!r} for {it['key']} (use {', '.join(LABELS)})")
        full = all(labs.values())
        agree = full and len(set(labs.values())) == 1
        if full and len(meta["labelers"]) == 2:
            pairs.append(tuple(labs.values()))
        prev = old.get(it["key"], {})
        final = prev.get("final") or (next(iter(labs.values())) if agree else "")
        if full and not agree and not final:
            pending.append(it["key"])
        rows.append({**it, **{f"{n}_label": labs[n] for n in meta["labelers"]}, "agree": "" if not full else ("yes" if agree else "no"),
                     "final": final, "note": prev.get("note", "")})
    fields = ["key", "pr", "cluster", "fingerprint"] + [f"{n}_label" for n in meta["labelers"]] + ["agree", "final", "note"]
    write_csv(out / "reconciled.csv", fields, rows)
    both = sum(1 for r in rows if r["agree"])
    print(f"{both}/{len(rows)} items labeled by everyone; agreement "
          f"{(100 * sum(1 for r in rows if r['agree'] == 'yes') / both):.0f}%" if both else "no item labeled by everyone yet",
          end="")
    k = kappa(pairs)
    print(f"; Cohen's kappa {k}" if k is not None else "")
    for key in pending:
        r = next(r for r in rows if r["key"] == key)
        print(f"  disagree {key}: " + ", ".join(f"{n}={r[n + '_label']}" for n in meta["labelers"]) + "  -> decide `final` in reconciled.csv")
    print(f"wrote {out / 'reconciled.csv'}")


def cmd_eval(t, a, data_dir=None):
    data_dir = Path(data_dir or t.data)
    out = data_dir / "labels"
    meta = load(out / "items.json") or die("run `export` first")
    if not (out / "reconciled.csv").is_file():
        die("run `reconcile` first")
    cur = {c["key"]: c for c in all_clusters(data_dir)}
    w = {v: (s["available"] / s["exported"] if s["exported"] else 0) for v, s in meta["strata"].items()}
    raw = {t_: {p: 0 for p in LABELS} for t_ in LABELS}
    wt = {t_: {p: 0.0 for p in LABELS} for t_ in LABELS}
    stale, skipped, labeled = [], 0, {}
    for r in read_csv(out / "reconciled.csv"):
        final = norm(r["final"])
        if not final:
            skipped += 1
            continue
        if final not in LABELS:
            die(f"invalid final label {final!r} for {r['key']}")
        c = cur.get(r["key"])
        if not c or c["fingerprint"] != r["fingerprint"]:
            stale.append(r["key"])
            continue
        raw[final][c["verdict"]] += 1
        wt[final][c["verdict"]] += w[c["verdict"]]
        labeled[r["key"]] = (c["pr"], final, c["verdict"])

    def prf(m, cls="unintended"):
        tp = m[cls][cls]
        pred = sum(m[t_][cls] for t_ in LABELS)
        act = sum(m[cls].values())
        return {"precision": None if not pred else round(tp / pred, 3), "recall": None if not act else round(tp / act, 3),
                "predicted": round(pred, 2), "actual": round(act, 2)}

    n = sum(sum(v.values()) for v in raw.values())
    by_pr = {}
    for pr, final, pred in labeled.values():
        by_pr.setdefault(pr, []).append((final, pred))
    exported_per_pr = {}
    for i in meta["items"]:
        exported_per_pr[i["pr"]] = exported_per_pr.get(i["pr"], 0) + 1
    pr_rows = []
    for pr, lst in sorted(by_pr.items()):
        if len(lst) == exported_per_pr[pr] == sum(1 for c in cur.values() if c["pr"] == pr):  # every cluster of the PR was labeled
            pr_rows.append({"pr": pr, "truth": any(f == "unintended" for f, _ in lst), "predicted": any(p == "unintended" for _, p in lst)})
    pr_tp = sum(1 for r in pr_rows if r["truth"] and r["predicted"])
    labs = [(norm(r[f"{meta['labelers'][0]}_label"]), norm(r[f"{meta['labelers'][1]}_label"])) for r in read_csv(out / "reconciled.csv")
            if len(meta["labelers"]) == 2 and norm(r[f"{meta['labelers'][0]}_label"]) in LABELS and norm(r[f"{meta['labelers'][1]}_label"]) in LABELS]
    res = {"target": t.name, "items_scored": n, "items_without_final": skipped, "stale_labels_skipped": stale,
           "confusion_raw": {"rows": "hand label", "columns": "classifier", "counts": raw},
           "accuracy_raw": None if not n else round(sum(raw[k][k] for k in LABELS) / n, 3),
           "unintended_raw": prf(raw), "unintended_weighted": prf(wt),
           "weights": {k: round(v, 2) for k, v in w.items()},
           "pr_level": {"prs": len(pr_rows), "true_regressions": sum(1 for r in pr_rows if r["truth"]),
                        "flagged": sum(1 for r in pr_rows if r["predicted"]), "caught": pr_tp, "rows": pr_rows},
           "labeler_kappa": kappa(labs), "labeler_pairs": len(labs)}
    write_text(out / "eval.json", json.dumps(res, indent=2) + "\n")
    print(f"{n} items scored against hand labels ({skipped} without a final label, {len(stale)} stale)")
    print("hand label \\ classifier   " + "  ".join(f"{p:>10}" for p in LABELS))
    for t_ in LABELS:
        print(f"{t_:<24}" + "  ".join(f"{raw[t_][p]:>10}" for p in LABELS))
    print(f"accuracy (raw, biased by sampling): {res['accuracy_raw']}")
    for tag in ("raw", "weighted"):
        m = res[f"unintended_{tag}"]
        print(f"unintended {tag}: precision {m['precision']}, recall {m['recall']} (predicted {m['predicted']}, actual {m['actual']})")
    print(f"PR level: {res['pr_level']['caught']}/{res['pr_level']['true_regressions']} true regressions flagged, "
          f"{res['pr_level']['flagged']} PRs flagged, over {res['pr_level']['prs']} fully labeled PRs; labeler kappa {res['labeler_kappa']} "
          f"over {res['labeler_pairs']} items\nwrote {out / 'eval.json'}")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["export", "check", "reconcile", "eval"])
    ap.add_argument("target")
    ap.add_argument("--labelers", nargs="+", default=["dennis", "parvi"])
    ap.add_argument("--intended-sample", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out-dir")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if len(a.labelers) != len(set(a.labelers)):
        ap.error("labeler names must differ")
    t = Target(a.target)
    {"export": cmd_export, "check": cmd_check, "reconcile": cmd_reconcile, "eval": cmd_eval}[a.command](t, a)


if __name__ == "__main__":
    main()
