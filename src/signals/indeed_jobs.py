"""
Signal: Indeed job postings
Uses Indeed's RSS feed (no auth required) to count open postings for an account.
Classifies job titles into role buckets defined in the vertical's signals.yaml.

fetch(account, params) -> dict with keys:
  jobs_total, jobs_<bucket> for each bucket in params["role_keywords"], jobs_titles_sample
Raises on a failed request or unparseable response; data keys are never set to error text.
"""

import re
import time
import xml.etree.ElementTree as ET

import requests

_RSS = "https://www.indeed.com/rss"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; territory-engine/1.0)"
}


def fetch(account: dict, params: dict) -> dict:
    name = account.get("name", "")
    city = account.get("city", "")
    state = account.get("state", "")
    location = f"{city}, {state}" if city else state

    role_keywords: dict = params.get("role_keywords", {})

    result = {"jobs_total": None}
    for bucket in role_keywords:
        result[f"jobs_{bucket}"] = None
    result["jobs_titles_sample"] = None

    if not name:
        return result

    resp = requests.get(
        _RSS,
        params={"q": f'"{name}"', "l": location, "radius": "10"},
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()

    titles = _parse_titles(resp.text)
    if titles is None:
        raise ValueError("response was not parseable XML")

    result["jobs_total"] = len(titles)
    result["jobs_titles_sample"] = "; ".join(titles[:5]) if titles else ""

    for bucket, keywords in role_keywords.items():
        count = sum(
            1 for t in titles
            if any(kw.lower() in t.lower() for kw in keywords)
        )
        result[f"jobs_{bucket}"] = count

    return result


def _parse_titles(xml_text: str):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    ns = {"media": "http://search.yahoo.com/mrss/"}
    titles = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            # Strip HTML entities
            title = re.sub(r"<[^>]+>", "", title_el.text).strip()
            titles.append(title)
    return titles
