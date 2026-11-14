"""Behavioral tests for retrieval coverage, review efficiency, and confidence claims."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation_metrics import calibration_metrics, review_budget


def fixture(rows):
    records, answers, gold = [], {}, {}
    for rid, truth, decision, confidence in rows:
        records.append({"id": rid})
        answers[rid] = {"C": {"answer": decision, "conf": confidence}}
        gold[rid] = {"C": truth}
    return records, answers, gold


class ReviewBudgetTests(unittest.TestCase):
    def test_eight_hits_in_ten_reviews_of_one_hundred_positives(self):
        rows = [(f"p{i:03}", "match", "match" if i < 8 else "undetermined", 0.9)
                for i in range(100)]
        rows += [(f"n{i}", "no_match", "match", 0.8) for i in range(2)]
        result = review_budget(*fixture(rows), ["C"], [10])["C"][0]
        self.assertEqual(result["precision"], 0.8)
        self.assertEqual(result["recall"], 0.08)
        self.assertEqual(result["reviewed"], 10)
        self.assertEqual(result["total_positives"], 100)

    def test_short_list_uses_actual_reviews_and_recall_includes_misses(self):
        rows = [("a", "match", "match", 0.9), ("b", "match", "no_match", 0.8),
                ("c", "match", "undetermined", None)]
        result = review_budget(*fixture(rows), ["C"], [10])["C"][0]
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["precision"], 1)
        self.assertAlmostEqual(result["recall"], 1 / 3)

    def test_unknown_gold_candidates_are_excluded_and_counted(self):
        rows = [("unknown", "undetermined", "match", 1), ("positive", "match", "match", 0.9)]
        result = review_budget(*fixture(rows), ["C"], [1])["C"][0]
        self.assertEqual(result["excluded_unknown_gold"], 1)
        self.assertEqual(result["precision"], 1)
        self.assertEqual(result["recall"], 1)

    def test_equal_confidence_ranking_does_not_depend_on_input_order(self):
        rows = [("b", "match", "match", 0.9), ("a", "no_match", "match", 0.9)]
        first = review_budget(*fixture(rows), ["C"], [1, 2])["C"]
        second = review_budget(*fixture(list(reversed(rows))), ["C"], [1, 2])["C"]
        self.assertEqual(first, second)
        self.assertEqual(first[0]["recall"], 0)
        self.assertEqual(first[1]["recall"], 1)

    def test_recall_never_decreases_with_larger_budget(self):
        rows = [(str(i), "match" if i % 3 else "no_match", "match", 1 - i / 100)
                for i in range(40)]
        result = review_budget(*fixture(rows), ["C"], [1, 10, 25, 50])["C"]
        recalls = [row["recall"] for row in result]
        self.assertEqual(recalls, sorted(recalls))
        self.assertEqual(recalls[-1], 1)

    def test_undefined_metrics_are_not_reported_as_measured_zero(self):
        empty = review_budget(*fixture([]), ["C"], [10])["C"][0]
        self.assertIsNone(empty["recall"])
        self.assertIsNone(empty["precision"])
        missed = review_budget(*fixture([("a", "match", "undetermined", None)]), ["C"], [10])["C"][0]
        self.assertEqual(missed["recall"], 0)
        self.assertIsNone(missed["precision"])
        false_match = review_budget(*fixture([("a", "no_match", "match", 1)]), ["C"], [10])["C"][0]
        self.assertIsNone(false_match["recall"])
        self.assertEqual(false_match["precision"], 0)

    def test_invalid_budgets_and_duplicate_patients_are_rejected(self):
        for budget in (0, -1, 1.5, True):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                review_budget(*fixture([]), ["C"], [budget])
        data = fixture([("a", "match", "match", 1)] * 2)
        with self.assertRaisesRegex(ValueError, "unique patient"):
            review_budget(*data, ["C"])


class CalibrationTests(unittest.TestCase):
    def test_correct_exclusions_cannot_mask_bad_shortlist_precision(self):
        rows = [(str(i), "no_match", "no_match", 1) for i in range(98)]
        rows += [("bad1", "no_match", "match", 1), ("bad2", "no_match", "match", 1)]
        data = fixture(rows)
        pooled = calibration_metrics(*data, ["C"])
        matches = calibration_metrics(*data, ["C"], decision="match")
        exclusions = calibration_metrics(*data, ["C"], decision="no_match")
        self.assertAlmostEqual(pooled[0], 0.02)
        self.assertEqual(matches[0], 1)
        self.assertEqual(matches[2], 2)
        self.assertEqual(exclusions[0], 0)
        self.assertEqual(exclusions[2], 98)

    def test_zero_and_one_confidence_are_binned_once(self):
        data = fixture([("zero", "no_match", "match", 0), ("one", "match", "match", 1)])
        error, table, count = calibration_metrics(*data, ["C"])
        self.assertEqual(error, 0)
        self.assertEqual(count, 2)
        self.assertEqual(sum(row[1] for row in table), count)

    def test_abstentions_and_unknown_gold_do_not_enter_calibration(self):
        data = fixture([("a", "match", "undetermined", None), ("b", "undetermined", "match", 1)])
        self.assertEqual(calibration_metrics(*data, ["C"]), (None, [], 0))

    def test_invalid_confidence_fails_instead_of_disappearing_from_bins(self):
        for value in (None, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calibration_metrics(*fixture([("a", "match", "match", value)]), ["C"])


if __name__ == "__main__":
    unittest.main()
