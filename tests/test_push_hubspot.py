import json

import pandas as pd
import pytest

from src import push_hubspot as hs

CFG = {
    "object": "companies",
    "id_property": "territory_engine_id",
    "tiers": ["A", "B"],
    "group": {"name": "territory_engine", "label": "Territory Engine"},
    "properties": [
        {"name": "name", "standard": True, "value": {"public": "{id}", "raw": "{name}"}},
        {"name": "phone", "standard": True, "value": {"raw": "{phone}"}},
        {"name": "territory_engine_id", "label": "ID", "type": "string", "field_type": "text", "unique": True,
         "value": {"public": "{id}", "raw": "{entity_id}"}},
        {"name": "territory_tier", "label": "Tier", "type": "enumeration", "field_type": "select",
         "options": ["A", "B"], "value": {"public": "{tier}", "raw": "{tier}"}},
        {"name": "territory_score", "label": "Score", "type": "number", "field_type": "number",
         "value": {"public": "{score}", "raw": "{score}"}},
        {"name": "has_site", "label": "Site", "type": "bool", "field_type": "booleancheckbox",
         "value": {"public": "{has_website}"}},
    ],
}

ACCOUNTS = pd.DataFrame([
    {"id": "Account 0001", "tier": "A", "score": "88", "has_website": "True"},
    {"id": "Account 0002", "tier": "B", "score": "50", "has_website": "False"},
    {"id": "Account 0003", "tier": "D", "score": "5", "has_website": ""},
])


class Response:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.content = b"" if body is None else b"x"
        self.text = json.dumps(body)

    def json(self):
        if self._body == "not json":
            raise ValueError("Expecting value")
        return self._body


class FakeHubSpot:
    """An in-memory HubSpot: enough of the companies and properties API for these tests."""

    def __init__(self, fail_first=()):
        self.companies, self.properties, self.groups = {}, {}, set()
        self.calls, self.fail_first = [], list(fail_first)

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = url.replace(hs.API, "")
        self.calls.append((method, path))
        if self.fail_first:
            return Response(self.fail_first.pop(0), {"message": "slow down"}, {"Retry-After": "0"})
        if path.endswith("/batch/read"):
            idp = json["idProperty"]
            hits = [c for c in self.companies.values() if c.get(idp) in {i["id"] for i in json["inputs"]}]
            # HubSpot returns numbers as strings with its own formatting.
            return Response(200, {"results": [{"properties": {k: c.get(k) for k in json["properties"]}} for c in hits]})
        if path.endswith("/batch/upsert"):
            results = []
            for inp in json["inputs"]:
                new = inp["id"] not in self.companies
                self.companies.setdefault(inp["id"], {inp["idProperty"]: inp["id"]}).update(inp["properties"])
                results.append({"id": inp["id"], "new": new})
            return Response(200, {"results": results})
        if "/groups" in path:
            name = path.rsplit("/", 1)[-1]
            if method == "GET":
                # HubSpot answers a missing group with a 404 whose body is not JSON.
                return Response(200, {"name": name}) if name in self.groups else Response(404, "not json")
            self.groups.add(json["name"])
            return Response(201, json)
        if path.startswith("/crm/v3/properties/companies"):
            name = path.rsplit("/", 1)[-1]
            if method == "GET":
                return Response(200, self.properties[name]) if name in self.properties else Response(404, {"message": "no"})
            self.properties[json["name"]] = json
            return Response(201, json)
        raise AssertionError(f"unexpected call {method} {path}")


def client(fake):
    return hs.Client("test-token", session=fake, sleep=lambda s: None)


def ready(fake=None):
    """A fake HubSpot that setup has already run against."""
    fake = fake or FakeHubSpot()
    hs.setup(client(fake), CFG)
    fake.calls.clear()
    return fake


def writes(fake):
    return [c for c in fake.calls if c[0] == "POST" and not c[1].endswith("/batch/read")]


