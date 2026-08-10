from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arnold_pipelines.megaplan.cloud import liveness_lease as ll
from arnold_pipelines.megaplan.cloud import status_snapshot as ss


def _marker(marker_dir: Path, session: str = "run") -> dict:
    marker_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "session": session,
        "workspace": f"/workspace/{session}",
        "remote_spec": f"/workspace/{session}/chain.yaml",
        "run_kind": "chain",
        "identity_digest": "abc123",
        "started_at": "2026-08-03T17:00:00Z",
        "run_id": str(uuid.uuid4()),
    }
    (marker_dir / f"{session}.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_publisher_and_observer_round_trip(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher(
        "run", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    marker = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    observed = ll.observe_liveness_lease(marker, marker_dir=tmp_path)
    assert observed["state"] == "live"
    assert observed["live"] is True
    assert observed["runner_container_id"]
    assert observed["run_id"] == marker["run_id"]
    assert observed["attempt_id"]
    assert observed["incarnation_id"]
    claimed = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert claimed["attempt_id"] == observed["attempt_id"]
    assert claimed["incarnation_id"] == observed["incarnation_id"]
    assert claimed["pid"] == os.getpid()
    assert claimed["process_start_identity"]


def test_status_uses_remote_lease_when_local_namespace_probe_misses(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher(
        "run", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    marker = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    result = ss._safe_liveness(
        lambda _marker: {"tmux": False, "process": False},
        marker,
        marker_dir=tmp_path,
    )
    assert result["process"] is True
    assert result["state"] == "remote_live"
    assert result["source"] == "runner_lease"


def test_marker_rebind_invalidates_old_lease(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher(
        "run", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    marker = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    changed = dict(marker)
    changed["started_at"] = "2026-08-03T18:00:00Z"
    observed = ll.observe_liveness_lease(changed, marker_dir=tmp_path)
    assert observed["state"] == "degraded"
    assert observed["live"] is False


def test_tampered_lease_is_degraded(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher(
        "run", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    path = ll.lease_path("run", marker_dir=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["target_pid"] = 999999
    path.write_text(json.dumps(payload), encoding="utf-8")
    observed = ll.observe_liveness_lease(marker, marker_dir=tmp_path)
    assert observed["state"] == "degraded"
    assert observed["live"] is False


def test_expired_lease_is_not_liveness(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher(
        "run", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    marker = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    future = datetime.now(timezone.utc) + timedelta(minutes=2)
    observed = ll.observe_liveness_lease(marker, marker_dir=tmp_path, now=future)
    assert observed["state"] == "expired"
    assert observed["live"] is False


def test_bare_foreign_pid_and_fresh_activity_never_establish_liveness(tmp_path: Path):
    plan_state = {
        "active_step": {
            "worker_pid": 999999,
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    result = ss._augment_liveness_with_plan_state(
        {"tmux": False, "process": False, "state": "unknown"},
        chain_health={"plan_has_live_activity": True},
        plan_state=plan_state,
    )
    assert result["process"] is False


def test_bare_marker_pid_cannot_manufacture_local_liveness(monkeypatch):
    monkeypatch.setattr(ss, "_pid_is_live", lambda _pid: True)
    monkeypatch.setattr(
        ss.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    result = ss.default_liveness_probe(
        {"session": "foreign", "pid": os.getpid(), "workspace": "/not-present"}
    )
    assert result == {"tmux": False, "process": False}


def test_restart_rotates_attempt_and_incarnation_under_one_run(tmp_path: Path) -> None:
    marker = _marker(tmp_path)
    first = ll.LivenessLeasePublisher("run", marker_dir=tmp_path)
    first.publish_once()
    first_observed = ll.observe_liveness_lease(
        json.loads((tmp_path / "run.json").read_text()), marker_dir=tmp_path
    )
    first.close()

    second = ll.LivenessLeasePublisher("run", marker_dir=tmp_path)
    second.publish_once()
    second_marker = json.loads((tmp_path / "run.json").read_text())
    second_observed = ll.observe_liveness_lease(second_marker, marker_dir=tmp_path)

    assert second_observed["run_id"] == marker["run_id"]
    assert second_observed["attempt_id"] != first_observed["attempt_id"]
    assert second_observed["incarnation_id"] != first_observed["incarnation_id"]
    second.close()


def test_competing_publisher_is_fenced_and_closed_owner_cannot_resurrect(
    tmp_path: Path,
) -> None:
    _marker(tmp_path)
    owner = ll.LivenessLeasePublisher("run", marker_dir=tmp_path)
    owner.publish_once()
    contender = ll.LivenessLeasePublisher("run", marker_dir=tmp_path)

    try:
        contender.publish_once()
    except RuntimeError as exc:
        assert "another liveness publisher" in str(exc)
    else:  # pragma: no cover - safety assertion
        raise AssertionError("competing publisher acquired the owner fence")

    owner.close()
    contender.publish_once()
    contender.close()
    try:
        owner.publish_once()
    except RuntimeError as exc:
        assert "cannot be resurrected" in str(exc)
    else:  # pragma: no cover - safety assertion
        raise AssertionError("closed publisher was resurrected")


def test_process_reuse_stops_renewal(tmp_path: Path, monkeypatch) -> None:
    _marker(tmp_path)
    original = ll._proc_start_identity
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path)
    publisher.publish_once()
    monkeypatch.setattr(
        ll,
        "_proc_start_identity",
        lambda pid: "reused-process" if pid == publisher.target_pid else original(pid),
    )

    try:
        publisher.publish_once()
    except RuntimeError as exc:
        assert "no longer live" in str(exc)
    else:  # pragma: no cover - safety assertion
        raise AssertionError("PID reuse renewed the old incarnation")
    publisher.close()


def test_lifecycle_terminalizes_on_cancellation(tmp_path: Path, monkeypatch) -> None:
    marker = _marker(tmp_path)
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "run")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))

    try:
        with ll.managed_runner_lifecycle():
            live_marker = json.loads((tmp_path / "run.json").read_text())
            assert (
                ll.observe_liveness_lease(live_marker, marker_dir=tmp_path)["state"]
                == "live"
            )
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass

    stopped_marker = json.loads((tmp_path / "run.json").read_text())
    stopped = ll.observe_liveness_lease(stopped_marker, marker_dir=tmp_path)
    assert stopped["state"] == "expired"
    assert stopped["live"] is False
    assert stopped_marker["run_id"] == marker["run_id"]


def test_incomplete_managed_marker_fails_safe_without_lease(
    tmp_path: Path, monkeypatch
) -> None:
    marker = _marker(tmp_path)
    marker.pop("run_id")
    (tmp_path / "run.json").write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "run")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))

    with ll.managed_runner_lifecycle() as publisher:
        assert publisher is None

    assert ll.observe_liveness_lease(marker, marker_dir=tmp_path)["state"] == "unknown"


def test_child_inheriting_exact_live_owner_never_starts_competing_publisher(
    tmp_path: Path, monkeypatch
) -> None:
    _marker(tmp_path)
    owner_pid = os.getpid() + 1000
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "run")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(tmp_path))
    monkeypatch.setenv(ll.OWNER_PID_ENV, str(owner_pid))
    monkeypatch.setenv(ll.OWNER_START_ENV, "boot:123")
    monkeypatch.setattr(
        ll,
        "_proc_start_identity",
        lambda pid: "boot:123" if pid == owner_pid else "child:456",
    )
    monkeypatch.setattr(ll, "_process_is_runnable", lambda pid: pid == owner_pid)

    assert ll.start_from_environment() is None
    assert not ll.lease_path("run", marker_dir=tmp_path).exists()
