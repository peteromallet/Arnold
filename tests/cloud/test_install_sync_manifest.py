"""Tests for manifest-driven install sync (design §6 install_sync.py row)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import install_sync
from arnold_pipelines.megaplan.cloud.install_sync import (
    EditablePointerMismatchError,
    manifest_driven_sync,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RuntimeManifest,
)


def _make_manifest(
    tmp_path: Path,
    *,
    sync_policy: Any = "enabled",
    runtime_root: Path | None = None,
    venv_path: Path | None = None,
) -> dict[str, Any]:
    """A schema-valid runtime manifest whose epic points at *tmp_path* trees."""
    runtime_root = runtime_root or (tmp_path / "runtime")
    venv_path = venv_path or (tmp_path / "venv")
    return {
        "runtime_id": "runtime-manifest-sync-1",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 1,
        "epic_id": "epic-manifest-sync",
        "state": "active",
        "owner": "superfixer",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "basecommit123",
            "editable_install_path": str(tmp_path / "base"),
            "venv_path": str(tmp_path / "base" / "venv"),
        },
        "epic": {
            "branch": "fixer/epic-manifest-sync-20260807",
            "worktree_path": str(tmp_path / "worktree"),
            "venv_path": str(venv_path),
            "runtime_root": str(runtime_root),
            "expected_head": "epichead123",
            "repair_bin": str(venv_path / "bin" / "arnold-repair-loop"),
            "deps_lockfile": str(tmp_path / "base" / "uv.lock"),
        },
        "indirection": {
            "host_path": str(tmp_path / "worktree"),
            "container_path": "/workspace/epic-manifest-sync",
            "mount_table": [],
            "execution_namespace": "epic-manifest-sync-ns",
            "verified_head": "epichead123",
            "last_verified_at": "2026-08-07T00:00:00+00:00",
            "attestation": {
                "module_file": str(runtime_root / "arnold_pipelines" / "__init__.py"),
                "module_digest": "d41d8cd98f00b204e9800998ecf8427e",
                "mount_id": "0:42",
            },
        },
        "policy": {
            "policy_sha": "policy-sha-1",
            "model_policy_sha": "model-sha-1",
            "sync_policy": sync_policy,
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


def _write_venv_pointer(venv_path: Path, target: str) -> Path:
    """Write an editable-install .pth into a temp venv layout."""
    site_packages = venv_path / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    pth = site_packages / "__editable__.arnold_pipelines.pth"
    pth.write_text(f"{target}\n", encoding="utf-8")
    return pth


def test_manifest_driven_sync_skips_when_sync_policy_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("must not run any sync step when sync_policy disables sync")

    monkeypatch.setattr(install_sync, "apply_install_sync", boom)
    monkeypatch.setattr(install_sync.subprocess, "run", boom)

    for disabled in ("disabled", {"enabled": False}):
        manifest = _make_manifest(tmp_path, sync_policy=disabled)
        result = manifest_driven_sync(manifest)
        assert result == {"status": "skipped", "reason": "sync_policy_disabled"}


def test_manifest_driven_sync_dry_run_performs_no_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    venv_path = tmp_path / "venv"
    _write_venv_pointer(venv_path, str(runtime_root))

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry_run must not mutate")

    monkeypatch.setattr(install_sync, "apply_install_sync", boom)
    monkeypatch.setattr(install_sync.subprocess, "run", boom)

    manifest = _make_manifest(tmp_path, runtime_root=runtime_root, venv_path=venv_path)
    result = manifest_driven_sync(manifest, dry_run=True)

    assert result["status"] == "would_sync"
    assert result["dry_run"] is True
    assert result["runtime_root"] == str(runtime_root)
    assert result["venv_path"] == str(venv_path)
    assert result["branch"] == "fixer/epic-manifest-sync-20260807"
    assert result["expected_head"] == "epichead123"
    assert result["editable_pointer"]["pointer_present"] is True
    assert result["editable_pointer"]["matches_runtime"] is True
    assert result["command"][-2:] == ["-e", str(runtime_root)]


def test_manifest_driven_sync_dry_run_allows_venv_without_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry_run must not mutate")

    monkeypatch.setattr(install_sync, "apply_install_sync", boom)

    manifest = _make_manifest(tmp_path)
    result = manifest_driven_sync(manifest, dry_run=True)

    assert result["status"] == "would_sync"
    assert result["editable_pointer"]["pointer_present"] is False
    assert result["editable_pointer"]["matches_runtime"] is True


def test_manifest_driven_sync_editable_pointer_mismatch_is_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    venv_path = tmp_path / "venv"
    other_tree = tmp_path / "some-other-runtime"
    _write_venv_pointer(venv_path, str(other_tree))

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("pointer mismatch must abort before any sync attempt")

    monkeypatch.setattr(install_sync, "apply_install_sync", boom)

    manifest = _make_manifest(tmp_path, runtime_root=runtime_root, venv_path=venv_path)
    with pytest.raises(EditablePointerMismatchError) as exc_info:
        manifest_driven_sync(manifest)

    assert exc_info.value.code == "editable_pointer_mismatch"
    assert "editable_pointer_mismatch" in str(exc_info.value)
    assert exc_info.value.runtime_root == str(runtime_root)
    assert exc_info.value.pointer_target == str(other_tree)


def test_manifest_driven_sync_matching_pointer_proceeds_to_sync_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    venv_path = tmp_path / "venv"
    _write_venv_pointer(venv_path, str(runtime_root))

    calls: list[dict[str, Any]] = []

    def fake_apply(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"status": "applied", "returncode": 0}

    monkeypatch.setattr(install_sync, "apply_install_sync", fake_apply)

    manifest = _make_manifest(tmp_path, runtime_root=runtime_root, venv_path=venv_path)
    result = manifest_driven_sync(manifest)

    assert result == {"status": "applied", "returncode": 0}
    assert len(calls) == 1
    assert Path(calls[0]["source_root"]).resolve() == runtime_root.resolve()
    assert calls[0]["python_executable"] == str(venv_path / "bin" / "python")
    assert calls[0]["incident_id"] == "epic-manifest-sync"


def test_manifest_driven_sync_accepts_runtime_manifest_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    venv_path = tmp_path / "venv"
    _write_venv_pointer(venv_path, str(runtime_root))

    def fake_apply(**kwargs: Any) -> dict[str, Any]:
        return {"status": "applied"}

    monkeypatch.setattr(install_sync, "apply_install_sync", fake_apply)

    manifest_obj = RuntimeManifest.from_dict(
        _make_manifest(tmp_path, runtime_root=runtime_root, venv_path=venv_path)
    )
    result = manifest_driven_sync(manifest_obj)

    assert result == {"status": "applied"}
