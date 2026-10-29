"""Shared helpers for the BQ2 analysis (mould risk + AC degradation).

Builds on outputs that already exist in the repo:
  - data-cleaning/outputs/analytics/zone_hourly.csv   (cleaned zone x hour table, with day_type)
  - data-cleaning/outputs/clean/<year>Floor<f>.csv     (cleaned minute data, for AC on/off events)
  - baseline/data/bangkok_era5_hourly_2018-2019.csv    (ERA5 cache, loaded by the baseline)

Put this file in the repo root (next to data-cleaning/ and baseline/) and import it from
both bq2_humidity.ipynb and bq2_ac.ipynb so you both use identical definitions.
"""
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- scope and data-quality flags
SCOPE_FLOORS = [3, 4, 5, 6, 7]
SCOPE_ZONES = [1, 2, 4, 5]

# Floor 5 zone 1: the cleaning notebook found this sensor sits in AC supply air (reads ~14-17 °C
# in office hours). Cold air reads HIGH RH, so its RH and dew-point results are also biased.
# Keep it in tables, but flag it and don't rank it alongside the other zones.
SUSPECT_SENSORS = {(5, 1): "Sensor in AC supply air: temperature biased cold, RH biased high (cleaning notebook 3.7/6.5)"}

# Building-wide indoor-sensor outage (cleaning notebook 3.2). Sensor-based metrics have no data here,
# so 2018 vs 2019 like-for-like comparison is only possible for Jul to mid-Sep.
SENSOR_OUTAGE = (pd.Timestamp("2018-09-12"), pd.Timestamp("2019-03-06"))


# ---------------------------------------------------------------- psychrometrics
def sat_vp_hpa(t_c):
    """Saturation vapour pressure (hPa), Magnus formula (Sonntag 1990 coefficients)."""
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


def dew_point_c(t_c, rh_pct):
    rh = np.clip(rh_pct, 1, 100)
    g = np.log(rh / 100) + 17.62 * t_c / (243.12 + t_c)
    return 243.12 * g / (17.62 - g)


def humidity_ratio_gkg(t_c, rh_pct, p_hpa=1013.25):
    """Grams of water vapour per kg of dry air."""
    pv = np.clip(rh_pct, 0, 100) / 100 * sat_vp_hpa(t_c)
    return 622 * pv / (p_hpa - pv)


def enthalpy_kjkg(t_c, w_gkg):
    """Moist-air enthalpy (kJ per kg dry air). Captures sensible + latent load in one number."""
    w = w_gkg / 1000
    return 1.006 * t_c + w * (2501 + 1.86 * t_c)


def surface_rh_pct(dew_c, surface_t_c):
    """RH at a surface colder than the room air (same moisture content, lower temperature)."""
    return np.clip(100 * sat_vp_hpa(dew_c) / sat_vp_hpa(surface_t_c), 0, 100)


# ---------------------------------------------------------------- seasons (Thai Meteorological Department)
SEASON_ORDER = ["hot", "rainy", "cool"]


def season(month):
    """Hot: Mar-May, rainy: Jun-Oct, cool: Nov-Feb. Works on an int or a Series of months."""
    m = pd.Series(month) if not isinstance(month, pd.Series) else month
    out = pd.Series(np.select([m.between(3, 5), m.between(6, 10)], ["hot", "rainy"], "cool"), index=m.index)
    return pd.Categorical(out, categories=SEASON_ORDER, ordered=True)


# ---------------------------------------------------------------- loading and merging
def load_zone_hourly(path, scope_only=True):
    """Cleaned zone x hour table + indoor dew point, humidity ratio, season and quality flag."""
    zh = pd.read_csv(path, parse_dates=["Date"])
    if scope_only:
        zh = zh[zh["floor"].isin(SCOPE_FLOORS) & zh["zone"].astype(int).isin(SCOPE_ZONES)].copy()
    zh["zone"] = zh["zone"].astype(int)
    zh["indoor_dew_C"] = dew_point_c(zh["temp_C"], zh["rh_pct"])
    zh["indoor_w_gkg"] = humidity_ratio_gkg(zh["temp_C"], zh["rh_pct"])
    zh["season"] = season(zh["Date"].dt.month)
    zh["year"] = zh["Date"].dt.year
    zh["suspect_sensor"] = [(f, z) in SUSPECT_SENSORS for f, z in zip(zh["floor"], zh["zone"])]
    return zh


