from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._core.phase_runtime import (
    WORKER_DEAD,
    WORKER_LIVE,
    WORKER_UNKNOWN,
    current_runner_incarnation,
    current_runner_lease_binding,
    observe_active_step_worker,
)
from arnold_pipelines.megaplan._core.state import set_active_step
from arnold_pipelines.megaplan.cloud.liveness_lease import LivenessLeasePublisher


def _marker(marker_dir: Path, session: str) -> None:
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / f"{session}.json").write_text(
        json.dumps(
            {
                "session": session,
                "workspace": "/workspace/demo",
                "remote_spec": "/workspace/demo/chain.yaml",
                "run_kind": "chain",
                "run_id": "run-demo",
                "identity_digest": "sha256:test",
                "started_at": "2026-08-03T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def _foreign_active(binding: dict) -> dict:
    return {
        "phase": "finalize",
        "run_id": "run-1",
        "worker_pid": 999_999,
        "runner_incarnation": {
            "schema": "arnold.megaplan.runner_incarnation.v1",
            "host_id": "foreign-container",
            "pid_namespace_id": "pid:[foreign]",
            "worker_pid": 999_999,
            "worker_process_start_identity": "boot:100",
        },
        "runner_lease": binding,
        "orphan_fence": {"run_id": "run-1", "invocation_id": "inv-1"},
    }


def test_foreign_pid_miss_with_fresh_exact_lease_is_live(
    tmp_path: Path, monkeypatch
) -> None:
    session = "demo"
    _marker(tmp_path, session)
    publisher = LivenessLeasePublisher(session, marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", session)
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    binding = current_runner_lease_binding()
    assert binding is not None

    observed = observe_active_step_worker(_foreign_active(binding))

    assert observed.state == WORKER_LIVE
    assert "exact runner lease" in observed.reason


def test_set_active_step_persists_incarnation_lease_and_occurrence_fence(
    tmp_path: Path, monkeypatch
) -> None:
    session = "demo"
    _marker(tmp_path, session)
    publisher = LivenessLeasePublisher(session, marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", session)
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    state = {"history": [], "sessions": {}, "meta": {}}

    run_id = set_active_step(
        state, step="finalize", agent="codex", mode="persistent"
    )

    active = state["active_step"]
    assert active["runner_incarnation"]["worker_process_start_identity"]
    assert active["runner_lease"]["lease_id"] == publisher.lease_id
    assert active["runner_lease"]["runner_fence"] == publisher.runner_fence
    assert active["orphan_fence"] == {
        "run_id": run_id,
        "invocation_id": state["meta"]["current_invocation_id"],
    }


def test_exact_foreign_lease_expiry_proves_stopped_runner(
    tmp_path: Path, monkeypatch
) -> None:
    session = "demo"
    _marker(tmp_path, session)
    publisher = LivenessLeasePublisher(
        session, marker_dir=tmp_path, target_pid=os.getpid(), ttl_s=1
    )
    publisher.publish_once()
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", session)
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    binding = current_runner_lease_binding()
    assert binding is not None

    observed = observe_active_step_worker(
        _foreign_active(binding),
        now=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    assert observed.state == WORKER_DEAD
    assert "expired" in observed.reason


def test_runner_replacement_lease_fences_old_active_step(
    tmp_path: Path, monkeypatch
) -> None:
    session = "demo"
    _marker(tmp_path, session)
    first = LivenessLeasePublisher(session, marker_dir=tmp_path, target_pid=os.getpid())
    first.publish_once()
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", session)
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    old_binding = current_runner_lease_binding()
    assert old_binding is not None
    first.close()
    replacement = LivenessLeasePublisher(session, marker_dir=tmp_path, target_pid=os.getpid())
    replacement.publish_once()
    # A closed superseded publisher cannot race a final renewal; the monotonic
    # fence still proves that the old active-step binding was replaced.
    with pytest.raises(RuntimeError, match="cannot be resurrected"):
        first.publish_once()

    observed = observe_active_step_worker(_foreign_active(old_binding))

    assert observed.state == WORKER_DEAD
    assert "replaced" in observed.reason


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="requires Linux /proc state")
def test_sigstop_target_stops_renewal_and_exact_lease_expires(
    tmp_path: Path, monkeypatch
) -> None:
    session = "demo"
    _marker(tmp_path, session)
    child = subprocess.Popen(["sleep", "30"])
    publisher = LivenessLeasePublisher(
        session,
        marker_dir=tmp_path,
        target_pid=child.pid,
        interval_s=0.2,
        ttl_s=0.5,
    ).start()
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", session)
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    binding = current_runner_lease_binding()
    assert binding is not None
    try:
        os.kill(child.pid, signal.SIGSTOP)
        time.sleep(0.8)
        observed = observe_active_step_worker(_foreign_active(binding))
        assert observed.state == WORKER_DEAD
    finally:
        os.kill(child.pid, signal.SIGCONT)
        child.terminate()
        child.wait(timeout=5)
        publisher.close()


def test_pid_reuse_is_dead_even_when_numeric_pid_is_alive(monkeypatch) -> None:
    incarnation = current_runner_incarnation()
    active = {
        "phase": "execute",
        "worker_pid": os.getpid(),
        "runner_incarnation": {
            **incarnation,
            "worker_process_start_identity": "different-process-start",
        },
    }

    assert observe_active_step_worker(active).state == WORKER_DEAD


def test_foreign_pid_without_bound_lease_is_unknown() -> None:
    active = _foreign_active({})
    active.pop("runner_lease")

    assert observe_active_step_worker(active).state == WORKER_UNKNOWN


def test_artifact_recovery_refuses_unknown_custody() -> None:
    active = _foreign_active({})
    active.pop("runner_lease")

    allowed, snapshot = auto._active_step_recovery_snapshot(
        {"active_step": active},
        expected_phase="finalize",
    )

    assert allowed is False
    assert snapshot == active


def test_artifact_recovery_accepts_only_proven_dead_local_custody() -> None:
    incarnation = current_runner_incarnation()
    active = {
        "phase": "execute",
        "worker_pid": os.getpid(),
        "runner_incarnation": {
            **incarnation,
            "worker_process_start_identity": "different-process-start",
        },
    }

    allowed, snapshot = auto._active_step_recovery_snapshot(
        {"active_step": active},
        expected_phase="execute",
    )

    assert allowed is True
    assert snapshot == active


def test_orphan_clear_is_exact_cas_under_concurrent_resume(tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    active = {
        "phase": "finalize",
        "run_id": "run-1",
        "worker_pid": 999_999,
        "runner_incarnation": {"pid_namespace_id": "pid:[foreign]"},
        "orphan_fence": {"run_id": "run-1", "invocation_id": "inv-1"},
    }
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "gated", "active_step": active}),
        encoding="utf-8",
    )

    def clear() -> bool:
        return auto._clear_orphaned_active_step(
            plan_dir,
            "finalize",
            expected_active_step=active,
            quarantine=False,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: clear(), range(2)))

    assert sorted(outcomes) == [False, True]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "active_step" not in state


def test_completed_phase_cleanup_cannot_clear_replacement_invocation(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    replacement = {
        "phase": "finalize",
        "run_id": "run-new",
        "invocation_id": "inv-new",
        "worker_pid": os.getpid(),
    }
    (plan_dir / "state.json").write_text(
        json.dumps(
            {"name": "demo", "current_state": "gated", "active_step": replacement}
        ),
        encoding="utf-8",
    )

    cleared = auto._clear_completed_active_step(
        plan_dir,
        "finalize",
        SimpleNamespace(phase="finalize", invocation_id="inv-old"),
    )

    assert cleared is False
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["active_step"] == replacement


def test_completed_phase_cleanup_clears_exact_result_occurrence(tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    active = {
        "phase": "finalize",
        "run_id": "run-1",
        "invocation_id": "inv-1",
        "worker_pid": os.getpid(),
    }
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "gated", "active_step": active}),
        encoding="utf-8",
    )

    cleared = auto._clear_completed_active_step(
        plan_dir,
        "finalize",
        SimpleNamespace(phase="finalize", invocation_id="inv-1"),
    )

    assert cleared is True
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "active_step" not in persisted


def test_failed_phase_cleanup_persists_and_validates_repair_identity_seed(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    active = {
        "phase": "finalize",
        "run_id": "run-1",
        "invocation_id": "inv-1",
        "worker_pid": os.getpid(),
        "orphan_fence": {"run_id": "run-1", "invocation_id": "inv-1"},
    }
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "gated",
                "active_step": active,
                "meta": {"current_invocation_id": "inv-1"},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            {
                "schema": "megaplan.phase_result",
                "phase": "finalize",
                "invocation_id": "inv-1",
                "exit_kind": "internal_error",
            }
        ),
        encoding="utf-8",
    )

    result = SimpleNamespace(
        phase="finalize", invocation_id="inv-1", exit_kind="internal_error"
    )
    assert auto._clear_completed_active_step(plan_dir, "finalize", result)

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "active_step" not in persisted
    seed = persisted["meta"]["repair_identity_seed"]
    assert seed["schema"] == "megaplan.repair_identity_seed.v1"
    assert seed["_non_authoritative"] is True
    assert seed["active_step"] == active
    assert seed["active_step_cas"].startswith("sha256:")
    assert auto._active_step_from_repair_identity_seed(
        plan_dir, persisted, phase="finalize"
    )[0] == active

    (plan_dir / "phase_result.json").write_text(
        json.dumps({"phase": "finalize", "invocation_id": "different"}),
        encoding="utf-8",
    )
    assert auto._active_step_from_repair_identity_seed(
        plan_dir,
        json.loads((plan_dir / "state.json").read_text(encoding="utf-8")),
        phase="finalize",
    ) is None


def test_unknown_liveness_forbids_auto_redispatch(tmp_path: Path, monkeypatch) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    active = {
        "phase": "finalize",
        "run_id": "run-1",
        "worker_pid": 999_999,
        "runner_incarnation": {
            "host_id": "foreign",
            "pid_namespace_id": "pid:[foreign]",
            "worker_process_start_identity": "boot:1",
        },
    }
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo", "current_state": "gated", "active_step": active}),
        encoding="utf-8",
    )
    calls = 0

    def status(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "state": "gated",
                "next_step": "finalize",
                "valid_next": ["finalize"],
                "active_step": {**active, "recommended_action": "resume_or_recover"},
                "progress": {},
            }
        return {"state": "done", "next_step": None, "valid_next": [], "progress": {}}

    dispatched: list[list[str]] = []
    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda *args, **kwargs: plan_dir)
    monkeypatch.setattr(auto, "_status", status)
    monkeypatch.setattr(
        auto,
        "_run_planning_phase",
        lambda args, **kwargs: (dispatched.append(list(args)) or (0, "", "")),
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto, "_publish_done_plan", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, poll_sleep=0)

    assert outcome.status == "done"
    assert dispatched == []
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["active_step"]["run_id"] == "run-1"
