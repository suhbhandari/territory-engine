"""
Phase 3: Account Scoring
Joins accounts with their signals, applies the vertical's rubric, and writes a ranked,
tiered account list where every point is traceable to a rule and a plain-language reason.

Usage:
  python3 src/score.py [--vertical <name>] [--metro config/metro/<name>.yaml]

Design:
  - The rubric (config/verticals/<name>/rubric.yaml) is a list of criteria. Each criterion
    has max_points and an ordered list of rules; the first rule that matches wins
  - A rule marked `known: false`, or a criterion where no rule matches, means the data to
    judge that criterion is missing. It scores its points (usually 0) but is tracked
    separately: data_coverage is the share of the rubric that was judged on real data,
    so a low score from missing data is distinguishable from a low score on evidence
  - Rule conditions are generic comparisons on columns; nothing here knows what a column means
  - Two derived columns are available to rules: website_domain, and domain_account_count
    (how many accounts in the list share that domain)
  - Accounts outside the territory (the metro file's exclude_zips) and accounts a person
    marked `exclude` in outputs/raw/exclusions.csv are left out before scoring, and written
    with the reason to outputs/raw/accounts_excluded.csv
  - Accounts that share a website domain are one group (one operator or network with
    several locations). Each account keeps its own score; the list is ordered by each
    group's best score with its members kept together, so a group takes one place
    in the ranking instead of several
"""

import argparse
import sys
import yaml
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.exclusions import reviewed_exclusions, split  # noqa: E402
from src.settings import DEFAULT_METRO, DEFAULT_VERTICAL  # noqa: E402

ACCOUNTS_PATH = ROOT / "outputs" / "raw" / "accounts_raw.csv"
SIGNALS_PATH = ROOT / "outputs" / "raw" / "signals_raw.csv"
OUTPUT_PATH = ROOT / "outputs" / "raw" / "accounts_scored.csv"
EXCLUDED_PATH = ROOT / "outputs" / "raw" / "accounts_excluded.csv"

ID_COL = "entity_id"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def matches(cond: dict, row: dict) -> bool:
    value = str(row.get(cond["column"], ""))
    op = cond["op"]
    target = cond.get("value")

    if op == "blank":
        return value == ""
    if op == "not_blank":
        return value != ""
    if op == "eq":
        return value == str(target)
    if op == "in":
        return value in [str(t) for t in target]
    if op == "contains":
        return str(target).lower() in value.lower()
    if op in ("gte", "lte", "between"):
        number = _num(value)
        if number is None:
            return False
        if op == "gte":
            return number >= target
        if op == "lte":
            return number <= target
        return target[0] <= number <= target[1]
    raise ValueError(f"unknown op {op!r}")


def score_criterion(criterion: dict, row: dict):
    for rule in criterion["rules"]:
        conditions = rule.get("when", [])
        if isinstance(conditions, dict):
            conditions = [conditions]
        if all(matches(c, row) for c in conditions):
            return rule["points"], rule.get("known", True), rule.get("reason", "").format(**row)
    return 0, False, ""


def assign_tier(score: float, tiers: list) -> str:
    for tier in sorted(tiers, key=lambda t: -t["min_score"]):
        if score >= tier["min_score"]:
            return tier["name"]
    return tiers[-1]["name"]


def _domain(url: str) -> str:
    if not url:
        return ""
    netloc = urlparse(url if "//" in url else "//" + url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def add_derived(df: pd.DataFrame, not_own_domains) -> pd.DataFrame:
    not_own_site = set(not_own_domains)
    df["website_domain"] = df["website"].map(_domain)
    df.loc[df["website_domain"].isin(not_own_site), "website_domain"] = ""
    counts = df.loc[df["website_domain"] != "", "website_domain"].value_counts()
    df["domain_account_count"] = df["website_domain"].map(counts).fillna(0).astype(int).astype(str)
    df.loc[df["website_domain"] == "", "domain_account_count"] = ""
    return df


def main(vertical: str, metro_path: str) -> None:
    rubric = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "rubric.yaml"))
    criteria = rubric["criteria"]
    total_max = sum(c["max_points"] for c in criteria.values())

    accounts = pd.read_csv(ACCOUNTS_PATH, dtype=str, keep_default_na=False)
    geo = yaml.safe_load(open(ROOT / metro_path))
    accounts, excluded = split(accounts, geo, reviewed_exclusions())
    excluded.to_csv(EXCLUDED_PATH, index=False)
    if len(excluded):
        print(f"[score] Left out {len(excluded)} accounts → {EXCLUDED_PATH.relative_to(ROOT)}: "
              f"{excluded['excluded_because'].str.split(':').str[0].value_counts().to_dict()}")
    signals = pd.read_csv(SIGNALS_PATH, dtype=str, keep_default_na=False)
    df = accounts.merge(signals, on=ID_COL, how="left").fillna("")
    discovery = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "discovery.yaml"))
    df = add_derived(df, discovery.get("not_own_website_domains", []))
    print(f"[score] {len(df)} accounts | {len(criteria)} criteria | {total_max} points possible")

    scored = []
    for row in df.to_dict("records"):
        out = {"score": 0, "known_max": 0}
        reasons = []
        for name, criterion in criteria.items():
            points, known, reason = score_criterion(criterion, row)
            if points > criterion["max_points"]:
                raise ValueError(f"criterion {name}: rule awards {points}, max is {criterion['max_points']}")
            out[f"pts_{name}"] = points
            out["score"] += points
            if known:
                out["known_max"] += criterion["max_points"]
            if reason:
                reasons.append((points, reason))
        out["data_coverage"] = round(out.pop("known_max") / total_max, 2)
        out["tier"] = assign_tier(out["score"], rubric["tiers"])
        out["score_reasons"] = "; ".join(r for _, r in sorted(reasons, key=lambda x: -x[0]))
        scored.append(out)

    result = pd.concat([df, pd.DataFrame(scored)], axis=1)
    result = result.sort_values(["score", "data_coverage", "name"], ascending=[False, False, True]).reset_index(drop=True)

    result["account_group"] = result["website_domain"].where(result["website_domain"] != "", result[ID_COL])
    result["group_size"] = result.groupby("account_group")[ID_COL].transform("size")
    # Rows are already best-first, so a group's first row is its best account.
    first_row = result.groupby("account_group", sort=False).ngroup()
    result["group_rank"] = first_row + 1
    result["rank_in_group"] = result.groupby("account_group").cumcount() + 1
    result = result.sort_values(["group_rank", "rank_in_group"]).reset_index(drop=True)

    lead = ["group_rank", "rank_in_group", "group_size", "tier", "score", "data_coverage",
            "name", "city", "zip", "phone", "website", "score_reasons"]
    result = result[lead + [c for c in result.columns if c not in lead]]
    result.to_csv(OUTPUT_PATH, index=False)

    print(f"[score] Written → {OUTPUT_PATH}\n")
    summary = result.groupby("tier").agg(
        accounts=("score", "size"), min_score=("score", "min"), max_score=("score", "max"),
        avg_data_coverage=("data_coverage", "mean"),
    ).round(2)
    print(summary.to_string())
    leads = result[result["rank_in_group"] == 1]
    print(f"\n{len(leads)} groups (accounts sharing a website count once). Groups by best tier:")
    print(leads["tier"].value_counts().sort_index().to_string())
    print("\nAverage points by criterion (of max):")
    for name, criterion in criteria.items():
        print(f"  {name}: {result[f'pts_{name}'].mean():.1f} / {criterion['max_points']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--metro", default=DEFAULT_METRO)
    args = parser.parse_args()
    main(args.vertical, args.metro)
