from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)


def test_drive_stops_on_non_retryable_recover_blocked_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "execute",
                    "retry_strategy": "manual_review",
                },
            }
        ),
        encoding="utf-8",
    )

    status_calls = 0
    run_calls = 0

    def fake_status(plan: str, **kwargs):
        nonlocal status_calls
        status_calls += 1
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "recover-blocked",
            "valid_next": ["recover-blocked"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        nonlocal run_calls
        run_calls += 1
        assert args == [
            "override",
            "recover-blocked",
            "--reason",
            "megaplan auto: recover blocked plan after blocker resolution",
            "--plan",
            "demo",
        ]
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "blocked_recovery_not_resolved",
                    "message": (
                        "recover-blocked requires every current blocker "
                        "to be explicitly resolved as non-terminal"
                    ),
                }
            ),
        )

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path)

    assert outcome.status == "blocked"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 1
    assert outcome.last_phase == "recover-blocked"
    assert outcome.blocking_reasons == ["blocked_recovery_not_resolved"]
    assert "explicitly resolved as non-terminal" in outcome.reason
    assert status_calls == 1
    assert run_calls == 1


def test_drive_auto_approve_resumes_prep_clarification(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "awaiting_human_verify",
                "config": {"auto_approve": True},
                "clarification": {
                    "source": "prep",
                    "questions": ["Which schema shape should structured params use?"],
                },
            }
        ),
        encoding="utf-8",
    )
    status_calls = 0

    def fake_status(plan: str, **kwargs):
        nonlocal status_calls
        status_calls += 1
        assert plan == "demo"
        if status_calls == 1:
            return {
                "state": "awaiting_human_verify",
                "next_step": "verify-human",
                "valid_next": ["verify-human", "resume-clarify"],
                "progress": {},
            }
        return {
            "state": "done",
            "next_step": None,
            "valid_next": [],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("prep clarification auto-resume should not dispatch a phase")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_publish_done_plan", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=3, poll_sleep=0)

    assert outcome.status == "done"
    assert status_calls == 2
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "prepped"
    assert "clarification" not in state
    notes = state["meta"]["notes"]
    assert notes[-1]["source"] == "auto_approve_prep_clarification"
    assert "structured params" in notes[-1]["text"]
    assert state["meta"]["overrides"][-1]["action"] == "auto-resume-clarify"


def test_drive_internal_error_log_prefers_latest_failure_over_warning_stderr(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    structural_failure = (
        "worker_structural_audit_failed: model output structural audit failed: "
        "Plan must include at least one step section"
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "prepped",
                "latest_failure": {
                    "kind": "phase_failed",
                    "phase": "plan",
                    "message": structural_failure,
                },
            }
        ),
        encoding="utf-8",
    )

    status_calls = 0

    def fake_status(plan: str, **kwargs):
        nonlocal status_calls
        status_calls += 1
        assert plan == "demo"
        return {
            "state": "prepped",
            "next_step": "plan",
            "valid_next": ["plan"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="plan",
                invocation_id="test-invocation",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            "",
            "M_WARN_ROUTING_DEGRADED plan -> codex:high (no premium credential)",
        )

    writes: list[str] = []
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=1,
        poll_sleep=0,
        writer=writes.append,
    )

    assert status_calls == 1
    assert outcome.status == "cap"
    joined = "".join(writes)
    assert structural_failure in joined
    assert "phase 'plan' exited with internal_error: M_WARN_ROUTING_DEGRADED" not in joined


def test_drive_internal_error_ignores_warning_only_stderr_when_stdout_has_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    structural_failure = (
        "worker_structural_audit_failed: model output structural audit failed: "
        "Plan must include at least one step section"
    )
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "prepped"}),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "prepped",
            "next_step": "plan",
            "valid_next": ["plan"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="plan",
                invocation_id="test-invocation",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            structural_failure,
            "M_WARN_ROUTING_DEGRADED plan -> codex:high (no premium credential)",
        )

    writes: list[str] = []
    captured_failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=1,
        poll_sleep=0,
        writer=writes.append,
    )

    phase_failure = next(item for item in captured_failures if item.get("kind") == "phase_failed")
    assert outcome.status == "cap"
    assert structural_failure in "".join(writes)
    assert phase_failure["message"] == structural_failure
    assert phase_failure["metadata"]["stderr"] == ""
    assert "M_WARN_ROUTING_DEGRADED" in phase_failure["metadata"]["stderr_raw"]


