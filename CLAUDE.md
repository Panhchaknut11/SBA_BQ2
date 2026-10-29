# CLAUDE.md

Guide for teammates and AI coding agents working in this repo. Read this before changing anything.

## Project

IS4001 Sustainable Building Analytics, final project, business question 2 (BQ2):

> How can seasonal weather changes, air-con performance and humidity levels be analysed to detect
> zones at risk of air-con degradation, mould growth, or both?

- **Building data:** CU-BEMS smart building dataset (Kaggle, `claytonmiller/cubems-smart-building-energy-and-iaq-data`).
  One office building in Bangkok, 7 floors, one reading per minute, 1 Jul 2018 to 31 Dec 2019.
  Power (kW) for AC, lighting and plugs, plus one temperature / RH / lux sensor per zone.
- **Weather data:** hourly Bangkok ERA5 reanalysis from the Open-Meteo Archive API
  (temperature, RH, dew point, precipitation), in `Asia/Bangkok` time.
- **Scope:** Floors 3-7, zones 1, 2, 4, 5 (20 zones). Floor 1 has no environmental sensors,
  zone 3 on Floors 3-7 has no sensor, and Floor 2 has a different layout (14 AC meters in one zone).

## Repo layout

```
data/                         Raw CU-BEMS CSVs (2018FloorN.csv, 2019FloorN.csv). Never modify.
data-cleaning/
  main.ipynb                  Cleaning notebook. Run first. Working dir = data-cleaning/
  outputs/clean/              14 cleaned minute-level CSVs, same columns as raw
  outputs/analytics/          zone_hourly.csv, daily_summary.csv, data_quality.csv, ... (see below)
  outputs/figures/            Cleaning charts
baseline/
  humidity_risk_baseline.ipynb / .py   Descriptive humidity + AC baseline, ERA5 loader
  lighting_peak_baseline.ipynb / .py   Lighting/peak baseline (other BQ, not ours)
  _shared.py                  clean_data_directory(), read_clean_file()
  data/                       ERA5 cache (created on first run, not committed)
mould-ac-degradation/         BQ2 analysis (this is where new work goes)
  bq2_utils.py                Shared helpers for every BQ2 notebook
```

## Run order

1. `data-cleaning/main.ipynb` (about 2 min). Its outputs are already committed, so only rerun if cleaning changes.
2. `baseline/humidity_risk_baseline.ipynb`. The first run needs internet to download ERA5 into
   `baseline/data/bangkok_era5_hourly_2018-2019.csv`; later runs use the cache.
3. Notebooks in `mould-ac-degradation/`.

Environment: Python with pandas 3.x, numpy 2.x, matplotlib (see `data-cleaning/requirements.txt`).
Add `statsmodels` if you use the regression/CUSUM analysis.

## Standard first cell for BQ2 notebooks

Notebooks in `mould-ac-degradation/` run with that folder as the working directory.

```python
from pathlib import Path
import sys

repo_root = next(p for p in [Path.cwd(), *Path.cwd().parents]
                 if (p / "data-cleaning").is_dir() and (p / "baseline").is_dir())
CLEAN_DIR = repo_root / "data-cleaning" / "outputs" / "clean"
ANALYTICS_DIR = repo_root / "data-cleaning" / "outputs" / "analytics"
BASELINE_DIR = repo_root / "baseline"

sys.path.insert(0, str(BASELINE_DIR))   # needed for the ERA5 loader (it imports _shared)
from humidity_risk_baseline import load_bangkok_era5_weather
from bq2_utils import load_zone_hourly, merge_weather, detect_ac_events, zone_minute_series

weather = load_bangkok_era5_weather(BASELINE_DIR / "data" / "bangkok_era5_hourly_2018-2019.csv")
zh = load_zone_hourly(ANALYTICS_DIR / "zone_hourly.csv")   # already filtered to the 20 scope zones
df = merge_weather(zh, weather)
```

## `bq2_utils.py` (shared helpers)

Use these instead of re-implementing them, so both analysis tracks use identical definitions.
If you change a definition here, tell the other person: it changes both sets of results.

