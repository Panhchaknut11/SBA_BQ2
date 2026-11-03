# SBA_BQ2

Panhchaknut and Lwin's BQ2 workspace. Track A covers humidity/mould indicators; Track B checks AC electricity and indoor conditions. Both identify inspection priorities; the combined risk matrix is pending.

## Person B: three findings

We screened 20 zones and investigated three, comparing eligible **July–August 2018 and 2019** readings. Each finding remained with filled readings excluded, although eligible samples can differ.

| Zone | What changed | What to check |
|---|---|---|
| **F3-Z4** | More continuous operation: time above the AC-on threshold rose **6.75 → about 7.25 h/day**, with similar start/stop times. | Controls and fewer low-power periods within the working day. |
| **F5-Z4** | Higher operating power: **15.1 → 20.1 kW**, while runtime stayed near **7.45 h/day**. | Settings, load/equipment changes and metering. |
| **F7-Z2** | Approximately **1.15 g/kg more recorded moisture** during matched sustained AC operation, with little power change. | Sensor continuity, ventilation/moisture sources and AC operation together. |

**See the evidence:** [runtime and power](mould-ac-degradation/reports/track-b/figures/runtime_and_power.png) · [F7-Z2 moisture](mould-ac-degradation/reports/track-b/figures/f7z2_sustained_moisture.png) · [detailed report](mould-ac-degradation/reports/track-b/track_b_report.md).

These are recorded changes, not confirmed degradation or efficiency loss. Cross-year sensor-error scenarios can erase F7-Z2's moisture increase; actual overcooling is also unverified. Some zones lack a fair comparison. Next, align Track A/B periods and coverage before combining their inspection priorities.

## Run order

| Order | Notebook | Purpose |
|---|---|---|
| 1 | [F3-Z1 input audit](mould-ac-degradation/notebooks/f3z1_input_audit.ipynb) | Coverage, filling and usable comparison windows |
| 2 | [20-zone screen](mould-ac-degradation/notebooks/bq2_ac.ipynb) | Eligible July–August 2018/2019 comparisons, with/without fills |
| 3 | [Case investigation](mould-ac-degradation/notebooks/bq2_case_investigation.ipynb) | Operating/sensor explanations for F3-Z4, F5-Z4 and F7-Z2 |
| Independent | [Track A humidity](mould-ac-degradation/notebooks/bq2_humidity.ipynb) | Mould-risk indicators, moisture rebound and peer context |

The case investigation uses the screen's saved results. When inputs or shared definitions change, rerun in order. Direct execution updates each notebook's output folder; use a scratch copy to preserve existing evidence during verification.

## Setup and code

<details>
<summary>Python environment and starting Jupyter</summary>

Use Python 3.12. From the repository root (macOS/Linux):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r mould-ac-degradation/requirements.txt
python -m ipykernel install --user --name sba-bq2 --display-name "SBA_BQ2 (Python 3.12)"
python -m jupyterlab
```

Choose **SBA_BQ2 (Python 3.12)**. Notebooks load the shared definitions and cached weather. Inputs and cleaned exports are already present; upstream preparation need not be rerun.

</details>

- [Calculation modules](mould-ac-degradation/src/bq2/) and [shared functions](mould-ac-degradation/bq2_utils.ipynb).
- [Zone shortlist](mould-ac-degradation/outputs/bq2-zone-screen/inspection_shortlist.csv) and [case conclusions](mould-ac-degradation/outputs/bq2-case-investigation/case_conclusions.csv).
- [AI working context](AGENTS.md), also used through [CLAUDE.md](CLAUDE.md).

Original data, shared cleaning/baselines and saved results retain their locations. Development tests, validation tools and old review notes are kept locally rather than distributed with the project.
