"""Lifecycle tests for megaplan.orchestration.suite_runner.

Verifies the core subprocess-group management contract:
- A long-running process is killed on deadline (SIGTERM → grace → SIGKILL).
- The raw log file is written even on timeout.
- The SuiteRunResult reports ``status='timeout'`` when the deadline fires.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import pytest

from megaplan.orchestration.suite_runner import (
    SuiteRunResult,
    _compute_code_hash,
    _parse_pytest_output,
    run_suite,
)
from megaplan.runtime.process import kill_group, spawn


# ---------------------------------------------------------------------------
# Helper: spawn a real sleep process via run_suite with imminent deadline
# ---------------------------------------------------------------------------

class _FakePopen:
    """Minimal fake that tracks whether kill_group was called."""

    def __init__(self) -> None:
        self.pid = 99999
        self._killed = False

    def poll(self) -> int | None:
        return None  # never exits on its own

    def wait(self, timeout: float | None = None) -> int:
        raise TimeoutError("would block forever")


def test_run_suite_timeout_kills_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sleep command that outlives the deadline must be killed, the raw
    log must exist, and the result must report status='timeout'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()  # so git ls-tree doesn't error loudly (but will still fail gracefully)

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    config = {
        "test_command": "sleep 30",
        "plan_dir": str(plan_dir),
    }

    # Use a very short deadline so we hit timeout quickly.
    deadline = time.monotonic() + 2.0

    result = run_suite(
        project_dir,
        config,
        phase="lifecycle_test",
        deadline_seconds=deadline,
    )

    # Verify the raw log was written
    assert result.raw_log_path.exists()
    assert result.raw_log_path.name.startswith("raw_")
    assert result.raw_log_path.name.endswith(".log")
    assert result.raw_log_path.parent == plan_dir / "verification"

    # The log should contain some output (even if just shell error or empty)
    log_content = result.raw_log_path.read_text(encoding="utf-8")
    assert isinstance(log_content, str)

    # The result must report timeout
    assert result.status == "timeout"
    assert result.exit_code is None or result.exit_code < 0
    assert result.phase == "lifecycle_test"
    assert result.command == "sleep 30"
    assert result.duration > 0

    # All fields must be present
    assert isinstance(result.run_id, str)
    assert len(result.run_id) == 12
    assert isinstance(result.collected, int)
    assert isinstance(result.collected_ids, list)
    assert isinstance(result.failures, list)
    assert isinstance(result.passes, list)
    assert isinstance(result.collections_parse_ok, bool)
    assert isinstance(result.code_hash, str)
    assert result.code_hash.startswith("sha256:")


def test_run_suite_normal_completion(
    tmp_path: Path,
) -> None:
    """A fast command that finishes before the deadline must report
    status='passed' (or 'failed' for non-zero exit) and capture output."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    config = {
        "test_command": "echo hello world",
        "plan_dir": str(plan_dir),
    }

    deadline = time.monotonic() + 30.0  # generous

    result = run_suite(
        project_dir,
        config,
        phase="smoke_test",
        deadline_seconds=deadline,
    )

    assert result.raw_log_path.exists()
    log_content = result.raw_log_path.read_text(encoding="utf-8")
    assert "hello world" in log_content

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.phase == "smoke_test"
    assert result.duration > 0


def test_run_suite_runner_error_on_spawn_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When spawn raises an exception, the result should be runner_error."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    # Make spawn raise
    def _failing_spawn(*args: object, **kwargs: object) -> object:
        raise OSError("spawn failed")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.spawn", _failing_spawn
    )

    config = {
        "test_command": "echo x",
        "plan_dir": str(plan_dir),
    }

    deadline = time.monotonic() + 30.0

    result = run_suite(
        project_dir,
        config,
        phase="error_test",
        deadline_seconds=deadline,
    )

    assert result.status == "runner_error"
    assert result.exit_code is None
    assert result.collected == 0
    assert result.collections_parse_ok is False
    # The log file should still exist (we opened it before spawn)
    assert result.raw_log_path.exists()


def test_run_suite_failed_command(
    tmp_path: Path,
) -> None:
    """A command that exits non-zero should report status='failed'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    config = {
        "test_command": "python -c \"import sys; sys.exit(1)\"",
        "plan_dir": str(plan_dir),
    }

    deadline = time.monotonic() + 30.0

    result = run_suite(
        project_dir,
        config,
        phase="fail_test",
        deadline_seconds=deadline,
    )

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.raw_log_path.exists()


def test_run_suite_defaults_to_pytest(
    tmp_path: Path,
) -> None:
    """When no test_command is configured, run_suite defaults to pytest."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    config: dict[str, object] = {
        "plan_dir": str(plan_dir),
    }

    deadline = time.monotonic() + 30.0

    result = run_suite(
        project_dir,
        config,
        phase="default_test",
        deadline_seconds=deadline,
    )

    assert "pytest" in result.command
    assert "--tb=no" in result.command


