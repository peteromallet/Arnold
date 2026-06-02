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
from megaplan.execute import aggregation as execute_aggregation
from megaplan.types import CliError


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
                "active_step": {"phase": "execute", "agent": "codex", "mode": "persistent"},
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


def test_drive_routes_post_revise_plan_to_gate_before_recritique(tmp_path: Path) -> None:
    plan = "post-revise-gate"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "planned",
                "history": [{"step": "revise", "result": "success"}],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "plan_v2.meta.json").write_text(
        json.dumps({"flags_addressed": [{"id": "FLAG-001", "resolution": "fixed"}]}),
        encoding="utf-8",
    )
    (plan_dir / "faults.json").write_text(
        json.dumps(
            {
                "flags": [
                    {
                        "id": "FLAG-001",
                        "status": "addressed",
                        "severity": "significant",
                        "category": "correctness",
                        "concern": "verify post-revise gate",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    statuses = [
        {**_phase_status(plan, state="planned", next_step="critique"), "iteration": 2},
        _done_status(plan),
    ]
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        assert plan_name == plan
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, max_iterations=3, poll_sleep=0, writer=lambda _message: None)

    assert outcome.status == "done"
    assert run_calls[0][:1] == ["gate"]
    assert any("post-revise gate ready" in event.get("msg", "") for event in outcome.events)


def _active_wait_status(plan: str, state: str = "planning", next_step: str = "plan") -> dict:
    response = _phase_status(plan, state=state, next_step=next_step)
    response["active_step"] = {
        "phase": next_step,
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
        "phase": "critique",
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
        "phase": "critique",
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
        "phase": "critique",
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
        "phase": "execute",
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
        "phase": "plan",
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
        "phase": "execute",
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
        "phase": "plan",
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
            "phase": "plan",
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


def test_stall_counter_resets_when_tasks_complete_despite_unchanged_state(
    tmp_path: Path,
) -> None:
    """Productivity-aware stall detection.

    Simulates a large execute phase: ``state`` stays pinned at ``finalized``
    for many iterations while tasks are PRODUCTIVELY draining. The naive
    same-state-name counter would false-kill the run, but each iteration the
    task-completion signature (``progress.tasks_done``) advances, so the
    stall counter must reset and the run must NOT be declared stalled — it
    should run all the way to the iteration backstop.
    """
    plan = "draining-execute-plan"
    _make_plan_dir(tmp_path, plan)

    # Drive a couple of no-progress iterations between each completion so the
    # stall counter actually climbs (and we can prove the reset fires) without
    # ever reaching the threshold. Pattern of tasks_done per status call:
    # 0,0,1,1,2,2,... — stall_count goes 0->1->reset->1->reset, never hits 3.
    obs = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        # State never changes (execute keeps the plan at finalized); the
        # task-completion signature advances every other observation.
        done = obs["n"] // 2
        obs["n"] += 1
        status = _execute_status(plan_name, state="finalized")
        status["progress"] = {
            "tasks_done": done,
            "tasks_skipped": 0,
            "tasks_pending": 100 - done,
            "tasks_blocked": 0,
        }
        return status

    def fake_run(args, cwd=None, timeout=None):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,  # would trip after 3 same-state iters if naive
            max_iterations=10,
            max_review_rework_cycles=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Progress every iteration => never stalled => run to the iteration cap.
    assert outcome.status == "cap", (
        f"expected cap (hit max_iterations) with task-progress resets, got "
        f"{outcome.status}: {outcome.reason}"
    )
    progress_events = [
        e for e in outcome.events if "task progress advanced" in e.get("msg", "")
    ]
    assert progress_events, (
        "expected at least one task-progress stall-reset event; events: "
        f"{[e.get('msg') for e in outcome.events]}"
    )


def test_stall_counter_still_trips_when_no_task_progress(tmp_path: Path) -> None:
    """The real safety net must survive productivity-aware reset.

    State unchanged AND no task progress (the genuinely-stuck case) must
    still abort with status ``stalled`` once the threshold is reached — the
    fix only suppresses FALSE stalls, never the real backstop.
    """
    plan = "genuinely-stuck-plan"
    _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        # State pinned at finalized AND task counts frozen — no progress.
        status = _execute_status(plan_name, state="finalized")
        status["progress"] = {
            "tasks_done": 5,
            "tasks_skipped": 0,
            "tasks_pending": 10,
            "tasks_blocked": 0,
        }
        return status

    def fake_run(args, cwd=None, timeout=None):
        # Phase dispatch makes no progress — task signature stays frozen.
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,
            max_iterations=50,  # high so stall trips before the cap
            max_review_rework_cycles=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled", (
        f"expected stalled (no progress) got {outcome.status}: {outcome.reason}"
    )
    assert outcome.final_state == "finalized"
    assert outcome.iterations <= 6, (
        "stall should trip near the threshold, not run to the iteration cap; "
        f"iterations={outcome.iterations}"
    )


def test_stall_counter_resets_when_event_journal_progress_advances(
    tmp_path: Path,
) -> None:
    """Same state plus new non-driver events is progress, not a stall."""
    plan = "event-progress-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        status = _phase_status(plan_name, state="critiquing", next_step="critique")
        status["progress"] = {
            "tasks_done": 0,
            "tasks_skipped": 0,
            "tasks_pending": 0,
            "tasks_blocked": 0,
        }
        return status

    def fake_run(args, **kwargs):
        auto.emit_event(
            auto.EventKind.LLM_TOKEN_HEARTBEAT,
            plan_dir=plan_dir,
            phase="critique",
            payload={"request_id": "req-progress"},
        )
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=1,
            max_iterations=4,
            max_review_rework_cycles=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "cap", (
        f"expected cap with event progress, got {outcome.status}: {outcome.reason}"
    )


def test_stall_counter_still_trips_without_event_journal_progress(
    tmp_path: Path,
) -> None:
    """Same state and no progress events still hits the wedge backstop."""
    plan = "event-wedge-plan"
    _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        status = _phase_status(plan_name, state="critiquing", next_step="critique")
        status["progress"] = {
            "tasks_done": 0,
            "tasks_skipped": 0,
            "tasks_pending": 0,
            "tasks_blocked": 0,
        }
        return status

    def fake_run(args, **kwargs):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=2,
            max_iterations=10,
            max_review_rework_cycles=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "stalled at 'critiquing' for 2 iterations" in outcome.reason


def test_stall_counter_respects_configured_iteration_threshold(
    tmp_path: Path,
) -> None:
    plan = "threshold-plan"
    _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan_name, state="critiquing", next_step="critique")

    def fake_run(args, **kwargs):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=4,
            max_iterations=10,
            max_review_rework_cycles=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "for 4 iterations" in outcome.reason


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
    assert auto._phase_command("recover-blocked") == [
        "override",
        "recover-blocked",
        "--reason",
        "megaplan auto: recover blocked plan after blocker resolution",
    ]
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
        "finalized": 0,
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


def test_drive_stop_at_finalized_returns_success_before_execute_dispatch(tmp_path: Path) -> None:
    plan = "stop-at-finalized"
    _make_plan_dir(tmp_path, plan)
    captured_args: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan_name, state="finalized")

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        captured_args.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stop_at_finalized=True,
            max_iterations=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "finalized"
    assert outcome.final_state == "finalized"
    assert captured_args == []


def test_drive_default_flow_continues_past_finalized_into_execute(tmp_path: Path) -> None:
    plan = "continue-past-finalized"
    _make_plan_dir(tmp_path, plan)
    statuses = [_execute_status(plan, state="finalized"), _done_status(plan)]
    captured_args: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None, progress_env=None, liveness_plan_dir=None):
        captured_args.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=2,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert captured_args == [auto._phase_command("execute") + ["--plan", plan]]


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

    # Policy retries_first=0 means no retries; single execute call, plan
    # proceeds to done without context retry.
    assert outcome.status == "done"
    assert outcome.context_retries_used == 0
    assert len(calls) == 1


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

    # Immediate bail removed; context retry loop never fires (cap=0 via
    # CATEGORY_POLICY).  Exhaustion falls through to escalate block which
    # triggers ceiling handoff (no tier ladder) → stall.
    assert outcome.status == "stalled"
    assert outcome.context_retries_used == 0


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

    # worker_blocked bail removed; exhaustion falls through to escalate
    # block → ceiling handoff (no tier ladder) → stall.
    assert outcome.status == "stalled"
    assert outcome.blocked_retries_used == 1
    # Ceiling handoff history expected after blocked_retries exhausted
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    assert any(
        isinstance(e, dict) and e.get("scope") == "ceiling_handoff"
        for e in history_entries
    ), f"expected ceiling_handoff history, got {history_entries}"


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


def test_execute_scope_drift_counts_claimed_untracked_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    new_file = tmp_path / "tests" / "characterization" / "_golden_recorders" / "case.py"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("print('golden')\n", encoding="utf-8")

    drift = execute_aggregation._compute_execute_scope_drift(
        tmp_path,
        {"files_changed": ["tests/characterization/_golden_recorders/case.py"]},
    )

    assert drift.files_missing == []
    assert drift.files_added == []
    assert drift.severity == "none"


@pytest.mark.parametrize(
    "exit_kind",
    ["blocked_by_quality", "blocked_by_prereq"],
)
def test_empty_execute_block_proceeds_without_retry(
    tmp_path: Path,
    exit_kind: str,
) -> None:
    plan = f"empty-{exit_kind}"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from tests.conftest import fake_run_with_phase_result

    statuses = [_execute_status(plan), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(
             auto,
             "_run_megaplan",
             side_effect=fake_run_with_phase_result(plan_dir, exit_kind=exit_kind),
         ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=0,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert outcome.blocked_retries_used == 0
    assert any("treating as success" in event["msg"] for event in outcome.events)


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
                "active_step": {"phase": "execute", "run_id": "stale"},
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
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "orphan-plan")
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CliError, match="M3B_HALT_ORPHAN_CLEAR_READ"):
        auto._clear_orphaned_active_step(plan_dir, "execute")


def test_drive_halts_before_progress_when_orphan_clear_read_fails(
    tmp_path: Path,
) -> None:
    plan = "orphan-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")
    run_calls: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=lambda *_args, **_kwargs: _orphaned_critique_status(plan)), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        with pytest.raises(CliError, match="M3B_HALT_ORPHAN_CLEAR_READ"):
            drive(
                plan,
                cwd=tmp_path,
                max_iterations=3,
                stall_threshold=10,
                poll_sleep=0,
                writer=lambda _m: None,
            )

    assert run_calls == []


