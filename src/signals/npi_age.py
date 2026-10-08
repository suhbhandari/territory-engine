"""
Signal: NPI enrollment age
Looks up the NPI record to get the enumeration date (when the provider registered).
Newer agencies (< 3 years) are often in growth mode; older ones are established.

fetch(account, params) -> dict with keys:
  npi_enrolled_year, npi_age_years
Returns empty values without a network call when entity_id is not a 10-digit NPI.
Raises on a failed request.
"""

import re
from datetime import datetime, timezone

import requests

_API = "https://npiregistry.cms.hhs.gov/api/"
_THIS_YEAR = datetime.now(timezone.utc).year
_NPI = re.compile(r"\d{10}")


def fetch(account: dict, params: dict) -> dict:
    result = {"npi_enrolled_year": None, "npi_age_years": None}

    npi = str(account.get("entity_id", "")).strip()
    if not _NPI.fullmatch(npi):
        return result

    resp = requests.get(
        _API,
        params={"version": "2.1", "number": npi, "limit": 1},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if not results:
        return result

    created = results[0].get("created_epoch")
    if created:
        enrolled_year = datetime.fromtimestamp(int(created) / 1000, tz=timezone.utc).year
        result["npi_enrolled_year"] = enrolled_year
        result["npi_age_years"] = _THIS_YEAR - enrolled_year

    return result
