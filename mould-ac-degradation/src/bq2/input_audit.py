"""Reproducible F3-Z1 input checks. No models, data cleaning or helper changes."""

from pathlib import Path
import hashlib
import itertools
import subprocess

import numpy as np
import pandas as pd


START = "2018-07-01 00:00"
END = "2019-12-31 23:59"
AC = [f"z1_AC{i}(kW)" for i in range(1, 5)]
TEMP, RH, PLUG = "z1_S1(degC)", "z1_S1(RH%)", "z1_Plug(kW)"
CHANNELS = AC + [PLUG, TEMP, RH]


def load_inputs(root):
    """Read only needed columns; preserve source values and complete denominators."""
    full_index = pd.date_range(START, END, freq="min", name="Date")
    frames, timeline, sources = {}, [], []
    for kind, folder in [("raw", "data"), ("clean", "data-cleaning/outputs/clean")]:
        parts = []
        for year in (2018, 2019):
            path = root / folder / f"{year}Floor3.csv"
            sources.append(path)
            table = pd.read_csv(path, usecols=["Date"] + CHANNELS)
            dates = pd.to_datetime(table.pop("Date"), errors="coerce")
            timeline.append({
                "source": str(path.relative_to(root)), "rows": len(table),
                "invalid_timestamps": int(dates.isna().sum()),
                "duplicate_timestamps": int(dates.duplicated().sum()),
                "sorted": bool(dates.is_monotonic_increasing),
                "first": str(dates.min()), "last": str(dates.max()),
                "off_minute_grid": int((dates.notna() & dates.ne(dates.dt.floor("min"))).sum()),
            })
            if dates.isna().any() or dates.duplicated().any():
                raise ValueError(f"Ambiguous timestamps in {path.name}; resolve before audit alignment.")
            table.index = pd.DatetimeIndex(dates, name="Date")
            parts.append(table)
        joined = pd.concat(parts)
        if not joined.index.equals(full_index):
            raise ValueError(f"{kind} timestamps differ from the expected complete minute grid.")
        frames[kind] = joined

    quality_path = root / "data-cleaning/outputs/analytics/data_quality.csv"
    removed_path = root / "data-cleaning/outputs/analytics/removed_readings.csv"
    hourly_path = root / "data-cleaning/outputs/analytics/zone_hourly.csv"
    quality = pd.read_csv(quality_path).query("floor == 3 and zone == 1").copy()
    removed = pd.read_csv(removed_path, parse_dates=["Date"])
    removed = removed[(removed["floor"] == 3) & removed["column"].isin(CHANNELS)].copy()
    hourly = pd.read_csv(hourly_path, parse_dates=["Date"])
    hourly = hourly[(hourly["floor"] == 3) & (hourly["zone"] == 1)].set_index("Date").sort_index()
    if hourly.index.has_duplicates:
        raise ValueError("Duplicate F3-Z1 keys in the hourly export.")
    expected_hours = pd.date_range(START, "2019-12-31 23:00", freq="h", name="Date")
    if not hourly.index.equals(expected_hours):
        raise ValueError("F3-Z1 hourly export has an incomplete timestamp grid.")
    sources += [quality_path, removed_path, hourly_path,
                root / "baseline/data/bangkok_era5_hourly_2018-2019.csv",
                root / "data-cleaning/main.ipynb", root / "baseline/humidity_risk_baseline.py",
                root / "mould-ac-degradation/bq2_utils.ipynb"]
    manifest = []
    for path in sources:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
                         "sha256": digest.hexdigest()})
    return frames["raw"], frames["clean"], hourly, quality, removed, pd.DataFrame(timeline), manifest


def valid_channel(frame, column):
    values = frame[column]
    mask = pd.Series(np.isfinite(values), index=frame.index)
    if column == TEMP:
        return mask & values.between(15, 40)
    if column == RH:
        return mask & values.between(0, 100)
    return mask & values.ge(0)


