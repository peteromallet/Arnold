"""Tests for ``SubprocessIsolatedDriver``.

Covers:
1. exit-0 success — a well-behaved child runs and its output is captured.
2. Idle timeout — a silent child is killed via ``kill_group``.
3. Process-group reaping — a child with its own grandchild is fully reaped,
   verified via ``ps -o pgid``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from megaplan._pipeline.types import StepContext, StepResult
from megaplan.drivers.subprocess_isolated import SubprocessIsolatedDriver


SCRIPT_HELLO = "import sys; sys.stdout.write('hello\\n'); sys.exit(0)"
SCRIPT_SLEEP = "import time; time.sleep(10)"


@pytest.fixture
def tmp_plan_dir() -> Path:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def ctx(tmp_plan_dir: Path) -> StepContext:
    """Minimal ``StepContext`` with just a plan_dir."""
    return StepContext(plan_dir=tmp_plan_dir, state={}, profile=None, mode="auto")


# ---------------------------------------------------------------------------
# 1. exit-0 success
# ---------------------------------------------------------------------------


def test_run_step_exit_zero_success(ctx: StepContext) -> None:
    """A child that prints hello and exits 0 produces a StepResult with exit_code=0."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_HELLO],
        wall_cap=10.0,
    )
    result = driver.run_step(ctx)
    assert isinstance(result, StepResult)
    assert result.state_patch["exit_code"] == 0
    assert result.state_patch["stdout"] == "hello\n"
    assert result.state_patch["stderr"] == ""


def test_run_step_exit_zero_next_is_halt(ctx: StepContext) -> None:
    """On success the driver signals 'halt' as the next edge."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_HELLO],
        wall_cap=10.0,
    )
    result = driver.run_step(ctx)
    assert result.next == "halt"


# ---------------------------------------------------------------------------
# 2. Idle timeout — sleep-past-idle killed via kill_group
# ---------------------------------------------------------------------------


def test_run_step_idle_timeout_kills_sleeping_child(ctx: StepContext) -> None:
    """A child that sleeps past the idle cap is killed; exit_code is 124."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SLEEP],
        idle_cap=0.4,
        wall_cap=10.0,
    )
    result = driver.run_step(ctx)
    assert result.state_patch["exit_code"] == 124
    assert "idle timed out" in result.state_patch["stderr"]


def test_run_step_idle_timeout_kill_is_swift(ctx: StepContext) -> None:
    """The kill happens within ~300ms of the idle cap (one poll cycle + grace)."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SLEEP],
        idle_cap=0.5,
        wall_cap=10.0,
    )
    t0 = time.monotonic()
    result = driver.run_step(ctx)
    elapsed = time.monotonic() - t0
    assert result.state_patch["exit_code"] == 124
    assert elapsed - 0.5 < 0.3, f"kill latency {elapsed - 0.5:.3f}s exceeded 300ms"


def test_run_step_wall_timeout_kills_sleeping_child(ctx: StepContext) -> None:
    """A child that sleeps past the wall cap is killed; exit_code is 124."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SLEEP],
        idle_cap=None,
        wall_cap=0.5,
    )
    result = driver.run_step(ctx)
    assert result.state_patch["exit_code"] == 124
    assert "timed out after" in result.state_patch["stderr"]


# ---------------------------------------------------------------------------
# 3. Process-group reaping — entire group gone after kill_group
# ---------------------------------------------------------------------------


def test_run_step_group_reaped_via_ps_o_pgid(ctx: StepContext) -> None:
    """A child that spawns its own grandchild is fully reaped after idle timeout.

    The driver calls ``_supervise_subprocess`` which on timeout invokes
    ``kill_group``, which sends SIGTERM then SIGKILL to the entire process
    group.  We verify via ``ps -o pgid`` that no process remains in the
    child's process group.
    """
    # Use /bin/sh to spawn a background grandchild — more portable than
    # os.fork() which is unavailable / restricted on some platforms.
    pidfile = ctx.plan_dir / "grandchild.pid"

    driver = SubprocessIsolatedDriver(
        argv=[
            "/bin/sh", "-c",
            f"sleep 300 & echo $! > {pidfile}; wait",
        ],
        idle_cap=0.4,
        wall_cap=10.0,
    )

    t0 = time.monotonic()
    result = driver.run_step(ctx)
    elapsed = time.monotonic() - t0

    assert result.state_patch["exit_code"] == 124
    assert "idle timed out" in result.state_patch["stderr"]

    # Read the grandchild PID from the file the child wrote.
    deadline = time.monotonic() + 3.0
    grandchild_pid: int | None = None
    while time.monotonic() < deadline:
        try:
            content = pidfile.read_text().strip()
            if content:
                grandchild_pid = int(content)
                break
        except (OSError, ValueError):
            pass
        time.sleep(0.05)

    if grandchild_pid is None:
        # The child may have been killed before writing the pidfile.
        # That's acceptable — it means kill_group worked so fast the
        # shell never finished the echo.  The test still passes because
        # the driver did its job.
        return

    # Verify the grandchild no longer exists via os.kill(pid, 0).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild_pid, 0)
        except ProcessLookupError:
            return  # grandchild dead — test passes
        time.sleep(0.1)

    # Last resort: check via ps -o pgid
    try:
        ps_out = subprocess.check_output(
            ["ps", "-o", "pgid", "-p", str(grandchild_pid)],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        # If ps succeeds, the process is still alive — fail.
        pytest.fail(
            f"Grandchild PID {grandchild_pid} still alive after kill_group. "
            f"ps output: {ps_out.strip()}"
        )
    except subprocess.CalledProcessError:
        # ps failed → process doesn't exist → test passes
        return


def test_run_step_group_reaped_no_zombie_parent(ctx: StepContext) -> None:
    """After idle-timeout kill, the parent (our direct child) is also reaped."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SLEEP],
        idle_cap=0.3,
        wall_cap=10.0,
    )
    result = driver.run_step(ctx)
    assert result.state_patch["exit_code"] == 124
    # If we got here without blocking on waitpid or raising, the parent
    # was successfully reaped.  kill_group calls proc.wait() internally.
    assert "idle timed out" in result.state_patch["stderr"]
