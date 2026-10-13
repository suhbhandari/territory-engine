import pandas as pd

from src.triggers import band, compare

CFG = {"watch": [{"column": "tier", "label": "Tier"}, {"column": "status", "label": "Status"},
                 {"column": "roles", "label": "Roles", "bands": [1, 5, 20]}, {"column": "added_later", "label": "New"}],
       "ignore_values": ["unreachable"]}


def frame(rows):
    base = {"group_rank": "1", "tier": "A", "name": "N", "city": "C", "status": "ok", "roles": "",
            "pts_x": "10", "signals_fetched_at": "2026-10-09T00:00:00"}
    return pd.DataFrame([dict(base, **r) for r in rows])


def test_bands():
    assert [band(v, [1, 5, 20]) for v in ("", "0", "4", "5", "19", "20", "161")] == \
        ["", "under 1", "1-4", "5-19", "5-19", "20+", "20+"]


def test_changes_new_gone_and_ignored():
    prev = frame([{"entity_id": "1", "roles": "4"}, {"entity_id": "2", "status": "ok"}, {"entity_id": "3"}])
    cur = frame([{"entity_id": "1", "roles": "7", "tier": "B", "pts_x": "4", "added_later": "y"},
                 {"entity_id": "2", "status": "unreachable"},
                 {"entity_id": "4"}])
    out = compare(prev, cur, CFG)
    got = {(r["entity_id"], r["change"], r["what"], r["before"], r["after"], r["because"]) for r in out.to_dict("records")}
    assert got == {("1", "changed", "Tier", "A", "B", "x -6"), ("1", "changed", "Roles", "1-4", "5-19", ""),
                   ("4", "new account", "", "", "", ""), ("3", "gone", "", "", "", "")}


def test_small_moves_inside_a_band_are_not_triggers():
    prev, cur = frame([{"entity_id": "1", "roles": "161"}]), frame([{"entity_id": "1", "roles": "158"}])
    assert compare(prev, cur, CFG).empty
