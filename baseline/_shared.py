"""Shared input validation for baseline notebooks."""

from pathlib import Path

import pandas as pd


EXPECTED_FILES = [
    f"{year}Floor{floor}.csv"
    for year in (2018, 2019)
    for floor in range(1, 8)
]


def clean_data_directory():
    repo_root = Path(__file__).resolve().parents[1]
    clean_dir = repo_root / "data-cleaning" / "outputs" / "clean"
    missing = [name for name in EXPECTED_FILES if not (clean_dir / name).is_file()]
    if missing:
        examples = ", ".join(missing[:4])
        more = f" and {len(missing) - 4} more" if len(missing) > 4 else ""
        raise FileNotFoundError(
            "The cleaned CU-BEMS files are required before running this baseline. "
            f"Missing: {examples}{more}. Run data-cleaning/main.ipynb first; "
            "it writes the required files to data-cleaning/outputs/clean/."
        )
    return clean_dir


def read_clean_file(path, pattern):
    header = pd.read_csv(path, nrows=0).columns.tolist()
    selected = ["Date", *(column for column in header if pattern.fullmatch(column))]
    if len(selected) == 1:
        return None
    data = pd.read_csv(path, usecols=selected, parse_dates=["Date"])
    data = data.dropna(subset=["Date"]).set_index("Date").sort_index()
    if data.index.has_duplicates:
        raise ValueError(f"{path.name} contains duplicate timestamps.")
    return data
