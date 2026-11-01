# SBA_BQ2

Panhchaknut and Lwin's BQ2 workspace: use weather, AC operation and humidity observations to identify zones worth inspecting. Track A covers humidity/mould indicators; Track B covers AC operation. Findings remain inspection leads, with the joint matrix pending.

## Setup

Use Python 3.12. From the repository root (macOS/Linux):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r mould-ac-degradation/requirements.txt
python -m ipykernel install --user --name sba-bq2 --display-name "SBA_BQ2 (Python 3.12)"
python -m jupyterlab
```

Choose **SBA_BQ2 (Python 3.12)**. Each notebook loads the shared definitions and cached weather. Inputs and cleaned exports are already present; upstream cleaning and weather downloads need not be rerun.

## Run order

| Order | Notebook | Purpose |
|---|---|---|
| 1 | [F3-Z1 input audit](mould-ac-degradation/notebooks/f3z1_input_audit.ipynb) | Coverage, filling and usable comparison windows |
| 2 | [20-zone screen](mould-ac-degradation/notebooks/bq2_ac.ipynb) | Eligible July–August 2018/2019 comparisons, with/without fills |
| 3 | [Case investigation](mould-ac-degradation/notebooks/bq2_case_investigation.ipynb) | Operating/sensor explanations for F3-Z4, F5-Z4 and F7-Z2 |

The case investigation uses the screen's saved results. When inputs or shared definitions change, rerun in order. Direct execution updates each notebook's output folder; use a scratch copy to preserve existing evidence during verification.

## Code and findings

- [Detailed report](mould-ac-degradation/reports/track-b/track_b_report.md): findings, charts, recommendations and limitations.
- [Calculation modules](mould-ac-degradation/src/bq2/) and [shared functions](mould-ac-degradation/bq2_utils.ipynb).
- [Zone shortlist](mould-ac-degradation/outputs/bq2-zone-screen/inspection_shortlist.csv) and [case conclusions](mould-ac-degradation/outputs/bq2-case-investigation/case_conclusions.csv).
- [AI working context](AGENTS.md), also used through [CLAUDE.md](CLAUDE.md).

Original data, shared cleaning/baselines and saved results retain their locations. Development tests, validation tools and old review notes are kept locally rather than distributed with the project.
