"""Check temporal separation, day weighting and genuinely shared conditions."""

import unittest
import numpy as np
import pandas as pd

from _support import reference_days
from bq2 import reference_models as models


class ReferenceTests(unittest.TestCase):
    def test_each_day_has_equal_total_weight(self):
        frame = pd.DataFrame({"date": pd.to_datetime(["2018-07-01"] * 3 + ["2018-07-02"])})
        weights = models.weights_by_day(frame)
        np.testing.assert_allclose(weights, [1 / 3, 1 / 3, 1 / 3, 1])

    def test_reference_recovers_known_affine_relationship(self):
        train = reference_days()
        fit = models.fit_reference(train, ["x"], "target")
        np.testing.assert_allclose(fit.params, [2, 3], atol=1e-10)

    def test_validation_never_trains_on_its_evaluation_day(self):
        scores, rows = models.temporal_cv(reference_days(), ["x"], "target")
        self.assertTrue(rows.train_last_date.lt(rows.date).all())
        self.assertTrue(rows.date.dt.year.eq(2018).all())
        self.assertLess(scores["MAE"], 1e-9)

    def test_support_rejects_point_inside_ranges_but_outside_hull(self):
        train = pd.DataFrame({"x": [0, 1, 0], "y": [0, 0, 1]})
        test = pd.DataFrame({"x": [0.2, 0.8], "y": [0.2, 0.8]})
        self.assertEqual(models.support_mask(train, test, ["x", "y"]).tolist(), [True, False])

    def test_missing_reference_session_and_changed_constant_are_unsupported(self):
        train = pd.DataFrame({"x": [1, 2, 3], "constant": [5] * 3, "afternoon": [0] * 3})
        test = pd.DataFrame({"x": [2, 2], "constant": [5, 6], "afternoon": [1, 0]})
        self.assertFalse(models.support_mask(train, test, ["x", "constant", "afternoon"]).any())

    def test_degenerate_geometry_withholds_instead_of_loosening_support(self):
        train = pd.DataFrame({"x": [0, 1, 2, 3], "y": [0, 1, 2, 3]})
        test = pd.DataFrame({"x": [1.5], "y": [1.5]})
        self.assertFalse(models.support_mask(train, test, ["x", "y"]).any())

    def test_week_bootstrap_is_deterministic_for_known_shift(self):
        train = reference_days()
        test = train.copy()
        test[["time", "date"]] += pd.DateOffset(years=1)
        test.target += 3
        a = models.block_bootstrap(train, test, ["x"], "target", repetitions=100, seed=42)
        b = models.block_bootstrap(train, test, ["x"], "target", repetitions=100, seed=42)
        self.assertEqual(a, b)
        np.testing.assert_allclose([a["low"], a["high"]], 3, atol=1e-9)

    def test_empty_evaluation_has_no_interval(self):
        train = reference_days()
        result = models.block_bootstrap(train, train.iloc[:0], ["x"], "target")
        self.assertEqual(result["valid_replicates"], 0)
        self.assertTrue(np.isnan(result["low"]))
