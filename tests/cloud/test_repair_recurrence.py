from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from subprocess import CompletedProcess

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
        "workspace": "",
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
        "",  # event_signature: empty when no events_path in the failure context
    )


def test_problem_signature_is_blank_for_mechanical_redrive_only_context() -> None:
    context = {
        "failure_classification": "timeout_or_hang",
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "recommended_action": "mechanical re-drive only",
        },
        "plan_latest_failure": {
            "plan_name": "demo-plan",
            "current_state": "initialized",
            "events_path": "/tmp/demo/events.ndjson",
        },
        "plan_runtime_state": {"current_state": "initialized"},
        "chain_state_summary": {
            "current_plan_name": "demo-plan",
            "last_state": "initialized",
        },
    }

    assert repair_recurrence.build_problem_signature(context) == {
        field: "" for field in repair_recurrence.PROBLEM_SIGNATURE_FIELDS
    }


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


def test_problem_signature_includes_event_signature_field(tmp_path: Path) -> None:
    events_path = tmp_path / "events.ndjson"
    events_path.write_text(
        json.dumps({"seq": 0, "ts_utc": "2026-07-05T00:00:00+00:00", "kind": "authority_divergence", "payload": {"reason": "head_mismatch"}}) + "\n",
        encoding="utf-8",
    )
    ctx = _failure_context()
    ctx["plan_latest_failure"]["events_path"] = str(events_path)
    signature = repair_recurrence.build_problem_signature(ctx)
    assert "event_signature" in signature
    assert signature["event_signature"] == "authority_divergence/head_mismatch"


