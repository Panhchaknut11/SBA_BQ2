# SBA_BQ2

Shared workspace for Panhchaknut and Lwin's IS4001 Smart Building Analytics final-project business question 2 (BQ2):

> How can seasonal weather changes, air-con performance and humidity levels be analysed to detect zones at risk of air-con degradation, mould growth, or both?

The intended result is an inspection shortlist supported by humidity exposure, AC behaviour and evidence quality. The readings do not establish confirmed mould, a particular mechanical fault or an exact failure date.

## Start here

- **Both AIs:** read [AGENTS.md](AGENTS.md), the canonical project context and working rules. [CLAUDE.md](CLAUDE.md) directs Claude to that same file.
- **People:** use this README for setup, notebook run order and Git workflow.
- **Current stage, 30 October 2026:** setup, the F3-Z1 input audit and the first F3-Z1 modelling pass are complete. Review [the executed Track B notebook](mould-ac-degradation/bq2_ac.ipynb) before expanding to other zones. Track A and the combined notebook remain planned.

## Responsibilities

| Track | Owner | Notebook | Planned handover |
|---|---|---|---|
| A: humidity and mould-risk indicators, including shutdown rebound | Panhchaknut | `bq2_humidity.ipynb` | `zone_mould_metrics.csv` |
| B: AC performance and signs of decline, including humidity response while AC runs | Lwin | `bq2_ac.ipynb` | `zone_ac_metrics.csv` |
| Combined inspection priorities | Both | `bq2_risk_matrix.ipynb` | Risk matrix and supporting cases |

The agreed scope is Floors 3-7, zones 1, 2, 4 and 5: 20 zones, subject to quality checks. Lighting analysis belongs to the other business question.

## Repository layout

```text
AGENTS.md                         Canonical context for both AIs
CLAUDE.md                         Claude entry point to AGENTS.md
README.md                         Setup and run instructions
data/                             14 raw floor/year CSVs; preserve unchanged
data-cleaning/
  main.ipynb                      Upstream cleaning implementation
  requirements.txt                Declared Python dependencies
  outputs/clean/                  14 committed cleaned minute-level CSVs
  outputs/analytics/              zone_hourly.csv, data_quality.csv, etc.
  outputs/figures/                Existing cleaning figures
baseline/
  humidity_risk_baseline.ipynb     Existing descriptive BQ2 baseline
  humidity_risk_baseline.py       Baseline functions and ERA5 loader
  _shared.py                     Baseline input helpers
  data/                          Committed Bangkok ERA5 weather cache
  outputs/                       Existing baseline tables and figures
  lighting_peak_baseline.*        Other question's baseline; preserve
mould-ac-degradation/
  bq2_utils.ipynb                 Existing shared helper notebook
  f3z1_input_audit.ipynb          Executed input audit, before modelling
  f3z1_audit.py                  Inspectable audit calculations
  f3z1_first_pass.py             F3-Z1 reference models and sensitivity checks
  requirements.txt              Base requirements plus Track B modelling dependencies
  bq2_humidity.ipynb              Planned, Track A
  bq2_ac.ipynb                    Executed first pass, F3-Z1 only
  bq2_risk_matrix.ipynb           Planned, combined
  outputs/f3z1-input-audit/       Audit tables, source hashes and figures
  outputs/f3z1-first-pass/        Model features, predictions, validation and figures
```

The helper is currently **`bq2_utils.ipynb`**. There is no `bq2_utils.py`; use the notebook-loading cell below rather than `from bq2_utils import ...`.

## Clone and create an environment

Each teammate needs their own checkout and local virtual environment. Clone the existing repository into your chosen project directory:

```bash
git clone https://github.com/Panhchaknut11/SBA_BQ2.git
cd SBA_BQ2
```