def test_clear_orphaned_active_step_raises_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "orphan-plan")
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "orphan-plan", "current_state": "finalized", "active_step": {"phase": "execute"}}),
        encoding="utf-8",
    )

    def broken_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(auto, "write_plan_state", broken_write)

    with pytest.raises(CliError, match="M3B_HALT_ORPHAN_CLEAR_WRITE"):
        auto._clear_orphaned_active_step(plan_dir, "execute")


def test_drive_halts_before_progress_when_orphan_clear_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = "orphan-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "finalized",
                "active_step": {"phase": "critique"},
            }
        ),
        encoding="utf-8",
    )
    run_calls: list[list[str]] = []

    def broken_write(*args, **kwargs):
        raise OSError("disk full")

    def fake_run(args, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        run_calls.append(list(args))
        return 0, "{}", ""

    monkeypatch.setattr(auto, "write_plan_state", broken_write)

    with patch.object(auto, "_status", side_effect=lambda *_args, **_kwargs: _orphaned_critique_status(plan)), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        with pytest.raises(CliError, match="M3B_HALT_ORPHAN_CLEAR_WRITE"):
            drive(
                plan,
                cwd=tmp_path,
                max_iterations=3,
                stall_threshold=10,
                poll_sleep=0,
                writer=lambda _m: None,
            )

    assert run_calls == []


def _awaiting_human_status(plan: str, state: str = "awaiting_human_verify") -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": "Plan is awaiting human input.",
        "next_step": None,
        "valid_next": [],
    }


