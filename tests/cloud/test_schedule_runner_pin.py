"""Tests for the manifest-only schedule runner resolution.

Shells out to arnold_pipelines/megaplan/cloud/systemd/
arnold-resident-schedule-run-once-r7 in controlled scenarios: runtime_root +
expected_head MUST be derived from the runtime manifest's ``epic`` section
(``ARNOLD_RUNTIME_MANIFEST`` or the /workspace/.megaplan default) — there is
no env pin, no pin file, and no hardcoded SHA anymore. Missing/invalid/
non-authoritative manifest must fail loudly (exit 2); a valid manifest flows
into the git drift guard, which is exercised with a non-repo runtime_root
(must fail with a non-pin exit code) and with a real repo at the pinned head
(the drift guard passes; the run then fails downstream of resolution).
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "arnold_pipelines"
    / "megaplan"
    / "cloud"
    / "systemd"
    / "arnold-resident-schedule-run-once-r7"
)

VALID_SHA = "a" * 40


def _write_manifest(
    path: Path,
    *,
    runtime_root: str,
    expected_head: str = VALID_SHA,
    compatibility_only: bool = False,
    valid_json: bool = True,
    epic_present: bool = True,
) -> None:
    payload = {"compatibility_only": compatibility_only}
    if epic_present:
        payload["epic"] = {
            "runtime_root": runtime_root,
            "expected_head": expected_head,
        }
    path.write_text(
        json.dumps(payload) if valid_json else "{not valid json",
        encoding="utf-8",
    )


def _run_script(
    tmp_path: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    manifest: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ARNOLD_SCHEDULE_SKIP_DOCKER_CHECK": "1",
        # Keep the default /workspace/... bootstrap path out of the picture.
        "ARNOLD_RUNTIME_MANIFEST": str(manifest or (tmp_path / "no-manifest.json")),
    }
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR


def test_manifest_derives_root_and_head_then_git_guard_fails(tmp_path: Path) -> None:
    """A valid manifest supplies runtime_root + expected_head (not exit 2);
    the git guard then fails loudly on a non-repo root."""
    runtime_root = tmp_path / "not-a-repo"
    runtime_root.mkdir()
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root=str(runtime_root))
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode != 0
    assert result.returncode != 2
    assert "HEAD" in result.stderr


def test_missing_manifest_fails_loudly_with_exit_2(tmp_path: Path) -> None:
    """No manifest at ARNOLD_RUNTIME_MANIFEST -> exit 2 naming the path."""
    missing = tmp_path / "no-such-manifest.json"
    result = _run_script(tmp_path, manifest=missing)
    assert result.returncode == 2
    assert str(missing) in result.stderr


def test_invalid_manifest_json_fails_loudly(tmp_path: Path) -> None:
    """Corrupt JSON -> exit 2 naming the manifest file."""
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root="/tmp/x", valid_json=False)
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode == 2
    assert str(manifest) in result.stderr
    assert "invalid" in result.stderr


def test_manifest_missing_epic_fields_fails_loudly(tmp_path: Path) -> None:
    """Manifest without epic.runtime_root/epic.expected_head -> exit 2."""
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root="/tmp/x", epic_present=False)
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode == 2
    assert "epic.runtime_root/epic.expected_head" in result.stderr


def test_manifest_bad_expected_head_sha_fails_loudly(tmp_path: Path) -> None:
    """epic.expected_head not a 40-hex SHA -> exit 2."""
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root="/tmp/x", expected_head="not-a-sha")
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode == 2
    assert "expected_head" in result.stderr
    assert "40-hex" in result.stderr


def test_manifest_relative_runtime_root_fails_loudly(tmp_path: Path) -> None:
    """epic.runtime_root not absolute -> exit 2."""
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root="relative/path")
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode == 2
    assert "runtime_root" in result.stderr
    assert "absolute" in result.stderr


def test_compatibility_only_pointer_is_refused(tmp_path: Path) -> None:
    """A compatibility_only pointer is NON-AUTHORITATIVE (G2) and cannot
    select a runtime -> exit 2, never an unpinned pass."""
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(
        manifest, runtime_root="/tmp/x", compatibility_only=True
    )
    result = _run_script(tmp_path, manifest=manifest)
    assert result.returncode == 2
    assert "invalid" in result.stderr


def test_matching_manifest_passes_drift_guard(tmp_path: Path) -> None:
    """A real repo at the manifest-pinned head passes the git drift guard;
    the run then fails downstream of resolution (dependency roots), proving
    runtime_root + expected_head came from the manifest."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (repo / "file.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = tmp_path / "runtime-manifest.json"
    _write_manifest(manifest, runtime_root=str(repo), expected_head=head)
    result = _run_script(tmp_path, manifest=manifest)
    # Resolution + drift guard passed: the failure is downstream (dependency
    # root / auth guards on the box paths), NOT a manifest or drift error.
    assert result.returncode == 1
    assert "manifest" not in result.stderr
    assert "drift" not in result.stderr
