"""
Phase 2: Signal Enrichment
Reads accounts CSV, runs all configured signal modules per account, writes signals CSV.

Usage:
  python3 src/enrich.py [--metro config/metro/<name>.yaml] [--vertical <name>]
                        [--limit N]        # process only first N accounts (for testing)
                        [--batch-size N]   # accounts per checkpoint (default 20)
                        [--accounts PATH] [--output PATH]

Design:
  - Each signal's run mode comes from the vertical's signals.yaml:
      mode: parallel | sequential (default sequential), delay: seconds between sequential calls
  - Accounts are processed in batches; the output file is rewritten after every batch,
    so an interrupted run loses at most one batch and a re-run resumes from there
  - Every signal has its own <signal>_error column. A signal is done for an account when
    the account has a row and that column is empty. Anything else is attempted again on
    the next run, and only the signals that need it are re-run
  - A signal marked `uses_website: true` is also re-run when the account's website has
    changed since that signal last ran (for example after a wrong website was removed).
    The website each such signal last read is kept in its <signal>_checked_website column
  - Within one run each account/signal pair is attempted at most once. A signal that fails
    MAX_CONSECUTIVE_ERRORS times in a row is switched off for the rest of the run
"""

import argparse
import importlib
import os
import sys
import time
import yaml
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import DEFAULT_METRO, DEFAULT_VERTICAL  # noqa: E402

ACCOUNTS_PATH = ROOT / "outputs" / "raw" / "accounts_raw.csv"
OUTPUT_PATH = ROOT / "outputs" / "raw" / "signals_raw.csv"

