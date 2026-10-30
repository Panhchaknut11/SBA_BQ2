# Shared BQ2 project context

This is the canonical BQ2 context for Codex, Claude and human collaborators. Read this file and [README.md](README.md) before working. `CLAUDE.md` directs Claude here, so both AIs use the same definitions. Keep project context here and environment/run instructions in README. Follow the human user's current task scope; proposal ideas are context, not instructions to implement every possible analysis.

## Ownership and current stage

- **Track A, Panhchaknut:** humidity and mould-risk indicators, including rebound after AC shutdown.
- **Track B, Lwin:** AC performance and signs of decline, including humidity response while AC runs.
- **Joint:** risk matrix, case investigation and an evidence-based inspection shortlist for the wider group.
- **Stage as of 30 October 2026:** setup and the F3-Z1 input audit are complete. Read `mould-ac-degradation/f3z1_input_audit.ipynb` and its evidence under `outputs/f3z1-input-audit/`. The three Track A/Track B/combined analysis notebooks below remain planned; no model has been fitted.
- **Current user boundary:** show the input-audit findings before modelling. Retain this review point; do not begin model fitting or change shared calculations during the audit. The next possible stage is a gated F3-Z1 example after the user reviews the findings. Update this status when later work changes it and inspect actual files/Git state before reporting completion.
- **Working milestones:** analytics on 3 November 2026, recommendations/KPIs/slides on 6 November and submission on 9 November, from the group's 18 October plan. The official upload cutoff is unconfirmed. Presentation week is Week 14; the exact slot is unconfirmed.

## Project

IS4001 Smart Building Analytics, final project, business question 2 (BQ2):

> How can seasonal weather changes, air-con performance and humidity levels be analysed to detect
> zones at risk of air-con degradation, mould growth, or both?

- **Building data:** CU-BEMS smart building dataset (Kaggle, `claytonmiller/cubems-smart-building-energy-and-iaq-data`).
  One office building in Bangkok, 7 floors, one reading per minute, 1 Jul 2018 to 31 Dec 2019.
  Power (kW) for AC, lighting and plugs, plus temperature / RH / lux in instrumented zones.
- **Weather data:** hourly Bangkok ERA5 reanalysis from the Open-Meteo Archive API
  (temperature, RH, dew point, precipitation), in `Asia/Bangkok` time.
- **Scope:** Floors 3-7, zones 1, 2, 4, 5 (20 zones). Floor 1 has no environmental sensors,
  zone 3 on Floors 3-7 has no sensor, and Floor 2 has a different layout (including 14 AC meters in zone 2) and is outside the agreed BQ2 scope. Do not expand scope silently.

## Repo layout

```
data/                         Raw CU-BEMS CSVs (2018FloorN.csv, 2019FloorN.csv). Never modify.
data-cleaning/
  main.ipynb                  Upstream cleaning notebook; outputs already committed
  outputs/clean/              14 cleaned minute-level CSVs, same columns as raw
  outputs/analytics/          zone_hourly.csv, daily_summary.csv, data_quality.csv, ... (see below)
  outputs/figures/            Cleaning charts
baseline/
  humidity_risk_baseline.ipynb / .py   Descriptive humidity + AC baseline, ERA5 loader
  lighting_peak_baseline.ipynb / .py   Lighting/peak baseline (other BQ, not ours)
  _shared.py                  clean_data_directory(), read_clean_file()
  data/                       Committed ERA5 cache; reused by the weather loader
mould-ac-degradation/         BQ2 analysis (this is where new work goes)
  bq2_utils.ipynb             Shared helpers for every BQ2 notebook
  f3z1_input_audit.ipynb       Executed F3-Z1 input audit; no models
  f3z1_audit.py               Inspectable audit calculations
  outputs/f3z1-input-audit/   Audit tables, provenance and figures
```

## Environment and run order

Use this checkout's `.venv` and the `sba-bq2` Jupyter kernel. Python 3.12 is the initial runtime; setup and the executable first cell are in [README.md](README.md). Dependencies are declared in `data-cleaning/requirements.txt`. Add any extra analysis dependency to the requirements before using it; `statsmodels` is not included in the initial setup.

