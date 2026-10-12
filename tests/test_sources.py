from src.sources import google_maps, nppes


def comp(text, *types):
    return {"shortText": text, "types": list(types)}


PLACE = {
    "id": "place-1",
    "displayName": {"text": " Bluebird Services "},
    "addressComponents": [
        comp("12", "street_number"), comp("Main St", "route"), comp("Brooklyn", "sublocality_level_1"),
        comp("NY", "administrative_area_level_1"), comp("11201-1234", "postal_code"),
    ],
    "nationalPhoneNumber": "(718) 555-0101",
    "websiteUri": "https://bluebird.example/",
    "primaryTypeDisplayName": {"text": "Consultant"},
    "businessStatus": "OPERATIONAL",
}


def test_maps_record_parses_address_components():
    rec = google_maps._to_record(PLACE)
    assert rec["name"] == "Bluebird Services"
    assert rec["address"] == "12 Main St"
    assert rec["city"] == "Brooklyn"  # falls back to sublocality when there is no locality
    assert rec["state"] == "NY" and rec["zip"] == "11201"
    assert rec["license_type"] == "Consultant" and rec["entity_id"] == "place-1"


def test_maps_record_without_type_is_unknown():
    rec = google_maps._to_record(dict(PLACE, primaryTypeDisplayName={}))
    assert rec["license_type"] == "Unknown"


def test_maps_fetch_filters_closed_out_of_area_and_excluded(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test")
    closed = dict(PLACE, id="p2", businessStatus="CLOSED_PERMANENTLY")
    elsewhere = dict(PLACE, id="p3", addressComponents=PLACE["addressComponents"][:4] + [comp("07001", "postal_code")])
    excluded = dict(PLACE, id="p4", primaryType="store")
    monkeypatch.setattr(google_maps, "_search", lambda *a: [PLACE, closed, elsewhere, excluded])
    monkeypatch.setattr(google_maps.time, "sleep", lambda s: None)
    df = google_maps.fetch({"search_templates": ["x {city}"], "exclude_types": ["store"]},
                           {"state": "NY", "search_cities": ["A"], "zip_prefixes": ["112"]})
    assert list(df["entity_id"]) == ["place-1"]


def test_maps_fetch_without_key_returns_empty(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    assert google_maps.fetch({}, {}).empty


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def registry_result(number, name, zip_code, primary):
    return {
        "number": number,
        "basic": {"organization_name": name},
        "addresses": [
            {"address_purpose": "MAILING", "postal_code": "070010000", "address_1": "PO Box 1"},
            {"address_purpose": "LOCATION", "postal_code": zip_code + "0000", "address_1": "1 Main St",
             "city": "BROOKLYN", "state": "NY", "telephone_number": "718-555-0101"},
        ],
        "taxonomies": [{"desc": "Other", "primary": False}, {"desc": primary, "primary": True}],
    }


def test_registry_keeps_location_address_and_primary_type(monkeypatch):
    payload = {"results": [
        registry_result(1111111111, "BLUEBIRD SERVICES LLC", "11201", "Type A"),
        registry_result(2222222222, "OUT OF AREA LLC", "07001", "Type A"),  # location outside the prefix
        registry_result(3333333333, "SECONDARY ONLY LLC", "11201", "Type B"),
    ]}
    monkeypatch.setattr(nppes.requests, "get", lambda *a, **k: FakeResponse(payload))
    df = nppes.fetch({"taxonomies": ["x", "y"], "primary_taxonomies": ["Type A"]},
                     {"state": "NY", "zip_prefixes": ["112"]})
    assert list(df["entity_id"]) == ["1111111111"]  # deduped across searches, filtered by primary type
    row = df.iloc[0]
    assert row["name"] == "Bluebird Services Llc" and row["city"] == "Brooklyn"
    assert row["zip"] == "11201" and row["address"] == "1 Main St"
