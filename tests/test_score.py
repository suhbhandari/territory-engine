import pandas as pd
import pytest

from src.score import add_derived, assign_tier, matches, score_criterion

ROW = {"n": "7", "s": "counted", "blank": "", "name": "Bluebird"}


@pytest.mark.parametrize("cond,expected", [
    ({"column": "blank", "op": "blank"}, True),
    ({"column": "s", "op": "not_blank"}, True),
    ({"column": "s", "op": "eq", "value": "counted"}, True),
    ({"column": "s", "op": "in", "value": ["a", "counted"]}, True),
    ({"column": "name", "op": "contains", "value": "BLUE"}, True),
    ({"column": "n", "op": "gte", "value": 7}, True),
    ({"column": "n", "op": "lte", "value": 6}, False),
    ({"column": "n", "op": "between", "value": [5, 7]}, True),
    ({"column": "blank", "op": "gte", "value": 0}, False),  # blank is not a number, never zero
    ({"column": "missing", "op": "blank"}, True),
])
def test_condition_ops(cond, expected):
    assert matches(cond, ROW) is expected


def test_unknown_op_raises():
    with pytest.raises(ValueError):
        matches({"column": "n", "op": "nope"}, ROW)


CRITERION = {"max_points": 10, "rules": [
    {"when": {"column": "n", "op": "gte", "value": 5}, "points": 10, "reason": "{n} found"},
    {"when": {"column": "n", "op": "gte", "value": 1}, "points": 5, "reason": "some"},
    {"when": {"column": "n", "op": "blank"}, "points": 0, "known": False},
]}


def test_first_matching_rule_wins_and_reason_is_filled():
    assert score_criterion(CRITERION, {"n": "7"}) == (10, True, "7 found")


def test_unknown_rule_lowers_coverage_not_score():
    assert score_criterion(CRITERION, {"n": ""}) == (0, False, "")


def test_no_rule_matching_counts_as_unknown():
    assert score_criterion(CRITERION, {"n": "0"}) == (0, False, "")


def test_conditions_in_a_list_must_all_hold():
    crit = {"rules": [{"when": [{"column": "a", "op": "eq", "value": "1"},
                                {"column": "b", "op": "eq", "value": "1"}], "points": 3}]}
    assert score_criterion(crit, {"a": "1", "b": "1"})[0] == 3
    assert score_criterion(crit, {"a": "1", "b": "0"})[0] == 0


TIERS = [{"name": "A", "min_score": 60}, {"name": "B", "min_score": 40}, {"name": "C", "min_score": 0}]


@pytest.mark.parametrize("score,tier", [(100, "A"), (60, "A"), (59, "B"), (40, "B"), (0, "C")])
def test_tiers(score, tier):
    assert assign_tier(score, TIERS) == tier


def test_derived_domain_counts_ignore_directory_sites():
    df = pd.DataFrame({"website": ["https://www.one.example/a", "one.example", "http://dir.example/x", ""]})
    out = add_derived(df, {"directory_domains": ["dir.example"]})
    assert list(out["website_domain"]) == ["one.example", "one.example", "", ""]
    assert list(out["domain_account_count"]) == ["2", "2", "", ""]
