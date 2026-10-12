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
    text = "Lists 12 open roles; runs hiring through Workday."
    assert scrub(text, ALIAS, [MEMBER], words()) == text


def test_leak_check_catches_what_scrub_missed():
    found = leaks("Ask for the Bluebird office, number ends 5550101, site bluebirdwell.example", [MEMBER], words())
    assert "bluebird" in found
    assert "phone …5550101" in found
    assert "bluebirdwell.example" in found
