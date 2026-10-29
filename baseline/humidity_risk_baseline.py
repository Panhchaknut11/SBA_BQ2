"""Descriptive humidity and AC screening calculations with Bangkok weather."""

import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _shared import clean_data_directory, read_clean_file


SENSOR_COLUMN = re.compile(
    r"z(?P<zone>\d+)_S1\((?P<unit>degC|RH%)\)"
)
AC_COLUMN = re.compile(r"z(?P<zone>\d+)_AC\d+\(kW\)")
PROPOSAL_FLOORS = range(3, 8)
PROPOSAL_ZONES = {1, 2, 4, 5}
HIGH_RH_THRESHOLD = 60.0
LONG_EXPOSURE_MINUTES = 6 * 60
MINUTE_COVERAGE = 0.8
WEATHER_API_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_START = "2018-07-01"
WEATHER_END = "2019-12-31"
WEATHER_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
)
WEATHER_COLUMNS = {
    "temperature_2m": "outdoor_temp_C",
    "relative_humidity_2m": "outdoor_rh_pct",
    "dew_point_2m": "outdoor_dew_point_C",
    "precipitation": "precipitation_mm",
}


def load_bangkok_era5_weather(cache_path, refresh=False):
    """Load cached or fetch hourly Bangkok ERA5 weather via the Open-Meteo Archive API."""
    cache_path = Path(cache_path)
    if cache_path.is_file() and not refresh:
        weather = pd.read_csv(cache_path, parse_dates=["Date"])
    else:
        params = {
            "latitude": 13.7563,
            "longitude": 100.5018,
            "start_date": WEATHER_START,
            "end_date": WEATHER_END,
            "hourly": ",".join(WEATHER_VARIABLES),
            "timezone": "Asia/Bangkok",
            "models": "era5",
        }
        request_url = f"{WEATHER_API_URL}?{urlencode(params)}"
        try:
            with urlopen(request_url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(
                "Could not retrieve Bangkok ERA5 weather from the Open-Meteo "
                "Archive API. Check the internet connection and retry."
            ) from error
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Open-Meteo returned a response that was not valid JSON."
            ) from error

        if "error" in payload:
            raise RuntimeError(
                f"Open-Meteo API error: {payload.get('reason', payload['error'])}"
            )
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict) or "time" not in hourly:
            raise ValueError("Open-Meteo response has no hourly time series.")
        expected_variables = set(WEATHER_VARIABLES)
        if not expected_variables.issubset(hourly):
            missing = sorted(expected_variables.difference(hourly))
            raise ValueError(f"Open-Meteo response is missing hourly variables: {missing}")

        weather = pd.DataFrame({"Date": hourly["time"]})
        for source, target in WEATHER_COLUMNS.items():
            weather[target] = hourly[source]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        weather.to_csv(cache_path, index=False)
        print(f"Downloaded and cached Open-Meteo ERA5 weather: {cache_path}")

    required = {"Date", *WEATHER_COLUMNS.values()}
    missing_columns = required.difference(weather.columns)
    if missing_columns:
        raise ValueError(f"Weather cache is missing columns: {sorted(missing_columns)}")
    weather = weather.loc[:, ["Date", *WEATHER_COLUMNS.values()]].copy()
    weather["Date"] = pd.to_datetime(weather["Date"], errors="raise")
    if weather["Date"].duplicated().any():
        raise ValueError("Weather series contains duplicate hourly timestamps.")
    weather = weather.set_index("Date").sort_index()
    expected_index = pd.date_range(
        WEATHER_START, f"{WEATHER_END} 23:00", freq="h", name="Date"
    )
    if not weather.index.equals(expected_index):
        raise ValueError(
            "Weather series does not cover every expected hourly timestamp from "
            f"{WEATHER_START} to {WEATHER_END}. Remove the cache and rerun to "
            "download it again."
        )
    return weather


def _zone_features(data, floor, zone):
    ac_columns = [
        column for column in data
        if (match := AC_COLUMN.fullmatch(column)) and int(match["zone"]) == zone
    ]
    temp_columns = [
        column for column in data
        if (match := SENSOR_COLUMN.fullmatch(column))
        and int(match["zone"]) == zone and match["unit"] == "degC"
    ]
    rh_columns = [
        column for column in data
        if (match := SENSOR_COLUMN.fullmatch(column))
        and int(match["zone"]) == zone and match["unit"] == "RH%"
    ]
    if not ac_columns or not temp_columns or not rh_columns:
        return None

    return pd.DataFrame({
        "floor": floor,
        "zone": zone,
        "ac_kW": data[ac_columns].sum(axis=1, min_count=len(ac_columns)),
        "temp_C": data[temp_columns].mean(axis=1, skipna=False),
        "rh_pct": data[rh_columns].mean(axis=1, skipna=False),
    }, index=data.index)


