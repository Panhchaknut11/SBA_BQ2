# BQ2 analysis workspace

This folder contains the shared BQ2 helpers and Lwin's current Person B work. Start with the [Person B scope and presentation guide](reports/track-b/person_b_scope_and_presentation.md) to understand the question, completed work, remaining gaps and presentation story. Read [AGENTS.md](../AGENTS.md) for shared context and the [root README](../README.md) for environment setup.

## Reading order

| Purpose | Open |
|---|---|
| Check our work against the friend's checklist and proposal | [Person B scope and presentation guide](reports/track-b/person_b_scope_and_presentation.md) |
| Read the findings, charts, recommendations and limitations | [Track B report](reports/track-b/track_b_report.md) |
| Inspect reproducibility and independent checks | [31 October review](reports/track-b/review_2026-10-31.md) and [verification JSON](reports/track-b/review_2026-10-31.json) |
| Understand input quality and why July-August was selected | [F3-Z1 input audit](f3z1_input_audit.ipynb) |
| Inspect all 20 zones and eligible metric comparisons | [Main Track B notebook](bq2_ac.ipynb) |
| Explain the three inspection cases | [Focused investigation](bq2_case_investigation.ipynb) |

## File responsibilities

```text
mould-ac-degradation/
  README.md                       Navigation and file responsibilities
  requirements.txt                Declared analysis dependencies
  bq2_utils.ipynb                  Shared definitions for both tracks
  f3z1_input_audit.ipynb           Executed input-quality audit
  bq2_ac.ipynb                     Current 20-zone Track B screen
  bq2_case_investigation.ipynb     Current three-case diagnostic companion
  f3z1_audit.py                    Audit calculations
  f3z1_first_pass.py               Reused feature/reference-model calculations
  bq2_zone_screen.py               Quality gates, screen and shortlist
  bq2_case_investigation.py        Operating/sensor diagnostics
  outputs/
    f3z1-input-audit/              Audit evidence and provenance
    f3z1-first-pass/               Preserved first-model evidence
    bq2-zone-screen/               Current 20-zone evidence
    bq2-case-investigation/        Current diagnostic evidence
  reports/track-b/
    person_b_scope_and_presentation.md  Scope, method reasoning and speaking outline
    track_b_report.md              Findings, recommendations and limitations
    review_2026-10-31.md / .json    Verification record
    figures/                       Two bundled report charts
```

Raw data belongs in `../data/`. Upstream cleaning, analytics exports and weather inputs retain their existing locations in `../data-cleaning/` and `../baseline/`. Analysis code reads those inputs and writes its own evidence under `outputs/`. Human-facing explanations belong in `reports/track-b/`.

The shared helper is a notebook. Load it with `%run -i ./bq2_utils.ipynb` after setting `RUN_CHECKS = False`, as shown in the root README. The module named `f3z1_first_pass.py` now also supplies calculations reused by the zone screen. The historical first F3-Z1 notebook is preserved in [commit b56f716](https://github.com/Panhchaknut11/SBA_BQ2/blob/b56f716/mould-ac-degradation/bq2_ac.ipynb); the current notebook at that path covers 20 zones.

Track A's `bq2_humidity.ipynb`, the combined `bq2_risk_matrix.ipynb` and the agreed final handover tables remain planned. Existing baseline humidity outputs do not complete Track A. The current 20-row `inspection_shortlist.csv` is an intermediate screening output, not the final joint risk matrix.

## Reproduction

Use the root README's environment and run commands. The dependency order is the input audit, main screen, then focused companion. The historical first-pass evidence is already committed and is checked by the current screen. Keep the calculation files in their existing locations because notebook imports, relative paths and evidence references depend on them. This navigation update moves no calculation or evidence file and adds no new model run.
