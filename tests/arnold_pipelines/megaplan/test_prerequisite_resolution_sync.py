from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.blocker_recovery import evaluate_prerequisite_blockers
from arnold_pipelines.megaplan.execute.batch import (
    _reset_resolved_prerequisite_blocked_tasks,
    _sync_resolved_prerequisite_blocked_tasks,
)
from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask


def _write_resolutions(plan_dir: Path) -> None:
    (plan_dir / "user_action_resolutions.json").write_text(
        json.dumps(
            {
                "ua-1": {
                    "action_id": "ua-1",
                    "state": "satisfied",
                    "reason": "operator resolved prerequisite",
                    "applies_to_task_ids": ["T1"],
                    "created_at": "2026-06-28T14:17:43Z",
                    "created_by": "operator",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _finalize_data() -> dict[str, object]:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": "blocked task",
                "status": "blocked",
                "executor_notes": "Blocked by explicit prerequisite `ua-1`.",
                "blocked_by_user_action_ids": ["ua-1"],
                "files_changed": ["stale.py"],
                "commands_run": ["pytest -q"],
                "evidence_files": ["artifact.txt"],
                "reviewer_verdict": "blocked",
            }
        ],
        "user_actions": [
            {
                "id": "ua-1",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
                "description": "Resolve prerequisite",
            }
        ],
    }


def test_prerequisite_blockers_consider_disk_resolutions_when_state_lags(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_resolutions(plan_dir)
    state = {"meta": {"user_action_resolutions": []}}

    evaluation = evaluate_prerequisite_blockers(
        _finalize_data(),
        state,
        [BlockedTask(task_id="T1", reason="blocked_by_prereq")],
        plan_dir=plan_dir,
    )

    assert len(evaluation.blockers) == 1
    blocker = evaluation.blockers[0]
    assert blocker.task_id == "T1"
    assert blocker.resolution_state == "satisfied"
    assert blocker.is_non_terminal is True
    assert blocker.is_terminal is False


def test_resolved_prerequisite_blocked_tasks_reset_to_pending(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_resolutions(plan_dir)
    finalize_data = _finalize_data()
    task = finalize_data["tasks"][0]
    task["recorded_invocation_id"] = "old-run"
    state = {"meta": {"user_action_resolutions": []}}

    reset_ids = _reset_resolved_prerequisite_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        state=state,
    )

    assert reset_ids == ["T1"]
    assert task["status"] == "pending"
    assert task["executor_notes"] == ""
    assert task["files_changed"] == []
    assert task["commands_run"] == []
    assert task["evidence_files"] == []
    assert task["reviewer_verdict"] == ""
    assert "recorded_invocation_id" not in task


def test_harness_generated_blocked_tasks_are_not_treated_as_prerequisites() -> None:
    evaluation = evaluate_prerequisite_blockers(
        {},
        {"meta": {}},
        [
            BlockedTask(
                task_id="T7",
                reason="blocked_by_prereq",
                notes=(
                    "BLOCKED — did not complete. No files modified.\n"
                    "[harness] status auto-downgraded: deviation contains budget exhausted"
                ),
            )
        ],
    )

    assert evaluation.blockers == ()


def test_sync_resolved_prerequisite_blocked_tasks_reloads_stale_finalize_snapshot(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_resolutions(plan_dir)
    stale_finalize = _finalize_data()
    persisted_finalize = _finalize_data()
    persisted_finalize["tasks"][0]["status"] = "pending"
    persisted_finalize["tasks"][0]["executor_notes"] = ""
    (plan_dir / "finalize.json").write_text(
        json.dumps(persisted_finalize, indent=2),
        encoding="utf-8",
    )
    state = {"meta": {"user_action_resolutions": []}}

    synced_finalize, reset_ids = _sync_resolved_prerequisite_blocked_tasks(
        stale_finalize,
        plan_dir=plan_dir,
        state=state,
        log_label="test",
    )

    assert reset_ids == []
    assert synced_finalize["tasks"][0]["status"] == "pending"
    assert synced_finalize["tasks"][0]["executor_notes"] == ""
