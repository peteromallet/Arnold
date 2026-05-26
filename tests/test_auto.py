"""Tests for megaplan.auto — the auto-driver loop.

Focus: the rework-cycle-aware stall detector added in v0.18.1. A plan in
``finalized`` state that's doing review→rework loops should not be flagged
as stalled just because ``state`` hasn't advanced — new ``review.json``
artifacts indicate real forward progress.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from megaplan import auto
from megaplan.auto import DriverOutcome, drive


def _make_plan_dir(tmp_path: Path, plan: str) -> Path:
    """Create a skeletal plan dir that `_resolve_plan_dir` can locate."""
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "finalized"}),
        encoding="utf-8",
    )
    return plan_dir


def test_format_phase_heartbeat_includes_plan_step_and_progress(tmp_path: Path) -> None:
    plan_dir = _make_plan_dir(tmp_path, "heartbeat-plan")
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "heartbeat-plan",
                "current_state": "planned",
                "active_step": {"step": "execute", "agent": "codex", "mode": "persistent"},
            }
        ),
        encoding="utf-8",
    )

    line = auto._format_phase_heartbeat(
        ["execute", "--plan", "heartbeat-plan"],
        elapsed_s=61.8,
        plan_dir=plan_dir,
        progress_changed=True,
    )

    assert "heartbeat" in line
    assert "elapsed=61s" in line
    assert "progress_mtime_changed=yes" in line
    assert "plan=heartbeat-plan" in line
    assert "active_step=execute" in line
    assert "worker=codex/persistent" in line


def _finalized_status(plan: str) -> dict:
    """Return a status snapshot that looks like 'review is next'."""
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "finalized",
        "iteration": 1,
        "summary": "Plan is in state 'finalized'.",
        "next_step": "review",
        "valid_next": ["review"],
    }


def _reviewed_status(plan: str) -> dict:
    """Return a status snapshot after review has approved the work."""
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "reviewed",
        "iteration": 1,
        "summary": "Plan is in state 'reviewed'.",
        "next_step": "feedback",
        "valid_next": ["feedback"],
    }


def _execute_status(plan: str, state: str = "finalized") -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": "execute",
        "valid_next": ["execute"],
    }


def _phase_status(plan: str, state: str = "planning", next_step: str = "prep") -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": next_step,
        "valid_next": [next_step],
    }


def _active_wait_status(plan: str, state: str = "planning", next_step: str = "plan") -> dict:
    response = _phase_status(plan, state=state, next_step=next_step)
    response["active_step"] = {
        "step": next_step,
        "agent": "codex",
        "mode": "persistent",
        "started_at": "2026-05-19T10:00:00Z",
        "age_seconds": 48,
        "stale": False,
        "health": "healthy",
        "recommended_action": "wait",
        "recommended_action_reason": "The active step is within its expected runtime window.",
        "idle_seconds": 48,
        "phase_progress_summary": "plan running (48s elapsed, typically completes within 15m).",
        "progress_pct": 5,
    }
    return response


def _done_status(plan: str) -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "done",
        "iteration": 1,
        "summary": "Plan is in state 'done'.",
        "next_step": None,
        "valid_next": [],
    }


def _terminal_status(plan: str, state: str) -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": None,
        "valid_next": [],
    }


def _write_history(plan_dir: Path, costs: list[object]) -> None:
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_dir.name,
                "current_state": "finalized",
                "history": [{"cost_usd": cost} for cost in costs],
            }
        ),
        encoding="utf-8",
    )


def _append_history_cost(plan_dir: Path, cost: float) -> None:
    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    history = state_data.setdefault("history", [])
    history.append({"cost_usd": cost})
    state_path.write_text(json.dumps(state_data), encoding="utf-8")


def test_auto_waits_for_healthy_active_step_instead_of_rerunning_phase(tmp_path: Path) -> None:
    plan = "active-plan"
    _make_plan_dir(tmp_path, plan)
    run_calls: list[list[str]] = []
    poll_count = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        # Return "wait" for the first 3 polls so the driver exercises the
        # healthy-wait branch, then transition to "done" to simulate the
        # plan finishing on its own (without consuming iteration budget).
        if poll_count["n"] <= 3:
            return _active_wait_status(plan_name, state="initialized", next_step="plan")
        return _done_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=2,
            stall_threshold=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # The plan should complete normally (the healthy waits didn't consume
    # the iteration budget, so the driver kept waiting until done).
    assert outcome.status == "done", f"expected done, got {outcome.status}: {outcome.reason}"
    assert run_calls == [], "driver should not have launched any phases"
    assert any("still running" in event.get("msg", "") for event in outcome.events), (
        "driver should have logged wait messages"
    )


def _orphaned_critique_status(plan: str) -> dict:
    """Status with an orphaned (dead-worker) active_step on critique.

    Mirrors what _build_active_step returns when the recorded worker PID
    is no longer alive — phase_runtime.build_phase_observability sets
    health=dead + recommended_action=resume_or_recover.
    """
    response = _phase_status(plan, state="planned", next_step="critique")
    response["active_step"] = {
        "step": "critique",
        "agent": "claude",
        "mode": "persistent",
        "worker_pid": 999999,
        "started_at": "2026-05-23T14:31:00Z",
        "age_seconds": 420,
        "stale": True,
        "health": "dead",
        "worker_pid_alive": False,
        "recommended_action": "resume_or_recover",
        "recommended_action_reason": (
            "The active step's recorded worker process (pid=999999) is no "
            "longer alive; the phase is not actually running. Re-run the "
            "step or recover via override."
        ),
    }
    return response


def test_auto_recovers_orphaned_active_step_after_silent_phase_death(
    tmp_path: Path,
) -> None:
    """Bug C regression: critique handler dies silently after writing an
    empty ``critique_output.json``. State.json keeps ``active_step`` set
    pointing at a now-dead worker PID. The next driver tick must clear
    the orphan, quarantine the half-written output, and dispatch the
    phase fresh — without spin-looping until the iteration cap.
    """
    plan = "wedged-critique-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    # The dead worker left an empty output file behind, exactly the
    # symptom reported on brief-scratchpad-emitter-20260523-1431.
    critique_output = plan_dir / "critique_output.json"
    critique_output.write_text("", encoding="utf-8")

    # State.json carries an orphaned active_step record. Persist it so
    # _clear_orphaned_active_step can read+rewrite the same file.
    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["current_state"] = "planned"
    state_data["active_step"] = {
        "step": "critique",
        "agent": "claude",
        "mode": "persistent",
        "worker_pid": 999999,
        "started_at": "2026-05-23T14:31:00Z",
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    poll_count = {"n": 0}
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        # First tick: orphaned active_step on critique. After the driver
        # dispatches critique once, simulate the phase completing and the
        # plan reaching done — proving the wedge unwound after a single
        # cleanup + dispatch rather than spinning to the iteration cap.
        if poll_count["n"] == 1:
            return _orphaned_critique_status(plan_name)
        return _done_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            stall_threshold=10,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Plan eventually reached `done` — the wedge unwound.
    assert outcome.status == "done", (
        f"expected done after orphan cleanup, got {outcome.status}: "
        f"{outcome.reason}"
    )
    # Exactly one critique dispatch happened — not 200 spin-loops.
    assert run_calls, "driver should have dispatched the orphaned phase"
    assert outcome.iterations <= 3, (
        f"orphan recovery should not consume the full iteration budget; "
        f"used {outcome.iterations}"
    )
    # The driver logged the orphan-clear path.
    assert any(
        "orphaned" in event.get("msg", "") for event in outcome.events
    ), (
        "driver should have logged the orphan cleanup; events: "
        f"{[e.get('msg') for e in outcome.events]}"
    )
    # state.json no longer carries the dead active_step.
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert reloaded.get("active_step") is None, (
        "orphaned active_step should have been cleared from state.json"
    )
    # The empty output file was quarantined (renamed) so the next dispatch
    # cannot be tricked into "recovering" malformed worker output.
    assert not critique_output.exists(), (
        "empty critique_output.json should have been moved out of the way"
    )
    assert (plan_dir / "critique_output.json.orphaned").exists(), (
        "quarantined output should land at .orphaned for forensics"
    )


def test_auto_orphan_recovery_leaves_non_empty_output_alone(
    tmp_path: Path,
) -> None:
    """A successfully-completed phase output that nonetheless coincides
    with an orphaned active_step (e.g. the parent died between worker
    success and ``clear_active_step``) must not be quarantined — the
    handler's own recover path can use it.
    """
    plan = "orphan-with-good-output"
    plan_dir = _make_plan_dir(tmp_path, plan)

    critique_output = plan_dir / "critique_output.json"
    good_payload = {"checks": [{"id": "c1", "status": "pass"}]}
    critique_output.write_text(json.dumps(good_payload), encoding="utf-8")

    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["current_state"] = "planned"
    state_data["active_step"] = {
        "step": "critique",
        "agent": "claude",
        "worker_pid": 999999,
        "started_at": "2026-05-23T14:31:00Z",
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    poll_count = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return _orphaned_critique_status(plan_name)
        return _done_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            stall_threshold=10,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # active_step cleared.
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert reloaded.get("active_step") is None
    # But the non-empty output file is preserved — handler recovery
    # paths depend on it.
    assert critique_output.exists(), (
        "non-empty critique output must not be quarantined"
    )
    assert json.loads(critique_output.read_text(encoding="utf-8")) == good_payload
    assert not (plan_dir / "critique_output.json.orphaned").exists()


def _orphaned_rerun_execute_status(plan: str) -> dict:
    """Status with a stale-but-alive active_step on execute.

    Mirrors what build_phase_observability returns when the worker PID is
    alive, the step is past the escalation threshold, and the plan lock is
    not held — health=stale + recommended_action=rerun_execute.
    """
    response = _execute_status(plan, state="planned")
    response["active_step"] = {
        "step": "execute",
        "agent": "shannon",
        "mode": "persistent",
        "worker_pid": os.getpid(),  # alive
        "started_at": "2026-05-23T14:00:00Z",
        "age_seconds": 420,
        "stale": True,
        "health": "stale",
        "worker_pid_alive": True,
        "recommended_action": "rerun_execute",
        "recommended_action_reason": (
            "The active execute step is stale and no process holds the plan lock."
        ),
    }
    return response


def _orphaned_rerun_same_step_status(plan: str) -> dict:
    """Status with a stale-but-alive active_step on plan.

    Mirrors what build_phase_observability returns for a non-execute stale
    step — health=stale + recommended_action=rerun_same_step.
    """
    response = _phase_status(plan, state="planning", next_step="plan")
    response["active_step"] = {
        "step": "plan",
        "agent": "shannon",
        "mode": "persistent",
        "worker_pid": os.getpid(),  # alive
        "started_at": "2026-05-23T14:00:00Z",
        "age_seconds": 420,
        "stale": True,
        "health": "stale",
        "worker_pid_alive": True,
        "recommended_action": "rerun_same_step",
        "recommended_action_reason": (
            "The active step is stale and no process holds the plan lock."
        ),
    }
    return response


def test_auto_clears_rerun_execute_before_redispatch(tmp_path: Path) -> None:
    """auto.drive must clear stale execute active_step (rerun_execute)
    before re-dispatching, just as it does for resume_or_recover."""
    plan = "stale-execute-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    execute_output = plan_dir / "execute_output.json"
    execute_output.write_text("", encoding="utf-8")

    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["current_state"] = "planned"
    state_data["active_step"] = {
        "step": "execute",
        "agent": "shannon",
        "mode": "persistent",
        "worker_pid": os.getpid(),
        "started_at": "2026-05-23T14:00:00Z",
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    poll_count = {"n": 0}
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return _orphaned_rerun_execute_status(plan_name)
        return _done_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            stall_threshold=10,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done", (
        f"expected done after stale execute cleanup, got {outcome.status}"
    )
    assert run_calls, "driver should have re-dispatched execute"
    assert outcome.iterations <= 3, (
        f"stale recovery should not consume the full iteration budget; "
        f"used {outcome.iterations}"
    )
    assert any(
        "orphaned" in event.get("msg", "") for event in outcome.events
    ), "driver should have logged the orphan cleanup"
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert reloaded.get("active_step") is None, (
        "stale active_step should have been cleared from state.json"
    )
    assert not execute_output.exists(), (
        "empty execute_output.json should have been quarantined"
    )


def test_auto_orphan_recovery_with_shannon_session_id_in_metadata(
    tmp_path: Path,
) -> None:
    """Shannon persists session_id into active_step metadata before launch.
    The orphan clearing (auto.drive → _clear_orphaned_active_step) must
    still work when session_id is present — it must not interfere with
    removal or quarantine."""
    plan = "shannon-session-orphan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    plan_output = plan_dir / "plan_output.json"
    plan_output.write_text("", encoding="utf-8")

    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["current_state"] = "planning"
    state_data["active_step"] = {
        "step": "plan",
        "agent": "shannon",
        "mode": "persistent",
        "worker_pid": 999999,
        "session_id": "shannon-dead-session-1234",
        "started_at": "2026-05-23T14:31:00Z",
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    def _orphaned_plan_with_session(plan_name: str) -> dict:
        response = _phase_status(plan_name, state="planning", next_step="plan")
        response["active_step"] = {
            "step": "plan",
            "agent": "shannon",
            "mode": "persistent",
            "worker_pid": 999999,
            "session_id": "shannon-dead-session-1234",
            "started_at": "2026-05-23T14:31:00Z",
            "age_seconds": 420,
            "stale": True,
            "health": "dead",
            "worker_pid_alive": False,
            "recommended_action": "resume_or_recover",
            "recommended_action_reason": (
                "The active step's recorded worker process (pid=999999) is no "
                "longer alive; the phase is not actually running. Re-run the "
                "step or recover via override."
            ),
        }
        return response

    poll_count = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return _orphaned_plan_with_session(plan_name)
        return _done_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            stall_threshold=10,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done", (
        f"expected done after orphan cleanup with session_id, got {outcome.status}"
    )
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert reloaded.get("active_step") is None, (
        "orphaned active_step with session_id should have been cleared"
    )
    assert not plan_output.exists(), (
        "empty plan_output.json should have been quarantined despite session_id metadata"
    )
    assert (plan_dir / "plan_output.json.orphaned").exists(), (
        "quarantined output should land at .orphaned when session_id is present"
    )


def test_stall_counter_resets_when_review_json_is_rewritten(tmp_path: Path) -> None:
    """Stall detection must be rework-aware.

    Simulates the production bug: state pinned at `finalized` while execute
    rework and review re-run. Each time review rewrites `review.json`, the
    stall counter must reset so the driver doesn't bail prematurely.
    """
    plan = "rework-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    review_path = plan_dir / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    base_mtime = review_path.stat().st_mtime

    iteration_counter = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        # Always return finalized — simulates state ping-pong that looks
        # stuck to the naive stall counter.
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        # Every phase invocation bumps review.json mtime by 1s, simulating
        # a completed review cycle. Over 6 iterations the driver should
        # observe ~5 rework cycles — well past the default stall_threshold
        # of 5, but NOT bail because each cycle resets the counter.
        iteration_counter["n"] += 1
        new_mtime = base_mtime + iteration_counter["n"]
        os.utime(review_path, (new_mtime, new_mtime))
        return 0, "{}", ""

    # Cap iterations low and allow plenty of rework cycles so we exercise
    # the reset path without tripping the rework cap.
    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,  # would normally trip after 3 same-state iters
            max_iterations=6,
            max_review_rework_cycles=10,  # high so we exercise reset, not cap
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # We should NOT have stalled — each rework cycle reset the stall counter.
    assert outcome.status == "cap", (
        f"expected cap (hit max_iterations) with rework resets, got "
        f"{outcome.status}: {outcome.reason}"
    )
    # And we should have observed multiple rework cycles.
    rework_events = [
        e for e in outcome.events if "rework cycle" in e.get("msg", "")
    ]
    assert len(rework_events) >= 3, (
        f"expected at least 3 rework cycles observed, got "
        f"{len(rework_events)}: {[e['msg'] for e in rework_events]}"
    )


def test_rework_cap_bails_after_exceeding_max_review_rework_cycles(
    tmp_path: Path,
) -> None:
    """The rework-cap guard must stop runaway needs_rework loops."""
    plan = "rework-cap-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    review_path = plan_dir / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    base_mtime = review_path.stat().st_mtime

    iteration_counter = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        iteration_counter["n"] += 1
        new_mtime = base_mtime + iteration_counter["n"]
        os.utime(review_path, (new_mtime, new_mtime))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=100,  # effectively disabled — force cap to trip
            max_iterations=20,
            max_review_rework_cycles=2,  # tight cap
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "review rework cap" in outcome.reason
    assert outcome.final_state == "finalized"


def test_rework_cap_does_not_bail_after_review_approves(
    tmp_path: Path,
) -> None:
    """A passing review after several reworks must proceed to feedback."""
    plan = "reviewed-after-reworks-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    review_path = plan_dir / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    base_mtime = review_path.stat().st_mtime

    status_calls = {"n": 0}
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        status_calls["n"] += 1
        if status_calls["n"] <= 4:
            return _finalized_status(plan_name)
        return _reviewed_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        run_calls.append(list(args))
        new_mtime = base_mtime + len(run_calls)
        os.utime(review_path, (new_mtime, new_mtime))
        if args and args[0] == "feedback":
            return 0, "{}", ""
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=100,
            max_iterations=10,
            max_review_rework_cycles=2,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status != "stalled"
    assert any(call and call[0] == "feedback" for call in run_calls)


def test_stall_still_trips_without_review_progress(tmp_path: Path) -> None:
    """Preserve existing stall detection for non-rework plans.

    When a plan has no ``review.json`` (e.g. light-robustness plans that
    skip review entirely) the marker stays ``None``, rework tracking is
    inert, and the driver should fall back to the plain stall counter.
    """
    plan = "no-review-plan"
    _make_plan_dir(tmp_path, plan)  # no review.json on disk

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,
            max_iterations=20,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "stalled at 'finalized'" in outcome.reason


def test_resolve_plan_dir_finds_plans_in_parent_tree(tmp_path: Path) -> None:
    """``_resolve_plan_dir`` must mirror `megaplan status`'s resolution."""
    plan = "nested-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    # Check cwd itself.
    assert auto._resolve_plan_dir(plan, tmp_path) == plan_dir

    # Check a child cwd (walks up).
    child = tmp_path / "nested" / "subdir"
    child.mkdir(parents=True)
    assert auto._resolve_plan_dir(plan, child) == plan_dir

    # Unknown plan returns None.
    assert auto._resolve_plan_dir("does-not-exist", tmp_path) is None


