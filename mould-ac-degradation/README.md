# BQ2 analysis workspace

Start with the [one-page overview](../README.md) or [detailed report](reports/track-b/track_b_report.md).

| Location | Purpose |
|---|---|
| [notebooks/](notebooks/README.md) | Executed input audit, 20-zone screen and focused investigation |
| [src/bq2/](src/bq2/) | Reusable calculation modules |
| [outputs/](outputs/) | Saved tables, charts and provenance; keep original evidence intact |
| [tests/](tests/README.md) | Shared automated checks and fixtures |
| [bq2_utils.ipynb](bq2_utils.ipynb) | Shared definitions for both tracks |
| [requirements.txt](requirements.txt) | Declared analysis dependencies |

Raw data, upstream cleaning and cached weather retain their owning folders. Historical first-pass outputs are still used by the screen's parity checks. Personal validation helpers stay local and ignored; dated notes live in the [archive](../docs/archive/README.md).
