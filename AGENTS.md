# Shared BQ2 project context

This is the canonical BQ2 context for Codex, Claude and human collaborators. Read this file and [README.md](README.md) before working. `CLAUDE.md` directs Claude here, so both AIs use the same definitions. Keep project context here and environment/run instructions in [docs/setup.md](docs/setup.md), linked from README. Follow the human user's current task scope; proposal ideas are context, not instructions to implement every possible analysis.

## Ownership and current stage

- **Track A, Panhchaknut:** humidity and mould-risk indicators, including rebound after AC shutdown.
- **Track B, Lwin:** AC performance and signs of decline, including humidity response while AC runs.
- **Joint:** risk matrix, case investigation and an evidence-based inspection shortlist for the wider group.
- **Stage as of 31 October 2026:** the 20-zone screen and focused investigation of F3-Z4, F5-Z4 and F7-Z2 are consolidated in [the Track B report](mould-ac-degradation/reports/track-b/track_b_report.md). The [integration review](mould-ac-degradation/reports/track-b/review_2026-10-31.md) records four fresh notebook runs, reproduction of all 70 saved CSV tables and eight charts, and independent raw-energy/reference-fit checks. `notebooks/bq2_ac.ipynb` remains the analysis entry point, with `notebooks/bq2_case_investigation.ipynb` as its diagnostic companion. No material analytical merge blocker was demonstrated within this historical screening scope. Original evidence is preserved. Broader seasonal/peer work, Track A and the joint risk matrix remain planned.
- **Current user boundary:** PRs #1–#5 were merged in order into `main` at `c730653` and their five topic branches were deleted after ancestry/tree checks. The user now requests a first-principles reassessment against Person B's checklist, a clear data-to-recommendation presentation story, and proper file/folder organisation. The [scope and presentation guide](mould-ac-degradation/reports/track-b/person_b_scope_and_presentation.md) records the implemented/withheld/pending work and proposal corrections. The user subsequently authorised a physical folder reorganisation and standalone tests. Current notebook entries live in `notebooks/` and calculation modules in `src/bq2/`. Verify the migration with the fast suite and fresh scratch execution; preserve scientific definitions, shared helpers and committed evidence. The group Canva deck is outside this change. Broader modelling, final handover fields and Track A/joint-matrix implementation remain follow-up tasks. Inspect actual files/Git state before claiming completion.
- **Audience clarification:** the immediate walkthrough is an internal discussion of Lwin's findings with his teammate, Person A. No individual class-presentation time has been assigned. Focus on data/method choices, findings, limitations and the next joint decisions; prepare timed class slides later if requested.
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
README.md / docs/setup.md      Human navigation, environment and run instructions
data/                         Original CU-BEMS CSVs; never modify
data-cleaning/                Shared upstream cleaning and committed exports
baseline/                     Earlier baselines, input helpers and weather cache
mould-ac-degradation/
  README.md                   Analysis index
  bq2_utils.ipynb             Stable shared helper; existing path preserved
  requirements.txt            Existing analysis dependency declarations
  notebooks/                 Executed input audit, main screen and case companion
  src/bq2/                   input_audit, reference_models, zone_screen, case_investigation, paths
  tests/                     Automated checks, synthetic support and frozen-evidence fixture
  tests/.runs/               Ignored local notebook validation copies/records
  scripts/validate_notebooks.py  Full scratch-run reproduction command
  outputs/                   Preserved audit, first-pass, zone-screen and case evidence
  reports/track-b/            Report, charts, teammate guide and dated review records