ID_COL = "entity_id"
FETCHED_COL = "signals_fetched_at"
RESERVED_KEYS = ("module", "description", "mode", "delay", "uses_website")
DEFAULT_DELAY = 1.2
MAX_WORKERS = 20
MAX_CONSECUTIVE_ERRORS = 5


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def read_csv_str(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_existing(path: Path):
    if not path.exists():
        return {}, [ID_COL, FETCHED_COL]
    df = read_csv_str(path)
    return {r[ID_COL]: r for r in df.to_dict("records")}, list(df.columns)


def write_output(path: Path, rows: dict, columns: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    pd.DataFrame(list(rows.values()), columns=columns, dtype=object).to_csv(tmp, index=False)
    os.replace(tmp, path)


def error_col(sig_name: str) -> str:
    return f"{sig_name}_error"


def website_col(sig_name: str) -> str:
    return f"{sig_name}_checked_website"


def needs_signal(row, sig_name: str, account=None, uses_website: bool = False) -> bool:
    if row is None:
        return True
    if uses_website and account is not None and row.get(website_col(sig_name), "") != account.get("website", ""):
        return True
    return error_col(sig_name) not in row or row[error_col(sig_name)] != ""


def call_signal(module, account: dict, params: dict):
    try:
        return module.fetch(account, params), ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def run_signal(sig: dict, accounts: list) -> list:
    if sig["disabled"]:
        return [({}, sig["disabled"])] * len(accounts)

    if sig["mode"] == "parallel":
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            outcomes = list(pool.map(lambda a: call_signal(sig["module"], a, sig["params"]), accounts))
    else:
        outcomes = []
        for acc in accounts:
            if sig["disabled"]:
                outcomes.append(({}, sig["disabled"]))
                continue
            outcome = call_signal(sig["module"], acc, sig["params"])
            outcomes.append(outcome)
            track_errors(sig, [outcome])
            time.sleep(sig["delay"])
        return outcomes

    track_errors(sig, outcomes)
    return outcomes


def track_errors(sig: dict, outcomes: list) -> None:
    for _, err in outcomes:
        sig["streak"] = sig["streak"] + 1 if err else 0
        if sig["streak"] >= MAX_CONSECUTIVE_ERRORS and not sig["disabled"]:
            sig["disabled"] = f"skipped: signal disabled after {MAX_CONSECUTIVE_ERRORS} consecutive errors"
            print(f"  [{sig['name']}] {MAX_CONSECUTIVE_ERRORS} consecutive errors, last: {err}")
            print(f"  [{sig['name']}] disabled for the rest of this run")


def load_signals(vertical: str) -> list:
    signals_cfg = load_yaml(ROOT / "config" / "verticals" / vertical / "signals.yaml")
    signals = []
    for sig_name, sig_cfg in signals_cfg.get("signals", {}).items():
        mode = sig_cfg.get("mode", "sequential")
        if mode not in ("parallel", "sequential"):
            raise ValueError(f"signal {sig_name}: mode must be parallel or sequential, got {mode!r}")
        signals.append({
            "name": sig_name,
            "module": importlib.import_module(sig_cfg["module"]),
            "mode": mode,
            "delay": float(sig_cfg.get("delay", DEFAULT_DELAY)),
            "params": {k: v for k, v in sig_cfg.items() if k not in RESERVED_KEYS},
            "uses_website": bool(sig_cfg.get("uses_website", False)),
            "streak": 0,
            "disabled": "",
        })
    return signals


def mark_for_redo(rows: dict, signals: list, redo: list, where: str) -> int:
    """Flag the named signals to run again for rows matching COLUMN=VALUE (or all rows)."""
    unknown = set(redo) - {s["name"] for s in signals}
    if unknown:
        raise SystemExit(f"--redo: unknown signal(s) {', '.join(sorted(unknown))}")
    column, _, value = where.partition("=") if where else ("", "", "")
    marked = 0
    for row in rows.values():
        if column and row.get(column, "") != value:
            continue
        for name in redo:
            row[error_col(name)] = "redo requested"
        marked += 1
    return marked


def main(metro_path: str, vertical: str, limit, batch_size: int, accounts_path: Path, output_path: Path,
         redo=None, where: str = "") -> None:
    accounts_df = read_csv_str(accounts_path)
    if limit:
        accounts_df = accounts_df.head(limit)
    accounts = accounts_df.to_dict("records")

    signals = load_signals(vertical)
    rows, columns = load_existing(output_path)
    missing = [website_col(s["name"]) for s in signals if s["uses_website"] and website_col(s["name"]) not in columns]
    if rows and missing:
        # Files written before these columns existed were enriched against the websites in the
        # account file at that time; record them once so later website changes are detected.
        websites = {a[ID_COL]: a.get("website", "") for a in read_csv_str(accounts_path).to_dict("records")}
        for key, row in rows.items():
            for col in missing:
                row[col] = websites.get(key, "")
        columns.extend(missing)
        write_output(output_path, rows, columns)
        print(f"[enrich] Recorded the website each existing row was checked against: {', '.join(missing)}")

    if redo:
        marked = mark_for_redo(rows, signals, redo, where)
        print(f"[enrich] Re-running {', '.join(redo)} for {marked} accounts{' where ' + where if where else ''}")

    def needs(row, sig, acc):
        return needs_signal(row, sig["name"], acc, sig["uses_website"])

    todo = [a for a in accounts if any(needs(rows.get(a[ID_COL]), s, a) for s in signals)]
    print(f"[enrich] {len(accounts)} accounts total | {len(accounts) - len(todo)} complete | {len(todo)} to process (new or with errors to retry)")

    if not todo:
        print("[enrich] Nothing to do.")
        return

    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        now = datetime.now(timezone.utc).isoformat()

        for sig in signals:
            pending = [a for a in batch if needs(rows.get(a[ID_COL]), sig, a)]
            if not pending:
                continue
            for acc, (vals, err) in zip(pending, run_signal(sig, pending)):
                row = rows.setdefault(acc[ID_COL], {ID_COL: acc[ID_COL]})
                row.update(vals)
                row[error_col(sig["name"])] = err
                row[FETCHED_COL] = now
                written = list(vals) + [error_col(sig["name"])]
                if sig["uses_website"]:
                    row[website_col(sig["name"])] = acc.get("website", "")
                    written.append(website_col(sig["name"]))
                for col in written:
                    if col not in columns:
                        columns.append(col)

        write_output(output_path, rows, columns)
        print(f"[enrich] {min(start + batch_size, len(todo))}/{len(todo)} processed, saved")

    print(f"\n[enrich] Written → {output_path}")
    print(f"Total enriched: {len(rows)}")

    run_rows = [rows[a[ID_COL]] for a in accounts if a[ID_COL] in rows]
    error_cols = [error_col(s["name"]) for s in signals]
    print(f"Coverage across the {len(run_rows)} accounts in this run:")
    for col in columns:
        if col in (ID_COL, FETCHED_COL) or col.endswith("_checked_website"):
            continue
        filled = sum(1 for r in run_rows if r.get(col) not in (None, ""))
        label = "accounts with errors (retried next run)" if col in error_cols else "accounts with data"
        print(f"  {col}: {filled}/{len(run_rows)} {label}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", default=DEFAULT_METRO)
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N accounts")
    parser.add_argument("--batch-size", type=int, default=20, help="Accounts per checkpoint")
    parser.add_argument("--accounts", type=Path, default=ACCOUNTS_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--redo", default="", help="Comma-separated signals to run again, e.g. careers_page,http_check")
    parser.add_argument("--where", default="", help="Only rows where COLUMN=VALUE, e.g. jobs_status=site_unreachable")
    args = parser.parse_args()
    main(args.metro, args.vertical, args.limit, args.batch_size, args.accounts, args.output,
         [s for s in args.redo.split(",") if s], args.where)
