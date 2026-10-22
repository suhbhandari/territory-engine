#!/usr/bin/env python3
"""
recall_check.py
How much of the territory the account list actually found.

Precision is easy to show and recall is not: the pipeline can prove that every account it
lists is real, and say nothing about the ones it missed. This takes a public register that
is meant to be complete for the territory (the same open-data table a signal already
matches against), keeps the records inside the metro's zip prefixes, and asks how many of
them appear in the account list. The answer is a floor on recall for the kinds of business
that register, not for the whole market.

It reads the same `signals.yaml` block as the signal, so it knows nothing about any one
vertical or state, and it reuses the signal's matching, so a record counts as found on the
same terms the pipeline already uses.

The register is downloaded live, so this needs network access to that endpoint.

Usage:
  python3 scripts/recall_check.py [--vertical <name>] [--metro <path>] [--signal state_license] [--csv PATH]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402
from src.settings import DEFAULT_METRO, DEFAULT_VERTICAL  # noqa: E402
from src.signals.open_data_match import _table, find_matches, name_key, phone_key  # noqa: E402

SCORED_PATH = RAW / "accounts_scored.csv"


def in_territory(record: dict, zip_field: str, prefixes: list) -> bool:
    zip5 = str(record.get(zip_field, ""))[:5]
    return bool(zip5) and any(zip5.startswith(p) for p in prefixes)


def main(vertical: str, metro_path: str, signal: str, csv_path) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    signals = yaml.safe_load(open(vdir / "signals.yaml"))
    block = signals["signals"][signal] if "signals" in signals else signals[signal]
    params = block.get("params", block)
    metro = yaml.safe_load(open(ROOT / metro_path))
    prefixes = [str(p) for p in metro["zip_prefixes"]]

    records = _table(params)
    local = [r for r in records if in_territory(r, params.get("zip_field", ""), prefixes)]
    print(f"[recall] register: {len(records)} records, {len(local)} inside the territory's zip prefixes")

    accounts = pd.read_csv(SCORED_PATH, dtype=str, keep_default_na=False).to_dict("records")
    # Index the accounts the same way the signal matches, so a hit here means the pipeline
    # would also have linked them.
    rows = []
    for rec in local:
        hit = next((a for a in accounts if find_matches(a, [rec], params)), None)
        rows.append({"found": bool(hit),
                     "register_name": next((rec.get(f, "") for f in params.get("name_fields", []) if rec.get(f)), ""),
                     "zip": str(rec.get(params.get("zip_field", ""), ""))[:5],
                     "type": rec.get(params.get("type_field", ""), ""),
                     "account": hit["name"] if hit else "",
                     "tier": hit["tier"] if hit else ""})

    table = pd.DataFrame(rows)
    found = int(table["found"].sum())
    print(f"[recall] found in the account list: {found} of {len(local)} ({100 * found / max(len(local), 1):.1f}%)")
    if not table.empty:
        print("\nby register type:")
        for kind, grp in table.groupby("type"):
            print(f"  {kind or '(none)'}: {int(grp['found'].sum())} of {len(grp)}")
        missing = table[~table["found"]]
        print(f"\n{len(missing)} not found. Each is a licensed provider in the territory that the account list does "
              f"not contain, or contains under a name and phone that do not match the register.")
    print("\nThis is a floor on recall: it counts only the businesses this register lists, and a register miss can "
          "also mean the match failed rather than the account being absent.")
    if csv_path:
        table.to_csv(csv_path, index=False)
        print(f"\nWritten → {csv_path} (holds real names: keep it private)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--metro", default=DEFAULT_METRO)
    parser.add_argument("--signal", default="state_license")
    parser.add_argument("--csv", default="outputs/private/recall_check.csv")
    args = parser.parse_args()
    main(args.vertical, args.metro, args.signal, args.csv)