def test_problem_signature_prefers_phase_result_over_noisy_event_signature(tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo-plan"
    plan_dir.mkdir()
    events_path = plan_dir / "events.ndjson"
    events_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "seq": index,
                    "ts_utc": f"2026-07-05T00:00:{index:02d}+00:00",
                    "kind": "llm_token_heartbeat",
                    "payload": {},
                }
            )
            for index in range(3)
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text("{}", encoding="utf-8")
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            {
                "phase": "execute",
                "exit_kind": "blocked_by_quality",
                "blocked_tasks": [],
                "deviations": [
                    {
                        "kind": "quality_gate",
                        "message": "Focused probe still reports AWF245_ROW_EVIDENCE_INSUFFICIENCY.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = _failure_context(phase="execute")
    ctx["workspace"] = str(tmp_path)
    ctx["plan_latest_failure"]["state_path"] = str(plan_dir / "state.json")
    ctx["plan_latest_failure"]["events_path"] = str(events_path)

    signature = repair_recurrence.build_problem_signature(ctx)

    assert signature["event_signature"] == (
        "phase_result/execute/blocked_by_quality/quality_gate:AWF245_ROW_EVIDENCE_INSUFFICIENCY"
    )


def test_problem_signature_ignores_superseded_phase_result_after_recover_blocked(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo-plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "executed",
                "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
                "meta": {
                    "overrides": [
                        {
                            "action": "recover-blocked",
                            "to_state": "executed",
                            "resume_cursor": {
                                "phase": "review",
                                "retry_strategy": "manual_review",
                            },
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            {
                "phase": "review",
                "exit_kind": "blocked_by_quality",
                "blocked_tasks": [],
                "deviations": [
                    {
                        "kind": "quality_gate",
                        "message": "Resolved import blocker still present in stale phase_result.json.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = _failure_context(
        phase="review",
        current_state="executed",
        gate_recommendation="PROCEED",
        blocked_task_id="",
    )
    ctx["workspace"] = str(tmp_path)
    ctx["plan_latest_failure"]["state_path"] = str(plan_dir / "state.json")

    signature = repair_recurrence.build_problem_signature(ctx)

    assert signature["event_signature"] == ""


def test_problem_signature_event_signature_empty_when_no_events() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    assert signature["event_signature"] == ""


def test_layer3_breaker_trips_on_consecutive_same_signature() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    attempts = [{"attempt_id": 1, "problem_signature": signature}]
    result = repair_recurrence.evaluate_recurrence(signature, attempts, {})
    assert result["deterministic_failure_breaker"] is True
    assert result["layer3"]["detected"] is True
    assert result["layer3"]["breaker_signature"] == result["problem_signature"]


def test_layer3_breaker_ignores_same_signature_before_advancement_epoch() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    attempts = [
        {
            "attempt_id": 1,
            "dispatched_at": "2026-06-30T00:00:00+00:00",
            "problem_signature": signature,
        }
    ]
    result = repair_recurrence.evaluate_recurrence(
        signature,
        attempts,
        {"last_advancement_at": "2026-06-30T00:10:00+00:00"},
    )
    assert result["deterministic_failure_breaker"] is False
    assert result["layer1"]["detected"] is False


def test_legacy_advancement_snapshot_promotes_updated_at_to_epoch() -> None:
    snapshot = repair_recurrence.build_advancement_snapshot(_failure_context(), run_kind="chain")
    legacy_previous = {
        "updated_at": "2026-06-30T00:10:00+00:00",
        "advancement_since_last_dispatch": True,
        "last_dispatch_snapshot": snapshot,
        "no_advance_dispatches": ["2026-06-30T00:10:00+00:00"],
        "no_advance_count": 1,
    }

    updated = repair_recurrence.update_session_repair_snapshot(
        legacy_previous,
        snapshot,
        dispatched_at="2026-06-30T00:20:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert updated["last_advancement_at"] == "2026-06-30T00:10:00+00:00"


def test_layer3_breaker_does_not_trip_when_signature_changed() -> None:
    prior_sig = repair_recurrence.build_problem_signature(_failure_context(blocked_task_id="task-a"))
    attempts = [{"attempt_id": 1, "problem_signature": prior_sig}]
    current_sig = repair_recurrence.build_problem_signature(_failure_context(blocked_task_id="task-b"))
    result = repair_recurrence.evaluate_recurrence(current_sig, attempts, {})
    assert result["deterministic_failure_breaker"] is False


def test_layer3_breaker_trips_on_consecutive_empty_pending_batches_across_tasks(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)

    def context_for(task_id: str, index: int) -> dict[str, object]:
        artifact = plan_dir / f"execute_batch_{index}_output.json"
        artifact.write_text(
            json.dumps(
                {
                    "files_changed": [],
                    "commands_run": [],
                    "task_updates": [
                        {
                            "task_id": task_id,
                            "status": "pending",
                            "executor_notes": "",
                            "files_changed": [],
                            "commands_run": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        ctx = _failure_context(blocked_task_id=task_id, current_state="finalized")
        ctx["workspace"] = str(tmp_path)
        ctx["execute_attempt_context"] = {
            "execution_batch": {
                "path": str(artifact),
                "blocked_or_deferred_tasks": [{"task_id": task_id}],
            },
            "execute_batch_output": {"path": str(artifact)},
            "plan_history": {"last_entries": [{"step": "execute", "result": "blocked"}]},
        }
        return ctx

    prior_one = context_for("T3", 1)
    prior_two = context_for("T5", 2)
    current = context_for("T8", 3)
    attempts = [
        {
            "attempt_id": 1,
            "problem_signature": repair_recurrence.build_problem_signature(prior_one),
            "failure_context": prior_one,
        },
        {
            "attempt_id": 2,
            "problem_signature": repair_recurrence.build_problem_signature(prior_two),
            "failure_context": prior_two,
        },
    ]
    current_snapshot = repair_recurrence.build_advancement_snapshot(current, run_kind="chain")

    result = repair_recurrence.evaluate_recurrence(
        repair_recurrence.build_problem_signature(current),
        attempts,
        {"current": current_snapshot, "min_dispatches": 3},
    )

    assert result["deterministic_failure_breaker"] is True
    assert result["layer3"]["consecutive_same_signature"] is False
    assert result["layer3"]["empty_batch_streak"] == {
        "detected": True,
        "count": 3,
        "min_dispatches": 3,
        "task_id_batches": [["T8"], ["T5"], ["T3"]],
    }


def test_layer3_breaker_does_not_trip_on_empty_signature() -> None:
    empty_sig = {field: "" for field in repair_recurrence.PROBLEM_SIGNATURE_FIELDS}
    attempts = [{"attempt_id": 1, "problem_signature": empty_sig}]
    result = repair_recurrence.evaluate_recurrence(empty_sig, attempts, {})
    assert result["deterministic_failure_breaker"] is False


def test_layer3_breaker_does_not_trip_when_no_prior_attempts() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    result = repair_recurrence.evaluate_recurrence(signature, [], {})
    assert result["deterministic_failure_breaker"] is False


def test_detected_rollup_unaffected_by_layer3_breaker() -> None:
    signature = repair_recurrence.build_problem_signature(_failure_context())
    attempts = [{"attempt_id": 1, "problem_signature": signature}]
    result = repair_recurrence.evaluate_recurrence(signature, attempts, {})
    # breaker trips but `detected` rolls up only layer1/layer2 (breaker is a
    # separate escalation channel, not a recurrence signal).
    assert result["deterministic_failure_breaker"] is True
    assert result["detected"] == (result["layer1"]["detected"] or result["layer2"]["detected"])


def test_live_merged_pr_does_not_reset_same_occurrence_recurrence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run(args, **kwargs):
        if args[:3] == ["gh", "pr", "view"]:
            return CompletedProcess(
                args,
                0,
                '{"state":"MERGED","mergedAt":"2026-06-30T00:15:00Z"}',
                "",
            )
        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return CompletedProcess(args, 1, "", "not a git worktree")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(repair_recurrence.subprocess, "run", fake_run)

    previous = repair_recurrence.build_advancement_snapshot(_failure_context(), run_kind="chain")
    current_context = _failure_context()
    current_context["workspace"] = str(tmp_path)
    current_context["chain_state_summary"] = {
        **current_context["chain_state_summary"],
        "pr_number": 123,
        "pr_state": "open",
    }
    current = repair_recurrence.build_advancement_snapshot(current_context, run_kind="chain")

    updated = repair_recurrence.update_session_repair_snapshot(
        {
            "last_dispatch_snapshot": previous,
            "no_advance_dispatches": [
                "2026-06-30T00:00:00+00:00",
                "2026-06-30T00:05:00+00:00",
            ],
        },
        current,
        dispatched_at="2026-06-30T00:10:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert current["external_checks"]["pr"]["merged"] is True
    assert updated["advancement_since_last_dispatch"] is False
    assert updated["layer2_recurrence"] is True
    assert updated["no_advance_count"] == 3


def test_phase_churn_without_milestone_progress_counts_as_no_advance() -> None:
    first_snapshot = repair_recurrence.build_advancement_snapshot(_failure_context(phase="execute"), run_kind="chain")
    second_snapshot = repair_recurrence.build_advancement_snapshot(_failure_context(phase="finalize"), run_kind="chain")
    third_snapshot = repair_recurrence.build_advancement_snapshot(_failure_context(phase="execute"), run_kind="chain")

    first = repair_recurrence.update_session_repair_snapshot(
        None,
        first_snapshot,
        dispatched_at="2026-06-30T00:00:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )
    second = repair_recurrence.update_session_repair_snapshot(
        first,
        second_snapshot,
        dispatched_at="2026-06-30T00:05:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )
    third = repair_recurrence.update_session_repair_snapshot(
        second,
        third_snapshot,
        dispatched_at="2026-06-30T00:10:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert second["advancement_since_last_dispatch"] is False
    assert third["layer2_recurrence"] is True
    assert third["no_advance_count"] == 3


def test_external_unavailable_falls_back_to_state_milestone_progress_with_log() -> None:
    logs: list[str] = []
    previous = repair_recurrence.build_advancement_snapshot(
        _failure_context(completed_count=2, current_milestone_index=7),
        run_kind="chain",
        logger=logs.append,
    )
    current = repair_recurrence.build_advancement_snapshot(
        _failure_context(completed_count=3, current_milestone_index=8),
        run_kind="chain",
        logger=logs.append,
    )

    updated = repair_recurrence.update_session_repair_snapshot(
        {"last_dispatch_snapshot": previous, "no_advance_dispatches": ["2026-06-30T00:00:00+00:00"]},
        current,
        dispatched_at="2026-06-30T00:05:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert current["external_checks"]["state_fallback"]["used"] is True
    assert any("falling back to state-file milestone counters" in item for item in logs)
    assert updated["advancement_since_last_dispatch"] is True
    assert updated["layer2_recurrence"] is False


def test_git_branch_advancement_does_not_reset_without_canonical_cursor_delta() -> None:
    previous = {
        **repair_recurrence.build_advancement_snapshot(_failure_context(), run_kind="chain"),
        "external_checks": {
            "pr": {"available": False, "reason": "no_pr_number"},
            "git": {"available": True, "head": "aaa", "base_ref": "origin/main", "ahead_count": 1},
            "state_fallback": {"used": False, "reason": ""},
        },
    }
    current = {
        **repair_recurrence.build_advancement_snapshot(_failure_context(), run_kind="chain"),
        "external_checks": {
            "pr": {"available": False, "reason": "no_pr_number"},
            "git": {"available": True, "head": "bbb", "base_ref": "origin/main", "ahead_count": 2},
            "state_fallback": {"used": False, "reason": ""},
        },
    }

    updated = repair_recurrence.update_session_repair_snapshot(
        {
            "last_dispatch_snapshot": previous,
            "no_advance_dispatches": [
                "2026-06-30T00:00:00+00:00",
                "2026-06-30T00:05:00+00:00",
            ],
        },
        current,
        dispatched_at="2026-06-30T00:10:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert updated["advancement_since_last_dispatch"] is False
    assert updated["layer2_recurrence"] is True


def test_completed_session_state_is_progress_when_external_checks_unavailable() -> None:
    previous = repair_recurrence.build_advancement_snapshot(_failure_context(current_state="blocked"), run_kind="chain")
    current = repair_recurrence.build_advancement_snapshot(_failure_context(current_state="done"), run_kind="chain")

    updated = repair_recurrence.update_session_repair_snapshot(
        {"last_dispatch_snapshot": previous, "no_advance_dispatches": ["2026-06-30T00:00:00+00:00"]},
        current,
        dispatched_at="2026-06-30T00:05:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert updated["advancement_since_last_dispatch"] is True
    assert updated["layer2_recurrence"] is False


def test_plan_event_growth_does_not_reset_without_canonical_cursor_delta(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps({"current_state": "finalized"}), encoding="utf-8")
    events_path = plan_dir / "events.ndjson"
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    events_path.write_text(json.dumps({"kind": "llm_call_start", "ts_utc": now}) + "\n", encoding="utf-8")

    previous_context = _failure_context()
    previous_context["workspace"] = str(workspace)
    previous_context["plan_latest_failure"]["state_path"] = str(state_path)
    previous_context["plan_events_path"] = str(events_path)
    previous = repair_recurrence.build_advancement_snapshot(previous_context, run_kind="chain")

    events_path.write_text(
        events_path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "kind": "llm_token_heartbeat",
                "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    current_context = _failure_context()
    current_context["workspace"] = str(workspace)
    current_context["plan_latest_failure"]["state_path"] = str(state_path)
    current_context["plan_events_path"] = str(events_path)
    current = repair_recurrence.build_advancement_snapshot(current_context, run_kind="chain")

    updated = repair_recurrence.update_session_repair_snapshot(
        {
            "last_dispatch_snapshot": previous,
            "no_advance_dispatches": [
                "2026-06-30T00:00:00+00:00",
                "2026-06-30T00:05:00+00:00",
            ],
        },
        current,
        dispatched_at="2026-06-30T00:10:00+00:00",
        min_dispatches=3,
        window_seconds=3600,
    )

    assert current["plan_activity"]["liveness"] == "progressing"
    assert updated["advancement_since_last_dispatch"] is False
    assert updated["layer2_recurrence"] is True
