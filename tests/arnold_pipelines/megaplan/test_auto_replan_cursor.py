"""Regression: replan/recover-blocked overrides must not manufacture a stale
workflow cursor (astrid-first m4 recovery, occurrence 96fe5e598a73).

``override replan`` / ``override recover-blocked`` rewind the plan to a
pre-gate state (``planned`` / ``critiqued``) without appending a phase-history
record.  The auto-driver's last-step fallback then derives a workflow cursor
from the stale history tail (e.g. a prior ``gate`` success whose successors
are finalize/revise/tiebreaker_run/override/halt) and flags
``workflow_cursor_mismatch`` against the rewound state's control projection,
blocking the documented replan seam (planned -> critique -> gate).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan import auto

GATE_HISTORY_TS = "2026-08-18T09:53:57Z"
REPLAN_TS = "2026-08-18T10:31:52Z"


def _write_plan_state(plan_dir: Path, state: dict[str, Any]) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(state, sort_keys=True), encoding="utf-8"
    )


def _base_state(*, current_state: str) -> dict[str, Any]:
    return {
        "schema_version": 0,
        "name": "m4-test-plan",
        "current_state": current_state,
        "iteration": 1,
        "history": [
            {
                "step": "gate",
                "result": "success",
                "timestamp": GATE_HISTORY_TS,
                "agent": "codex",
                "output_file": "gate.json",
            }
        ],
        "meta": {"overrides": []},
        "config": {},
    }


def _base_status(*, state: str) -> dict[str, Any]:
    return {
        "state": state,
        "last_step": {
            "step": "gate",
            "result": "success",
            "timestamp": GATE_HISTORY_TS,
        },
    }


def _status_with_stale_gate_cursor(*, state: str) -> dict[str, Any]:
    """Status as built by the driver after a gate success: last_step AND the
    derived workflow_cursor (dispatch_phase gate, successors finalize/revise/
    tiebreaker_run/override/halt).  This is the REAL occurrence shape
    (astrid-first m4, 48d51bc6b31f): the stale status cursor must not survive a
    newer state-rewinding override even though the last_step fallback is
    suppressed."""
    status = _base_status(state=state)
    status["workflow_cursor"] = {
        "dispatch_phase": "gate",
        "next_dispatch_phases": [
            "finalize",
            "revise",
            "tiebreaker_run",
            "override",
            "halt",
        ],
    }
    return status


def test_replan_after_gate_success_drives_critique_without_cursor_mismatch(
    tmp_path: Path,
) -> None:
    """planned + history tail gate(success) + newer replan override -> critique."""
    state = _base_state(current_state="planned")
    state["meta"]["overrides"] = [
        {"action": "replan", "timestamp": REPLAN_TS, "reason": "topology revision"}
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_base_status(state="planned"),
    )
    assert projection.issue is None, projection.message
    assert projection.next_step == "critique", projection
    assert "critique" in projection.valid_next, projection


def test_recover_blocked_after_gate_success_drives_gate_without_cursor_mismatch(
    tmp_path: Path,
) -> None:
    """critiqued + history tail gate(success) + newer recover-blocked override -> gate."""
    state = _base_state(current_state="critiqued")
    state["meta"]["overrides"] = [
        {
            "action": "recover-blocked",
            "timestamp": REPLAN_TS,
            "reason": "recorded gate decision",
        }
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_base_status(state="critiqued"),
    )
    assert projection.issue is None, projection.message
    assert projection.next_step == "gate", projection
    assert "gate" in projection.valid_next, projection


def test_no_override_preserves_cursor_mismatch(tmp_path: Path) -> None:
    """No state-rewinding override: the stale gate cursor still mismatches and
    must be reported (do not silently widen the repair surface)."""
    state = _base_state(current_state="planned")
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_base_status(state="planned"),
    )
    assert projection.issue == "workflow_cursor_mismatch", projection
    assert projection.next_step is None, projection
    assert projection.valid_next == (), projection


def test_override_predating_last_step_does_not_suppress_mismatch(
    tmp_path: Path,
) -> None:
    """An override OLDER than the last history entry must not suppress a real
    cursor mismatch: only a newer rewind supersedes the stale cursor."""
    state = _base_state(current_state="planned")
    state["meta"]["overrides"] = [
        {"action": "replan", "timestamp": "2026-08-18T09:00:00Z", "reason": "old"}
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_base_status(state="planned"),
    )
    assert projection.issue == "workflow_cursor_mismatch", projection


def test_irrelevant_override_does_not_suppress_mismatch(tmp_path: Path) -> None:
    """Non-rewinding overrides (e.g. set-profile) are not rewind evidence."""
    state = _base_state(current_state="planned")
    state["meta"]["overrides"] = [
        {
            "action": "set-profile",
            "timestamp": REPLAN_TS,
            "from": "partnered-5",
            "to": "partnered-5",
        }
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_base_status(state="planned"),
    )
    assert projection.issue == "workflow_cursor_mismatch", projection


def test_replan_with_stale_status_cursor_drives_critique_without_mismatch(
    tmp_path: Path,
) -> None:
    """REAL occurrence shape: status carries the stale gate workflow_cursor
    (dispatch_phase gate) in addition to last_step.  A newer replan override
    supersedes BOTH: the projection must drive critique, not mismatch."""
    state = _base_state(current_state="planned")
    state["meta"]["overrides"] = [
        {"action": "replan", "timestamp": REPLAN_TS, "reason": "topology revision"}
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_status_with_stale_gate_cursor(state="planned"),
    )
    assert projection.issue is None, projection.message
    assert projection.next_step == "critique", projection
    assert "critique" in projection.valid_next, projection


def test_recover_blocked_with_stale_status_cursor_drives_gate_without_mismatch(
    tmp_path: Path,
) -> None:
    """Same stale-status-cursor shape after recover-blocked: critiqued -> gate."""
    state = _base_state(current_state="critiqued")
    state["meta"]["overrides"] = [
        {
            "action": "recover-blocked",
            "timestamp": REPLAN_TS,
            "reason": "recorded gate decision",
        }
    ]
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_status_with_stale_gate_cursor(state="critiqued"),
    )
    assert projection.issue is None, projection.message
    assert projection.next_step == "gate", projection
    assert "gate" in projection.valid_next, projection


def test_stale_status_cursor_without_rewind_override_preserves_mismatch(
    tmp_path: Path,
) -> None:
    """No rewind override: the stale status cursor must still produce the
    workflow_cursor_mismatch (fail-closed; do not widen the repair surface)."""
    state = _base_state(current_state="planned")
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_status_with_stale_gate_cursor(state="planned"),
    )
    assert projection.issue == "workflow_cursor_mismatch", projection
    assert projection.next_step is None, projection


TIEBREAKER_DECIDE_TS = "2026-08-19T23:03:10Z"


def _status_after_tiebreaker_decide(*, state: str) -> dict[str, Any]:
    """Status as built by the driver after a completed tiebreaker decide:
    last_step = tiebreaker_decide(success) and the pypeline decision-route
    cursor (pick -> finalize, replan -> critique-fanout, escalate -> override).
    This is the REAL occurrence shape (47671addc195): the decision-route cursor
    must not override the rewound main-loop control projection (critiqued ->
    gate) after the handler cleared last_gate."""
    status = _base_status(state=state)
    status["last_step"] = {
        "step": "tiebreaker_decide",
        "result": "success",
        "timestamp": TIEBREAKER_DECIDE_TS,
    }
    status["workflow_cursor"] = {
        "dispatch_phase": "tiebreaker_decide",
        "next_dispatch_phases": ["finalize", "revise", "override"],
    }
    return status


def test_tiebreaker_decide_rewound_to_critiqued_drives_gate_without_mismatch(
    tmp_path: Path,
) -> None:
    """critiqued + history tail tiebreaker_decide(success) + decision-route
    cursor -> the main-loop projection (gate) wins; no workflow_cursor_mismatch
    (occurrence 47671addc195, second layer)."""
    state = _base_state(current_state="critiqued")
    state["history"] = [
        {
            "step": "tiebreaker_decide",
            "result": "success",
            "timestamp": TIEBREAKER_DECIDE_TS,
        }
    ]
    state["last_gate"] = {}
    _write_plan_state(tmp_path, state)
    projection = auto._project_auto_dispatch(
        "m4-test-plan",
        plan_dir=tmp_path,
        status=_status_after_tiebreaker_decide(state="critiqued"),
    )
    assert projection.issue is None, projection.message
    assert projection.next_step == "gate", projection
    assert projection.valid_next == ("gate",), projection


def test_tiebreaker_decide_escalate_is_not_stale_cursor() -> None:
    """An escalated decision parks at awaiting_human_verify: the rewind-to-step-
    context treatment must NOT apply (the verify-human seam stays in control)."""
    state = _base_state(current_state="awaiting_human_verify")
    state["last_gate"] = {"recommendation": "TIEBREAKER", "passed": False}
    last_step = {
        "step": "tiebreaker_decide",
        "result": "success",
        "timestamp": TIEBREAKER_DECIDE_TS,
    }
    assert (
        auto._tiebreaker_rewound_to_step_context(state, last_step) is False
    )