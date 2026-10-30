# Tests and reproducibility

Run these commands from the repository root with its `.venv` active. Tests use Python's built-in `unittest`; no additional test framework is needed.

## Fast checks

```bash
python -m unittest discover -s mould-ac-degradation/tests -v
```

| File | What it protects |
|---|---|
| [test_input_quality.py](test_input_quality.py) | Valid channels, complete-day energy, all-meter sums, source-only sensitivity and continuous startup windows |
| [test_reference_models.py](test_reference_models.py) | Day weighting, a known reference relationship, temporal separation, convex support/session checks and deterministic week resampling |
| [test_case_diagnostics.py](test_case_diagnostics.py) | Independent energy accounting, matching calipers and long-inactive control rules |
| [test_repository.py](test_repository.py) | Project discovery, notebook structure, local documentation links, frozen evidence and all 20 shortlist keys |
| [test_notebook_validation.py](test_notebook_validation.py) | Fresh scratch outputs and rejection of missing/unexpected results |
| [_support.py](_support.py) | Small synthetic inputs and shared test imports |
| [fixtures/frozen_evidence_sha256.json](fixtures/frozen_evidence_sha256.json) | Original evidence/chart/helper fingerprints for this structural migration |

The calculation tests use synthetic data. Repository checks read the existing small evidence files; the large raw/cleaned input CSVs are not loaded. Tests write temporary files outside the source tree and clean them up automatically.

The [BQ2 GitHub Actions workflow](../../.github/workflows/bq2-tests.yml) runs this same fast suite for pull requests and pushes to `main`. Full notebook reproduction is a separate local check using the committed datasets.

## Full notebook reproduction

```bash
python mould-ac-degradation/scripts/validate_notebooks.py
```

This runs the audit, screen and case companion from fresh kernels in a scratch copy under `tests/.runs/`. Current output folders are removed from that copy before execution, so every compared result must be regenerated. It checks the expected CSV/PNG file sets, compares regenerated values/images with the committed evidence and verifies that original outputs/shared helpers remain unchanged. The historical first-pass evidence is preserved and its F3-Z1 parity checks run in the current screen. Raw data, upstream outputs and the weather cache are reused, with no cache refresh.

`tests/.runs/` contains local execution logs, scratch outputs and `validation.json`; Git ignores it. Failed runs remain there for diagnosis. Remove an individual run folder when its local evidence is no longer needed. Do not commit these scratch copies.

For an intentional notebook-source update, add `--save-executed` after reviewing the changes. This refreshes the three notebook outputs only after successful reproduction. It does not overwrite committed analytical CSV/PNG evidence. Use `--kernel python3` if that is the correctly configured local kernel instead of `sba-bq2`.

## Historical provenance

Old JSON evidence records the code names and hashes that existed at the original run. The source modules now live under `src/bq2/`; the migrated notebooks record the active source-file paths and hashes in scratch-run metadata. Historical JSON remains unchanged. A deliberate new analysis result needs review of its CSVs, figures, claims and provenance before updating the frozen-evidence fixture.

The [reorganisation verification record](evidence/reorganisation_2026-10-31.json) records the migration's fresh notebook run, output comparisons, module hashes and setup-cell checks. The new tests also exposed an empty-startup-list dtype edge case; its fix preserves a usable datetime column and does not change existing analytical results.

The [PR #6 review record](evidence/pr6_review_2026-10-31.json) records the later review, the scratch-output freshness fix, 27 passing tests and a new three-notebook reproduction with 52 matching tables, six identical charts and 89 unchanged protected files. Its file hashes identify the reviewed source; final remote CI and merge status live on the PR.
