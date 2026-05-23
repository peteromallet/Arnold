from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import megaplan.worktrees.patches as patches_module
from megaplan.worktrees import (
    PatchCaptureError,
    capture_patch_bundle,
    custody_paths,
    git_apply_check_bundle,
    load_patch_bundle,
    make_task_identity,
    prevalidate_patch_apply,
    read_registry_entries,
    validate_bundle_for_apply,
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
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")


def _codes(result: dict) -> list[str]:
    return [error["code"] for error in result["errors"]]


def _bundle(project_dir: Path, patch: str | bytes) -> object:
    paths = custody_paths(project_dir)
    patch_path = paths.patch_payload("run-8", "T8")
    manifest_path = paths.patch_manifest("run-8", "T8")
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_bytes = patch.encode("utf-8") if isinstance(patch, str) else patch
    patch_path.write_bytes(patch_bytes)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-8",
                "task_id": "T8",
                "patch": {
                    "path": patch_path.relative_to(paths.custody_root).as_posix(),
                    "sha256": patches_module._sha256_bytes(patch_bytes),
                    "size_bytes": len(patch_bytes),
                    "changed_paths": [],
                },
            }
        ),
        encoding="utf-8",
    )
    return load_patch_bundle(project_dir, "run-8", "T8")


def _finalize_data(task_id: str = "T8") -> dict[str, object]:
    return {"tasks": [{"id": task_id, "description": "Apply patch"}]}


