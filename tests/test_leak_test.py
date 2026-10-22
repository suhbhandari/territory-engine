import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("leak_test", Path(__file__).parent.parent / "scripts" / "leak_test.py")
leak_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leak_test)


def build(tmp_path, published_text, extra_accounts=()):
    raw = tmp_path / "outputs" / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([
        {"name": "Bluebird Wellness LLC", "address": "12 Main Street", "city": "Brooklyn", "state": "NY",
         "phone": "718-555-0101", "website": "https://bluebird.example", "entity_id": "1234567890"},
        {"name": "Brooklyn Services", "address": "", "city": "Brooklyn", "state": "NY",
         "phone": "", "website": "", "entity_id": "ChIJabcdefghijkl"},
        *extra_accounts,
    ]).to_csv(raw / "accounts_raw.csv", index=False)
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<p>page</p>")
    (tmp_path / "outputs" / "public").mkdir()
    (tmp_path / "outputs" / "public" / "data.json").write_text(published_text)
    return tmp_path


def kinds(tmp_path, text):
    hits, _, _ = leak_test.find_leaks(build(tmp_path, text))
    return {k for k, _, _ in hits}


def test_clean_output_passes(tmp_path):
    assert kinds(tmp_path, "Account 0001 in Brooklyn lists 4 open roles.") == set()


def test_each_identifier_kind_is_caught(tmp_path):
    text = "Bluebird Wellness at 12 Main Street, (718) 555-0101, bluebird.example, id 1234567890"
    assert kinds(tmp_path, text) == {"names", "addresses", "phones", "urls", "domains", "ids"}


def test_name_of_only_place_words_is_not_a_leak(tmp_path):
    # "Brooklyn" alone names a place, not an account.
    assert kinds(tmp_path, "an office in Brooklyn") == set()


def test_names_found_by_a_signal_are_checked_too(tmp_path):
    root = build(tmp_path, "Run by Redwing Partners in Brooklyn.")
    pd.DataFrame([{"entity_id": "1234567890", "license_names": "Redwing Partners; Brooklyn"}]).to_csv(
        root / "outputs" / "raw" / "signals_raw.csv", index=False)
    hits, _, _ = leak_test.find_leaks(root)
    assert {(k, v) for k, v, _ in hits} == {("names", "redwing partners")}


# A reviewed phrase may contain an account's name without identifying the account.
TRUSTED_PARTNERS = {"name": "Trusted Partners", "address": "", "city": "Brooklyn", "state": "NY",
                  "phone": "", "website": "", "entity_id": "ChIJzzzzzzzzzzzz"}
PHRASE = "registered trusted partners"


def allow(root, name="trusted partners", phrase=PHRASE):
    pd.DataFrame([{"name": name, "allowed_phrase": phrase, "reason": "category wording"}]).to_csv(
        root / "outputs" / "raw" / "leak_allowlist.csv", index=False)


def leaks(tmp_path, text, allowlist=True):
    root = build(tmp_path, text, extra_accounts=[TRUSTED_PARTNERS])
    if allowlist:
        allow(root)
    hits, _, _ = leak_test.find_leaks(root)
    return {(k, v) for k, v, _ in hits}


def test_name_inside_a_reviewed_phrase_is_not_a_leak(tmp_path):
    text = "We could not find Account 0156 on the list of registered trusted partners."
    assert leaks(tmp_path / "a", text, allowlist=False) == {("names", "trusted partners")}
    assert leaks(tmp_path / "b", text) == set()


def test_name_on_its_own_still_fails_beside_a_reviewed_phrase(tmp_path):
    text = "The list of registered trusted partners. Note: trusted partners owes 90 days."
    assert leaks(tmp_path, text) == {("names", "trusted partners")}


def test_name_in_another_case_inside_the_phrase_still_fails(tmp_path):
    assert leaks(tmp_path, "Registered Trusted Partners is overdue.") == {("names", "trusted partners")}


def test_allowed_phrase_does_not_hide_other_names(tmp_path):
    text = "registered trusted partners and Bluebird Wellness"
    assert leaks(tmp_path, text) == {("names", "bluebird wellness")}


def test_allowlist_phrase_must_add_a_word_to_the_name(tmp_path):
    root = build(tmp_path, "text", extra_accounts=[TRUSTED_PARTNERS])
    allow(root, phrase="trusted partners")
    with pytest.raises(SystemExit):
        leak_test.find_leaks(root)


def test_allowlist_name_must_be_an_account(tmp_path):
    root = build(tmp_path, "text", extra_accounts=[TRUSTED_PARTNERS])
    allow(root, name="not an account", phrase="a not an account phrase")
    with pytest.raises(SystemExit):
        leak_test.find_leaks(root)


def test_a_second_runs_identifiers_are_checked_against_every_published_file(tmp_path):
    root = build(tmp_path, "Account 0001 in Brooklyn.")
    run = root / "outputs" / "raw" / "other-run"
    run.mkdir()
    pd.DataFrame([{"name": "Copperline Heating Co", "address": "9 Elm Road", "city": "Mesa", "state": "AZ",
                   "phone": "480-555-0199", "website": "https://copperline.example", "entity_id": "ChIJzyxwvutsrqpo"}]
                 ).to_csv(run / "accounts_raw.csv", index=False)
    (root / "outputs" / "public" / "other-run").mkdir()
    (root / "outputs" / "public" / "other-run" / "data.json").write_text("Copperline Heating Co in Mesa")
    hits, ids, _ = leak_test.find_leaks(root)
    assert {(k, f) for k, _, f in hits} >= {("names", "outputs/public/other-run/data.json")}
    assert "copperline heating co" in ids["names"] and "bluebird wellness llc" in ids["names"]


def test_snapshot_runs_folder_is_not_treated_as_a_run(tmp_path):
    root = build(tmp_path, "clean")
    (root / "outputs" / "raw" / "runs" / "2026-01-01").mkdir(parents=True)
    (root / "outputs" / "raw" / "runs" / "accounts_raw.csv").write_text("name\n")
    assert leak_test.raw_dirs(root) == [root / "outputs" / "raw"]