def test_get_review_marker_returns_none_when_review_missing(
    tmp_path: Path,
) -> None:
    plan = "no-review"
    plan_dir = _make_plan_dir(tmp_path, plan)
    assert auto._get_review_marker(plan_dir) is None
    assert auto._get_review_marker(None) is None

    (plan_dir / "review.json").write_text("{}", encoding="utf-8")
    marker = auto._get_review_marker(plan_dir)
    assert marker is not None
    assert isinstance(marker, float)


def test_run_megaplan_uses_module_launcher(tmp_path: Path) -> None:
    proc = auto.subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="{}",
        stderr="",
    )

    with patch.object(auto.subprocess, "run", return_value=proc) as mock_run:
        code, out, err = auto._run_megaplan(["status", "--plan", "demo"], cwd=tmp_path, timeout=5)

    assert (code, out, err) == (0, "{}", "")
    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "megaplan",
        "status",
        "--plan",
        "demo",
    ]


def test_phase_command_splits_multi_token_next_step() -> None:
    """`_phase_command` must split values like 'override add-note' into argv tokens.

    Regression: status returns multi-word next_step values for override
    sub-subcommands (`override add-note`, `override force-proceed`, etc.).
    Passing the whole string as a single argv element makes argparse reject
    it with `invalid choice: 'override add-note'`, the auto-driver then
    exits 2 every iteration and stalls.
    """
    assert auto._phase_command("override add-note") == ["override", "add-note"]
    assert auto._phase_command("override force-proceed") == ["override", "force-proceed"]
    assert auto._phase_command("override abort") == ["override", "abort"]
    # Single-token phases unchanged.
    assert auto._phase_command("review") == ["review"]
    assert auto._phase_command("step") == ["step"]
    # Execute keeps its auto-mode flags. --retry-blocked-tasks is always
    # passed because a fresh `megaplan auto` invocation is the user's signal
    # that any external prereq blocking a prior session has been resolved.
    assert auto._phase_command("execute") == [
        "execute",
        "--confirm-destructive",
        "--user-approved",
        "--retry-blocked-tasks",
    ]


