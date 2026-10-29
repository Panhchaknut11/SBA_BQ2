# Data cleaning

This folder holds the data-cleaning notebook for the CU-BEMS dataset. [`main.ipynb`](main.ipynb) reads the raw floor-level CSVs in [`../data/`](../data/). Anything it produces goes into [`outputs/`](outputs/). Its dependencies are listed in [`requirements.txt`](requirements.txt).

## What the notebook does

It follows six steps: **explore → plan segments and plots → plot to find problems → recommend actions → clean → plot again**. Step 7 exports the results, Section 8 lists every assumption, and Section 9 shows every before/after chart side by side.

It applies these data-quality principles:

- **The six problems:** missing, stale, noisy, misaligned, wrong context and too much data.
- **Bad data vs unusual operation:** bad data is cleaned or flagged, while unusual operation such as building closures is investigated and kept.
- **Cleaning is never hidden:** every removed reading is logged.

Issues it finds and fixes:

| Issue | Action |
|---|---|
| 2019 Floor 7 uses day-first dates (`D/M/YY H:MM`) | Parsed correctly; all files exported as `YYYY-MM-DD HH:MM:SS` |
| 2019 Floor 6 is cut off on 22 Oct 2019 and ends in a junk row | Junk row dropped; missing minutes kept as blank rows |
| ~450 power spikes, mostly logger bursts after a dropout (up to 4,762 kW) | Removed and filled by interpolation; each one logged in `removed_readings.csv` |
| Floor 5 zone 1 temperature reads 10–15 °C (sensor in AC air flow) | Readings below 15 °C removed and logged; sensor flagged in `data_quality.csv` |
| 28 weekdays with weekend-level energy (building closures) look like anomalies | **Kept, not deleted**: detected from the energy data alone and labelled with a `day_type` column (working day, weekend or closure) |
| Lux never exceeds ~140 (sensors probably not at desk height) | Kept; flagged as a relative indicator in `data_quality.csv` |
| Short gaps (≤ 15 min) | Linear interpolation |
| Long outages (e.g. all environmental sensors, Sep 2018 – Mar 2019) | Left blank, and documented |

## Outputs

Running the notebook (about 2 minutes) writes:

| Folder | Contents |
|---|---|
| `outputs/clean/` | The 14 source files in their original format (same names and columns), cleaned: about 750 MB in total |
| `outputs/analytics/` | `building_15min.csv`, `floor_15min.csv`, `zone_hourly.csv`, `daily_summary.csv`, `data_quality.csv`, `removed_readings.csv` |
| `outputs/figures/` | Every chart in the notebook as a PNG, ready for a report, including side-by-side before/after comparisons (`9_*.png`) |

## Run the notebook

Set up the Python environment from the repository root using the instructions in the root [`README.md`](../README.md). From a terminal, change to this folder before running the notebook:

```bash
cd data-cleaning
```

### Option A: VS Code

1. Open the repository folder in VS Code. The Python and Jupyter extensions must be installed.
2. Open `data-cleaning/main.ipynb`.
3. Click the kernel picker at the top right and choose **Select Another Kernel → Jupyter Kernel → Python 3.15 (SBA)**. If the kernel isn't listed, run **Developer: Reload Window** from the Command Palette.
4. Click **Run All**.

### Option B: JupyterLab

```bash
jupyter lab
```

Open `main.ipynb`. Choose **Kernel → Change Kernel → Python 3.15 (SBA)**, then **Run → Run All Cells**.

### Option C: Command line (no editor)

This runs every cell and saves the outputs back into the notebook:

```bash
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=sba-py315 main.ipynb
```

## Paths

All three options run the notebook with `data-cleaning/` as the working directory. Use paths relative to that folder:

```python
from pathlib import Path

DATA_DIR = Path("../data")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
```

## Adding packages

Install the package into the venv, then add it to [`requirements.txt`](requirements.txt) so others get it too:

```bash
pip install <package>
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Running cells with 'Python 3.15.0' requires the ipykernel package` | VS Code picked the system Python. Switch the kernel to **Python 3.15 (SBA)**. |
| `No such file or directory: 'requirements.txt'` or `'main.ipynb'` | You're not in this folder. Run `cd data-cleaning` from the repository root. |
| `FileNotFoundError` for a CSV | Check that the working directory is `data-cleaning/` (`import os; os.getcwd()`). |
| pandas fails to build | Install the Xcode Command Line Tools, or rebuild the venv with Python 3.14 and re-register the kernel. |

To remove the kernel later:

```bash
jupyter kernelspec uninstall sba-py315
```
