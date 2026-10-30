"""F3-Z1 July-August reference models and interpolation/cohort sensitivity."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.spatial import Delaunay, QhullError

from . import input_audit as audit


VARIANTS = ["with_fills", "without_fills"]
ENERGY_CANDIDATES = {
    "mean_only": [],
    "activity_only": ["plug_kWh"],
    "temperature_activity": ["outdoor_temp_C", "plug_kWh"],
    "enthalpy_activity": ["outdoor_enthalpy_kJkg", "plug_kWh"],
}
COOLING_FEATURES = ["initial_temp_C", "outdoor_temp_C", "afternoon"]
MOISTURE_FEATURES = ["outdoor_w_gkg", "outdoor_temp_C", "afternoon", "plug_kW"]


def scoped(index):
    return index.year.isin([2018, 2019]) & index.month.isin([7, 8])


def strict_events(ac_kw, threshold):
    """Reuse the agreed threshold formula with a frozen 2018 value and real gaps."""
    state = np.where(ac_kw.notna(), ac_kw.gt(threshold).astype(int), -1)
    start = np.r_[0, np.flatnonzero(state[1:] != state[:-1]) + 1]
    end = np.r_[start[1:], len(state)]
    rows = []
    for i in range(1, len(start)):
        before, now = start[i - 1], start[i]
        if state[before] >= 0 and state[now] >= 0 and now - before >= 30 and end[i] - now >= 30:
            rows.append({"time": ac_kw.index[now], "event": "start" if state[now] else "stop",
                         "threshold_kW": threshold})
    result = pd.DataFrame(rows, columns=["time", "event", "threshold_kW"])
    # Empty event lists still need a datetime column for downstream .dt filters.
    result["time"] = pd.to_datetime(result["time"])
    return result


def build_tables(raw, clean, hourly, weather, helpers, column_spec=None):
    # Explicit columns permit the same definitions for zones with one or four meters.
    spec = column_spec or {"ac": audit.AC, "temp": audit.TEMP, "rh": audit.RH, "plug": audit.PLUG}
    ac_cols, temp_col, rh_col, plug_col = spec["ac"], spec["temp"], spec["rh"], spec["plug"]
    keep = scoped(clean.index)
    # Original readings replaced by upstream cleaning are also excluded in the strict variant.
    observed = raw.where(raw.eq(clean))
    scope_mask = pd.Series(keep, index=clean.index)
    frames = {"with_fills": clean.where(scope_mask, axis=0),
              "without_fills": observed.where(scope_mask, axis=0)}
    weather = helpers["add_outdoor_psychrometrics"](weather)
    day_type = hourly["day_type"].groupby(hourly.index.normalize()).first()
    ref_ac = observed[ac_cols].sum(axis=1, min_count=len(ac_cols))
    threshold = float(helpers["ac_on_threshold"](ref_ac.loc["2018-07-01":"2018-08-31"]))
    ac_clean = frames["with_fills"][ac_cols].sum(axis=1, min_count=len(ac_cols))
    candidates = strict_events(ac_clean, threshold)
    candidates = candidates[candidates.time.dt.month.isin([7, 8])].copy()

    daily_parts, event_parts, humidity_parts, eligibility = [], [], [], []
    for variant, frame in frames.items():
        valid = pd.DataFrame({c: np.isfinite(frame[c]) & (frame[c].between(15, 40) if c == temp_col
                              else frame[c].between(0, 100) if c == rh_col else frame[c].ge(0))
                              for c in ac_cols + [temp_col, rh_col, plug_col]})
        masks = pd.DataFrame({"ac": valid[ac_cols].all(axis=1),
                              "environment": valid[[temp_col, rh_col]].all(axis=1),
                              "ac_plug": valid[ac_cols + [plug_col]].all(axis=1)})
        ac = frame[ac_cols].sum(axis=1, min_count=len(ac_cols))
        on = masks["ac"] & ac.gt(threshold)
        moisture = helpers["humidity_ratio_gkg"](frame[temp_col], frame[rh_col])
        daily = pd.DataFrame(index=frame.resample("D").size().index)
        complete = masks["ac_plug"].resample("D").sum().eq(1440)
        daily["ac_kWh"] = (ac.resample("D").sum(min_count=1440) / 60).where(complete)
        daily["plug_kWh"] = (frame[plug_col].resample("D").sum(min_count=1440) / 60).where(complete)
        daily["AC_on_hours"] = (on.resample("D").sum() / 60).where(complete)
        daily["on_mean_kW"] = ac.where(on).resample("D").mean().where(complete)
        daily = daily.join(weather[["outdoor_temp_C", "outdoor_w_gkg", "outdoor_enthalpy_kJkg"]].resample("D").mean())
        daily["day_type"] = day_type
        daily = daily[scoped(daily.index) & daily.day_type.eq("working day")].copy()
        daily["eligible"] = complete.reindex(daily.index)
        daily["variant"] = variant
        daily["time"] = daily.index
        daily["date"] = daily.index.normalize()
        daily["year"] = daily.index.year
        daily_parts.append(daily.reset_index(drop=True))

        # Both variants use the same clean-data transition anchors and frozen threshold.
        for candidate in candidates[candidates.event.eq("start")].itertuples():
            pos = frame.index.get_loc(candidate.time)
            if pos < 30 or pos + 60 > len(frame):
                continue
            pre, post = slice(pos - 30, pos), slice(pos, pos + 60)
            state_ok = masks["ac"].iloc[pre].all() and (~on.iloc[pre]).all() and on.iloc[post].all()
            sensor_ok = masks["environment"].iloc[post].all()
            hour = candidate.time.hour
            session_ok = (6 <= hour <= 9) or (12 <= hour <= 14)
            working = day_type.loc[candidate.time.normalize()] == "working day"
            eligible = bool(state_ok and sensor_ok and session_ok and working)
            eligibility.append({"variant": variant, "time": candidate.time, "year": candidate.time.year,
                                "power_window_ok": bool(state_ok), "sensors_complete": bool(sensor_ok),
                                "scheduled_session": session_ok, "working_day": working, "eligible": eligible})
            if not eligible:
                continue
            window = frame.iloc[post]
            air_w = moisture.iloc[post]
            outside = weather.loc[candidate.time.floor("h")]
            row = {"variant": variant, "time": candidate.time, "date": candidate.time.normalize(),
                   "year": candidate.time.year, "afternoon": int(hour >= 12),
                   "initial_temp_C": float(window[temp_col].iloc[:5].median()),
                   "cooling_rate_C_per_h": float(-np.polyfit(np.arange(60), window[temp_col], 1)[0] * 60),
                   "cooling_drop_C": float(window[temp_col].iloc[:5].median() - window[temp_col].iloc[-5:].median()),
                   "drying_rate_gkg_per_h": float(-np.polyfit(np.arange(60), air_w, 1)[0] * 60),
                   "outdoor_temp_C": float(outside.outdoor_temp_C), "outdoor_w_gkg": float(outside.outdoor_w_gkg),
                   "first_hour_AC_kWh": float(window[ac_cols].sum(axis=1, min_count=len(ac_cols)).sum() / 60)}
            event_parts.append(row)

        # Require 120 continuous AC-on minutes ending at the hour's last minute.
        # This excludes the first hour after start-up from the steady-on moisture comparison.
        stable = on.rolling(120, min_periods=120).sum().eq(120).resample("h").last()
        sensors_ok = masks["environment"].resample("h").sum().eq(60)
        plug_ok = frame[plug_col].notna().resample("h").sum().eq(60)
        h = pd.DataFrame({"indoor_w_gkg": moisture.resample("h").mean(),
                          "temp_C": frame[temp_col].resample("h").mean(),
                          "rh_pct": frame[rh_col].resample("h").mean(),
                          "plug_kW": frame[plug_col].resample("h").mean(),
                          "ac_kW": ac.resample("h").mean()}).join(weather)
        h["day_type"] = h.index.normalize().map(day_type)
        h["eligible"] = stable & sensors_ok & plug_ok & h.day_type.eq("working day") & scoped(h.index)
        h = h[h.eligible].copy()
        h["humidity_gap_gkg"] = h.outdoor_w_gkg - h.indoor_w_gkg
        h["afternoon"] = (h.index.hour >= 12).astype(int)
        h["variant"], h["time"], h["date"], h["year"] = variant, h.index, h.index.normalize(), h.index.year
        humidity_parts.append(h.reset_index(drop=True))
    return (pd.concat(daily_parts, ignore_index=True), pd.DataFrame(event_parts, columns=["variant", "time", "date", "year", "afternoon", "initial_temp_C",
                "cooling_rate_C_per_h", "cooling_drop_C", "drying_rate_gkg_per_h",
                "outdoor_temp_C", "outdoor_w_gkg", "first_hour_AC_kWh"]),
            pd.concat(humidity_parts, ignore_index=True), pd.DataFrame(eligibility), threshold)


def weights_by_day(frame):
    return 1.0 / frame.groupby("date")["date"].transform("size").to_numpy()


def design(frame, features):
    x = frame[features].astype(float).copy()
    x.insert(0, "intercept", 1.0)
    return x


def fit_reference(train, features, target):
    x = design(train, features)
    if len(train) < len(x.columns) + 5 or np.linalg.matrix_rank(x) != len(x.columns):
        raise ValueError("Too few independent reference observations for this specification.")
    # Day balancing is a deliberate estimand choice, not inverse-variance precision weighting.
    return sm.WLS(train[target], x, weights=weights_by_day(train)).fit()


def temporal_cv(train, features, target):
    """Expanding 2018-only folds; all rows from a date stay in the same fold."""
    dates = np.array(sorted(train.date.unique()))
    initial = max(len(features) + 6, len(dates) // 2)
    folds = np.array_split(dates[initial:], 3)
    rows = []
    for fold_id, dates_test in enumerate(folds, 1):
        if not len(dates_test):
            continue
        reference = train[train.date < dates_test[0]]
        validation = train[train.date.isin(dates_test)]
        fitted = fit_reference(reference, features, target)
        p = fitted.predict(design(validation, features)).to_numpy()
        out = validation[["time", "date", target]].copy()
        out["prediction"], out["residual"], out["fold"] = p, validation[target].to_numpy() - p, fold_id
        out["train_last_date"] = reference.date.max()
        assert reference.date.max() < validation.date.min()
        rows.append(out)
    result = pd.concat(rows, ignore_index=True)
    w = weights_by_day(result)
    return {"MAE": float(np.average(result.residual.abs(), weights=w)),
            "RMSE": float(np.sqrt(np.average(result.residual ** 2, weights=w))),
            "bias": float(np.average(result.residual, weights=w)),
            "validation_rows": len(result), "validation_days": result.date.nunique()}, result


def support_mask(train, test, features):
    """Convex-hull membership within each discrete start-up/session class."""
    result = pd.Series(False, index=test.index)
    groups = [0, 1] if "afternoon" in features else [None]
    continuous = [f for f in features if f != "afternoon"]
    for group in groups:
        a = train if group is None else train[train.afternoon == group]
        b = test if group is None else test[test.afternoon == group]
        if b.empty or a.empty:
            continue
        if not continuous:
            result.loc[b.index] = True
            continue
        center = a[continuous].mean()
        scale = a[continuous].std()
        active = scale[scale > 1e-10].index.tolist()
        constants = [f for f in continuous if f not in active]
        constant_ok = pd.Series(True, index=b.index)
        for field in constants:
            constant_ok &= np.isclose(b[field], center[field], atol=1e-8)
        x = ((a[active] - center[active]) / scale[active]).to_numpy()
        y = ((b[active] - center[active]) / scale[active]).to_numpy()
        if len(active) == 0:
            inside = np.ones(len(b), dtype=bool)
        elif len(active) == 1:
            inside = (y[:, 0] >= x[:, 0].min() - 1e-9) & (y[:, 0] <= x[:, 0].max() + 1e-9)
        else:
            try:
                inside = Delaunay(x).find_simplex(y, tol=1e-9) >= 0
            except QhullError:
                # Never replace unsupported geometry with a weaker unlabelled rule.
                inside = np.zeros(len(b), dtype=bool)
        result.loc[b.index] = inside & constant_ok
    return result


def block_bootstrap(train, test, features, target, repetitions=2000, seed=4001):
    """Independent calendar-week resampling in each year; refit the 2018 model."""
    rng = np.random.default_rng(seed)
    train = train.copy().reset_index(drop=True)
    test = test.copy().reset_index(drop=True)
    if test.empty:
        return {"low": np.nan, "high": np.nan, "percent_low": np.nan, "percent_high": np.nan, "valid_replicates": 0}
    x, y, w = design(train, features).to_numpy(), train[target].to_numpy(), weights_by_day(train)
    z, v, q = design(test, features).to_numpy(), test[target].to_numpy(), weights_by_day(test)
    def blocks(frame):
        labels = frame.date.dt.to_period("W-SUN")
        return [np.flatnonzero(labels.eq(label).to_numpy()) for label in labels.unique()]
    a, b = blocks(train), blocks(test)
    values, percentages = [], []
    for _ in range(repetitions):
        ia = np.concatenate([a[k] for k in rng.integers(len(a), size=len(a))])
        ib = np.concatenate([b[k] for k in rng.integers(len(b), size=len(b))])
        xx = x[ia] * np.sqrt(w[ia])[:, None]
        if np.linalg.matrix_rank(xx) < x.shape[1]:
            continue
        beta = np.linalg.lstsq(xx, y[ia] * np.sqrt(w[ia]), rcond=None)[0]
        pred = z[ib] @ beta
        values.append(float(np.average(v[ib] - pred, weights=q[ib])))
        den = float(np.average(pred, weights=q[ib]))
        percentages.append(100 * values[-1] / den if den > 0 else np.nan)
    return {"low": float(np.quantile(values, .025)), "high": float(np.quantile(values, .975)),
            "percent_low": float(np.nanquantile(percentages, .025)), "percent_high": float(np.nanquantile(percentages, .975)),
            "valid_replicates": len(values), "train_weeks": len(a), "test_weeks": len(b)}


def fixed_window_interpolation_check(raw, clean, events):
    """Numerical slope sensitivity within the same windows; not a new cohort model."""
    rows = []
    for row in events[events.variant.eq("with_fills")].itertuples():
        pos = clean.index.get_loc(row.time)
        source = raw[audit.TEMP].iloc[pos:pos + 60]
        trusted = source.notna() & source.eq(clean[audit.TEMP].iloc[pos:pos + 60])
        positions = np.flatnonzero(trusted)
        if len(positions) < 48 or positions[-1] - positions[0] < 50:
            continue
        observed_rate = float(-np.polyfit(positions, source.iloc[positions], 1)[0] * 60)
        rows.append({"time": row.time, "year": row.year, "source_minutes": len(positions),
                     "cleaned_rate_C_per_h": row.cooling_rate_C_per_h,
                     "observed_points_rate_C_per_h": observed_rate,
                     "clean_minus_observed_points_C_per_h": row.cooling_rate_C_per_h - observed_rate})
    return pd.DataFrame(rows)


def specification_checks(daily, humidity):
    """Bounded descriptive checks; neither selects a model using 2019 outcomes."""
    by_hour = humidity.assign(hour=humidity.time.dt.hour).groupby(
        ["variant", "year", "hour"]
    ).indoor_w_gkg.agg(["size", "mean"]).reset_index()
    rows = []
    energy = daily[daily.eligible]
    alternatives = {name: ENERGY_CANDIDATES[name]
                    for name in ["temperature_activity", "enthalpy_activity"]}
    for variant in VARIANTS:
        train = energy[(energy.variant == variant) & (energy.year == 2018)]
        test = energy[(energy.variant == variant) & (energy.year == 2019)]
        common = pd.Series(True, index=test.index)
        for fields in alternatives.values():
            common &= support_mask(train, test, fields)
        evaluation = test[common]
        for name, fields in alternatives.items():
            fit = fit_reference(train, fields, "ac_kWh")
            prediction = fit.predict(design(evaluation, fields))
            actual, expected = evaluation.ac_kWh.mean(), prediction.mean()
            rows.append({"variant": variant, "specification": name,
                         "common_supported_days": len(evaluation),
                         "observed_mean_kWh": actual, "expected_mean_kWh": expected,
                         "residual_pct": 100 * (actual - expected) / expected})
    return pd.DataFrame(rows), by_hour


def run_models(daily, events, humidity, repetitions=2000):
    tables = {"energy": daily[daily.eligible].copy(), "cooling": events.copy(), "moisture": humidity.copy()}
    targets = {"energy": "ac_kWh", "cooling": "cooling_rate_C_per_h", "moisture": "indoor_w_gkg"}
    # Select the energy specification using 2018 with-fills data only, before 2019 scoring.
    candidates, cv_rows = [], []
    reference = tables["energy"].query("variant == 'with_fills' and year == 2018")
    for name, fields in ENERGY_CANDIDATES.items():
        scores, rows = temporal_cv(reference, fields, targets["energy"])
        candidates.append({"candidate": name, "predictors": ", ".join(fields), **scores})
        cv_rows.append(rows.assign(analysis="energy_candidate", candidate=name, variant="with_fills"))
    candidates = pd.DataFrame(candidates).sort_values(["MAE", "candidate"])
    winner = candidates[candidates.candidate.isin(["temperature_activity", "enthalpy_activity"])].iloc[0].candidate
    specs = {"energy": ENERGY_CANDIDATES[winner], "cooling": COOLING_FEATURES, "moisture": MOISTURE_FEATURES}
    summaries, predictions, coefficients, checks = [], [], [], []
    for analysis, data in tables.items():
        fields, target = specs[analysis], targets[analysis]
        for variant in VARIANTS:
            subset = data[data.variant == variant].copy()
            train, test = subset[subset.year == 2018].copy(), subset[subset.year == 2019].copy()
            train, test = train.sort_values("time"), test.sort_values("time")
            fitted = fit_reference(train, fields, target)
            cv, validation = temporal_cv(train, fields, target)
            cv_rows.append(validation.assign(analysis=analysis, variant=variant, candidate="selected"))
            test["prediction"] = fitted.predict(design(test, fields))
            test["residual"] = test[target] - test.prediction
            test["within_reference_support"] = support_mask(train, test, fields)
            if analysis == "energy":
                test["within_reference_support"] &= test.prediction.gt(0)
            test["analysis"], test["actual"] = analysis, test[target]
            test["cusum_observed_rows"] = test.residual.cumsum() if analysis == "energy" else np.nan
            predictions.append(test)
            for parameter, value in fitted.params.items():
                coefficients.append({"analysis": analysis, "variant": variant, "parameter": parameter,
                                     "value": value, "reference_rows": len(train), "reference_days": train.date.nunique()})
            supported = test[test.within_reference_support].copy()
            train_weeks = train.date.dt.to_period("W-SUN").nunique()
            test_weeks = supported.date.dt.to_period("W-SUN").nunique()
            reportable = supported.date.nunique() >= 10 and train_weeks >= 4 and test_weeks >= 4
            interval = (block_bootstrap(train, supported, fields, target, repetitions=repetitions)
                        if reportable else {"low": np.nan, "high": np.nan,
                                            "percent_low": np.nan, "percent_high": np.nan, "valid_replicates": 0})
            for sample_name, sample in [("all_eligible", test), ("within_reference_support", supported)]:
                w = weights_by_day(sample) if len(sample) else np.array([])
                actual = float(np.average(sample[target], weights=w)) if len(sample) else np.nan
                expected = float(np.average(sample.prediction, weights=w)) if len(sample) else np.nan
                summaries.append({"analysis": analysis, "variant": variant, "evaluation": sample_name,
                    "reference_rows": len(train), "reference_days": train.date.nunique(),
                    "evaluation_rows": len(sample), "evaluation_days": sample.date.nunique(),
                    "all_eligible_2019_rows": len(test), "unsupported_2019_rows": int((~test.within_reference_support).sum()),
                    "observed_mean": actual, "reference_expected_mean": expected,
                    "mean_residual": actual - expected if sample_name == "all_eligible" or reportable else np.nan,
                    "residual_pct": 100 * (actual - expected) / expected if expected > 0 and (sample_name == "all_eligible" or reportable) else np.nan,
                    "reportable": bool(reportable and sample_name == "within_reference_support"),
                    "assessment_status": ("supported descriptive comparison" if reportable else "insufficient supported days/weeks") if sample_name == "within_reference_support" else "diagnostic only; includes extrapolations",
                    "reference_weeks": train_weeks, "supported_evaluation_weeks": test_weeks,
                    "reference_CV_MAE": cv["MAE"], "reference_CV_RMSE": cv["RMSE"], "reference_CV_bias": cv["bias"],
                    "bootstrap_low": interval["low"] if sample_name == "within_reference_support" else np.nan,
                    "bootstrap_high": interval["high"] if sample_name == "within_reference_support" else np.nan,
                    "bootstrap_percent_low": interval["percent_low"] if sample_name == "within_reference_support" else np.nan,
                    "bootstrap_percent_high": interval["percent_high"] if sample_name == "within_reference_support" else np.nan,
                    "bootstrap_valid_replicates": interval["valid_replicates"] if sample_name == "within_reference_support" else 0,
                    "predictors": ", ".join(fields), "target": target})
            # The shared unfilled cohort must have identical inputs and outcomes in both variants.
        clean_data = data[data.variant == "with_fills"].set_index("time")
        observed_data = data[data.variant == "without_fills"].set_index("time")
        overlap = observed_data.index.intersection(clean_data.index)
        numeric = fields + [target]
        delta = (clean_data.loc[overlap, numeric] - observed_data.loc[overlap, numeric]).abs()
        checks.append({"analysis": analysis, "shared_rows": len(overlap),
                       "max_absolute_input_or_target_difference": float(delta.max().max())})
        assert np.allclose(delta, 0, atol=1e-9)
    return {"summary": pd.DataFrame(summaries), "predictions": pd.concat(predictions, ignore_index=True),
            "coefficients": pd.DataFrame(coefficients), "cross_validation": pd.concat(cv_rows, ignore_index=True),
            "energy_candidates": candidates, "shared_cohort_checks": pd.DataFrame(checks),
            "selected_energy_model": winner, "specifications": specs}
