"""
Phase 10: Push to HubSpot
Writes the scored accounts into HubSpot as companies, as described by the `hubspot` block
of the vertical's export.yaml.

Usage:
  python3 src/push_hubspot.py setup [--vertical <name>]
  python3 src/push_hubspot.py push [--vertical <name>] [--source public|raw] [--confirm]

Design:
  - Property names, labels, types and the template for each value live in config, so
    adding or renaming a CRM field is a config edit
  - setup creates the property group and every custom property, and can be run again:
    a property that exists already is left alone, and one whose type differs is reported
  - push reads the companies already in HubSpot by the ID property first, so every
    account is counted as create, update or unchanged. Only creates and updates are sent,
    through the batch upsert endpoint, so a second identical push writes nothing
  - Dry run by default: it reads and counts but writes nothing. --confirm writes
  - The public source is the anonymized build, so the CRM can be shown on screen
  - A 429 or a 5xx is retried with backoff. Every batch is logged to
    outputs/raw/hubspot_push_log.json, which the report card reads for its counts
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW, PUBLIC  # noqa: E402
from src.settings import DEFAULT_VERTICAL  # noqa: E402

load_dotenv(ROOT / ".env")

API = "https://api.hubapi.com"
SOURCES = {
    "public": PUBLIC / "accounts_public.csv",
    "raw": RAW / "accounts_scored.csv",
}
LOG_PATH = RAW / "hubspot_push_log.json"
BATCH_SIZE = 100
MAX_ATTEMPTS = 6


class _Blank(dict):
    def __missing__(self, key):
        return ""


class HubSpotError(RuntimeError):
    pass


class Client:
    """The few HubSpot calls this module makes, with retry on 429 and 5xx."""

    def __init__(self, token: str, session=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.sleep = sleep

    def call(self, method: str, path: str, body=None):
        """Returns (status, parsed JSON or None, attempts). Raises on any other error."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            r = self.session.request(method, API + path, headers=self.headers, json=body, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    break
                wait = float(r.headers.get("Retry-After") or 2 ** (attempt - 1))
                print(f"  [hubspot] {r.status_code} on {method} {path}; retrying in {wait:g}s")
                self.sleep(wait)
                continue
            if r.status_code == 401:
                hint = ("" if self.headers["Authorization"].startswith("Bearer pat-") else
                        " It does not start with 'pat-', so it is not a private app token: copy the token "
                        "from the private app's Auth tab, not its client secret or a developer API key.")
                raise HubSpotError("HubSpot rejected HUBSPOT_TOKEN (401). Check the token in .env is current." + hint)
            if r.status_code == 403:
                raise HubSpotError(f"HubSpot refused {method} {path} (403). The private app is missing a scope: "
                                   + _message(r))
            if r.status_code >= 400 and r.status_code != 404:
                raise HubSpotError(f"HubSpot {r.status_code} on {method} {path}: {_message(r)}")
            return r.status_code, _json(r), attempt
        raise HubSpotError(f"HubSpot still returned {r.status_code} on {method} {path} after {MAX_ATTEMPTS} attempts")


def _json(r):
    """The parsed body, or None when it is empty or not JSON (some 404s are neither)."""
    try:
        return r.json() if r.content else None
    except ValueError:
        return None


def _message(r) -> str:
    try:
        return r.json().get("message", r.text)
    except ValueError:
        return r.text


def token() -> str:
    t = os.getenv("HUBSPOT_TOKEN", "").strip()
    if not t:
        raise SystemExit("HUBSPOT_TOKEN is not set. Add a HubSpot private app token to .env "
                         "(see .env.example for the scopes it needs).")
    return t


def load_config(vertical: str) -> dict:
    cfg = yaml.safe_load(open(ROOT / "config" / "verticals" / vertical / "export.yaml"))
    if "hubspot" not in cfg:
        raise SystemExit(f"No `hubspot` block in config/verticals/{vertical}/export.yaml")
    return cfg["hubspot"]


# ---- mapping -------------------------------------------------------------------------

def _clean(value: str, prop: dict) -> str:
    value = value.strip()
    if prop.get("type") == "bool" and value:
        return "true" if value.lower() in ("true", "1", "yes") else "false"
    return value


