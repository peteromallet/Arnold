from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

from megaplan.worktrees import (
    DIFF_FLAGS,
    PatchCaptureError,
    capture_patch_bundle,
    custody_paths,
    make_task_identity,
    read_registry_entries,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "core.filemode", "true")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    (repo / "old-name.txt").write_text("rename me\n", encoding="utf-8")
    (repo / "script.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (repo / "blob.bin").write_bytes(b"\x00base-binary\x00")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")


def _status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain=v1").stdout


def _cached_names(repo: Path) -> str:
    return _git(repo, "diff", "--cached", "--name-only").stdout


def test_capture_patch_bundle_uses_temp_index_for_tracked_untracked_rename_binary_and_mode(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "task-worktree"
    project_dir = tmp_path / "coordinator"
    _init_repo(repo)

    (repo / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")
    (repo / "old-name.txt").rename(repo / "new-name.txt")
    (repo / "untracked.txt").write_text("new file\n", encoding="utf-8")
    (repo / "blob.bin").write_bytes(b"\x00changed-binary\x00\xff")
    script = repo / "script.sh"
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    status_before = _status(repo)
    cached_before = _cached_names(repo)

    result = capture_patch_bundle(
        project_dir,
        "run-7",
        "T7",
        repo,
        secret_scan_mode="local_only",
    )

    assert _status(repo) == status_before
    assert _cached_names(repo) == cached_before == ""
    patch = result.patch_path.read_text(encoding="utf-8", errors="replace")
    assert "diff --git a/tracked.txt b/tracked.txt" in patch
    assert "+changed" in patch
    assert "diff --git a/untracked.txt b/untracked.txt" in patch
    assert "rename from old-name.txt" in patch
    assert "rename to new-name.txt" in patch
    assert "diff --git a/blob.bin b/blob.bin" in patch
    assert "GIT binary patch" in patch
    assert "old mode 100644" in patch
    assert "new mode 100755" in patch

    assert set(result.changed_paths) == {
        "blob.bin",
        "new-name.txt",
        "script.sh",
        "tracked.txt",
        "untracked.txt",
    }
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "run-7"
    assert manifest["task_id"] == "T7"
    identity = make_task_identity("T7")
    assert manifest["task_key"] == identity.task_key
    assert manifest["identity"] == identity.registry_identity()
    assert manifest["trailers"] == identity.trailer_fields()
    assert manifest["patch"]["sha256"] == result.patch_sha256
    assert manifest["patch"]["size_bytes"] == result.patch_size_bytes
    assert manifest["secret_scan"]["policy"] == "gitleaks"
    assert manifest["secret_scan"]["mode"] == "local_only"
    assert manifest["secret_scan"]["status"] == "skipped"
    assert manifest["secret_scan"]["exit_class"] == "skipped"
    assert manifest["secret_scan"]["explicit_local_only_opt_in"] is True
    assert "local_only" in manifest["secret_scan"]["redacted_reason"]
    assert manifest["git"]["temporary_index"] is True
    for flag in ["--cached", "--binary", "--full-index", "--find-renames", "--no-color", "--no-ext-diff"]:
        assert flag in manifest["git"]["diff_flags"]
        assert flag in DIFF_FLAGS
    registry_entries = read_registry_entries(project_dir, "run-7")
    assert [entry["entry_type"] for entry in registry_entries] == ["patch_captured"]
    assert registry_entries[0]["task_key"] == identity.task_key
    assert registry_entries[0]["payload"]["secret_scan"]["mode"] == "local_only"


def test_capture_patch_bundle_requires_explicit_secret_scan_mode(tmp_path: Path) -> None:
    repo = tmp_path / "task-worktree"
    _init_repo(repo)

    with pytest.raises(TypeError):
        capture_patch_bundle(tmp_path / "coordinator", "run-7", "T7", repo)  # type: ignore[call-arg]
    with pytest.raises(PatchCaptureError) as excinfo:
        capture_patch_bundle(
            tmp_path / "coordinator",
            "run-7",
            "T7",
            repo,
            secret_scan_mode="implicit",
        )
    assert excinfo.value.code == "invalid_secret_scan_mode"


def test_capture_patch_bundle_hardens_external_diff_color_and_textconv(tmp_path: Path) -> None:
    repo = tmp_path / "task-worktree"
    _init_repo(repo)
    (repo / ".gitattributes").write_text("*.txt diff=explode\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attributes")
    _git(repo, "config", "diff.external", "sh -c 'echo EXTERNAL_DIFF >&2; exit 2'")
    _git(repo, "config", "diff.explode.textconv", "sh -c 'echo TEXTCONV >&2; exit 3'")
    _git(repo, "config", "color.ui", "always")
    (repo / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")

    result = capture_patch_bundle(
        tmp_path / "coordinator",
        "run-7",
        "T7",
        repo,
        secret_scan_mode="local_only",
    )

    patch = result.patch_path.read_bytes()
    assert b"EXTERNAL_DIFF" not in patch
    assert b"TEXTCONV" not in patch
    assert b"\x1b[" not in patch
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert "--no-textconv" in manifest["git"]["diff_flags"]
    assert manifest["git"]["hardened_environment"]["GIT_EXTERNAL_DIFF"] == ""


def test_capture_patch_bundle_can_store_custody_inside_same_worktree_without_self_capture(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "task-worktree"
    _init_repo(repo)
    (repo / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")

    result = capture_patch_bundle(repo, "run-7", "T7", repo, secret_scan_mode="local_only")

    assert result.patch_path == custody_paths(repo).patch_payload("run-7", "T7")
    patch = result.patch_path.read_text(encoding="utf-8")
    assert ".megaplan/worktrees" not in patch
    assert _cached_names(repo) == ""
    assert "?? .megaplan/" in _status(repo)
