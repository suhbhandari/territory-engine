import pytest
import requests

from src import enrich
from src.signals import careers_page, http_check, online


def fail(*a, **k):
    raise requests.ConnectionError("down")


@pytest.fixture(autouse=True)
def fresh_probe(monkeypatch):
    monkeypatch.setattr(online, "_last_ok", [float("-inf")])  # never checked, whatever the clock reads


def test_site_down_while_online_is_recorded(monkeypatch):
    monkeypatch.setattr(http_check.requests, "head", fail)
    monkeypatch.setattr(online, "_last_ok", [float("inf")])  # a reference site answered just now
    assert http_check.fetch({"website": "x.example"}, {})["website_live"] is False


def test_our_connection_down_raises_so_the_account_is_retried(monkeypatch):
    monkeypatch.setattr(online.requests, "head", fail)
    monkeypatch.setattr(http_check.requests, "head", fail)
    with pytest.raises(online.Offline):
        http_check.fetch({"website": "x.example"}, {})


def test_careers_page_raises_instead_of_saving_unreachable_when_offline(monkeypatch):
    monkeypatch.setattr(online.requests, "head", fail)
    monkeypatch.setattr(careers_page, "_request", fail)
    monkeypatch.setattr(careers_page, "_site_cache", {})
    with pytest.raises(online.Offline):
        careers_page.fetch({"website": "x.example"}, {"role_keywords": {}})


def test_redo_marks_only_matching_rows():
    rows = {"1": {"jobs_status": "site_unreachable", "careers_error": ""},
            "2": {"jobs_status": "counted", "careers_error": ""}}
    signals = [{"name": "careers"}, {"name": "other"}]
    assert enrich.mark_for_redo(rows, signals, ["careers"], "jobs_status=site_unreachable") == 1
    assert rows["1"]["careers_error"] == "redo requested" and rows["2"]["careers_error"] == ""
    with pytest.raises(SystemExit):
        enrich.mark_for_redo(rows, signals, ["nope"], "")