def _episode_table(rh, threshold):
    high = rh.gt(threshold).fillna(False)
    if not high.any():
        return pd.DataFrame(columns=["start", "minutes"])
    timestamp_gap = rh.index.to_series().diff().ne(pd.Timedelta(minutes=1))
    groups = ((~high) | timestamp_gap).cumsum()
    events = high.loc[high].groupby(groups.loc[high]).agg(["size"])
    starts = high.loc[high].groupby(groups.loc[high]).apply(lambda values: values.index[0])
    return pd.DataFrame({
        "start": starts.to_numpy(),
        "minutes": events["size"].to_numpy(),
    })


def _episode_statistics(rh, threshold):
    events = _episode_table(rh, threshold)
    if events.empty:
        return 0, 0, 0
    return (
        len(events),
        int(events["minutes"].max()),
        int((events["minutes"] >= LONG_EXPOSURE_MINUTES).sum()),
    )


def _monthly_summary(features, hourly):
    rows = []
    for (floor, zone), group in features.groupby(["floor", "zone"], sort=True):
        group = group.sort_index()
        episodes = _episode_table(group["rh_pct"], HIGH_RH_THRESHOLD)
        for (year, month), monthly in group.groupby(
            [group.index.year, group.index.month], sort=True
        ):
            monthly_hourly = hourly.loc[
                (hourly["floor"] == floor)
                & (hourly["zone"] == zone)
                & (hourly["year"] == year)
                & (hourly["month"] == month)
            ]
            rh = monthly["rh_pct"]
            valid_rh = rh.dropna()
            month_episodes = episodes.loc[
                (episodes["start"].map(lambda date: date.year) == year)
                & (episodes["start"].map(lambda date: date.month) == month)
            ]
            episode_count = len(month_episodes)
            longest = int(month_episodes["minutes"].max()) if episode_count else 0
            long_episodes = int(
                (month_episodes["minutes"] >= LONG_EXPOSURE_MINUTES).sum()
            )
            high_mask = rh > HIGH_RH_THRESHOLD
            valid_ac = monthly["ac_kW"].dropna()
            rows.append({
                "floor": floor,
                "zone": zone,
                "year": year,
                "month": month,
                "valid_rh_minutes": len(valid_rh),
                "rh_coverage_pct": 100 * rh.notna().mean(),
                "mean_rh_pct": valid_rh.mean() if len(valid_rh) else np.nan,
                "p95_rh_pct": valid_rh.quantile(0.95) if len(valid_rh) else np.nan,
                "minutes_rh_above_60": int(high_mask.sum()),
                "high_rh_share_of_valid_pct": 100 * high_mask.sum() / len(valid_rh)
                if len(valid_rh) else np.nan,
                "high_rh_episodes": episode_count,
                "longest_high_rh_episode_minutes": longest,
                "episodes_at_least_6h": long_episodes,
                "mean_ac_kW": valid_ac.mean() if len(valid_ac) else np.nan,
                "mean_ac_kW_rh_above_60": monthly.loc[high_mask, "ac_kW"].mean(),
                "mean_temp_C": monthly["temp_C"].mean(),
                "mean_outdoor_temp_C": monthly_hourly["outdoor_temp_C"].mean(),
                "mean_outdoor_rh_pct": monthly_hourly["outdoor_rh_pct"].mean(),
                "mean_outdoor_dew_point_C": monthly_hourly["outdoor_dew_point_C"].mean(),
                "total_precipitation_mm": monthly_hourly["precipitation_mm"].sum(min_count=1),
                "mean_ac_kW_per_cooling_degree": monthly_hourly[
                    "ac_kw_per_cooling_degree"
                ].mean(),
            })
    return pd.DataFrame(rows)


