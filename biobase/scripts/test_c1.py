"""Numerical and data-isolation checks for C1 model selection."""
import unittest

import numpy as np

from c1_embeddings import folds
from c1_features import normalize
from c1_screen import ridge_fit, ridge_loo


class C1Checks(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(23)
        x = normalize(rng.normal(size=(20, 8)))
        x[-1] = 0  # A missing feature block must remain valid.
        self.kernel = x @ x.T
        self.labels = np.arange(20) % 4
        self.targets = np.eye(4)[self.labels]

    def test_leave_one_out_matches_explicit_refits(self):
        train = np.arange(20)
        for alpha in [0.003, 0.1, 1.]:
            fast = ridge_loo(self.kernel, self.targets, train, [alpha])[0]
            exact = np.vstack([ridge_fit(self.kernel, self.targets, train[train != i], [i], alpha) for i in train])
            np.testing.assert_allclose(fast, exact, atol=1e-9)

    def test_validation_targets_do_not_affect_fitting(self):
        train, validation = np.arange(14), np.arange(14, 20)
        expected = ridge_fit(self.kernel, self.targets, train, validation, 0.1)
        poisoned = self.targets.copy()
        poisoned[validation] = 12345
        actual = ridge_fit(self.kernel, poisoned, train, validation, 0.1)
        np.testing.assert_array_equal(expected, actual)

    def test_folds_keep_slides_separate_and_rare_classes_in_training(self):
        labels = np.array([0, 0, 1, 1, 2, 2, 2, 2, 2])
        indices = np.arange(len(labels))
        for seed in [17, 101, 211, 307, 401, 503]:
            parts = folds(indices, labels, seed)
            self.assertEqual(sorted(np.concatenate(parts)), list(indices))
            for validation in parts:
                train = np.setdiff1d(indices, validation)
                self.assertFalse(set(train) & set(validation))
                self.assertTrue(set(labels[validation]) <= set(labels[train]))

    def test_zero_feature_is_finite(self):
        np.testing.assert_array_equal(normalize(np.zeros((2, 8))), np.zeros((2, 8)))


if __name__ == "__main__":
    unittest.main()