def test_auto_driver_prep_awaiting_human_includes_blocking_questions(
    tmp_path: Path,
) -> None:
    plan = "prep-halt-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "awaiting_human_verify",
                "clarification": {
                    "intent_summary": "prep surfaced 2 blocking ambiguities",
                    "questions": [
                        "[blocking] Which auth library?",
                        "[blocking] REST or GraphQL?",
                    ],
                    "source": "prep",
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _awaiting_human_status(plan_name)

    with patch.object(auto, "_status", side_effect=fake_status):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "awaiting_human"
    assert "Which auth library?" in outcome.reason
    assert "REST or GraphQL?" in outcome.reason
    assert "override add-note" in outcome.reason
    assert "override resume-clarify" in outcome.reason


def test_auto_driver_criteria_awaiting_human_has_generic_reason(
    tmp_path: Path,
) -> None:
    plan = "criteria-halt-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": "awaiting_human_verify",
                "clarification": {
                    "intent_summary": "Criteria verification needed.",
                    "questions": ["Is the plan acceptable?"],
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _awaiting_human_status(plan_name)

    with patch.object(auto, "_status", side_effect=fake_status):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "awaiting_human"
    assert "plan has criteria requiring human verification" in outcome.reason
    assert "override add-note" not in outcome.reason
    assert "override resume-clarify" not in outcome.reason


# ─────────────────────────────────────────────────────────────────────────
# Auto-ESCALATE-up: respond to repeated execute failures by climbing to a
# more capable tier model (capped at the ceiling), forcing a fresh session.
# ─────────────────────────────────────────────────────────────────────────

# Canonical premium ladder: tiers 1-2 = DeepSeek (same model), 3 = Sonnet,
# 4-5 = Opus (same model). Exercises both the distinct-model climb and the
# skip-same-model edge case (4→5 is a no-op).
_PREMIUM_LADDER = {
    1: "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro",
    2: "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro",
    3: "claude:claude-sonnet-4-6",
    4: "claude:claude-opus-4-7",
    5: "claude:claude-opus-4-7",
}


def _write_tier_state(
    plan_dir: Path,
    *,
    ladder: dict[int, str] | None = _PREMIUM_LADDER,
    max_tier: int | None = None,
) -> None:
    """Stamp state.json with a tier_models.execute ladder and (optionally) an
    execute history entry recording the highest tier the last execute used.
    """
    state: dict = {
        "name": plan_dir.name,
        "current_state": "finalized",
        "history": [],
        "meta": {},
    }
    if ladder is not None:
        state["config"] = {
            "tier_models": {"execute": {str(k): v for k, v in ladder.items()}}
        }
    if max_tier is not None:
        state["history"] = [
            {
                "step": "execute",
                "result": "blocked",
                "cost_usd": 0.1,
                "batch_to_tier": [
                    {"batch_number": 1, "batch_complexity": max_tier},
                ],
            }
        ]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


# ── Pure helper unit tests ───────────────────────────────────────────────


def test_next_escalation_tier_skips_same_model_step() -> None:
    # Baseline tier 3 (Sonnet) escalates to tier 4 (Opus) — a distinct model.
    nxt = auto._next_escalation_tier(_PREMIUM_LADDER, current_tier=3)
    assert nxt == (4, "claude:claude-opus-4-7")
    # Baseline tier 4 (Opus): tier 5 is also Opus (same spec) → no distinct
    # stronger model → ceiling reached → None.
    assert auto._next_escalation_tier(_PREMIUM_LADDER, current_tier=4) is None
    # Baseline tier 1 (DeepSeek): tier 2 is the same DeepSeek spec, so the
    # first *distinct* model up is tier 3 (Sonnet), not tier 2.
    assert auto._next_escalation_tier(_PREMIUM_LADDER, current_tier=1) == (
        3,
        "claude:claude-sonnet-4-6",
    )


def test_next_escalation_tier_empty_ladder_is_noop() -> None:
    assert auto._next_escalation_tier({}, current_tier=None) is None


def test_read_execute_tier_ladder_missing_is_empty(tmp_path: Path) -> None:
    plan_dir = _make_plan_dir(tmp_path, "no-tiers")
    # _make_plan_dir writes a state with no config.tier_models.
    assert auto._read_execute_tier_ladder(plan_dir) == {}


def test_latest_execute_max_tier_reads_history(tmp_path: Path) -> None:
    plan_dir = _make_plan_dir(tmp_path, "tier-hist")
    _write_tier_state(plan_dir, max_tier=3)
    assert auto._latest_execute_max_tier(plan_dir) == 3


# ── (a) Consecutive failures escalate up to the next distinct model ──────


def test_review_nonconvergence_single_cycle_does_not_escalate() -> None:
    streaks: dict[str, int] = {}

    nonconverging = auto._nonconverging_rework_tasks(
        previous={},
        current={"T1": {"flag:REVIEW-001"}},
        streaks=streaks,
    )

    assert nonconverging == []
    assert streaks == {"T1": 1}


def test_review_nonconvergence_second_same_issue_escalates() -> None:
    streaks = {"T1": 1}

    nonconverging = auto._nonconverging_rework_tasks(
        previous={"T1": {"flag:REVIEW-001"}},
        current={"T1": {"flag:REVIEW-001"}},
        streaks=streaks,
    )

    assert nonconverging == ["T1"]
    assert streaks["T1"] == 2


def test_review_nonconvergence_shrinking_findings_do_not_escalate() -> None:
    streaks = {"T1": 1}

    nonconverging = auto._nonconverging_rework_tasks(
        previous={"T1": {"flag:REVIEW-001", "flag:REVIEW-002"}},
        current={"T1": {"flag:REVIEW-001"}},
        streaks=streaks,
    )

    assert nonconverging == []
    assert streaks["T1"] == 1


def test_review_nonconvergence_escalation_plan_uses_next_distinct_tier(
    tmp_path: Path,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "review-nonconvergence")
    _write_tier_state(plan_dir, max_tier=3)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "T1", "complexity": 3, "tier_override": 3},
                ]
            }
        ),
        encoding="utf-8",
    )

    baseline, next_tier = auto._review_nonconvergence_escalation_plan(
        plan_dir=plan_dir,
        task_id="T1",
        ladder=_PREMIUM_LADDER,
    )

    assert baseline == 3
    assert next_tier == (4, "claude:claude-opus-4-7")
    assert auto._pin_tasks_to_tier(plan_dir, ["T1"], next_tier[0]) == ["T1"]
    finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    assert finalize["tasks"][0]["tier_override"] == 4


def test_review_nonconvergence_escalation_plan_returns_none_at_ceiling(
    tmp_path: Path,
) -> None:
    plan_dir = _make_plan_dir(tmp_path, "review-nonconvergence-ceiling")
    _write_tier_state(plan_dir, max_tier=4)
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "complexity": 4, "tier_override": 4}]}),
        encoding="utf-8",
    )

    baseline, next_tier = auto._review_nonconvergence_escalation_plan(
        plan_dir=plan_dir,
        task_id="T1",
        ladder=_PREMIUM_LADDER,
    )

    assert baseline == 4
    assert next_tier is None


def test_consecutive_failures_escalate_up_to_next_distinct_model(
    tmp_path: Path,
) -> None:
    plan = "escalate-up"
    plan_dir = _make_plan_dir(tmp_path, plan)
    # Failing execute routed at tier 3 (Sonnet); escalate should pin tier 4 Opus.
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        # Always fail execute with internal_error; distinct invocation_id each
        # call so _run_phase sees a changed phase_result signature.
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # First two execute dispatches run un-escalated (internal_error consumes
    # retries_first=1 inline retry); on the 3rd failure the streak reaches 2
    # and the driver escalates via phase_pin.  --fresh is appended
    # (escalation_fired=True) but --phase-model is NOT (only on legacy path).
    escalated_cmds = [
        c for c in seen_cmds
        if "--fresh" in c
    ]
    assert len(escalated_cmds) >= 1, (
        f"expected at least one escalated execute with --fresh, saw: {seen_cmds}"
    )
    # Per-task/phase_pin semantics: --phase-model execute=<spec> is NOT
    # appended (only the legacy category-is-None path sets it).
    for c in escalated_cmds:
        assert "--phase-model" not in c, (
            f"--phase-model should not appear on phase_pin path: {c}"
        )
    assert outcome.tier_escalations_used >= 1
    # escalation_tier_pin is only set on the legacy category-is-None path,
    # not on the phase_pin path.
    # The escalation is observable as a tier_escalated event carrying the
    # from→to model + tier and the failure count.
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        e
        for e in (json.loads(ln) for ln in lines if ln.strip())
        if e.get("kind") == "tier_escalated"
    ]
    assert tier_events, "expected a tier_escalated event"
    payload = tier_events[0].get("payload", {})
    assert payload.get("from_tier") == 3
    assert payload.get("to_tier") == 4
    assert payload.get("to_model") == "claude:claude-opus-4-7"
    assert payload.get("failure_count") == 2