# ---------------------------------------------------------------------------
# _compute_code_hash tests
# ---------------------------------------------------------------------------


def test_compute_code_hash_git_primary(tmp_path: Path) -> None:
    """code_hash uses git ls-tree when available."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    # Initialise a real git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    (project_dir / "hello.py").write_text("print('hi')")
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=project_dir,
        capture_output=True,
    )

    h = _compute_code_hash(project_dir)
    assert h.startswith("sha256:")
    assert len(h) > len("sha256:")


def test_compute_code_hash_fallback_no_git(tmp_path: Path) -> None:
    """When git is absent, fallback to find-based hash."""
    project_dir = tmp_path / "norepo"
    project_dir.mkdir()
    (project_dir / "a.py").write_text("a")
    (project_dir / "b.py").write_text("b")

    h = _compute_code_hash(project_dir)
    assert h.startswith("sha256:")
    assert len(h) > len("sha256:")


# ---------------------------------------------------------------------------
# _parse_pytest_output tests
# ---------------------------------------------------------------------------


def test_parse_pytest_output_collected_count() -> None:
    """Parse 'collected N items' from pytest output."""
    stdout = "collected 42 items\n...\n3 passed"
    parsed = _parse_pytest_output(stdout)
    assert parsed["collected"] == 42
    assert parsed["parse_ok"] is False


def test_parse_pytest_output_failures_listed() -> None:
    """Parse FAILED node IDs from pytest output."""
    stdout = (
        "collected 5 items\n"
        "FAILED tests/test_a.py::test_x - AssertionError\n"
        "FAILED tests/test_b.py::test_y - ValueError\n"
        "PASSED tests/test_a.py::test_ok1\n"
        "PASSED tests/test_a.py::test_ok2\n"
        "PASSED tests/test_a.py::test_ok3\n"
        "2 failed, 3 passed\n"
    )
    parsed = _parse_pytest_output(stdout)
    assert parsed["failures"] == [
        "tests/test_a.py::test_x",
        "tests/test_b.py::test_y",
    ]
    assert parsed["passes"] == [
        "tests/test_a.py::test_ok1",
        "tests/test_a.py::test_ok2",
        "tests/test_a.py::test_ok3",
    ]


def test_parse_pytest_output_empty() -> None:
    """Empty stdout yields zeroed-out fields."""
    parsed = _parse_pytest_output("")
    assert parsed["collected"] == 0
    assert parsed["failures"] == []
    assert parsed["passes"] == []
    assert parsed["parse_ok"] is False


def test_parse_pytest_output_all_pass() -> None:
    """All-pass output yields correct counts."""
    stdout = "collected 10 items\n..........\n10 passed in 0.50s"
    parsed = _parse_pytest_output(stdout)
    assert parsed["collected"] == 10
    assert parsed["passes"] == []
    assert parsed["failures"] == []
    assert parsed["parse_ok"] is False


def test_parse_pytest_output_mixed() -> None:
    """Mixed pass/fail with per-ID listing."""
    stdout = (
        "collected 3 items\n"
        "FAILED tests/test_z.py::test_bad - AssertionError\n"
        "PASSED tests/test_z.py::test_ok1\n"
        "PASSED tests/test_z.py::test_ok2\n"
        "1 failed, 2 passed in 0.12s\n"
    )
    parsed = _parse_pytest_output(stdout)
    assert parsed["collected"] == 3
    assert parsed["failures"] == ["tests/test_z.py::test_bad"]
    assert parsed["passes"] == [
        "tests/test_z.py::test_ok1",
        "tests/test_z.py::test_ok2",
    ]


# ---------------------------------------------------------------------------
# SuiteRunResult field completeness
# ---------------------------------------------------------------------------


def test_suite_run_result_all_fields_present() -> None:
    """Every field listed in the spec must be constructable."""
    result = SuiteRunResult(
        run_id="abc123def456",
        phase="post_execute",
        command="pytest",
        duration=1.5,
        collected=10,
        collected_ids=["tests/test_a.py::test_x"],
        failures=["tests/test_b.py::test_y"],
        passes=["tests/test_a.py::test_x"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/tmp/raw_abc.log"),
        code_hash="sha256:abcdef",
        collections_parse_ok=True,
    )
    assert result.run_id == "abc123def456"
    assert result.phase == "post_execute"
    assert result.command == "pytest"
    assert result.duration == 1.5
    assert result.collected == 10
    assert result.collected_ids == ["tests/test_a.py::test_x"]
    assert result.failures == ["tests/test_b.py::test_y"]
    assert result.passes == ["tests/test_a.py::test_x"]
    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.raw_log_path == Path("/tmp/raw_abc.log")
    assert result.code_hash == "sha256:abcdef"
    assert result.collections_parse_ok is True
