# Analysis notebooks

Use the `sba-bq2` kernel from the [setup guide](../../docs/setup.md).

| Order | Notebook | Purpose |
|---|---|---|
| 1 | [f3z1_input_audit.ipynb](f3z1_input_audit.ipynb) | Understand the inputs, gaps, filling and event eligibility |
| 2 | [bq2_ac.ipynb](bq2_ac.ipynb) | Audit and screen eligible comparisons across all 20 zones |
| 3 | [bq2_case_investigation.ipynb](bq2_case_investigation.ipynb) | Investigate F3-Z4, F5-Z4 and F7-Z2 |

Each setup cell locates the repository, imports `src/bq2/` and loads the unchanged shared helper at `../bq2_utils.ipynb`. Outputs remain in the sibling `outputs/` folder. Open the [Track B report](../reports/track-b/track_b_report.md) for the narrative, or the [teammate walkthrough](../reports/track-b/person_b_scope_and_presentation.md) for the internal discussion.

Running these notebooks directly regenerates their own evidence folders. For a validation run that preserves committed evidence, use the [scratch-run command](../tests/README.md#full-notebook-reproduction).
