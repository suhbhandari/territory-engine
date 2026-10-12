"""
Which saved briefs and sequences still match the current scored account list and checks.

A saved brief or sequence is current when:
  - its group still leads in a tier that gets written text,
  - the facts saved in its file (text, source label and link) are exactly the facts the
    code builds from the scored data now, and
  - its saved text passes the checks as they are now.
Anything else is stale. Stale text is left out of the exports and the public build, and
the next brief or sequence run writes it again. Collection dates on facts are not
compared, so a signal refresh alone does not make text stale.
"""

from pathlib import Path

import pandas as pd


def saved_facts(path: Path) -> list:
    """[(text, label, url)] from the fact lines of a saved file."""
    from src.brief import parse_fact_line

    if not path.exists():
        return []
    facts = [parse_fact_line(line) for line in path.read_text().splitlines() if line.startswith("- **F")]
    return [(f["text"], f["source_label"], f["source_url"]) for f in facts if f]


def leads(scored: pd.DataFrame, tiers: list) -> dict:
    """{account_group: row} for each group's best account, in the given tiers."""
    rows = scored[(scored["rank_in_group"] == "1") & scored["tier"].isin(tiers)]
    return {r["account_group"]: r for r in rows.to_dict("records")}


def split(index: pd.DataFrame, scored: pd.DataFrame, tiers: list, facts_cfg: dict, out_dir: Path,
          recheck=None) -> tuple:
    """Returns (current index rows, {stale account_group: reason}). Rows for groups that no
    longer lead in these tiers are dropped from both. `recheck(row, lead, facts)` returns the
    problems the current checks find in the saved text."""
    from src.brief import build_facts

    lead = leads(scored, tiers)
    keep, stale = [], {}
    for row in index.to_dict("records"):
        group = row["account_group"]
        if group not in lead:
            continue
        facts = build_facts(lead[group], facts_cfg)
        path = out_dir / row["file"] if row.get("file") else None
        if path is None or saved_facts(path) != [(f["text"], f["source_label"], f["source_url"]) for f in facts]:
            stale[group] = "facts changed"
        elif row.get("check_status") == "passed" and recheck and recheck(row, lead[group], facts):
            stale[group] = "fails current checks"
        else:
            keep.append(row)
    return pd.DataFrame(keep, columns=index.columns), stale


def current_briefs(index: pd.DataFrame, scored: pd.DataFrame, facts_cfg: dict, briefs_dir: Path) -> tuple:
    from src.brief import check_statements, saved_statements

    def recheck(row, lead, facts):
        statements = saved_statements((briefs_dir / row["file"]).read_text())
        return check_statements(statements, facts, lead["name"], facts_cfg.get("allowed_words", []))

    return split(index, scored, facts_cfg["tiers"], facts_cfg, briefs_dir, recheck)


def current_sequences(index: pd.DataFrame, touches: pd.DataFrame, scored: pd.DataFrame, seq_cfg: dict,
                      facts_cfg: dict, seq_dir: Path) -> tuple:
    from src.sequence import check

    ids = [t["id"] for t in seq_cfg["touches"]]

    def recheck(row, lead, facts):
        mine = touches[touches["account_group"] == row["account_group"]]
        result = {"touches": [{"touch_id": ids[int(t["touch"]) - 1], "subject": t["subject"], "body": t["body"],
                               "fact_ids": t["fact_ids"].split()} for t in mine.to_dict("records")]}
        return check(result, facts, lead, seq_cfg, facts_cfg.get("allowed_words", []))

    return split(index, scored, seq_cfg["tiers"], facts_cfg, seq_dir, recheck)
