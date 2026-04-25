import json
from pathlib import Path

from megaplan.bakeoff.comparison import build_comparison, write_comparison


def test_comparison_schema_stable_for_mixed_profiles_and_relative_receipts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = {
        "schema_version": 1,
        "experiment_id": "exp-1",
        "base_sha": "base",
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": [
            {
                "name": "done",
                "worktree": str(tmp_path / "wt-done"),
                "plan_id": "exp-1",
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": {"status": "done"},
                "log_path": str(root / "done.log"),
                "outcome_path": str(root / "done.json"),
            },
            {
                "name": "failed",
                "worktree": str(tmp_path / "wt-failed"),
                "plan_id": "exp-1",
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": {"status": "failed"},
                "log_path": str(root / "failed.log"),
                "outcome_path": str(root / "failed.json"),
            },
        ],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }
    metric_keys = {
        "duration_s": None,
        "cost_usd": None,
        "rework_cycles": 0,
        "escalations": 0,
        "review_verdict": None,
        "diff_lines": None,
        "tests_added": None,
        "scope_drift_severity_by_phase": {
            "plan": None,
            "critique": None,
            "gate": None,
            "finalize": None,
            "execute": None,
            "review": None,
            "sprint1_pending": True,
        },
        "receipts_ref": ["execution.json"],
        "outcome_status": "done",
    }
    comparison = build_comparison(
        state,
        {
            "done": metric_keys,
            "failed": {**metric_keys, "outcome_status": "failed", "receipts_ref": []},
        },
        None,
    )

    json_path, md_path = write_comparison(root, comparison)
    loaded = json.loads(json_path.read_text(encoding="utf-8"))

    assert loaded["schema_version"] == 1
    assert [profile["name"] for profile in loaded["profiles"]] == ["done", "failed"]
    assert loaded["profiles"][0]["outcome_status"] == "done"
    assert loaded["profiles"][1]["outcome_status"] == "failed"
    assert loaded["profiles"][0]["receipts_ref"] == ["execution.json"]
    assert not Path(loaded["profiles"][0]["receipts_ref"][0]).is_absolute()
    assert set(loaded["profiles"][1]["metrics"]) == {
        "duration_s",
        "cost_usd",
        "rework_cycles",
        "escalations",
        "review_verdict",
        "diff_lines",
        "tests_added",
        "scope_drift_severity_by_phase",
    }
    assert "judge skipped: no --judge flag" in md_path.read_text(encoding="utf-8")
