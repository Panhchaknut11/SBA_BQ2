# Analysis notebooks

Use the `sba-bq2` kernel from the [setup guide](../../docs/setup.md).

| Order | Notebook | Purpose |
|---|---|---|
| 1 | [f3z1_input_audit.ipynb](f3z1_input_audit.ipynb) | Understand the inputs, gaps, filling and event eligibility |
| 2 | [bq2_ac.ipynb](bq2_ac.ipynb) | Audit and screen eligible comparisons across all 20 zones |
| 3 | [bq2_case_investigation.ipynb](bq2_case_investigation.ipynb) | Investigate F3-Z4, F5-Z4 and F7-Z2 |

Each setup cell locates the repository, imports `src/bq2/` and loads the unchanged shared helper at `../bq2_utils.ipynb`. Outputs remain in the sibling `outputs/` folder. Read the [one-page overview](../../README.md), then the [Track B report](../reports/track-b/track_b_report.md) for detail.

Running these notebooks directly regenerates their own evidence folders. Use a fresh kernel and a scratch copy to preserve committed evidence; the [test guide](../tests/README.md) explains shared checks and local verification.
