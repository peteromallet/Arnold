from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan._core.phase_runtime import _pid_namespace_id
from arnold_pipelines.megaplan._core.state import touch_active_step, write_plan_state


def _base_state(current_state: str) -> dict:
    return {
        "schema_version": 1,
        "current_state": current_state,
        "history": [],
        "meta": {},
        "sessions": {},
        "config": {},
    }


def _dead_local_execute_active(run_id: str = "execute-run") -> dict:
    """Build an execute active_step whose local worker is provably dead.

    The phase-handoff reconciler only pops active_step when the worker is
    observed dead in its own incarnation domain (host + PID namespace), so the
    fixture spawns a real process, lets it exit, and binds that PID.
    """
    proc = subprocess.run(
        ["/bin/true"],
        capture_output=True,
        check=True,
    )
    child = subprocess.Popen(["/bin/true"])
    dead_pid = child.pid
    child.wait()
    return {
        "phase": "execute",
        "run_id": run_id,
        "worker_pid": dead_pid,
        "runner_incarnation": {
            "schema": "arnold.megaplan.runner_incarnation.v1",
            "host_id": socket.gethostname(),
            "pid_namespace_id": _pid_namespace_id(),
            "worker_pid": dead_pid,
        },
    }


def test_execute_success_atomically_arms_recoverable_review_handoff(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text('{"output":"done"}', encoding="utf-8")
    state = _base_state("executed")
    state["active_step"] = _dead_local_execute_active()
    state["history"].append({"step": "execute", "result": "success"})

    persisted = write_plan_state(plan_dir, mode="replace", state=state)
    on_disk = json.loads((plan_dir / "state.json").read_text())

    assert persisted == on_disk
    assert "active_step" not in on_disk
    handoff = on_disk["pending_phase_handoff"]
    assert handoff["from_phase"] == "execute"
    assert handoff["to_phase"] == "review"
    assert handoff["status"] == "recovery_required"
    assert handoff["recovery_action"] == "resume_review"


def test_review_claim_and_crossing_are_durable_state_transitions(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text('{"output":"done"}', encoding="utf-8")
    state = _base_state("executed")
    state["history"].append({"step": "execute", "result": "success"})
    write_plan_state(plan_dir, mode="replace", state=state)

    claimed = write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={
            "active_step": {
                "phase": "review",
                "run_id": "review-run",
                "worker_pid": 123,
            }
        },
    )
    assert claimed["pending_phase_handoff"]["status"] == "claimed"
    assert claimed["pending_phase_handoff"]["claim_run_id"] == "review-run"

    crossed_state = dict(claimed)
    crossed_state["current_state"] = "done"
    crossed_state["history"] = [
        *claimed["history"],
        {"step": "review", "result": "success"},
    ]
    crossed = write_plan_state(plan_dir, mode="replace", state=crossed_state)

    assert "pending_phase_handoff" not in crossed
    receipt = crossed["meta"]["phase_handoff_receipts"][-1]
    assert receipt["status"] == "crossed"
    assert receipt["crossed_to_state"] == "done"


def test_heartbeat_cache_write_preserves_live_execute_custody(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A liveness projection cannot reinterpret an already-persisted lifecycle."""
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    run_id = "live-execute"
    state = _base_state("executed")
    state["active_step"] = {
        "phase": "execute",
        "run_id": run_id,
        "worker_pid": os.getpid(),
        "last_activity_at": "2026-01-01T00:00:00+00:00",
    }
    # Seed the legacy shape directly: calling the lifecycle-authoritative
    # replace API would intentionally reconcile it before this regression can
    # exercise the cache-only writer.
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("MEGAPLAN_HEARTBEAT_PERSIST_INTERVAL_S", "0")

    touch_active_step(plan_dir, run_id=run_id, kind="worker-output")

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["active_step"]["run_id"] == run_id
    assert persisted["active_step"]["phase"] == "execute"
    assert persisted["active_step"]["last_activity_kind"] == "worker-output"
    assert "pending_phase_handoff" not in persisted


def test_heartbeat_cache_write_does_not_advance_existing_handoff(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    run_id = "live-review"
    state = _base_state("executed")
    state["active_step"] = {
        "phase": "review",
        "run_id": run_id,
        "worker_pid": os.getpid(),
    }
    handoff = {
        "handoff_id": "sha256:existing",
        "from_phase": "execute",
        "to_phase": "review",
        "status": "pending",
        "source_history_length": 0,
    }
    state["pending_phase_handoff"] = handoff
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("MEGAPLAN_HEARTBEAT_PERSIST_INTERVAL_S", "0")

    touch_active_step(plan_dir, run_id=run_id, kind="worker-output")

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["pending_phase_handoff"] == handoff
    assert persisted["active_step"]["phase"] == "review"
    assert persisted["active_step"]["last_activity_kind"] == "worker-output"


def test_mismatched_heartbeat_cannot_reconcile_lifecycle(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state = _base_state("executed")
    state["active_step"] = {
        "phase": "execute",
        "run_id": "current-run",
        "worker_pid": os.getpid(),
    }
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    touch_active_step(plan_dir, run_id="stale-run", kind="worker-output")

    assert state_path.read_bytes() == before


def test_authoritative_execute_complete_transition_still_arms_recovery(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text('{"output":"done"}', encoding="utf-8")
    state = _base_state("executing")
    state["active_step"] = _dead_local_execute_active()
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    persisted = write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": "executed"},
    )

    assert "active_step" not in persisted
    assert persisted["pending_phase_handoff"]["status"] == "recovery_required"
    assert (
        persisted["pending_phase_handoff"]["recovery_reason"]
        == "execute_complete_with_proven_dead_execute_custody"
    )
