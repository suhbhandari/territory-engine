"""Recall is the one thing the pipeline cannot show from its own output, so the check
that measures it has to agree with the matching the pipeline already uses."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("recall_check", Path(__file__).parent.parent / "scripts" / "recall_check.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def test_records_outside_the_zip_prefixes_are_left_out():
    assert rc.in_territory({"z": "11201"}, "z", ["112", "100"]) is True
    assert rc.in_territory({"z": "90210"}, "z", ["112", "100"]) is False


def test_a_record_with_no_zip_is_left_out():
    # Counting it would make the territory look larger than the register can show.
    assert rc.in_territory({"z": ""}, "z", ["112"]) is False
    assert rc.in_territory({}, "z", ["112"]) is False