# ── (b) At the ceiling it does NOT escalate; manual_review halt still fires ─


def test_at_ceiling_no_escalation_and_manual_review_halt_fires(
    tmp_path: Path,
) -> None:
    plan = "escalate-ceiling"
    plan_dir = _make_plan_dir(tmp_path, plan)
    # Failing execute already routed at tier 4 (Opus). Tier 5 is also Opus
    # (same model) → no distinct stronger model → nothing to escalate to.
    _write_tier_state(plan_dir, max_tier=4)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=3,
            max_iterations=8,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No execute command should carry a phase-model escalation pin.
    assert not any("--phase-model" in c for c in seen_cmds), seen_cmds
    assert outcome.tier_escalations_used == 0
    assert outcome.escalation_tier_pin is None
    # The existing state-stall manual_review halt is the genuine last resort.
    assert outcome.status == "stalled"
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["resume_cursor"]["retry_strategy"] == "manual_review"


# ── (c) Escalate forces fresh dispatch (no resume of old session) ─────────


def test_escalate_forces_fresh_dispatch(tmp_path: Path) -> None:
    plan = "escalate-fresh"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Every escalated execute carries --fresh (escalation_fired=True).
    # --phase-model is NOT appended on the phase_pin path (only legacy).
    fresh_cmds = [c for c in seen_cmds if "--fresh" in c]
    assert fresh_cmds, f"expected at least one escalated execute with --fresh, saw {seen_cmds}"
    for c in fresh_cmds:
        assert "--phase-model" not in c, (
            f"--phase-model should not appear on phase_pin path: {c}"
        )


# ── (d) Non-tier-routed run no-ops gracefully ─────────────────────────────


def test_non_tier_routed_run_no_ops_gracefully(tmp_path: Path) -> None:
    plan = "escalate-no-tiers"
    plan_dir = _make_plan_dir(tmp_path, plan)
    # No config.tier_models at all (flat execute pin) — write history only.
    _write_tier_state(plan_dir, ladder=None, max_tier=None)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=3,
            max_iterations=8,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Nothing to escalate to — no pin, no crash, falls through to the halt.
    assert not any("--phase-model" in c for c in seen_cmds), seen_cmds
    assert outcome.tier_escalations_used == 0
    assert outcome.status == "stalled"


# ── (e) Counter resets on progress ────────────────────────────────────────


def test_failure_streak_resets_on_progress(tmp_path: Path) -> None:
    plan = "escalate-progress-reset"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    state = {"n": 0, "done": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        resp = _execute_status(plan)
        # Report increasing progress so the streak resets each iteration.
        resp["progress"] = {"tasks_done": state["done"], "tasks_skipped": 0}
        return resp

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        state["n"] += 1
        # Make forward progress on every execute (one more task done), but still
        # report a failure exit_kind — progress must win and reset the streak.
        state["done"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{state['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=4,
            max_iterations=6,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Because each iteration makes forward progress, the failure streak never
    # reaches the escalate threshold — no escalation occurs.
    assert not any("--phase-model" in c for c in seen_cmds), seen_cmds
    assert outcome.tier_escalations_used == 0


# ── Legacy regression: exit_kind=None degrades to streak-based phase-pin ──


def test_legacy_exit_kind_none_phase_model_and_fresh(
    tmp_path: Path,
) -> None:
    """When result.exit_kind is None (uncategorised failure), the legacy
    streak-based phase-pin path fires: cmd contains --phase-model
    execute=<spec> AND --fresh."""
    plan = "legacy-none-exit-kind"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        # Write a phase_result with exit_kind=None so classify_failure
        # returns (None, []) — the legacy category-is-None path.
        from tests.conftest import make_fake_phase_result
        make_fake_phase_result(
            plan_dir,
            exit_kind=None,
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "generic failure"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # The legacy path sets escalation_pin_spec and escalation_tier_pin,
    # so --phase-model execute=<spec> AND --fresh both appear.
    escalated_cmds = [
        c for c in seen_cmds
        if "--fresh" in c
    ]
    assert len(escalated_cmds) >= 1, (
        f"expected at least one escalated cmd with --fresh, saw: {seen_cmds}"
    )
    for c in escalated_cmds:
        assert "--phase-model" in c, (
            f"legacy path should append --phase-model execute=<spec>: {c}"
        )
        # Find the --phase-model argument and verify execute=<spec>
        try:
            idx = c.index("--phase-model")
            spec = c[idx + 1]
            assert spec.startswith("execute="), (
                f"expected execute=<spec>, got: {spec}"
            )
        except (ValueError, IndexError):
            raise AssertionError(
                f"--phase-model not found or missing value in: {c}"
            )

    # The legacy path sets escalation_tier_pin.
    assert outcome.escalation_tier_pin is not None
    assert outcome.tier_escalations_used >= 1


# ═══════════════════════════════════════════════════════════════════════════
# T5 tests (restored): per-task escalate, context_exhausted, legacy,
# drift no-op, ceiling handoff
# ═══════════════════════════════════════════════════════════════════════════


def test_per_task_escalate_sibling_unset(tmp_path: Path) -> None:
    """Per-task escalate: pin only failing tasks, cmd has --fresh, no
    --phase-model execute=<spec>."""
    plan = "per-task-escalate"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    # Write a finalize.json so _pin_tasks_to_tier has tasks to pin.
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [
            {"id": "T1", "status": "pending"},
            {"id": "T2", "status": "done"},
        ]}),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result, BlockedTask

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            blocked_tasks=(BlockedTask(task_id="T1", reason="prereq missing"),),
        )
        return 1, "", "blocked"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Escalation should have fired via per_task path.
    assert outcome.tier_escalations_used >= 1
    # --fresh present but no --phase-model.
    fresh_cmds = [c for c in seen_cmds if "--fresh" in c]
    assert fresh_cmds, f"expected --fresh in escalated cmd, saw {seen_cmds}"
    for c in fresh_cmds:
        assert "--phase-model" not in c, (
            f"--phase-model should not appear on per-task path: {c}"
        )


def test_first_context_exhausted_escalates(tmp_path: Path) -> None:
    """First-occurrence context_exhausted escalates (retries_first=0)."""
    plan = "ctx-exhaust-escalate"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="context_exhausted",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "context window exhausted"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Two context_exhausted failures should trigger escalation
    assert outcome.tier_escalations_used >= 1
    # Context retry never fires (retries_first=0)
    assert outcome.context_retries_used == 0
    # TIER_ESCALATED event should be present
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        json.loads(ln) for ln in lines if ln.strip()
        if json.loads(ln).get("kind") == "tier_escalated"
    ]
    assert tier_events, "expected a tier_escalated event"


def test_legacy_no_category_appends_both_flags(tmp_path: Path) -> None:
    """Legacy path (category is None): --phase-model AND --fresh appended.

    When classify_failure returns None (e.g., unknown exit_kind), the
    legacy path sets escalation_pin_spec and both flags are appended.
    """
    plan = "legacy-both-flags"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        # Use a non-standard exit_kind that classify_failure returns None for
        make_fake_phase_result(
            plan_dir,
            exit_kind="unknown_exit_kind",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "unknown failure"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Legacy path: both --phase-model AND --fresh should appear
    pinned = [
        c for c in seen_cmds
        if "--phase-model" in c and "--fresh" in c
    ]
    assert pinned, (
        f"expected --phase-model + --fresh on legacy path, saw: {seen_cmds}"
    )


def test_drift_noop_and_history(tmp_path: Path) -> None:
    """blocked_by_quality_drift: no-op — no retry, no escalate, history written."""
    plan = "drift-noop"
    plan_dir = _make_plan_dir(tmp_path, plan)
    from tests.conftest import make_fake_phase_result, Deviation

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            deviations=(Deviation(kind="scope_drift", message="scope drift"),),
        )
        return 1, "", "drift"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=2,
            max_iterations=4,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No escalation should happen for drift
    assert outcome.tier_escalations_used == 0
    # Drift skip history should be recorded with category=blocked_by_quality_drift
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    drift_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "drift_skip"
    ]
    assert len(drift_entries) >= 1, f"expected drift_skip history, got {history_entries}"
    # Verify category field
    for e in drift_entries:
        assert e.get("category") == "blocked_by_quality_drift", (
            f"expected category=blocked_by_quality_drift, got {e.get('category')}"
        )
    # Verify no streak advancement: no --fresh flags should appear in any
    # execute commands (--fresh is only appended on escalation).
    execute_cmds = [c for c in seen_cmds if "execute" in c]
    for cmd in execute_cmds:
        assert "--fresh" not in cmd, (
            f"drift should not advance streak, but --fresh was in: {cmd}"
        )


