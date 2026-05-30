"""Regression test for the hermes execute-worker wedge watchdog.

Production wedge (2026-05-24/28): a `megaplan auto` execute phase routed to the
hermes worker produced NO events/output for ~17 minutes while the parent sat
alive waiting. The in-agent `stream_progress_stall` watchdog (real-char-keyed,
catches whitespace-keepalive freezes) and the shannon subprocess `idle_timeout`
watchdog (catches silent Popen turns) both missed this regime: the hermes
in-process `run_conversation` simply stopped producing chunks of ANY kind —
content, reasoning, or keepalive.

`_WorkerStallWatchdog` is the coarse, transport-agnostic backstop. It observes
the same `_StreamTracker` the heartbeat uses and, after the FULL stall timeout
of zero advancement in BOTH `tokens_emitted` and `reasoning_emitted`, calls
`agent.interrupt()` and flags the trip so `_run_attempt` re-raises it as a
retryable `worker_stall`.

These tests are fully in-process (no network, no real AIAgent): a fake agent
emits a few chunks through the tracker, then goes fully silent. With the
watchdog the call aborts within the (short, test-only) timeout; WITHOUT it the
same fake agent hangs (proven by a thread that never completes within a bound).
"""

from __future__ import annotations

import threading
import time

import pytest

from megaplan.types import CliError
from megaplan.workers.hermes import (
    DEFAULT_WORKER_STALL_TIMEOUT_SECONDS,
    _StreamTracker,
    _WorkerStallWatchdog,
    _worker_stall_timeout_seconds,
)


def test_worker_stall_timeout_default_env_override_and_floor(monkeypatch):
    monkeypatch.delenv("HERMES_WORKER_STALL_TIMEOUT", raising=False)
    assert (
        _worker_stall_timeout_seconds()
        == DEFAULT_WORKER_STALL_TIMEOUT_SECONDS
        == 300.0
    )

    monkeypatch.setenv("HERMES_WORKER_STALL_TIMEOUT", "120")
    assert _worker_stall_timeout_seconds() == 120.0

    monkeypatch.setenv("HERMES_WORKER_STALL_TIMEOUT", "not-a-number")
    assert _worker_stall_timeout_seconds() == DEFAULT_WORKER_STALL_TIMEOUT_SECONDS

    # A misconfigured tiny value must never drop below the 60s floor that
    # protects a healthy-but-slow long turn from being false-aborted.
    monkeypatch.setenv("HERMES_WORKER_STALL_TIMEOUT", "1")
    assert _worker_stall_timeout_seconds() == 60.0


class _FakeAgent:
    """Mimics AIAgent's interrupt contract for the wedge regime.

    ``run_conversation`` emits ``real_chunks`` real chunks through the tracker
    (advancing progress, resetting the watchdog clock each time), then goes
    fully SILENT — no further chunks of any kind — blocking until either
    ``interrupt()`` is called (the watchdog path) or a hard cap elapses (the
    "would hang" proof for the no-watchdog control).

    On ``interrupt()`` it behaves like the real agent loop: it releases the
    block and returns a result flagged ``interrupted=True`` (the real agent
    swallows InterruptedError internally and returns this shape).
    """

    def __init__(self, tracker: _StreamTracker, *, real_chunks: int = 5,
                 hang_cap: float = 30.0) -> None:
        self._tracker = tracker
        self._real_chunks = real_chunks
        self._hang_cap = hang_cap
        self._interrupted = threading.Event()
        self.interrupt_calls = 0

    def interrupt(self, message: str | None = None) -> None:
        self.interrupt_calls += 1
        self._interrupted.set()

    def clear_interrupt(self) -> None:
        self._interrupted.clear()

    def run_conversation(self) -> dict:
        for i in range(self._real_chunks):
            time.sleep(0.02)
            self._tracker(f"real-token-{i}")  # advances tokens_emitted
        # Phase 2: full silence. No chunk of any kind. Block until interrupted
        # (watchdog) or the hard cap (no-watchdog control proving the hang).
        fired = self._interrupted.wait(timeout=self._hang_cap)
        return {
            "final_response": "Operation interrupted." if fired else "late answer",
            "messages": [],
            "interrupted": fired,
        }


