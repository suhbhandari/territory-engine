"""The out-of-date check reads saved briefs and sequences back from their files. These tests
render with the real renderers and read back with the real readers, so a change to either
side that breaks the other fails here instead of silently marking text stale or current."""

from src import brief, sequence
from src.current import saved_facts

ROW = {"name": "Bluebird Services", "tier": "A", "score": "80", "group_rank": "1", "data_coverage": "0.9",
       "address": "12 Main St", "city": "Brooklyn", "zip": "11201", "phone": "718-555-0101",
       "score_reasons": "Live website"}
FACTS = [
    {"id": "F1", "text": "Has 3 sites (all local).", "source_label": "Registry record 1 (A)", "source_url": "https://r.example/1",
     "as_of": "2026-10-09"},
    {"id": "F2", "text": "Shares a domain.", "source_label": "This territory list, built from A records", "source_url": "",
     "as_of": ""},
]
BRIEF = {"headline": {"text": "Bluebird runs 3 sites.", "fact_ids": ["F1"]},
         "snapshot": [{"text": "Three sites.", "fact_ids": ["F1"]}, {"text": "Shared domain.", "fact_ids": ["F1", "F2"]}],
         "why_now": [{"text": "Nothing on hiring.", "fact_ids": ["F2"]}],
         "opening_angle": {"text": "Ask about the sites.", "fact_ids": ["F1"]}}


def test_brief_round_trip(tmp_path):
    for members in ([ROW], [ROW, dict(ROW, name="Bluebird Two")]):
        md = brief.render(ROW, members, BRIEF, FACTS, ["Headcount unknown."], [])
        statements = brief.saved_statements(md)
        assert [(s["text"], s["fact_ids"]) for _, s in statements] == [
            ("Bluebird runs 3 sites.", ["F1"]), ("Three sites.", ["F1"]), ("Shared domain.", ["F1", "F2"]),
            ("Nothing on hiring.", ["F2"]), ("Ask about the sites.", ["F1"])]
        path = tmp_path / "b.md"
        path.write_text(md)
        assert saved_facts(path) == [(f["text"], f["source_label"], f["source_url"]) for f in FACTS]


def test_brief_with_failed_check_banner_still_reads_back():
    md = brief.render(ROW, [ROW], BRIEF, FACTS, [], ["headline: number 9 is not in the cited facts"])
    assert len(brief.saved_statements(md)) == 5


def test_sequence_facts_round_trip(tmp_path):
    rows = [{"touch": 1, "channel": "email", "day": 1, "subject": "s", "body": "b", "fact_ids": "F1", "word_count": 1}]
    path = tmp_path / "s.md"
    path.write_text(sequence.render(ROW, {"title": "Owner"}, rows, FACTS, []))
    assert saved_facts(path) == [(f["text"], f["source_label"], f["source_url"]) for f in FACTS]
