"""
Which saved briefs and sequences still match the current scored account list.

A saved brief or sequence is current when its group still leads in a tier that gets
written text, and the facts saved in its file are exactly the facts the code builds from
the scored data now. Anything else is stale: the account was excluded since, the group's
lead changed, or a fact changed when the list was re-scored. Stale text is left out of
the exports and the public build, and the next brief or sequence run writes it again.
"""

from pathlib import Path

import pandas as pd

from src.brief import build_facts


def saved_fact_texts(path: Path) -> list:
    """Fact texts from the '- **F1** text ([label](url))' lines of a saved file."""
    if not path.exists():
        return []
    texts = []
    for line in path.read_text().splitlines():
        if line.startswith("- **F") and "** " in line and " ([" in line:
            texts.append(line.split("** ", 1)[1].rsplit(" ([", 1)[0])
    return texts


def leads(scored: pd.DataFrame, tiers: list) -> dict:
    """{account_group: row} for each group's best account, in the given tiers."""
    rows = scored[(scored["rank_in_group"] == "1") & scored["tier"].isin(tiers)]
    return {r["account_group"]: r for r in rows.to_dict("records")}


def split(index: pd.DataFrame, scored: pd.DataFrame, tiers: list, facts_cfg: dict, out_dir: Path) -> tuple:
    """Returns (current index rows, set of stale account_groups). Rows for groups that no
    longer lead in these tiers are dropped from both."""
    lead = leads(scored, tiers)
    keep, stale = [], set()
    for row in index.to_dict("records"):
        group = row["account_group"]
        if group not in lead:
            continue
        expected = [f["text"] for f in build_facts(lead[group], facts_cfg)]
        if row.get("file") and saved_fact_texts(out_dir / row["file"]) == expected:
            keep.append(row)
        else:
            stale.add(group)
    return pd.DataFrame(keep, columns=index.columns), stale
