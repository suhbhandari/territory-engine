"""
Signal: match each account to a record in a public open-data table (for example a state
list of licensed providers) and report what the table says about it.

Everything about the table is set in the vertical's signals.yaml, so this module knows
nothing about any one vertical or state:
  url:          endpoint returning a JSON list of records (a Socrata-style API works)
  query:        query parameters for that endpoint (filters, row limit)
  name_fields:  record fields holding names to match the account's name against
  zip_field:    record field holding a zip code
  phone_field:  record field holding a phone number
  type_field:   record field whose values are reported (for example a licence type)
  prefix:       prefix for the output columns (default "match")

fetch(account, params) -> dict with keys (for prefix "license"):
  license_status  matched | not_found
  license_types   distinct type_field values across matched records, "; "-joined
  license_names   names on the matched records (kept private: not used in published text)
  license_match   how the match was made: phone, name, or name+zip

Matching is strict, so a wrong match is unlikely and a miss is possible:
  - phone: the account's 10-digit phone equals a record's
  - name: the account's name equals a record's name once case, punctuation and legal
    suffixes are removed
  - name+zip: names are near-identical (similarity 0.9 or more) and the 5-digit zips match
Every matching record is collected, since one organisation can hold several licences.
"not_found" means no record matched; it is not proof the account is unlicensed (it may
trade under a name the table does not show). The table is downloaded once per run.
Raises on a failed download, so enrich records the error and retries next run.
"""

import re
import threading
from difflib import SequenceMatcher
from functools import lru_cache

import requests

_LEGAL = {"llc", "inc", "corp", "corporation", "ltd", "co", "company", "lp", "llp", "pllc", "the", "dba"}
_SIMILARITY = 0.9
_lock = threading.Lock()
_tables = {}


@lru_cache(maxsize=None)
def name_key(name: str) -> str:
    tokens = re.sub(r"[^\w\s]", " ", str(name).lower()).split()
    return " ".join(t for t in tokens if t not in _LEGAL)


@lru_cache(maxsize=None)
def phone_key(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone))[-10:]
    return digits if len(digits) == 10 else ""


def _table(params: dict) -> list:
    key = (params["url"], repr(sorted(params.get("query", {}).items())))
    with _lock:
        if key not in _tables:
            resp = requests.get(params["url"], params=params.get("query", {}), timeout=90)
            resp.raise_for_status()
            _tables[key] = resp.json()
        return _tables[key]


def find_matches(account: dict, records: list, params: dict) -> list:
    """[(record, how)] for every record that matches the account."""
    phone = phone_key(account.get("phone", ""))
    name = name_key(account.get("name", ""))
    zip5 = str(account.get("zip", ""))[:5]
    found = []
    for rec in records:
        names = [name_key(rec.get(f, "")) for f in params.get("name_fields", [])]
        if phone and phone_key(rec.get(params.get("phone_field", ""), "")) == phone:
            found.append((rec, "phone"))
        elif name and name in names:
            found.append((rec, "name"))
        elif (name and zip5 and str(rec.get(params.get("zip_field", ""), ""))[:5] == zip5
              and any(n and SequenceMatcher(None, name, n).ratio() >= _SIMILARITY for n in names)):
            found.append((rec, "name+zip"))
    return found


def fetch(account: dict, params: dict) -> dict:
    p = params.get("prefix", "match")
    matches = find_matches(account, _table(params), params)
    if not matches:
        return {f"{p}_status": "not_found", f"{p}_types": "", f"{p}_names": "", f"{p}_match": ""}
    first_name_field = (params.get("name_fields") or [""])[0]
    return {
        f"{p}_status": "matched",
        f"{p}_types": "; ".join(dict.fromkeys(str(r.get(params.get("type_field", ""), "")) for r, _ in matches)),
        f"{p}_names": "; ".join(dict.fromkeys(str(r.get(first_name_field, "")) for r, _ in matches)),
        f"{p}_match": "; ".join(dict.fromkeys(how for _, how in matches)),
    }
