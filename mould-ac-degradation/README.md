# BQ2 analysis workspace

Start with the [teammate walkthrough](reports/track-b/person_b_scope_and_presentation.md) to understand Person B's work, or the [report](reports/track-b/track_b_report.md) for the findings and charts. [Setup](../docs/setup.md) and [shared AI context](../AGENTS.md) live at repository level.

## Where things belong

| Folder/file | Purpose | Start here |
|---|---|---|
| `notebooks/` | Executed analysis entry points | [Notebook order](notebooks/README.md) |
| `src/bq2/` | Reusable Python calculations | [input_audit.py](src/bq2/input_audit.py), [reference_models.py](src/bq2/reference_models.py), [zone_screen.py](src/bq2/zone_screen.py), [case_investigation.py](src/bq2/case_investigation.py) |
| `tests/` | Automated checks, synthetic inputs and evidence fingerprints | [Test guide](tests/README.md) |
| `scripts/` | Commands for complete validation | [validate_notebooks.py](scripts/validate_notebooks.py) |
| `outputs/` | Original calculation tables, figures and provenance | [Zone shortlist](outputs/bq2-zone-screen/inspection_shortlist.csv) |
| `reports/track-b/` | Human-facing explanations and review history | [Report index](reports/track-b/README.md) |
| `bq2_utils.ipynb` | Stable shared helper for both tracks | [Loading instructions](../docs/setup.md#shared-helper-loading-cell) |
| `requirements.txt` | Declared analysis dependencies | [requirements.txt](requirements.txt) |

Raw data, upstream cleaning and the weather cache retain their owning folders outside this workspace. The shared helper stays at its existing path so both tracks and historical input manifests continue to agree. New reusable code goes in `src/bq2/`; new automated checks go in `tests/`.

## Which notebook to use

1. [F3-Z1 input audit](notebooks/f3z1_input_audit.ipynb): understand quality and eligibility.
2. [Main Track B screen](notebooks/bq2_ac.ipynb): inspect all 20 zones and eligible comparisons.
3. [Case investigation](notebooks/bq2_case_investigation.ipynb): explain F3-Z4, F5-Z4 and F7-Z2.

The old first F3-Z1 notebook is preserved in [commit b56f716](https://github.com/Panhchaknut11/SBA_BQ2/blob/b56f716/mould-ac-degradation/bq2_ac.ipynb). Its evidence remains under `outputs/f3z1-first-pass/`, and the current screen checks parity against it. The reusable model definitions now live in `src/bq2/reference_models.py`.

## Test and reproduce

From the repository root with the environment active:

```bash
python -m unittest discover -s mould-ac-degradation/tests -v
python mould-ac-degradation/scripts/validate_notebooks.py
```

The first command runs small synthetic and repository-integrity checks. The second uses fresh kernels in an ignored scratch copy, compares regenerated results and preserves committed evidence. Its run records stay under `tests/.runs/`.

Track A, final AC handover fields and the joint matrix remain planned in this checkout. `inspection_shortlist.csv` is an intermediate output, not the final matrix. Organisation and testing do not expand the analysis window or establish physical faults.
