# Shared BQ2 context for Codex and Claude

Read [README.md](README.md) for the one-page overview and [the Track B report](mould-ac-degradation/reports/track-b/track_b_report.md) for findings and limits. Keep detailed explanations there; this file owns working rules. Follow the user's current scope.

## Ownership, scope and status

- Panhchaknut: Track A, humidity and mould-risk indicators. Lwin: Track B, AC operation/performance indicators. Joint: case interpretation and the risk matrix.
- Building inputs: CU-BEMS, Bangkok office, minute readings from July 2018 to December 2019. Scope: Floors 3–7, zones 1, 2, 4, 5 (20 zones). Do not silently expand it.
- Track B audits all 20 zones and compares eligible July–August 2018/2019 observations with/without fills. F3-Z4, F5-Z4 and F7-Z2 are inspection leads; see the report for numbers and competing explanations.
- CUSUM remains exploratory, adjusted cooling comparisons are withheld, controlled peers and broader seasonal work remain pending. Track A, final AC handover fields and the joint matrix are not completed by the current Track B work.
- Immediate audience: an internal teammate discussion. The group Canva deck is outside the current change.

## Files and shared definitions

- `data/`: original inputs. `data-cleaning/`: shared preparation/exports. `baseline/`: earlier analyses and cached weather. Preserve them; do not rerun cleaning or refresh weather unless in scope.
- `mould-ac-degradation/notebooks/`: audit, main screen and case companion, in that order. Reusable code lives in `src/bq2/`; automated checks in `tests/`; results in `outputs/`; the detailed narrative in `reports/track-b/`.
- `mould-ac-degradation/bq2_utils.ipynb` is the unchanged shared helper for both tracks. Reuse its psychrometrics, loading and event definitions; do not create a competing `.py` helper. Coordinate changes and restart affected kernels.
- Loading: set `RUN_CHECKS = False`, locate the helper from the repository root and use `%run -i` with its quoted absolute path. The executable loading cell and `sba-bq2` kernel setup are in [docs/setup.md](docs/setup.md).
- Weather is hourly regional ERA5 in Bangkok time. A successful join does not verify the building clock. Approximate season labels are project conventions.
- `moisture_removal_gkg` is the legacy outdoor-minus-indoor humidity-ratio gap: a supporting indicator, not measured coil removal or an airflow-based rate.

## Quality and interpretation rules

- Preserve the existing complete-day, continuity, reference-support, benchmark and sample-size gates. Fit/select references using 2018 only; do not fit on evaluation data or relax gates to obtain a desired result.
- Daily energy requires all 1,440 valid AC-plus-plug minutes and every assigned AC meter. Missing periods stay unknown; do not scale partial days or turn gaps into zero use/risk.
- Upstream filling affects eligible samples and events. Retain the source-observed sensitivity and distinguish interpolation effects from changed cohorts. Working-day and plug-load labels are activity proxies, not occupancy measurements.
- Validate timestamp continuity separately from the shared event detector. Startup and sustained-on comparisons require their existing continuous environmental/power windows.
- Keep F5-Z1 environmental sensor concerns and F4-Z1/F7-Z1 near-zero meter flags visible. Other outages vary by channel; apply eligibility per metric instead of a blanket full-year exclusion.
- Sensor continuity/calibration/placement, clock alignment, occupancy, setpoints, ventilation, airflow, cooling output and maintenance/failure outcomes remain unverified or unavailable. Inactive-state and sensor-scenario checks limit causal interpretation.
- Report observations and inspection priorities. Do not infer confirmed faults, COP/efficiency loss, actual overcooling, coil moisture removal, mould, remaining useful life or achieved savings. An unavailable comparison or lower energy does not establish healthy equipment.
- Match Track A/B periods and eligible populations before combining results. Agree final units, sign conventions, coverage/status flags and field names before creating handover tables keyed by `floor, zone`. The current shortlist is intermediate evidence.

## Changes and verification

- Preserve partner work and Git history. Reuse an open task PR for related follow-ups; start independent work from current `main` on a reviewable branch. Stage intended files only; no force-pushes. Delete branches only after verified integration and no open dependency.
- Keep code, notebooks, inputs, results and test fixtures intact during documentation work. Historical JSON retains its original hashes/paths; archived reviews are dated evidence, not current execution instructions.
- Run `python -m unittest discover -s mould-ac-degradation/tests -v`. The two optional local-runner tests skip explicitly when the personal runner is absent; shared analysis/integrity tests must still run.
- For analysis/path changes, also verify affected notebooks from fresh kernels in scratch storage and compare outputs while preserving committed evidence. Personal validation tools belong in ignored `.local/`; scratch runs remain in ignored `tests/.runs/`. Do not upload those helpers or new execution logs to GitHub.
- Keep notebooks readable: short markdown explaining the check, a short code cell, then what the result shows. State thresholds and assumptions. Update the owning overview/report/setup document when definitions or status change, without duplicating it here.
- For library/API/CLI-specific syntax or setup, resolve and fetch current documentation through the Context7 CLI. Never include credentials in documentation queries.
