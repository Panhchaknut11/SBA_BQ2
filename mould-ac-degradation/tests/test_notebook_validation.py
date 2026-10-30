"""A reproduction check must fail when a notebook leaves outputs unwritten."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from _support import ANALYSIS_DIR

spec = importlib.util.spec_from_file_location(
    "bq2_notebook_validation", ANALYSIS_DIR / "scripts/validate_notebooks.py")
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class NotebookValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "source"
        self.analysis = self.root / "mould-ac-degradation"
        for name in ["data", "data-cleaning", "baseline"]:
            (self.root / name).mkdir(parents=True)
        for name in ["AGENTS.md", "README.md", "CLAUDE.md"]:
            (self.root / name).write_text("Synthetic test checkout\n")
        for folder in [*validation.REGENERATED, "f3z1-first-pass"]:
            target = self.analysis / "outputs" / folder
            target.mkdir(parents=True)
            (target / "result.csv").write_text("value\n1\n")
        self.patched = patch.multiple(validation, REPO_ROOT=self.root, ANALYSIS_DIR=self.analysis)
        self.patched.start()
        self.addCleanup(self.patched.stop)

    def test_scratch_run_cannot_inherit_current_results(self):
        run = Path(self.temporary.name) / "run"
        run.mkdir()
        scratch = validation.prepare_scratch(run)
        for folder in validation.REGENERATED:
            self.assertFalse((scratch / "outputs" / folder).exists())
            self.assertEqual((self.analysis / "outputs" / folder / "result.csv").read_text(),
                             "value\n1\n")
        self.assertTrue((scratch / "outputs/f3z1-first-pass/result.csv").is_file())
        self.assertEqual((scratch.parent / "data").resolve(), self.root / "data")
        with self.assertRaises(FileNotFoundError):
            validation.compare_outputs(scratch)

    def test_output_comparison_rejects_missing_and_unexpected_artifacts(self):
        scratch = Path(self.temporary.name) / "generated"
        for folder in validation.REGENERATED:
            target = scratch / "outputs" / folder
            target.mkdir(parents=True)
            (target / "result.csv").write_text("value\n1\n")
        tables, figures, changes = validation.compare_outputs(scratch)
        self.assertEqual((len(tables), len(figures), len(changes)), (3, 0, 0))
        target = scratch / "outputs" / validation.REGENERATED[0]
        (target / "result.csv").unlink()
        with self.assertRaisesRegex(AssertionError, "missing=.*result.csv"):
            validation.compare_outputs(scratch)
        (target / "result.csv").write_text("value\n1\n")
        (target / "unexpected.csv").write_text("value\n2\n")
        with self.assertRaisesRegex(AssertionError, "unexpected=.*unexpected.csv"):
            validation.compare_outputs(scratch)