def test_mapping_uses_the_source_templates_and_tiers():
    recs = hs.build_records(CFG, ACCOUNTS, "public")
    assert [r["id"] for r in recs] == ["Account 0001", "Account 0002"]  # tier D left out
    assert recs[0]["properties"] == {"name": "Account 0001", "territory_engine_id": "Account 0001",
                                     "territory_tier": "A", "territory_score": "88", "has_site": "true"}
    assert "phone" not in recs[0]["properties"]  # no public template, so not sent


def test_dry_run_makes_no_write_calls(tmp_path):
    fake = ready()
    run = hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=False, log_path=tmp_path / "log.json")
    assert writes(fake) == []
    assert fake.companies == {}
    assert (run["to_create"], run["to_update"], run["unchanged"]) == (2, 0, 0)


def test_second_identical_push_creates_and_updates_nothing(tmp_path):
    fake = ready()
    log = tmp_path / "log.json"
    first = hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=True, log_path=log)
    assert (first["created"], first["updated"]) == (2, 0)
    fake.companies["Account 0001"]["territory_score"] = "88.0"  # how HubSpot may echo a number
    fake.calls.clear()
    second = hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=True, log_path=log)
    assert (second["created"], second["updated"], second["unchanged"]) == (0, 0, 2)
    assert writes(fake) == []
    assert len(json.loads(log.read_text())) == 2


def test_a_changed_value_is_sent_as_an_update_with_only_that_property(tmp_path):
    fake = ready()
    hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=True, log_path=tmp_path / "log.json")
    changed = ACCOUNTS.copy()
    changed.loc[0, "score"] = "90"
    create, update, unchanged = hs.diff(hs.build_records(CFG, changed, "public"), fake.companies, CFG)
    assert create == [] and len(unchanged) == 1
    assert update == [{"id": "Account 0001", "properties": {"territory_score": "90"}}]


def test_429_is_retried_then_succeeds(tmp_path):
    fake = ready()
    fake.fail_first = [429, 429]
    run = hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=True, log_path=tmp_path / "log.json")
    assert run["created"] == 2
    assert run["batches"][0]["attempts"] == 1  # the 429s landed on the property check
    assert sum(1 for c in fake.calls if c[0] == "GET") == 3


def test_push_before_setup_stops_instead_of_counting_everything_as_new(tmp_path):
    fake = FakeHubSpot()
    with pytest.raises(SystemExit, match="run make hubspot-setup first"):
        hs.push(client(fake), CFG, ACCOUNTS, "public", confirm=False, log_path=tmp_path / "log.json")
    assert not (tmp_path / "log.json").exists()


def test_missing_token_fails_with_a_plain_message(monkeypatch):
    monkeypatch.delenv("HUBSPOT_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="HUBSPOT_TOKEN is not set"):
        hs.token()


def test_setup_creates_group_and_custom_properties_once():
    fake = FakeHubSpot()
    hs.setup(client(fake), CFG)
    assert fake.groups == {"territory_engine"}
    assert set(fake.properties) == {"territory_engine_id", "territory_tier", "territory_score", "has_site"}
    assert fake.properties["territory_engine_id"]["hasUniqueValue"] is True
    assert [o["value"] for o in fake.properties["territory_tier"]["options"]] == ["A", "B"]
    fake.calls.clear()
    hs.setup(client(fake), CFG)
    assert writes(fake) == []


def test_the_shipped_config_maps_every_property_it_creates():
    import yaml
    from src.settings import DEFAULT_VERTICAL
    cfg = yaml.safe_load(open(hs.ROOT / "config" / "verticals" / DEFAULT_VERTICAL / "export.yaml"))["hubspot"]
    for p in cfg["properties"]:
        assert p.get("standard") or {"label", "type", "field_type"} <= set(p), p["name"]
        assert set(p["value"]) <= set(hs.SOURCES), p["name"]
    assert all(cfg["id_property"] in [p["name"] for p in cfg["properties"] if s in p["value"]] for s in hs.SOURCES)
