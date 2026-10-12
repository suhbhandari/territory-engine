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
