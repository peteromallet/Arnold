"""Regression tests for the shannon (Claude-via-shannon-CLI) idle-output stall fix.

Background: a megaplan critique/finalize phase on a shannon-backed profile (e.g.
``partnered``, which runs ``shannon --model claude-... --output-format=stream-json``)
can establish its stream, emit some output, then STALL — the subprocess
stays alive (a packaged turn watchdog is raised above the megaplan budget) but
produces no further stdout/stderr for many minutes. The blocking reader threads
in ``run_command`` sit in ``stream.read(4096)`` with no idle bound, and the
liveness heartbeat keeps bumping the OUTER ``megaplan auto`` idle watchdog, so
nothing aborts until the coarse phase wall-clock ``worker_timeout`` (~30m+)
fires — failing the WHOLE plan.

The fix adds an inter-chunk idle-output watchdog to ``run_command`` (opt-in via
``idle_timeout``, used by the shannon worker), mirroring the hermes
``HERMES_STREAM_READ_TIMEOUT`` per-chunk read timeout. A stall surfaces promptly
as a retryable ``worker_stall`` CliError so the phase retries instead of the plan
failing. Real output (not the heartbeat) resets the bound, so a healthy
long-but-active call never trips it.

These tests drive real python subprocesses (no shannon CLI / network) so they
faithfully exercise the Popen reader-thread + watchdog path.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from megaplan.types import CliError
from megaplan.workers._impl import (
    DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS,
    _worker_stream_idle_timeout_seconds,
    run_command,
)


def test_idle_timeout_default_env_override_and_floor(monkeypatch):
    monkeypatch.delenv("SHANNON_STREAM_READ_TIMEOUT", raising=False)
    assert (
        _worker_stream_idle_timeout_seconds()
        == DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS
        == 300.0
    )

    monkeypatch.setenv("SHANNON_STREAM_READ_TIMEOUT", "200")
    assert _worker_stream_idle_timeout_seconds() == 200.0

    monkeypatch.setenv("SHANNON_STREAM_READ_TIMEOUT", "not-a-number")
    assert _worker_stream_idle_timeout_seconds() == DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS

    # A misconfigured tiny value must never drop below the floor that protects
    # a healthy slow tool turn from being aborted.
    monkeypatch.setenv("SHANNON_STREAM_READ_TIMEOUT", "0.5")
    assert _worker_stream_idle_timeout_seconds() == 30.0


def test_watchdog_fires_on_stalled_stream() -> None:
    """A subprocess that emits one chunk then goes silent (alive, no output)
    must abort via the idle-output watchdog with a retryable ``worker_stall`` —
    promptly (after ~idle_timeout), NOT after the coarse phase ``timeout``.
    """
    calls: list[tuple[str, str]] = []
    lock = threading.Lock()

    def _cb(kind: str, detail: str) -> None:
        with lock:
            calls.append((kind, detail))

    # Emit one line, then sleep silently for far longer than the idle bound but
    # well under `timeout` — models a stalled SSE stream on a live process.
    script = "import sys, time; print('streaming...'); sys.stdout.flush(); time.sleep(30)"

    start = time.monotonic()
    with pytest.raises(CliError) as excinfo:
        run_command(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            timeout=60,  # coarse phase budget — must NOT be what fires
            activity_callback=_cb,
            idle_timeout=1.0,  # tight idle bound for a fast test
        )
    elapsed = time.monotonic() - start

    assert excinfo.value.code == "worker_stall"
    # Captured pre-stall output is preserved for diagnostics.
    assert "streaming..." in excinfo.value.extra.get("raw_output", "")
    # Aborts shortly after the 1s idle bound, NOT near the 60s phase timeout,
    # and NOT after the subprocess's own 30s sleep finishes.
    assert elapsed < 10.0, f"watchdog did not abort promptly (took {elapsed:.2f}s)"


def test_watchdog_does_not_fire_on_healthy_active_stream() -> None:
    """A subprocess that keeps emitting output faster than the idle bound must
    complete normally — the watchdog must NOT trip a healthy active stream.
    """
    # Emit 12 lines spaced 0.3s (well under the 3s idle bound), total ~3.6s,
    # then exit 0. Every chunk resets last_output, so the watchdog never fires.
    # The idle bound (3s) is generous relative to interpreter cold-start so the
    # test is not flaky, yet far larger than the 0.3s inter-chunk cadence.
    script = (
        "import sys, time\n"
        "for i in range(12):\n"
        "    print('chunk', i); sys.stdout.flush(); time.sleep(0.3)\n"
    )

    result = run_command(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        timeout=60,
        activity_callback=lambda *a: None,
        idle_timeout=3.0,
    )

    assert result.returncode == 0
    assert "chunk 0" in result.stdout
    assert "chunk 9" in result.stdout


def test_heartbeat_alone_does_not_keep_a_silent_stream_alive() -> None:
    """The liveness heartbeat must NOT reset the idle-output bound: a silent
    process still trips the watchdog even though heartbeats keep firing. This is
    the precise failure that let the original stall hang — the heartbeat masked
    the stall from the OUTER watchdog, so the idle bound here must rely ONLY on
    real stdout/stderr, never the heartbeat.
    """
    calls: list[tuple[str, str]] = []
    lock = threading.Lock()

    def _cb(kind: str, detail: str) -> None:
        with lock:
            calls.append((kind, detail))

    # Silent for 30s. The 5s heartbeat WILL fire (proving the heartbeat path is
    # live), but it must not reset the idle bound, so worker_stall still raises.
    script = "import time; time.sleep(30)"

    with pytest.raises(CliError) as excinfo:
        run_command(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            timeout=60,
            activity_callback=_cb,
            idle_timeout=6.0,  # just above the 5s heartbeat interval
        )

    assert excinfo.value.code == "worker_stall"
    # Confirm a heartbeat actually fired during the wait (so we know the bound
    # held DESPITE heartbeats, not because none occurred).
    assert any(c[0] == "liveness" for c in calls), (
        f"expected a liveness heartbeat during the stall, got {calls!r}"
    )


def test_liveness_probe_keeps_buffered_live_worker_alive() -> None:
    """A buffered worker that emits NO stdout for the whole turn (the shannon
    ``--output-format=json`` failure mode) must NOT be killed by the idle bound
    while a ``liveness_probe`` reports the worker is alive and progressing.

    Models the real bug: the subprocess stays silent on stdout far past the idle
    bound, but a tmux-pane/transcript probe shows it is still working. The
    watchdog must treat the probe's progress as activity (reset the idle clock)
    and let the turn complete — bounded only by the wall-clock ``timeout``.
    """
    probe_calls = [0]

    def _always_progressing() -> bool:
        probe_calls[0] += 1
        return True  # alive + progressing on every probe

    # Silent on stdout for 6s — many multiples of the 1s idle bound — then exits
    # 0. With the legacy stdout-only bound this trips worker_stall almost
    # immediately; with the probe it must run to completion.
    script = "import time; time.sleep(6)"

    start = time.monotonic()
    result = run_command(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        timeout=60,  # generous wall-clock — must NOT fire
        activity_callback=lambda *a: None,
        idle_timeout=1.0,  # tight idle bound the probe must override
        liveness_probe=_always_progressing,
    )
    elapsed = time.monotonic() - start

    assert result.returncode == 0
    assert elapsed >= 5.0, "worker exited too early — was it killed?"
    # The idle bound expired repeatedly (~1s cadence over 6s); the probe must
    # have been consulted each time to keep the turn alive.
    assert probe_calls[0] >= 2, (
        f"liveness_probe was barely consulted ({probe_calls[0]}x); idle clock "
        "may not be deferring to it"
    )


def test_liveness_probe_still_kills_genuinely_hung_buffered_worker() -> None:
    """A buffered worker that is alive but NOT progressing (probe returns False)
    must STILL be killed promptly at the idle bound. The liveness rescue must not
    turn the watchdog into a no-op for genuinely hung/dead turns.
    """
    probe_calls = [0]

    def _not_progressing() -> bool:
        probe_calls[0] += 1
        return False  # alive process, but no real progress observed

    # Silent and idle for 30s (well under the 60s wall-clock) — a genuine hang.
    script = "import time; time.sleep(30)"

    start = time.monotonic()
    with pytest.raises(CliError) as excinfo:
        run_command(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            timeout=60,
            activity_callback=lambda *a: None,
            idle_timeout=1.0,
            liveness_probe=_not_progressing,
        )
    elapsed = time.monotonic() - start

    assert excinfo.value.code == "worker_stall"
    # Killed shortly after the idle bound, NOT after the 30s sleep or 60s budget.
    assert elapsed < 10.0, f"hung worker not killed promptly (took {elapsed:.2f}s)"
    assert probe_calls[0] >= 1, "probe was never consulted before the kill"


def test_liveness_probe_exception_is_treated_as_progress() -> None:
    """A probe that raises must never cause a false kill: the watchdog falls back
    to the conservative 'treat as progress' stance and lets the wall-clock bound
    govern. Guarantees a probe bug can never collateral-kill a live worker.
    """

    def _boom() -> bool:
        raise RuntimeError("probe blew up")

    script = "import time; time.sleep(5)"

    result = run_command(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        timeout=60,
        activity_callback=lambda *a: None,
        idle_timeout=1.0,
        liveness_probe=_boom,
    )
    assert result.returncode == 0


def test_no_idle_timeout_preserves_legacy_behavior() -> None:
    """When idle_timeout is None (codex/claude-native paths), a silent-but-alive
    subprocess must NOT be aborted early — only the coarse phase timeout governs.
    Proven by a short silent sleep completing successfully.
    """
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        cwd=Path.cwd(),
        timeout=30,
        activity_callback=lambda *a: None,
        # idle_timeout omitted -> None -> legacy single process.wait path
    )
    assert result.returncode == 0