def test_drive_dispatches_multi_token_next_step_correctly(tmp_path: Path) -> None:
    """End-to-end: a gate response advising 'override add-note' must dispatch
    as the subcommand `override add-note`, not as a single positional arg.
    """
    plan = "multi-token-plan"
    _make_plan_dir(tmp_path, plan)

    statuses = [
        {
            "success": True,
            "step": "status",
            "plan": plan,
            "state": "critiqued",
            "iteration": 1,
            "summary": "Plan is in state 'critiqued'.",
            "next_step": "override add-note",
            "valid_next": [
                "override add-note",
                "override force-proceed",
                "override abort",
                "step",
            ],
        },
        _done_status(plan),
    ]

    captured_args: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0) if len(statuses) > 1 else statuses[0]

    def fake_run(args, cwd=None, timeout=None):
        captured_args.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=10,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # The first phase invocation must split "override add-note" into separate
    # argv tokens followed by --plan and a synthesized --note; otherwise
    # argparse rejects the combined-string positional as an invalid command
    # choice, or the override CLI rejects the missing --note as invalid_args.
    assert captured_args, "expected at least one phase invocation"
    first = captured_args[0]
    assert first[:4] == ["override", "add-note", "--plan", plan], (
        f"expected next_step to be split into argv tokens, got {first!r}"
    )
    assert "--note" in first, f"expected synthesized --note, got {first!r}"
    note_value = first[first.index("--note") + 1]
    assert note_value, "synthesized --note must be non-empty"
    assert outcome.status == "done"


