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
