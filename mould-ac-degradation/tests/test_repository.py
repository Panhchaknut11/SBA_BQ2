"""Check navigation and preserved evidence without reading the large raw CSVs."""

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

import nbformat
import pandas as pd

from _support import ANALYSIS_DIR, REPO_ROOT
from bq2.paths import find_repo_root


class RepositoryTests(unittest.TestCase):
    def test_project_discovery_is_independent_of_working_directory(self):
        self.assertEqual(find_repo_root(ANALYSIS_DIR / "notebooks"), REPO_ROOT)
        self.assertEqual(find_repo_root(), REPO_ROOT)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                find_repo_root(directory)

    def test_all_current_notebooks_validate_and_have_no_saved_errors(self):
        paths = list((ANALYSIS_DIR / "notebooks").glob("*.ipynb"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            with self.subTest(notebook=path.name):
                notebook = nbformat.read(path, as_version=4)
                nbformat.validate(notebook)
                for cell in notebook.cells:
                    if cell.cell_type == "code":
                        self.assertFalse(any(o.output_type == "error" for o in cell.get("outputs", [])))

    def test_owned_documentation_local_links_resolve(self):
        paths = [REPO_ROOT / name for name in ["README.md", "AGENTS.md", "CLAUDE.md"]]
        paths += list((REPO_ROOT / "docs").glob("*.md"))
        paths += [ANALYSIS_DIR / "README.md", ANALYSIS_DIR / "tests/README.md"]
        paths += list((ANALYSIS_DIR / "reports").rglob("*.md"))
        for path in paths:
            for raw in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', path.read_text()):
                if raw.startswith(("https://", "http://", "#", "mailto:")):
                    continue
                target = unquote(raw.split("#", 1)[0].strip("<>"))
                with self.subTest(document=str(path.relative_to(REPO_ROOT)), link=raw):
                    self.assertTrue((path.parent / target).exists())

    def test_frozen_evidence_and_shared_helper_remain_byte_identical(self):
        fixture = json.loads((ANALYSIS_DIR / "tests/fixtures/frozen_evidence_sha256.json").read_text())
        for relative, expected in fixture["files"].items():
            with self.subTest(file=relative):
                self.assertEqual(hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_shortlist_keeps_all_zones_and_cooling_is_withheld(self):
        outputs = ANALYSIS_DIR / "outputs/bq2-zone-screen"
        shortlist = pd.read_csv(outputs / "inspection_shortlist.csv")
        models = pd.read_csv(outputs / "model_summary.csv")
        self.assertEqual(len(shortlist), 20)
        self.assertFalse(shortlist.duplicated(["floor", "zone"]).any())
        self.assertFalse(models.query("analysis == 'cooling'").reportable.any())
        self.assertTrue(models.query("reportable").bootstrap_valid_replicates.ge(1800).all())
