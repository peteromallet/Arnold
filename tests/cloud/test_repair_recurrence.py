from __future__ import annotations

from arnold_pipelines.megaplan.cloud import repair_recurrence


def _failure_context(
    *,
    failure_kind: str = "authority_divergence",
    current_state: str = "blocked",
    phase: str = "execute",
    plan_name: str = "demo-plan",
    milestone_label: str = "m7-final-gate",
    gate_recommendation: str = "ITERATE",
    blocked_task_id: str = "m7-13-full-suite-final-gate",
    message: str = "stalled at 'blocked' for 5 iterations",
    stderr: str = "stale pr_head target deadbeef",
    current_milestone_index: int = 7,
    completed_count: int = 2,
) -> dict[str, object]:
    return {
        "failure_classification": "blocked_state_or_recovery_error",
        "plan_latest_failure": {
            "kind": failure_kind,
            "current_state": current_state,
            "phase": phase,
            "plan_name": plan_name,
            "message": message,
            "metadata": {"stderr": stderr},
        },
        "plan_runtime_state": {
            "current_state": current_state,
            "retry_strategy": "manual_review",
            "manual_review_origin": "auto_stall",
        },
        "chain_state_summary": {
            "current_plan_name": plan_name,
            "current_milestone_label": milestone_label,
            "current_milestone_index": current_milestone_index,
            "completed_count": completed_count,
            "last_state": current_state,
        },
        "last_gate": {"recommendation": gate_recommendation},
        "execute_attempt_context": {
            "execution_batch": {
                "blocked_or_deferred_tasks": [{"task_id": blocked_task_id}],
            },
            "plan_history": {"last_entries": [{"step": phase, "result": "blocked"}]},
        },
    }


def test_problem_signature_is_stable_across_message_drift() -> None:
    first = _failure_context(
        message="stalled at 'blocked' for 5 iterations",
        stderr="stale pr_head target 1111111",
    )
    second = _failure_context(
        message="stalled at 'blocked' for 6 iterations",
        stderr="stale pr_head target 9999999",
    )

    assert repair_recurrence.build_problem_signature(first) == repair_recurrence.build_problem_signature(second)
    assert repair_recurrence.signature_tuple(repair_recurrence.build_problem_signature(first)) == (
        "authority_divergence",
        "blocked",
        "execute",
        "m7-final-gate",
        "ITERATE",
        "m7-13-full-suite-final-gate",
    )


def test_advancement_window_fires_only_when_repairs_repeat_without_progress() -> None:
    snapshot = repair_recurrence.build_advancement_snapshot(_failure_context(), run_kind="chain")
    first = repair_recurrence.update_session_repair_snapshot(
        None,
        snapshot,
        dispatched_at="2026-06-30T00:00:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )
    second = repair_recurrence.update_session_repair_snapshot(
        first,
        snapshot,
        dispatched_at="2026-06-30T00:10:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )
    third = repair_recurrence.update_session_repair_snapshot(
        second,
        snapshot,
        dispatched_at="2026-06-30T00:20:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert first["layer2_recurrence"] is False
    assert second["layer2_recurrence"] is False
    assert third["layer2_recurrence"] is True
    assert third["no_advance_count"] == 3

    advanced_snapshot = repair_recurrence.build_advancement_snapshot(
        _failure_context(current_state="reviewed", current_milestone_index=8, completed_count=3),
        run_kind="chain",
    )
    reset = repair_recurrence.update_session_repair_snapshot(
        second,
        advanced_snapshot,
        dispatched_at="2026-06-30T00:20:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert reset["advancement_since_last_dispatch"] is True
    assert reset["layer2_recurrence"] is False
    assert reset["no_advance_count"] == 1


def test_recurrence_verdict_handles_layer1_layer2_and_false_cases() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    attempts = [
        {
            "attempt_id": 1,
            "problem_signature": signature,
            "dev_model": "gpt-5.4",
            "dev_summary": "updated prompt path handling",
        }
    ]
    session_snapshot = {
        "no_advance_count": 2,
        "min_dispatches": 3,
        "window_seconds": 3600,
    }

    layer1 = repair_recurrence.evaluate_recurrence(signature, attempts, session_snapshot)
    assert layer1["detected"] is True
    assert layer1["layer1"]["detected"] is True
    assert layer1["layer2"]["detected"] is False
    assert layer1["attempt_number"] == 2

    layer2 = repair_recurrence.evaluate_recurrence(
        repair_recurrence.build_problem_signature(_failure_context(blocked_task_id="other-task")),
        [],
        {"no_advance_count": 3, "min_dispatches": 3, "window_seconds": 3600},
    )
    assert layer2["detected"] is True
    assert layer2["layer1"]["detected"] is False
    assert layer2["layer2"]["detected"] is True
    assert layer2["attempt_number"] == 3

    false_case = repair_recurrence.evaluate_recurrence(
        repair_recurrence.build_problem_signature(_failure_context(blocked_task_id="other-task")),
        attempts,
        {"no_advance_count": 1, "min_dispatches": 3, "window_seconds": 3600},
    )
    assert false_case["detected"] is False
    assert false_case["layer1"]["detected"] is False
    assert false_case["layer2"]["detected"] is False
