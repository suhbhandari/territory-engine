from src.evals import first_attempt_summary


def test_first_attempts_add_up_per_step():
    log = {
        "runs": [
            {"step": "brief", "prompt": "v1", "written": 10, "passed": 9, "failed": 1,
             "failure_types": {"digit not in cited facts": 1}},
            {"step": "brief", "prompt": "v1", "written": 20, "passed": 18, "failed": 2,
             "failure_types": {"digit not in cited facts": 1, "number word not in cited facts": 1}},
            {"step": "sequence", "prompt": "v2", "written": 5, "passed": 5, "failed": 0, "failure_types": {}},
        ],
        "retries": [
            {"step": "brief", "redone": 3, "passed": 2, "failed": 1, "failure_types": {}},
            {"step": "brief", "redone": 1, "passed": 1, "failed": 0, "failure_types": {}},
        ],
    }
    out = first_attempt_summary(log)
    brief = out["steps"]["brief"]
    assert (brief["written"], brief["passed"], brief["failed"]) == (30, 27, 3)
    assert brief["passed_pct"] == 90.0
    assert brief["failure_types"] == {"digit not in cited facts": 2, "number word not in cited facts": 1}
    assert brief["prompts"] == ["v1"]
    assert out["steps"]["sequence"]["passed_pct"] == 100.0
    assert out["retries"]["brief"] == {"redone": 4, "passed": 3}


def test_empty_log_gives_empty_summary():
    assert first_attempt_summary({}) == {"steps": {}, "retries": {}}
