"""
Signal: Website liveness
HEAD request to the account's website URL. Returns live/dead and SSL status.

fetch(account, params) -> dict with keys:
  website_live, website_has_ssl
"""

import requests

_TIMEOUT = 8


def fetch(account: dict, params: dict) -> dict:
    result = {"website_live": None, "website_has_ssl": None}

    url = account.get("website")
    url = url.strip() if isinstance(url, str) else ""
    if not url:
        result["website_live"] = False
        return result

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.head(url, timeout=_TIMEOUT, allow_redirects=True)
        result["website_live"] = resp.status_code < 400
        result["website_has_ssl"] = resp.url.startswith("https://")
    except requests.exceptions.SSLError:
        # Site exists but SSL is broken
        result["website_live"] = True
        result["website_has_ssl"] = False
    except Exception:
        result["website_live"] = False
        result["website_has_ssl"] = False

    return result