def build_records(cfg: dict, accounts: pd.DataFrame, source: str) -> list:
    """[{id, properties}] for accounts in the configured tiers. A property with no template
    for this source is left out, so HubSpot keeps whatever it has."""
    props = [p for p in cfg["properties"] if source in p["value"]]
    id_prop = next((p for p in props if p["name"] == cfg["id_property"]), None)
    if id_prop is None:
        raise SystemExit(f"`{cfg['id_property']}` has no `{source}` template in the hubspot config")
    rows = accounts[accounts["tier"].isin(cfg["tiers"])]
    records = []
    for row in rows.to_dict("records"):
        context = _Blank(row)
        values = {p["name"]: _clean(p["value"][source].format_map(context), p) for p in props}
        if not values[cfg["id_property"]]:
            continue
        records.append({"id": values[cfg["id_property"]], "properties": values})
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{len(ids) - len(set(ids))} accounts share a `{cfg['id_property']}`; fix before pushing")
    return records


def _same(ours: str, theirs, prop: dict) -> bool:
    theirs = "" if theirs is None else str(theirs)
    if prop.get("type") == "number" and ours and theirs:
        try:
            return float(ours) == float(theirs)
        except ValueError:
            return False
    return ours == theirs.strip()


def diff(records: list, existing: dict, cfg: dict) -> tuple:
    """Splits records into (create, update, unchanged). An update carries only the
    properties whose values differ."""
    by_name = {p["name"]: p for p in cfg["properties"]}
    create, update, unchanged = [], [], []
    for rec in records:
        current = existing.get(rec["id"])
        if current is None:
            create.append({"id": rec["id"], "properties": {k: v for k, v in rec["properties"].items() if v != ""}})
            continue
        changed = {k: v for k, v in rec["properties"].items() if not _same(v, current.get(k), by_name[k])}
        (update if changed else unchanged).append({"id": rec["id"], "properties": changed})
    return create, update, unchanged


# ---- HubSpot calls -------------------------------------------------------------------

def setup(client: Client, cfg: dict) -> None:
    obj, group = cfg["object"], cfg["group"]
    status, _, _ = client.call("GET", f"/crm/v3/properties/{obj}/groups/{group['name']}")
    if status == 404:
        client.call("POST", f"/crm/v3/properties/{obj}/groups", {"name": group["name"], "label": group["label"]})
        print(f"[hubspot] created property group '{group['label']}'")
    else:
        print(f"[hubspot] property group '{group['label']}' exists")
    made = kept = 0
    for p in cfg["properties"]:
        if p.get("standard"):
            continue
        status, current, _ = client.call("GET", f"/crm/v3/properties/{obj}/{p['name']}")
        if status != 404:
            kept += 1
            if (current.get("type"), current.get("fieldType")) != (p["type"], p["field_type"]):
                print(f"  WARNING: '{p['name']}' exists as {current.get('type')}/{current.get('fieldType')}, "
                      f"config says {p['type']}/{p['field_type']}; left as it is")
            if p.get("unique") and not current.get("hasUniqueValue"):
                print(f"  WARNING: '{p['name']}' exists without unique values; upsert by it will fail. "
                      "Delete it in HubSpot and run setup again")
            continue
        body = {"name": p["name"], "label": p["label"], "type": p["type"], "fieldType": p["field_type"],
                "groupName": group["name"], "hasUniqueValue": bool(p.get("unique"))}
        if p.get("options"):
            body["options"] = [{"label": str(o), "value": str(o), "displayOrder": i} for i, o in enumerate(p["options"])]
        client.call("POST", f"/crm/v3/properties/{obj}", body)
        made += 1
        print(f"  created '{p['name']}' ({p['type']}{', unique' if p.get('unique') else ''})")
    print(f"[hubspot] setup done: {made} properties created, {kept} already there")


