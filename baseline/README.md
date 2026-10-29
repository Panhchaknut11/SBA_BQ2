# Baseline analysis

This folder contains two Jupyter notebooks for the proposal's analytics questions:

- [`lighting_peak_baseline.ipynb`](lighting_peak_baseline.ipynb): observed zone-level lighting and total-demand peaks, with a Floor 2 March-calibration/April-evaluation deep dive.
- [`humidity_risk_baseline.ipynb`](humidity_risk_baseline.ipynb): monthly humidity exposure, air-conditioning summaries, Bangkok ERA5 weather context, and an inspection-screening view for Floors 3–7 and zones 1, 2, 4, and 5.

## Run order and inputs

1. From `data-cleaning/`, run [`main.ipynb`](../data-cleaning/main.ipynb) to create the cleaned files in `outputs/clean/`.
2. Open either baseline notebook. Its first code cell checks that all 14 expected cleaned CSVs exist. It stops with an instruction to run the cleaning notebook if any are missing.
3. Run all cells. Both notebooks display the charts and a final baseline summary; reproducible tables and PNG charts are also written to `baseline/outputs/`.

The notebooks read only the cleaned source CSVs; they do not read raw files or substitute the existing analytics tables. They use pandas, NumPy, and Matplotlib, which are already listed in `data-cleaning/requirements.txt`.

The humidity notebook fetches hourly ERA5 weather from the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) for Bangkok (13.7563, 100.5018), 1 July 2018–31 December 2019, in `Asia/Bangkok` time. The first run requires internet access. It caches the source response at `baseline/data/bangkok_era5_hourly_2018-2019.csv`; subsequent runs use the cache. Remove that file to download again. The notebook exports hourly and monthly weather tables and joins weather variables to the indoor hourly/monthly analyses.

## Scope and limitations

The proposal's operating window (weekdays 08:00–18:00), 500-lux target, and 60% RH / six-hour screening thresholds are assumptions to test, not verified building requirements. No task-plane lux, actual occupancy, operating-state labels, maintenance records, or failure labels are included. Open-Meteo ERA5 is a city-level reanalysis estimate, not an on-site weather station. The humidity analysis uses weather as seasonal context and reports an exploratory AC-power-per-positive-temperature-difference ratio; neither is a calibrated, causal weather-adjusted efficiency estimate. The lighting notebook reports descriptive peaks rather than comfort-safe savings, and the humidity notebook supports inspection prioritisation rather than mould diagnosis, forecasting, or remaining-useful-life claims.