```

## Environment and run order

Use this checkout's `.venv` and the `sba-bq2` Jupyter kernel. Python 3.12 is the initial runtime; setup and the executable loading cell are in [docs/setup.md](docs/setup.md). Install `mould-ac-degradation/requirements.txt`, which includes the base cleaning requirements plus statsmodels and SciPy for Track B. Add any extra analysis dependency to the requirements before using it.

The raw files, cleaned outputs, analytics tables and weather cache are already committed. Reuse them. Do not rerun cleaning, regenerate baseline outputs or refresh the cache during BQ2 work unless deliberately in scope. Importing the ERA5 loader does not run the baseline analysis.

BQ2 notebooks now live under `mould-ac-degradation/notebooks/`. Each setup cell locates this checkout, adds `mould-ac-degradation/src/` to `sys.path` and imports the `bq2` package. It loads the shared notebook at its unchanged absolute path:

```python
RUN_CHECKS = False
helper_notebook = analysis_dir / "bq2_utils.ipynb"
get_ipython().run_line_magic("run", f'-i "{helper_notebook}"')
```

The full bootstrap is in the setup guide. There is no `bq2_utils.py`; do not create diverging helper definitions. The `-i` option exposes the caller's `RUN_CHECKS = False`. Source modules use package-relative imports. Output paths derive from `analysis_dir`, so notebook working directories do not relocate the evidence. Run Track A and Track B before the combined notebook once they exist.

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
5. **Upstream stale-value checks covered power meters.** The later BQ2 audits also checked raw RH/temperature flatlines; no hour-long paired flatline explained the three focused cases. Those checks do not verify calibration, sensor continuity, placement or drift. Keep these unresolved when interpreting year-to-year environmental changes.
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

**Track B: AC performance and degradation** → `notebooks/bq2_ac.ipynb` (20-zone July-August screen implemented; broader seasonal/peer work below remains planned)
- Weather-adjusted daily zone AC kWh reference model using weather and plug-load context, followed by residual/CUSUM screening. Compare candidate weather formulations rather than automatically including correlated temperature and enthalpy terms together. Exclude closures and low-coverage days.
- Use separate calibration and later evaluation periods. Eligible Jul-Dec 2018 energy data are a candidate reference, not a known fault-free baseline. Score only supported weather conditions; flag extrapolation when evaluating other seasons of 2019. Environmental outages do not automatically invalidate energy-only models, while missing required power/plug fields do.
- Check high and low energy departures alongside cooling response; a positive residual alone is not proof of decline.
- Pull-down rate after start-up (first 30-60 min), trended by month.
- Outdoor-minus-indoor humidity-ratio difference (`moisture_removal_gkg`) while AC is on, under similar conditions over time. Interpret as a proxy, not measured removal.
- Compare peers with similar meter configuration and operating context; the same zone number on another floor does not ensure comparability. Match calendar period, time of day, initial conditions and weather where feasible for 2018/2019 comparisons.

### Historical first F3-Z1 modelling findings

July-August 2018 is the reference and July-August 2019 is evaluation, on inferred working days only. The reference is not known to be fault-free. The notebook compares existing cleaned values with source-observed values unchanged by cleaning, without new filling. Source data, the audit and shared helpers remain unchanged.

- **Energy:** complete 1,440-minute AC-plus-plug days; temperature-plus-plug reference selected by expanding 2018-only validation (MAE 8.89 kWh/day, versus 9.62 for a mean-only benchmark). Under supported conditions, 2019 departures are **−9.0% with fills** (25 days; conditional 95% interval −11.8% to −5.4%) and **−10.2% without fills** (12 days; −13.0% to −6.7%). Alternative temperature/enthalpy specifications agree in direction on the same jointly supported days.
- **Recorded moisture:** complete steady-on hours, after at least 120 continuous AC-on minutes, with outdoor humidity ratio, outdoor temperature, plug activity and session as predictors. Supported indoor humidity-ratio departures are **−0.40/−0.41 g/kg** with/without fills, from 34 hours/18 days and 15 hours/10 days respectively. Exact clock hour and elapsed run time are not regression controls; descriptive clock-hour checks agree in direction. Higher RH alongside lower temperature does not imply more absolute moisture.
- **Cooling:** 2019 starts begin about 2.4°C cooler. Only **1/78** fills-allowed and **0/71** observed-only 2019 events lie within the reference conditions, so an adjusted comparison is inconclusive and withheld. Do not label slower unadjusted cooling as decline.
- **Support and uncertainty:** coefficients use 2018 only. Reported comparisons require predictors inside the 2018 convex hull, at least 10 supported evaluation days and four calendar weeks in each year. This is a project reporting gate, not a scientific standard. Day-balanced estimates use 2,000 calendar-week bootstrap replicates with fixed specification and supported cohort. Intervals do not establish causation or future fault probability.
- **Filling sensitivity:** excluding filled readings reduces eligible 2019 energy days from 40 to 16 and eligible 2018 cooling events from 81 to 29. Common retained observations agree exactly across variants. Numerical interpolation effects and cohort selection are distinguished in the notebook; individual event slopes can still be affected.
- **Interpretation:** this first pass did not establish AC decline or improved efficiency/dehumidification. Clock alignment, sensor calibration, controls and operating changes remain unresolved. Its CUSUM is an exploratory record over available days, includes flagged extrapolations and has no fault decision threshold. The expansion below supersedes the old F3-Z1-only review boundary, while preserving its evidence.

### Current 20-zone screen and inspection leads

The user authorised expansion after reviewing F3-Z1. The active notebook is still `notebooks/bq2_ac.ipynb`; the historical first-pass notebook is available in Git commit `b56f716`. Current outputs are in `outputs/bq2-zone-screen/`, including a separate `inspection_shortlist.csv` with all 20 unique `floor, zone` keys. This is exploratory triage, not a new final handover schema or composite fault score.

- **Quality before fitting:** 20 source-file timelines, 95 relevant channel quality records and 80 hourly comparisons are checked. Parse Floor 7's raw day-first dates with `%d/%m/%y %H:%M`, matching upstream cleaning. Floor 6 has one malformed final row without measurements; record and exclude only that local empty row. Reindex absent tail minutes to missing. Raw/cleaned sources stay unchanged.
- **QA holds:** F4-Z1 AC1/AC3 and F7-Z1 AC1 are near-all-zero in the requested windows. Verify whether channels are inactive, unmapped or faulty; zero power is not a diagnosis. Hold meter-dependent comparisons pending that check. Hold F5-Z1 environmental comparisons for unusual cold readings/unknown placement or calibration, but assess energy separately. Other ordinary zones show no requested-window hour-long paired exact sensor plateau; this does not certify calibration.
- **Same underlying definitions:** dynamic meter lists handle one/four-meter zones, while original F3-Z1 features and energy/moisture departures are reproduced. No shared-helper changes. Existing cleaned inputs are compared against present source readings unchanged by cleaning, with no new filling or scaling of partial days. Minute coverage alone does not establish complete-day eligibility.
- **Additional model gates:** at least 20 reference days and four reference weeks; at least 10 supported evaluation days and four evaluation weeks for a reported departure. Support is the 2018 predictor convex hull, separated by session for environmental comparisons. All fits/energy selection use 2018 only, with day balancing and 2,000 week-bootstrap replicates. The rules are project screening choices, not validated engineering thresholds.
- **Validation and tiers:** stronger inspection leads require the reference CV MAE to beat a mean-only reference and a consistent adverse direction across both versions' nominal intervals. A separate validate-reference queue preserves descriptive leads when both input versions and a mean-only sensitivity on the exact same supported evaluation rows agree, while retaining the weak-model caution. No multiplicity correction is applied across zones; agreement between overlapping input versions is not independent replication.
- **F3-Z4, stronger energy/controls lead:** +13.3% with fills (22 supported days) and +15.2% without (10 days). Reference validation improves on the simple benchmark. Recorded moisture is lower and cooling remains incomparable, so inspect controls/schedules/load before attributing efficiency loss.
- **F5-Z4, energy change with reference caution:** +36.7% in both versions (23 supported days each). The weather reference has MAE 15.12 versus 11.75 kWh/day for the simple mean; it is not reliable evidence of a weather-adjusted efficiency change. Mean-only sensitivity on the same days is still +33.0%, supporting an operating/energy investigation.
- **F7-Z2, environmental lead with reference caution:** indoor humidity-ratio departures +1.15/+1.14 g/kg from 33/29 supported days. Observed-only validation MAE 0.284 versus 0.272 for the mean misses the stronger tier. Mean-only sensitivity agrees at +1.17/+1.16 g/kg. Cross-check sensors, moisture loads, ventilation/infiltration and AC operation with Track A; no measured coil removal or confirmed mould is inferred.
- **Provisional filling-dependent leads:** F5-Z2 (+24.7% energy) and F6-Z4 (+9.7%) have positive fills-allowed departures but no complete observed-only 2018 energy reference days. The shortlist retains them for reference/data follow-up rather than promoting them into the consistent two-version inspection group. The strict complete-day rule can cause this even at roughly 98-99% observed minute coverage.
- **Controls context:** eligible fills-allowed steady-on temperature means fall from 21.4 to 17.9°C in F3-Z4 and 23.9 to 19.9°C in F5-Z4. These are different descriptive cohorts, not controlled setpoint measurements. Check controls and sensor behaviour before attributing higher energy to declining efficiency.
- **Limits and unresolved zones:** no zone has a reportable adjusted cooling comparison under these rules. F3-Z1/F3-Z2 show lower supported energy as operating-change context. Other results retain reasons for insufficient reference data, unsupported conditions or weak models. Do not call unreported zones healthy. No final `zone_ac_metrics.csv`, joint risk matrix, fault threshold, seasonal generalisation or RUL result has been produced.

### Focused case investigation and confidence limits

The user requested a closer check after the 20-zone screen. The diagnostic companion reads only F3-Z4, F5-Z4 and F7-Z2 within July-August 2018/2019, with both input versions. It preserves all earlier evidence folders and uses the existing shared psychrometrics.

- **Documented measurement caveat:** the [dataset paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7371880/) reports ceiling mounting and sensor removal for a firmware update between September 2018 and March 2019. Nominal design values are ±0.4°C/±2 RH percentage points. These do not verify continuity, field calibration or unchanged local placement across years.
- **Electrical accounting:** decompose raw daily mean energy as mean on-hours × pooled on-power plus below-threshold energy. Symmetric runtime/power contributions reconcile exactly. The comparison uses all 2018 reference days and the screen's supported 2019 days. These accounting terms are not causal contributions to the earlier weather-model residual.
- **F3-Z4:** on-hours rise from 6.75 to 7.24/7.27 h/day and pooled on-power from 19.39 to 20.59/20.78 kW with/without fills. Below-threshold time inside fixed 08:00–11:00/13:15–16:15 windows falls from about 25 to 1/0 minutes/day. Median start/stop times move only a few minutes. Report a more continuous metered operating pattern; do not claim a large schedule extension, thermostat change or confirmed degradation.
- **F5-Z4:** runtime remains about 7.45 h/day, while on-power rises 15.13→20.10 kW. About 99.4% of the unadjusted energy difference is an on-power accounting contribution. Control/load/equipment or metering changes remain unverified; actual overcooling and efficiency loss cannot be established.
- **Inactive controls:** full-hour T/RH/AC/plug data are matched on exact clock hour/state, outdoor temperature, outdoor humidity ratio and plug activity. A separate control requires at least 24 uninterrupted hours of measured AC ≤0.1 kW. F3-Z4/F5-Z4 still show substantially cooler readings in that control. The absolute temperature shift cannot be attributed wholly to active cooling; sensor baseline, placement, other spaces and ambient/thermal changes remain alternatives.
- **F7-Z2:** matched steady-on recorded moisture is +1.15/+1.16 g/kg with/without fills with little on-power change. Same-day on-minus-night associations shift about +1°C and +1 g/kg, on 35/30 paired days. July and August both retain the moisture lead. This is a possible performance/control issue, not confirmed dehumidification loss or a progressive failure trend. Normal runtime medians stay near 7.98 h; eight 2018 reference days exceed nine on-hours versus none in the supported 2019 cohort, so lower mean runtime is not a shorter routine schedule.
- **Sensor scenarios:** a common fixed bias barely changes F7-Z2's absolute moisture departure, but opposing year-specific nominal T/RH design-error scenarios can reduce it to around zero. This is an assumption-driven sensitivity, not a measured error estimate or confidence interval. Constant additive T/RH offsets cancel in the respective on-minus-night contrasts; nonlinear moisture, gain/placement changes and state-dependent errors do not necessarily cancel.
- **Methods:** these new state matches/contrasts are descriptive and do not add causal or inferential intervals. Require three candidate reference dates, ten evaluation/reference days and four weeks; stricter matching or paired-hour sensitivity can become unavailable and is withheld. Same-day contrasts are not a causal difference-in-differences design. Regional weather and unmeasured occupancy/ventilation/control states limit interpretation. Local peers have differing operations and missingness, and are context only.
- **Handover:** `case_conclusions.csv` records confident observations, competing explanations, degradation status, next checks and reusable reporting language. Prioritise sensor continuity/calibration plus control/meter/equipment records. No mechanical fault, mould condition, COP change or RUL estimate is confirmed. Keep the historical screen's findings and the newer attribution limits distinct.

### Consolidated Track B report and reuse limits

**Person B checklist coverage:** the verified July-August energy/residual and sustained-on moisture work does not complete every original Person B item. CUSUM is an exploratory historical F3-Z1 trace; no validated alert or all-zone CUSUM assessment exists. Startup feature extraction/comparability checks are implemented, but every adjusted cooling comparison is withheld and a fair deterioration trend is unavailable. Peer context is descriptive rather than controlled benchmarking. Cross-year comparison is restricted to supported July-August cohorts. Final `zone_ac_metrics.csv` and the joint matrix remain planned. The folder README and scope/presentation guide make these distinctions explicit.

**Presentation alignment:** the current Canva proposal still contains exact RUL, 30-day failure-warning, leak-diagnosis, real-time-engine and fixed-improvement ambitions beyond the measurements. Treat them as unvalidated proposal ideas, not achieved outputs. The course briefing prioritises a defensible building decision, transparent preparation, a fair comparison, useful action and a KPI; ML is optional. `w_out - w_in` is a supporting humidity-gap indicator. Electrical inputs and room-temperature slopes do not establish delivered cooling, COP or coil moisture removal. Proposed trial KPIs are not achieved savings or validated fault thresholds.

The report at `mould-ac-degradation/reports/track-b/track_b_report.md` is the human-facing consolidation of the existing 20-zone screen and focused case investigation, not another model or a final joint handover. Its adjacent `figures/` contains byte-identical copies of the two case charts. Keep relative asset links portable and preserve the original outputs/provenance when updating the narrative. The report links its calculations and analysis commit; do not silently replace figures with a different cohort or rerun results during a prose-only update.

- **Reportable observations:** F3-Z4 has more continuous metered operation; F5-Z4 has higher on-power with nearly unchanged runtime; F7-Z2 has higher recorded moisture during sustained AC operation. Recommend sensor continuity/calibration checks and operating/control/meter/load investigation before assigning a mechanical cause.
- **Interpretation:** F3-Z4/F5-Z4 remain cooler after long near-zero-power periods, so actual overcooling is unverified. F7-Z2's absolute moisture change is sensitive to opposing year-specific nominal sensor-error scenarios; those scenarios are assumptions, not measured bias. Neither state associations nor electrical accounting establishes causation.
- **Reuse limits:** July-August 2018/2019 only; 2018 is not known fault-free; removing fills changes cohorts; some references miss simple benchmarks; nominal conditional intervals have no multiplicity correction. Strict complete-day rules reduce eligibility. No fair adjusted cooling comparison, validated CUSUM fault threshold, controlled peer ranking, COP, RUL, confirmed mechanical fault, measured coil moisture removal or mould finding is established. Missing occupancy, setpoints, ventilation, airflow, cooling output and maintenance/failure outcomes limit attribution. Lower energy and unavailable comparisons do not certify healthy equipment.
- **Next scope:** group review and later integration with Track A are separate steps. Broader seasonal/peer analysis, Track A and the joint risk matrix remain planned. The report does not complete those deliverables or establish recoverable savings.

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

- Never edit `data/` or `data-cleaning/outputs/`. Read from them; write analysis evidence to `mould-ac-degradation/outputs/` and report prose/bundled figures to `mould-ac-degradation/reports/`.
- One notebook per person/track to avoid merge conflicts. Shared logic goes in `bq2_utils.ipynb`.
- Baselines from clean, normal days only: `day_type == "working day"`. Never fit a baseline on the period it is evaluated on.
- Keep the notebook style used in `data-cleaning/main.ipynb`: markdown "what we're checking" → short code cell →
  "what this shows". State every threshold and assumption.
- Wording: say "risk indicator", "inspection priority", "signs of declining performance".
  Do not claim confirmed mould, faults or remaining useful life. Mould metrics use room-air sensors, not surface measurements.
- Small, separate commits with clear messages (e.g. "Add surface RH and time-of-wetness metrics").
- Restart the kernel after editing `bq2_utils.ipynb`, then rerun dependent notebooks. Coordinate shared definitions and record changes in the handover/PR; setup itself does not change them.
- Preserve partner work and Git history. Reuse an existing task branch/PR for related follow-ups while it remains open; start separate work from current `main` with a reviewable PR. The initial delivery used #1 setup → #2 audit → #3 first model → #4 zone screen → #5 case investigation/report. Retain remote branches until their work is verified on `main` and no open PR depends on them. Do not force-push shared history. Stage only intended files. Never commit `.venv`, credentials or temporary execution files.
- During setup, check dependencies, kernel launch, helper loading and input/weather joins without overwriting source notebooks or upstream outputs. Before handing off later analysis, rerun from a fresh kernel and report exactly what passed and what remains uncertain.
- Keep shared context in AGENTS.md and setup/run instructions in docs/setup.md, linked from README.md. CLAUDE.md remains a pointer. Update the owning document in the same change when methods, schemas or status change.
- For library/API/CLI-specific syntax or setup, resolve and fetch current documentation with the Context7 CLI before relying on remembered details. Never send credentials in documentation queries.

## Organisation and verification rules

- Put notebook entry points in `mould-ac-degradation/notebooks/`, reusable code in `src/bq2/`, automated tests/fixtures in `tests/`, run commands in `scripts/`, and human explanations in `reports/track-b/`. Keep raw/upstream data in their current owning folders.
- Run `python -m unittest discover -s mould-ac-degradation/tests -v` from the repository root for fast synthetic and integrity checks. For path/import or calculation changes, also run `python mould-ac-degradation/scripts/validate_notebooks.py`. It uses fresh kernels in `tests/.runs/`, compares regenerated outputs and preserves committed evidence.
- Historical JSON stores old source names/hashes. Do not rewrite it just to match moved modules. New scratch metadata records active paths and hashes; changed calculations require an explicitly reviewed evidence update.
- The frozen-evidence fixture protects original output files, bundled report charts and the shared helper. Scratch logs/copies remain ignored. Do not scatter temporary scripts, generated test outputs or verification notebooks at repository root.
