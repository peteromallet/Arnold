from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._core.phase_runtime import current_runner_incarnation
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)


def test_drive_forwards_live_phase_model_to_phase_subprocess(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "finalized"}),
        encoding="utf-8",
    )
    captured_args: list[list[str]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        captured_args.append(list(args))
        return (0, "", "")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=1,
        poll_sleep=0,
        phase_model=["execute=omp:deepseek/deepseek-v4-pro"],
    )

    assert len(captured_args) == 1
    assert captured_args[0][0] == "execute"
    assert captured_args[0][-4:] == [
        "--plan",
        "demo",
        "--phase-model",
        "execute=omp:deepseek/deepseek-v4-pro",
    ]


def test_drive_clears_stale_latest_failure_before_phase_redispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "initialized",
                "config": {"with_prep": True},
                "latest_failure": {
                    "kind": "phase_failed",
                    "phase": "prep",
                    "message": "stale structural audit failure",
                },
                "resume_cursor": {
                    "phase": "prep",
                    "retry_strategy": "rerun_phase",
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "initialized",
            "next_step": "prep",
            "valid_next": ["prep"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        assert args == ["prep", "--plan", "demo"]
        return (0, "", "")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: None)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "cap"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["latest_failure"] is None
    assert "resume_cursor" not in state


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


def test_drive_clears_obsolete_invalid_transition_failure_on_terminal_quality_block(
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
                "latest_failure": {
                    "kind": "phase_failed",
                    "phase": "review",
                    "message": (
                        '{"success": false, "error": "invalid_transition", '
                        '"message": "Cannot run review while current state is blocked"}'
                    ),
                    "metadata": {
                        "stderr": '{"success": false, "error": "invalid_transition"}',
                    },
                },
                "resume_cursor": {"phase": "review", "retry_strategy": "rerun_phase"},
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": None,
            "valid_next": [],
            "progress": {},
            "blocker_recovery": {
                "has_terminal_blockers": True,
                "blockers": [{"blocker_kind": "quality"}],
            },
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("terminal blocked status must not dispatch a phase")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "blocked"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["latest_failure"] is None
    assert "resume_cursor" not in state


def test_drive_keeps_quality_failure_on_terminal_quality_block(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    quality_failure = {
        "kind": "quality_gate_blocked",
        "phase": "review",
        "message": "review found unresolved blockers",
    }
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "blocked",
                "latest_failure": quality_failure,
                "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": None,
            "valid_next": [],
            "progress": {},
            "blocker_recovery": {
                "has_terminal_blockers": True,
                "blockers": [{"blocker_kind": "quality"}],
            },
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("terminal blocked status must not dispatch a phase")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "blocked"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["latest_failure"] == quality_failure
    assert state["resume_cursor"] == {"phase": "review", "retry_strategy": "manual_review"}


def test_drive_ignores_legacy_resume_clarify_hint_and_uses_recovery_projection(
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

    run_calls = 0

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "override resume-clarify",
            "valid_next": ["override resume-clarify"],
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
        return (0, "", "")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "cap"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 1
    assert outcome.last_phase == "recover-blocked"
    assert run_calls == 1


def test_drive_breaks_repeated_control_invalid_transition(
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

    run_calls = 0
    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "override force-proceed",
            "valid_next": ["override force-proceed"],
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
                    "error": "invalid_transition",
                    "message": "recover-blocked rejected",
                }
            ),
        )

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=80, poll_sleep=0)

    assert outcome.status == "blocked"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 2
    assert outcome.last_phase == "recover-blocked"
    assert outcome.blocking_reasons == ["invalid_transition_loop"]
    assert run_calls == 2
    failure = captured_failures[-1]
    assert failure["kind"] == "invalid_transition_loop"
    assert failure["phase"] == "recover-blocked"
    assert failure["metadata"]["count"] == 2
    assert failure["metadata"]["max_attempts"] == 2


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
    assert "structured params" in notes[-1]["note"]
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


def test_drive_bounds_identical_structural_phase_failures(monkeypatch, tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "critiqued"}),
        encoding="utf-8",
    )
    detail = (
        "worker_structural_audit_failed: missing_required at "
        "/north_star_actions"
    )

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "critiqued",
            "next_step": "gate",
            "valid_next": ["gate"],
            "progress": {},
        },
    )

    def fail_gate(args, **kwargs):
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="gate",
                invocation_id="test",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return 1, detail, ""

    failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_run_planning_phase", fail_gate)
    monkeypatch.setattr(
        auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(kwargs)
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=10, poll_sleep=0)

    assert outcome.status == "blocked"
    assert outcome.iterations == 3
    terminal = failures[-1]
    assert terminal["kind"] == "deterministic_phase_failure"
    assert terminal["resume_cursor"]["retry_strategy"] == "repair_phase_contract"
    assert terminal["metadata"]["count"] == 3


