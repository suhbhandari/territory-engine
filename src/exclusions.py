"""
Accounts left out of scoring, and why. Two kinds:
  - out of territory: the account's zip is in the metro file's `exclude_zips`
  - reviewed: a person marked the account `exclude` in outputs/raw/exclusions.csv
    (columns entity_id, name, decision, reason). That file holds real names, so it
    lives with the raw data and is never committed. Rows with any other decision,
    or a blank one, are kept.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
REVIEW_PATH = ROOT / "outputs" / "raw" / "exclusions.csv"


def out_of_territory(accounts: pd.DataFrame, geo: dict) -> pd.Series:
    excluded = {str(z) for z in geo.get("exclude_zips", [])}
    return accounts["zip"].astype(str).str[:5].isin(excluded)


def reviewed_exclusions(path: Path = REVIEW_PATH) -> dict:
    """{entity_id: reason} for every row marked `exclude`."""
    if not path.exists():
        return {}
    review = pd.read_csv(path, dtype=str, keep_default_na=False)
    marked = review[review["decision"].str.strip().str.lower() == "exclude"]
    return dict(zip(marked["entity_id"], marked["reason"]))


def split(accounts: pd.DataFrame, geo: dict, reviewed: dict) -> tuple:
    """Returns (kept, excluded); excluded carries an `excluded_because` column."""
    reason = pd.Series("", index=accounts.index)
    reason[out_of_territory(accounts, geo)] = "outside territory (excluded zip)"
    by_review = accounts["entity_id"].map(reviewed)
    has_review = by_review.notna() & (reason == "")
    reason[has_review] = "reviewed: " + by_review[has_review].astype(str)
    excluded = accounts[reason != ""].assign(excluded_because=reason[reason != ""])
    return accounts[reason == ""].copy(), excluded