def availability(frame):
    valid = pd.DataFrame({c: valid_channel(frame, c) for c in CHANNELS})
    masks = pd.DataFrame(index=frame.index)
    masks["ac"] = valid[AC].all(axis=1)
    masks["environment"] = valid[[TEMP, RH]].all(axis=1)
    masks["ac_environment"] = masks["ac"] & masks["environment"]
    masks["ac_plug"] = masks["ac"] & valid[PLUG]
    return masks


def channel_profile(raw, clean, quality):
    rows = []
    for column in CHANNELS:
        rv, cv = valid_channel(raw, column), valid_channel(clean, column)
        changed = raw[column].notna() & clean[column].notna() & raw[column].ne(clean[column])
        log = quality.set_index("column").loc[column]
        finite = clean.loc[cv, column]
        rows.append({
            "column": column, "expected_minutes": len(clean),
            "raw_valid_minutes": int(rv.sum()), "clean_valid_minutes": int(cv.sum()),
            "raw_coverage_pct": 100 * rv.mean(), "clean_coverage_pct": 100 * cv.mean(),
            "raw_missing_to_filled_minutes": int((raw[column].isna() & clean[column].notna()).sum()),
            "raw_present_changed_minutes": int(changed.sum()),
            "raw_present_removed_minutes": int((raw[column].notna() & clean[column].isna()).sum()),
            "clean_invalid_nonmissing": int((clean[column].notna() & ~cv).sum()),
            "min": float(finite.min()), "p01": float(finite.quantile(.01)),
            "median": float(finite.median()), "p99": float(finite.quantile(.99)),
            "max": float(finite.max()), "zero_share_of_valid_pct": 100 * finite.eq(0).mean(),
            "logged_filled_minutes": int(log["short_gap_min_filled"]),
            "logged_spikes_removed": int(log["spikes_removed"]),
            "quality_log_missing_pct_agrees": bool(abs(100 * clean[column].isna().mean() - log["final_missing_pct"]) <= .011),
            "fill_and_replacement_count_agrees": bool(int((raw[column].isna() & clean[column].notna()).sum()) + int(changed.sum()) == int(log["short_gap_min_filled"])),
        })
    return pd.DataFrame(rows)


def true_runs(mask):
    """Inclusive starts/ends; length counts expected contiguous one-minute slots."""
    values = mask.to_numpy(dtype=bool)
    edges = np.diff(np.r_[False, values, False].astype(np.int8))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return pd.DataFrame({"start": mask.index[starts], "end": mask.index[ends - 1],
                         "minutes": ends - starts, "days": (ends - starts) / 1440})


def coverage_tables(raw, clean, hourly):
    masks = {"raw": availability(raw), "clean": availability(clean)}
    monthly = pd.DataFrame(index=clean.resample("MS").size().index)
    monthly["expected_minutes"] = clean.resample("MS").size()
    for source, table in masks.items():
        for field in table:
            monthly[f"{source}_{field}_valid_minutes"] = table[field].resample("MS").sum()
            monthly[f"{source}_{field}_pct"] = table[field].resample("MS").mean() * 100
    day_types = hourly["day_type"].groupby(hourly.index.normalize()).agg(["first", "nunique"])
    if day_types["nunique"].ne(1).any():
        raise ValueError("Inconsistent day_type within a day.")
    daily = pd.DataFrame(index=clean.resample("D").size().index)
    daily["day_type"] = day_types["first"]
    for source, table in masks.items():
        for field in table:
            daily[f"{source}_{field}_pct"] = table[field].resample("D").mean() * 100
    for field in ["ac_plug", "environment", "ac_environment"]:
        passes = daily["day_type"].eq("working day") & daily[f"clean_{field}_pct"].ge(95)
        monthly[f"working_days_{field}_95pct"] = passes.resample("MS").sum()
    monthly["working_days"] = daily["day_type"].eq("working day").resample("MS").sum()
    sensitivity = []
    for period, lo, hi in [("2018 reference candidate", "2018-07-01", "2018-12-31"),
                           ("2019 full year", "2019-01-01", "2019-12-31"),
                           ("Jul-Aug 2018", "2018-07-01", "2018-08-31"),
                           ("Jul-Aug 2019", "2019-07-01", "2019-08-31")]:
        sample = daily.loc[lo:hi]
        working = sample["day_type"].eq("working day")
        for threshold in [90, 95, 100]:
            sensitivity.append({"period": period, "minimum_daily_coverage_pct": threshold,
                "working_days": int(working.sum()),
                "clean_energy_days": int((working & sample["clean_ac_plug_pct"].ge(threshold)).sum()),
                "raw_energy_days": int((working & sample["raw_ac_plug_pct"].ge(threshold)).sum()),
                "clean_joint_days": int((working & sample["clean_ac_environment_pct"].ge(threshold)).sum()),
                "raw_joint_days": int((working & sample["raw_ac_environment_pct"].ge(threshold)).sum())})
    gaps = []
    for source, table in masks.items():
        for field in ["ac", "environment"]:
            runs = true_runs(~table[field])
            runs = runs[runs["minutes"] > 15].copy()
            runs.insert(0, "stream", field)
            runs.insert(0, "source", source)
            gaps.append(runs)
    return monthly, daily, pd.DataFrame(sensitivity), pd.concat(gaps, ignore_index=True), masks


