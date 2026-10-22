#!/usr/bin/env python3
"""
tier_stability.py
How much of the ranking survives a change to the rubric's weights.

The weights in a rubric are a judgment. Nobody has fitted them to outcomes, so the fair
question is not "are they right" but "how much would the answer change if they were
wrong". This re-scores the current list with one criterion's weight raised or lowered,
re-ranks, and reports how much of the top of the list is still the same accounts.

It needs no re-run and no network: a criterion's weight scales the points it awards, and
the scored file already records the points each criterion awarded each account, so the
new score is arithmetic on columns that are already there.

Two ways of asking it are reported, because they answer different questions:
  - same_size: of the groups in the top tier today, how many are still in the top N by
    rank afterwards, where N is the size of the top tier today. This isolates the ORDER
    from the cut-off, and is the number to quote. It is symmetric: raising a weight can
    push a group out just as lowering one can.
  - fixed_cut: the same comparison against the rubric's written cut-off scores. Raising
    any weight lifts every score, so nothing falls below a fixed cut-off and this column
    reads 100% for every increase. That is the honest behaviour of editing a weight and
    leaving the cut-offs alone, which is why it is kept, but it measures the cut-off as
    much as the weight.

Usage:
  python3 scripts/tier_stability.py [--vertical <name>] [--factors 0.5 1.5] [--csv PATH]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402
from src.score import assign_tier  # noqa: E402
from src.settings import DEFAULT_VERTICAL  # noqa: E402

SCORED_PATH = RAW / "accounts_scored.csv"


def rank_groups(df: pd.DataFrame, score: pd.Series) -> pd.Series:
    """Group order for a set of scores, the same way score.py orders them: accounts best
    first, then each group takes the position of its best account."""
    ordered = df.assign(_score=score).sort_values(
        ["_score", "data_coverage", "name"], ascending=[False, False, True])
    return pd.Series(ordered.groupby("account_group", sort=False).ngroup().values,
                     index=ordered.index).sort_index()


def top_tier_groups(df: pd.DataFrame, score: pd.Series, tiers: list, names: set) -> set:
    """The groups whose best account lands in one of `names`, under these scores."""
    ordered = df.assign(_score=score).sort_values(
        ["_score", "data_coverage", "name"], ascending=[False, False, True])
    best = ordered.groupby("account_group", sort=False).first()
    return {g for g, row in best.iterrows() if assign_tier(row["_score"], tiers) in names}


def top_n_groups(df: pd.DataFrame, score: pd.Series, n: int) -> set:
    """The best n groups by rank under these scores, however the cut-offs are set."""
    ranks = rank_groups(df, score)
    return set(df.loc[ranks < n, "account_group"])


def compare(df: pd.DataFrame, base: pd.Series, changed: pd.Series, tiers: list, names: set) -> dict:
    was, now = top_tier_groups(df, base, tiers, names), top_tier_groups(df, changed, tiers, names)
    n = len(was)
    same_size = top_n_groups(df, changed, n)
    shift = (rank_groups(df, changed) - rank_groups(df, base)).abs()
    return {"same_size_kept_pct": round(100 * len(was & same_size) / n, 1) if n else 0.0,
            "swapped": n - len(was & same_size),
            "fixed_cut_size": len(now),
            "fixed_cut_kept_pct": round(100 * len(was & now) / n, 1) if n else 0.0,
            "median_places_moved": int(shift.median()), "worst_places_moved": int(shift.max())}


def main(vertical: str, factors: list, csv_path, tier_names: set) -> None:
    rubric = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "rubric.yaml"))
    tiers, criteria = rubric["tiers"], rubric["criteria"]
    df = pd.read_csv(SCORED_PATH)
    base = df["score"].astype(float)

    rows = []
    for name, criterion in criteria.items():
        column = f"pts_{name}"
        if column not in df:
            continue
        points = df[column].astype(float)
        for factor in factors:
            changed = base - points + points * factor
            rows.append({"change": f"{criterion['label']} ×{factor}",
                         "max_points": criterion["max_points"], **compare(df, base, changed, tiers, tier_names)})

    # Every criterion worth the same: the strongest disagreement with the author's weights.
    total = sum(c["max_points"] for c in criteria.values())
    flat = sum(df[f"pts_{n}"].astype(float) * (total / len(criteria) / c["max_points"])
               for n, c in criteria.items() if f"pts_{n}" in df)
    rows.append({"change": "every criterion weighted the same", "max_points": total,
                 **compare(df, base, flat, tiers, tier_names)})

    table = pd.DataFrame(rows)
    print(f"=== tier stability ({', '.join(sorted(tier_names))} groups, {len(df)} accounts) ===")
    print(table.to_string(index=False))
    worst = table.loc[table["same_size_kept_pct"].idxmin()]
    print(f"\nLeast stable: {worst['change']} keeps {worst['same_size_kept_pct']}% of the same number of "
          f"top groups ({worst['swapped']} swapped out).")
    print(f"Across every change tested, the share kept runs from {table['same_size_kept_pct'].min()}% "
          f"to {table['same_size_kept_pct'].max()}%.")
    if csv_path:
        table.to_csv(csv_path, index=False)
        print(f"\nWritten → {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--factors", type=float, nargs="+", default=[0.5, 1.5])
    parser.add_argument("--tiers", nargs="+", default=["A", "B"])
    parser.add_argument("--csv", default=None)
    args = parser.parse_args()
    main(args.vertical, args.factors, args.csv, set(args.tiers))