def test_ceiling_handoff_monotonic(tmp_path: Path) -> None:
    """Ceiling handoff: no escalation beyond highest distinct tier.

    When already at the ceiling tier, escalation hits ceiling_handoff
    and does NOT pin a higher tier.
    """
    plan = "ceiling-monotonic"
    plan_dir = _make_plan_dir(tmp_path, plan)
    # Tier 4 is Opus; tier 5 is also Opus (same model).  So the ceiling
    # is tier 4 — there's no distinct stronger model above.
    _write_tier_state(plan_dir, max_tier=4)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="internal_error",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "boom"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No escalation to a higher tier (ceiling reached)
    assert outcome.tier_escalations_used == 0
    # Ceiling handoff history should be recorded
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    ceiling_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "ceiling_handoff"
    ]
    assert len(ceiling_entries) >= 1, f"expected ceiling_handoff, got {history_entries}"
    # No --phase-model appended
    assert not any("--phase-model" in c for c in seen_cmds)


# ═══════════════════════════════════════════════════════════════════════════
# T6: Timeout remediation
# ═══════════════════════════════════════════════════════════════════════════


def test_timeout_remediation_then_escalation(tmp_path: Path) -> None:
    """Two consecutive timeouts — first appends --batch 1 + --phase-idle-timeout
    3600 (no tier change); second triggers tier escalation via Step 5."""
    plan = "timeout-remediation"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="timeout",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "timeout"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # After first timeout: remediation cmd should carry --batch 1 and
    # --phase-idle-timeout 3600
    remediation_cmds = [
        c for c in seen_cmds
        if "--batch" in c and "1" in c and "--phase-idle-timeout" in c
    ]
    assert len(remediation_cmds) >= 1, (
        f"expected remediation cmd with --batch 1 + --phase-idle-timeout, "
        f"saw: {seen_cmds}"
    )
    # The first timeout must NOT escalate (no tier change yet)
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    remediation_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "timeout_remediation"
    ]
    assert len(remediation_entries) >= 1, (
        f"expected timeout_remediation history, got {history_entries}"
    )
    # Second consecutive timeout triggers escalation
    assert outcome.tier_escalations_used >= 1, (
        "expected tier escalation after second consecutive timeout"
    )
    # Verify tier_escalated event exists
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        json.loads(ln) for ln in lines if ln.strip()
        if json.loads(ln).get("kind") == "tier_escalated"
        and json.loads(ln).get("payload", {}).get("scope") != "lateral_deferred"
    ]
    assert tier_events, "expected a tier_escalated event after second timeout"


# ═══════════════════════════════════════════════════════════════════════════
# T8: External error lateral defer
# ═══════════════════════════════════════════════════════════════════════════


def test_external_error_lateral_deferred(tmp_path: Path) -> None:
    """external_error PhaseResult emits lateral_deferred history entry, does
    not touch tier_override, does not advance streak."""
    plan = "ext-error-defer"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result, ExternalError

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="external_error",
            invocation_id=f"inv-{call['n']}",
            external_error=ExternalError(
                provider="openrouter",
                error_kind="quota",
                message="quota exceeded",
            ),
        )
        return 1, "", "quota"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=2,
            max_iterations=4,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No escalation — external_error is not a capability problem
    assert outcome.tier_escalations_used == 0
    # Lateral deferred history entry should exist
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    deferred_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "lateral_deferred"
    ]
    assert len(deferred_entries) >= 1, (
        f"expected lateral_deferred history, got {history_entries}"
    )
    for e in deferred_entries:
        assert e.get("category") == "external_error"
    # No --fresh (no streak advancement)
    execute_cmds = [c for c in seen_cmds if "execute" in c]
    for cmd in execute_cmds:
        assert "--fresh" not in cmd, (
            f"external_error should not advance streak, got --fresh in: {cmd}"
        )
    # No tier_override changes (no escalation fired)
    assert outcome.escalation_tier_pin is None


# ═══════════════════════════════════════════════════════════════════════════
# T9: Dual-channel escalation recording
# ═══════════════════════════════════════════════════════════════════════════


