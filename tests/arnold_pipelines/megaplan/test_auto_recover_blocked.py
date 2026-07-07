from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)


def test_read_state_data_reconciles_failed_no_next_after_finalize(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "failed",
                "iteration": 1,
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [{"step": "finalize", "result": "success"}],
                "meta": {},
                "last_gate": {},
                "latest_failure": {"kind": "no_next_step"},
                "resume_cursor": {"phase": "status", "retry_strategy": "repair_state"},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            PhaseResult(
                phase="finalize",
                invocation_id="test-finalize-success",
                exit_kind="success",
                artifacts_written=("finalize.json",),
            ).to_dict()
        ),
        encoding="utf-8",
    )

    state = auto._read_state_data(plan_dir)

    assert state is not None
    assert state["current_state"] == "finalized"
    assert state["latest_failure"] is None
    assert "resume_cursor" not in state


def test_git_text_normalizes_timeout_as_cli_error(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args") or args[0],
            timeout=kwargs["timeout"],
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(auto.subprocess, "run", fake_run)

    try:
        auto._git_text(tmp_path, ["git", "push"], timeout=3)
    except CliError as error:
        assert error.code == "git_publish_timeout"
        assert "git push timed out after 3 seconds" == error.message
        assert error.extra["stdout"] == "partial stdout"
        assert error.extra["stderr"] == "partial stderr"
    else:
        raise AssertionError("expected CliError")


def test_publish_done_plan_records_push_timeout_without_raising(monkeypatch, tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    commands: list[list[str]] = []

    def fake_git_text(root: Path, argv: list[str], *, timeout: int = 120) -> str:
        commands.append(list(argv))
        if argv == ["git", "status", "--porcelain"]:
            return " M changed.txt"
        if argv == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature"
        if argv == ["git", "rev-parse", "HEAD"]:
            return "abc1234567890"
        if argv[:2] == ["git", "switch"] or argv[:2] == ["git", "add"]:
            return ""
        if argv[:2] == ["git", "commit"]:
            return "committed"
        if argv[:3] == ["git", "push", "--no-verify"]:
            raise CliError("git_publish_timeout", "git push timed out after 180 seconds")
        raise AssertionError(f"unexpected git command: {argv}")

    class Completed:
        returncode = 1

    monkeypatch.setattr(auto, "_git_text", fake_git_text)
    monkeypatch.setattr(auto.subprocess, "run", lambda *args, **kwargs: Completed())

    lines: list[str] = []
    payload = auto._publish_done_plan(
        plan="demo",
        plan_dir=plan_dir,
        root=tmp_path,
        branch=None,
        writer=lines.append,
    )

    assert payload is not None
    assert payload["status"] == "publish_failed"
    assert payload["reason"] == "git_publish_timeout"
    assert payload["push_output"] == "git push timed out after 180 seconds"
    assert "reason=git_publish_timeout" in lines[-1]
    assert json.loads((plan_dir / "publish.json").read_text(encoding="utf-8")) == payload


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
        phase_model=["execute=hermes:deepseek:deepseek-v4-pro"],
    )

    assert len(captured_args) == 1
    assert captured_args[0][0] == "execute"
    assert captured_args[0][-4:] == [
        "--plan",
        "demo",
        "--phase-model",
        "execute=hermes:deepseek:deepseek-v4-pro",
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


def test_drive_blocked_resume_clarify_without_prep_clarification_fails_in_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "blocked"}),
        encoding="utf-8",
    )

    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "override resume-clarify",
            "valid_next": ["override resume-clarify"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        assert args == ["override", "resume-clarify", "--plan", "demo"]
        return (
            1,
            json.dumps(
                {
                    "success": False,
                    "error": "invalid_transition",
                    "message": (
                        "resume-clarify can only resume a prep-sourced "
                        "clarification halt; use verify-human for "
                        "criteria-verification awaiting_human states"
                    ),
                }
            ),
            "",
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
    assert outcome.last_phase == "resume-clarify"
    assert outcome.blocking_reasons == ["invalid_transition_loop"]
    assert "resume-clarify can only resume a prep-sourced clarification halt" in outcome.reason
    failure = captured_failures[-1]
    assert failure["kind"] == "invalid_transition_loop"
    assert failure["phase"] == "resume-clarify"
    assert failure["resume_cursor"] == {
        "phase": "resume-clarify",
        "retry_strategy": "repair_control_binding",
    }
    assert failure["metadata"]["required_state"] is None
    assert failure["metadata"]["actual_state"] == "blocked"


def test_drive_breaks_repeated_control_invalid_transition(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "critiqued"}),
        encoding="utf-8",
    )

    run_calls = 0
    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "critiqued",
            "next_step": "override force-proceed",
            "valid_next": ["override force-proceed"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        nonlocal run_calls
        run_calls += 1
        assert args == ["override", "force-proceed", "--plan", "demo"]
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "invalid_transition",
                    "message": "routed override rejected",
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
    assert outcome.last_phase == "force-proceed"
    assert outcome.blocking_reasons == ["invalid_transition_loop"]
    assert run_calls == 2
    failure = captured_failures[-1]
    assert failure["kind"] == "invalid_transition_loop"
    assert failure["phase"] == "force-proceed"
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


def test_drive_allows_blocked_prep_resume_clarify(
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
                "clarification": {
                    "source": "prep",
                    "questions": ["Is the prerequisite complete?"],
                },
            }
        ),
        encoding="utf-8",
    )

    status_calls = 0
    commands: list[list[str]] = []

    def fake_status(plan: str, **kwargs):
        nonlocal status_calls
        status_calls += 1
        assert plan == "demo"
        if status_calls == 1:
            return {
                "state": "blocked",
                "next_step": "override resume-clarify",
                "valid_next": ["override resume-clarify"],
                "progress": {},
            }
        return {
            "state": "prepped",
            "next_step": None,
            "valid_next": [],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        commands.append(list(args))
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = "prepped"
        state.pop("clarification", None)
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return 0, json.dumps({"success": True, "state": "prepped"}), ""

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=2, poll_sleep=0)

    assert outcome.status == "failed"
    assert outcome.final_state == "prepped"
    assert commands == [["override", "resume-clarify", "--plan", "demo"]]


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
