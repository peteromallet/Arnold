"""Tests for the corrected schedule runner's expected_head pin resolution.

Shells out to arnold_pipelines/megaplan/cloud/systemd/
arnold-resident-schedule-run-once-r7 in controlled scenarios: the pin must be
accepted from the env override or pin file (exit != 2), and missing pin
configuration must fail loudly (exit 2). The git guard is exercised with a
non-repo runtime_root, which must fail with a non-pin exit code.
"""

from __future__ import annotations

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


def _run_script(
    tmp_path: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    pin_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ARNOLD_SCHEDULE_SKIP_DOCKER_CHECK": "1",
        # Keep the default /workspace/... paths out of the picture entirely.
        "ARNOLD_SCHEDULE_PIN_FILE": str(pin_file or (tmp_path / "no-pin-file")),
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


def test_env_pin_accepted_then_git_guard_fails(tmp_path: Path) -> None:
    """Env pin is accepted (not exit 2); the git guard then fails loudly."""
    runtime_root = tmp_path / "not-a-repo"
    runtime_root.mkdir()
    result = _run_script(
        tmp_path,
        env_overrides={
            "ARNOLD_SCHEDULE_EXPECTED_HEAD": VALID_SHA,
            "ARNOLD_SCHEDULE_RUNTIME_ROOT": str(runtime_root),
        },
    )
    assert result.returncode != 0
    assert result.returncode != 2
    assert "HEAD" in result.stderr


def test_no_pin_fails_loudly_with_exit_2(tmp_path: Path) -> None:
    """No env pin and no pin file -> exit 2 with an actionable message."""
    result = _run_script(tmp_path)
    assert result.returncode == 2
    assert "expected_head pin" in result.stderr
    assert "ARNOLD_SCHEDULE_EXPECTED_HEAD" in result.stderr


def test_pin_file_accepted_then_git_guard_fails(tmp_path: Path) -> None:
    """Pin file with a valid 40-hex SHA is accepted; git guard then fails."""
    runtime_root = tmp_path / "not-a-repo"
    runtime_root.mkdir()
    pin_file = tmp_path / "schedule-pin"
    pin_file.write_text(f"{VALID_SHA}\n", encoding="utf-8")
    result = _run_script(
        tmp_path,
        pin_file=pin_file,
        env_overrides={"ARNOLD_SCHEDULE_RUNTIME_ROOT": str(runtime_root)},
    )
    assert result.returncode != 0
    assert result.returncode != 2
    assert "HEAD" in result.stderr


def test_invalid_pin_file_content_is_a_hard_error(tmp_path: Path) -> None:
    """Pin file with non-SHA content -> exit 2 naming the file."""
    pin_file = tmp_path / "schedule-pin"
    pin_file.write_text("not-a-sha\n", encoding="utf-8")
    result = _run_script(tmp_path, pin_file=pin_file)
    assert result.returncode == 2
    assert str(pin_file) in result.stderr


def test_pin_file_whitespace_is_trimmed(tmp_path: Path) -> None:
    """Leading/trailing whitespace around the SHA is trimmed before use."""
    runtime_root = tmp_path / "not-a-repo"
    runtime_root.mkdir()
    pin_file = tmp_path / "schedule-pin"
    pin_file.write_text(f"  {VALID_SHA}\t\n", encoding="utf-8")
    result = _run_script(
        tmp_path,
        pin_file=pin_file,
        env_overrides={"ARNOLD_SCHEDULE_RUNTIME_ROOT": str(runtime_root)},
    )
    assert result.returncode != 0
    assert result.returncode != 2
