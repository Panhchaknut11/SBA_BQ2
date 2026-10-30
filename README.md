# SBA_BQ2

Panhchaknut and Lwin's shared IS4001 Smart Building Analytics workspace. BQ2 asks how weather, AC behaviour and humidity can identify zones worth inspecting for AC or mould risk.

## Start here

| I want to… | Open |
|---|---|
| Explain Person B findings to my teammate | [Internal walkthrough](mould-ac-degradation/reports/track-b/person_b_scope_and_presentation.md) |
| Read the findings and charts | [Track B report](mould-ac-degradation/reports/track-b/track_b_report.md) |
| Explore or rerun the analysis | [Notebook index](mould-ac-degradation/notebooks/README.md) |
| Find calculation code, outputs or reports | [Analysis workspace](mould-ac-degradation/README.md) |
| Set up Python and Jupyter | [Setup and run guide](docs/setup.md) |
| Run tests or check reproducibility | [Test guide](mould-ac-degradation/tests/README.md) |
| Give either AI the project context | [AGENTS.md](AGENTS.md), also used through [CLAUDE.md](CLAUDE.md) |

## Folder structure

```text
SBA_BQ2/
  README.md                    Start here
  AGENTS.md / CLAUDE.md         Shared AI context
  docs/                        Setup and run instructions
  data/                        Original building CSVs
  data-cleaning/               Shared upstream cleaning and exports
  baseline/                    Earlier baselines and cached weather
  mould-ac-degradation/
    README.md                  BQ2 analysis index
    requirements.txt           Analysis dependencies
    bq2_utils.ipynb            Stable shared helper for both tracks
    notebooks/                 Executed audit, screen and case notebooks
    src/bq2/                   Reusable Python calculation modules
    tests/                     Automated tests and small fixtures
    scripts/                   Safe full-notebook validation command
    outputs/                   Preserved analysis tables, charts and provenance
    reports/track-b/            Findings, teammate guide and review records
```

Local environments, Python caches and `tests/.runs/` validation copies are ignored by Git. Raw inputs, upstream preparation and saved evidence each have an owning folder. Tests and validation scripts do not belong beside the report or notebook entry points.

## Run checks

After [environment setup](docs/setup.md), run from the repository root:

```bash
python -m unittest discover -s mould-ac-degradation/tests -v
```

For a fresh-kernel reproduction that preserves committed evidence:

```bash
python mould-ac-degradation/scripts/validate_notebooks.py
```

The [test guide](mould-ac-degradation/tests/README.md) explains test coverage, scratch outputs and historical provenance.
The fast suite also runs automatically through [GitHub Actions](.github/workflows/bq2-tests.yml) on pull requests and pushes to `main`.

## Current scope

Track B covers quality checks across 20 agreed zones and eligible July-August 2018/2019 comparisons. F3-Z4 shows more continuous metered operation, F5-Z4 higher on-power and F7-Z2 higher recorded sustained-on moisture. These are inspection leads. Sensor/operating uncertainty prevents confirmed mechanical-degradation, efficiency-loss or mould claims.

The original Person B checklist is partly complete: CUSUM is exploratory, fair adjusted pull-down comparisons are unavailable, and controlled peer benchmarking remains pending. Panhchaknut owns Track A; its integration, final handover tables and the joint risk matrix remain planned in this checkout. Read the report and scope guide for the evidence and limitations.

The earlier [five-PR review](mould-ac-degradation/reports/track-b/review_2026-10-31.md) records fresh execution and independent checks before this structural migration. Its dated source references remain historical. The analysis window, formulas and saved evidence are preserved by the reorganisation.

## Collaboration

Use the existing open task branch/PR for related follow-ups. Start later independent work from current `main`; review intended files before committing. Coordinate shared-helper/schema changes with the other track. Do not commit `.venv`, credentials, Python caches or scratch runs. The setup guide contains the detailed [Git workflow](docs/setup.md#git-workflow).
