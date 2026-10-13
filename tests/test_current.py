import pandas as pd

from src.current import saved_facts, split

CFG = {"sources": {"s": {"label": "Site", "url": "{website}"}},
       "facts": [{"text": "Has {n} sites", "source": "s"}]}


def scored():
    return pd.DataFrame([
        {"account_group": g, "rank_in_group": "1", "tier": t, "n": n, "website": "w", "name": g}
        for g, t, n in (("g1", "A", "3"), ("g2", "A", "2"), ("g3", "C", "1"), ("g4", "A", "5"), ("g5", "A", "6"))
    ])


def write(path, n, url="w"):
    path.write_text(f"# x\n\n## Facts and sources\n- **F1** Has {n} sites ([Site]({url}), checked 2026-10-09)\n")


def test_saved_facts_reads_fact_lines(tmp_path):
    write(tmp_path / "a.md", 3)
    assert saved_facts(tmp_path / "a.md") == [("Has 3 sites", "Site", "w")]
    assert saved_facts(tmp_path / "missing.md") == []


def test_current_stale_and_dropped(tmp_path):
    write(tmp_path / "g1.md", 3)            # matches the data
    write(tmp_path / "g2.md", 4)            # a fact changed since it was written
    write(tmp_path / "g3.md", 1)            # group no longer in a tier that gets text
    write(tmp_path / "g4.md", 5, url="old")  # source link changed
    write(tmp_path / "g5.md", 6)            # matches, but fails a check added since
    index = pd.DataFrame({"account_group": ["g1", "g2", "g3", "g4", "g5"],
                          "file": [f"g{i}.md" for i in range(1, 6)], "check_status": ["passed"] * 5})
    recheck = lambda row, lead, facts: ["bad"] if row["account_group"] == "g5" else []
    current, stale = split(index, scored(), ["A", "B"], CFG, tmp_path, recheck)
    assert list(current["account_group"]) == ["g1"]
    assert stale == {"g2": "facts changed", "g4": "facts changed", "g5": "fails current checks"}


def test_undated_fact_is_stale_once_its_source_has_a_date(tmp_path):
    cfg = {"sources": {"s": {"label": "Site", "url": "{website}", "date_column": "checked"}},
           "facts": [{"text": "Has {n} sites", "source": "s"}]}
    rows = pd.DataFrame([{"account_group": "g1", "rank_in_group": "1", "tier": "A", "n": "3", "website": "w",
                          "name": "g1", "checked": "2026-10-13T08:00:00"}])
    (tmp_path / "old.md").write_text("- **F1** Has 3 sites ([Site](w))\n")
    (tmp_path / "new.md").write_text("- **F1** Has 3 sites ([Site](w), checked 2026-10-09)\n")
    for name, expected in (("old.md", {"g1": "facts not dated"}), ("new.md", {})):
        index = pd.DataFrame({"account_group": ["g1"], "file": [name], "check_status": ["passed"]})
        assert split(index, rows, ["A"], cfg, tmp_path)[1] == expected


def test_saved_text_is_rechecked_against_a_check_added_later(tmp_path):
    """A check added after a brief was written has to reach the saved text, or the build
    keeps publishing text that the same check would reject if it were written today."""
    import pandas as pd
    from src.current import current_briefs

    facts_cfg = {
        "tiers": ["A"],
        "sources": {"s": {"label": "Source", "url": "https://e.example", "date_column": "checked"}},
        "facts": [{"text": "Uses a job board.", "when": {"column": "ats", "op": "not_blank"}, "source": "s"}],
        "hedges": ["which suggests"],
        "claim_words": ["ongoing"],
    }
    brief = tmp_path / "0001-one.md"
    brief.write_text(
        "# One\n\n**Tier A · score 70/100 · rank 1** · data coverage 100%\n\n"
        "Uses a job board, which suggests recruiting is ongoing. [F1]\n\n"
        "## Facts and sources\n"
        "- **F1** Uses a job board. ([Source](https://e.example), checked 2026-10-13)\n")
    index = pd.DataFrame([{"account_group": "g", "file": brief.name, "check_status": "passed"}])
    scored = pd.DataFrame([{"account_group": "g", "rank_in_group": "1", "tier": "A",
                            "name": "One", "ats": "Workable", "checked": "2026-10-13"}])
    current, stale = current_briefs(index, scored, facts_cfg, tmp_path)
    assert len(current) == 0
    assert list(stale.values()) == ["fails current checks"]
