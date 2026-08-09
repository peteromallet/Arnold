"""Tests for scheduler manifest pin checks + proactive seam dispatch (design §6).

Covers ``runtime_pin_ok`` (expected_head/clean-tree verification against the
per-runtime manifest or explicit values), ``proactive_seam_dispatch`` (the
``arnold-repair-loop --mode=proactive`` dispatch-planning hook), and the
``superfixer_proactive`` handler registration/behavior.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RuntimeManifest,
)
from arnold_pipelines.megaplan.resident import scheduler as scheduler_module
from arnold_pipelines.megaplan.resident.scheduler import (
    proactive_seam_dispatch,
    runtime_pin_ok,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_git_repo(tmp_path: Path, name: str = "runtime") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("content\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def _write_manifest(path: Path, runtime_root: Path, expected_head: str) -> None:
    manifest = RuntimeManifest.from_dict(
        {
            "runtime_id": "runtime-sched-test",
            "schema": MANIFEST_SCHEMA_VERSION,
            "generation": 1,
            "epic_id": "epic-sched-test",
            "state": "active",
            "owner": "superfixer",
            "base": {
                "ref": "refs/heads/base/editable-install",
                "commit": "x" * 40,
                "editable_install_path": str(runtime_root),
                "venv_path": str(runtime_root / "venv"),
            },
            "epic": {
                "branch": "fixer/epic-sched-test",
                "worktree_path": str(runtime_root),
                "venv_path": str(runtime_root / "venv"),
                "runtime_root": str(runtime_root),
                "expected_head": expected_head,
                "repair_bin": str(runtime_root / "venv/bin/arnold-repair-loop"),
                "deps_lockfile": str(runtime_root / "uv.lock"),
            },
            "indirection": {
                "host_path": str(runtime_root),
                "container_path": "/workspace/sched-test",
                "mount_table": [],
                "execution_namespace": "sched-test-ns",
                "verified_head": expected_head,
                "last_verified_at": "2026-08-07T00:00:00+00:00",
                "attestation": {
                    "module_file": str(runtime_root / "arnold_pipelines/__init__.py"),
                    "module_digest": "d41d8cd98f00b204e9800998ecf8427e",
                    "mount_id": "0:42",
                },
            },
            "policy": {
                "policy_sha": "policy-sha-1",
                "model_policy_sha": "model-sha-1",
                "sync_policy": "push-on-promote",
            },
            "promotions": [],
            "timestamps": {
                "created": "2026-08-07T00:00:00+00:00",
                "updated": "2026-08-07T00:00:00+00:00",
                "closed": "",
            },
            "gc_policy": "closed-only",
            "commands": ["megaplan chain"],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")


# ── runtime_pin_ok ──────────────────────────────────────────────────────────


def test_runtime_pin_ok_no_pin_configured() -> None:
    assert runtime_pin_ok() == (True, "no_pin_configured")
    assert runtime_pin_ok(
        manifest_path=Path("/nonexistent/manifest.json")
    ) == (True, "no_pin_configured")


def test_runtime_pin_ok_matching_head_clean_tree(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest_path, repo, head)
    assert runtime_pin_ok(manifest_path=manifest_path) == (True, "ok")


def test_runtime_pin_ok_explicit_matching_values(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    assert runtime_pin_ok(expected_head=head, runtime_root=repo) == (True, "ok")


def test_runtime_pin_ok_head_mismatch(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path)
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest_path, repo, "0" * 40)
    ok, reason = runtime_pin_ok(manifest_path=manifest_path)
    assert ok is False
    assert "expected_head mismatch" in reason


def test_runtime_pin_ok_dirty_tree(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest_path, repo, head)
    (repo / "file.txt").write_text("modified\n", encoding="utf-8")
    ok, reason = runtime_pin_ok(manifest_path=manifest_path)
    assert ok is False
    assert "dirty" in reason


def test_runtime_pin_ok_present_invalid_manifest_fails_closed(
    tmp_path: Path,
) -> None:
    """A present-but-invalid manifest is a pin FAILURE, never no_pin_configured."""
    corrupt = tmp_path / "runtime-manifest.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    ok, reason = runtime_pin_ok(manifest_path=corrupt)
    assert ok is False
    assert "manifest_invalid:" in reason


def test_runtime_pin_ok_env_set_but_manifest_missing_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ARNOLD_RUNTIME_MANIFEST set but unreadable fails closed (the operator
    pointed at a manifest; absence is not an unpinned pass)."""
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(tmp_path / "missing.json"))
    ok, reason = runtime_pin_ok(manifest_path=tmp_path / "missing.json")
    assert ok is False
    assert "manifest_invalid:" in reason


