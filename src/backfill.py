"""
Phase 1: Account Backfill
Fills blank fields on discovered accounts by looking each one up in a second source.
Configured per vertical under `backfill:` in discovery.yaml.

Usage:
  python3 src/backfill.py [--vertical <name>] [--limit N]

Design:
  - One lookup per account that is missing a configured field and was not already
    found by the lookup source during discovery
  - A candidate is accepted only if its phone matches, or its zip matches and its
    name is near-identical; otherwise the field stays blank rather than guessed
  - Every lookup (hit or miss) is logged to a cache CSV, so re-runs cost nothing
    and each filled value can be traced to the listing it came from
  - Then websites that are not the account's own are removed: any on a domain in the
    vertical's not_own_website_domains, and any a person listed in
    outputs/raw/website_rejections.csv (columns entity_id, reason). A rejected website is
    never filled in again from the cache
"""

import argparse
import importlib
import sys
import time
import yaml
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402
from src.settings import DEFAULT_VERTICAL  # noqa: E402

from src.discover import _name_key, _phone_key  # noqa: E402

ACCOUNTS_PATH = RAW / "accounts_raw.csv"
CACHE_PATH = RAW / "backfill_cache.csv"
REJECTIONS_PATH = RAW / "website_rejections.csv"
CACHE_COLS = ["entity_id", "lookup_source", "query", "match_reason", "matched_id", "matched_name", "looked_up_at"]

_NAME_SIMILARITY = 0.85
_BATCH = 50
_MAX_PER_MINUTE = 400  # lookup APIs meter per minute; over-quota calls fail and must be re-run


def match(account: dict, candidates: list):
    phone = _phone_key(account["phone"])
    for c in candidates:
        if phone and _phone_key(c["phone"]) == phone:
            return c, "phone"
    name = _name_key(account["name"])
    for c in candidates:
        if c["zip"] != account["zip"]:
            continue
        if SequenceMatcher(None, name, _name_key(c["name"])).ratio() >= _NAME_SIMILARITY:
            return c, "name+zip"
    return None, "no_match"


def domain(url: str) -> str:
    netloc = urlparse(url if "//" in url else "//" + url).netloc.lower() if url else ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def not_own_website(websites: pd.Series, not_own_domains, rejected: pd.Series) -> pd.Series:
    """True where the website is on a listed domain (or a subdomain of one), or rejected."""
    listed = [d.lower() for d in not_own_domains]
    on_listed = websites.map(lambda w: any(domain(w) == d or domain(w).endswith("." + d) for d in listed))
    return (websites != "") & (on_listed | rejected)


def lookup_one(module, account: dict, template: str, fields: list) -> dict:
    query = template.format(**account)
    row = {"entity_id": account["entity_id"], "query": query, "matched_id": "", "matched_name": ""}
    row.update({f: "" for f in fields})
    try:
        candidate, reason = match(account, module.lookup(query))
    except Exception as exc:
        row["match_reason"] = f"error: {exc}"
        return row
    row["match_reason"] = reason
    if candidate:
        row["matched_id"] = candidate["entity_id"]
        row["matched_name"] = candidate["name"]
        row.update({f: candidate[f] for f in fields})
    return row


def main(vertical: str, limit) -> None:
    discovery = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "discovery.yaml"))
    accounts = pd.read_csv(ACCOUNTS_PATH, dtype=str).fillna("")

    for source_name, cfg in discovery.get("backfill", {}).items():
        module = importlib.import_module(f"src.sources.{source_name}")
        fields = cfg["fields"]
        cache_cols = CACHE_COLS + fields

        cache = pd.read_csv(CACHE_PATH, dtype=str).fillna("") if CACHE_PATH.exists() else pd.DataFrame(columns=cache_cols)
        cache = cache.reindex(columns=cache_cols, fill_value="")
        done = set(cache.loc[
            (cache["lookup_source"] == source_name) & ~cache["match_reason"].str.startswith("error"),
            "entity_id",
        ])

        missing = accounts[fields].eq("").any(axis=1)
        found_by_source = accounts["source"].str.contains(module.SOURCE_LABEL, regex=False)
        todo = accounts[missing & ~found_by_source & ~accounts["entity_id"].isin(done)]
        if limit:
            todo = todo.head(limit)
        print(f"[backfill] {source_name}: {int(missing.sum())} accounts missing {fields} | {len(todo)} to look up")

        todo_records = todo.to_dict("records")
        errors = 0
        for start in range(0, len(todo_records), _BATCH):
            batch = todo_records[start:start + _BATCH]
            batch_started = time.monotonic()
            with ThreadPoolExecutor(max_workers=8) as pool:
                rows = list(pool.map(lambda a: lookup_one(module, a, cfg["query_template"], fields), batch))
            now = datetime.now(timezone.utc).isoformat()
            for r in rows:
                r["lookup_source"] = source_name
                r["looked_up_at"] = now
            errors += sum(r["match_reason"].startswith("error") for r in rows)
            cache = cache[~cache["entity_id"].isin([r["entity_id"] for r in rows])]
            cache = pd.concat([cache, pd.DataFrame(rows, columns=cache_cols)], ignore_index=True)
            cache.to_csv(CACHE_PATH, index=False)
            print(f"    {min(start + _BATCH, len(todo_records))}/{len(todo_records)}")
            if errors >= 10 and errors == start + len(batch):
                print("[backfill] every lookup is failing — stopping. Last error:", rows[-1]["match_reason"])
                break
            time.sleep(max(0.0, len(batch) * 60 / _MAX_PER_MINUTE - (time.monotonic() - batch_started)))

        hits = cache[(cache["lookup_source"] == source_name) & (cache["matched_id"] != "")].set_index("entity_id")
        for field in fields:
            filled = accounts["entity_id"].map(hits[field]).fillna("")
            accounts[field] = accounts[field].where(accounts[field] != "", filled)

        reasons = cache.loc[cache["lookup_source"] == source_name, "match_reason"].str.replace(r"^error.*", "error", regex=True)
        print(f"[backfill] {source_name} lookups so far: {reasons.value_counts().to_dict()}")
        for field in fields:
            print(f"  {field}: {int(accounts[field].ne('').sum())}/{len(accounts)} accounts now have a value")

    rejections = pd.read_csv(REJECTIONS_PATH, dtype=str).fillna("") if REJECTIONS_PATH.exists() else pd.DataFrame(columns=["entity_id"])
    remove = not_own_website(accounts["website"], discovery.get("not_own_website_domains", []),
                             accounts["entity_id"].isin(rejections["entity_id"]))
    accounts.loc[remove, "website"] = ""
    print(f"[backfill] Removed {int(remove.sum())} websites that are not the account's own site")

    accounts.to_csv(ACCOUNTS_PATH, index=False)
    print(f"\n[backfill] Written → {ACCOUNTS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--limit", type=int, default=None, help="Look up only the first N accounts")
    args = parser.parse_args()
    main(args.vertical, args.limit)
