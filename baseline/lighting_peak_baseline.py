"""Descriptive lighting demand baseline calculations."""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _shared import clean_data_directory, read_clean_file


POWER_COLUMN = re.compile(r"z(?P<zone>\d+)_(?:AC\d+|Light|Plug)\(kW\)")
LIGHT_COLUMN = re.compile(r"z(?P<zone>\d+)_Light\(kW\)")
LUX_COLUMN = re.compile(r"z(?P<zone>\d+)_S1\(lux\)")
MINUTES_PER_INTERVAL = 15
MINIMUM_COVERAGE = 0.8


def _quarter_hour_mean(values):
    grouped = values.resample("15min")
    count = grouped.count()
    mean = grouped.mean().where(count >= MINUTES_PER_INTERVAL * MINIMUM_COVERAGE)
    return mean, count / MINUTES_PER_INTERVAL


def _build_zone_intervals(clean_dir):
    records = []
    for path in sorted(clean_dir.glob("*Floor*.csv")):
        floor = int(path.stem[-1])
        data = read_clean_file(path, re.compile(
            r"z\d+_(?:AC\d+|Light|Plug)\(kW\)|z\d+_S1\(lux\)"
        ))
        if data is None:
            continue

        zones = sorted({
            int(match.group("zone"))
            for column in data.columns
            if (match := POWER_COLUMN.fullmatch(column))
        })
        for zone in zones:
            power_columns = [c for c in data if (m := POWER_COLUMN.fullmatch(c)) and int(m["zone"]) == zone]
            light_columns = [c for c in data if (m := LIGHT_COLUMN.fullmatch(c)) and int(m["zone"]) == zone]
            lux_columns = [c for c in data if (m := LUX_COLUMN.fullmatch(c)) and int(m["zone"]) == zone]

            total = data[power_columns].sum(axis=1, min_count=len(power_columns))
            light = data[light_columns].sum(axis=1, min_count=len(light_columns)) if light_columns else None
            lux = data[lux_columns].mean(axis=1, skipna=False) if lux_columns else None

            total_mean, total_coverage = _quarter_hour_mean(total)
            light_mean, light_coverage = _quarter_hour_mean(light) if light is not None else (None, None)
            lux_mean, lux_coverage = _quarter_hour_mean(lux) if lux is not None else (None, None)

            row = pd.DataFrame({
                "Date": total_mean.index,
                "floor": floor,
                "zone": zone,
                "total_kW": total_mean.to_numpy(),
                "total_coverage": total_coverage.to_numpy(),
                "light_kW": light_mean.to_numpy() if light_mean is not None else np.nan,
                "light_coverage": light_coverage.to_numpy() if light_coverage is not None else np.nan,
                "lux": lux_mean.to_numpy() if lux_mean is not None else np.nan,
                "lux_coverage": lux_coverage.to_numpy() if lux_coverage is not None else np.nan,
            })
            records.append(row)

    if not records:
        raise ValueError("No zone power columns were found in the cleaned files.")
    return pd.concat(records, ignore_index=True).sort_values(["floor", "zone", "Date"])


def _operating_hours(data):
    weekdays = data["Date"].dt.dayofweek < 5
    office_hours = data["Date"].dt.hour.between(8, 17)
    return data.loc[weekdays & office_hours].copy()


def _peak_summary(intervals):
    records = []
    for (floor, zone), group in intervals.groupby(["floor", "zone"], sort=True):
        april = _operating_hours(group)
        march = _operating_hours(group.loc[
            (group["Date"] >= "2019-03-06") & (group["Date"] < "2019-04-01")
        ])
        april = april.loc[
            (april["Date"] >= "2019-04-01") & (april["Date"] < "2019-05-01")
        ]

        valid_march = march["total_kW"].dropna()
        valid_april = april["total_kW"].dropna()
        threshold = valid_march.quantile(0.95) if not valid_march.empty else np.nan
        peak = april.loc[april["total_kW"].idxmax()] if not valid_april.empty else None

        records.append({
            "floor": floor,
            "zone": zone,
            "march_calibration_intervals": len(march),
            "march_valid_intervals": len(valid_march),
            "march_coverage_pct": 100 * len(valid_march) / len(march) if len(march) else np.nan,
            "march_p95_trigger_kW": threshold,
            "april_evaluation_intervals": len(april),
            "april_valid_intervals": len(valid_april),
            "april_coverage_pct": 100 * len(valid_april) / len(april) if len(april) else np.nan,
            "april_peak_time": peak["Date"] if peak is not None else pd.NaT,
            "april_peak_total_kW": peak["total_kW"] if peak is not None else np.nan,
            "lighting_kW_at_peak": peak["light_kW"] if peak is not None else np.nan,
            "lighting_share_at_peak_pct": (
                100 * peak["light_kW"] / peak["total_kW"]
                if peak is not None and pd.notna(peak["light_kW"]) and peak["total_kW"] > 0
                else np.nan
            ),
            "ambient_lux_at_peak": peak["lux"] if peak is not None else np.nan,
            "april_max_ambient_lux": april["lux"].max(),
            "april_valid_lux_intervals": int(april["lux"].notna().sum()),
            "april_lux_coverage_pct": 100 * april["lux"].notna().mean() if len(april) else np.nan,
            "april_intervals_above_march_p95": int((valid_april > threshold).sum())
            if pd.notna(threshold) else 0,
        })
    return pd.DataFrame(records)