def test_runtime_pin_ok_absent_manifest_without_env_is_no_pin_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    assert runtime_pin_ok(
        manifest_path=tmp_path / "no-such-manifest.json"
    ) == (True, "no_pin_configured")


def test_proactive_seam_dispatch_uses_manifest_repair_bin(tmp_path: Path) -> None:
    """When the manifest names epic.repair_bin, the dispatch command resolves
    the wrapper from the manifest, not __file__ (design line 191)."""
    repo = _init_git_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest_path, repo, head)
    record = proactive_seam_dispatch(
        session="sess-m",
        workspace=tmp_path / "ws",
        remote_spec=tmp_path / "ws" / "chain.yaml",
        manifest_path=manifest_path,
    )
    expected_bin = str(repo / "venv/bin/arnold-repair-loop")
    assert record["command"][0] == expected_bin
    assert record["repair_bin_source"] == "manifest"
    assert record["pin_ok"] is True


def test_proactive_seam_dispatch_falls_back_to_local_wrapper_without_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    ws = tmp_path / "ws"
    spec = ws / "chain.yaml"
    record = proactive_seam_dispatch(
        session="sess-f",
        workspace=ws,
        remote_spec=spec,
        manifest_path=tmp_path / "no-such-manifest.json",
    )
    expected_wrapper = (
        Path(scheduler_module.__file__).resolve().parents[1]
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    )
    assert record["command"][0] == str(expected_wrapper)
    assert record["repair_bin_source"] == "absent_manifest_fallback"
    assert record["pin_reason"] == "no_pin_configured"


# ── proactive_seam_dispatch ─────────────────────────────────────────────────


