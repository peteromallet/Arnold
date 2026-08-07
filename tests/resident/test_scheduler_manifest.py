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

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> None:
        self.updated.append((job_id, changes))

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


def test_superfixer_proactive_handler_plans_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeStore()
    handlers = scheduler_module.ResidentJobHandlers(
        store=fake, config=None, cloud_backend=None
    )
    # No manifest at the configured path -> no_pin_configured -> dispatch planned.
    monkeypatch.setenv(
        "ARNOLD_RUNTIME_MANIFEST", str(tmp_path / "no-such-manifest.json")
    )
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
