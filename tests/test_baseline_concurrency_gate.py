"""Host-wide concurrency gate for the finalize test-baseline suite run.

Reproduces the incident: several megaplan chains run on one box. Each one's
``finalize`` phase runs the project's FULL pytest suite to capture a regression
baseline. With 3 chains in finalize at once that's 3 simultaneous full-suite
runs (~10 pytest processes) that saturate the host's CPU — so every chain's
other work (notably the Shannon ``claude`` turn) is starved, finalize phases
time out and RETRY, re-running baselines, and the box never recovers.

The gate (:mod:`megaplan.orchestration.baseline_gate`) makes concurrent baseline
runs QUEUE for a slot instead of all running at once. Unlike the subscription
gate it DEFAULTS ON (serialize, max=1) and DEGRADES GRACEFULLY on slot-wait
timeout (skip the baseline, proceed "baseline unavailable") rather than raising —
re-queuing a full-suite run is exactly the storm being prevented.

These tests prove: default serializes (max=1), serialization to ``max_concurrent``,
``<= 0`` disables, large value relaxes, a saturation timeout DEGRADES (does not
raise / hang), and the wait runs on an injectable clock outside any phase timeout.
"""

from __future__ import annotations

import threading
import time

from megaplan.orchestration.baseline_gate import (
    BaselineSlot,
    baseline_max_concurrent,
    baseline_slot,
)


def test_default_is_serialize_max_one(monkeypatch, tmp_path):
    """Unset MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT => 1 (serialize), NOT disabled."""
    monkeypatch.delenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", raising=False)
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    assert baseline_max_concurrent() == 1
    with baseline_slot(poll_interval=0.01) as slot:
        assert slot is BaselineSlot.HELD
        assert slot.should_run is True


def test_invalid_value_falls_back_to_serialize(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "garbage")
    assert baseline_max_concurrent() == 1


def test_non_positive_disables(monkeypatch, tmp_path):
    """A value <= 0 explicitly DISABLES the gate (run unguarded)."""
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    for raw in ("0", "-1"):
        monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", raw)
        assert baseline_max_concurrent() <= 0
        with baseline_slot() as slot:
            assert slot is BaselineSlot.DISABLED
            assert slot.should_run is True


def test_large_value_relaxes(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "64")
    assert baseline_max_concurrent() == 64
    with baseline_slot(poll_interval=0.01) as slot:
        assert slot is BaselineSlot.HELD


def test_gate_serializes_to_max_concurrent(monkeypatch, tmp_path):
    """With max=2, at most 2 baseline runs hold a slot simultaneously."""
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "2")
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "30")

    concurrent = 0
    peak = 0
    lock = threading.Lock()
    start = threading.Barrier(5)

    def worker():
        nonlocal concurrent, peak
        start.wait()
        with baseline_slot(poll_interval=0.01) as slot:
            assert slot is BaselineSlot.HELD
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

    assert peak <= 2, f"gate let {peak} baselines run concurrently with max=2"
    assert peak >= 1


def test_default_serialize_holds_at_most_one(monkeypatch, tmp_path):
    """The whole point: with the default (max=1) only ONE baseline runs at a time."""
    monkeypatch.delenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", raising=False)
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "30")

    concurrent = 0
    peak = 0
    lock = threading.Lock()
    start = threading.Barrier(4)

    def worker():
        nonlocal concurrent, peak
        start.wait()
        with baseline_slot(poll_interval=0.01) as slot:
            assert slot is BaselineSlot.HELD
            with lock:
                concurrent += 1
                peak = max(peak, concurrent)
            time.sleep(0.05)
            with lock:
                concurrent -= 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert peak == 1, f"default gate let {peak} baselines run concurrently (want 1)"


def test_saturation_degrades_gracefully_does_not_raise(monkeypatch, tmp_path):
    """When the slot is held and none frees, acquire DEGRADES (skip baseline),
    rather than raising or hanging. This is the core no-new-deadlock guarantee."""
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "1")
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "5")

    fake_now = [0.0]
    slept = []

    def fake_monotonic():
        return fake_now[0]

    def fake_sleep(seconds):
        slept.append(seconds)
        fake_now[0] += seconds  # advance the virtual clock past the deadline

    # Hold the single slot in a separate (real-FD) thread for the whole test.
    holder_in = threading.Event()
    release = threading.Event()

    def holder():
        with baseline_slot(poll_interval=0.01):
            holder_in.set()
            release.wait(timeout=10)

    h = threading.Thread(target=holder)
    h.start()
    assert holder_in.wait(timeout=5)

    degraded = None
    with baseline_slot(
        poll_interval=1.0, sleep=fake_sleep, monotonic=fake_monotonic
    ) as slot:
        degraded = slot

    assert degraded is BaselineSlot.DEGRADED
    assert degraded.should_run is False, "DEGRADED must signal 'skip the baseline'"
    assert slept, "expected the gate to wait (sleep) before degrading"

    release.set()
    h.join(timeout=5)


def test_queue_wait_uses_injected_clock_not_real_time(monkeypatch, tmp_path):
    """The acquire/wait loop runs on the injected clock and acquires a slot held
    by a separate FD as soon as it is released — all before the suite (and its
    own timeout clock) starts, so the wait never burns the phase timeout."""
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "1")
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "100")

    holder_in = threading.Event()
    release = threading.Event()

    def holder():
        with baseline_slot(poll_interval=0.01):
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
            release.set()
            h.join(timeout=5)

    t0 = time.monotonic()
    with baseline_slot(
        poll_interval=1.0, sleep=fake_sleep, monotonic=fake_monotonic
    ) as slot:
        assert slot is BaselineSlot.HELD
    wall = time.monotonic() - t0

    assert polls["n"] >= 1, "expected the gate to queue (sleep) at least once"
    assert fake_now[0] < 100.0  # deadline never hit
    assert wall < 5.0


def test_slot_released_when_holder_process_fd_closes(monkeypatch, tmp_path):
    """flock semantics: a slot held by one FD is reacquirable once that FD is
    closed (the kernel auto-releases on the holder dying / closing)."""
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "1")
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", str(tmp_path))
    monkeypatch.setenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "5")

    # Hold and release once...
    with baseline_slot(poll_interval=0.01) as slot:
        assert slot is BaselineSlot.HELD
    # ...the slot is free again, so a second acquire succeeds immediately.
    with baseline_slot(poll_interval=0.01) as slot:
        assert slot is BaselineSlot.HELD
