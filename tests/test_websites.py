import pandas as pd

from src.backfill import not_own_website
from src.enrich import needs_signal


def test_directory_and_rejected_websites_are_removed():
    sites = pd.Series(["https://www.dir.example/x/1", "https://own.example", "https://sub.dir.example/a", "", "https://bad.example"])
    rejected = pd.Series([False, False, False, False, True])
    assert list(not_own_website(sites, ["dir.example"], rejected)) == [True, False, True, False, True]


def test_website_signal_reruns_when_the_website_changed():
    row = {"careers_error": "", "careers_checked_website": "https://old.example"}
    assert needs_signal(row, "careers", {"website": ""}, uses_website=True)
    assert not needs_signal(row, "careers", {"website": "https://old.example"}, uses_website=True)
    # A signal that does not read the website is not re-run for a website change.
    assert not needs_signal(row, "careers", {"website": ""}, uses_website=False)


def test_failed_or_missing_signal_reruns():
    assert needs_signal(None, "x")
    assert needs_signal({"x_error": "Timeout"}, "x")
    assert not needs_signal({"x_error": ""}, "x")
