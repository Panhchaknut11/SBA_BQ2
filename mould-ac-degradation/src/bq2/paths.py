"""Locate the checkout without depending on the terminal's working directory."""

from pathlib import Path


def find_repo_root(start=None):
    """Find the nearest ancestor containing the BQ2 project markers."""
    current = Path(start) if start is not None else Path(__file__)
    current = current.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if ((candidate / "AGENTS.md").is_file()
                and (candidate / "mould-ac-degradation/bq2_utils.ipynb").is_file()):
            return candidate
    raise FileNotFoundError(f"No SBA_BQ2 checkout found above {current}")
