from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from arnold.pipelines.megaplan._core.state import resolve_plan_dir
from arnold.pipelines.megaplan._core.workflow import workflow_next
from arnold.pipelines.megaplan.cli import _build_status_payload, handle_list
from arnold.pipelines.megaplan.planning.state import (
    AUTOMATION_TERMINAL_STATES,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_FAILED,
    STATE_PAUSED,
    TERMINAL_STATES,
)


def _state(name: str, current_state: str) -> dict:
    return {
        "name": name,
        "idea": "idea",
        "current_state": current_state,
        "iteration": 1,
        "created_at": "2026-05-05T00:00:00Z",
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
    }


def _write_plan(root: Path, name: str, current_state: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps(_state(name, current_state)), encoding="utf-8")
    return plan_dir


def test_lifecycle_state_sets_make_paused_automation_terminal_but_listable() -> None:
    assert {STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED} <= TERMINAL_STATES
    assert STATE_PAUSED not in TERMINAL_STATES
    assert {STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED, STATE_PAUSED} <= AUTOMATION_TERMINAL_STATES


def test_workflow_next_has_no_steps_for_lifecycle_stop_states() -> None:
    for state in (STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED, STATE_PAUSED):
        assert workflow_next(_state("plan", state)) == []


def test_status_payload_reports_lifecycle_stop_states_without_valid_next(tmp_path: Path) -> None:
    for state in (STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED, STATE_PAUSED):
        plan_dir = _write_plan(tmp_path, f"plan-{state}", state)
        payload = _build_status_payload(plan_dir, _state(f"plan-{state}", state))
        assert payload["state"] == state
        assert payload["next_step"] is None
        assert payload["valid_next"] == []
        assert f"state '{state}'" in payload["summary"]


def test_status_payload_exposes_recovery_for_recoverable_blocked_gate(tmp_path: Path) -> None:
    plan_dir = _write_plan(tmp_path, "recoverable-blocked", STATE_BLOCKED)
    state = _state("recoverable-blocked", STATE_BLOCKED)
    state["last_gate"] = {
        "recommendation": "PROCEED",
        "passed": False,
        "preflight_results": {
            "project_dir_exists": True,
            "project_dir_writable": True,
            "success_criteria_present": True,
            "claude_available": False,
            "codex_available": False,
        },
    }

    payload = _build_status_payload(plan_dir, state)

    assert payload["next_step"] == "override force-proceed"
    assert payload["valid_next"] == ["override force-proceed", "gate"]


def test_list_hides_terminal_lifecycle_states_but_keeps_paused_visible(tmp_path: Path) -> None:
    _write_plan(tmp_path, "planned", "planned")
    _write_plan(tmp_path, "paused", STATE_PAUSED)
    _write_plan(tmp_path, "failed", STATE_FAILED)
    _write_plan(tmp_path, "blocked", STATE_BLOCKED)
    _write_plan(tmp_path, "cancelled", STATE_CANCELLED)

    result = handle_list(tmp_path, Namespace(filter_status=None, no_tree=True, include_done=False, summary=True, all=False))

    listed = {row["name"] for row in result["plans"]}
    assert listed == {"planned", "paused"}
    assert any("terminal plans hidden" in hint for hint in result["hints"])
    assert result["state_summary"][STATE_FAILED] == 1
    assert result["state_summary"][STATE_PAUSED] == 1


def test_resolve_plan_dir_ignores_terminal_lifecycle_states_when_selecting_active(tmp_path: Path) -> None:
    _write_plan(tmp_path, "failed", STATE_FAILED)
    _write_plan(tmp_path, "blocked", STATE_BLOCKED)
    paused = _write_plan(tmp_path, "paused", STATE_PAUSED)

    assert resolve_plan_dir(tmp_path, None) == paused
