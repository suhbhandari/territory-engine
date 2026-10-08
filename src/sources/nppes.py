"""
Source: NPPES NPI Registry (npiregistry.cms.hhs.gov/api)
Fetches Type-2 (organization) NPI providers whose taxonomy matches any of the
descriptions supplied by the vertical's discovery config.

Interface: fetch(params, geo) -> DataFrame[SCHEMA]
  params: {taxonomies: [str, ...],
           primary_taxonomies: [str, ...]}  # optional: keep only orgs whose primary taxonomy is listed
  geo:    {state: str, zip_prefixes: [str, ...]}
"""

import time
import requests
import pandas as pd
from .base import SCHEMA, empty_df

_API = "https://npiregistry.cms.hhs.gov/api/"


def fetch(params: dict, geo: dict) -> pd.DataFrame:
    taxonomies = params.get("taxonomies", [])
    state = geo.get("state", "")
    zip_prefixes = geo.get("zip_prefixes", [])

    primary_taxonomies = set(params.get("primary_taxonomies", []))

    # The registry matches a taxonomy anywhere on the record, so the same org can
    # come back under several searches; keyed by NPI to keep one row each.
    by_npi: dict[str, dict] = {}
    for taxonomy in taxonomies:
        for prefix in zip_prefixes or [None]:
            for rec in _fetch_taxonomy(taxonomy, state, prefix):
                by_npi.setdefault(rec["entity_id"], rec)

    records = list(by_npi.values())
    if primary_taxonomies:
        records = [r for r in records if r["license_type"] in primary_taxonomies]

    if not records:
        return empty_df()
    return pd.DataFrame(records, columns=SCHEMA)


_MAX_RECORDS = 1200  # registry API refuses to page past this per query


def _fetch_taxonomy(taxonomy_desc: str, state: str, zip_prefix) -> list:
    records = []
    skip = 0
    limit = 200
    query_geo = {"state": state}
    if zip_prefix:
        query_geo["postal_code"] = f"{zip_prefix}*"

    while True:
        if skip >= _MAX_RECORDS:
            print(f"  [nppes] '{taxonomy_desc}' {zip_prefix or state}: hit {_MAX_RECORDS}-record cap, results truncated")
            break
        try:
            resp = requests.get(
                _API,
                params={
                    "version": "2.1",
                    "enumeration_type": "NPI-2",
                    "taxonomy_description": taxonomy_desc,
                    **query_geo,
                    "limit": limit,
                    "skip": skip,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"  [nppes] error at skip={skip}: {exc}")
            break

        results = data.get("results", [])
        if not results:
            break

        for r in results:
            addresses = r.get("addresses", [])
            loc = next(
                (a for a in addresses if a.get("address_purpose") == "LOCATION"),
                addresses[0] if addresses else {},
            )
            zip_code = loc.get("postal_code", "")[:5]

            # postal_code matches mailing addresses too; keep only orgs located in the prefix
            if zip_prefix and not zip_code.startswith(zip_prefix):
                continue

            primary_tax = next(
                (t.get("desc", "") for t in r.get("taxonomies", []) if t.get("primary")),
                "",
            )

            records.append({
                "name": r.get("basic", {}).get("organization_name", "").strip().title(),
                "address": loc.get("address_1", ""),
                "city": loc.get("city", "").title(),
                "state": loc.get("state", ""),
                "zip": zip_code,
                "phone": loc.get("telephone_number", ""),
                "website": "",
                "source": "NPPES",
                "license_type": primary_tax,
                "entity_id": str(r.get("number", "")),
            })

        if len(results) < limit:
            break
        skip += limit
        time.sleep(0.3)

    return records
