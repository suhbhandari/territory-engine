from src.evals import first_attempt_summary

LOG = {
    "runs": [
        {"step": "brief", "prompt": "v1", "written": 10, "passed": 9, "failed": 1,
         "failure_types": {"digit not in cited facts": 1}},
        {"step": "brief", "prompt": "v1", "written": 20, "passed": 18, "failed": 2,
         "failure_types": {"digit not in cited facts": 1, "number word not in cited facts": 1}},
        {"step": "brief", "prompt": "v2", "written": 40, "passed": 40, "failed": 0, "failure_types": {}},
        {"step": "sequence", "prompt": "v2", "written": 5, "passed": 5, "failed": 0, "failure_types": {}},
    ],
    "retries": [
        {"step": "brief", "redone": 3, "passed": 2, "failed": 1, "failure_types": {}},
        {"step": "brief", "redone": 1, "passed": 1, "failed": 0, "failure_types": {}},
    ],
}


def by(summary, step, prompt):
    return next(t for t in summary["steps"] if t["step"] == step and t["prompt"] == prompt)


def test_runs_of_one_prompt_version_add_up():
    t = by(first_attempt_summary(LOG), "brief", "v1")
    assert (t["written"], t["passed"], t["failed"]) == (30, 27, 3)
    assert t["passed_pct"] == 90.0
    assert t["failure_types"] == {"digit not in cited facts": 2, "number word not in cited facts": 1}


def test_prompt_versions_are_kept_apart():
    """Merging them would hide that a rate belongs to a particular prompt, which is the
    only thing that makes the rate mean anything."""
    summary = first_attempt_summary(LOG)
    assert by(summary, "brief", "v2")["passed_pct"] == 100.0
    assert by(summary, "brief", "v1")["passed_pct"] == 90.0
    assert len([t for t in summary["steps"] if t["step"] == "brief"]) == 2


def test_retries_are_counted_per_step():
    assert first_attempt_summary(LOG)["retries"]["brief"] == {"redone": 4, "passed": 3}


def test_a_run_with_no_prompt_recorded_is_still_counted():
    out = first_attempt_summary({"runs": [{"step": "brief", "written": 2, "passed": 2, "failed": 0}]})
    assert out["steps"][0]["prompt"] == "unrecorded"
    assert out["steps"][0]["passed_pct"] == 100.0


def test_empty_log_gives_empty_summary():
    assert first_attempt_summary({}) == {"steps": [], "retries": {}}
