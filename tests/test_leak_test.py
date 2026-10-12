import importlib.util
from pathlib import Path

import pandas as pd

spec = importlib.util.spec_from_file_location("leak_test", Path(__file__).parent.parent / "scripts" / "leak_test.py")
leak_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leak_test)


def build(tmp_path, published_text):
    raw = tmp_path / "outputs" / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([
        {"name": "Bluebird Wellness LLC", "address": "12 Main Street", "city": "Brooklyn", "state": "NY",
         "phone": "718-555-0101", "website": "https://bluebird.example", "entity_id": "1234567890"},
        {"name": "Brooklyn Services", "address": "", "city": "Brooklyn", "state": "NY",
         "phone": "", "website": "", "entity_id": "ChIJabcdefghijkl"},
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