def test_drive_iteration_cap_preserves_original_resume_cursor_after_recover_blocked_loop(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "execute",
                    "retry_strategy": "manual_review",
                },
            }
        ),
        encoding="utf-8",
    )

    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "recover-blocked",
            "valid_next": ["recover-blocked"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        assert args == [
            "override",
            "recover-blocked",
            "--reason",
            "megaplan auto: recover blocked plan after blocker resolution",
            "--plan",
            "demo",
        ]
        return (1, "", "recover-blocked failed without structured payload")

    def fake_record_failure(**kwargs):
        captured_failures.append(dict(kwargs))

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", fake_record_failure)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=2)

    assert outcome.status == "cap"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 2
    assert outcome.last_phase == "recover-blocked"
    iteration_cap_failure = captured_failures[-1]
    assert iteration_cap_failure["kind"] == "iteration_cap"
    assert iteration_cap_failure["resume_cursor"] == {
        "phase": "execute",
        "retry_strategy": "manual_review",
    }


def test_drive_bails_on_repeated_finalize_failure_signature(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "critiqued",
                "history": [
                    {
                        "step": "finalize",
                        "result": "error",
                        "message": (
                            "Finalize could not resolve a scoped baseline test "
                            "command. Reason: test_blast_radius strategy is "
                            "'scoped' but selectors are missing or empty."
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run_calls = 0
    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "critiqued",
            "next_step": "revise",
            "valid_next": ["revise"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        nonlocal run_calls
        run_calls += 1
        assert args == ["revise", "--plan", "demo"]
        return (0, "", "")

    def fake_record_failure(**kwargs):
        captured_failures.append(dict(kwargs))

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", fake_record_failure)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=120,
        max_repeated_failure_signatures=3,
        stall_threshold=10,
    )

    assert outcome.status == "blocked"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 3
    assert outcome.blocking_reasons == ["repeated_failure_signature"]
    assert run_calls == 2
    assert captured_failures
    failure = captured_failures[-1]
    assert failure["kind"] == "repeated_failure_signature"
    assert failure["current_state"] == "blocked"
    assert failure["resume_cursor"] == {
        "phase": "finalize",
        "retry_strategy": "repair_repeated_failure",
    }
    assert failure["metadata"]["count"] == 3


def test_drive_stall_marks_manual_review_origin_auto_stall(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "executing",
                "resume_cursor": {
                    "phase": "execute",
                    "retry_strategy": "rerun_phase",
                },
            }
        ),
        encoding="utf-8",
    )

    captured_failures: list[dict[str, object]] = []
    statuses = [
        {
            "state": "executing",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        }
        for _ in range(6)
    ]
    status_iter = iter(statuses)

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return next(status_iter)

    def fake_run_planning_phase(args, **kwargs):
        assert args[0] == "execute"
        assert "--plan" in args
        assert args[args.index("--plan") + 1] == "demo"
        return (0, "", "")

    def fake_record_failure(**kwargs):
        captured_failures.append(dict(kwargs))

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", fake_record_failure)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, stall_threshold=5, max_iterations=10)

    assert outcome.status == "stalled"
    assert outcome.final_state == "executing"
    assert captured_failures
    failure = captured_failures[-1]
    assert failure["kind"] == "stalled"
    assert failure["resume_cursor"] == {
        "phase": "execute",
        "retry_strategy": "manual_review",
    }
    assert failure["metadata"] == {
        "stall_count": 5,
        "iteration": 6,
        "manual_review_origin": "auto_stall",
    }


def test_drive_execute_prereq_block_without_user_actions_surfaces_blocked(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "finalized",
                "active_step": {
                    "phase": "execute",
                    "run_id": "stale-run",
                    "worker_pid": 12345,
                    "started_at": "2026-07-03T10:44:49Z",
                    "last_activity_at": "2026-07-03T10:44:49Z",
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps({"user_actions": [], "tasks": []}),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        assert args[0] == "execute"
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="execute",
                invocation_id="test-invocation",
                exit_kind=ExitKind.blocked_by_prereq.value,
                blocked_tasks=(
                    BlockedTask(task_id="T11", reason="blocked_by_prereq", notes="M7 incomplete"),
                ),
            ),
        )
        return (0, "", "")

    captured_failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "blocked"
    assert outcome.final_state == "finalized"
    assert "T11" in outcome.reason
    assert captured_failures[-1]["kind"] == "execution_blocked"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "active_step" not in state


def test_drive_execute_prereq_block_with_user_action_stays_awaiting_human(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "finalized"}),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {"id": "UA1", "phase": "before_execute", "blocks_task_ids": ["T11"]}
                ],
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        assert args[0] == "execute"
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="execute",
                invocation_id="test-invocation",
                exit_kind=ExitKind.blocked_by_prereq.value,
                blocked_tasks=(
                    BlockedTask(task_id="T11", reason="blocked_by_prereq", notes="needs user approval"),
                ),
            ),
        )
        return (0, "", "")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "awaiting_human"
    assert outcome.final_state == "finalized"
    assert "awaiting user action" in outcome.reason
