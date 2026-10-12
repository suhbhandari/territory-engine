import pandas as pd

from src.exclusions import reviewed_exclusions, split


def accounts():
    return pd.DataFrame({"entity_id": ["1", "2", "3", "4"], "zip": ["11201", "11050", "10001", "11050-1234"]})


def test_excluded_zips_and_reviewed_accounts_are_split_out_with_reasons():
    kept, excluded = split(accounts(), {"exclude_zips": ["11050"]}, {"3": "not the target type"})
    assert list(kept["entity_id"]) == ["1"]
    assert dict(zip(excluded["entity_id"], excluded["excluded_because"])) == {
        "2": "outside territory (excluded zip)",
        "3": "reviewed: not the target type",
        "4": "outside territory (excluded zip)",
    }


def test_no_exclusions_keeps_everything():
    kept, excluded = split(accounts(), {}, {})
    assert len(kept) == 4 and excluded.empty


def test_only_rows_marked_exclude_are_used(tmp_path):
    path = tmp_path / "exclusions.csv"
    pd.DataFrame({"entity_id": ["1", "2", "3"], "name": ["a", "b", "c"],
                  "decision": ["exclude", "", "keep"], "reason": ["r1", "", "r3"]}).to_csv(path, index=False)
    assert reviewed_exclusions(path) == {"1": "r1"}
    assert reviewed_exclusions(tmp_path / "missing.csv") == {}
