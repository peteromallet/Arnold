"""Idle/stall detection for the test-suite runner.

Root cause this guards against: baseline/verification capture used a single
total-wall-clock cap. As the target suite grew past that cap, a *healthy but
slow* suite was killed exactly like a wedged one — emitting a poison null
baseline that hard-blocked the no-new-failures checkpoint and killed the chain.

The fix makes "is it moving?" the primary signal: while the suite's output log
keeps growing it is making progress and is left alone; only a log that goes
SILENT for ``idle_seconds`` is treated as wedged. The absolute deadline remains
as a generous last-resort runaway ceiling.
"""
from __future__ import annotations

import time
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.suite_runner import _make_progress_writer, run_suite


def _project(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    return project_dir, plan_dir


# A command that prints steadily for ~2s (0.1s gaps), then exits 0.
_MOVING_CMD = (
    "python -c \"import time,sys;"
    "[(sys.stdout.write(str(i)+chr(10)), sys.stdout.flush(), time.sleep(0.1)) "
    "for i in range(20)]\""
)
# A command that prints once, then hangs silently for 30s.
_HANGS_CMD = "python -c \"import time,sys; sys.stdout.write('start\\n'); sys.stdout.flush(); time.sleep(30)\""


def test_moving_suite_survives_idle_cap_shorter_than_total_runtime(tmp_path: Path) -> None:
    """A suite that keeps producing output is NOT killed even though its total
    runtime (~2s) exceeds the idle cap (1s) — because it is never silent."""
    project_dir, plan_dir = _project(tmp_path)
    config = {"test_command": _MOVING_CMD, "plan_dir": str(plan_dir)}

    result = run_suite(
        project_dir,
        config,
        phase="idle_test",
        deadline_seconds=time.monotonic() + 30.0,  # generous absolute ceiling
        idle_seconds=1.0,                            # < total runtime, but it keeps moving
    )

    assert result.status == "passed", f"moving suite must not be killed, got {result.status}"
    assert result.exit_code == 0
    assert result.timeout_reason is None
    assert result.duration > 1.0, "should have run its full ~2s, not been cut at the idle cap"


def test_silent_suite_is_killed_quickly_with_idle_reason(tmp_path: Path) -> None:
    """A suite that goes silent (a hung test) is killed shortly after the idle
    cap, long before the absolute deadline — and reports timeout_reason='idle'."""
    project_dir, plan_dir = _project(tmp_path)
    config = {"test_command": _HANGS_CMD, "plan_dir": str(plan_dir)}

    result = run_suite(
        project_dir,
        config,
        phase="idle_test",
        deadline_seconds=time.monotonic() + 30.0,  # would otherwise wait the full 30s
        idle_seconds=1.0,
    )

    assert result.status == "timeout"
    assert result.timeout_reason == "idle"
    assert result.duration < 10.0, "must be killed at the idle cap, not the 30s deadline"


def test_absolute_ceiling_still_trips_for_a_moving_suite(tmp_path: Path) -> None:
    """Even a steadily-moving suite is killed if it crosses the absolute ceiling;
    that timeout is attributed to 'deadline', not 'idle'."""
    project_dir, plan_dir = _project(tmp_path)
    config = {"test_command": _MOVING_CMD, "plan_dir": str(plan_dir)}

    result = run_suite(
        project_dir,
        config,
        phase="idle_test",
        deadline_seconds=time.monotonic() + 0.5,  # ceiling below the ~2s runtime
        idle_seconds=5.0,                           # idle never trips (it keeps moving)
    )

    assert result.status == "timeout"
    assert result.timeout_reason == "deadline"


def test_progress_writer_appends_to_sibling_file_not_the_log(tmp_path: Path) -> None:
    """The soft heartbeat is written to raw_<id>.progress, a different file than
    the raw log, so it can never feed the idle detector."""
    raw_log = tmp_path / "raw_abc123.log"
    raw_log.write_text("", encoding="utf-8")
    cb = _make_progress_writer(raw_log)
    cb(61.0, 4096)
    cb(122.0, 8192)

    progress = raw_log.with_suffix(".progress")
    assert progress.exists()
    assert progress != raw_log
    body = progress.read_text(encoding="utf-8")
    assert "still running" in body
    assert "61s" in body and "4096 bytes" in body
    assert raw_log.read_text(encoding="utf-8") == "", "raw log must be untouched by heartbeats"
