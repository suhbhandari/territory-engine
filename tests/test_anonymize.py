from src.anonymize import identifying_words, leaks, scrub, short_name

MEMBER = {"name": "Bluebird Wellness Services LLC", "address": "12 Main Street", "phone": "(718) 555-0101",
          "entity_id": "1234567890", "website_domain": "bluebirdwell.example"}
ALIAS = "Account 0007"


def words():
    return identifying_words([MEMBER], generic={"services", "wellness"}, place_words={"brooklyn"})


def test_identifying_words_skip_generic_and_place_words():
    assert words() == {"bluebird", "llc", "bluebirdwell"}


def test_short_name_drops_legal_suffix():
    assert short_name("Bluebird Services, Inc.") == "Bluebird Services"


def test_scrub_removes_every_identifier():
    text = ("Bluebird Wellness Services LLC at 12 Main Street, Brooklyn NY 11201. Call (718) 555-0101, "
            "visit https://bluebirdwell.example/careers or bluebirdwell.example. NPI 1234567890. Bluebird's team.")
    out = scrub(text, ALIAS, [MEMBER], words())
    assert leaks(out, [MEMBER], words()) == []
    assert "Account 0007" in out and "112xx" in out
    for gone in ("Bluebird", "Main Street", "555-0101", "bluebirdwell", "1234567890", "11201"):
        assert gone.lower() not in out.lower()


def test_scrub_leaves_ordinary_text_alone():
    text = "Registered 11 years ago; runs hiring through Workday."
    assert scrub(text, ALIAS, [MEMBER], words()) == text
    assert scrub("Lists 12 open roles.", ALIAS, [MEMBER], words()) == "Lists 5-19 open roles."


def test_leak_check_catches_what_scrub_missed():
    found = leaks("Ask for the Bluebird office, number ends 5550101, site bluebirdwell.example", [MEMBER], words())
    assert "bluebird" in found
    assert "phone …5550101" in found
    assert "bluebirdwell.example" in found


def test_open_role_counts_become_ranges():
    from src.anonymize import band, band_counts

    assert [band(x) for x in ("", "0", "3", "5", "19", "20", "99", "161", "1,204")] == \
        ["", "0", "1-4", "5-19", "5-19", "20-49", "50-99", "100+", "100+"]
    text = ("Its job board lists 161 open roles located in NY, out of 192 across all locations. "
            "Of these: 17 are scheduling roles. At least 4 open role(s). Registered 11 years ago. 3 locations share it.")
    assert band_counts(text) == (
        "Its job board lists 100+ open roles located in NY, out of 100+ across all locations. "
        "Of these: 5-19 are scheduling roles. At least 1-4 open role(s). Registered 11 years ago. 3 locations share it.")


def test_hiring_system_names_are_hidden_as_whole_words():
    from src.anonymize import hide_terms

    assert hide_terms("Runs hiring through ADP and Workday; ADPX is not one.", {"ADP", "Workday"}, "[hiring system]") == \
        "Runs hiring through [hiring system] and [hiring system]; ADPX is not one."