def test_proactive_seam_dispatch_command_and_dry_run(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    spec = ws / "chain.yaml"
    record = proactive_seam_dispatch(
        session="sess-1", workspace=ws, remote_spec=spec, dry_run=True
    )
    assert record["seam"] == "arnold-repair-loop"
    assert record["mode"] == "proactive"
    assert record["dry_run"] is True
    assert record["pin_ok"] is True
    assert record["pin_reason"] == "no_pin_configured"
    expected_wrapper = (
        Path(scheduler_module.__file__).resolve().parents[1]
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    )
    assert record["command"] == [
        str(expected_wrapper),
        "--mode=proactive",
        "sess-1",
        str(ws),
        str(spec),
    ]
    assert Path(record["command"][0]).is_file()


def test_proactive_seam_dispatch_without_dry_run_also_returns_record(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "ws"
    spec = ws / "chain.yaml"
    record = proactive_seam_dispatch(
        session="sess-2", workspace=ws, remote_spec=spec, dry_run=False
    )
    assert record["dry_run"] is False
    assert record["command"][1] == "--mode=proactive"
    assert record["command"][2] == "sess-2"


# ── superfixer_proactive handler ────────────────────────────────────────────


class _FakeStore:
    def __init__(self) -> None:
        self.updated: list[tuple[str, dict[str, Any]]] = []
        self.events: list[dict[str, Any]] = []
        self.created: list[dict[str, Any]] = []

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> None:
        self.updated.append((job_id, changes))

    def create_scheduled_job(
        self,
        job: Any,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self.created.append({"job": job, "idempotency_key": idempotency_key})

    def list_scheduled_jobs(
        self,
        *,
        conversation_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[Any]:
        return []

    def log_system_event(self, **fields: Any) -> None:
        self.events.append(fields)


def _job_payload(session: str = "sess-1") -> dict[str, Any]:
    # job_type uses a valid enum value: the handler is invoked directly here,
    # bypassing dispatch; payload carries the occurrence's seam inputs.
    return {
        "id": "job-1",
        "job_type": "heartbeat",
        "status": "pending",
        "payload": {
            "session": session,
            "workspace": "/tmp/ws",
            "remote_spec": "/tmp/ws/chain.yaml",
        },
        "scheduled_for": datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        "attempt_count": 0,
        "max_attempts": 3,
    }


def test_superfixer_proactive_handler_registered() -> None:
    handlers = scheduler_module.ResidentJobHandlers(
        store=None, config=None, cloud_backend=None
    )
    assert "superfixer_proactive" in handlers.handlers()


def test_superfixer_proactive_handler_plans_dispatch_and_stays_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeStore()
    handlers = scheduler_module.ResidentJobHandlers(
        store=fake, config=None, cloud_backend=None
    )
    # Genuinely absent manifest (no env, no file) -> no_pin_configured ->
    # dispatch planned.  The occurrence is recorded as PLANNED and re-armed
    # as a pending follow-up — never a terminal success from planning alone.
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.setattr(
        scheduler_module,
        "_runtime_manifest_path",
        lambda: tmp_path / "no-such-manifest.json",
    )
    # Planning alone is never terminal: the handler raises PlannedOutcome so
    # the worker does NOT mark the job fired (a plan is not a launch).
    with pytest.raises(scheduler_module.PlannedOutcome):
        asyncio.run(handlers.handle_superfixer_proactive(_job_payload()))
    assert fake.updated
    job_id, changes = fake.updated[0]
    assert job_id == "job-1"
    plan = changes["payload"]["seam_dispatch_plan"]
    assert plan["seam"] == "arnold-repair-loop"
    assert plan["mode"] == "proactive"
    assert plan["pin_ok"] is True
    assert plan["pin_reason"] == "no_pin_configured"
    assert plan["command"][2] == "sess-1"
    assert changes["payload"]["superfixer_occurrence_state"] == "planned"
    # The follow-up pending occurrence carries the dispatch plan (occurrence
    # stays pending until the actual launch is recorded).
    assert fake.created
    follow_up = fake.created[0]["job"]
    assert follow_up.job_type == "superfixer_proactive"
    assert follow_up.payload["superfixer_occurrence_state"] == "planned"
    assert follow_up.payload["seam_dispatch_plan"]["seam"] == "arnold-repair-loop"
    assert fake.events[0]["event_type"] == "resident_superfixer_proactive"


def test_superfixer_proactive_handler_fails_on_pin_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeStore()
    handlers = scheduler_module.ResidentJobHandlers(
        store=fake, config=None, cloud_backend=None
    )
    monkeypatch.setattr(
        scheduler_module,
        "runtime_pin_ok",
        lambda **kwargs: (
            False,
            "expected_head mismatch: tree /tmp/r is at abc, pin expects def",
        ),
    )
    with pytest.raises(ValueError, match="pin check failed"):
        asyncio.run(handlers.handle_superfixer_proactive(_job_payload()))
    assert fake.updated == []
    assert fake.created == []


def test_superfixer_proactive_handler_fails_closed_on_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A present-but-invalid manifest fails the occurrence through the pin
    check (manifest_invalid) instead of planning a dispatch."""
    fake = _FakeStore()
    handlers = scheduler_module.ResidentJobHandlers(
        store=fake, config=None, cloud_backend=None
    )
    corrupt = tmp_path / "runtime-manifest.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        scheduler_module,
        "_runtime_manifest_path",
        lambda: corrupt,
    )
    with pytest.raises(ValueError, match="manifest_invalid"):
        asyncio.run(handlers.handle_superfixer_proactive(_job_payload()))
    assert fake.updated == []
    assert fake.created == []


class _FakePlannedBackend:
    """Minimal ScheduledJobBackend recording fired/failed transitions."""

    def __init__(self) -> None:
        self.fired: list[str] = []
        self.failed: list[tuple[str, str]] = []

    async def claim_due_jobs(
        self, *, worker_id: str, now: datetime
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "job-plan",
                "job_type": "superfixer_proactive",
                "status": "pending",
                "payload": {},
            }
        ]

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        self.fired.append(job_id)

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        self.failed.append((job_id, error))
        return False


async def _plan_only_handler(_job_payload: dict[str, Any]) -> None:
    raise scheduler_module.PlannedOutcome("planned, not fired")


def test_worker_does_not_mark_planned_job_fired() -> None:
    """A PlannedOutcome handler result is neither fired nor failed."""
    backend = _FakePlannedBackend()
    worker = scheduler_module.ScheduledJobWorker(
        backend=backend,
        handlers={"superfixer_proactive": _plan_only_handler},
        worker_id="test-worker",
    )
    result = asyncio.run(worker.run_due_once())
    assert result.claimed == 1
    assert result.fired == 0
    assert result.retried == 0
    assert result.cancelled == 0
    assert backend.fired == []
    assert backend.failed == []