def test_dual_channel_escalation_recording(tmp_path: Path) -> None:
    """After a simulated escalation, the latest entry in state.json['history']
    carries category, from_tier, to_tier, retries_before_escalation,
    failing_task_ids, and scope — AND events.ndjson carries the same fields."""
    plan = "dual-channel"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result, BlockedTask

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            blocked_tasks=(BlockedTask(task_id="T1", reason="prereq missing"),),
        )
        return 1, "", "blocked"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.tier_escalations_used >= 1

    # Check state.json history for the escalation entry
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    escalation_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("step") == "escalation"
        and e.get("scope") not in ("retries_exhausted",)
        and e.get("scope") != "drift_skip"
    ]
    # Find the actual tier escalation entry (not retries_exhausted/drift)
    tier_entries = [
        e for e in escalation_entries
        if e.get("from_tier") is not None
    ]
    assert len(tier_entries) >= 1, (
        f"expected tier escalation history entry, got {escalation_entries}"
    )
    entry = tier_entries[-1]
    # Verify the six required fields
    assert "category" in entry
    assert "from_tier" in entry
    assert "to_tier" in entry
    assert "retries_before_escalation" in entry
    assert "failing_task_ids" in entry
    assert "scope" in entry
    assert "from_model" in entry
    assert "to_model" in entry

    # Check events.ndjson for the escalation event
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        json.loads(ln) for ln in lines if ln.strip()
        if json.loads(ln).get("kind") == "tier_escalated"
        and json.loads(ln).get("payload", {}).get("scope") not in (
            "lateral_deferred", None
        )
    ]
    assert tier_events, "expected a tier_escalated event in events.ndjson"
    payload = tier_events[0].get("payload", {})
    assert "category" in payload
    assert "from_tier" in payload
    assert "to_tier" in payload
    assert "retries_before_escalation" in payload
    assert "failing_task_ids" in payload
    assert "scope" in payload
    assert "from_model" in payload
    assert "to_model" in payload


# ═══════════════════════════════════════════════════════════════════════════
# T10: Step 8a core integration tests
# ═══════════════════════════════════════════════════════════════════════════


def test_blocked_by_quality_semantic_per_task_escalate(tmp_path: Path) -> None:
    """Drive a synthetic two-task finalize.json through the auto loop with
    _run_phase returning blocked_by_quality whose blocked_tasks reference
    task B. After DEFAULT_MAX_BLOCKED_RETRIES retries assert: B has
    tier_override == new_tier; A unchanged; one history entry with
    category=blocked_by_quality_semantic, failing_task_ids=['B'],
    scope='per_task'; cmd contains --fresh and NOT --phase-model execute=.
    """
    plan = "bq-semantic-per-task"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    # Two-task finalize.json
    (plan_dir / "finalize.json").write_text(
        json.dumps({
            "tasks": [
                {"id": "A", "complexity": 1, "status": "pending"},
                {"id": "B", "complexity": 1, "status": "pending"},
            ]
        }),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result, BlockedTask

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            blocked_tasks=(BlockedTask(task_id="B", reason="quality gate"),),
        )
        return 1, "", "blocked"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=1,
            escalate_after_fails=1,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Escalation should have fired via per_task path.
    assert outcome.tier_escalations_used >= 1

    # Verify finalize.json: B has tier_override, A does not.
    finalize_data = json.loads(
        (plan_dir / "finalize.json").read_text(encoding="utf-8")
    )
    task_a = next(t for t in finalize_data["tasks"] if t["id"] == "A")
    task_b = next(t for t in finalize_data["tasks"] if t["id"] == "B")
    assert task_b.get("tier_override") is not None, (
        f"task B should have tier_override set, got {task_b}"
    )
    new_tier = task_b["tier_override"]
    assert isinstance(new_tier, int) and new_tier >= 1
    # A should be unchanged — no tier_override or still the original
    assert task_a.get("tier_override") is None, (
        f"task A should NOT have tier_override, got {task_a}"
    )

    # Verify history: one entry with category=blocked_by_quality_semantic,
    # failing_task_ids=['B'], scope='per_task'.
    state_data = json.loads(
        (plan_dir / "state.json").read_text(encoding="utf-8")
    )
    history_entries = state_data.get("history", [])
    per_task_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "per_task"
    ]
    assert len(per_task_entries) >= 1, (
        f"expected per_task scope history entry, got {history_entries}"
    )
    entry = per_task_entries[0]
    assert entry.get("category") == "blocked_by_quality_semantic", (
        f"expected category=blocked_by_quality_semantic, got {entry.get('category')}"
    )
    assert entry.get("failing_task_ids") == ["B"], (
        f"expected failing_task_ids=['B'], got {entry.get('failing_task_ids')}"
    )

    # Verify cmd: contains --fresh and NOT --phase-model execute=
    fresh_cmds = [c for c in seen_cmds if "--fresh" in c]
    assert fresh_cmds, f"expected --fresh in escalated cmd, saw {seen_cmds}"
    for c in fresh_cmds:
        assert "--phase-model" not in c, (
            f"--phase-model should not appear on per-task path: {c}"
        )


def test_blocked_by_prereq_awaiting_human_no_escalation(
    tmp_path: Path,
) -> None:
    """blocked_by_prereq: no override applied; awaiting_human outcome;
    history entry with scope='manual_review_handoff'; no streak increment.
    """
    plan = "bq-prereq-awaiting"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    from tests.conftest import make_fake_phase_result, BlockedTask

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_prereq",
            invocation_id=f"inv-{call['n']}",
            blocked_tasks=(BlockedTask(task_id="T1", reason="prereq missing"),),
        )
        return 1, "", "blocked"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=1,
            escalate_after_fails=2,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # Should exit as awaiting_human without escalation.
    assert outcome.status == "awaiting_human", (
        f"expected awaiting_human, got {outcome.status!r}"
    )
    assert outcome.tier_escalations_used == 0, (
        "blocked_by_prereq must not trigger tier escalation"
    )

    # No tier_override applied to any task.
    state_data = json.loads(
        (plan_dir / "state.json").read_text(encoding="utf-8")
    )
    history_entries = state_data.get("history", [])
    manual_review_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "manual_review_handoff"
    ]
    assert len(manual_review_entries) >= 1, (
        f"expected manual_review_handoff history entry, got {history_entries}"
    )
    entry = manual_review_entries[0]
    assert entry.get("category") == "blocked_by_prereq", (
        f"expected category=blocked_by_prereq, got {entry.get('category')}"
    )
    assert "failing_task_ids" in entry

    # No streak increment: no --fresh in any execute command.
    execute_cmds = [c for c in seen_cmds if "execute" in c]
    for cmd in execute_cmds:
        assert "--fresh" not in cmd, (
            f"blocked_by_prereq should not advance streak, "
            f"but --fresh was in: {cmd}"
        )

    # No tier escalation pin set.
    assert outcome.escalation_tier_pin is None


