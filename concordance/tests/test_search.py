"""End-to-end cohort export and checks against accidental use of evaluation labels."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search import search

SOURCE = Path(__file__).resolve().parents[1]


class CohortSearchTests(unittest.TestCase):
    def test_demo_command_exports_matches_exclusions_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidates.json"
            result = subprocess.run(
                [sys.executable, str(SOURCE / "search.py"), "--organ", "colon", "--criterion", "C7",
                 "--input", str(SOURCE / "examples/colon_reports.jsonl"), "--output", str(output)],
                capture_output=True, text=True, check=True,
            )
            self.assertIn("shortlisted=1", result.stdout)
            exported = json.loads(output.read_text())
            self.assertEqual(exported["counts"], {"match": 1, "undetermined": 1, "no_match": 2})
            self.assertEqual(exported["shortlist_ids"], ["DEMO-001"])
            by_id = {row["id"]: row for row in exported["results"]}
            self.assertIn("clinical.age", " ".join(by_id["DEMO-001"]["why"]))
            self.assertIn("pN1a", by_id["DEMO-001"]["facts"]["n_major"]["evidence"])
            self.assertIsNone(by_id["DEMO-003"]["facts"]["n_major"])
            self.assertIn("unknown", " ".join(by_id["DEMO-003"]["why"]))

    def test_breast_export_uses_report_evidence(self):
        records = [{"id": "breast-example", "report_text": "Pathologic stage: pT2 pN1a."}]
        result = search(records, "breast", "B6")
        self.assertEqual(result["shortlist_ids"], ["breast-example"])
        self.assertIn("pN1a", " ".join(result["results"][0]["why"]))

    def test_gold_and_labels_cannot_fill_missing_age(self):
        records = [{"id": "example", "report_text": "Pathologic stage: pT2 pN1a."}]
        expected = search(records, "colon", "C7")
        poisoned = copy.deepcopy(records)
        poisoned[0].update(gold={"age": 90, "n_major": 0}, labels={"AGE": "90"})
        self.assertEqual(search(poisoned, "colon", "C7"), expected)
        self.assertEqual(expected["counts"]["undetermined"], 1)
        self.assertEqual(expected["shortlist_ids"], [])

    def test_clinical_age_is_explicitly_sourced_and_limit_is_respected(self):
        records = [{"id": rid, "report_text": "Pathologic stage: pT2 pN1a.", "clinical": {"age": 75}}
                   for rid in ("z", "a")]
        result = search(records, "colon", "C7", limit=1)
        self.assertEqual(result["shortlist_ids"], ["a"])
        self.assertEqual(result["counts"]["match"], 2)
        self.assertEqual(len(result["results"]), 2)

    def test_duplicate_ids_mixed_organs_and_malformed_input_are_rejected(self):
        record = {"id": "a", "report_text": "Pathologic stage: pT2 pN1a."}
        for records in ([record, record], [{**record, "organ": "breast"}], [None],
                        [{**record, "clinical": {"age": True}}]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                search(records, "colon", "C1")
        with self.assertRaisesRegex(ValueError, "Unknown criterion"):
            search([record], "colon", "B1")

    def test_command_refuses_to_overwrite_its_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reports.jsonl"
            path.write_text('{"id":"a","report_text":"pT2 pN1a"}\n')
            before = path.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SOURCE / "search.py"), "--organ", "colon", "--criterion", "C1",
                 "--input", str(path), "--output", str(path)], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output must differ", result.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