def _auto_args(plan: str, outcome_file: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        plan=plan,
        stall_threshold=1,
        max_iterations=1,
        max_review_rework_cycles=1,
        on_escalate="force-proceed",
        poll_sleep=0,
        phase_timeout=1,
        status_timeout=1,
        outcome_file=outcome_file,
        max_cost_usd=None,
        max_context_retries=2,
        max_blocked_retries=1,
        max_add_note_attempts=2,
    )


def test_run_auto_writes_outcome_file_matching_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = DriverOutcome(
        status="done",
        plan="demo",
        final_state="done",
        iterations=2,
        reason="complete",
        last_phase="review",
        events=[{"msg": "finished"}],
    )
    outcome_path = tmp_path / "nested" / "outcome.json"

    with patch.object(auto, "drive", return_value=outcome):
        rc = auto.run_auto(tmp_path, _auto_args("demo", str(outcome_path)))

    stdout = capsys.readouterr().out
    outcome_json = outcome.to_json()
    assert rc == 0
    assert outcome_path.read_text(encoding="utf-8") == outcome_json
    assert stdout == outcome_json + "\n"


def test_run_auto_without_outcome_file_preserves_stdout_only_behavior(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = DriverOutcome(
        status="stalled",
        plan="demo",
        final_state="finalized",
        iterations=3,
        reason="stalled",
    )

    with patch.object(auto, "drive", return_value=outcome):
        rc = auto.run_auto(tmp_path, _auto_args("demo"))

    stdout = capsys.readouterr().out
    assert rc == 2
    assert stdout == outcome.to_json() + "\n"


def test_run_auto_passes_progress_env_to_driver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan.orchestration.progress import ProgressContext

    captured: dict[str, dict[str, str] | None] = {}
    env = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id="epic-1",
        plan_id="demo",
        run_id="run-1",
    ).to_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    outcome = DriverOutcome(status="done", plan="demo", final_state="done", iterations=1)

    def fake_drive(*args, **kwargs):
        del args
        captured["progress_env"] = kwargs.get("progress_env")
        return outcome

    with patch.object(auto, "drive", side_effect=fake_drive):
        assert auto.run_auto(tmp_path, _auto_args("demo")) == 0

    assert captured["progress_env"] == env


def test_auto_driver_stops_on_lifecycle_terminal_states_without_phase_runs(tmp_path: Path) -> None:
    expected = {
        "failed": "failed",
        "blocked": "blocked",
        "cancelled": "cancelled",
        "paused": "paused",
    }
    for state, status in expected.items():
        plan = f"auto-{state}"
        _make_plan_dir(tmp_path, plan)
        calls: list[list[str]] = []

        with patch.object(auto, "_status", return_value=_terminal_status(plan, state)), \
             patch.object(auto, "_run_megaplan", side_effect=lambda *args, **kwargs: calls.append(list(args[0])) or (0, "", "")):
            outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

        assert outcome.status == status
        assert outcome.final_state == state
        assert calls == []


def test_auto_driver_recovers_blocked_gate_agent_preflight_via_valid_next(tmp_path: Path) -> None:
    plan = "recoverable-blocked-auto"
    _make_plan_dir(tmp_path, plan)
    statuses = [
        {
            "success": True,
            "step": "status",
            "plan": plan,
            "state": "blocked",
            "iteration": 1,
            "summary": "Plan is in state 'blocked'.",
            "next_step": "override force-proceed",
            "valid_next": ["override force-proceed", "gate"],
        },
        _done_status(plan),
    ]
    captured_args: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0) if len(statuses) > 1 else statuses[0]

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        captured_args.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,
            max_iterations=3,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert captured_args == [["override", "force-proceed", "--plan", plan]]


def test_run_auto_exit_codes_for_lifecycle_outcomes(tmp_path: Path, capsys) -> None:
    outcomes = {
        "failed": 1,
        "blocked": 5,
        "cancelled": 0,
        "paused": 0,
    }
    for status, expected_rc in outcomes.items():
        outcome = DriverOutcome(status=status, plan=f"demo-{status}", final_state=status, iterations=1)
        with patch.object(auto, "drive", return_value=outcome):
            assert auto.run_auto(tmp_path, _auto_args(f"demo-{status}")) == expected_rc
        capsys.readouterr()
def test_context_retry_success_retries_execute_with_fresh(tmp_path: Path) -> None:
    plan = "context-retry-success"
    _make_plan_dir(tmp_path, plan)
    statuses = [_execute_status(plan), _done_status(plan)]
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        if len(calls) == 1:
            return 1, "", fragment
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    assert outcome.context_retries_used == 1
    assert len(calls) == 2
    assert "--fresh" not in calls[0]
    assert "--fresh" in calls[1]


def test_context_retry_exhaustion_stops_after_max_retries(tmp_path: Path) -> None:
    plan = "context-retry-exhausted"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, fragment, ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_context_retries=2,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "context_retry_exhausted"
    assert outcome.context_retries_used == 2
    assert len(calls) == 3
    assert "--fresh" not in calls[0]
    assert "--fresh" in calls[1]
    assert "--fresh" in calls[2]


def test_context_retry_zero_disables_context_handling(tmp_path: Path) -> None:
    plan = "context-retry-disabled"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, "", fragment

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_context_retries=0,
            stall_threshold=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert outcome.status != "context_retry_exhausted"
    assert outcome.context_retries_used == 0
    assert len(calls) == 1
    assert all("--fresh" not in call for call in calls)


def test_generic_execute_failure_uses_stall_path_not_fresh_retry(tmp_path: Path) -> None:
    plan = "generic-execute-failure"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, "", "ordinary execute failure"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert outcome.context_retries_used == 0
    assert len(calls) == 1
    assert all("--fresh" not in call for call in calls)
    state_data = json.loads((tmp_path / ".megaplan" / "plans" / plan / "state.json").read_text(encoding="utf-8"))
    # Driver stall is a driver-lifecycle exit, not a plan failure — current_state
    # is preserved so a future driver can pick up where work left off.
    # Audit trail (latest_failure, resume_cursor) IS still recorded.
    assert state_data["current_state"] != "blocked"
    assert state_data["latest_failure"]["kind"] == "stalled"
    assert state_data["resume_cursor"]["phase"] == "execute"


def test_phase_failure_persists_failure_before_next_status(tmp_path: Path) -> None:
    plan = "phase-failure-persists"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _terminal_status(plan, "failed")]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        return 7, "", "prep exploded"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert outcome.status == "failed"
    # Phase exiting with internal_error is a driver-lifecycle observation, not a
    # plan-failure verdict — current_state is preserved. Audit trail IS recorded.
    assert state_data["current_state"] != "failed"
    assert state_data["latest_failure"]["kind"] == "phase_failed"
    assert state_data["latest_failure"]["phase"] == "prep"
    assert state_data["latest_failure"]["metadata"]["exit_code"] == 7
    assert state_data["resume_cursor"] == {"phase": "prep", "retry_strategy": "rerun_phase"}


def test_cli_rejects_negative_max_context_retries() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "megaplan",
            "auto",
            "--plan",
            "x",
            "--max-context-retries",
            "-1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "--max-context-retries" in proc.stderr
    assert "non-negative" in proc.stderr


def test_cost_cap_aborts_after_cumulative_cost_exceeds_cap(tmp_path: Path) -> None:
    plan = "cost-cap-cumulative"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan, state="planning", next_step="prep")

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 1.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=2.5,
            stall_threshold=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "cost_cap_exceeded"
    assert outcome.total_cost_usd == 3.0
    assert outcome.cost_cap_usd == 2.5
    assert len(calls) == 3