def reconcile_hourly(clean, hourly):
    minute = pd.DataFrame(index=clean.index)
    minute["ac_kW"] = clean[AC].sum(axis=1, min_count=len(AC))
    minute["plug_kW"] = clean[PLUG]
    minute["temp_C"] = clean[TEMP]
    minute["rh_pct"] = clean[RH]
    expected = minute.resample("h").mean().where(minute.notna().resample("h").sum() >= 48).round(2)
    rows = []
    for field in expected:
        difference = (expected[field] - hourly[field]).abs()
        rows.append({"field": field, "hours": len(expected),
            "availability_mismatches": int(expected[field].isna().ne(hourly[field].isna()).sum()),
            "value_mismatches_above_0_01": int(difference.gt(.0100001).sum()),
            "maximum_absolute_difference": float(difference.max())})
    return pd.DataFrame(rows)


def flatline_profile(raw, clean):
    summaries, examples = [], []
    for source, frame in [("raw", raw), ("clean", clean)]:
        for fields, label in [([TEMP], "temperature"), ([RH], "humidity"), ([TEMP, RH], "both sensors")]:
            valid = frame[fields].notna().all(axis=1)
            same = frame[fields].eq(frame[fields].shift()).all(axis=1) & valid & valid.shift(fill_value=False)
            groups = (~same).cumsum()
            run = pd.DataFrame({"time": frame.index[valid], "group": groups[valid].to_numpy()})
            runs = run.groupby("group")["time"].agg(start="first", end="last", minutes="size")
            summaries.append({"source": source, "stream": label, "longest_constant_minutes": int(runs["minutes"].max()),
                "constant_runs_at_least_60min": int(runs["minutes"].ge(60).sum()),
                "constant_runs_at_least_360min": int(runs["minutes"].ge(360).sum())})
            example = runs.nlargest(3, "minutes").reset_index(drop=True)
            example.insert(0, "stream", label)
            example.insert(0, "source", source)
            examples.append(example)
    return pd.DataFrame(summaries), pd.concat(examples, ignore_index=True)


