"""Host-wide subscription gate for the shared ``claude`` CLI subscription.

Reproduces the incident: several megaplan chains share ONE ``claude`` CLI
subscription on a box. When over-subscribed, a ``finalize`` Shannon turn gets no
slot, emits no tokens, and the liveness probe reads it as a hang — burning the
phase wall timeout, which for non-execute phases is a TERMINAL ``phase_timeout``
→ ``failed``.

The gate (:mod:`megaplan.workers.subscription_gate`) makes concurrent turns
QUEUE for a slot instead of all starving, and the queue-wait happens OUTSIDE the
turn's ``run_command`` timeout window so it never burns the phase timeout. These
tests prove: serialization to ``max_concurrent``, disabled = no-op, and that a
saturation timeout raises (which ``run_turn`` maps to a retryable
``worker_stall``, NOT a terminal phase failure).
"""

from __future__ import annotations

import threading
import time

import pytest

from arnold.pipelines.megaplan.workers.subscription_gate import (
    SubscriptionSlotTimeout,
    max_concurrent,
    subscription_slot,
)


def test_disabled_by_default_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", raising=False)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_DIR", str(tmp_path))
    assert max_concurrent() == 0
    with subscription_slot() as held:
        assert held is False  # no real slot held; ran unguarded


def test_non_positive_disables(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_DIR", str(tmp_path))
    for raw in ("0", "-1", "garbage"):
        monkeypatch.setenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", raw)
        assert max_concurrent() == 0
        with subscription_slot() as held:
            assert held is False


def test_gate_serializes_to_max_concurrent(monkeypatch, tmp_path):
    """With max=2, at most 2 turns hold a slot simultaneously."""
    monkeypatch.setenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", "2")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_WAIT_SECONDS", "30")

    concurrent = 0
    peak = 0
    lock = threading.Lock()
    start = threading.Barrier(5)

    def worker():
        nonlocal concurrent, peak
        start.wait()
        with subscription_slot(poll_interval=0.01) as held:
            assert held is True
            with lock:
                concurrent += 1
                peak = max(peak, concurrent)
            time.sleep(0.05)
            with lock:
                concurrent -= 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert peak <= 2, f"gate let {peak} turns run concurrently with max=2"
    assert peak >= 1


def test_saturation_raises_timeout(monkeypatch, tmp_path):
    """When every slot is held and none frees, acquire raises (→ retryable)."""
    monkeypatch.setenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_WAIT_SECONDS", "5")

    fake_now = [0.0]
    slept = []

    def fake_monotonic():
        return fake_now[0]

    def fake_sleep(seconds):
        slept.append(seconds)
        fake_now[0] += seconds  # advance the virtual clock past the deadline

    # Hold the single slot in a separate thread for the whole test.
    holder_in = threading.Event()
    release = threading.Event()

    def holder():
        with subscription_slot(poll_interval=0.01):
            holder_in.set()
            release.wait(timeout=10)

    h = threading.Thread(target=holder)
    h.start()
    assert holder_in.wait(timeout=5)

    with pytest.raises(SubscriptionSlotTimeout):
        with subscription_slot(
            poll_interval=1.0, sleep=fake_sleep, monotonic=fake_monotonic
        ):
            pass  # pragma: no cover - should not enter the block

    release.set()
    h.join(timeout=5)
    assert slept, "expected the gate to wait (sleep) before timing out"


def test_queue_wait_uses_injected_clock_not_real_time(monkeypatch, tmp_path):
    """The acquire/wait loop runs on the injected clock and frees a slot held by
    a separate process-FD as soon as it is released.

    This pins the structural guarantee that matters for the incident: the
    wait-to-acquire is a self-contained loop that runs to completion BEFORE
    run_turn starts the turn's run_command timeout. We hold the only slot, then
    release it after a couple of virtual polls and confirm acquire then
    succeeds — all without burning real wall time on any phase-timeout clock.
    """
    monkeypatch.setenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_SHANNON_SLOT_WAIT_SECONDS", "100")

    holder_in = threading.Event()
    release = threading.Event()

    def holder():
        with subscription_slot(poll_interval=0.01):
            holder_in.set()
            release.wait(timeout=10)

    h = threading.Thread(target=holder)
    h.start()
    assert holder_in.wait(timeout=5)

    fake_now = [0.0]
    polls = {"n": 0}

    def fake_monotonic():
        return fake_now[0]

    def fake_sleep(seconds):
        polls["n"] += 1
        fake_now[0] += seconds
        if polls["n"] == 2:
            # Release the held slot mid-wait; the next acquire attempt succeeds.
            release.set()
            h.join(timeout=5)

    t0 = time.monotonic()
    with subscription_slot(
        poll_interval=1.0, sleep=fake_sleep, monotonic=fake_monotonic
    ) as held:
        assert held is True
    wall = time.monotonic() - t0

    assert polls["n"] >= 1, "expected the gate to queue (sleep) at least once"
    # Virtual clock advanced (polls * 1.0s) but the deadline (100s) was never hit.
    assert fake_now[0] < 100.0
    assert wall < 5.0