def _lux_sensitivity(intervals):
    targets = [100, 150, 200, 300, 500]
    rows = []
    april = _operating_hours(intervals)
    april = april.loc[
        (april["Date"] >= "2019-04-01") & (april["Date"] < "2019-05-01")
    ]
    for (floor, zone), group in april.groupby(["floor", "zone"], sort=True):
        lux = group["lux"].dropna()
        for target in targets:
            rows.append({
                "floor": floor,
                "zone": zone,
                "illustrative_lux_target": target,
                "valid_lux_intervals": len(lux),
                "intervals_at_or_above_target": int((lux >= target).sum()),
                "share_at_or_above_target_pct": 100 * (lux >= target).mean()
                if len(lux) else np.nan,
            })
    return pd.DataFrame(rows)


def run_lighting_baseline():
    clean_dir = clean_data_directory()
    output_dir = Path(__file__).resolve().parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    intervals = _build_zone_intervals(clean_dir)
    summary = _peak_summary(intervals)
    sensitivity = _lux_sensitivity(intervals)
    floor2 = summary.loc[summary["floor"] == 2].copy()

    summary.to_csv(output_dir / "lighting_zone_april_baseline.csv", index=False)
    floor2.to_csv(output_dir / "lighting_floor2_april_baseline.csv", index=False)
    sensitivity.to_csv(output_dir / "lighting_lux_sensitivity.csv", index=False)

    plot = summary.sort_values(["floor", "zone"])
    labels = [f"F{row.floor}-Z{row.zone}" for row in plot.itertuples()]
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.bar(labels, plot["april_peak_total_kW"], color="#2a78d6")
    ax.set(title="April 2019 weekday daytime zone peaks", ylabel="Peak zone demand (kW)")
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()
    fig.savefig(output_dir / "lighting_zone_april_peaks.png", dpi=150)
    plt.show()

    ranked = summary.sort_values("april_peak_total_kW", ascending=True).copy()
    labels = [f"F{row.floor}-Z{row.zone}" for row in ranked.itertuples()]
    other_load = (ranked["april_peak_total_kW"] - ranked["lighting_kW_at_peak"]).clip(lower=0)
    colors = np.where(ranked["april_coverage_pct"] >= 80, "#2a78d6", "#a3a29c")
    fig, axes = plt.subplots(
        1, 2, figsize=(15, max(7, len(ranked) * 0.27)),
        gridspec_kw={"width_ratios": [1.5, 1]},
    )
    axes[0].barh(labels, other_load, color=colors, label="AC + plug at zone peak")
    axes[0].barh(
        labels,
        ranked["lighting_kW_at_peak"].fillna(0),
        left=other_load,
        color="#eb6834",
        label="Lighting at zone peak",
    )
    axes[0].set_xlabel("Zone demand at its April peak (kW)")
    axes[0].set_title("Peak demand composition by zone")
    axes[0].legend(loc="lower right")
    axes[0].grid(axis="y", visible=False)

    lux = summary.loc[summary["april_valid_lux_intervals"] > 0].sort_values(
        "april_max_ambient_lux", ascending=True
    )
    lux_labels = [f"F{row.floor}-Z{row.zone}" for row in lux.itertuples()]
    axes[1].barh(lux_labels, lux["april_max_ambient_lux"], color="#1baf7a")
    axes[1].axvline(
        500, color="#d03b3b", linestyle="--", linewidth=1.5,
        label="Illustrative 500 lux target",
    )
    axes[1].set_xlabel("Maximum April ambient lux")
    axes[1].set_title("Available ambient-light sensors")
    axes[1].legend(loc="lower right")
    axes[1].grid(axis="y", visible=False)
    fig.suptitle("April weekday daytime baseline; gray demand bars have <80% coverage")
    fig.tight_layout()
    fig.savefig(output_dir / "lighting_peak_and_lux_baseline.png", dpi=150)
    plt.show()

    return {
        "zone_summary": summary,
        "floor2_deep_dive": floor2,
        "lux_sensitivity": sensitivity,
        "output_directory": output_dir,
    }