def test_cost_cap_equal_boundary_does_not_abort(tmp_path: Path) -> None:
    plan = "cost-cap-boundary"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 2.5)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=2.5,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status != "cost_cap_exceeded"
    assert outcome.status == "done"
    assert outcome.total_cost_usd == 2.5
    assert len(calls) == 1


def test_cost_cap_single_expensive_phase_finishes_before_abort(tmp_path: Path) -> None:
    plan = "cost-cap-single-expensive"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan, state="planning", next_step="prep")

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 10.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=5.0,
            stall_threshold=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "cost_cap_exceeded"
    assert outcome.total_cost_usd == 10.0
    assert outcome.cost_cap_usd == 5.0
    assert len(calls) == 1


def test_unset_cost_cap_does_not_terminate_on_high_cost(tmp_path: Path) -> None:
    plan = "cost-cap-unset"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 9999.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=None,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert outcome.status != "cost_cap_exceeded"
    assert outcome.total_cost_usd == 9999.0
    assert len(calls) == 1


def test_cli_rejects_negative_max_cost_usd() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "megaplan",
            "auto",
            "--plan",
            "x",
            "--max-cost-usd",
            "-1.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "--max-cost-usd" in proc.stderr
    assert "non-negative" in proc.stderr


def test_sum_history_cost_usd_handles_missing_corrupt_and_bad_entries(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    assert auto._sum_history_cost_usd(plan_dir) == 0.0

    (plan_dir / "state.json").write_text("{bad json", encoding="utf-8")
    assert auto._sum_history_cost_usd(plan_dir) == 0.0

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "history": [
                    {"cost_usd": "1.25"},
                    {"cost_usd": None},
                    {"cost_usd": "not-a-number"},
                    {"cost_usd": 2},
                    {"other": 99},
                    "not-a-dict",
                ],
                "meta": {"total_cost_usd": 9999},
            }
        ),
        encoding="utf-8",
    )
    assert auto._sum_history_cost_usd(plan_dir) == 3.25


def test_auto_help_surfaces_cost_and_context_retry_flags() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "auto", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "--max-context-retries" in proc.stdout
    assert "--max-cost-usd" in proc.stdout
    assert "--max-blocked-retries" in proc.stdout
    assert "context" in proc.stdout
    assert "cost" in proc.stdout


def _write_blocked_execute_history(plan_dir: Path, deviations: list[str] | None = None) -> None:
    """Stamp a history entry that mimics the executor finishing with result=blocked."""
    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data.setdefault("history", []).append({"step": "execute", "result": "blocked", "cost_usd": 0.16})
    state_path.write_text(json.dumps(state_data), encoding="utf-8")
    if deviations is not None:
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps({"deviations": deviations}),
            encoding="utf-8",
        )


def test_worker_blocked_after_max_retries_emits_terminal_status(tmp_path: Path) -> None:
    plan = "worker-blocked-cap"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from megaplan.orchestration.phase_result import Deviation
    from tests.conftest import fake_run_with_phase_result

    # Also write execution_batch for last_artifact assertion
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"deviations": ["done tasks missing both files_changed and commands_run: T1, T2"]}),
        encoding="utf-8",
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(
             auto,
             "_run_megaplan",
             side_effect=fake_run_with_phase_result(
                 plan_dir,
                 exit_kind="blocked_by_quality",
                 deviations=(
                     Deviation(
                         kind="quality_gate",
                         message="done tasks missing both files_changed and commands_run: T1, T2",
                     ),
                 ),
             ),
         ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "worker_blocked"
    assert outcome.blocked_retries_used == 1
    # Deviations from PhaseResult surface directly — no more prefix filtering.
    assert any("missing both files_changed" in r for r in outcome.blocking_reasons)
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"
    assert state_data["latest_failure"]["kind"] == "execution_blocked"
    assert state_data["latest_failure"]["last_artifact"] == "execution_batch_1.json"
    assert state_data["resume_cursor"]["phase"] == "execute"


def _write_blocked_task_update_batch(
    plan_dir: Path,
    *,
    task_id: str = "T10",
    notes: str = "DEV_LIVE_UPDATE_CHANNEL_ID missing from .env.",
) -> None:
    """Persist an execution_batch_1.json whose task_updates reports the named
    task as ``status: "blocked"`` with executor notes. Mirrors what the real
    execute handler writes when a task hits an unmet user prerequisite.
    """
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": task_id,
                        "status": "blocked",
                        "executor_notes": notes,
                        "files_changed": [],
                        "commands_run": ["env_check"],
                    }
                ],
                "deviations": [
                    f"task(s) reported status=blocked by the worker: {task_id}. "
                    "Resolve or replan the blocked task(s) before continuing.",
                ],
            }
        ),
        encoding="utf-8",
    )


