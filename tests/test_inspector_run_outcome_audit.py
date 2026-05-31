from __future__ import annotations

from pathlib import Path

from megaplan.cli.status_view import _projected_valid_next
from megaplan.planning.control_binding import planning_run_state_view
from megaplan.run_outcome import RunOutcome
from megaplan.types import (
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_GATED,
)


def _state(current_state: str, **extra: object) -> dict[str, object]:
    return {
        "name": "demo-plan",
        "current_state": current_state,
        "config": {"robustness": "standard", "mode": "code"},
        **extra,
    }


def test_planning_run_state_view_projects_neutral_outcome() -> None:
    assert planning_run_state_view(_state(STATE_GATED)).outcome is None
    assert (
        planning_run_state_view(
            _state(
                STATE_BLOCKED,
                latest_failure={"kind": "external_error"},
            )
        ).metadata["blocking_reason"]
        == "external_error"
    )
    assert (
        planning_run_state_view(
            _state(STATE_AWAITING_HUMAN, clarification={"source": "prep"})
        ).outcome
        == RunOutcome.AWAITING_HUMAN
    )


def test_status_view_projects_recovery_targets_for_human_and_blocked_states() -> None:
    gated_targets = _projected_valid_next(_state(STATE_GATED))
    assert "finalize" in gated_targets
    assert _projected_valid_next(
        _state(
            STATE_BLOCKED,
            resume_cursor={"phase": "finalize"},
        )
    ) == ["recover-blocked"]
    assert _projected_valid_next(
        _state(
            STATE_AWAITING_HUMAN,
            clarification={"source": "prep"},
        )
    ) == ["resume-clarify"]


def test_inspector_audit_leaves_cost_and_trace_outside_planning_projection_surface() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    cost_source = (repo_root / "megaplan" / "observability" / "cost.py").read_text(encoding="utf-8")
    trace_source = (repo_root / "megaplan" / "observability" / "trace.py").read_text(encoding="utf-8")
    for source in (cost_source, trace_source):
        assert "workflow_next(" not in source
        assert "read_valid_targets(" not in source
        assert "RunOutcome" not in source


def test_workflow_next_caller_audit_covers_doctor_and_migrated_inspectors() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    status_source = (repo_root / "megaplan" / "cli" / "status_view.py").read_text(encoding="utf-8")
    introspect_source = (repo_root / "megaplan" / "observability" / "introspect.py").read_text(encoding="utf-8")
    doctor_source = (repo_root / "megaplan" / "observability" / "doctor.py").read_text(encoding="utf-8")
    assert "read_valid_targets(" in status_source
    assert "read_valid_targets(" in introspect_source
    assert "workflow_next(" not in introspect_source
    assert "workflow_next(" in doctor_source
    assert "current_state\") == \"awaiting_human_verify\"" not in status_source