def event_audit(raw, clean, masks, detect_ac_events, ac_on_threshold):
    ac_kw = clean[AC].sum(axis=1, min_count=len(AC))
    threshold = float(ac_on_threshold(ac_kw))
    existing = detect_ac_events(ac_kw).copy()
    state = ac_kw.gt(threshold).to_numpy()
    states = np.where(masks["clean"]["ac"], state.astype(int), -1)
    starts = np.r_[0, np.flatnonzero(states[1:] != states[:-1]) + 1]
    ends = np.r_[starts[1:], len(states)]
    strict = []
    for j in range(1, len(starts)):
        a, b = starts[j - 1], starts[j]
        if states[a] >= 0 and states[b] >= 0 and b - a >= 30 and ends[j] - b >= 30:
            strict.append((clean.index[b], "start" if states[b] == 1 else "stop"))
    strict_set = set(strict)
    helper_set = set(zip(existing["time"], existing["event"]))
    rows = []
    for row in existing.itertuples():
        pos = clean.index.get_loc(row.time)
        wanted = row.event == "start"
        bounded30 = pos >= 30 and pos + 30 <= len(clean)
        bounded60 = pos >= 30 and pos + 60 <= len(clean)
        pre = slice(max(0, pos - 30), pos)
        post30, post60 = slice(pos, pos + 30), slice(pos, pos + 60)
        power30 = bounded30 and masks["clean"]["ac"].iloc[pre].all() and masks["clean"]["ac"].iloc[post30].all()
        state30 = power30 and (state[pre] == (not wanted)).all() and (state[post30] == wanted).all()
        power60 = bounded60 and masks["clean"]["ac"].iloc[post60].all()
        same_state60 = power60 and (state[post60] == wanted).all()
        clean_env60 = bounded60 and masks["clean"]["environment"].iloc[post60].all()
        clean_ok = state30 and same_state60 and clean_env60
        raw_ok = clean_ok and masks["raw"]["ac"].iloc[pre].all() and masks["raw"]["ac_environment"].iloc[post60].all()
        rows.append({"time": row.time, "event": row.event, "threshold_kW": threshold,
            "continuous_state_30min": bool(state30), "same_state_60min_after": bool(same_state60),
            "paired_environment_60min_after": bool(clean_env60),
            "eligible_clean_60min": bool(clean_ok), "eligible_raw_observed_60min": bool(raw_ok),
            "strict_detector_contains_event": (row.time, row.event) in strict_set})
    events = pd.DataFrame(rows)
    summary = []
    for kind in ["start", "stop"]:
        part = events[events["event"] == kind]
        summary.append({"event": kind, "helper_candidates": len(part),
            "continuous_state_30min": int(part["continuous_state_30min"].sum()),
            "eligible_clean_60min": int(part["eligible_clean_60min"].sum()),
            "eligible_raw_observed_60min": int(part["eligible_raw_observed_60min"].sum()),
            "helper_events_not_strict": sum(e == kind for t, e in helper_set - strict_set),
            "strict_events_missing_from_helper": sum(e == kind for t, e in strict_set - helper_set)})
    return events, pd.DataFrame(summary), threshold


def meter_pair_checks(clean):
    rows = []
    for a, b in itertools.combinations(AC, 2):
        valid = clean[[a, b]].notna().all(axis=1)
        active = valid & clean[[a, b]].max(axis=1).gt(.5)
        rows.append({"meter_a": a, "meter_b": b, "joint_minutes_either_above_0_5kw": int(active.sum()),
                     "equal_values_pct_in_active_sample": 100 * clean.loc[active, a].eq(clean.loc[active, b]).mean()})
    return pd.DataFrame(rows)


def provenance(root, manifest):
    return {"audit_as_of": "2026-10-30", "floor": 3, "zone": 1,
            "scope": "Input audit only; no models or source corrections",
            "source_commit_at_run": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "expected_minutes": len(pd.date_range(START, END, freq="min")),
            "period_start": START, "period_end": END,
            "timezone_note": "Building CSVs have naive timestamps. ERA5 loader requests Asia/Bangkok. Matching keys do not independently confirm clock alignment.",
            "range_checks": {"temperature_C": [15, 40], "rh_pct": [0, 100], "power_kW": ">=0; no rated-capacity upper bound available"},
            "candidate_daily_gate": "95% of all 1440 expected minutes; sensitivity at 90/95/100%; working day labels are inferred activity, not measured occupancy",
            "event_gate": "30 contiguous power minutes before/after transition, unchanged power state for 60 minutes after, paired temperature/RH for those 60 minutes; raw variant requires source observations rather than filled readings",
            "input_manifest": manifest}
