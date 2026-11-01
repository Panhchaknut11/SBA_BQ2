# SBA_BQ2 — Person B overview

**Purpose:** identify zones worth inspecting for changes in AC operation and indoor moisture. Panhchaknut owns humidity/mould analysis (Track A); Lwin owns AC analysis (Track B). The joint risk matrix is still pending.

## What we did

- Reused existing CU-BEMS building measurements and cached Bangkok weather.
- Audited 20 zones: Floors 3–7, zones 1, 2, 4 and 5.
- Compared July–August 2018 with 2019, using complete daily energy and continuous environmental/event windows.
- Repeated comparisons with and without filled readings, then investigated three leads.

## Findings to discuss

| Zone | Recorded change | Next check |
|---|---|---|
| F3-Z4 | Energy about 13–15% above the model reference; more continuous operation | Controls, operating modes and load |
| F5-Z4 | Operating power about 15.1 → 20.1 kW; runtime nearly unchanged | Controls, equipment/loading and metering |
| F7-Z2 | Matched sustained-on moisture about 1.15–1.16 g/kg higher | Sensor comparability, ventilation/moisture sources and AC operation |
| F3-Z1 | Supported energy and absolute moisture lower despite the earlier RH concern | Joint interpretation with Track A |

**Limits:** these are inspection leads, not confirmed AC faults or efficiency loss. Sensor comparability remains uncertain; some references are weak. Cooling comparisons were withheld, CUSUM is exploratory and controlled peer benchmarking remains pending. Removing fills changes the eligible sample. Results do not establish other seasons, measured coil moisture removal or mould.

## What we do together next

Compare Track A/B findings for the same zones and periods, especially F3-Z1 and F7-Z2. Agree the observations, coverage, uncertainty and next checks for each case, then build the joint matrix after Track A is available.

## Where to go

- [Detailed report and charts](mould-ac-degradation/reports/track-b/track_b_report.md): evidence, methods, recommendations and limitations.
- [Notebooks](mould-ac-degradation/notebooks/README.md): input audit → 20-zone screen → case investigation.
- [Setup](docs/setup.md) · [Calculation code](mould-ac-degradation/src/bq2/) · [Tests](mould-ac-degradation/tests/README.md) · [AI context](AGENTS.md).

From the repository root with the environment active:

```bash
python -m unittest discover -s mould-ac-degradation/tests -v
```

Original data, cleaning, weather, analysis code and saved results retain their existing locations. Personal validation tools stay local and ignored. Historical notes are in the [archive](docs/archive/README.md).
