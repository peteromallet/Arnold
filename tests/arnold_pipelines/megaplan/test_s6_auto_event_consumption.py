from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._core.io import plans_root
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.cli.status_view import handle_status
from arnold_pipelines.megaplan.cli.status_view import _observed_workflow_phase
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED
from tests.conftest import load_state


def test_handle_status_fences_legacy_next_step_hints_from_workflow_cursor(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    base = build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(base))
    args.project_dir = str(project_dir)
    args.idea = "fixture plan"
    args.name = "fixture-plan"
    args.robustness = "standard"

    response = handle_init(root, args)
    plan_dir = plans_root(root) / response["plan"]

    state = load_state(plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
    }
    state["latest_failure"] = {
        "kind": "blocked_recovery_not_resolved",
        "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    state["clarification"] = {
        "source": "prep",
        "intent_summary": "prep surfaced 1 blocking ambiguity",
        "questions": ["Question 1"],
    }
    write_plan_state(plan_dir, mode="replace", state=state)

    status = handle_status(
        root,
        argparse.Namespace(plan=response["plan"], pending_human=False),
    )

    assert status["status_route_authority"] == "workflow_source_only"
    assert status["next_step"] == "resume-clarify"
    assert status["legacy_route_hints"] == {
        "authority": "display_only_non_authoritative",
        "next_step": "resume-clarify",
        "valid_next": ["resume-clarify"],
    }
    assert status["workflow_cursor"]["phase"] == "execute"
    assert status["workflow_cursor"]["next_dispatch_phases"]
    assert status["workflow_cursor"]["phase"] != status["next_step"]


def test_blocked_execute_history_is_not_a_completed_workflow_cursor() -> None:
    """Partial/rework execute must remain on the finalized -> execute route."""

    blocked_execute = {"step": "execute", "result": "blocked"}
    assert (
        _observed_workflow_phase(
            {},
            active_step=None,
            last_step=blocked_execute,
        )
        is None
    )
    assert auto._observed_phase_context(
        {}, {"last_step": blocked_execute}
    ) == (None, None)

    # Review rework is a completed, non-successful transition and must keep
    # its source cursor so the canonical route can return to execute.
    review_rework = {"step": "review", "result": "needs_rework"}
    assert _observed_workflow_phase({}, active_step=None, last_step=review_rework) == "review"
    assert auto._observed_phase_context(
        {}, {"last_step": review_rework}
    ) == ("review", "last_step")


def test_drive_blocks_when_workflow_cursor_disagrees_with_forward_state_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "critiqued", "config": {}}),
        encoding="utf-8",
    )

    captured_failures: list[dict[str, object]] = []

    def fake_status(plan: str, **kwargs):
        assert plan == "demo"
        return {
            "state": "critiqued",
            "next_step": "gate",
            "valid_next": ["gate"],
            "progress": {},
            "workflow_cursor": {
                "phase": "gate",
                "dispatch_phase": "gate",
                "next_dispatch_phases": ["finalize", "revise", "override", "halt"],
            },
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("cursor mismatch must stop before dispatch")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=3, poll_sleep=0)

    assert outcome.status == "blocked"
    assert outcome.final_state == "blocked"
    assert outcome.blocking_reasons == ["workflow_cursor_mismatch"]
    assert "expects one of [finalize, revise, override, halt]" in outcome.reason
    failure = captured_failures[-1]
    assert failure["kind"] == "workflow_cursor_mismatch"
    assert failure["resume_cursor"] == {
        "phase": "gate",
        "retry_strategy": "repair_workflow_projection",
    }


def test_drive_stops_for_gate_escalation_instead_of_auto_force_proceed(
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
                "config": {},
                "last_gate": {
                    "recommendation": "ESCALATE",
                    "passed": False,
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
            "next_step": "override force-proceed",
            "valid_next": ["override force-proceed"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        raise AssertionError("gate escalation must stop for operator action")

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "_record_lifecycle_failure", lambda **kwargs: captured_failures.append(kwargs))
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=3, poll_sleep=0)

    assert outcome.status == "human_required"
    assert outcome.final_state == "blocked"
    assert "requires an operator decision" in outcome.reason
    failure = captured_failures[-1]
    assert failure["kind"] == "gate_escalated"
    assert failure["resume_cursor"]["retry_strategy"] == "human_decision"
