"""Crash-isolation oracle (T28 / hinge-gate done-criterion).

Three synthetic crash shapes — ``sys.exit(1)``, sleep-past-idle, ``os._exit(137)`` —
are run under both drivers:

* ``SubprocessIsolatedDriver``: each crash MUST be a contained per-step failure;
  the parent test process MUST survive; for the sleep case the kill-group reap
  MUST fire and the grandchild MUST be gone (verified via ``ps -o pgid`` /
  ``os.kill(pid, 0)``).
* ``InProcessDriver``: each crash takes the run down — ``sys.exit`` propagates
  ``SystemExit`` to the caller; ``os._exit`` terminates the interpreter (verified
  by spawning a subprocess wrapper and asserting the child died with code 137).

Marked ``hinge_gate`` so the chain-CI selector picks it up alongside T10/T25/T26
as a done-criterion: red here auto-halts the hinge gate.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from megaplan._pipeline.types import StepContext, StepResult
from megaplan.drivers.in_process import InProcessDriver
from megaplan.drivers.subprocess_isolated import SubprocessIsolatedDriver


pytestmark = pytest.mark.hinge_gate


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> StepContext:
    with tempfile.TemporaryDirectory() as td:
        yield StepContext(plan_dir=Path(td), state={}, profile=None, mode="auto")


SCRIPT_SYS_EXIT_1 = "import sys; sys.exit(1)"
SCRIPT_SLEEP_PAST_IDLE = "import time; time.sleep(30)"
SCRIPT_OS_EXIT_137 = "import os; os._exit(137)"


# ---------------------------------------------------------------------------
# subprocess_isolated: all three shapes contained, parent survives
# ---------------------------------------------------------------------------


def test_subprocess_isolated_contains_sys_exit_1(ctx: StepContext) -> None:
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SYS_EXIT_1],
        wall_cap=10.0,
    )
    parent_pid_before = os.getpid()
    result = driver.run_step(ctx)
    assert os.getpid() == parent_pid_before, "parent must survive"
    assert isinstance(result, StepResult)
    assert result.state_patch["exit_code"] == 1


def test_subprocess_isolated_contains_os_exit_137(ctx: StepContext) -> None:
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_OS_EXIT_137],
        wall_cap=10.0,
    )
    parent_pid_before = os.getpid()
    result = driver.run_step(ctx)
    assert os.getpid() == parent_pid_before, "parent must survive os._exit child"
    assert result.state_patch["exit_code"] == 137


def test_subprocess_isolated_kill_group_fires_on_idle(ctx: StepContext) -> None:
    """sleep-past-idle: kill_group reaps the whole group; parent survives."""
    driver = SubprocessIsolatedDriver(
        argv=[sys.executable, "-c", SCRIPT_SLEEP_PAST_IDLE],
        idle_cap=0.4,
        wall_cap=10.0,
    )
    parent_pid_before = os.getpid()
    t0 = time.monotonic()
    result = driver.run_step(ctx)
    elapsed = time.monotonic() - t0
    assert os.getpid() == parent_pid_before, "parent must survive idle kill"
    assert result.state_patch["exit_code"] == 124
    assert "idle timed out" in result.state_patch["stderr"]
    # Kill must be swift relative to wall_cap — proves kill_group fired
    # on the idle path, not the wall path.
    assert elapsed < 5.0


def test_subprocess_isolated_group_reaped_via_ps_o_pgid(ctx: StepContext, tmp_path: Path) -> None:
    """Grandchild spawned by the child is reaped: pid no longer alive
    after kill_group fires. Uses os.kill(pid, 0) with ``ps -o pgid`` fallback."""
    pidfile = tmp_path / "grandchild.pid"
    shell_script = (
        f"sleep 300 & echo $! > {pidfile}; wait"
    )
    driver = SubprocessIsolatedDriver(
        argv=["/bin/sh", "-c", shell_script],
        idle_cap=0.4,
        wall_cap=10.0,
    )
    result = driver.run_step(ctx)
    assert result.state_patch["exit_code"] == 124

    # Wait briefly for OS to finish reaping the group
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not pidfile.exists():
        time.sleep(0.05)
    assert pidfile.exists(), "grandchild never wrote its pid"
    gc_pid = int(pidfile.read_text().strip())

    # Grandchild must be dead (kill_group reaped the whole pgid).
    alive = True
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.kill(gc_pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            alive = False
            break
        except PermissionError:  # exists but not ours — still treat as gone-from-us
            alive = False
            break
    if alive:
        # Fallback to ps -o pgid as a final cross-check
        ps = subprocess.run(
            ["ps", "-o", "pgid=", "-p", str(gc_pid)],
            capture_output=True,
            text=True,
        )
        assert ps.returncode != 0 or not ps.stdout.strip(), (
            f"grandchild pid={gc_pid} survived kill_group (ps={ps.stdout!r})"
        )


# ---------------------------------------------------------------------------
# in_process: sys.exit + os._exit take the run down
# ---------------------------------------------------------------------------


def _sys_exit_step(ctx: StepContext) -> StepResult:
    sys.exit(1)
    return StepResult(next="halt")  # unreachable


def test_in_process_sys_exit_propagates_system_exit(tmp_path: Path) -> None:
    """In-process driver cannot contain sys.exit — SystemExit propagates."""
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="auto")
    driver = InProcessDriver(step_func=_sys_exit_step)
    with pytest.raises(SystemExit) as exc_info:
        driver.run_step(ctx)
    assert exc_info.value.code == 1


def test_in_process_os_exit_terminates_interpreter(tmp_path: Path) -> None:
    """In-process os._exit terminates the host interpreter — verified by
    spawning a wrapper child that uses InProcessDriver and asserting the
    child exits with code 137 (no Python exception, no cleanup)."""
    wrapper = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        from megaplan._pipeline.types import StepContext, StepResult
        from megaplan.drivers.in_process import InProcessDriver

        def step(ctx):
            os._exit(137)
            return StepResult(next="halt")

        ctx = StepContext(plan_dir=Path("."), state={}, profile=None, mode="auto")
        InProcessDriver(step_func=step).run_step(ctx)
        # If we ever get here, in-process did not actually take the run down.
        sys.exit(0)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", wrapper],
        capture_output=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert proc.returncode == 137, (
        f"in-process os._exit must terminate the interpreter with the given "
        f"code (got rc={proc.returncode}, stderr={proc.stderr!r})"
    )
