import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("agreement", Path(__file__).parent.parent / "scripts" / "agreement.py")
agreement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agreement)


def sheet(items):
    out = ["# sheet", ""]
    for gid, (ba, bu, da, ds, first) in items.items():
        out += [f"## {gid}: Some Business", "text F1", f"- Brief accuracy (1-5): {ba}", f"- Brief usefulness (1-5): {bu}",
                f"- Draft accuracy (1-5): {da}", f"- Draft sendability (1-5): {ds}",
                f"- First this week? (yes / no / not sure): {first}", "- Notes: fine", ""]
    return "\n".join(out)


def model_csv(tmp_path, name, rows):
    path = tmp_path / name
    pd.DataFrame([{"id": k, "brief_accuracy": v[0], "brief_usefulness": v[1], "draft_accuracy": v[2],
                   "draft_sendability": v[3], "first_this_week": v[4], "note": "n"} for k, v in rows.items()]).to_csv(path, index=False)
    return path


def test_exact_and_within_one_per_round(tmp_path):
    hand = tmp_path / "hand.md"
    hand.write_text(sheet({"G1": (5, 3, 4, 2, "yes"), "G2": (4, 1, 5, 3, "no")}))
    r1 = model_csv(tmp_path, "m1.csv", {"G1": (5, 2, 4, 4, "yes"), "G2": (4, 3, 5, 3, "not sure")})
    out = agreement.main(hand, [("round 1", r1, "different")], tmp_path / "agreement.json")
    d = out["rounds"][0]["dimensions"]
    assert d["brief_accuracy"]["exact_pct"] == 100.0
    assert (d["brief_usefulness"]["exact_pct"], d["brief_usefulness"]["within_one_pct"]) == (0.0, 50.0)
    assert (d["draft_sendability"]["exact_pct"], d["draft_sendability"]["within_one_pct"]) == (50.0, 50.0)
    assert d["brief_usefulness"]["hand_mean"] == 2.0 and d["brief_usefulness"]["model_mean"] == 2.5
    assert out["rounds"][0]["first_this_week"] == {"exact_pct": 50.0, "hand_yes": 1, "model_yes": 1}
    assert out["rounds"][0]["same_text"] is False


def test_an_unsaved_or_blank_sheet_stops_with_a_plain_message(tmp_path):
    hand = tmp_path / "hand.md"
    hand.write_text(sheet({"G1": (5, 3, 4, 2, "yes"), "G2": ("", "", "", "", "")}))
    with pytest.raises(SystemExit, match="5 grades are blank"):
        agreement.main(hand, [], tmp_path / "agreement.json")
    assert not (tmp_path / "agreement.json").exists()


def test_output_holds_numbers_not_names_or_notes(tmp_path):
    hand = tmp_path / "hand.md"
    hand.write_text(sheet({"G1": (5, 3, 4, 2, "yes")}))
    r = model_csv(tmp_path, "m.csv", {"G1": (5, 3, 4, 2, "yes")})
    agreement.main(hand, [("round 2", r, "same")], tmp_path / "agreement.json")
    text = (tmp_path / "agreement.json").read_text()
    assert "Some Business" not in text and "fine" not in text and '"n"' not in text
    assert json.loads(text)["rounds"][0]["same_text"] is True