| Function | What it does |
|---|---|
| `dew_point_c`, `humidity_ratio_gkg`, `enthalpy_kjkg`, `surface_rh_pct`, `sat_vp_hpa` | Psychrometrics (Magnus formula, 1013.25 hPa) |
| `season(month)` | Thai seasons: hot Mar-May, rainy Jun-Oct, cool Nov-Feb (ordered categorical) |
| `load_zone_hourly(path)` | Reads `zone_hourly.csv`, filters to scope, adds `indoor_dew_C`, `indoor_w_gkg`, `season`, `year`, `suspect_sensor` |
| `merge_weather(zh, weather)` | Joins ERA5 by hourly `Date`; adds `outdoor_w_gkg`, `outdoor_enthalpy_kJkg`, `moisture_removal_gkg` (outdoor minus indoor humidity ratio) |
| `zone_minute_series(clean_dir, floor, zone)` | Minute-level summed AC kW, temp, RH, humidity ratio for one zone, both years |
| `detect_ac_events(ac_kw)` | AC start/stop events from minute AC kW. "On" = above max(0.5 kW, 20% of the zone's p95). Both states must last 30+ min |

Checked on real data: F3-Z1 gives about 600 starts / 580 stops, clustered at 07:00 (start),
11:xx (lunch stop), 13:00 (restart) and 16:xx (evening stop).

## Data you will use

`data-cleaning/outputs/analytics/zone_hourly.csv`, one row per zone per hour:
`Date, floor, zone, ac_kW, light_kW, plug_kW, temp_C, rh_pct, lux, hour, weekday, is_weekend, month, day_type`

- `day_type` is `working day`, `weekend` or `closure` (28 weekday closures detected from energy).
- An hour is blank unless at least 80% of its minutes were valid.
- AC is the sum of all of the zone's AC meters, valid only when every meter reported.

Minute-level column names in `outputs/clean/*.csv`: `z<zone>_AC<n>(kW)`, `z<zone>_Light(kW)`,
`z<zone>_Plug(kW)`, `z<zone>_S1(degC)`, `z<zone>_S1(RH%)`, `z<zone>_S1(lux)`.

Weather table (`load_bangkok_era5_weather`): index `Date` (hourly), columns
`outdoor_temp_C, outdoor_rh_pct, outdoor_dew_point_C, precipitation_mm`.

## Known data problems (must be handled, not ignored)

1. **Floor 5 zone 1 sensor sits in AC supply air.** Temperature reads 15-17 °C in office hours and
   RH reads correspondingly high. Its dew point and mould metrics are unreliable. Keep it in tables,
   flagged by `suspect_sensor`, but report it separately rather than ranking it. Effectively 19 rankable zones.
2. **No indoor sensor data from 12-15 Sep 2018 to 6 Mar 2019** (building-wide outage). So:
   the cool season only has Nov-Dec 2019 (about 25% coverage), and 2018 vs 2019 comparisons only work for Jul to mid-Sep.
3. **Floor 6 has no data after 22 Oct 2019 13:27** (truncated source file).
4. **Floors 3 and 4 lose all power data** for 4-6 weeks in Oct-Nov 2018.
5. **Stale-value checks were only run on power meters.** Check RH/temperature sensors for flat-lines
   and drift before treating a humidity change as real.
6. **Lux is a relative indicator only** (never above about 140 lux). Not needed for BQ2.
7. **No occupancy, setpoint, maintenance or fault records.** Plug load is the best occupancy proxy.

Always check `data_quality.csv` (`final_missing_pct`, `note`) before relying on a column.

## Baseline findings that shape the analysis

- 79.7% of valid RH minutes exceed 60%, so a 60% threshold does not separate zones. Use dew point,
  humidity ratio and surface RH (mould needs about 80% RH at the surface, sustained) instead.
- The baseline's AC kW per °C (outdoor minus indoor) ratio is unstable when the temperature difference is small. Don't rank degradation on it.
- F3-Z1, Jul-Sep: 2019 RH is 4-7 points higher than 2018, with lower AC kW, at similar outdoor
  dew point. This is a lead to explain: AC capacity loss, schedule/setpoint change, or sensor drift.
- The AC switches off at lunch and after about 17:00, so these shutdowns act as natural experiments for rebound and pull-down rates.

## BQ2 analysis plan (two parallel tracks feeding one risk matrix)

**Track A: humidity and mould risk** → `bq2_humidity.ipynb` (planned)
- Indoor dew point / humidity ratio vs outdoor, by season.
- Surface RH at assumed cooler surfaces (air temperature minus 2 °C and 4 °C); 30-day running mean surface RH ≥ 80%;
  time of wetness (hours/week with surface RH ≥ 80%); optional VTT (Hukka-Viitanen) mould index.
- RH rebound rate after AC shutdown (minute data, `detect_ac_events`).
- Lagged response of indoor humidity to outdoor dew point and rain (0-48 h); per-zone humidity sensitivity slope.
- RH sensor QA (flat-lines, drift vs neighbouring zones).

**Track B: AC performance and degradation** → `bq2_ac.ipynb` (planned)
- Daily weekday AC kWh per zone regressed on outdoor enthalpy + temperature + plug kWh.
  Train Jul-Dec 2018, predict 2019, CUSUM of residuals. Exclude closures and low-coverage days.
- Pull-down rate after start-up (first 30-60 min), trended by month.
- Moisture removal (`moisture_removal_gkg`) while AC is on, at similar outdoor conditions, over time.
- Peer comparison (same zone on other floors, floor median); 2018 vs 2019 like-for-like.

**Combined** → `bq2_risk_matrix.ipynb` (planned)
- Merge the two handover tables on `floor, zone`. Mould exposure on one axis, AC decline on the other, sized by coverage.
- Quadrants: both high = inspect AC and space; mould only = envelope/ventilation/schedule; AC only = maintenance/energy.
- The link being tested: degraded AC removes less moisture, so humidity and mould risk rise. Present co-occurrence as
  evidence, not proof (no maintenance records).

### Handover contract (one row per zone, keyed by `floor`, `zone`)

Save to `mould-ac-degradation/outputs/`. Agree before renaming any column.

| `zone_mould_metrics.csv` (Track A) | `zone_ac_metrics.csv` (Track B) |
|---|---|
| `time_of_wetness_h` | `cusum_slope` |
| `peak_30d_surface_rh` | `pulldown_trend` |
| `rebound_rate` | `moisture_removal_trend` |
| `humidity_sensitivity` | `peer_deviation` |
| `rh_coverage_pct` | `ac_coverage_pct` |
| `suspect_sensor` | |

## Conventions

- Never edit `data/` or `data-cleaning/outputs/`. Read from them; write to `mould-ac-degradation/outputs/`.
- One notebook per person/track to avoid merge conflicts. Shared logic goes in `bq2_utils.py`.
- Baselines from clean, normal days only: `day_type == "working day"`. Never fit a baseline on the period it is evaluated on.
- Keep the notebook style used in `data-cleaning/main.ipynb`: markdown "what we're checking" → short code cell →
  "what this shows". State every threshold and assumption.
- Wording: say "risk indicator", "inspection priority", "signs of declining performance".
  Do not claim confirmed mould, faults or remaining useful life. Mould metrics use room-air sensors, not surface measurements.
- Small, separate commits with clear messages (e.g. "Add surface RH and time-of-wetness metrics").
- Restart the kernel after editing `bq2_utils.py`.