def add_outdoor_psychrometrics(weather):
    """Adds outdoor humidity ratio and enthalpy to the ERA5 table from load_bangkok_era5_weather()."""
    w = weather.copy()
    w["outdoor_w_gkg"] = humidity_ratio_gkg(w["outdoor_temp_C"], w["outdoor_rh_pct"])
    w["outdoor_enthalpy_kJkg"] = enthalpy_kjkg(w["outdoor_temp_C"], w["outdoor_w_gkg"])
    return w


def merge_weather(zone_hourly, weather):
    """Joins hourly ERA5 onto the zone table by timestamp and adds moisture removal (out - in)."""
    w = add_outdoor_psychrometrics(weather)
    w = w.reset_index().rename(columns={w.index.name or "index": "Date"})
    df = zone_hourly.merge(w, on="Date", how="left")
    df["moisture_removal_gkg"] = df["outdoor_w_gkg"] - df["indoor_w_gkg"]
    return df


# ---------------------------------------------------------------- AC on/off events (minute data)
def ac_on_threshold(ac_kw):
    """'On' = above 20% of the zone's 95th-percentile AC power, and at least 0.5 kW (above standby)."""
    return max(0.5, 0.2 * ac_kw.quantile(0.95))


def detect_ac_events(ac_kw, min_state_minutes=30):
    """Start-ups and shutdowns from a minute-level AC kW series (DatetimeIndex).

    An event is kept only if the AC was in the old state for >= min_state_minutes before it and
    stays in the new state for >= min_state_minutes after it, so brief cycling isn't counted.
    Returns a DataFrame: time, event ('start' or 'stop'), threshold_kW.
    """
    ac_kw = ac_kw.dropna()
    thr = ac_on_threshold(ac_kw)
    on = (ac_kw > thr).astype(int)
    run_id = on.ne(on.shift()).cumsum()
    runs = pd.DataFrame({"state": on.groupby(run_id).first(),
                         "start": ac_kw.index.to_series().groupby(run_id).first(),
                         "minutes": on.groupby(run_id).size()}).reset_index(drop=True)
    # A real transition also needs the series to be continuous across it (no data gap)
    events = []
    for i in range(1, len(runs)):
        prev, cur = runs.iloc[i - 1], runs.iloc[i]
        if prev.minutes < min_state_minutes or cur.minutes < min_state_minutes:
            continue
        before = cur.start - pd.Timedelta(minutes=1)
        if before not in ac_kw.index:
            continue
        events.append({"time": cur.start, "event": "start" if cur.state == 1 else "stop"})
    out = pd.DataFrame(events, columns=["time", "event"])
    out["threshold_kW"] = thr
    return out


def zone_minute_series(clean_dir, floor, zone):
    """Minute-level AC kW (all AC meters summed), temperature and RH for one zone, both years."""
    parts = [pd.read_csv(Path(clean_dir) / f"{y}Floor{floor}.csv", parse_dates=["Date"], index_col="Date")
             for y in (2018, 2019)]
    df = pd.concat(parts)
    ac_cols = [c for c in df.columns if c.startswith(f"z{zone}_AC")]
    out = pd.DataFrame(index=df.index)
    out["ac_kW"] = df[ac_cols].sum(axis=1, min_count=len(ac_cols)) if ac_cols else np.nan
    out["temp_C"] = df.get(f"z{zone}_S1(degC)")
    out["rh_pct"] = df.get(f"z{zone}_S1(RH%)")
    out["indoor_w_gkg"] = humidity_ratio_gkg(out["temp_C"], out["rh_pct"])
    return out