The initial setup uses Python **3.12** on macOS. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r mould-ac-degradation/requirements.txt
python -m ipykernel install --user --name sba-bq2 --display-name "SBA_BQ2 (Python 3.12)"
python -m pip check
```

The activation command is for macOS/Linux. Use your platform's virtual-environment activation equivalent on Windows. Install into `.venv`, not the system Python. Git ignores `.venv`; recreate it on each computer.

The BQ2 requirements include the base pandas, NumPy, Matplotlib, IPython kernel, JupyterLab and nbconvert dependencies, plus statsmodels and SciPy for Track B. Add any additional analysis dependency to the declared requirements before using it.

The 30 October environment resolved Python 3.12.16 with pandas 3.1.0, numpy 2.5.4, matplotlib 3.11.2, ipykernel 7.4.0, jupyterlab 4.6.5, nbconvert 7.17.2, statsmodels 0.15.0 and SciPy 1.18.1. The requirements use version ranges rather than a lockfile, so later installations may resolve different versions; rerun the setup checks after dependency changes. The first-pass `summary.json` records the analysis package versions and source hashes.

### Open notebooks

With `.venv` active, launch JupyterLab from the repository root:

```bash
python -m jupyterlab
```

Select **SBA_BQ2 (Python 3.12)** as the notebook kernel. In VS Code, open the repository folder and select that kernel or the `.venv/bin/python` interpreter.

Confirm the selected interpreter in a notebook:

```python
import sys
print(sys.executable)
```

It should point inside this checkout's `.venv`. Existing notebook metadata and older `data-cleaning/README.md` examples may mention `python3`, `sba-py315` or Python 3.15. Select `sba-bq2` explicitly instead of installing into an unrelated interpreter.

Inspect registered kernels with:

```bash
python -m jupyter kernelspec list
```

## Inputs and run order

All 14 raw files, 14 cleaned files, analytics tables and the ERA5 cache are committed. A new clone can read them without rerunning cleaning, uploading another dataset or refreshing weather.

1. Read `data-cleaning/README.md` and `data-cleaning/outputs/analytics/data_quality.csv` for provenance and flags.
2. Inspect the existing humidity baseline. Importing its weather loader does not rerun the baseline analysis.
3. Run BQ2 notebooks from `mould-ac-degradation/` using the cell below.
4. Once implemented, run Track A and Track B before the combined risk-matrix notebook.

Rebuild cleaning or baseline outputs only when that upstream work is deliberately in scope. Existing cleaning fills short gaps of at most 15 minutes; account for that when validating start-up rates and exposure episodes.

### First cell for a BQ2 notebook

Use an IPython/Jupyter notebook with `mould-ac-degradation/` as its working directory:

```python
from pathlib import Path
import sys

RUN_CHECKS = False
%run -i ./bq2_utils.ipynb

repo_root = Path.cwd().parent
assert (repo_root / "data-cleaning").is_dir(), "Run from mould-ac-degradation/"
CLEAN_DIR = repo_root / "data-cleaning" / "outputs" / "clean"
ANALYTICS_DIR = repo_root / "data-cleaning" / "outputs" / "analytics"
BASELINE_DIR = repo_root / "baseline"

sys.path.insert(0, str(BASELINE_DIR))
from humidity_risk_baseline import load_bangkok_era5_weather

weather = load_bangkok_era5_weather(
    BASELINE_DIR / "data" / "bangkok_era5_hourly_2018-2019.csv"
)
zh = load_zone_hourly(ANALYTICS_DIR / "zone_hourly.csv")
df = merge_weather(zh, weather)

