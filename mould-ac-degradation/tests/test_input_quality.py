"""Missing readings must never become zero use or a continuous observed run."""

import unittest
import numpy as np
import pandas as pd

from _support import minute_inputs
from bq2 import input_audit as audit, reference_models as models, zone_screen as screen


class QualityTests(unittest.TestCase):
    def test_invalid_power_and_sensor_values_fail_the_correct_gate(self):
        raw, frame, *_ = minute_inputs()
        spec = screen.column_spec(frame.columns, 1)
        frame.loc[frame.index[0], spec["ac"][0]] = np.nan
        frame.loc[frame.index[1], spec["plug"]] = -1
        frame.loc[frame.index[2], spec["temp"]] = 45
        frame.loc[frame.index[3], spec["rh"]] = np.inf
        mask = screen.valid_masks(frame, spec)
        self.assertFalse(mask.iloc[0].ac)
        self.assertFalse(mask.iloc[1].energy)
        self.assertTrue(mask.iloc[1].environment)
        self.assertFalse(mask.iloc[2].environment)
        self.assertTrue(mask.iloc[2].energy)
        self.assertFalse(mask.iloc[3].environment)

    def test_meter_selection_does_not_mix_zones_or_other_end_uses(self):
        columns = ["z1_AC1(kW)", "z1_AC2(kW)", "z1_Light(kW)", "z11_AC1(kW)"]
        self.assertEqual(screen.column_spec(columns, 1)["ac"], columns[:2])

    def test_missing_value_interrupts_flatline(self):
        frame = pd.DataFrame({"temp": [24, 24, np.nan, 24, 24, 24]})
        self.assertEqual(screen.flatline_minutes(frame, ["temp"]), 3)

    def test_power_ranges_reject_negative_and_infinite_values(self):
        frame = pd.DataFrame({audit.PLUG: [0, 0.5, -0.1, np.inf, np.nan]})
        self.assertEqual(audit.valid_channel(frame, audit.PLUG).tolist(),
                         [True, True, False, False, False])


class FeatureTests(unittest.TestCase):
    def test_complete_day_energy_uses_all_meters_and_minutes(self):
        daily, *_ = models.build_tables(*minute_inputs())
        self.assertTrue(daily.eligible.all())
        np.testing.assert_allclose(daily.ac_kWh, 192.0)  # 8 kW × 24 h
        np.testing.assert_allclose(daily.plug_kWh, 14.4)

    def test_one_filled_power_minute_removes_only_observed_day(self):
        raw, clean, hourly, weather, helpers = minute_inputs()
        raw.iloc[15, raw.columns.get_loc("z1_AC1(kW)")] = np.nan
        daily, *_ = models.build_tables(raw, clean, hourly, weather, helpers)
        filled = daily[daily.variant.eq("with_fills")]
        observed = daily[daily.variant.eq("without_fills")]
        self.assertEqual(filled.eligible.tolist(), [True, True])
        self.assertEqual(observed.eligible.tolist(), [False, True])
        self.assertTrue(np.isnan(observed.iloc[0].ac_kWh))
        self.assertEqual(observed.iloc[1].ac_kWh, 192.0)

    def test_replaced_present_reading_is_also_excluded(self):
        raw, clean, hourly, weather, helpers = minute_inputs()
        raw.iloc[15, raw.columns.get_loc("z1_Plug(kW)")] = 999
        daily, *_ = models.build_tables(raw, clean, hourly, weather, helpers)
        observed = daily[daily.variant.eq("without_fills")]
        self.assertEqual(observed.eligible.tolist(), [False, True])

    def test_missing_power_breaks_startup_continuity(self):
        dates = pd.date_range("2018-07-02", periods=120, freq="min")
        power = pd.Series([0.0] * 60 + [2.0] * 60, index=dates)
        self.assertEqual(models.strict_events(power, 1.0).event.tolist(), ["start"])
        power.iloc[50] = np.nan
        self.assertTrue(models.strict_events(power, 1.0).empty)

    def test_continuous_operation_has_a_usable_empty_event_table(self):
        dates = pd.date_range("2018-07-02", periods=120, freq="min")
        events = models.strict_events(pd.Series(2.0, index=dates), 1.0)
        self.assertTrue(events.empty)
        self.assertEqual(events.time.dt.month.tolist(), [])