def test_predispatch_validation_signature_ignores_volatile_evidence() -> None:
    def payload(evidence_hash: str, artifact_path: str) -> str:
        return json.dumps(
            {
                "success": False,
                "error": "validation_job_failed",
                "message": "validation job VJ2 exited 124; expected one of [0]",
                "details": {
                    "job_id": "VJ2",
                    "validation_job_kind": "post_execute_suite",
                    "exit_code": 124,
                    "expected_exit_codes": [0],
                    "evidence_hash": evidence_hash,
                    "artifact_path": artifact_path,
                },
            }
        )

    first = auto._predispatch_validation_failure(
        "",
        payload("sha256:first", "/tmp/validation_VJ2_run-1.json"),
    )
    second = auto._predispatch_validation_failure(
        "",
        payload("sha256:second", "/tmp/validation_VJ2_run-2.json"),
    )

    assert first is not None
    assert second is not None
    assert first["signature"] == second["signature"]
    assert first["occurrence_id"] == second["occurrence_id"]
    assert first["retryable_infrastructure"] is True
    assert first["worker_dispatched"] is False


def test_drive_bounds_predispatch_validation_infrastructure_without_model_escalation(
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
                "config": {
                    "tier_models": {
                        "execute": {
                            "1": "omp:zai/glm-5.2",
                            "2": "codex:gpt-5.6-sol:high",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    run_count = 0

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        },
    )

    def fail_validation(args, **kwargs):
        nonlocal run_count
        run_count += 1
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="execute",
                invocation_id=f"validation-{run_count}",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "validation_job_failed",
                    "message": "validation job VJ2 exited 124; expected one of [0]",
                    "details": {
                        "job_id": "VJ2",
                        "validation_job_kind": "post_execute_suite",
                        "exit_code": 124,
                        "expected_exit_codes": [0],
                        "evidence_hash": f"sha256:attempt-{run_count}",
                        "artifact_path": f"verification/validation_VJ2_{run_count}.json",
                    },
                }
            ),
        )

    failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_run_planning_phase", fail_validation)
    monkeypatch.setattr(
        auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(kwargs)
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=10,
        poll_sleep=0,
        escalate_after_fails=1,
    )

    assert outcome.status == "blocked"
    assert outcome.iterations == 2
    assert run_count == 2
    assert outcome.tier_escalations_used == 0
    # The retry is telemetry only; lifecycle/repair/notification admission is
    # performed once when the stable occurrence exhausts its bounded budget.
    assert len(failures) == 1
    terminal = failures[0]
    assert terminal["kind"] == "pre_dispatch_validation_failed"
    assert terminal["resume_cursor"]["retry_strategy"] == "repair_validation_infrastructure"
    assert terminal["metadata"]["count"] == 2
    assert terminal["metadata"]["worker_dispatched"] is False
    assert terminal["metadata"]["notification_occurrence_id"].startswith(
        "validation-"
    )


def test_drive_does_not_retry_predispatch_validation_assertion_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "finalized"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
        },
    )

    def fail_validation(args, **kwargs):
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="execute",
                invocation_id="validation-1",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "validation_job_failed",
                    "message": "validation job VJ2 exited 1; expected one of [0]",
                    "details": {
                        "job_id": "VJ2",
                        "validation_job_kind": "post_execute_suite",
                        "exit_code": 1,
                        "expected_exit_codes": [0],
                        "evidence_hash": "sha256:failure",
                    },
                }
            ),
        )

    failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_run_planning_phase", fail_validation)
    monkeypatch.setattr(
        auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(kwargs)
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=10,
        poll_sleep=0,
        escalate_after_fails=1,
    )

    assert outcome.status == "blocked"
    assert outcome.iterations == 1
    assert outcome.tier_escalations_used == 0
    assert len(failures) == 1
    assert failures[0]["resume_cursor"]["retry_strategy"] == "repair_validation_failure"