def test_validate_bundle_accepts_c_style_quoted_diff_file_rename_and_copy_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    patch = """
diff --git "a/space name.txt" "b/space name.txt"
--- "a/space name.txt"
+++ "b/space name.txt"
@@ -1 +1 @@
-old
+new
diff --git "a/copy source.txt" "b/copy target.txt"
copy from "copy\\040source.txt"
copy to "copy\\040target.txt"
diff --git "a/old name.txt" "b/new name.txt"
rename from "old\\040name.txt"
rename to "new\\040name.txt"
""".lstrip()

    result = validate_bundle_for_apply(repo, _bundle(tmp_path / "coordinator", patch))

    assert result == {"ok": True, "errors": []}


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ("diff --git a/../outside b/../outside\n", "traversal_path"),
        ("diff --git a//empty b//empty\n", "absolute_path"),
        ("diff --git a/C:/drive b/C:/drive\n", "drive_letter_path"),
        ("diff --git a/\\rooted b/\\rooted\n", "absolute_path"),
        ("diff --git a/ b/\n", "empty_path"),
        ("diff --git a/file b/file\n--- /dev/null\n+++ /dev/null\n", "invalid_dev_null"),
        ("diff --git /dev/null b/file\n", "invalid_dev_null"),
        ("rename from /dev/null\n", "invalid_dev_null"),
        ("diff --git \"a/unterminated b/file\n", "malformed_quoted_path"),
    ],
)
def test_validate_bundle_rejects_unsafe_or_malformed_paths(
    tmp_path: Path,
    patch: str,
    code: str,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    result = validate_bundle_for_apply(repo, _bundle(tmp_path / "coordinator", patch))

    assert code in _codes(result)


def test_validate_bundle_rejects_symlink_escape_before_git_apply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    _init_repo(repo)
    outside.mkdir()
    os.symlink(outside, repo / "link-out")
    patch = "diff --git a/link-out/file.txt b/link-out/file.txt\n--- a/link-out/file.txt\n+++ b/link-out/file.txt\n"

    result = validate_bundle_for_apply(repo, _bundle(tmp_path / "coordinator", patch))

    assert "symlink_escape" in _codes(result)


def test_validate_bundle_rejects_submodule_gitlink_edits(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "update-index", "--add", "--cacheinfo", "160000,1111111111111111111111111111111111111111,sub")
    _git(repo, "commit", "-m", "add gitlink")
    patch = "diff --git a/sub/file.txt b/sub/file.txt\n--- a/sub/file.txt\n+++ b/sub/file.txt\n"

    result = validate_bundle_for_apply(repo, _bundle(tmp_path / "coordinator", patch))

    assert "submodule_edit" in _codes(result)


def test_validate_bundle_rejects_symlink_and_submodule_modes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    patch = """
diff --git a/link b/link
new file mode 120000
diff --git a/sub b/sub
new file mode 160000
""".lstrip()

    result = validate_bundle_for_apply(repo, _bundle(tmp_path / "coordinator", patch))

    assert "symlink_edit" in _codes(result)
    assert "submodule_edit" in _codes(result)


def test_git_apply_check_rejects_oversized_binary_hunk_before_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.setattr(patches_module, "MAX_BINARY_HUNK_BYTES", 5)

    def fail_if_called(_repo: Path, _patch_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("git apply --check should not run for invalid bundle")

    monkeypatch.setattr(patches_module, "_run_git_apply_check", fail_if_called)
    patch = """
diff --git a/blob.bin b/blob.bin
GIT binary patch
literal 6
abc
""".lstrip()

    result = git_apply_check_bundle(repo, _bundle(tmp_path / "coordinator", patch))

    assert result["ok"] is False
    assert result["git_apply_ran"] is False
    assert "oversized_binary_hunk" in _codes(result["validation"])


def test_git_apply_check_runs_after_validation_for_safe_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    patch = _git(repo, "diff", "--binary", "--full-index", "--no-color", "--no-ext-diff").stdout
    (repo / "file.txt").write_text("base\n", encoding="utf-8")

    result = git_apply_check_bundle(repo, _bundle(tmp_path / "coordinator", patch))

    assert result["ok"] is True
    assert result["git_apply_ran"] is True
    assert result["validation"] == {"ok": True, "errors": []}


def test_prevalidate_patch_apply_requires_identity_base_head_and_records_registry(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    project_dir = tmp_path / "coordinator"
    _init_repo(repo)
    identity = make_task_identity("T8")
    (repo / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture_patch_bundle(
        project_dir,
        "run-8",
        "T8",
        repo,
        secret_scan_mode="local_only",
        identity=identity,
    )
    _git(repo, "checkout", "--", "file.txt")

    result = prevalidate_patch_apply(project_dir, "run-8", "T8", repo, _finalize_data())

    assert result["ok"] is True
    assert result["task_key"] == identity.task_key
    assert result["identity"] == identity.registry_identity()
    assert result["trailers"] == identity.trailer_fields()
    assert result["secret_scan"]["mode"] == "local_only"
    assert result["secret_scan"]["explicit_local_only_opt_in"] is True
    assert result["base_head"] == result["current_head"]
    assert result["apply_check"]["git_apply_ran"] is True
    registry_entries = read_registry_entries(project_dir, "run-8")
    assert [entry["entry_type"] for entry in registry_entries] == ["patch_captured", "apply_checked"]
    assert all(entry["task_key"] == identity.task_key for entry in registry_entries)
    assert all(entry["identity"] == identity.registry_identity() for entry in registry_entries)


def test_prevalidate_patch_apply_blocks_base_head_mismatch_before_git_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    project_dir = tmp_path / "coordinator"
    _init_repo(repo)
    (repo / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture_patch_bundle(project_dir, "run-8", "T8", repo, secret_scan_mode="local_only")
    _git(repo, "checkout", "--", "file.txt")
    (repo / "later.txt").write_text("later\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance milestone")

    def fail_if_called(_repo: Path, _patch_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("git apply --check should not run when milestone HEAD mismatches")

    monkeypatch.setattr(patches_module, "_run_git_apply_check", fail_if_called)

    result = prevalidate_patch_apply(project_dir, "run-8", "T8", repo, _finalize_data())

    assert result["ok"] is False
    assert result["apply_check"]["git_apply_ran"] is False
    assert "base_head_mismatch" in _codes(result)
    assert (repo / "file.txt").read_text(encoding="utf-8") == "base\n"


def test_prevalidate_patch_apply_blocks_trailer_mismatch_before_git_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    project_dir = tmp_path / "coordinator"
    _init_repo(repo)
    (repo / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture = capture_patch_bundle(project_dir, "run-8", "T8", repo, secret_scan_mode="local_only")
    _git(repo, "checkout", "--", "file.txt")
    manifest = json.loads(capture.manifest_path.read_text(encoding="utf-8"))
    manifest["trailers"]["Task-Id-B64"] = "not-the-finalized-id"
    capture.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def fail_if_called(_repo: Path, _patch_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("git apply --check should not run when trailer identity mismatches")

    monkeypatch.setattr(patches_module, "_run_git_apply_check", fail_if_called)

    result = prevalidate_patch_apply(project_dir, "run-8", "T8", repo, _finalize_data())

    assert result["ok"] is False
    assert result["apply_check"]["git_apply_ran"] is False
    assert "trailer_identity_mismatch" in _codes(result)
    assert (repo / "file.txt").read_text(encoding="utf-8") == "base\n"


def test_apply_helpers_reject_raw_patch_inputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    patch_path = tmp_path / "worker.patch"
    patch_path.write_text("diff --git a/file.txt b/file.txt\n", encoding="utf-8")

    for raw in ["diff --git a/file.txt b/file.txt\n", patch_path, b"diff --git a/file.txt b/file.txt\n"]:
        with pytest.raises(PatchCaptureError) as excinfo:
            validate_bundle_for_apply(repo, raw)  # type: ignore[arg-type]
        assert excinfo.value.code == "invalid_bundle_record"


def test_load_patch_bundle_rejects_manifest_pointing_outside_custody_layout(tmp_path: Path) -> None:
    project_dir = tmp_path / "coordinator"
    paths = custody_paths(project_dir)
    manifest_path = paths.patch_manifest("run-8", "T8")
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-8",
                "task_id": "T8",
                "patch": {
                    "path": "../worker.patch",
                    "sha256": "sha256:" + "0" * 64,
                    "size_bytes": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PatchCaptureError) as excinfo:
        load_patch_bundle(project_dir, "run-8", "T8")

    assert excinfo.value.code == "manifest_invalid"