def _hourly_summary(features):
    hourly = []
    for (floor, zone), group in features.groupby(["floor", "zone"], sort=True):
        values = group[["ac_kW", "temp_C", "rh_pct"]].resample("h").mean()
        counts = group[["ac_kW", "temp_C", "rh_pct"]].resample("h").count()
        values = values.where(counts >= 60 * MINUTE_COVERAGE)
        values["floor"] = floor
        values["zone"] = zone
        hourly.append(values.reset_index(names="Date"))
    if not hourly:
        return pd.DataFrame()
    result = pd.concat(hourly, ignore_index=True)
    result["hour"] = result["Date"].dt.hour
    result["year"] = result["Date"].dt.year
    result["month"] = result["Date"].dt.month
    result["weekday"] = result["Date"].dt.dayofweek < 5
    result["assumed_occupied"] = result["weekday"] & result["hour"].between(8, 17)
    return result


def _year_comparison(monthly):
    overlap = monthly.loc[monthly["month"].between(7, 12)]
    averages = overlap.groupby(["floor", "zone", "month", "year"], as_index=False).agg(
        mean_ac_kW=("mean_ac_kW", "mean"),
        mean_rh_pct=("mean_rh_pct", "mean"),
        high_rh_share_of_valid_pct=("high_rh_share_of_valid_pct", "mean"),
        mean_outdoor_temp_C=("mean_outdoor_temp_C", "mean"),
        mean_outdoor_rh_pct=("mean_outdoor_rh_pct", "mean"),
        mean_outdoor_dew_point_C=("mean_outdoor_dew_point_C", "mean"),
        total_precipitation_mm=("total_precipitation_mm", "sum"),
        mean_ac_kW_per_cooling_degree=("mean_ac_kW_per_cooling_degree", "mean"),
    )
    wide = averages.pivot(
        index=["floor", "zone", "month"], columns="year",
        values=["mean_ac_kW", "mean_rh_pct", "high_rh_share_of_valid_pct"],
    )
    wide.columns = [f"{metric}_{year}" for metric, year in wide.columns]
    wide = wide.reset_index()
    for metric in (
        "mean_ac_kW",
        "mean_rh_pct",
        "high_rh_share_of_valid_pct",
        "mean_outdoor_temp_C",
        "mean_outdoor_rh_pct",
        "mean_outdoor_dew_point_C",
        "total_precipitation_mm",
        "mean_ac_kW_per_cooling_degree",
    ):
        col_2018, col_2019 = f"{metric}_2018", f"{metric}_2019"
        if col_2018 in wide and col_2019 in wide:
            wide[f"{metric}_2019_minus_2018"] = wide[col_2019] - wide[col_2018]
    return wide


def _monthly_weather(weather):
    monthly = weather.resample("MS").agg(
        mean_outdoor_temp_C=("outdoor_temp_C", "mean"),
        mean_outdoor_rh_pct=("outdoor_rh_pct", "mean"),
        mean_outdoor_dew_point_C=("outdoor_dew_point_C", "mean"),
        total_precipitation_mm=("precipitation_mm", "sum"),
        valid_weather_hours=("outdoor_temp_C", "count"),
    )
    monthly.index.name = "month_start"
    return monthly.reset_index()


def _attach_weather(hourly, weather):
    weather_hourly = weather.copy()
    if hourly.empty:
        return hourly
    result = hourly.merge(
        weather_hourly.reset_index(), on="Date", how="left", validate="many_to_one"
    )
    temperature_difference = (
        result["outdoor_temp_C"] - result["temp_C"]
    ).where(lambda values: values > 0)
    result["cooling_degree_difference_C"] = temperature_difference
    result["ac_kw_per_cooling_degree"] = (
        result["ac_kW"] / temperature_difference
    ).where(temperature_difference > 0)
    return result


def _schedule_summary(hourly):
    if hourly.empty:
        return pd.DataFrame()
    subset = hourly.loc[hourly["assumed_occupied"]]
    return subset.groupby(["floor", "zone", "hour"], as_index=False).agg(
        mean_rh_pct=("rh_pct", "mean"),
        mean_ac_kW=("ac_kW", "mean"),
        mean_outdoor_temp_C=("outdoor_temp_C", "mean"),
        mean_outdoor_rh_pct=("outdoor_rh_pct", "mean"),
        mean_outdoor_dew_point_C=("outdoor_dew_point_C", "mean"),
        mean_precipitation_mm=("precipitation_mm", "mean"),
        mean_ac_kw_per_cooling_degree=("ac_kw_per_cooling_degree", "mean"),
        valid_hours=("rh_pct", "count"),
    )


