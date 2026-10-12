import pandas as pd

from src.discover import _name_key, _phone_key, deduplicate
from src.sources.base import SCHEMA


def rows(*records):
    return pd.DataFrame([{c: r.get(c, "") for c in SCHEMA} for r in records], columns=SCHEMA)


def test_name_key_drops_legal_suffixes_and_punctuation():
    assert _name_key("Bluebird Services, LLC.") == _name_key("bluebird services inc")
    assert _name_key("The Bluebird Group") == "bluebirdgroup"


def test_phone_key_keeps_last_ten_digits_or_nothing():
    assert _phone_key("+1 (212) 555-0101") == "2125550101"
    assert _phone_key("555-0101") == ""
    assert _phone_key("") == ""


def test_same_name_and_zip_across_sources_merge_and_fill_blanks():
    df = rows(
        {"name": "Bluebird Services LLC", "zip": "10001", "phone": "", "source": "Registry", "entity_id": "1"},
        {"name": "Bluebird Services", "zip": "10001", "website": "bluebird.example", "phone": "2125550101",
         "source": "Maps", "entity_id": "x"},
    )
    out = deduplicate(df)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["entity_id"] == "1"  # earlier source wins
    assert row["website"] == "bluebird.example"  # blank filled from later source
    assert row["source"] == "Registry; Maps"


def test_shared_phone_merges_different_names():
    df = rows(
        {"name": "North Office", "zip": "10001", "phone": "212-555-0101", "source": "A", "entity_id": "1"},
        {"name": "South Office", "zip": "11201", "phone": "(212) 555-0101", "source": "B", "entity_id": "2"},
    )
    assert len(deduplicate(df)) == 1


def test_same_name_different_zip_stay_separate():
    df = rows(
        {"name": "Bluebird Services", "zip": "10001", "source": "A", "entity_id": "1"},
        {"name": "Bluebird Services", "zip": "11201", "source": "A", "entity_id": "2"},
    )
    assert len(deduplicate(df)) == 2


def test_merge_is_transitive():
    df = rows(
        {"name": "Alpha Group", "zip": "10001", "phone": "2125550101", "source": "A", "entity_id": "1"},
        {"name": "Alpha Group", "zip": "10001", "phone": "", "source": "B", "entity_id": "2"},
        {"name": "Other Name", "zip": "10301", "phone": "2125550101", "source": "C", "entity_id": "3"},
    )
    out = deduplicate(df)
    assert len(out) == 1
    assert out.iloc[0]["source"] == "A; B; C"
