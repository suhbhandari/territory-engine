#!/usr/bin/env python3
"""
snapshot.py
Keeps a copy of one run's private data so a later run can be compared with it (the
trigger list) and nothing is lost when discover and enrich write new files.

Copies outputs/raw/ account, signal, score, exclusion and export files into
outputs/raw/runs/<label>/. The label defaults to the date most signals were collected.
Never deletes data: with --fresh-signals the signals file is moved into the snapshot
only after its copy there is confirmed identical, so the next enrich re-checks every
account instead of keeping the old results.

Usage:
  python3 scripts/snapshot.py [--label NAME] [--fresh-signals]
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402

FILES = ["accounts_raw.csv", "signals_raw.csv", "accounts_scored.csv", "accounts_excluded.csv",
         "discover_summary.json", "exclusions.csv", "website_rejections.csv",
         "exports/salesforce_accounts.csv", "exports/outreach_accounts.csv",
         "briefs/briefs_index.csv", "sequences/sequences_index.csv", "sequences/sequences.csv"]


def default_label() -> str:
    signals = RAW / "signals_raw.csv"
    if not signals.exists():
        raise SystemExit("no signals file to label the snapshot by; pass --label")
    dates = pd.read_csv(signals, dtype=str, keep_default_na=False)["signals_fetched_at"].str[:10]
    return dates[dates != ""].mode().iat[0]


def main(label: str, fresh_signals: bool) -> int:
    dest = RAW / "runs" / label
    copied, same = [], []
    for name in FILES:
        src = RAW / name
        if not src.exists():
            continue
        target = dest / name
        if target.exists():
            if not filecmp.cmp(src, target, shallow=False):
                print(f"[snapshot] {target.relative_to(ROOT)} exists and differs from the current file. "
                      "Nothing changed; choose another --label.")
                return 1
            same.append(name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(name)
    print(f"[snapshot] {dest.relative_to(ROOT)}: {len(copied)} copied, {len(same)} already there and identical")
    if fresh_signals:
        src, kept = RAW / "signals_raw.csv", dest / "signals_raw.csv"
        if src.exists() and kept.exists() and filecmp.cmp(src, kept, shallow=False):
            src.unlink()
            print(f"[snapshot] signals_raw.csv moved into the snapshot; the next enrich re-checks every account")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label")
    parser.add_argument("--fresh-signals", action="store_true")
    args = parser.parse_args()
    sys.exit(main(args.label or default_label(), args.fresh_signals))
