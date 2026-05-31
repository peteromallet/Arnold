from __future__ import annotations

from megaplan.blocker_recovery import (
    build_prerequisite_scopes,
    command_blocker_details,
    evaluate_blocker_recovery,
    quality_blocker_id,
)
from megaplan.orchestration.phase_result import BlockedTask, Deviation
from megaplan.quality_resolutions import build_quality_resolution_event
from megaplan.user_actions import action_resolution_status, build_resolution_event


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


def test_malformed_prerequisite_blocker_suggests_retry_not_unknown_action() -> None:
    evaluation = evaluate_blocker_recovery(
        {"tasks": [{"id": "T1"}], "user_actions": []},
        _state(),
        blocked_tasks=[BlockedTask(task_id="T1", reason="blocked_by_prereq")],
    )
    details = command_blocker_details(evaluation)

    assert evaluation.requires_rerun is True
    assert evaluation.has_terminal_blockers is False
    assert details[0]["blocker_id"] == "prereq:unknown:T1"
    assert details[0]["malformed_reason"] == "no blocking action scope"
    assert details[0]["resolution_behavior"] == "rerun_required"
    assert details[0]["suggested_commands"] == ["execute --retry-blocked-tasks"]
    assert "user-action resolve --action-id unknown" not in details[0]["suggested_commands"]


# ══════════════════════════════════════════════════════════════════════════════
# Characterization: memory resolution_applies_to_task semantics
# ══════════════════════════════════════════════════════════════════════════════


def test_memory_applies_to_task_missing_scope_applies_to_all() -> None:
    """Memory event: missing ``applies_to_tasks`` key → applies to all tasks."""
    from megaplan.user_actions import resolution_applies_to_task

    event = {"resolution": "satisfied", "action_id": "ua1"}  # no applies_to_tasks
    assert resolution_applies_to_task(event, "T1") is True
    assert resolution_applies_to_task(event, "T2") is True
    assert resolution_applies_to_task(event, "T99") is True


def test_memory_applies_to_task_explicit_empty_applies_to_none() -> None:
    """Memory event: explicit empty ``applies_to_tasks`` → no concrete task."""
    from megaplan.user_actions import resolution_applies_to_task

    event = {"resolution": "satisfied", "action_id": "ua1", "applies_to_tasks": []}
    assert resolution_applies_to_task(event, "T1") is False
    assert resolution_applies_to_task(event, "T2") is False


def test_memory_applies_to_task_non_empty_scoped() -> None:
    """Memory event: non-empty ``applies_to_tasks`` → only listed tasks."""
    from megaplan.user_actions import resolution_applies_to_task

    event = {"resolution": "satisfied", "action_id": "ua1", "applies_to_tasks": ["T1", "T3"]}
    assert resolution_applies_to_task(event, "T1") is True
    assert resolution_applies_to_task(event, "T3") is True
    assert resolution_applies_to_task(event, "T2") is False


def test_memory_applies_to_task_task_id_none_returns_true() -> None:
    """Memory event: ``task_id=None`` always returns True (aggregate check)."""
    from megaplan.user_actions import resolution_applies_to_task

    # Missing scope
    assert resolution_applies_to_task({"resolution": "satisfied"}, None) is True
    # Explicit empty list
    assert resolution_applies_to_task({"resolution": "satisfied", "applies_to_tasks": []}, None) is True
    # Non-empty list
    assert resolution_applies_to_task({"resolution": "satisfied", "applies_to_tasks": ["T1"]}, None) is True


def test_memory_applies_to_task_defensively_filters_empty_strings() -> None:
    """Memory event: empty strings in ``applies_to_tasks`` are filtered out."""
    from megaplan.user_actions import resolution_applies_to_task

    event = {"resolution": "satisfied", "action_id": "ua1", "applies_to_tasks": ["T1", "", "T2"]}
    # "" is filtered out by set comprehension, so only "T1" and "T2" count
    assert resolution_applies_to_task(event, "T1") is True
    assert resolution_applies_to_task(event, "T2") is True
    assert resolution_applies_to_task(event, "") is False  # empty string not a valid task


def test_memory_applies_to_task_none_event_returns_false() -> None:
    from megaplan.user_actions import resolution_applies_to_task

    assert resolution_applies_to_task(None, "T1") is False
    assert resolution_applies_to_task(None, None) is False


def test_action_resolution_status_accepts_memory_state_alias() -> None:
    action = {"id": "ua1"}
    effective = {
        "ua1": {
            "action_id": "ua1",
            "state": "satisfied",
            "applies_to_task_ids": ["T1"],
        }
    }

    status = action_resolution_status(action, effective, task_id="T1")

    assert status["resolution"] == "satisfied"
    assert status["behavior"] == "omit"
    assert status["is_resolved"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Characterization: classify_resolution_behavior (user-action classifier)
# ══════════════════════════════════════════════════════════════════════════════


def test_classify_resolution_behavior_all_supported_states() -> None:
    from megaplan.user_actions import classify_resolution_behavior

    assert classify_resolution_behavior("satisfied") == "omit"
    assert classify_resolution_behavior("accepted_blocked") == "fallback"
    assert classify_resolution_behavior("waived") == "fallback"
    assert classify_resolution_behavior("manual_required") == "hard_block"
    assert classify_resolution_behavior("rejected") == "hard_block"


def test_classify_resolution_behavior_none_and_unknown() -> None:
    from megaplan.user_actions import classify_resolution_behavior

    assert classify_resolution_behavior(None) == "hard_block"
    assert classify_resolution_behavior("bogus") == "hard_block"
    assert classify_resolution_behavior("") == "hard_block"


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


def test_scope_drift_quality_blocker_id_is_stable_across_file_lists() -> None:
    first = Deviation.from_string(
        "scope_drift_severity=high: unclaimed files ['a.py'] "
        "with 10 LOC outside the claimed set"
    )
    second = Deviation.from_string(
        "scope_drift_severity=high: unclaimed files ['a.py', 'b.py'] "
        "with 20 LOC outside the claimed set"
    )

    assert quality_blocker_id(first) == "quality:global:scope-drift-high"
    assert quality_blocker_id(second) == "quality:global:scope-drift-high"


def test_unclaimed_files_quality_blocker_id_is_stable_across_file_lists() -> None:
    first = Deviation.from_string(
        "Advisory audit finding: Git status shows changed files not claimed "
        "by any task: a.py"
    )
    second = Deviation.from_string(
        "Advisory audit finding: Git status shows changed files not claimed "
        "by any task: a.py, b.py"
    )

    assert quality_blocker_id(first) == "quality:global:unclaimed-files"
    assert quality_blocker_id(second) == "quality:global:unclaimed-files"
