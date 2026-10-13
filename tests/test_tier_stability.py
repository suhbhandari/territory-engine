"""The weight-change test has to rank the same way the scorer does, or its answer is
about the test rather than the rubric."""
import importlib.util
from pathlib import Path

import pandas as pd

spec = importlib.util.spec_from_file_location("tier_stability", Path(__file__).parent.parent / "scripts" / "tier_stability.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

TIERS = [{"name": "A", "min_score": 60}, {"name": "B", "min_score": 42}, {"name": "C", "min_score": 0}]
DF = pd.DataFrame([
    {"name": "one", "account_group": "g1", "score": 80.0, "data_coverage": 1.0, "pts_x": 40.0},
    {"name": "two", "account_group": "g1", "score": 70.0, "data_coverage": 1.0, "pts_x": 30.0},
    {"name": "three", "account_group": "g2", "score": 50.0, "data_coverage": 1.0, "pts_x": 0.0},
    {"name": "four", "account_group": "g3", "score": 30.0, "data_coverage": 1.0, "pts_x": 30.0},
])


def test_a_group_takes_the_position_of_its_best_account():
    ranks = ts.rank_groups(DF, DF["score"])
    assert ranks.tolist() == [0, 0, 1, 2]


def test_top_tier_uses_the_best_account_in_each_group():
    assert ts.top_tier_groups(DF, DF["score"], TIERS, {"A"}) == {"g1"}
    assert ts.top_tier_groups(DF, DF["score"], TIERS, {"A", "B"}) == {"g1", "g2"}


def test_lowering_a_weight_can_push_a_group_out_of_the_same_sized_top():
    # g3 scores only on x; halving x drops it below g2, which scores on nothing else.
    changed = DF["score"] - DF["pts_x"] + DF["pts_x"] * 0.5
    assert ts.top_n_groups(DF, DF["score"], 2) == {"g1", "g2"}
    assert ts.top_n_groups(DF, changed, 2) == {"g1", "g2"}


def test_an_unchanged_weight_keeps_everything():
    out = ts.compare(DF, DF["score"], DF["score"], TIERS, {"A", "B"})
    assert out["same_size_kept_pct"] == 100.0
    assert out["swapped"] == 0
    assert out["worst_places_moved"] == 0


def test_the_two_measures_are_reported_separately():
    changed = DF["score"] - DF["pts_x"] + DF["pts_x"] * 3
    out = ts.compare(DF, DF["score"], changed, TIERS, {"A", "B"})
    # Raising a weight lifts every score, so nothing falls below a written cut-off.
    assert out["fixed_cut_kept_pct"] == 100.0
    assert out["fixed_cut_size"] >= out["same_size_kept_pct"] / 100 * 2
