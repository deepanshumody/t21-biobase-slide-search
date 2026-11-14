#!/usr/bin/env python3
"""Behavioral checks for leakage, ranking, and the C2 submission contract."""
import unittest

import numpy as np

from c2_retrieval import (
    FEATURES, fit_organs, precision, rank_results, select_weight,
    split_folds, validate_submission, visual_similarity,
)


class RetrievalTests(unittest.TestCase):
    def test_hidden_labels_cannot_affect_model_or_selection(self):
        rng = np.random.default_rng(31)
        features = rng.normal(size=(36, 12))
        features /= np.linalg.norm(features, axis=1, keepdims=True)
        similarity = features @ features.T
        kernels = {name: similarity for name in FEATURES}
        kernels["class_count"] = 3
        labels = np.arange(36) % 3
        train = np.arange(27)
        altered = labels.copy()
        altered[27:] = (altered[27:] + 1) % 3
        probabilities, model = fit_organs(kernels, labels, train)
        other, other_model = fit_organs(kernels, altered, train)
        np.testing.assert_array_equal(probabilities, other)
        self.assertEqual(model, other_model)
        ids = np.array([str(i) for i in range(36)])
        self.assertEqual(select_weight(kernels, labels, train, similarity, ids, 43),
                         select_weight(kernels, altered, train, similarity, ids, 43))

    def test_known_labels_and_uncertain_matches(self):
        probabilities = np.array([[0.7, 0.3], [1., 0.], [0., 1.], [0.8, 0.2]])
        similarity = np.array([[1., 0.2, 0.9, 0.4], [0.2, 1., 0., 0.],
                               [0.9, 0., 1., 0.], [0.4, 0., 0., 1.]])
        ids = np.array(["query", "known_correct", "known_other", "uncertain"])
        args = (probabilities, similarity, np.array([0]), np.arange(4))
        np.testing.assert_array_equal(rank_results(*args, 1, ids, k=3), [[1, 3, 2]])
        np.testing.assert_array_equal(rank_results(*args, 0, ids, k=3), [[2, 3, 1]])

    def test_ties_visual_then_identifier(self):
        p = np.ones((4, 1))
        similarity = np.array([[1., 0.2, 0.5, 0.5]] * 4)
        result = rank_results(p, similarity, np.array([0]), np.arange(4), 1,
                              np.array(["q", "z", "b", "a"]), k=3)
        np.testing.assert_array_equal(result, [[3, 2, 1]])

    def test_missing_features_do_not_mix_cosine_scales(self):
        kernels = {"gigapath": np.array([[1., 0.4, 0.], [0.4, 1., 0.], [0., 0., 0.]]),
                   "biomedclip": np.full((3, 3), 0.95)}
        visual = visual_similarity(kernels, {"gigapath": np.array([True, True, False])})
        self.assertEqual(visual[0, 1], 0.4)
        self.assertEqual(visual[0, 2], 0.)

    def test_submission_contract_and_failures(self):
        rows = [{"query_slide_id": "q", "rank": i + 1, "result_slide_id": f"r{i}"} for i in range(10)]
        valid_ids = {"q"} | {f"r{i}" for i in range(10)}
        validate_submission(rows, {"q"}, valid_ids)
        for bad in [rows[:-1], [{**row, "rank": 1} for row in rows],
                    [{**row, "result_slide_id": "q"} for row in rows],
                    [{**row, "result_slide_id": "r0"} for row in rows],
                    [{**row, "result_slide_id": "unknown"} for row in rows]]:
            with self.assertRaises(ValueError):
                validate_submission(bad, {"q"}, valid_ids)

    def test_folds_cover_rare_groups_once(self):
        labels = np.array([0] * 2 + [1] * 7 + [2] * 12)
        parts = split_folds(np.arange(len(labels)), labels, 43)
        np.testing.assert_array_equal(np.sort(np.concatenate(parts)), np.arange(len(labels)))
        self.assertLessEqual(max(map(len, parts)) - min(map(len, parts)), 1)
        self.assertEqual(sum(np.any(labels[part] == 0) for part in parts), 2)

    def test_precision_counts_and_unknown_label_rejection(self):
        labels = np.array([1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        result = precision(labels, np.array([0]), np.arange(1, 11)[None, :])
        np.testing.assert_allclose(result, [[1, 0.6, 0.5]])
        labels[10] = -1
        with self.assertRaises(ValueError):
            precision(labels, np.array([0]), np.arange(1, 11)[None, :])


if __name__ == "__main__":
    unittest.main()
