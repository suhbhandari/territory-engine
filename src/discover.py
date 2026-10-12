"""
Phase 1: Account Discovery
Generic orchestrator. Loads metro geo config + vertical discovery config,
runs each configured source module, deduplicates, writes CSV.

Usage:
  python3 src/discover.py [--metro config/metro/<name>.yaml] [--vertical <name>]
"""

import argparse
import importlib
import json
import re
import sys
import yaml
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import DEFAULT_METRO, DEFAULT_VERTICAL  # noqa: E402

from src.exclusions import out_of_territory  # noqa: E402
from src.sources.base import SCHEMA  # noqa: E402

OUTPUT_PATH = ROOT / "outputs" / "raw" / "accounts_raw.csv"
SUMMARY_PATH = ROOT / "outputs" / "raw" / "discover_summary.json"


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


_LEGAL_SUFFIXES = {"llc", "inc", "corp", "corporation", "ltd", "co", "company", "lp", "llp", "pllc", "the"}


def _name_key(name: str) -> str:
    tokens = re.sub(r"[^\w\s]", "", str(name).lower()).split()
    return "".join(t for t in tokens if t not in _LEGAL_SUFFIXES)


def _phone_key(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone))[-10:]
    return digits if len(digits) == 10 else ""


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Merge rows that share (name, zip) or a phone number into one account.

    Earlier sources in the discovery config win; blanks are filled from later ones,
    so a registry row picks up the website its map listing carries.
    """
    df = df.fillna("").astype(str).reset_index(drop=True)

    parent = list(range(len(df)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first_seen: dict[str, int] = {}
    for i, row in df.iterrows():
        keys = [f"n:{_name_key(row['name'])}|{row['zip'][:5]}"]
        if _phone_key(row["phone"]):
            keys.append(f"p:{_phone_key(row['phone'])}")
        for key in keys:
            if key in first_seen:
                parent[find(i)] = find(first_seen[key])
            else:
                first_seen[key] = i

    groups: dict[int, list[int]] = {}
    for i in range(len(df)):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for members in groups.values():
        rows = [df.loc[i] for i in sorted(members)]
        account = rows[0].to_dict()
        for other in rows[1:]:
            for col in SCHEMA:
                if account[col] in ("", "Unknown") and other[col] not in ("", "Unknown"):
                    account[col] = other[col]
        account["source"] = "; ".join(dict.fromkeys(r["source"] for r in rows))
        merged.append(account)

    return pd.DataFrame(merged, columns=SCHEMA)


def main(metro_path: str, vertical: str) -> None:
    geo = load_yaml(ROOT / metro_path)
    discovery = load_yaml(ROOT / "config" / "verticals" / vertical / "discovery.yaml")

    print(f"[discover] Metro: {geo['metro']} | Vertical: {vertical}")

    run_at = datetime.now(timezone.utc).isoformat()
    fetched = {}
    dfs: list[pd.DataFrame] = []
    for source_name, params in discovery.get("sources", {}).items():
        try:
            module = importlib.import_module(f"src.sources.{source_name}")
        except ImportError as exc:
            print(f"  [skip] src.sources.{source_name} not found: {exc}")
            continue

        print(f"[discover] Source: {source_name}...")
        df = module.fetch(params, geo)
        print(f"  → {len(df)} records")
        fetched[source_name] = len(df)
        dfs.append(df)

    if not dfs:
        print("[discover] No data fetched.")
        sys.exit(1)

    combined = pd.concat(dfs, ignore_index=True)
    combined = combined[combined["name"].str.strip() != ""]
    print(f"[discover] Combined: {len(combined)} | Deduplicating...")

    final = deduplicate(combined)
    print(f"[discover] After merging duplicates: {len(final)} accounts ({len(combined) - len(final)} rows merged)")
    outside = out_of_territory(final, geo)
    final = final[~outside].copy()
    print(f"[discover] Dropped {int(outside.sum())} outside the territory (exclude_zips) | Final: {len(final)}")
    final["discovered_at"] = run_at

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)
    summary = {
        "run_at": run_at, "metro": geo["metro"], "vertical": vertical, "fetched_by_source": fetched,
        "combined_rows": len(combined), "after_merging": len(final) + int(outside.sum()),
        "rows_merged": len(combined) - len(final) - int(outside.sum()),
        "dropped_outside_territory": int(outside.sum()), "final_accounts": len(final),
        "final_by_source": final["source"].value_counts().to_dict(),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))
    print(f"\n[discover] Written → {OUTPUT_PATH} and {SUMMARY_PATH.name}")
    print(f"\nBy source:\n{final['source'].value_counts().to_string()}")
    print(f"\nBy license_type (top 10):\n{final['license_type'].value_counts().head(10).to_string()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", default=DEFAULT_METRO)
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    args = parser.parse_args()
    main(args.metro, args.vertical)
