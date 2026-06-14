"""Regression test for the dueling-drivers single-driver lock.

Production stall (observed live): two `megaplan auto --plan X` processes on the
SAME plan contended over plan state and pinned the run at a fixed file count for
~hours — a zero-progress plateau that masquerades as a stall. The short
per-step `plan_lock` did not prevent it: the driver releases that lock between
phases, so two drivers interleave at step boundaries.

`driver_lock` is a per-plan, driver-LIFETIME advisory `fcntl.flock` (same
primitive as `plan_lock`) held for the whole `auto` process. A second live
acquisition is refused with a `driver_locked` CliError naming the holder pid; a
stale lockfile (dead holder pid) is reclaimed and the new driver proceeds.

The "live holder" case uses a real subprocess (flock is per-open-file-handle and
re-entrant within one process, so we can't fake contention in-process). The
"stale lock" case writes a dead pid into the lockfile — the kernel has already
released the flock when that process exited, so flock itself doesn't block; the
lingering pidfile must not wedge a new driver.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core import driver_lock, driver_lock_path
from arnold.pipelines.megaplan._core.state import _pid_is_live, _read_lock_pid
from arnold.pipelines.megaplan.types import CliError


WORKTREE = str(Path(__file__).resolve().parents[1])


def _spawn_lock_holder(plan_dir: Path, hold_seconds: float = 30.0) -> subprocess.Popen:
    """Spawn a child process that acquires driver_lock and holds it.

    Prints ``LOCKED`` to stdout once the lock is held, then sleeps. The parent
    waits for that line before asserting contention, avoiding a race.
    """
    code = textwrap.dedent(
        f"""
        import sys, time
        from pathlib import Path
        from arnold.pipelines.megaplan._core import driver_lock
        with driver_lock(Path({str(plan_dir)!r})):
            sys.stdout.write("LOCKED\\n")
            sys.stdout.flush()
            time.sleep({hold_seconds})
        """
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = WORKTREE + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    # Block until the child confirms it holds the lock (or dies).
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if line.strip() == "LOCKED":
            return proc
        if proc.poll() is not None:
            err = proc.stderr.read()
            raise AssertionError(f"lock-holder child exited early: {err}")
    proc.kill()
    raise AssertionError("lock-holder child never acquired the lock in time")


def test_second_live_driver_is_refused_naming_holder_pid(tmp_path):
    """A second driver_lock acquisition while a LIVE holder owns it is refused
    with a driver_locked CliError that names the holding pid."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    holder = _spawn_lock_holder(plan_dir, hold_seconds=30.0)
    try:
        with pytest.raises(CliError) as excinfo:
            with driver_lock(plan_dir):
                pass  # should never get here — the lock is held by `holder`
        err = excinfo.value
        assert err.code == "driver_locked"
        assert str(holder.pid) in err.message, (
            f"error did not name holder pid {holder.pid}: {err.message}"
        )
        assert err.extra.get("holder_pid") == holder.pid
    finally:
        holder.kill()
        holder.wait(timeout=5.0)


def test_driver_lock_released_lets_a_new_driver_proceed(tmp_path):
    """Once the live holder exits (releasing the flock), a fresh driver_lock
    acquisition succeeds — the lock is not sticky."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    holder = _spawn_lock_holder(plan_dir, hold_seconds=2.0)
    holder.wait(timeout=10.0)  # let it run its course and release the lock

    acquired = False
    with driver_lock(plan_dir):
        acquired = True
        # We now hold it and recorded our own pid.
        assert _read_lock_pid(driver_lock_path(plan_dir)) == os.getpid()
    assert acquired


def test_stale_lockfile_with_dead_pid_is_reclaimed(tmp_path):
    """A lingering lockfile whose recorded pid is DEAD must be reclaimed: the
    kernel already dropped the flock when that process exited, so a new driver
    acquires the lock and overwrites the stale pid with its own."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    lock_path = driver_lock_path(plan_dir)
    dead_pid = _find_dead_pid()
    lock_path.write_text(f"{dead_pid}\n", encoding="utf-8")
    assert _pid_is_live(dead_pid) is False

    # No live flock holder exists (only a stale pidfile), so this must succeed
    # and reclaim the lock, replacing the dead pid with ours.
    with driver_lock(plan_dir):
        assert _read_lock_pid(lock_path) == os.getpid()


def _find_dead_pid() -> int:
    """Return a pid that is not currently live (for the stale-lock test)."""
    # Spawn a trivial child, reap it, and reuse its now-dead pid. Far more
    # robust than guessing a high integer that might happen to be live.
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10.0)
    pid = proc.pid
    # Give the OS a beat to fully tear it down, then confirm it's dead.
    for _ in range(50):
        if not _pid_is_live(pid):
            return pid
        time.sleep(0.05)
    pytest.skip("could not obtain a reliably-dead pid on this platform")
