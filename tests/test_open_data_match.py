from src.signals import open_data_match as odm

PARAMS = {"url": "https://data.example/table.json", "name_fields": ["operator_name", "facility_name"],
          "zip_field": "zip", "phone_field": "phone", "type_field": "kind", "prefix": "license"}
RECORDS = [
    {"operator_name": "Bluebird Services, Inc.", "facility_name": "Bluebird At Home", "zip": "11201",
     "phone": "7185550101", "kind": "TYPE-A"},
    {"operator_name": "Bluebird Services Inc", "facility_name": "Bluebird Second Site", "zip": "11201",
     "phone": "", "kind": "TYPE-B"},
    {"operator_name": "Redwing Group LLC", "facility_name": "Redwing Care", "zip": "10001", "phone": "2125550199",
     "kind": "TYPE-A"},
]


def run(account, monkeypatch, records=RECORDS):
    monkeypatch.setattr(odm, "_table", lambda params: records)
    return odm.fetch(account, PARAMS)


def test_name_match_collects_every_licence(monkeypatch):
    out = run({"name": "BLUEBIRD SERVICES LLC", "zip": "10999", "phone": ""}, monkeypatch)
    assert out["license_status"] == "matched"
    assert out["license_types"] == "TYPE-A; TYPE-B"
    assert out["license_match"] == "name"


def test_phone_match_with_a_different_name(monkeypatch):
    out = run({"name": "Totally Different", "zip": "", "phone": "(212) 555-0199"}, monkeypatch)
    assert out["license_status"] == "matched" and out["license_match"] == "phone"
    assert out["license_names"] == "Redwing Group LLC"


def test_near_identical_name_needs_the_same_zip(monkeypatch):
    near = {"name": "Redwing Grup", "zip": "10001", "phone": ""}
    assert run(near, monkeypatch)["license_match"] == "name+zip"
    assert run(dict(near, zip="10002"), monkeypatch)["license_status"] == "not_found"


def test_loosely_similar_name_is_not_a_match(monkeypatch):
    out = run({"name": "Bluejay Services", "zip": "11201", "phone": ""}, monkeypatch)
    assert out == {"license_status": "not_found", "license_types": "", "license_names": "", "license_match": ""}


def test_table_is_downloaded_once(monkeypatch):
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return RECORDS

    monkeypatch.setattr(odm, "_tables", {})
    monkeypatch.setattr(odm.requests, "get", lambda *a, **k: calls.append(1) or Resp())
    for _ in range(3):
        odm.fetch({"name": "Bluebird Services", "zip": "", "phone": ""}, PARAMS)
    assert len(calls) == 1
