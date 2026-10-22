"""
Trigger list: what changed for each account between two runs.

Usage:
  python3 src/triggers.py [--vertical <name>] [--previous outputs/raw/runs/<label>]

Design:
  - Compares the previous run's scored list (a snapshot from scripts/snapshot.py) with the
    current one, account by account (entity_id), on the columns listed in the vertical's
    triggers.yaml. Numeric columns can be compared by band so small wobbles are not triggers
  - Also lists accounts that are new in this run and accounts that are gone
  - A column the previous run did not have (a signal added since) is skipped, not reported
    as a change for every account
  - Values that mean "could not check" (ignore_values) are not treated as changes
  - A tier change lists, in `because`, each rubric criterion whose points moved, so a change
    caused by a rubric edit (for example a new criterion input) is told apart from a change
    at the account
  - Writes outputs/raw/triggers.csv (real names, private), best-ranked accounts first, with
    the dates the before and after values were collected
  - Calls no external service
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402
from src.settings import DEFAULT_VERTICAL  # noqa: E402

OUTPUT_PATH = RAW / "triggers.csv"
COLS = ["group_rank", "tier", "name", "city", "entity_id", "change", "what", "before", "after", "because",
        "before_checked", "after_checked"]


def band(value: str, edges: list) -> str:
    if str(value).strip() == "":
        return ""
    n = float(value)
    if n < edges[0]:
        return f"under {edges[0]}"
    for low, high in zip(edges, edges[1:]):
        if low <= n < high:
            return f"{low}-{high - 1}"
    return f"{edges[-1]}+"


def latest_snapshot(current_dates: set) -> Path:
    runs = sorted(p for p in (RAW / "runs").iterdir() if (p / "accounts_scored.csv").exists()) if (RAW / "runs").exists() else []
    earlier = [p for p in runs if p.name not in current_dates]
    if not earlier:
        raise SystemExit("no earlier snapshot in outputs/raw/runs/; run make snapshot before a fresh run")
    return earlier[-1]


def compare(previous: pd.DataFrame, current: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    ignore = set(cfg.get("ignore_values", []))
    prev = previous.set_index("entity_id")
    rows = []
    for acc in current.to_dict("records"):
        base = {k: acc.get(k, "") for k in ("group_rank", "tier", "name", "city", "entity_id")}
        after_date = str(acc.get("signals_fetched_at", ""))[:10]
        if acc["entity_id"] not in prev.index:
            rows.append(dict(base, change="new account", what="", before="", after="", because="", before_checked="",
                             after_checked=after_date))
            continue
        old = prev.loc[acc["entity_id"]]
        before_date = str(old.get("signals_fetched_at", ""))[:10]
        for w in cfg["watch"]:
            col = w["column"]
            if col not in prev.columns or col not in acc:
                continue
            a, b = str(old[col]), str(acc[col])
            if "bands" in w:
                a, b = band(a, w["bands"]), band(b, w["bands"])
            if a == b or a in ignore or b in ignore:
                continue
            because = ""
            if col == "tier":
                moved = [(c[4:], int(float(old[c] or 0)), int(float(acc[c] or 0))) for c in acc
                         if c.startswith("pts_") and c in prev.columns and str(old[c]) != str(acc[c])]
                because = "; ".join(f"{name} {after - before:+d}" for name, before, after in moved)
            rows.append(dict(base, change="changed", what=w["label"], before=a or "unknown", after=b or "unknown",
                             because=because, before_checked=before_date, after_checked=after_date))
    for eid in sorted(set(prev.index) - set(current["entity_id"])):
        old = prev.loc[eid]
        rows.append({"group_rank": "", "tier": old.get("tier", ""), "name": old.get("name", ""), "city": old.get("city", ""),
                     "entity_id": eid, "change": "gone", "what": "", "before": "", "after": "", "because": "",
                     "before_checked": str(old.get("signals_fetched_at", ""))[:10], "after_checked": ""})
    out = pd.DataFrame(rows, columns=COLS)
    out["_rank"] = pd.to_numeric(out["group_rank"], errors="coerce").fillna(10**9)
    return out.sort_values(["_rank", "change", "what"]).drop(columns="_rank").reset_index(drop=True)


def main(vertical: str, previous_dir) -> None:
    cfg = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "triggers.yaml"))
    current = pd.read_csv(RAW / "accounts_scored.csv", dtype=str, keep_default_na=False)
    dates = set(current["signals_fetched_at"].str[:10])
    previous_dir = Path(previous_dir) if previous_dir else latest_snapshot(dates)
    previous = pd.read_csv(previous_dir / "accounts_scored.csv", dtype=str, keep_default_na=False)
    out = compare(previous, current, cfg)
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"[triggers] {previous_dir.name} → current: {len(out)} rows → {OUTPUT_PATH.relative_to(ROOT)}")
    print(out.groupby(["change", "what"]).size().to_string())
    tiers = out[out["what"] == "Tier"]
    print(f"[triggers] tier changes by criteria that moved: {tiers['because'].value_counts().head(6).to_dict()}")
    top = out[(out["change"] != "gone") & out["tier"].isin(["A", "B"])]
    print(f"[triggers] {top['entity_id'].nunique()} accounts now in tiers A or B have at least one trigger")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--previous", help="snapshot folder to compare with (default: the latest earlier one)")
    args = parser.parse_args()
    main(args.vertical, args.previous)