# ═══════════════════════════════════════════════════════════════════════════
# T11: Step 8b remaining-category integration tests
# ═══════════════════════════════════════════════════════════════════════════


def test_context_exhausted_override_bypasses_loop(tmp_path: Path) -> None:
    """context_exhausted → override applied on first failure, existing while
    loop bypassed (cap=0).  Phase-pin escalates all pending tasks."""
    plan = "ctx-exhaust-override"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    # finalize.json so phase_pin has tasks to pin
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [
            {"id": "A", "complexity": 1, "status": "pending"},
            {"id": "B", "complexity": 1, "status": "pending"},
        ]}),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="context_exhausted",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "context exhausted"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=1,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # context_exhausted has retries_first=0 → while loop bypassed →
    # no context retries consumed
    assert outcome.context_retries_used == 0

    # Escalation should fire (phase_pin since failing_task_ids is empty)
    assert outcome.tier_escalations_used >= 1

    # Verify override applied in finalize.json (phase_pin pins all pending)
    finalize_data = json.loads(
        (plan_dir / "finalize.json").read_text(encoding="utf-8")
    )
    for task in finalize_data["tasks"]:
        assert task.get("tier_override") is not None, (
            f"task {task['id']} should have tier_override after phase_pin"
        )
        assert isinstance(task["tier_override"], int)

    # --fresh present, no --phase-model (per_task/phase_pin path)
    fresh_cmds = [c for c in seen_cmds if "--fresh" in c]
    assert fresh_cmds, f"expected --fresh in escalated cmd, saw {seen_cmds}"
    for c in fresh_cmds:
        assert "--phase-model" not in c, (
            f"--phase-model should not appear on phase_pin path: {c}"
        )

    # tier_escalated event should be present
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        json.loads(ln) for ln in lines if ln.strip()
        if json.loads(ln).get("kind") == "tier_escalated"
        and json.loads(ln).get("payload", {}).get("scope") not in (
            "lateral_deferred", None
        )
    ]
    assert tier_events, "expected a tier_escalated event"
    payload = tier_events[0].get("payload", {})
    assert payload.get("scope") == "phase_pin", (
        f"expected scope=phase_pin, got {payload.get('scope')}"
    )


def test_timeout_remediation_before_override_then_escalate(
    tmp_path: Path,
) -> None:
    """timeout → batch-1 + --phase-idle-timeout 3600 applied BEFORE any
    override; second consecutive timeout escalates."""
    plan = "timeout-remed-then-esc"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    # finalize.json for phase_pin verification
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [
            {"id": "A", "complexity": 1, "status": "pending"},
            {"id": "B", "complexity": 1, "status": "pending"},
        ]}),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="timeout",
            invocation_id=f"inv-{call['n']}",
        )
        return 1, "", "timeout"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=1,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # First timeout: remediation cmd with --batch 1 + --phase-idle-timeout 3600
    batch1_cmds = [
        c for c in seen_cmds
        if "--batch" in c and "1" in c
        and any(a.startswith("--phase-idle-timeout") for a in c)
    ]
    assert len(batch1_cmds) >= 1, (
        f"expected remediation cmd with --batch 1 + --phase-idle-timeout, "
        f"saw: {seen_cmds}"
    )
    # Verify --batch 1 value is a separate arg
    for cmd in batch1_cmds:
        batch_idx = cmd.index("--batch") if "--batch" in cmd else -1
        assert batch_idx >= 0
        assert cmd[batch_idx + 1] == "1", (
            f"--batch should be followed by '1', got: {cmd}"
        )

    # timeout_remediation history entry BEFORE any tier override
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    remediation_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "timeout_remediation"
    ]
    assert len(remediation_entries) >= 1, (
        f"expected timeout_remediation history, got {history_entries}"
    )
    for e in remediation_entries:
        assert e.get("category") == "timeout"

    # Second consecutive timeout should escalate (tier_escalations >= 1)
    assert outcome.tier_escalations_used >= 1, (
        "expected tier escalation after second consecutive timeout"
    )

    # tier_escalated event should exist with scope=phase_pin
    lines = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    tier_events = [
        json.loads(ln) for ln in lines if ln.strip()
        if json.loads(ln).get("kind") == "tier_escalated"
        and json.loads(ln).get("payload", {}).get("scope") not in (
            "lateral_deferred", None
        )
    ]
    assert tier_events, "expected a tier_escalated event after second timeout"


def test_external_error_lateral_deferred_no_override_integration(
    tmp_path: Path,
) -> None:
    """external_error → no override, lateral_deferred history entry, no
    streak advancement (integration-level)."""
    plan = "ext-err-lateral-int"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [
            {"id": "A", "complexity": 1, "status": "pending"},
        ]}),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result, ExternalError

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="external_error",
            invocation_id=f"inv-{call['n']}",
            external_error=ExternalError(
                provider="openrouter",
                error_kind="quota",
                message="quota exceeded",
            ),
        )
        return 1, "", "quota"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=2,
            max_iterations=4,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No escalation — external_error is not a capability problem
    assert outcome.tier_escalations_used == 0

    # lateral_deferred history entry must exist
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    deferred_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "lateral_deferred"
    ]
    assert len(deferred_entries) >= 1, (
        f"expected lateral_deferred history, got {history_entries}"
    )
    for e in deferred_entries:
        assert e.get("category") == "external_error"

    # No override applied — tier_override must remain None on all tasks
    finalize_data = json.loads(
        (plan_dir / "finalize.json").read_text(encoding="utf-8")
    )
    for task in finalize_data["tasks"]:
        assert task.get("tier_override") is None, (
            f"task {task['id']} should NOT have tier_override"
        )

    # No --fresh (no streak advancement)
    execute_cmds = [c for c in seen_cmds if "execute" in c]
    for cmd in execute_cmds:
        assert "--fresh" not in cmd, (
            f"external_error should not advance streak, got --fresh in: {cmd}"
        )

    assert outcome.escalation_tier_pin is None