print(f"{len(df):,} zone-hours across {df.groupby(['floor', 'zone']).ngroups} zones")
```

`%run -i` preserves the caller's `RUN_CHECKS = False` and loads helper definitions. To run the built-in checks, open `bq2_utils.ipynb` itself and run all cells from a fresh kernel. After helper edits, restart the kernel and rerun dependent notebooks. Saved outputs remain historical until rerun.

ERA5 is hourly regional reanalysis in Bangkok time, not an on-site station. Confirm the building timestamp convention before interpreting aligned readings.

## Git collaboration

Start from an up-to-date `main` and use a task branch:

```bash
git switch main
git pull --ff-only
git switch -c your-name/task-name
```

Use one analysis notebook per track. Coordinate shared-helper or output-schema changes before relying on them. Update the relevant documentation when methods, run instructions or project status change.

Review `git status` and `git diff`, stage the intended files explicitly, commit a small change, then push the branch and open a pull request into `main`. Save or commit local work before switching branches or pulling. Keep raw data, upstream outputs, virtual environments, credentials and temporary notebook executions out of setup commits.

## F3-Z1 input audit

Open [the executed audit notebook](mould-ac-degradation/f3z1_input_audit.ipynb). It checks raw/cleaned minute grids, filled readings, coverage, sensor flatlines, hourly export reconciliation, weather completeness and event-window eligibility. The calculations are in [f3z1_audit.py](mould-ac-degradation/f3z1_audit.py); exact tables, provenance and figures are under `mould-ac-degradation/outputs/f3z1-input-audit/`.

The main limitation is missingness: only 61.92% of the full period has jointly available cleaned AC/temperature/RH. There is a second environmental gap across late November-December 2019, in addition to the known 2018-2019 outage. July-August provides the clearest initial overlap, but interpolation affects 2018 event-window retention much more than 2019. Read the notebook's sample counts and sensitivity checks before selecting a comparison cohort.

With the environment active, rerun from the repository root:

```bash
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=sba-bq2 mould-ac-degradation/f3z1_input_audit.ipynb
```

This writes only the audit notebook and its own output folder. It does not regenerate upstream data or fit a model. Source hashes are checked again at the end of execution. Clock alignment and sensor drift cannot be certified by these checks.

## F3-Z1 first modelling pass

Open [bq2_ac.ipynb](mould-ac-degradation/bq2_ac.ipynb) after the input audit. It uses July-August 2018 as a reference and July-August 2019 for evaluation, comparing existing cleaned inputs against unchanged source observations. Coefficients and energy-model selection use 2018 only. Common support, day balancing and calendar-week uncertainty checks limit the comparison to the observed evidence.

| Supported 2019 departure from the reference | With existing fills | Without filled/replaced readings |
|---|---:|---:|
| Daily AC energy | −9.0%, 25 days | −10.2%, 12 days |
| Recorded indoor humidity ratio | −0.40 g/kg, 18 days | −0.41 g/kg, 10 days |
| Cooling response | Inconclusive, 1 supported event | Inconclusive, 0 supported events |

These findings do not establish AC decline or higher efficiency. Initial rooms are about 2.4°C cooler in 2019, leaving too little overlap for a fair cooling comparison. Higher RH accompanies cooler room temperatures and lower absolute moisture in the eligible readings. Operations, sensor calibration and clock alignment remain unresolved. Removing filled values changes cohort membership substantially; read the notebook's counts, conditional intervals and sensitivity checks before generalising.

Rerun from the repository root with `.venv` active:

```bash
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=sba-bq2 --ExecutePreprocessor.timeout=180 mould-ac-degradation/bq2_ac.ipynb
```

Calculations are in `mould-ac-degradation/f3z1_first_pass.py`. Outputs under `mould-ac-degradation/outputs/f3z1-first-pass/` include cohort/features tables, predictions with support flags, coefficients, 2018 validation, bootstrap summaries, sensitivity checks, two figures and provenance. CUSUM is diagnostic over available days, includes flagged extrapolations and has no fault threshold. No final zone handover scores are produced. The notebook checks source hashes and preserves raw/cleaned inputs, baseline outputs, the prior audit and shared helper. Review this pass before modelling other zones.

## Planning milestones

The group plan recorded on 18 October lists **3 November 2026** for analytics, **6 November** for recommendations/KPIs/slides and **9 November** for submission. These are working milestones; confirm the official eLearn upload cutoff. The updated course record places presentations in Week 14, with the exact presentation slot still unconfirmed.

The first F3-Z1 model findings are ready for review. Expansion to other zones, the remaining Track A/Track B work and the risk matrix follow separately after that review.

## Setup verification, 30 October 2026

- `python -m pip check` passed, and the JupyterLab entry point reported its installed version.
- The registered `sba-bq2` kernel launched and used this checkout's `.venv/bin/python`.
- The README's exact first cell executed successfully in that kernel: 263,520 unique zone-hours across all 20 scope zones, with complete weather matches.
- Known-value dew-point and humidity-ratio examples passed a separate import smoke check.

These setup checks establish environment and input-loading compatibility. The later audit and F3-Z1 modelling checks are recorded in their executed notebooks. Setup did not overwrite notebooks, raw data or upstream outputs, and its verification kernel was shut down.

## References

- [CU-BEMS original dataset paper](https://www.nature.com/articles/s41597-020-00582-3)
- [CU-BEMS dataset](https://www.kaggle.com/datasets/claytonmiller/cubems-smart-building-energy-and-iaq-data)
- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [IPython kernel installation](https://ipython.readthedocs.io/en/stable/install/kernel_install.html)