def run_humidity_baseline(weather):
    clean_dir = clean_data_directory()
    output_dir = Path(__file__).resolve().parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    features_by_zone = []
    for floor in PROPOSAL_FLOORS:
        yearly = []
        for year in (2018, 2019):
            path = clean_dir / f"{year}Floor{floor}.csv"
            columns_pattern = re.compile(
                r"z\d+_S1\((?:degC|RH%)\)|z\d+_AC\d+\(kW\)"
            )
            frame = read_clean_file(path, columns_pattern)
            if frame is not None:
                yearly.append(frame)
        if not yearly:
            continue
        data = pd.concat(yearly).sort_index()
        if data.index.has_duplicates:
            raise ValueError(f"Cleaned files for floor {floor} have duplicate timestamps.")

        present_zones = {
            int(match.group("zone"))
            for column in data.columns
            if (match := SENSOR_COLUMN.fullmatch(column))
        }
        for zone in sorted(present_zones & PROPOSAL_ZONES):
            features = _zone_features(data, floor, zone)
            if features is not None:
                features_by_zone.append(features)

    if not features_by_zone:
        raise ValueError(
            "No complete temperature, humidity, and AC zone series were found "
            "for proposal floors 3-7 and zones 1, 2, 4, and 5."
        )

    features = pd.concat(features_by_zone).sort_index()
    hourly = _attach_weather(_hourly_summary(features), weather)
    monthly = _monthly_summary(features, hourly)
    year_comparison = _year_comparison(monthly)
    schedule = _schedule_summary(hourly)

    sensitivity_rows = []
    for threshold in (60.0, 65.0, 70.0):
        for (floor, zone), group in features.groupby(["floor", "zone"], sort=True):
            valid = group["rh_pct"].notna()
            count, longest, long_episodes = _episode_statistics(group["rh_pct"], threshold)
            sensitivity_rows.append({
                "floor": floor,
                "zone": zone,
                "rh_threshold_pct": threshold,
                "valid_minutes": int(valid.sum()),
                "minutes_above_threshold": int(group["rh_pct"].gt(threshold).sum()),
                "share_of_valid_minutes_pct": 100 * group["rh_pct"].gt(threshold).sum() / valid.sum()
                if valid.sum() else np.nan,
                "episodes": count,
                "longest_episode_minutes": longest,
                "episodes_at_least_6h": long_episodes,
            })
    sensitivity = pd.DataFrame(sensitivity_rows)
    screening = monthly.groupby(["floor", "zone"], as_index=False).agg(
        average_high_rh_share_pct=("high_rh_share_of_valid_pct", "mean"),
        worst_month_high_rh_share_pct=("high_rh_share_of_valid_pct", "max"),
        longest_monthly_episode_minutes=("longest_high_rh_episode_minutes", "max"),
        total_episodes_at_least_6h=("episodes_at_least_6h", "sum"),
        valid_rh_minutes=("valid_rh_minutes", "sum"),
        minutes_rh_above_60=("minutes_rh_above_60", "sum"),
        average_rh_coverage_pct=("rh_coverage_pct", "mean"),
        months_with_rh_data=("rh_coverage_pct", lambda values: int(values.gt(0).sum())),
        average_ac_kW=("mean_ac_kW", "mean"),
        average_temp_C=("mean_temp_C", "mean"),
        average_outdoor_temp_C=("mean_outdoor_temp_C", "mean"),
        average_outdoor_rh_pct=("mean_outdoor_rh_pct", "mean"),
        total_precipitation_mm=("total_precipitation_mm", "sum"),
        average_ac_kW_per_cooling_degree=("mean_ac_kW_per_cooling_degree", "mean"),
    )
    screening["valid_minutes_above_60_pct"] = (
        100 * screening["minutes_rh_above_60"] / screening["valid_rh_minutes"]
    )
    screening = screening.sort_values(
        ["valid_minutes_above_60_pct", "longest_monthly_episode_minutes"],
        ascending=False,
    )
    weather_monthly = _monthly_weather(weather)

    outputs = {
        "bangkok_era5_hourly_baseline.csv": weather.reset_index(),
        "bangkok_era5_monthly_baseline.csv": weather_monthly,
        "humidity_zone_monthly_baseline.csv": monthly,
        "humidity_zone_hourly_baseline.csv": hourly,
        "humidity_year_comparison.csv": year_comparison,
        "humidity_assumed_occupied_profile.csv": schedule,
        "humidity_threshold_sensitivity.csv": sensitivity,
        "humidity_inspection_screen.csv": screening,
    }
    for filename, table in outputs.items():
        table.to_csv(output_dir / filename, index=False)

    if not monthly.empty:
        heatmap_data = monthly.pivot_table(
            index=["floor", "zone"], columns=["year", "month"],
            values="mean_rh_pct", aggfunc="mean",
        )
        fig, ax = plt.subplots(figsize=(15, max(4, len(heatmap_data) * 0.32)))
        image = ax.imshow(heatmap_data, aspect="auto", interpolation="nearest", cmap="YlOrRd")
        ax.set_yticks(range(len(heatmap_data)))
        ax.set_yticklabels([f"F{f}-Z{z}" for f, z in heatmap_data.index])
        ax.set_xticks(range(len(heatmap_data.columns)))
        ax.set_xticklabels(
            [f"{year}-{month:02d}" for year, month in heatmap_data.columns],
            rotation=90,
        )
        ax.set_title("Monthly mean relative humidity by zone")
        fig.colorbar(image, ax=ax, label="Mean RH (%)")
        fig.tight_layout()
        fig.savefig(output_dir / "humidity_monthly_heatmap.png", dpi=150)
        plt.show()

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        axes[0].plot(
            weather_monthly["month_start"],
            weather_monthly["mean_outdoor_temp_C"],
            marker="o",
            color="#d66b2a",
        )
        axes[0].set_ylabel("Outdoor temperature (°C)")
        axes[0].set_title("Bangkok ERA5 monthly weather context")
        axes[1].bar(
            weather_monthly["month_start"],
            weather_monthly["total_precipitation_mm"],
            width=20,
            color="#2a78d6",
        )
        axes[1].set_ylabel("Precipitation (mm)")
        axes[1].set_xlabel("Month")
        fig.tight_layout()
        fig.savefig(output_dir / "bangkok_era5_monthly_context.png", dpi=150)
        plt.show()

        screen_plot = screening.sort_values("valid_minutes_above_60_pct")
        screen_labels = [
            f"F{row.floor}-Z{row.zone}" for row in screen_plot.itertuples()
        ]
        colors = np.where(
            screen_plot["average_rh_coverage_pct"] >= 80, "#d66b2a", "#a3a29c"
        )
        fig, ax = plt.subplots(figsize=(10, max(5, len(screen_plot) * 0.28)))
        ax.barh(
            screen_labels,
            screen_plot["valid_minutes_above_60_pct"],
            color=colors,
        )
        ax.axvline(
            10, color="#2a78d6", linestyle="--", linewidth=1.5,
            label="Proposal KPI: 10% of valid minutes",
        )
        ax.set_xlabel("Valid minutes with RH >60% (%)")
        ax.set_title("Zone humidity exposure; gray bars have <80% mean RH coverage")
        ax.legend(loc="lower right")
        ax.grid(axis="y", visible=False)
        fig.tight_layout()
        fig.savefig(output_dir / "humidity_zone_exposure_ranking.png", dpi=150)
        plt.show()

        relationship = monthly.dropna(
            subset=["mean_outdoor_dew_point_C", "mean_rh_pct"]
        )
        fig, ax = plt.subplots(figsize=(9, 6))
        for floor, floor_data in relationship.groupby("floor", sort=True):
            ax.scatter(
                floor_data["mean_outdoor_dew_point_C"],
                floor_data["mean_rh_pct"],
                s=30,
                alpha=0.65,
                label=f"Floor {floor}",
            )
        ax.axhline(60, color="#d03b3b", linestyle="--", linewidth=1.2, label="60% RH screen")
        ax.set(
            xlabel="Monthly mean outdoor dew point (°C, ERA5)",
            ylabel="Monthly mean indoor zone RH (%)",
            title="Monthly indoor humidity with outdoor moisture context",
        )
        ax.legend(ncol=2)
        fig.tight_layout()
        fig.savefig(output_dir / "indoor_rh_vs_outdoor_dew_point.png", dpi=150)
        plt.show()
    return {
        "monthly_baseline": monthly,
        "hourly_baseline": hourly,
        "year_comparison": year_comparison,
        "assumed_occupied_profile": schedule,
        "threshold_sensitivity": sensitivity,
        "inspection_screen": screening,
        "weather_monthly": weather_monthly,
        "output_directory": output_dir,
    }