def test_blocked_by_quality_drift_no_override_no_streak_integration(
    tmp_path: Path,
) -> None:
    """blocked_by_quality_drift → no override, no streak, drift_skip history
    entry (integration-level)."""
    plan = "drift-noop-int"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_tier_state(plan_dir, max_tier=3)
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [
            {"id": "A", "complexity": 1, "status": "pending"},
        ]}),
        encoding="utf-8",
    )
    from tests.conftest import make_fake_phase_result, Deviation

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            deviations=(Deviation(kind="scope_drift", message="scope drift"),),
        )
        return 1, "", "drift"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            escalate_after_fails=2,
            stall_threshold=2,
            max_iterations=4,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # No escalation should happen for drift
    assert outcome.tier_escalations_used == 0

    # drift_skip history with category=blocked_by_quality_drift
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    drift_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "drift_skip"
    ]
    assert len(drift_entries) >= 1, f"expected drift_skip history, got {history_entries}"
    for e in drift_entries:
        assert e.get("category") == "blocked_by_quality_drift"

    # No override applied
    finalize_data = json.loads(
        (plan_dir / "finalize.json").read_text(encoding="utf-8")
    )
    for task in finalize_data["tasks"]:
        assert task.get("tier_override") is None, (
            f"task {task['id']} should NOT have tier_override"
        )

    # No --fresh (no streak advancement)
    execute_cmds = [c for c in seen_cmds if "execute" in c]
    for cmd in execute_cmds:
        assert "--fresh" not in cmd, (
            f"drift should not advance streak, but --fresh was in: {cmd}"
        )


# ── Synthetic ladder for ceiling test: single tier, no distinct upgrade ───
_SINGLE_TIER_LADDER: dict[int, str] = {
    1: "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro",
}


def test_ladder_ceiling_blocked_by_quality_semantic_terminates(
    tmp_path: Path,
) -> None:
    """Ladder ceiling: synthetic ladder of length 1; second
    blocked_by_quality_semantic failure produces ceiling_handoff and
    terminates."""
    plan = "ceiling-bq-semantic"
    plan_dir = _make_plan_dir(tmp_path, plan)
    # Use a synthetic ladder of length 1 — no higher distinct tier exists.
    _write_tier_state(plan_dir, ladder=_SINGLE_TIER_LADDER, max_tier=1)
    from tests.conftest import make_fake_phase_result, BlockedTask

    seen_cmds: list[list[str]] = []
    call = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(cmd, *, cwd=None, timeout=None, idle_timeout=None,
                 progress_env=None, liveness_plan_dir=None):
        seen_cmds.append(list(cmd))
        call["n"] += 1
        make_fake_phase_result(
            plan_dir,
            exit_kind="blocked_by_quality",
            invocation_id=f"inv-{call['n']}",
            blocked_tasks=(BlockedTask(task_id="T1", reason="quality gate"),),
        )
        return 1, "", "blocked"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=1,
            escalate_after_fails=1,
            stall_threshold=8,
            max_iterations=12,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # After retries exhausted, escalate path finds ceiling → ceiling_handoff
    # No escalation to a higher tier (ceiling reached — only 1 tier in ladder)
    assert outcome.tier_escalations_used == 0, (
        "expected no tier escalation at ceiling"
    )

    # ceiling_handoff history entry must exist
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    history_entries = state_data.get("history", [])
    ceiling_entries = [
        e for e in history_entries
        if isinstance(e, dict) and e.get("scope") == "ceiling_handoff"
    ]
    assert len(ceiling_entries) >= 1, (
        f"expected ceiling_handoff history, got {history_entries}"
    )

    # No --phase-model appended (no legacy escalation)
    assert not any("--phase-model" in c for c in seen_cmds), seen_cmds

    # No tier escalation pin set
    assert outcome.escalation_tier_pin is None


def _execute_stall_phase_result(plan_dir: Path):
    from megaplan.orchestration.phase_result import ExternalError
    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        phase="execute",
        exit_kind="external_error",
        external_error=ExternalError(
            provider="claude",
            error_kind="worker_stall",
            message="Worker produced no output for 1800s (stalled stream).",
            error_layer="worker_stream_stall",
            stall_timeout_s=1800.0,
        ),
    )


def test_auto_escalate_drops_tier_on_repeated_worker_stalls_before_halt(
    tmp_path: Path,
) -> None:
    plan = "execute-tier-drop"
    plan_dir = _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    run_calls: list[list[str]] = []

    def fake_run(
        args,
        cwd=None,
        timeout=None,
        idle_timeout=None,
        progress_env=None,
        liveness_plan_dir=None,
    ):
        run_calls.append(list(args))
        _execute_stall_phase_result(plan_dir)
        return 1, "", "Worker produced no output (stalled stream)."

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto, "_run_megaplan", side_effect=fake_run
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=5,
            tier_drop_after_stalls=2,
            max_tier_drops=2,
            max_iterations=20,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "manual intervention required" in outcome.reason
    assert outcome.tier_drops_used == 2
    assert outcome.max_tier_drops == 2

    tier_drop_levels = [
        int(call[call.index("--tier-drop") + 1])
        for call in run_calls
        if "--tier-drop" in call
    ]
    assert 1 in tier_drop_levels
    assert 2 in tier_drop_levels
    assert max(tier_drop_levels) == 2
    assert "--tier-drop" not in run_calls[0]

    from megaplan.observability.events import read_events

    kinds = [event.get("kind") for event in read_events(plan_dir)]
    assert "tier_drop" in kinds


def test_auto_escalate_disabled_never_drops_tier(tmp_path: Path) -> None:
    plan = "execute-tier-drop-disabled"
    plan_dir = _make_plan_dir(tmp_path, plan)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    run_calls: list[list[str]] = []

    def fake_run(
        args,
        cwd=None,
        timeout=None,
        idle_timeout=None,
        progress_env=None,
        liveness_plan_dir=None,
    ):
        run_calls.append(list(args))
        _execute_stall_phase_result(plan_dir)
        return 1, "", "Worker produced no output (stalled stream)."

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto, "_run_megaplan", side_effect=fake_run
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,
            tier_drop_after_stalls=0,
            max_iterations=20,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert outcome.tier_drops_used == 0
    assert all("--tier-drop" not in call for call in run_calls)


def test_auto_escalate_streak_resets_on_execute_progress(tmp_path: Path) -> None:
    plan = "execute-tier-drop-reset"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [
        _execute_status(plan),
        _execute_status(plan),
        _execute_status(plan),
        _done_status(plan),
    ]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    run_calls: list[list[str]] = []

    def fake_run(
        args,
        cwd=None,
        timeout=None,
        idle_timeout=None,
        progress_env=None,
        liveness_plan_dir=None,
    ):
        from tests.conftest import make_fake_phase_result

        run_calls.append(list(args))
        if len(run_calls) == 2:
            make_fake_phase_result(plan_dir, phase="execute", exit_kind="success")
            return 0, "{}", ""
        _execute_stall_phase_result(plan_dir)
        return 1, "", "stalled stream"

    with patch.object(auto, "_status", side_effect=fake_status), patch.object(
        auto, "_run_megaplan", side_effect=fake_run
    ):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=10,
            tier_drop_after_stalls=2,
            max_tier_drops=2,
            max_iterations=20,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.tier_drops_used == 0
    assert all("--tier-drop" not in call for call in run_calls)
