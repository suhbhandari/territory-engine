"""
Tells "this website is down" apart from "our own connection is down".

A signal that reads other people's websites calls require_online() when a request fails at
the network level. If a couple of well-known hosts also cannot be reached, the problem is
on our side, so it raises Offline instead of recording the website as unreachable. Enrich
then records an error for that account and retries it on the next run, rather than saving
a wrong answer. A successful check is remembered for a short time so a run of failures
does not trigger a probe per request.
"""

import threading
import time

import requests

PROBE_URLS = ("https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace")
_REMEMBER_SECONDS = 30
_lock = threading.Lock()
_last_ok = [0.0]


class Offline(RuntimeError):
    pass


def require_online() -> None:
    with _lock:
        if time.monotonic() - _last_ok[0] < _REMEMBER_SECONDS:
            return
        for url in PROBE_URLS:
            try:
                requests.head(url, timeout=6)
                _last_ok[0] = time.monotonic()
                return
            except requests.RequestException:
                continue
    raise Offline("no internet connection: reference sites also unreachable; will retry next run")
