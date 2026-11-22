import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pipeline import labels


def cluster(key, verdict, programs=("a.cpp",)):
    pr, cid = key.split("-")
    return {"id": cid, "status": "output_diff", "failed_on": None, "programs": list(programs), "verdict": verdict,
            "key": key, "pr": int(pr), "fingerprint": labels.fingerprint({"status": "output_diff", "failed_on": None, "programs": list(programs)}),
            "dir": Path(".")}


def make_data(root, spec):
    """spec: {pr: [(cluster id, verdict), ...]} -> data dir with classification.json files."""
    for pr, cl in spec.items():
        d = Path(root) / "tests" / str(pr)
        d.mkdir(parents=True)
        (d / "classification.json").write_text(json.dumps({"clusters": [
            {"id": cid, "status": "output_diff", "failed_on": None, "programs": ["a.cpp"], "verdict": v, "confidence": "high", "reason": "SECRET"}
            for cid, v in cl]}))


def args(out=None, **kw):
    return SimpleNamespace(labelers=["dennis", "parvi"], intended_sample=2, seed=1, out_dir=out, force=False, **kw)


class Sampling(unittest.TestCase):
    def test_all_nonintended_and_sample_of_intended(self):
        cl = [cluster(f"1-C{i}", "intended") for i in range(6)] + [cluster("2-C1", "unintended"), cluster("2-C2", "unclear")]
        chosen, strata = labels.pick(cl, 2, 1)
        self.assertEqual(len(chosen), 4)
        self.assertEqual(strata["intended"], {"available": 6, "exported": 2})
        self.assertEqual(strata["unintended"], {"available": 1, "exported": 1})
        self.assertEqual(labels.pick(cl, 2, 1)[0], chosen)  # seeded

    def test_small_intended_taken_whole(self):
        chosen, strata = labels.pick([cluster("1-C1", "intended")], 5, 1)
        self.assertEqual(strata["intended"], {"available": 1, "exported": 1})


class Kappa(unittest.TestCase):
    def test_values(self):
        self.assertEqual(labels.kappa([("intended", "intended"), ("unintended", "unintended")]), 1.0)
        self.assertIsNone(labels.kappa([]))
        self.assertIsNone(labels.kappa([("intended", "intended")]))  # chance agreement 1
        self.assertEqual(labels.kappa([("intended", "intended"), ("intended", "unintended"),
                                       ("unintended", "unintended"), ("unintended", "intended")]), 0.0)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "data"
        make_data(self.root, {1: [("C1", "unintended"), ("C2", "intended")], 2: [("C1", "intended")], 3: [("C1", "unintended")]})
        self.t = SimpleNamespace(name="x", data=self.root)
        self.addCleanup(self.tmp.cleanup)
        # evidence needs real PR data; stub it, and check separately that no verdict can leak through the block
        self.p = mock.patch.object(labels, "evidence", lambda t, c: f"## {c['key']}\n")
        self.p.start()
        self.addCleanup(self.p.stop)
        self.out = self.root / "labels"

    def export(self, **kw):
        a = args(**kw)
        a.intended_sample = 10
        labels.cmd_export(self.t, a, self.root)

    def fill(self, name, mapping):
        rows = labels.read_csv(self.out / f"labels_{name}.csv")
        for r in rows:
            r["label"] = mapping.get(r["key"], "")
        labels.write_csv(self.out / f"labels_{name}.csv", labels.FIELDS, rows)

    def test_export_hides_classifier_output(self):
        self.export()
        text = (self.out / "items.md").read_text()
        self.assertNotIn("SECRET", text)
        self.assertNotIn("verdict", (self.out / "labels_dennis.csv").read_text())
        self.assertEqual(len(labels.read_csv(self.out / "labels_parvi.csv")), 4)

    def test_export_refuses_to_overwrite_labels(self):
        self.export()
        self.fill("dennis", {"1-C1": "intended"})
        with self.assertRaises(SystemExit):
            self.export()

    def test_reconcile_eval(self):
        self.export()
        d = {"1-C1": "unintended", "1-C2": "intended", "2-C1": "intended", "3-C1": "intended"}
        p = dict(d, **{"2-C1": "unclear"})
        self.fill("dennis", d)
        self.fill("parvi", p)
        labels.cmd_reconcile(self.t, args(), self.root)
        rows = {r["key"]: r for r in labels.read_csv(self.out / "reconciled.csv")}
        self.assertEqual(rows["2-C1"]["agree"], "no")
        self.assertEqual(rows["2-C1"]["final"], "")
        self.assertEqual(rows["1-C1"]["final"], "unintended")
        with self.assertRaises(SystemExit) as ctx:  # still labels without final are fine; but a bad final is not
            rows["3-C1"]["final"] = "bogus"
            labels.write_csv(self.out / "reconciled.csv", list(rows["3-C1"]), list(rows.values()))
            labels.cmd_eval(self.t, args(), self.root)
        self.assertIn("invalid", str(ctx.exception))
        rows["3-C1"]["final"] = "intended"
        rows["2-C1"]["final"] = "intended"
        rows["2-C1"]["note"] = "discussed"
        labels.write_csv(self.out / "reconciled.csv", list(rows["3-C1"]), list(rows.values()))
        labels.cmd_reconcile(self.t, args(), self.root)  # rerun keeps final and note
        kept = {r["key"]: r for r in labels.read_csv(self.out / "reconciled.csv")}
        self.assertEqual((kept["2-C1"]["final"], kept["2-C1"]["note"]), ("intended", "discussed"))
        res = labels.cmd_eval(self.t, args(), self.root)
        self.assertEqual(res["items_scored"], 4)
        self.assertEqual(res["confusion_raw"]["counts"]["unintended"]["unintended"], 1)
        self.assertEqual(res["confusion_raw"]["counts"]["intended"]["unintended"], 1)  # PR 3 false positive
        self.assertEqual(res["unintended_raw"]["precision"], 0.5)
        self.assertEqual(res["unintended_raw"]["recall"], 1.0)
        self.assertEqual(res["pr_level"], {**res["pr_level"], "prs": 3, "true_regressions": 1, "flagged": 2, "caught": 1})
        self.assertEqual(res["labeler_pairs"], 4)

    def test_weights_and_stale(self):
        self.export()
        self.fill("dennis", {k: "intended" for k in ("1-C1", "1-C2", "2-C1", "3-C1")})
        self.fill("parvi", {k: "intended" for k in ("1-C1", "1-C2", "2-C1", "3-C1")})
        labels.cmd_reconcile(self.t, args(), self.root)
        meta = json.loads((self.out / "items.json").read_text())
        meta["strata"]["intended"] = {"available": 10, "exported": 2}  # pretend intended was subsampled 5x
        (self.out / "items.json").write_text(json.dumps(meta))
        rows = labels.read_csv(self.out / "reconciled.csv")
        rows[0]["fingerprint"] = "stale"
        labels.write_csv(self.out / "reconciled.csv", list(rows[0]), rows)
        res = labels.cmd_eval(self.t, args(), self.root)
        self.assertEqual(len(res["stale_labels_skipped"]), 1)
        self.assertEqual(res["weights"]["intended"], 5.0)

    def test_invalid_label_rejected(self):
        self.export()
        self.fill("dennis", {"1-C1": "maybe"})
        with self.assertRaises(SystemExit):
            labels.cmd_reconcile(self.t, args(), self.root)


if __name__ == "__main__":
    unittest.main()
