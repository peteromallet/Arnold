from __future__ import annotations

from megaplan.blocker_recovery import (
    build_prerequisite_scopes,
    command_blocker_details,
    evaluate_blocker_recovery,
    quality_blocker_id,
)
from megaplan.orchestration.phase_result import BlockedTask, Deviation
from megaplan.quality_resolutions import build_quality_resolution_event
from megaplan.user_actions import build_resolution_event


def _state() -> dict[str, object]:
    return {"meta": {"user_action_resolutions": [], "quality_gate_resolutions": []}}


def test_build_prerequisite_scopes_derives_synthetic_before_execute_gate() -> None:
    finalize_data = {
        "tasks": [
            {"id": "gate", "depends_on": []},
            {"id": "T1", "depends_on": ["gate"]},
            {"id": "T2", "depends_on": ["gate"]},
        ],
        "user_actions": [{"id": "ua", "phase": "before_execute"}],
    }

    scope = build_prerequisite_scopes(finalize_data)["ua"]

    assert scope.synthetic_gate_task_id == "gate"
    assert scope.protected_task_ids == ("T1", "T2")
    assert scope.effective_task_ids == ("T1", "T2", "gate")


def test_prerequisite_blocker_resolution_is_task_scoped() -> None:
    finalize_data = {
        "tasks": [{"id": "T1"}, {"id": "T2"}],
        "user_actions": [
            {"id": "ua", "phase": "before_execute", "blocks_task_ids": ["T1", "T2"]}
        ],
    }
    state = _state()
    state["meta"]["user_action_resolutions"] = [
        build_resolution_event(
            action_id="ua",
            resolution="satisfied",
            tasks=["T1"],
            timestamp="2026-05-20T10:00:00Z",
        )
    ]

    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        blocked_tasks=[
            BlockedTask(task_id="T1", reason="blocked"),
            BlockedTask(task_id="T2", reason="blocked"),
        ],
    )
    details = {item["task_id"]: item for item in command_blocker_details(evaluation)}

    assert details["T1"]["resolution_behavior"] == "omit"
    assert details["T1"]["is_non_terminal"] is True
    assert details["T2"]["resolution_behavior"] == "hard_block"
    assert details["T2"]["is_terminal"] is True


def test_active_fixed_quality_blocker_requires_rerun() -> None:
    deviation = Deviation(kind="quality_gate", task_id="T1", message="lint failed")
    blocker_id = quality_blocker_id(deviation)
    state = _state()
    state["meta"]["quality_gate_resolutions"] = [
        build_quality_resolution_event(
            blocker_id=blocker_id,
            resolution="fixed",
            fallback_mode="rerun",
            timestamp="2026-05-20T10:00:00Z",
        )
    ]

    evaluation = evaluate_blocker_recovery({}, state, deviations=[deviation])
    detail = command_blocker_details(evaluation)[0]

    assert detail["blocker_id"] == blocker_id
    assert detail["resolution_behavior"] == "rerun_required"
    assert detail["requires_rerun"] is True
    assert detail["is_non_terminal"] is False
    assert detail["fallback_mode"] == "rerun"
