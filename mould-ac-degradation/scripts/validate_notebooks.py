"""Run the current notebooks in a scratch copy and reconcile saved evidence.

From the repository root:
    python mould-ac-degradation/scripts/validate_notebooks.py

Runs and logs live under tests/.runs/ (ignored by Git). Source datasets, the
weather cache and committed output tables are never regenerated in place.
"""

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import nbformat
from nbclient import NotebookClient
import pandas as pd

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ANALYSIS_DIR.parent
NOTEBOOKS = ["f3z1_input_audit.ipynb", "bq2_ac.ipynb", "bq2_case_investigation.ipynb"]
REGENERATED = ["f3z1-input-audit", "bq2-zone-screen", "bq2-case-investigation"]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def protected_files():
    files = [p for p in (ANALYSIS_DIR / "outputs").rglob("*") if p.is_file()]
    files += list((ANALYSIS_DIR / "reports/track-b/figures").glob("*.png"))
    files += [ANALYSIS_DIR / "bq2_utils.ipynb"]
    return {str(p.relative_to(REPO_ROOT)): digest(p) for p in files}


def prepare_scratch(run_dir):
    scratch = run_dir / "scratch"
    scratch.mkdir()
    for name in ["data", "data-cleaning", "baseline"]:
        source = REPO_ROOT / name
        if not source.is_dir():
            raise FileNotFoundError(f"Required committed input folder is missing: {source}")
        (scratch / name).symlink_to(source, target_is_directory=True)
    for name in ["AGENTS.md", "README.md", "CLAUDE.md"]:
        shutil.copy2(REPO_ROOT / name, scratch / name)
    shutil.copytree(ANALYSIS_DIR, scratch / ANALYSIS_DIR.name,
                    ignore=shutil.ignore_patterns(".runs", "__pycache__"))
    return scratch / ANALYSIS_DIR.name


def compare_outputs(scratch_analysis):
    tables, figures, metadata_changes = [], [], []
    for folder in REGENERATED:
        original = ANALYSIS_DIR / "outputs" / folder
        generated = scratch_analysis / "outputs" / folder
        for path in sorted(original.iterdir()):
            other = generated / path.name
            if path.suffix == ".csv":
                a, b = pd.read_csv(path), pd.read_csv(other)
                pd.testing.assert_frame_equal(a, b, check_dtype=False, rtol=1e-9, atol=1e-9)
                tables.append({"path": str(path.relative_to(ANALYSIS_DIR)), "rows": len(a)})
            elif path.suffix == ".png":
                if path.read_bytes() != other.read_bytes():
                    raise AssertionError(f"Figure changed and requires review: {path.name}")
                figures.append(str(path.relative_to(ANALYSIS_DIR)))
            elif path.suffix == ".json":
                a, b = json.loads(path.read_text()), json.loads(other.read_text())
                if a != b:
                    metadata_changes.append({"path": str(path.relative_to(ANALYSIS_DIR)),
                                             "changed_fields": sorted(k for k in set(a) | set(b)
                                                                      if a.get(k) != b.get(k))}
                                            if isinstance(a, dict) and isinstance(b, dict)
                                            else {"path": str(path.relative_to(ANALYSIS_DIR)),
                                                  "changed_fields": ["input manifest"]})
    return tables, figures, metadata_changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", default="sba-bq2", help="Registered Jupyter kernel name")
    parser.add_argument("--save-executed", action="store_true",
                        help="After all checks pass, refresh only the three saved notebook outputs")
    options = parser.parse_args()
    run_parent = ANALYSIS_DIR / "tests/.runs"
    run_parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="notebooks-", dir=run_parent))
    before = protected_files()
    report = {"status": "running", "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(), "notebooks": [],
        "versions": {p: metadata.version(p) for p in ["pandas", "numpy", "scipy", "statsmodels", "matplotlib"]}}
    print(f"Scratch run: {run_dir}", flush=True)
    try:
        scratch_analysis = prepare_scratch(run_dir)
        for name in NOTEBOOKS:
            path = scratch_analysis / "notebooks" / name
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            started = time.monotonic()
            print(f"Running {name}", flush=True)
            NotebookClient(notebook, timeout=300, kernel_name=options.kernel,
                           resources={"metadata": {"path": str(path.parent)}}).execute()
            nbformat.write(notebook, path)
            report["notebooks"].append({"path": "notebooks/" + name, "status": "passed",
                                        "code_cells": sum(c.cell_type == "code" for c in notebook.cells),
                                        "elapsed_seconds": round(time.monotonic() - started, 2)})
            print(f"Passed {name}", flush=True)
        tables, figures, changes = compare_outputs(scratch_analysis)
        if protected_files() != before:
            raise AssertionError("Committed evidence or the shared helper changed during validation")
        report.update(status="passed", regenerated_csv_tables=tables,
                      identical_regenerated_figures=figures, metadata_differences=changes,
                      protected_files_unchanged=len(before),
                      historical_first_pass="Preserved and checked by the current screen; not rerun here")
        if options.save_executed:
            for name in NOTEBOOKS:
                shutil.copy2(scratch_analysis / "notebooks" / name, ANALYSIS_DIR / "notebooks" / name)
        print(f"Verified {len(tables)} regenerated CSV tables, {len(figures)} identical figures "
              f"and {len(before)} unchanged evidence/helper files.", flush=True)
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        (run_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Record: {run_dir / 'validation.json'}", flush=True)


if __name__ == "__main__":
    main()
