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


def test_doc_mode_comparison_uses_doc_metrics_and_renders_doc_table(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = {
        "schema_version": 1,
        "experiment_id": "exp-doc",
        "base_sha": "base",
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "doc",
        "output_path": "docs/foo.md",
        "profiles": [
            {
                "name": "alpha",
                "worktree": str(tmp_path / "wt-alpha"),
                "plan_id": "exp-doc",
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": {"status": "done"},
                "log_path": str(root / "alpha.log"),
                "outcome_path": str(root / "alpha.json"),
            },
        ],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }
    metrics = {
        "duration_s": 10.0,
        "cost_usd": 0.42,
        "rework_cycles": 0,
        "escalations": 0,
        "review_verdict": "pass",
        "doc_path": "docs/foo.md",
        "doc_present": True,
        "doc_size_bytes": 123,
        "doc_line_count": 7,
        "scope_drift_severity_by_phase": {
            "plan": None, "critique": None, "gate": None,
            "finalize": None, "execute": None, "review": None, "sprint1_pending": True,
        },
        "outcome_status": "done",
        "receipts_ref": [],
    }

    comparison = build_comparison(state, {"alpha": metrics}, None)
    assert comparison["mode"] == "doc"
    assert comparison["output_path"] == "docs/foo.md"
    profile = comparison["profiles"][0]
    # Doc-mode comparison should expose doc_* metrics, not diff_lines/tests_added.
    assert "doc_present" in profile["metrics"]
    assert "doc_size_bytes" in profile["metrics"]
    assert "doc_line_count" in profile["metrics"]
    assert "diff_lines" not in profile["metrics"]
    assert "tests_added" not in profile["metrics"]

    json_path, md_path = write_comparison(root, comparison)
    md = md_path.read_text(encoding="utf-8")
    assert "doc mode" in md
    assert "docs/foo.md" in md
    assert "doc_present" in md
    assert "doc_size_bytes" in md
    assert "diff_lines" not in md
    assert "tests_added" not in md
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["mode"] == "doc"
    assert loaded["output_path"] == "docs/foo.md"
