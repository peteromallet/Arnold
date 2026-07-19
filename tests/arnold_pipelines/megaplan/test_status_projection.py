from __future__ import annotations

import json

import pytest

from arnold_pipelines.megaplan.cli.status_view import _build_status_payload
from arnold_pipelines.megaplan.observability.introspect import build_introspect_payload
from arnold_pipelines.megaplan.status_projection import plan_status_presentation


@pytest.mark.parametrize(
    ("plan_state", "active_step", "execution_state", "display_state"),
    [
        ("finalized", {"phase": "execute"}, "executing", "executing"),
        ("finalized", None, "ready", "finalized"),
        ("paused", {"phase": "execute"}, "paused", "paused"),
        ("failed", {"phase": "execute"}, "failed", "failed"),
        ("blocked", {"phase": "execute"}, "blocked", "blocked"),
        ("done", None, "completed", "done"),
    ],
)
def test_plan_status_presentation_preserves_lifecycle_precedence(
    plan_state, active_step, execution_state, display_state
):
    projection = plan_status_presentation(plan_state, active_step=active_step)

    assert projection == {
        "active_phase": active_step["phase"] if active_step else None,
        "execution_state": execution_state,
        "display_state": display_state,
    }


def test_plan_status_presentation_distinguishes_review_rework_from_acceptance():
    reworking = plan_status_presentation(
        "finalized",
        active_step={"phase": "execute"},
        review_verdict="needs_rework",
    )
    reviewing = plan_status_presentation(
        "executed",
        active_step={"phase": "review"},
        review_verdict="needs_rework",
    )
    awaiting_rework = plan_status_presentation(
        "finalized",
        review_verdict="needs_rework",
    )

    assert reworking["display_state"] == "reworking"
    assert reviewing["display_state"] == "reviewing"
    assert awaiting_rework["display_state"] == "needs_rework"


def test_accepted_and_idle_finalized_presentations_keep_terminal_precedence():
    assert plan_status_presentation(
        "done", review_verdict="needs_rework"
    )["display_state"] == "done"
    assert plan_status_presentation(
        "finalized", review_verdict="approved"
    )["display_state"] == "finalized"


def test_cli_status_distinguishes_live_execution_from_finalized_lifecycle(tmp_path):
    state = {
        "name": "live-plan",
        "current_state": "finalized",
        "iteration": 0,
        "config": {"mode": "code"},
        "sessions": {},
        "meta": {"notes": [], "total_cost_usd": 0.0},
        "history": [],
        "active_step": {"phase": "execute", "agent": "codex"},
    }

    payload = _build_status_payload(tmp_path, state)

    assert payload["state"] == "finalized"
    assert payload["active_phase"] == "execute"
    assert payload["execution_state"] == "executing"
    assert payload["display_state"] == "executing"
    assert "currently executing (lifecycle state 'finalized')" in payload["summary"]


def test_introspect_distinguishes_live_execution_from_finalized_lifecycle(tmp_path):
    plan_dir = tmp_path / ".megaplan" / "plans" / "live-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "live-plan",
                "current_state": "finalized",
                "active_step": {"phase": "execute"},
            }
        ),
        encoding="utf-8",
    )

    payload = build_introspect_payload(plan_dir)

    assert payload["plan_state"] == "finalized"
    assert payload["active_phase"]["phase"] == "execute"
    assert payload["execution_state"] == "executing"
    assert payload["display_state"] == "executing"
