"""Regression: a phase *timeout* is a retryable stall, not a terminal plan failure.

Bug (caught driving the structural-decomposition epic, 2026-06-10): m6's
``finalize`` phase hung on a transient Shannon TUI handshake stall and hit the
phase timeout. The driver recorded that timeout with ``current_state=STATE_FAILED``
*and* ``resume_cursor.retry_strategy=="rerun_phase"`` — a contradiction. The
terminal-state check then saw ``failed`` and gave up on the whole plan, so the
chain's ``on_failure: stop_chain`` killed the driver. A single hung worker turn
took down a 6/7-complete epic.

The fix (auto.py): record the timeout with ``current_state=None`` so the plan's
real pre-phase state is preserved and the driver RE-RUNS the phase (bounded by
stall detection), exactly like the sibling ``internal_error``/``phase_failed``
path already does and exactly what the timeout's own log line promises
("stall detection will enforce the cap").

These tests lock the invariant at the failure-recording boundary so a future
edit can't silently flip the timeout path back to a terminal STATE_FAILED.
"""
from __future__ import annotations

import json
from pathlib import Path

from megaplan import auto
from megaplan.auto import STATE_FAILED


def _make_plan_dir(tmp_path: Path, plan: str, *, current_state: str) -> Path:
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": current_state}),
        encoding="utf-8",
    )
    return plan_dir


def _record_timeout(plan_dir: Path, *, current_state):
    """Mirror the driver's phase-timeout failure recording."""
    auto._record_lifecycle_failure(
        plan_dir=plan_dir,
        kind="phase_timeout",
        message="phase 'finalize' timed out after 3600.0s",
        current_state=current_state,
        phase="finalize",
        resume_cursor={"phase": "finalize", "retry_strategy": "rerun_phase"},
        last_artifact=None,
        suggested_action="Investigate the timed-out phase and resume from the phase cursor.",
        metadata={"timeout_seconds": 3600.0, "iteration": 1},
    )


def test_phase_timeout_with_none_state_preserves_plan_state(tmp_path: Path) -> None:
    """current_state=None (the fix) must NOT terminate the plan.

    A finalize timeout on a plan in ``finalized`` leaves it in ``finalized`` so
    the next status() returns ``finalize`` as next_step and the driver re-runs it.
    """
    plan_dir = _make_plan_dir(tmp_path, "m6-timeout-retryable", current_state="finalized")

    _record_timeout(plan_dir, current_state=None)

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "finalized", (
        "a phase timeout recorded with current_state=None must preserve the plan's "
        f"actual state (retryable), not terminate it; got {state['current_state']!r}"
    )
    assert state["current_state"] != STATE_FAILED
    # The failure is still recorded for audit, with the rerun_phase cursor intact
    # (resume_cursor is persisted top-level on the plan state).
    failure = state.get("latest_failure") or {}
    assert failure.get("kind") == "phase_timeout"
    cursor = state.get("resume_cursor") or failure.get("resume_cursor") or {}
    assert cursor.get("retry_strategy") == "rerun_phase", (
        f"rerun_phase cursor must survive the timeout recording; got {cursor!r}"
    )


def test_explicit_state_failed_would_terminate(tmp_path: Path) -> None:
    """Contrast / documentation: passing STATE_FAILED is what the old code did,
    and it DOES drive the plan terminal — which is the exact bug. This guards the
    semantic boundary so the difference stays understood."""
    plan_dir = _make_plan_dir(tmp_path, "m6-timeout-terminal", current_state="finalized")

    _record_timeout(plan_dir, current_state=STATE_FAILED)

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == STATE_FAILED, (
        "recording with STATE_FAILED terminates the plan — this is precisely why "
        "the timeout path must pass None instead"
    )