def test_execute_blocked_task_routes_to_awaiting_human_without_retry(
    tmp_path: Path,
) -> None:
    """Regression: when the executor legitimately reports a task as
    status=blocked (e.g. an unmet user prerequisite), the auto driver must
    exit cleanly as awaiting_human, surface the executor notes, and NOT
    consume a blocked-retry attempt. Retrying execute won't unblock the
    user — only the user can.
    """
    plan = "execute-blocked-awaiting-human"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from megaplan.orchestration.phase_result import BlockedTask
    from tests.conftest import fake_run_with_phase_result

    _write_blocked_task_update_batch(plan_dir)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(
             auto,
             "_run_megaplan",
             side_effect=fake_run_with_phase_result(
                 plan_dir,
                 exit_kind="blocked_by_prereq",
                 blocked_tasks=(
                     BlockedTask(
                         task_id="T10",
                         reason="blocked",
                         notes="DEV_LIVE_UPDATE_CHANNEL_ID missing from .env.",
                     ),
                 ),
             ),
         ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            # max_blocked_retries=1 would normally permit one retry — the fix
            # must NOT consume one for awaiting-human blocked tasks.
            max_blocked_retries=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "awaiting_human", (
        f"expected awaiting_human, got {outcome.status!r} with reason={outcome.reason!r}"
    )
    assert outcome.blocked_retries_used == 0, (
        "awaiting-human exit must not burn a retry attempt; "
        f"got blocked_retries_used={outcome.blocked_retries_used}"
    )
    assert outcome.final_state == "finalized"
    # Reason must surface the task id and executor notes.
    assert "T10" in outcome.reason
    assert "DEV_LIVE_UPDATE_CHANNEL_ID" in outcome.reason
    assert "execute reported blocked tasks awaiting user action" in outcome.reason
    # blocking_reasons should carry the per-task notes for downstream
    # consumers (CI dashboards, oncall hand-off summaries).
    joined = " | ".join(outcome.blocking_reasons)
    assert "T10" in joined
    assert "DEV_LIVE_UPDATE_CHANNEL_ID" in joined
    # And the false-positive "tracking is incomplete" message must be absent.
    assert not any(
        "tracking is incomplete" in r for r in outcome.blocking_reasons
    )


def test_worker_blocked_does_not_loop_forever_with_zero_retries(tmp_path: Path) -> None:
    plan = "worker-blocked-zero"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from tests.conftest import fake_run_with_phase_result

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(
             auto,
             "_run_megaplan",
             side_effect=fake_run_with_phase_result(plan_dir, exit_kind="blocked_by_quality"),
         ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=0,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "worker_blocked"
    assert outcome.blocked_retries_used == 0


def test_worker_blocked_detection_skipped_when_execute_result_is_success(tmp_path: Path) -> None:
    """A clean execute (result=success) must NOT trigger the worker_blocked path."""
    plan = "execute-success-no-blocked"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from tests.conftest import fake_run_with_phase_result
    statuses = [_execute_status(plan), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(
             auto,
             "_run_megaplan",
             side_effect=fake_run_with_phase_result(plan_dir, exit_kind="success"),
         ):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    assert outcome.blocked_retries_used == 0


def test_stale_phase_result_from_previous_phase_does_not_mask_failure(tmp_path: Path) -> None:
    plan = "stale-phase-result"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(plan_dir, phase="critique", exit_kind="success")

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return {
            "success": True,
            "step": "status",
            "plan": plan,
            "state": "critiqued",
            "iteration": 1,
            "summary": "Plan is in state 'critiqued'.",
            "next_step": "gate",
            "valid_next": ["gate", "step"],
        }

    def fake_run(args, cwd=None, timeout=None):
        return 1, "", "gate crashed before phase_result emission"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=1,
            max_iterations=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert any(
        event["msg"].startswith("phase 'gate' exited with internal_error")
        and "gate crashed" in event["msg"]
        for event in outcome.events
    )
    assert outcome.status in {"stalled", "cap"}


def test_execute_callback_failure_reconciles_latest_batch_and_clears_active_step(tmp_path: Path) -> None:
    plan = "callback-reconcile"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "finalized",
                "active_step": {"step": "execute", "run_id": "stale"},
                "config": {"mode": "code"},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "T1", "status": "pending", "executor_notes": ""},
                ],
                "sense_checks": [
                    {"id": "SC1", "executor_note": ""},
                ],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "id": "T1",
                        "status": "completed",
                        "executor_notes": "Completed before callback failure.",
                        "files_changed": ["app.py"],
                        "commands_run": ["pytest"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"id": "SC1", "executor_note": "Confirmed before callback failure."}
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan_name)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None):
        return 0, "execute ok", ""

    def failing_callback(step: str, code: int, out: str, err: str) -> None:
        raise RuntimeError("nested publish failed")

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            poll_sleep=0,
            on_phase_complete=failing_callback,
            writer=lambda _m: None,
        )

    assert outcome.status == "failed"
    finalize_data = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    assert finalize_data["tasks"][0]["status"] == "done"
    assert finalize_data["tasks"][0]["files_changed"] == ["app.py"]
    assert finalize_data["sense_checks"][0]["executor_note"] == "Confirmed before callback failure."
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "active_step" not in state_data
    assert state_data["latest_failure"]["metadata"]["checkpoint_reconciliation"]["reconciled"] is True


