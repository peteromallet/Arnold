from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud.repair_escalation import (
    evaluate_checkpoint_escalation,
    stranded_replan_reason,
)


def _write_goal(
    marker_dir: Path,
    *,
    name: str = "goal-a.json",
    checkpoint: str = "checkpoint-a",
    worker_live: bool = False,
) -> Path:
    path = marker_dir / "repair-goals" / "demo" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "goal_id": "goal-a",
                "checkpoint_digest": checkpoint,
                "status": "active",
                "target": {
                    "session": "demo",
                    "plan_name": "m3",
                    "blocker_id": "blocker-a",
                },
                "last_terminal_failure": {
                    "outcome": "recovery_not_verified",
                    "goal_id": "goal-a",
                    "checkpoint_digest": checkpoint,
                    "escalation_required": True,
                    "owner_terminal": True,
                    "owner_run_id": "repair-run-2",
                    "last_evaluation": {
                        "control_action": "meta_repair",
                        "failed_fixer_evidence": {
                            "outcome": "replan_required",
                            "goal_id": "goal-a",
                            "checkpoint_digest": checkpoint,
                            "escalation_required": True,
                            "owner_terminal": True,
                            "owner_run_id": "repair-run-1",
                        },
                    },
                    "last_observation": {
                        "plan_name": "m3",
                        "plan_state": "blocked",
                        "active_worker": {
                            "fresh": worker_live,
                            "worker_pid_live": worker_live,
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_checkpoint_bound_replan_is_actionable_for_l2_and_visible_to_l3(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    path = _write_goal(marker_dir)

    evidence = evaluate_checkpoint_escalation(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    )

    assert evidence["actionable"] is True
    assert evidence["goal_path"] == str(path)
    assert evidence["checkpoint_digest"] == "checkpoint-a"
    assert stranded_replan_reason(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    ).startswith("stranded_checkpoint_replan:")


def test_checkpoint_bound_replan_fails_closed_for_live_worker(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    _write_goal(marker_dir, worker_live=True)

    evidence = evaluate_checkpoint_escalation(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    )

    assert evidence["actionable"] is False
    assert stranded_replan_reason(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    ) == ""


def test_checkpoint_bound_replan_fails_closed_for_ambiguous_goals(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    _write_goal(marker_dir)
    _write_goal(marker_dir, name="goal-b.json")

    evidence = evaluate_checkpoint_escalation(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    )

    assert evidence["actionable"] is False
    assert evidence["reason"] == "ambiguous checkpoint-bound L2 escalation"


def test_checkpoint_bound_replan_rejects_checkpoint_mismatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    path = _write_goal(marker_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["last_terminal_failure"]["last_evaluation"]["failed_fixer_evidence"][
        "checkpoint_digest"
    ] = "different"
    path.write_text(json.dumps(payload), encoding="utf-8")

    evidence = evaluate_checkpoint_escalation(
        marker_dir=marker_dir,
        session="demo",
        plan_name="m3",
        blocker_id="blocker-a",
    )

    assert evidence["actionable"] is False