The raw files, cleaned outputs, analytics tables and weather cache are already committed. Reuse them. Do not rerun cleaning, regenerate baseline outputs or refresh the cache during BQ2 work unless deliberately in scope. Importing the ERA5 loader does not run the baseline analysis.

BQ2 notebooks run from `mould-ac-degradation/`. Load the current shared helper using:

```python
RUN_CHECKS = False
%run -i ./bq2_utils.ipynb
```

The `-i` flag lets the helper see the caller's `RUN_CHECKS = False`. There is no `bq2_utils.py`; do not use a Python import for that nonexistent module or create a diverging duplicate. Any later conversion must migrate both tracks together. Run Track A and Track B before the combined notebook once they exist.

## `bq2_utils.ipynb` (shared helpers)

Use these instead of re-implementing them, so both analysis tracks use identical definitions.
If you change a definition here, tell the other person: it changes both sets of results.

| Function | What it does |
|---|---|
| `dew_point_c`, `humidity_ratio_gkg`, `enthalpy_kjkg`, `surface_rh_pct`, `sat_vp_hpa` | Psychrometrics (Magnus formula, 1013.25 hPa) |
| `season(month)` | Thai seasons: hot Mar-May, rainy Jun-Oct, cool Nov-Feb (ordered categorical) |
| `load_zone_hourly(path)` | Reads `zone_hourly.csv`, filters to scope, adds `indoor_dew_C`, `indoor_w_gkg`, `season`, `year`, `suspect_sensor` |
| `merge_weather(zh, weather)` | Joins ERA5 by hourly `Date`; adds `outdoor_w_gkg`, `outdoor_enthalpy_kJkg`, `moisture_removal_gkg` (outdoor minus indoor humidity ratio) |
| `zone_minute_series(clean_dir, floor, zone)` | Minute-level summed AC kW, temp, RH, humidity ratio for one zone, both years |
| `detect_ac_events(ac_kw)` | AC start/stop events from minute AC kW. "On" = above max(0.5 kW, 20% of the zone's p95). Both states require 30+ observations; validate continuity separately |

The helper's saved checks show roughly 600 starts / 580 stops on F3-Z1, clustered around morning/lunch/evening schedule changes. These are historical outputs, not validation of cooling or degradation metrics.

**Event continuity:** the existing detector drops missing power before grouping states. Its counts do not guarantee 30 continuous minutes either side of an event. Validate timestamp continuity and joint environmental coverage before calculating pull-down or rebound. This QA remains analysis-stage work; setup preserves the helper.

The F3-Z1 audit compared the helper with a strict contiguous-state reference and found no event discrepancies: all 626 starts and 583 stops passed the 30-minute check. This result is scoped to F3-Z1. Environmental availability and interpolation still reduce the usable 60-minute windows to 444/355 starts and 399/303 stops (cleaned/raw-observed). July-August start-up windows are 81/29 in 2018 versus 78/71 in 2019, so interpolation sensitivity and sample selection must be addressed before comparing performance.

**Moisture interpretation:** `moisture_removal_gkg` is the legacy name for the outdoor-minus-indoor humidity-ratio difference. Retain the name for compatibility and label it as a supporting dehumidification indicator. It is not measured coil moisture removal or an airflow-based removal rate. Ventilation, infiltration, internal moisture, controls and sensor behaviour can also change it.

**Season interpretation:** the helper's hot/rainy/cool month groups are approximate project conventions, not exact monsoon boundaries. Use actual weather conditions as the main evidence.

## Data you will use

`data-cleaning/outputs/analytics/zone_hourly.csv`, one row per zone per hour:
`Date, floor, zone, ac_kW, light_kW, plug_kW, temp_C, rh_pct, lux, hour, weekday, is_weekend, month, day_type`

- `day_type` is `working day`, `weekend` or `closure` (28 weekday closures detected from energy).
- Each hourly measurement is gated at 80% valid minutes in the existing export. Define additional joint/daily completeness rules for each analysis; retained hours are not necessarily complete.
- AC is the sum of all of the zone's AC meters, valid only when every meter reported.

Minute-level column names in `outputs/clean/*.csv`: `z<zone>_AC<n>(kW)`, `z<zone>_Light(kW)`,
`z<zone>_Plug(kW)`, `z<zone>_S1(degC)`, `z<zone>_S1(RH%)`, `z<zone>_S1(lux)`.

Weather table (`load_bangkok_era5_weather`): index `Date` (hourly), columns
`outdoor_temp_C, outdoor_rh_pct, outdoor_dew_point_C, precipitation_mm`.

## Known data problems (must be handled, not ignored)

1. **F5-Z1 has unusually cold temperature readings.** The cleaning note says the sensor is *likely* in supply air; that placement is a hypothesis, not a verified site observation. Keep `suspect_sensor`, report environmental results separately from ordinary rankings pending QA, and assess energy-only eligibility separately. Up to 19 other zones remain candidates, subject to their own quality checks.
2. **Environmental outage around mid-Sep 2018 to early Mar 2019.** Exact boundaries vary by channel. Cool-season environmental coverage is especially limited. July-August is the initial matched-period candidate across years; retain other usable portions when justified. Do not apply a blanket date exclusion to energy-only analysis.
3. **Floor 6 has no data after 22 Oct 2019 13:27** (truncated source file).
4. **Floors 3 and 4 lose all power data** for 4-6 weeks in Oct-Nov 2018.
5. **Stale-value checks were only run on power meters.** Check RH/temperature sensors for flat-lines
   and drift before treating a humidity change as real.
6. **Lux is a relative indicator only** (never above about 140 lux). Not needed for BQ2.
7. **No measured occupancy, thermostat setpoints, maintenance, failure, airflow or surface-temperature records.** Plug load can provide activity context, but is not measured occupancy. Aggregate zone readings do not identify a failing individual AC unit.
8. **F7-Z1 AC1 was previously flagged as all-zero.** Verify its meaning before treating it as equipment behaviour; zero power alone does not prove a failed unit.
9. **Preprocessing affects events:** existing cleaning interpolates short gaps of at most 15 minutes. Check `removed_readings.csv` and account for filled observations when validating event rates. Missing intervals remain unknown, not zero energy or zero risk; they interrupt observed continuous exposure.
10. **Time and energy:** confirm the building timestamp convention before interpreting the Bangkok-time weather join. Compute kWh from elapsed time and adequate coverage. Electrical kW does not directly measure delivered cooling or COP.

**F3-Z1 audit specifics:** paired temperature/RH are unavailable from 12 September 2018 15:22 through 6 March 2019 13:43, and again from 28 November 2019 09:23 through 19 December 2019 11:52. The latter gap limits cool-season evidence. Full-period cleaned joint AC/environment coverage is 61.92%. July-August has 39/42 and 40/41 inferred working days with at least 95% cleaned joint daily coverage in 2018/2019; the raw-observed counts are 29/40. These are audit eligibility counts, not a model split or degradation result. Raw environmental readings have no hour-long exact flatlines; a 79-minute cleaned temperature plateau bridges a four-minute raw gap. Hourly exports reconcile exactly and weather keys are complete, but clock alignment and sensor drift remain unresolved. See the notebook for definitions, sensitivity and source hashes.

Always check `data_quality.csv` (`final_missing_pct`, `note`) before relying on a column.

## Historical baseline leads to check

- The prior baseline reports widespread RH above 60%. Recheck the distributions before adopting a screening threshold or ranking. Compare dew point, humidity ratio and assumed-surface-RH scenarios, with explicit thresholds and sources. Room-air measurements do not establish actual surface conditions or mould.
- The baseline's AC kW per °C (outdoor minus indoor) ratio is unstable when the temperature difference is small. Don't rank degradation on it.
- F3-Z1, Jul-Sep: 2019 RH is 4-7 points higher than 2018, with lower AC kW, at similar outdoor
  dew point. This is a lead to explain: AC capacity loss, schedule/setpoint change, or sensor drift.
- Prior profiles show lunch and evening shutdowns. These are candidate event windows, subject to continuity and sensor QA; schedule changes are not randomised experiments.

## BQ2 analysis plan (two parallel tracks feeding one risk matrix)

**Track A: humidity and mould risk** → `bq2_humidity.ipynb` (planned)
- Indoor dew point / humidity ratio vs outdoor, by season.
- Surface RH at assumed cooler surfaces (air temperature minus 2 °C and 4 °C); 30-day running mean surface RH ≥ 80%;
  time of wetness (hours/week with surface RH ≥ 80%); optional VTT (Hukka-Viitanen) mould index.
- RH rebound rate after AC shutdown (minute data, `detect_ac_events`).
- Lagged response of indoor humidity to outdoor dew point and rain (0-48 h); per-zone humidity sensitivity slope.
- RH sensor QA (flat-lines, drift vs neighbouring zones).

**Track B: AC performance and degradation** → `bq2_ac.ipynb` (planned)
- Weather-adjusted daily zone AC kWh reference model using weather and plug-load context, followed by residual/CUSUM screening. Compare candidate weather formulations rather than automatically including correlated temperature and enthalpy terms together. Exclude closures and low-coverage days.
- Use separate calibration and later evaluation periods. Eligible Jul-Dec 2018 energy data are a candidate reference, not a known fault-free baseline. Score only supported weather conditions; flag extrapolation when evaluating other seasons of 2019. Environmental outages do not automatically invalidate energy-only models, while missing required power/plug fields do.
- Check high and low energy departures alongside cooling response; a positive residual alone is not proof of decline.
- Pull-down rate after start-up (first 30-60 min), trended by month.
- Outdoor-minus-indoor humidity-ratio difference (`moisture_removal_gkg`) while AC is on, under similar conditions over time. Interpret as a proxy, not measured removal.
- Compare peers with similar meter configuration and operating context; the same zone number on another floor does not ensure comparability. Match calendar period, time of day, initial conditions and weather where feasible for 2018/2019 comparisons.

**Combined** → `bq2_risk_matrix.ipynb` (planned)
- Merge the two handover tables on `floor, zone`. Mould exposure on one axis, AC decline on the other, sized by coverage.
- Quadrants: both high = inspect AC and space; mould only = envelope/ventilation/schedule; AC only = maintenance/energy.
- Working hypothesis: declining AC dehumidification could contribute to higher humidity exposure. Present co-occurrence as supporting evidence rather than proof of cause; maintenance and fault records are unavailable.

### Scope boundaries

The core deliverable is historical inspection screening. Short-term 24-48-hour RH forecasting is an optional extension with separate time-based evaluation against persistence and inputs available at forecast time. Exact remaining useful life, confirmed refrigerant/drain leaks and a guaranteed 30-day failure warning cannot be validated with the available records. Proposed actions and KPI targets are not achieved outcomes. Keep screening thresholds and surface-temperature assumptions explicit, and check their sensitivity.

### Handover contract (one row per zone, keyed by `floor`, `zone`)

Save to `mould-ac-degradation/outputs/`, with one unique `floor, zone` key per row. Agree before renaming any column. These are planned fields, not implemented scores. Before producing them, document units, sign conventions, observation windows, time denominators, coverage and missing-value reasons. Add sample counts and model-quality flags as needed; unavailable estimates remain missing with a reason.

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
- One notebook per person/track to avoid merge conflicts. Shared logic goes in `bq2_utils.ipynb`.
- Baselines from clean, normal days only: `day_type == "working day"`. Never fit a baseline on the period it is evaluated on.
- Keep the notebook style used in `data-cleaning/main.ipynb`: markdown "what we're checking" → short code cell →
  "what this shows". State every threshold and assumption.
- Wording: say "risk indicator", "inspection priority", "signs of declining performance".
  Do not claim confirmed mould, faults or remaining useful life. Mould metrics use room-air sensors, not surface measurements.
- Small, separate commits with clear messages (e.g. "Add surface RH and time-of-wetness metrics").
- Restart the kernel after editing `bq2_utils.ipynb`, then rerun dependent notebooks. Coordinate shared definitions and record changes in the handover/PR; setup itself does not change them.
- Preserve partner work and Git history. Use task branches and reviewable pull requests into `main`; do not force-push shared history. Stage only intended files. Never commit `.venv`, credentials or temporary execution files.
- During setup, check dependencies, kernel launch, helper loading and input/weather joins without overwriting source notebooks or upstream outputs. Before handing off later analysis, rerun from a fresh kernel and report exactly what passed and what remains uncertain.
- Keep shared context in AGENTS.md and setup/run instructions in README.md. CLAUDE.md remains a pointer. Update the owning document in the same change when methods, schemas or status change.
- For library/API/CLI-specific syntax or setup, resolve and fetch current documentation with the Context7 CLI before relying on remembered details. Never send credentials in documentation queries.