def test_failed_execute_callback_resume_restores_executed_state(tmp_path: Path) -> None:
    plan = "callback-resume"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "failed",
                "history": [{"step": "execute", "result": "success"}],
                "latest_failure": {
                    "kind": "phase_callback_failed",
                    "phase": "execute",
                    "state": "failed",
                    "metadata": {
                        "checkpoint_reconciliation": {"reconciled": True},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution.json").write_text(json.dumps({"output": "ok"}), encoding="utf-8")

    def fake_status(plan_name: str, cwd=None, timeout=60):
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state = state_data["current_state"]
        if state == "executed":
            return _phase_status(plan_name, state="executed", next_step="review")
        return _terminal_status(plan_name, state=state)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        assert args[0] == "review"
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state_data["current_state"] = "done"
        (plan_dir / "state.json").write_text(json.dumps(state_data), encoding="utf-8")
        return 0, "review ok", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "done"
    assert any("recovered execute state" in event.get("msg", "") for event in outcome.events)


def test_failed_execute_callback_resume_restores_blocked_execute_to_finalized(tmp_path: Path) -> None:
    plan = "callback-blocked-resume"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "failed",
                "history": [{"step": "execute", "result": "blocked"}],
                "latest_failure": {
                    "kind": "phase_callback_failed",
                    "phase": "execute",
                    "state": "failed",
                    "metadata": {
                        "checkpoint_reconciliation": {"reconciled": True},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution.json").write_text(json.dumps({"output": "blocked"}), encoding="utf-8")

    def fake_status(plan_name: str, cwd=None, timeout=60):
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state = state_data["current_state"]
        if state == "finalized":
            return _execute_status(plan_name, state="finalized")
        return _terminal_status(plan_name, state=state)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        assert args[0] == "execute"
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state_data["current_state"] = "done"
        state_data.setdefault("history", []).append({"step": "execute", "result": "success"})
        (plan_dir / "state.json").write_text(json.dumps(state_data), encoding="utf-8")
        return 0, "execute ok", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    assert any("recovered execute state" in event.get("msg", "") for event in outcome.events)


def test_phase_complete_callback_skipped_after_nonzero_phase(tmp_path: Path) -> None:
    plan = "nonzero-no-callback"
    plan_dir = _make_plan_dir(tmp_path, plan)
    callback_calls: list[str] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan_name, state="planned", next_step="critique")

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        return 1, "", "critique failed"

    def callback(step: str, code: int, out: str, err: str) -> None:
        callback_calls.append(step)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=1,
            poll_sleep=0,
            on_phase_complete=callback,
            writer=lambda _m: None,
        )

    assert outcome.status == "cap"
    assert callback_calls == []
    assert any("phase 'critique'" in event.get("msg", "") for event in outcome.events)


def test_plan_liveness_mtime_uses_state_and_execution_batches(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    assert auto._plan_liveness_mtime(plan_dir) is None
    state_path = plan_dir / "state.json"
    state_path.write_text("{}", encoding="utf-8")
    first = auto._plan_liveness_mtime(plan_dir)
    assert first is not None

    batch_path = plan_dir / "execution_batch_1.json"
    batch_path.write_text("{}", encoding="utf-8")
    os.utime(batch_path, (state_path.stat().st_mtime + 10, state_path.stat().st_mtime + 10))
    batch_mtime = batch_path.stat().st_mtime
    assert auto._plan_liveness_mtime(plan_dir) == batch_mtime


def test_auto_strict_notes_blocks_force_proceed_after_escalate(tmp_path: Path) -> None:
    """When force-proceed is rejected by strict-notes, the auto driver should
    surface a `human_required` outcome rather than a generic `failed`."""
    plan = "strict-plan"
    _make_plan_dir(tmp_path, plan)

    def escalated_status(plan_name: str, cwd=None, timeout=60):
        return {
            "success": True,
            "step": "status",
            "plan": plan_name,
            "state": "critiqued",
            "iteration": 1,
            "summary": "Escalate awaiting override.",
            "next_step": None,
            "valid_next": ["override force-proceed", "override add-note", "override abort"],
        }

    def fake_run(args, cwd=None, timeout=None):
        # The first override-force-proceed call should fail with the strict
        # invariant error code in stderr.
        if args[:2] == ["override", "force-proceed"]:
            return 1, "", "CliError: escalate_requires_user_approval — user must approve"
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=escalated_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            on_escalate="force-proceed",
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "human_required", (
        f"expected human_required outcome, got {outcome.status}: {outcome.reason}"
    )
    assert "strict-notes" in outcome.reason





def _critiqued_status_with_overrides(plan: str) -> dict:
    """Status snapshot when the gate has escalated to override add-note.

    Mirrors the gate.py output for ESCALATE: next_step is "override add-note"
    and valid_next includes the full override fan-out plus "step".
    """
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "critiqued",
        "iteration": 1,
        "summary": "Plan is in state 'critiqued'.",
        "next_step": "override add-note",
        "valid_next": [
            "override add-note",
            "override force-proceed",
            "override abort",
            "step",
        ],
    }


def _write_gate_signals(plan_dir: Path, version: int, flag_ids: list[str]) -> None:
    flags = [
        {"id": fid, "concern": f"concern for {fid}", "severity": "significant", "status": "open"}
        for fid in flag_ids
    ]
    (plan_dir / f"gate_signals_v{version}.json").write_text(
        json.dumps({"unresolved_flags": flags, "signals": {}, "warnings": []}),
        encoding="utf-8",
    )


def test_synthesize_add_note_text_includes_unresolved_flag_ids(tmp_path: Path) -> None:
    """Note text must include flag ids when gate signals are present."""
    plan_dir = _make_plan_dir(tmp_path, "synth-plan")
    _write_gate_signals(plan_dir, 1, ["F-1", "F-2"])
    _write_gate_signals(plan_dir, 2, ["F-3", "F-4", "F-5"])
    note = auto._synthesize_add_note_text(plan_dir, iteration=12, attempt=1)
    # Must read the highest-versioned gate_signals file.
    assert "F-3" in note and "F-4" in note and "F-5" in note
    assert "F-1" not in note and "F-2" not in note
    assert "iter 12" in note
    assert "attempt 1" in note


def test_synthesize_add_note_text_falls_back_when_no_artifacts(tmp_path: Path) -> None:
    """Without artifacts the helper still produces a non-empty note."""
    plan_dir = _make_plan_dir(tmp_path, "synth-empty")
    note = auto._synthesize_add_note_text(plan_dir, iteration=3, attempt=2)
    assert note.strip()
    assert "unknown" in note
    assert "iter 3" in note


def test_build_override_add_note_command_includes_note_argument(tmp_path: Path) -> None:
    """The override add-note dispatch must always include --note <text>."""
    plan_dir = _make_plan_dir(tmp_path, "build-cmd-plan")
    _write_gate_signals(plan_dir, 1, ["FLAG-A"])
    cmd = auto._build_override_add_note_command(
        "build-cmd-plan", plan_dir, iteration=4, attempt=1
    )
    assert cmd[:4] == ["override", "add-note", "--plan", "build-cmd-plan"]
    assert "--note" in cmd
    note_idx = cmd.index("--note")
    assert cmd[note_idx + 1].strip(), "--note must be non-empty"
    assert "FLAG-A" in cmd[note_idx + 1]


def test_drive_supplies_note_arg_when_dispatching_override_add_note(tmp_path: Path) -> None:
    """End-to-end: a gate ESCALATE that surfaces 'override add-note' must
    dispatch the subprocess with a non-empty --note argument; otherwise the
    CLI rejects it as invalid_args and the auto-driver loops until stalled.
    """
    plan = "synth-note-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_gate_signals(plan_dir, 1, ["FLAG-X", "FLAG-Y"])

    statuses = [
        _critiqued_status_with_overrides(plan),
        _done_status(plan),
    ]
    captured: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0) if len(statuses) > 1 else statuses[0]

    def fake_run(args, cwd=None, timeout=None):
        captured.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=10,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert captured, "expected at least one phase invocation"
    first = captured[0]
    assert first[:2] == ["override", "add-note"]
    assert "--plan" in first and first[first.index("--plan") + 1] == plan
    assert "--note" in first
    note_value = first[first.index("--note") + 1]
    assert note_value, "synthesized --note must be non-empty"
    assert "FLAG-X" in note_value or "FLAG-Y" in note_value
    assert outcome.status == "done"


def test_drive_escalates_to_force_proceed_after_max_add_note_attempts(
    tmp_path: Path,
) -> None:
    """If add-note keeps failing, fall through to override force-proceed.

    Track B safety-net: after `max_add_note_attempts` consecutive
    add-note failures, the auto-driver must escalate to force-proceed
    rather than retrying the same broken (or merely insufficient)
    add-note dispatch forever. This is the existing escape valve when
    human intervention isn't available.
    """
    plan = "escalate-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_gate_signals(plan_dir, 1, ["FLAG-Z"])

    # Status always reports the same critiqued/override-add-note fork.
    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _critiqued_status_with_overrides(plan)

    captured: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=None):
        captured.append(list(args))
        # Simulate add-note always failing (e.g. the worker rejects the
        # synthesized note), but force-proceed succeeding.
        if args[:2] == ["override", "add-note"]:
            return 1, "", '{"success": false, "error": "rejected"}'
        if args[:2] == ["override", "force-proceed"]:
            return 0, "{}", ""
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=10,  # let escalation fire before stall trips
            max_iterations=10,
            max_add_note_attempts=2,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    add_note_calls = [c for c in captured if c[:2] == ["override", "add-note"]]
    fp_calls = [c for c in captured if c[:2] == ["override", "force-proceed"]]
    # The fake status never advances state, so the loop alternates: 2
    # add-note failures -> 1 force-proceed (counter reset) -> 2 add-note
    # failures -> 1 force-proceed -> ...  What matters is that the FIRST
    # force-proceed appears after exactly 2 add-note failures.
    assert len(add_note_calls) >= 2, (
        f"expected at least 2 add-note attempts before escalation, got {add_note_calls!r}"
    )
    assert fp_calls, "expected at least one force-proceed dispatch after add-note failures"
    assert captured[0][:2] == ["override", "add-note"]
    assert captured[1][:2] == ["override", "add-note"]
    assert captured[2][:2] == ["override", "force-proceed"], (
        f"expected force-proceed as 3rd dispatch after 2 add-note failures, "
        f"got {captured[2]!r}"
    )
    fp_first = fp_calls[0]
    assert "--reason" in fp_first
    reason = fp_first[fp_first.index("--reason") + 1]
    assert "add-note" in reason and "forcing proceed" in reason
    # Outcome can be `done`/`stalled`/etc. depending on later flow; what
    # matters is that the loop did not stay stuck on add-note.
    assert outcome.status in {"done", "stalled", "failed", "aborted", "cap"}


def test_drive_surfaces_external_error_distinctly(tmp_path: Path) -> None:
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import fake_run_with_phase_result

    plan = "external-error-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    phase_runner = fake_run_with_phase_result(
        plan_dir,
        exit_kind="external_error",
        code=1,
        stderr="provider failed",
        external_error=ExternalError(
            provider="deepseek",
            error_kind="rate_limit",
            message="429 Too Many Requests",
            status_code=429,
            retry_after_s=60.0,
        ),
    )
    statuses = [_execute_status(plan), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=phase_runner,
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _message: None,
        )

    assert any(
        event.get("msg", "").startswith("phase 'execute' external_error [deepseek]")
        for event in outcome.events
    )


