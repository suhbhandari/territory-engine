from src.backfill import match

ACCOUNT = {"name": "Bluebird Services LLC", "zip": "10001", "phone": "212-555-0101"}


def cand(**kw):
    base = {"name": "Something Else", "zip": "99999", "phone": "", "entity_id": "c"}
    base.update(kw)
    return base


def test_phone_match_wins_even_with_another_name():
    found, reason = match(ACCOUNT, [cand(name="Unrelated", phone="(212) 555-0101")])
    assert reason == "phone" and found["name"] == "Unrelated"


def test_near_identical_name_in_same_zip_matches():
    found, reason = match(ACCOUNT, [cand(name="Bluebird Services Inc", zip="10001")])
    assert reason == "name+zip"


def test_similar_name_in_other_zip_is_rejected():
    assert match(ACCOUNT, [cand(name="Bluebird Services", zip="10002")]) == (None, "no_match")


def test_loosely_similar_name_is_rejected():
    assert match(ACCOUNT, [cand(name="Bluejay Partners", zip="10001")]) == (None, "no_match")


def test_no_candidates():
    assert match(ACCOUNT, []) == (None, "no_match")
