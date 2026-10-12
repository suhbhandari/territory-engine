import pandas as pd

from src.current import saved_fact_texts, split

CFG = {"sources": {"s": {"label": "Site", "url": "{website}"}},
       "facts": [{"text": "Has {n} sites", "source": "s"}]}


def scored():
    return pd.DataFrame([
        {"account_group": "g1", "rank_in_group": "1", "tier": "A", "n": "3", "website": "w"},
        {"account_group": "g2", "rank_in_group": "1", "tier": "A", "n": "2", "website": "w"},
        {"account_group": "g3", "rank_in_group": "1", "tier": "C", "n": "1", "website": "w"},
    ])


def write(path, n):
    path.write_text(f"# x\n\n## Facts and sources\n- **F1** Has {n} sites ([Site](w))\n")


def test_saved_fact_texts_reads_fact_lines(tmp_path):
    write(tmp_path / "a.md", 3)
    assert saved_fact_texts(tmp_path / "a.md") == ["Has 3 sites"]
    assert saved_fact_texts(tmp_path / "missing.md") == []


def test_current_stale_and_dropped(tmp_path):
    write(tmp_path / "g1.md", 3)   # matches the data
    write(tmp_path / "g2.md", 4)   # a fact changed since it was written
    write(tmp_path / "g3.md", 1)   # group no longer in a tier that gets text
    index = pd.DataFrame({"account_group": ["g1", "g2", "g3"], "file": ["g1.md", "g2.md", "g3.md"]})
    current, stale = split(index, scored(), ["A", "B"], CFG, tmp_path)
    assert list(current["account_group"]) == ["g1"]
    assert stale == {"g2"}
