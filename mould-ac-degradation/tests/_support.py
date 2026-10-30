"""Shared test imports and small synthetic inputs; no building-data reads."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ANALYSIS_DIR.parent
sys.path.insert(0, str(ANALYSIS_DIR / "src"))


def minute_inputs():
    """Two complete working days with eight kW AC and 0.6 kW plug load."""
    index = pd.date_range("2018-07-02", periods=2880, freq="min", name="Date")
    frame = pd.DataFrame({**{f"z1_AC{i}(kW)": 2.0 for i in range(1, 5)},
                          "z1_Plug(kW)": 0.6, "z1_S1(degC)": 24.0,
                          "z1_S1(RH%)": 55.0}, index=index)
    hours = index[::60]
    hourly = pd.DataFrame({"day_type": "working day"}, index=hours)
    weather = pd.DataFrame({"outdoor_temp_C": 30.0, "outdoor_w_gkg": 15.0,
                            "outdoor_enthalpy_kJkg": 70.0}, index=hours)
    # Stubs isolate energy/coverage logic from the unchanged psychrometric helper.
    helpers = {"add_outdoor_psychrometrics": lambda value: value.copy(),
               "humidity_ratio_gkg": lambda temp, rh: pd.Series(10.0, index=temp.index),
               "ac_on_threshold": lambda value: 1.0}
    return frame.copy(), frame, hourly, weather, helpers


def reference_days():
    dates = pd.date_range("2018-07-01", periods=35, freq="D")
    x = np.arange(len(dates), dtype=float)
    return pd.DataFrame({"time": dates, "date": dates, "x": x, "target": 2 + 3 * x})
