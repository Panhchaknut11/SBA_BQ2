# Tests

From the repository root with its environment active:

```bash
python -m unittest discover -s mould-ac-degradation/tests -v
```

The shared suite checks input quality, complete-day energy, temporal separation, reference support, matching, energy accounting, notebook structure, documentation links and frozen evidence. It runs in GitHub Actions without loading the large building CSVs.

The two tests in `test_notebook_validation.py` concern a personal notebook runner. They run when that ignored local tool is available and explicitly skip on a fresh checkout: **25 shared checks plus two optional local checks**. The analysis tests and their assertions are unchanged.

`fixtures/frozen_evidence_sha256.json` protects original outputs, report charts and the shared helper. Keep historical results/provenance intact. Dated verification records are in the [archive](../../docs/archive/README.md).

Full notebook verification uses fresh kernels in scratch storage, with regenerated outputs compared against saved evidence. Personal tools live in ignored `.local/`, and temporary notebook copies/logs in ignored `tests/.runs/`; they are not distributed with the repository. Direct notebook execution regenerates its own output folder, so use a scratch copy when preserving evidence.
