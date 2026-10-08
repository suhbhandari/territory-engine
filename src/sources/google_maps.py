"""
Source: Google Maps Places API (New) Text Search
Fetches businesses matching search_templates expanded with metro city/state values.
Website and phone come back in the same call, so no per-place detail lookups.

Interface: fetch(params, geo) -> DataFrame[SCHEMA]
  params: {search_templates: [str, ...],   # use {city} and {state} as placeholders
           exclude_types: [str, ...]}      # optional: Places primaryType values to drop
  geo:    {state: str, city: str, search_cities: [str, ...], zip_prefixes: [str, ...]}

Also: lookup(query, limit) -> list of SCHEMA records for one free-text query,
used by backfill.py to find the listing for an account another source discovered.
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from .base import SCHEMA, empty_df

load_dotenv(Path(__file__).parent.parent.parent / ".env")

_API = "https://places.googleapis.com/v1/places:searchText"
SOURCE_LABEL = "Google Maps"
_FIELDS = ",".join([
    "places.id",
    "places.displayName",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.primaryType",
    "places.primaryTypeDisplayName",
    "places.businessStatus",
    "nextPageToken",
])
_MAX_PAGES = 3  # API caps a query at 60 results (3 pages of 20)


def fetch(params: dict, geo: dict) -> pd.DataFrame:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("  [google_maps] GOOGLE_MAPS_API_KEY not set — skipping")
        return empty_df()

    templates = params.get("search_templates", [])
    exclude_types = set(params.get("exclude_types", []))
    state = geo.get("state", "")
    zip_prefixes = geo.get("zip_prefixes", [])
    cities = geo.get("search_cities") or [geo.get("city", geo.get("metro", ""))]

    search_terms = [
        t.format(city=city, state=state)
        for city in cities
        for t in templates
    ]

    places: dict[str, dict] = {}

    for term in search_terms:
        try:
            for p in _search(term, api_key, _MAX_PAGES, 20):
                places.setdefault(p["id"], p)
        except Exception as exc:
            print(f"  [google_maps] '{term}' failed: {exc}")
        time.sleep(0.3)

    records = []
    for p in places.values():
        if p.get("businessStatus") == "CLOSED_PERMANENTLY":
            continue
        if p.get("primaryType") in exclude_types:
            continue

        rec = _to_record(p)
        if state and rec["state"] != state:
            continue
        if zip_prefixes and not any(rec["zip"].startswith(pr) for pr in zip_prefixes):
            continue
        records.append(rec)

    if not records:
        return empty_df()
    return pd.DataFrame(records, columns=SCHEMA)


def lookup(query: str, limit: int = 3) -> list:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set")
    return [
        _to_record(p)
        for p in _search(query, api_key, 1, limit)
        if p.get("businessStatus") != "CLOSED_PERMANENTLY"
    ]


def _search(term: str, api_key: str, max_pages: int, page_size: int) -> list:
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": _FIELDS}
    places = []
    page_token = None
    for _ in range(max_pages):
        body = {"textQuery": term, "pageSize": page_size}
        if page_token:
            body["pageToken"] = page_token

        resp = requests.post(_API, json=body, headers=headers, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", {}).get("message", resp.status_code))

        places.extend(p for p in data.get("places", []) if p.get("id"))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return places


def _to_record(p: dict) -> dict:
    addr = _parse_address(p.get("addressComponents", []))
    return {
        "name": p.get("displayName", {}).get("text", "").strip(),
        "address": addr["street"],
        "city": addr["city"],
        "state": addr["state"],
        "zip": addr["zip"],
        "phone": p.get("nationalPhoneNumber", ""),
        "website": p.get("websiteUri", ""),
        "source": SOURCE_LABEL,
        "license_type": p.get("primaryTypeDisplayName", {}).get("text", "") or "Unknown",
        "entity_id": p["id"],
    }


def _parse_address(components: list) -> dict:
    by_type: dict[str, str] = {}
    for c in components:
        for t in c.get("types", []):
            by_type.setdefault(t, c.get("shortText", ""))

    street = f"{by_type.get('street_number', '')} {by_type.get('route', '')}".strip()
    city = (
        by_type.get("locality")
        or by_type.get("sublocality_level_1")
        or by_type.get("sublocality")
        or ""
    )
    return {
        "street": street,
        "city": city,
        "state": by_type.get("administrative_area_level_1", ""),
        "zip": by_type.get("postal_code", "")[:5],
    }
