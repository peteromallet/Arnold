from __future__ import annotations

from arnold_pipelines.megaplan.workflows.events import (
    resolve_workflow_phase,
    resolve_workflow_source_phase,
    workflow_cursor,
    workflow_dispatch_phase_names,
)


def test_workflow_dispatch_phase_names_are_source_derived() -> None:
    assert workflow_dispatch_phase_names() == {
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "tiebreaker_run",
        "tiebreaker_decide",
        "finalize",
        "execute",
        "review",
    }


def test_workflow_cursor_exposes_gate_routes_from_lowered_source() -> None:
    cursor = workflow_cursor("gate")

    assert cursor is not None
    assert cursor.phase == "gate"
    assert cursor.dispatch_phase == "gate"
    assert cursor.next_phases == (
        "finalize",
        "revise",
        "revise",
        "revise",
        "tiebreaker_researcher",
        "override",
        "halt",
        "halt",
        "override",
        "finalize",
        "finalize",
    )
    assert cursor.next_dispatch_phases == (
        "finalize",
        "revise",
        "tiebreaker_run",
        "override",
        "halt",
    )
    assert [event.route_signal for event in cursor.next_events] == [
        "proceed",
        "iterate",
        "retry_gate",
        "reprompt_downgrade",
        "tiebreaker",
        "escalate",
        "abort",
        "suspend",
        "blocked_preflight",
        "force_proceed",
        "else",
    ]


def test_workflow_cursor_resolves_tiebreaker_bridge_and_source_phase() -> None:
    cursor = workflow_cursor("tiebreaker-run")

    assert cursor is not None
    assert cursor.phase == "tiebreaker_researcher"
    assert cursor.dispatch_phase == "tiebreaker_run"
    assert cursor.next_phases == ("tiebreaker_challenger",)
    assert cursor.next_dispatch_phases == ("tiebreaker_run",)
    assert resolve_workflow_phase("megaplan:tiebreaker_researcher") == "tiebreaker_run"
    assert resolve_workflow_source_phase("megaplan:tiebreaker_researcher") == "tiebreaker_researcher"
    assert resolve_workflow_source_phase("tiebreaker-run") == "tiebreaker_researcher"


def test_workflow_cursor_resolves_tiebreaker_decision_routes() -> None:
    cursor = workflow_cursor("tiebreaker_decide")

    assert cursor is not None
    assert cursor.phase == "tiebreaker_decision"
    assert cursor.dispatch_phase == "tiebreaker_decide"
    assert cursor.next_dispatch_phases == ("finalize", "revise", "override")
    assert {event.route_signal for event in cursor.next_events} == {
        "proceed",
        "iterate",
        "escalate",
        "replan",
        "else",
    }
