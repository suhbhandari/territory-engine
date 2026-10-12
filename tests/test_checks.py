from src.brief import _numbers, build_facts, build_unknowns, check_statements, source_check
from src.sequence import check

FACTS = [{"id": "F1", "text": "Lists 1,204 open roles in NY."}, {"id": "F2", "text": "Founded 2015."}]


def st(text, *ids):
    return ("s", {"text": text, "fact_ids": list(ids)})


def test_numbers_with_thousands_separators():
    assert _numbers("1,204 roles since 2015 and 3") == ["1204", "2015", "3"]


def test_statement_with_supported_number_passes():
    assert check_statements([st("It lists 1204 open roles.", "F1")], FACTS) == []


def test_statement_without_citation_fails():
    assert check_statements([st("A claim.")], FACTS) == ["s: no fact cited"]


def test_unknown_fact_id_fails():
    assert "cites unknown fact F9" in check_statements([st("x", "F9")], FACTS)[0]


def test_number_not_in_cited_fact_fails_even_if_in_another_fact():
    assert check_statements([st("Founded 2015.", "F1")], FACTS) == ["s: number 2015 is not in the cited facts"]


def test_digits_in_the_account_name_are_allowed():
    assert check_statements([st("Route 66 Services lists 1204 roles.", "F1")], FACTS, "Route 66 Services") == []


def test_source_check_covers_every_section():
    brief = {"headline": {"text": "h", "fact_ids": ["F1"]}, "opening_angle": {"text": "o", "fact_ids": []},
             "snapshot": [{"text": "99 sites", "fact_ids": ["F2"]}], "why_now": []}
    problems = source_check(brief, FACTS)
    assert "opening_angle: no fact cited" in problems
    assert "snapshot[0]: number 99 is not in the cited facts" in problems


CFG = {
    "sources": {"site": {"label": "Website", "url": "{website}"}},
    "facts": [
        {"text": "Has a website: {website}", "when": {"column": "website", "op": "not_blank"}, "source": "site"},
        {"text": "Always shown for {name}", "source": "site"},
    ],
    "unknowns": [{"text": "No site", "when": {"column": "website", "op": "blank"}}, {"text": "Always"}],
}


def test_facts_only_built_when_their_condition_holds_and_are_numbered():
    with_site = build_facts({"website": "x.example", "name": "N"}, CFG)
    assert [f["id"] for f in with_site] == ["F1", "F2"]
    assert with_site[0]["source_url"] == "x.example"
    assert [f["id"] for f in build_facts({"website": "", "name": "N"}, CFG)] == ["F1"]
    assert build_unknowns({"website": ""}, CFG) == ["No site", "Always"]


SEQ_CFG = {
    "subject_max_chars": 20,
    "merge_fields": ["{{first_name}}"],
    "touches": [{"id": "e1", "max_words": 6, "subject": True}, {"id": "c1", "max_words": 50}],
}


def touch(tid, subject, body, ids=("F2",)):
    return {"touch_id": tid, "subject": subject, "body": body, "fact_ids": list(ids)}


def test_good_sequence_passes():
    result = {"touches": [touch("e1", "since 2015", "Hi {{first_name}}, founded 2015?"), touch("c1", "", "Hello.")]}
    assert check(result, FACTS, {"name": "N"}, SEQ_CFG) == []


def test_sequence_rule_breaks_are_each_reported():
    result = {"touches": [
        touch("e1", "a subject that is far too long", "one two three four five six seven {{last_name}}"),
        touch("x9", "", "extra"),
    ]}
    problems = check(result, FACTS, {"name": "N"}, SEQ_CFG)
    assert "e1: 8 words, limit 6" in problems
    assert any(p.startswith("e1: subject is") for p in problems)
    assert "e1: merge field {{last_name}} is not allowed" in problems
    assert "c1: missing" in problems
    assert "unexpected touches: x9" in problems


def test_call_touch_must_have_empty_subject():
    result = {"touches": [touch("e1", "s", "ok"), touch("c1", "not empty", "ok")]}
    assert "c1: subject should be empty" in check(result, FACTS, {"name": "N"}, SEQ_CFG)


# --- wording the facts do not support -------------------------------------------------

from src.brief import parse_fact_line, render_fact, saved_statements, unsupported_words  # noqa: E402

SOURCE = "Registered practice location: 12 Main St, Brooklyn, NY 11201. Runs hiring through Workday."


def test_place_not_in_the_facts_is_flagged():
    assert unsupported_words("An office in Midtown that uses Workday.", SOURCE) == ["Midtown"]


def test_sentence_starts_contractions_and_allowed_words_pass():
    text = "Brooklyn office. I'm asking about the Main Street site.\nHi {{first_name}}, Workday is in use."
    assert unsupported_words(text, SOURCE, allowed=["Street"]) == []


def test_hyphenated_and_possessive_words_are_checked_by_part():
    assert unsupported_words("A Brooklyn-based team and Workday's board.", SOURCE) == []
    assert unsupported_words("A Harlem-based team.", SOURCE) == ["Harlem"]


def test_number_words_must_match_a_cited_number():
    assert unsupported_words("It has three sites.", "Runs 3 sites.") == []
    assert unsupported_words("It has five sites.", "Runs 3 sites.") == ["five"]


def test_check_statements_reports_unsupported_words():
    facts = [{"id": "F1", "text": SOURCE}]
    assert check_statements([st("A team near Harlem that uses Workday.", "F1")], facts) == [
        "s: 'Harlem' is not in the cited facts"]


def test_fact_lines_round_trip_with_and_without_link_and_date():
    linked = {"id": "F1", "text": "Has 3 sites (all local).", "source_label": "Site (x)", "source_url": "https://x",
              "as_of": "2026-10-09"}
    plain = {"id": "F2", "text": "Shares a domain.", "source_label": "This territory list, built from A records",
             "source_url": "", "as_of": ""}
    for fact in (linked, plain):
        line = render_fact(fact)
        assert parse_fact_line(line) == fact
    assert render_fact(linked).endswith("([Site (x)](https://x), checked 2026-10-09)")


def test_saved_statements_reads_back_every_section():
    md = """# Name

**Tier A · score 90/100 · rank 1** · data coverage 100%

Headline text [F1]

## Snapshot
- Snap one [F1, F2]

## Why now
- Why one [F2]

## Opening angle
Angle text [F1]

## Contact
- 12 Main St
"""
    got = saved_statements(md)
    assert [(s, d["text"], d["fact_ids"]) for s, d in got] == [
        ("headline", "Headline text", ["F1"]), ("Snapshot", "Snap one", ["F1", "F2"]),
        ("Why now", "Why one", ["F2"]), ("Opening angle", "Angle text", ["F1"])]