def test_drive_does_not_latch_distinct_critique_validation_failures(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "planned"}),
        encoding="utf-8",
    )
    messages = [
        "Critique output failed check validation: issue_hints, correctness",
        "Critique output failed check validation: issue_hints, correctness, scope",
        (
            "Critique output failed check validation: "
            "issue_hints, correctness, scope, conventions"
        ),
    ]
    call_count = 0

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "planned",
            "next_step": "critique",
            "valid_next": ["critique"],
            "progress": {},
        },
    )

    def fail_critique(args, **kwargs):
        nonlocal call_count
        message = messages[call_count]
        call_count += 1
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="critique",
                invocation_id=f"attempt-{call_count}",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "invalid_critique",
                    "message": message,
                    "details": {"raw_output": "parallel"},
                }
            ),
        )

    failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_run_planning_phase", fail_critique)
    monkeypatch.setattr(
        auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(kwargs)
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=3, poll_sleep=0)

    assert outcome.status == "cap"
    assert outcome.iterations == 3
    assert call_count == 3
    phase_failures = [
        failure for failure in failures if failure["kind"] == "phase_failed"
    ]
    assert len(phase_failures) == 3
    assert not any(
        failure["kind"] == "deterministic_phase_failure" for failure in failures
    )
    for failure, message in zip(phase_failures, messages, strict=True):
        assert message in str(failure["message"])
        assert "inspect critique_check_* artifacts" in str(failure["message"])
        assert '"raw_output": "parallel"' not in str(failure["message"])


def test_drive_still_latches_identical_critique_validation_failures(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "planned"}),
        encoding="utf-8",
    )
    message = "Critique output failed check validation: issue_hints, correctness"
    call_count = 0

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "planned",
            "next_step": "critique",
            "valid_next": ["critique"],
            "progress": {},
        },
    )

    def fail_critique(args, **kwargs):
        nonlocal call_count
        call_count += 1
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="critique",
                invocation_id=f"attempt-{call_count}",
                exit_kind=ExitKind.internal_error.value,
            ),
        )
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "invalid_critique",
                    "message": message,
                    "details": {"raw_output": "parallel"},
                }
            ),
        )

    failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_run_planning_phase", fail_critique)
    monkeypatch.setattr(
        auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(kwargs)
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=10, poll_sleep=0)

    assert outcome.status == "blocked"
    assert outcome.iterations == 3
    assert call_count == 3
    terminal = failures[-1]
    assert terminal["kind"] == "deterministic_phase_failure"
    assert terminal["metadata"]["count"] == 3
    assert message in str(terminal["message"])


def test_drive_phase_failure_preserves_native_exception_forensics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "prepped"}),
        encoding="utf-8",
    )
    try:
        raise UnicodeDecodeError("utf-8", b"agent output: \\xa3", 14, 15, "invalid start byte")
    except UnicodeDecodeError as error:
        diagnostic = auto._native_exception_diagnostic(error)

    def fake_status(plan: str, **kwargs):
        return {"state": "prepped", "next_step": "plan", "valid_next": ["plan"], "progress": {}}

    def fake_run_planning_phase(args, **kwargs):
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(phase="plan", invocation_id="test", exit_kind=ExitKind.internal_error.value),
        )
        return 1, "", auto._PhaseDiagnosticText("UnicodeDecodeError: invalid start byte", diagnostic)

    captured_failures: list[dict[str, object]] = []
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    phase_failure = next(item for item in captured_failures if item.get("kind") == "phase_failed")
    metadata = phase_failure["metadata"]
    assert metadata["stderr_raw"] == "UnicodeDecodeError: invalid start byte"
    assert metadata["exception_type"] == "UnicodeDecodeError"
    assert metadata["exception_traceback"]
    assert metadata["exception_callsite"]["function"] == "test_drive_phase_failure_preserves_native_exception_forensics"
    assert base64.b64decode(metadata["diagnostic_bytes_b64"]).decode("utf-8") == metadata["exception_traceback"]


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


