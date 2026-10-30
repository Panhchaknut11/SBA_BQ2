"""Accounting and matching checks use small, independently specified cases."""

import tempfile
import unittest
import numpy as np
import pandas as pd

from _support import REPO_ROOT
from bq2 import case_investigation as cases


class DiagnosticTests(unittest.TestCase):
    def test_runtime_power_and_below_threshold_contributions_reconcile(self):
        reference = pd.date_range("2018-07-02", periods=20)
        evaluation = pd.date_range("2019-07-02", periods=10)
        rows = []
        for year, dates, hours, power, off in [(2018, reference, 4, 2, .5),
                                               (2019, evaluation, 5, 3, .75)]:
            for date in dates:
                rows.append(dict(zone_id="F3-Z4", variant="with_fills", date=date, year=year,
                                 on_hours=hours, on_kWh=hours * power, off_kWh=off,
                                 ac_kWh=hours * power + off, plug_kWh=1,
                                 interior_below_on_hours=0))
        daily = pd.DataFrame(rows)
        predictions = pd.DataFrame({"zone_id": "F3-Z4", "variant": "with_fills",
                                    "analysis": "energy", "within_reference_support": True,
                                    "time": evaluation})
        with tempfile.TemporaryDirectory() as directory:
            row = cases.energy_decomposition(daily, predictions, directory).iloc[0]
        self.assertEqual(row.reference_days, 20)
        self.assertEqual(row.evaluation_days, 10)
        np.testing.assert_allclose([row.runtime_contribution_kWh, row.power_contribution_kWh,
                                    row.off_contribution_kWh, row.energy_change_kWh],
                                   [2.5, 4.5, .25, 7.25], atol=1e-12)

    def test_matching_respects_hour_weather_and_activity_calipers(self):
        train = pd.DataFrame({"hour": [10] * 3, "outdoor_temp_C": [30.] * 3,
                              "outdoor_w_gkg": [15.] * 3, "plug_kW": [.5] * 3})
        test = pd.DataFrame({"hour": [10, 11, 10, 10],
                             "outdoor_temp_C": [30.8, 30.8, 31.2, 30.8],
                             "outdoor_w_gkg": [15.9] * 4, "plug_kW": [.6, .6, .6, .61]})
        match, caliper = cases.match_matrix(train, test)
        self.assertEqual(caliper, .1)
        self.assertEqual(match.sum(axis=1).tolist(), [3, 0, 0, 0])

    def test_long_off_control_requires_24_hours_and_keeps_overlap_explicit(self):
        frame = pd.DataFrame({"complete": [True] * 3, "working": [True] * 3,
                              "state": ["night_off"] * 3,
                              "near_zero_run_hours": [23.9, 24, 30], "hour": [3, 3, 12]})
        result = cases.state_population(frame)
        self.assertEqual(result.state.eq("long_off").sum(), 1)
        self.assertEqual(len(result), 4)  # The control overlaps the ordinary cohort.
