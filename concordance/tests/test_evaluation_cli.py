"""Exercise the same evaluation commands used to generate published results."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class EvaluationCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("concordance_breast", "concordance_colon", "criteria_search"):
            target = self.root / folder
            target.mkdir()
            for source in (SOURCE / folder).glob("*.py"):
                shutil.copy2(source, target / source.name)
        for source in SOURCE.glob("*.py"):
            shutil.copy2(source, self.root / source.name)

    def fixture(self, organ):
        ids, i = [], 0
        while len(ids) < 100:
            rid = f"SYNTHETIC-EVALUATION-{i:04}"
            if int(hashlib.md5(rid.encode()).hexdigest(), 16) % 2:
                ids.append(rid)
            i += 1
        reports = [{
            "id": rid,
            "report_text": "Pathologic stage: pT2 pN1a.\nLymph nodes: 1 of 10 positive.\n",
            "gold": {"t_major": 2, "n_major": 1, "nodes_pos": 1, "age": 75},
        } for rid in ids]
        folder = self.root / f"concordance_{organ}"
        data = folder / "data"
        data.mkdir()
        name = "brca_linked.jsonl" if organ == "breast" else "coadread_linked.jsonl"
        (data / name).write_text("".join(json.dumps(r) + "\n" for r in reports))
        return folder

    def test_top_ten_of_one_hundred_is_ten_percent_recall(self):
        for organ, criterion in (("breast", "B6"), ("colon", "C1")):
            with self.subTest(organ=organ):
                result = subprocess.run(
                    [sys.executable, "evaluate.py", "--holdout"],
                    cwd=self.fixture(organ), capture_output=True, text=True, check=True,
                )
                # Columns: criterion, budget, reviewed, hits, positives, precision, recall, excluded.
                self.assertRegex(
                    result.stdout,
                    rf"(?m)^\s+{criterion}\s+10\s+10\s+10\s+100\s+1\.000\s+0\.100\s+0$",
                )
                self.assertIn("match decisions only", result.stdout)
                self.assertIn("no_match decisions only", result.stdout)

    def test_holdout_cannot_be_used_to_fit_calibration_or_generate_audit(self):
        folder = self.fixture("colon")
        for action in ("--fit", "--audit"):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, "evaluate.py", action, "--holdout"],
                    cwd=folder, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DEV only", result.stderr)
                self.assertFalse((folder / "calibration.json").exists())
                self.assertFalse((folder / "audit").exists())


if __name__ == "__main__":
    unittest.main()
