# Setup and run guide

Use a separate checkout and virtual environment on each computer. Read the [root index](../README.md) and [shared context](../AGENTS.md) first.

## Create the environment

The project uses Python 3.12. From your chosen project directory:

```bash
git clone https://github.com/Panhchaknut11/SBA_BQ2.git
cd SBA_BQ2
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r mould-ac-degradation/requirements.txt
python -m ipykernel install --user --name sba-bq2 --display-name "SBA_BQ2 (Python 3.12)"
python -m pip check
```

The activation command is for macOS/Linux. Use the platform equivalent on Windows. Python 3.12 must already be installed. Requirements use version ranges rather than a lockfile; the dated analysis records contain the versions used for the saved results.

The local environment was repaired on 31 October after its original Homebrew interpreter disappeared. `.venv` is ignored and not portable between machines. If its interpreter becomes unavailable, recreate the environment and reselect/register the kernel instead of changing analysis code.

## Open notebooks

```bash
python -m jupyterlab
```

Launch from the repository root and open the [notebook folder](../mould-ac-degradation/notebooks/README.md). Select **SBA_BQ2 (Python 3.12)**. In VS Code, select the same kernel or this checkout's `.venv/bin/python`.

Check the interpreter in a notebook:

```python
import sys
print(sys.executable)
```

It should point inside the checkout's `.venv`. Older upstream notebook metadata may mention other kernels; choose `sba-bq2` explicitly. Inspect registered kernels with `python -m jupyter kernelspec list`.

## Inputs and run order

The 14 raw CSVs, cleaned exports, analytics tables and weather cache are already committed. Read them in place. Do not rerun upstream cleaning or refresh weather just to open the BQ2 analysis.

| Order | Notebook | Role |
|---|---|---|
| 1 | [Input audit](../mould-ac-degradation/notebooks/f3z1_input_audit.ipynb) | Missingness, filling, sensor/event coverage and reconciliation |
| 2 | [Track B screen](../mould-ac-degradation/notebooks/bq2_ac.ipynb) | Quality gates and eligible comparisons for all 20 zones |
| 3 | [Case companion](../mould-ac-degradation/notebooks/bq2_case_investigation.ipynb) | Operating/sensor diagnostics for the three leads |

Their setup cells locate the repository from any subfolder, add `mould-ac-degradation/src/` to the Python path and load the stable shared helper. Notebook outputs use the analysis `outputs/` directory rather than the notebook working directory.

Direct execution regenerates that notebook's output folder. For a preservation-safe check of all three, use:

```bash
python mould-ac-degradation/scripts/validate_notebooks.py
```

See the [test guide](../mould-ac-degradation/tests/README.md) for the fast suite, scratch records and `--save-executed` option. Track A and the combined matrix remain planned; agree their entry paths and output contracts before implementing them.

## Shared-helper loading cell

The helper remains `mould-ac-degradation/bq2_utils.ipynb` for both tracks. There is no `bq2_utils.py` duplicate. This loading cell works from the repository or a notebook subfolder:

```python
from pathlib import Path
import sys

repo_root = next(p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
                 if (p / "AGENTS.md").is_file()
                 and (p / "mould-ac-degradation/bq2_utils.ipynb").is_file())
analysis_dir = repo_root / "mould-ac-degradation"
sys.path.insert(0, str(analysis_dir / "src"))
RUN_CHECKS = False
helper_notebook = analysis_dir / "bq2_utils.ipynb"
get_ipython().run_line_magic("run", f'-i "{helper_notebook}"')

sys.path.insert(0, str(repo_root / "baseline"))
from humidity_risk_baseline import load_bangkok_era5_weather
weather = load_bangkok_era5_weather(
    repo_root / "baseline/data/bangkok_era5_hourly_2018-2019.csv"
)
zh = load_zone_hourly(repo_root / "data-cleaning/outputs/analytics/zone_hourly.csv")
df = merge_weather(zh, weather)
print(f"{len(df):,} zone-hours across {df.groupby(['floor', 'zone']).ngroups} zones")
```

The `-i` run option preserves the caller's `RUN_CHECKS = False`. To run the helper's own historical checks, open the helper itself and run from a fresh kernel. After intentional helper edits, restart dependent kernels and rerun the affected analyses. Coordinate definition changes across tracks.

ERA5 provides hourly regional weather in Bangkok time. A successful join does not independently verify the building clock. Input flags, strict completeness rules and source-observed sensitivity still apply after loading.

## Git workflow

For related changes, reuse the existing open task branch and PR. For new independent work after prerequisites merge:

```bash
git switch main
git pull --ff-only
git switch -c your-name/task-name
```

Review `git status`/`git diff`, stage intended files explicitly, commit and push the branch, then open a reviewable PR into `main`. Save local changes before switching. Retire topic branches only after their work is verified on `main` and no open PR depends on them. Never force-push shared history.

PRs #1-#5 were integrated with merge commits in dependency order. [PR #5](https://github.com/Panhchaknut11/SBA_BQ2/pull/5) records that integration and its branch cleanup. Later task branches are separate work.
