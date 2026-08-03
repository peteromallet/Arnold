from __future__ import annotations

import json
import os
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
    }
    (marker_dir / f"{session}.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_publisher_and_observer_round_trip(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
    observed = ll.observe_liveness_lease(marker, marker_dir=tmp_path)
    assert observed["state"] == "live"
    assert observed["live"] is True
    assert observed["runner_container_id"]


def test_status_uses_remote_lease_when_local_namespace_probe_misses(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
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
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
    changed = dict(marker)
    changed["started_at"] = "2026-08-03T18:00:00Z"
    observed = ll.observe_liveness_lease(changed, marker_dir=tmp_path)
    assert observed["state"] == "degraded"
    assert observed["live"] is False


def test_tampered_lease_is_degraded(tmp_path: Path):
    marker = _marker(tmp_path)
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path, target_pid=os.getpid())
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
    publisher = ll.LivenessLeasePublisher("run", marker_dir=tmp_path, target_pid=os.getpid())
    publisher.publish_once()
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