def test_drive_auto_retries_stream_stall_once_for_non_execute_phase(tmp_path: Path) -> None:
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import make_fake_phase_result

    plan = "critique-stream-stall-recovers"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [_phase_status(plan, state="planned", next_step="critique"), _done_status(plan)]
    run_calls: list[list[str]] = []

    stream_stall = ExternalError(
        provider="deepseek",
        error_kind="stream_content_stall",
        message="Streaming response stalled without content or reasoning progress.",
        provider_error_code="timeout",
        error_layer="stream_content_stall",
        stall_timeout_s=60.0,
        elapsed_s=454.0,
        content_chunk_count=182,
        reasoning_chunk_count=0,
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        if len(run_calls) == 1:
            make_fake_phase_result(
                plan_dir,
                phase="critique",
                invocation_id="critique-attempt-1",
                exit_kind="external_error",
                external_error=stream_stall,
            )
            return 1, "", "Request timed out."
        make_fake_phase_result(
            plan_dir,
            phase="critique",
            invocation_id="critique-attempt-2",
            exit_kind="success",
        )
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=fake_run,
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _message: None,
        )

    assert outcome.status == "done"
    assert outcome.external_retries_used == 1
    assert len(run_calls) == 2
    assert run_calls[0] == ["critique", "--plan", plan]
    assert run_calls[1] == ["critique", "--plan", plan, "--fresh"]
    assert any(event.get("provider_error_code") == "timeout" for event in outcome.events)


def test_drive_blocks_after_retryable_external_error_fails_twice(tmp_path: Path) -> None:
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import make_fake_phase_result

    plan = "critique-stream-stall-twice"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [
        _phase_status(plan, state="planned", next_step="critique"),
        _terminal_status(plan, "blocked"),
    ]
    run_calls: list[list[str]] = []
    stream_stall = ExternalError(
        provider="deepseek",
        error_kind="stream_content_stall",
        message="Request timed out.",
        provider_error_code="timeout",
        error_layer="stream_content_stall",
        content_chunk_count=182,
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        make_fake_phase_result(
            plan_dir,
            phase="critique",
            invocation_id=f"critique-attempt-{len(run_calls)}",
            exit_kind="external_error",
            external_error=stream_stall,
        )
        return 1, "", "Request timed out."

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=fake_run,
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _message: None,
        )

    assert outcome.status == "blocked"
    assert outcome.external_retries_used == 1
    assert len(run_calls) == 2
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    latest_failure = state_data["latest_failure"]
    assert latest_failure["kind"] == "external_error"
    assert state_data["resume_cursor"]["phase"] == "critique"
    assert latest_failure["metadata"]["error_layer"] == "stream_content_stall"
    assert latest_failure["metadata"]["content_chunk_count"] == 182
    assert latest_failure["metadata"]["external_retries_used"] == 1
    assert latest_failure["metadata"]["suggested_recovery_commands"] == [
        f"python -m megaplan resume --plan {plan}"
    ]


def test_drive_does_not_auto_retry_permanent_external_errors(tmp_path: Path) -> None:
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import make_fake_phase_result

    plan = "critique-auth-failure"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [
        _phase_status(plan, state="planned", next_step="critique"),
        _terminal_status(plan, "blocked"),
    ]
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        make_fake_phase_result(
            plan_dir,
            phase="critique",
            exit_kind="external_error",
            external_error=ExternalError(
                provider="deepseek",
                error_kind="auth",
                message="401 invalid api key",
                status_code=401,
            ),
        )
        return 1, "", "401 invalid api key"

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=fake_run,
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _message: None,
        )

    assert outcome.status == "blocked"
    assert outcome.external_retries_used == 0
    assert run_calls == [["critique", "--plan", plan]]


def test_drive_does_not_auto_retry_execute_external_stream_stall(tmp_path: Path) -> None:
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import make_fake_phase_result

    plan = "execute-stream-stall"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [_execute_status(plan), _terminal_status(plan, "blocked")]
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        make_fake_phase_result(
            plan_dir,
            phase="execute",
            exit_kind="external_error",
            external_error=ExternalError(
                provider="deepseek",
                error_kind="stream_content_stall",
                message="Request timed out.",
                provider_error_code="timeout",
                error_layer="stream_content_stall",
            ),
        )
        return 1, "", "Request timed out."

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=fake_run,
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=5,
            poll_sleep=0,
            writer=lambda _message: None,
        )

    assert outcome.status == "blocked"
    assert outcome.external_retries_used == 0
    assert run_calls == [
        [
            "execute",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
            "--plan",
            plan,
        ]
    ]


def test_format_phase_heartbeat_logs_corrupt_state(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "corrupt-heartbeat")
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    caplog.set_level("WARNING", logger="megaplan")
    line = auto._format_phase_heartbeat(
        ["execute", "--plan", "corrupt-heartbeat"],
        elapsed_s=5,
        plan_dir=plan_dir,
        progress_changed=False,
    )

    assert "heartbeat" in line
    assert any("M3A_WARN_HEARTBEAT_STATE_READ" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    ("payload", "error", "expected_warning"),
    [
        (None, None, False),
        ("{not valid json", None, True),
        (None, PermissionError("denied"), True),
    ],
)
def test_read_unresolved_flag_ids_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    payload: str | None,
    error: Exception | None,
    expected_warning: bool,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "flags-plan")
    artifact_path = plan_dir / "gate_signals_v2.json"
    if payload is not None:
        artifact_path.write_text(payload, encoding="utf-8")
    elif error is not None:
        artifact_path.write_text("{}", encoding="utf-8")

    if error is not None:
        original_open = Path.open

        def _open(self: Path, *args, **kwargs):
            if self == artifact_path:
                raise error
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", _open)

    caplog.set_level("WARNING", logger="megaplan")

    assert auto._read_unresolved_flag_ids(plan_dir) == []
    messages = [record.getMessage() for record in caplog.records]
    if expected_warning:
        assert any("M3A_WARN_AUTO_FLAGS_READ" in message for message in messages)
    else:
        assert not messages


def test_drive_logs_warning_when_phase_start_emit_fails(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = "emit-warning-plan"
    _make_plan_dir(tmp_path, plan)
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args: list[str], cwd=None, timeout=60, progress_env=None):
        return 0, "ok", ""

    original_emit = auto.emit_event

    def maybe_fail_emit(kind, *args, **kwargs):
        if kind == auto.EventKind.INIT:
            return original_emit(kind, *args, **kwargs)
        raise RuntimeError("emit broke")

    caplog.set_level("WARNING", logger="megaplan")
    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto,
        "_run_megaplan",
        side_effect=fake_run,
    ), patch.object(auto, "emit_event", side_effect=maybe_fail_emit):
        outcome = drive(plan, cwd=tmp_path, max_iterations=3, poll_sleep=0, writer=lambda _message: None)

    assert outcome.status == "done"
    assert any("M3A_WARN_EMIT_AUTO_PHASE_START" in record.getMessage() for record in caplog.records)


def test_sum_history_cost_usd_logs_invalid_cost_entry(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "cost-plan")
    (plan_dir / "state.json").write_text(
        json.dumps({"history": [{"cost_usd": "bad"}, {"cost_usd": 1.5}]}),
        encoding="utf-8",
    )

    caplog.set_level("WARNING", logger="megaplan")
    total = auto._sum_history_cost_usd(plan_dir)

    assert total == 1.5
    assert any("M3A_WARN_COST_COERCION" in record.getMessage() for record in caplog.records)


def test_recover_execute_callback_failure_state_logs_corrupt_state(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "callback-plan")
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    caplog.set_level("WARNING", logger="megaplan")
    assert auto._recover_execute_callback_failure_state(plan_dir) is False
    assert any("M3A_WARN_CALLBACK_RECOVERY_READ" in record.getMessage() for record in caplog.records)


def test_clear_orphaned_active_step_logs_corrupt_state(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "orphan-plan")
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    caplog.set_level("WARNING", logger="megaplan")
    assert auto._clear_orphaned_active_step(plan_dir, "execute") is False
    assert any("M3A_WARN_ORPHAN_CLEAR_READ" in record.getMessage() for record in caplog.records)
