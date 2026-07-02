from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan import auto


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