def _drive(agent: _FakeAgent, tracker: _StreamTracker,
           watchdog: _WorkerStallWatchdog | None):
    """Mirror _run_attempt's run + post-call stall check in miniature."""
    from contextlib import nullcontext

    ctx = watchdog if watchdog is not None else nullcontext()
    with ctx:
        result = agent.run_conversation()
    if watchdog is not None and watchdog.tripped:
        raise CliError(
            "worker_stall",
            f"stalled: {watchdog.seconds_since_progress:.0f}s no progress "
            f"(tokens={watchdog.tokens_at_trip}, reasoning={watchdog.reasoning_at_trip})",
            extra={"raw_output": ""},
        )
    return result


def test_watchdog_aborts_silent_worker_with_retryable_worker_stall():
    """The wedge: real chunks, then full silence. The watchdog must abort it
    and surface a RETRYABLE worker_stall shortly after the (short, test-only)
    timeout — NOT after the fake agent's 30s hang cap."""
    tracker = _StreamTracker()
    agent = _FakeAgent(tracker, real_chunks=5, hang_cap=30.0)
    watchdog = _WorkerStallWatchdog(agent, tracker, timeout=1.0)

    start = time.monotonic()
    with pytest.raises(CliError) as excinfo:
        _drive(agent, tracker, watchdog)
    elapsed = time.monotonic() - start

    assert excinfo.value.code == "worker_stall"
    assert agent.interrupt_calls >= 1, "watchdog never called agent.interrupt()"
    # Aborts shortly after the 1s timeout, NOT after the 30s hang cap.
    assert elapsed < 8.0, f"watchdog did not abort promptly (took {elapsed:.2f}s)"
    # The progress made before the freeze is captured for diagnostics.
    assert watchdog.tokens_at_trip == 5


def test_silent_worker_HANGS_without_the_watchdog():
    """Control: the SAME fake agent, run WITHOUT the watchdog, never completes
    within a bound far larger than the watchdog's timeout — proving the wedge
    really hangs and that the watchdog is what breaks it."""
    tracker = _StreamTracker()
    agent = _FakeAgent(tracker, real_chunks=5, hang_cap=30.0)

    done = threading.Event()

    def _runner():
        try:
            _drive(agent, tracker, None)  # no watchdog
        finally:
            done.set()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    # The watchdog test aborts in <8s; give the no-watchdog control 5s — far
    # longer than that — and it must STILL be hung (no interrupt was ever fired).
    completed = done.wait(timeout=5.0)
    assert not completed, "expected the silent worker to hang without the watchdog"
    assert agent.interrupt_calls == 0
    # Release the daemon so it doesn't linger past the test.
    agent.interrupt()


def test_watchdog_does_not_abort_a_healthy_streaming_worker():
    """Conservative guard: a worker that keeps emitting chunks faster than the
    timeout must run to completion — the watchdog requires the FULL timeout of
    ZERO progress, so a steady (even slow) stream is never killed."""
    tracker = _StreamTracker()

    class _HealthyAgent:
        interrupt_calls = 0

        def interrupt(self, message=None):
            self.interrupt_calls += 1

        def clear_interrupt(self):
            pass

        def run_conversation(self):
            # 10 chunks at 0.1s (well under the 1s timeout); each resets the
            # watchdog clock, so it never trips.
            for i in range(10):
                time.sleep(0.1)
                tracker(f"tok-{i}")
            return {"final_response": "done", "messages": [], "interrupted": False}

    agent = _HealthyAgent()
    watchdog = _WorkerStallWatchdog(agent, tracker, timeout=1.0)
    result = _drive(agent, tracker, watchdog)

    assert result["final_response"] == "done"
    assert watchdog.tripped is False
    assert agent.interrupt_calls == 0


def test_watchdog_clock_resets_on_reasoning_only_progress():
    """A reasoning model streaming ONLY reasoning_content (no content delta yet)
    must NOT be aborted — reasoning advancement is real progress that resets the
    clock, mirroring the heartbeat's dual-counter logic."""
    tracker = _StreamTracker()

    class _ReasoningAgent:
        interrupt_calls = 0

        def interrupt(self, message=None):
            self.interrupt_calls += 1

        def clear_interrupt(self):
            pass

        def run_conversation(self):
            for i in range(10):
                time.sleep(0.1)
                tracker.on_reasoning(f"thinking-{i}")  # reasoning only
            return {"final_response": "{}", "messages": [], "interrupted": False}

    agent = _ReasoningAgent()
    watchdog = _WorkerStallWatchdog(agent, tracker, timeout=1.0)
    _drive(agent, tracker, watchdog)

    assert watchdog.tripped is False
    assert agent.interrupt_calls == 0