def test_drive_blocks_when_observed_cursor_disagrees_with_forward_projection(
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
            "workflow_cursor": {
                "phase": "gate",
                "dispatch_phase": "gate",
                "next_dispatch_phases": ["revise"],
            },
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("cursor mismatch must stop before dispatch")

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
    assert outcome.iterations == 1
    assert outcome.blocking_reasons == ["workflow_cursor_mismatch"]
    assert run_calls == 0
    assert captured_failures
    failure = captured_failures[-1]
    assert failure["kind"] == "workflow_cursor_mismatch"
    assert failure["current_state"] == "blocked"
    assert failure["resume_cursor"] == {
        "phase": "gate",
        "retry_strategy": "repair_workflow_projection",
    }
    assert failure["metadata"]["observed_phase_source"] is None


def test_drive_reconciles_completed_execute_before_cursor_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A persisted finalized->executed gap must not become a cursor mismatch.

    This is the real recovery shape: status still projects ``execute`` from
    ``finalized`` while the last completed execute event projects ``review``.
    Artifact adoption is deliberately evidence-gated in production; this test
    isolates the ordering contract and proves that gate runs before cursor
    comparison can falsely terminal-block the plan.
    """

    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "finalized", "history": []}),
        encoding="utf-8",
    )
    reconciliations: list[Path | None] = []
    failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
            "progress": {},
            "last_step": {"step": "execute", "result": "success"},
            "workflow_cursor": {
                "phase": "execute",
                "dispatch_phase": "execute",
                "next_dispatch_phases": ["review"],
            },
        }

    def fake_reconcile(candidate: Path | None) -> bool:
        reconciliations.append(candidate)
        return True

    def fail_projection(*args, **kwargs):
        raise AssertionError("cursor projection must run only after reconciliation")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_recover_completed_execute_artifacts_after_failure", fake_reconcile)
    monkeypatch.setattr(auto, "_project_auto_dispatch", fail_projection)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: failures.append(dict(kwargs)))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert reconciliations == [plan_dir]
    assert outcome.status == "cap"
    assert all(failure["kind"] != "workflow_cursor_mismatch" for failure in failures)


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

    # Native workflow authority refuses the legacy status fixture because it
    # supplies no source-derived actionable target; it must fail rather than
    # manufacture a legacy dispatch.
    assert outcome.status == "failed"
    assert outcome.final_state == "executing"
    assert captured_failures
    failure = captured_failures[-1]
    assert failure["kind"] == "no_next_step"
    assert failure["resume_cursor"] == {
        "phase": "status",
        "retry_strategy": "repair_state",
    }
    assert failure["metadata"] == {
        "iteration": 1,
        "legacy_next_step": "execute",
        "legacy_valid_next": ["execute"],
        "valid_next": [],
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
                        "worker_pid": os.getpid(),
                        "runner_incarnation": {
                            **current_runner_incarnation(),
                            "worker_process_start_identity": "reused-process-start",
                        },
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
def test_drive_stall_preserves_original_blocked_cursor_not_recover_blocked(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A stall after repeated recover-blocked attempts must not wedge the cursor.

    Bounded sibling instance (r7 CL2): the stall path recorded
    ``resume_cursor={"phase": last_phase or next_step, ...}`` where last_phase
    was the recovery helper ``recover-blocked`` (no topology predecessor), so
    the plan wedged: recover-blocked rejected ``invalid_resume_cursor`` and
    resume tried to exec a nonexistent ``recover-blocked`` binary.  The stall
    path must preserve the original blocked-phase cursor exactly like the
    iteration-cap path via ``_failure_resume_cursor_for_step``.
    """
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    original_cursor = {
        "phase": "gate",
        "retry_strategy": "repair_workflow_projection",
    }
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "blocked",
                "latest_failure": {
                    "kind": "workflow_cursor_mismatch",
                    "phase": "gate",
                    "state": "blocked",
                },
                "resume_cursor": original_cursor,
                "history": [
                    {"step": "gate", "result": "success"},
                ],
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
        # Retryable recover-blocked failure: missing phase_result, not one of
        # the non-retryable codes, so the loop keeps iterating into the stall.
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "missing_phase_result",
                    "message": (
                        "recover-blocked requires phase_result.json with "
                        "current blocker details"
                    ),
                }
            ),
        )

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        stall_threshold=2,
        max_iterations=10,
        poll_sleep=0,
    )

    assert outcome.status == "stalled"
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    persisted_cursor = persisted.get("resume_cursor") or {}
    assert persisted_cursor.get("phase") == "gate", (
        f"stall must preserve original blocked-phase cursor, got {persisted_cursor!r}"
    )
    assert persisted_cursor.get("retry_strategy") == "manual_review"
    assert persisted.get("latest_failure", {}).get("kind") == "stalled"
    assert status_calls >= 2
