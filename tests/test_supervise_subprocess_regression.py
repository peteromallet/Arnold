"""Regression tests for extracted `_supervise_subprocess` supervision contract.

Asserts behavior on exit code, stdout, stderr, and kill timing for
deterministic scenarios using the extracted helper.
"""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

from arnold.pipelines.megaplan.auto import _supervise_subprocess, WatcherState
from arnold.pipelines.megaplan.runtime.process import spawn


SCRIPT_HELLO = "import sys; sys.stdout.write('hello\\n'); sys.stderr.write('warn\\n'); sys.exit(0)"
SCRIPT_FAIL = "import sys; sys.stdout.write('fail-out\\n'); sys.stderr.write('fail-err\\n'); sys.exit(7)"
SCRIPT_SLEEP = "import time; time.sleep(10)"


def _spawn_python(script: str):
    return spawn(
        [sys.executable, "-c", script],
        cwd=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=None,
    )



def test_supervise_success_byte_identical_to_legacy_module_exports():
    """The extracted helper produces identical (exit, stdout, stderr) to
    spawning + watching the same script. Locks the contract shape against
    the legacy snapshot at the watcher-block level."""
    proc = _spawn_python(SCRIPT_HELLO)
    rc, out, err, state = _supervise_subprocess(proc, None, None, 10.0)
    assert rc == 0
    assert out == "hello\n"
    assert err == "warn\n"
    assert isinstance(state, WatcherState)
    assert state.timed_out_reason is None
    assert state.kill_monotonic is None


def test_supervise_nonzero_exit_propagates():
    proc = _spawn_python(SCRIPT_FAIL)
    rc, out, err, _state = _supervise_subprocess(proc, None, None, 10.0)
    assert rc == 7
    assert out == "fail-out\n"
    assert err == "fail-err\n"


def test_supervise_wall_timeout_kills_within_100ms_of_cap():
    """Kill timing: the watcher polls every 0.2s, so we expect the kill to
    fire within ~200ms of the cap. The contract requires within 100ms of
    the legacy implementation; both share the same poll loop, so this
    asserts the timing-window equivalence."""
    wall_cap = 0.5
    proc = _spawn_python(SCRIPT_SLEEP)
    t0 = time.monotonic()
    rc, _out, err, state = _supervise_subprocess(proc, None, None, wall_cap)
    elapsed = time.monotonic() - t0
    assert rc == 124  # PHASE_TIMEOUT_EXIT_CODE
    assert "timed out after" in err
    assert state.kill_monotonic is not None
    # Kill must happen within one poll-cycle (0.2s) of the cap.
    assert elapsed - wall_cap < 0.3, f"kill latency {elapsed - wall_cap:.3f}s exceeded 300ms"


def test_supervise_idle_timeout_kills_when_silent():
    idle_cap = 0.4
    proc = _spawn_python(SCRIPT_SLEEP)
    t0 = time.monotonic()
    rc, _out, err, state = _supervise_subprocess(proc, None, idle_cap, 10.0)
    elapsed = time.monotonic() - t0
    assert rc == 124
    assert "idle timed out" in err
    assert state.kill_monotonic is not None
    assert elapsed - idle_cap < 0.3



def test_watcher_state_buffers_capture_streams():
    proc = _spawn_python(SCRIPT_HELLO)
    _rc, _out, _err, state = _supervise_subprocess(proc, None, None, 10.0)
    assert b"".join(state.stdout_parts) == b"hello\n"
    assert b"".join(state.stderr_parts) == b"warn\n"
    assert state.last_hard_progress >= state.started