def read_existing(client: Client, cfg: dict, ids: list, names: list, log: list) -> dict:
    existing = {}
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i:i + BATCH_SIZE]
        body = {"idProperty": cfg["id_property"], "properties": names, "inputs": [{"id": x} for x in chunk]}
        status, data, attempts = client.call("POST", f"/crm/v3/objects/{cfg['object']}/batch/read", body)
        found = 0
        for res in (data or {}).get("results", []):
            props = res.get("properties", {})
            if props.get(cfg["id_property"]):
                existing[props[cfg["id_property"]]] = props
                found += 1
        log.append({"step": "read", "batch": i // BATCH_SIZE + 1, "records": len(chunk),
                    "found": found, "status": status, "attempts": attempts})
    return existing


def upsert(client: Client, cfg: dict, records: list, log: list) -> dict:
    counts = {"created": 0, "updated": 0}
    for i in range(0, len(records), BATCH_SIZE):
        chunk = records[i:i + BATCH_SIZE]
        body = {"inputs": [{"idProperty": cfg["id_property"], "id": r["id"], "properties": r["properties"]}
                           for r in chunk]}
        status, data, attempts = client.call("POST", f"/crm/v3/objects/{cfg['object']}/batch/upsert", body)
        results = (data or {}).get("results", [])
        new = sum(1 for r in results if r.get("new"))
        counts["created"] += new
        counts["updated"] += len(results) - new
        entry = {"step": "upsert", "batch": i // BATCH_SIZE + 1, "records": len(chunk), "status": status,
                 "attempts": attempts, "created": new, "updated": len(results) - new}
        if data and data.get("errors"):
            entry["errors"] = [e.get("message") for e in data["errors"]][:5]
            print(f"  WARNING: batch {entry['batch']}: {len(data['errors'])} errors, first: {entry['errors'][0]}")
        log.append(entry)
    return counts


def push(client: Client, cfg: dict, accounts: pd.DataFrame, source: str, confirm: bool,
         log_path: Path = LOG_PATH) -> dict:
    # HubSpot answers a lookup by a property that does not exist with no matches, not an
    # error, which would count every account as new. Check the ID property first.
    status, prop, _ = client.call("GET", f"/crm/v3/properties/{cfg['object']}/{cfg['id_property']}")
    if status == 404 or not (prop or {}).get("hasUniqueValue"):
        raise SystemExit(f"[hubspot] '{cfg['id_property']}' is missing or not unique in HubSpot; run make hubspot-setup first")
    records = build_records(cfg, accounts, source)
    names = sorted({k for r in records for k in r["properties"]})
    batches = []
    existing = read_existing(client, cfg, [r["id"] for r in records], names, batches)
    create, update, unchanged = diff(records, existing, cfg)
    run = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": source,
           "mode": "write" if confirm else "dry_run", "tiers": cfg["tiers"], "accounts": len(records),
           "to_create": len(create), "to_update": len(update), "unchanged": len(unchanged)}
    label = "" if confirm else " (dry run: nothing written)"
    print(f"[hubspot] {source} build, tiers {'/'.join(cfg['tiers'])}: {len(records)} accounts{label}")
    print(f"  create {len(create)} | update {len(update)} | unchanged {len(unchanged)}")
    if confirm and (create or update):
        result = upsert(client, cfg, create + update, batches)
        run.update(result)
        print(f"  written: {result['created']} created, {result['updated']} updated")
    elif confirm:
        run.update({"created": 0, "updated": 0})
        print("  nothing to write")
    else:
        print("  run with CONFIRM=1 to write")
    run["batches"] = batches

    log_path.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(log_path.read_text()) if log_path.exists() else []
    history.append(run)
    log_path.write_text(json.dumps(history, indent=2))
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "push"])
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--source", choices=list(SOURCES), default="public")
    parser.add_argument("--confirm", action="store_true", help="write to HubSpot; without it, a dry run")
    args = parser.parse_args()

    cfg = load_config(args.vertical)
    client = Client(token())
    try:
        if args.command == "setup":
            setup(client, cfg)
        else:
            path = SOURCES[args.source]
            if not path.exists():
                raise SystemExit(f"{path.relative_to(ROOT)} not found; build it first")
            accounts = pd.read_csv(path, dtype=str, keep_default_na=False)
            push(client, cfg, accounts, args.source, args.confirm)
    except HubSpotError as e:
        raise SystemExit(f"[hubspot] {e}")


if __name__ == "__main__":
    main()
