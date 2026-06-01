"""Unit tests for the event writer (megaplan/observability/events.py)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from megaplan._core.io import atomic_write_text
from megaplan.observability.events import (
    EventKind,
    EventWriter,
    _ALL_EVENT_KINDS,
    emit,
    read_events,
)


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    """Create a temporary plan directory."""
    pd = tmp_path / "test-plan"
    pd.mkdir(parents=True, exist_ok=True)
    return pd


class TestEventWriterBasic:
    """Tests (a) single emit, (b) two sequential emits."""

    def test_single_emit_init(self, plan_dir: Path) -> None:
        """Single emit produces valid JSON with seq=0, ts_utc present, ts_rel_init_s ~0 for init."""
        writer = EventWriter(plan_dir)
        event = writer.emit(EventKind.INIT, payload={"plan_name": "test"})

        assert event["seq"] == 0
        assert "ts_utc" in event
        assert event["ts_rel_init_s"] == 0.0
        assert event["kind"] == EventKind.INIT

        # Verify the file on disk
        ndjson = plan_dir / "events.ndjson"
        assert ndjson.exists()
        lines = ndjson.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["seq"] == 0
        assert parsed["kind"] == EventKind.INIT

    def test_two_sequential_emits(self, plan_dir: Path) -> None:
        """Two sequential emits produce seq 0, 1."""
        writer = EventWriter(plan_dir)
        e0 = writer.emit(EventKind.INIT)
        e1 = writer.emit(EventKind.PHASE_START, phase="plan")

        assert e0["seq"] == 0
        assert e1["seq"] == 1

        ndjson = plan_dir / "events.ndjson"
        lines = ndjson.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["seq"] == 0
        assert json.loads(lines[1])["seq"] == 1

    def test_module_level_emit(self, plan_dir: Path) -> None:
        """Module-level emit() helper works."""
        event = emit(EventKind.INIT, plan_dir=plan_dir)
        assert event["seq"] == 0
        assert event["kind"] == EventKind.INIT


class TestConcurrentEmit:
    """Tests (c) concurrent emit from two threads does not corrupt the file."""

    def test_concurrent_two_threads(self, plan_dir: Path) -> None:
        """Concurrent emit from two threads: all lines parse as JSON, seq is monotonic."""
        writer = EventWriter(plan_dir)
        num_per_thread = 50
        errors: list[Exception] = []

        def _writer(thread_id: int) -> None:
            for i in range(num_per_thread):
                try:
                    writer.emit(
                        EventKind.NOTE_ADDED,
                        payload={"thread": thread_id, "i": i},
                    )
                except Exception as e:
                    errors.append(e)

        t1 = threading.Thread(target=_writer, args=(1,))
        t2 = threading.Thread(target=_writer, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors during concurrent emit: {errors}"

        ndjson = plan_dir / "events.ndjson"
        lines = ndjson.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == num_per_thread * 2

        seqs: list[int] = []
        for line in lines:
            parsed = json.loads(line)
            assert "seq" in parsed
            seqs.append(parsed["seq"])

        # All seqs should be unique and cover 0..N-1
        assert len(set(seqs)) == len(seqs), "Duplicate seq values found"
        assert sorted(seqs) == list(range(len(seqs))), "Seq values are not monotonic 0..N-1"

    def test_concurrent_file_order_monotonic(self, plan_dir: Path) -> None:
        """Seq values in file order must be strictly increasing (no out-of-order)."""
        writer = EventWriter(plan_dir)
        num_events = 30
        barrier = threading.Barrier(3, timeout=5)

        def _writer() -> None:
            barrier.wait()
            for _ in range(num_events // 3):
                writer.emit(EventKind.NOTE_ADDED, payload={})

        threads = [threading.Thread(target=_writer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ndjson = plan_dir / "events.ndjson"
        lines = ndjson.read_text(encoding="utf-8").strip().split("\n")
        seqs = [json.loads(line)["seq"] for line in lines]

        # Must be strictly increasing in file order
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i - 1], (
                f"File order not monotonic: seq[{i}]={seqs[i]} <= seq[{i - 1}]={seqs[i - 1]}"
            )


class TestReadEvents:
    """Tests (e) read_events generator yields correct events."""

    def test_read_all_events(self, plan_dir: Path) -> None:
        writer = EventWriter(plan_dir)
        writer.emit(EventKind.INIT)
        writer.emit(EventKind.PHASE_START, phase="plan")
        writer.emit(EventKind.PHASE_END, phase="plan")

        events = list(read_events(plan_dir))
        assert len(events) == 3
        assert [e["kind"] for e in events] == [
            EventKind.INIT,
            EventKind.PHASE_START,
            EventKind.PHASE_END,
        ]

    def test_since_seq_filter(self, plan_dir: Path) -> None:
        writer = EventWriter(plan_dir)
        writer.emit(EventKind.INIT)
        writer.emit(EventKind.PHASE_START, phase="plan")
        writer.emit(EventKind.PHASE_END, phase="plan")

        events = list(read_events(plan_dir, since_seq=0))
        assert len(events) == 2
        assert events[0]["kind"] == EventKind.PHASE_START

    def test_kinds_filter(self, plan_dir: Path) -> None:
        writer = EventWriter(plan_dir)
        writer.emit(EventKind.INIT)
        writer.emit(EventKind.PHASE_START, phase="plan")
        writer.emit(EventKind.LLM_CALL_START, phase="plan")

        events = list(read_events(plan_dir, kinds=[EventKind.PHASE_START, EventKind.LLM_CALL_START]))
        assert len(events) == 2
        assert events[0]["kind"] == EventKind.PHASE_START
        assert events[1]["kind"] == EventKind.LLM_CALL_START

    def test_empty_file(self, plan_dir: Path) -> None:
        events = list(read_events(plan_dir))
        assert events == []


class TestFlockCriticalSection:
    """Tests (f) flock held across full critical section."""

    def test_slow_writer_fast_reader_seq_consistency(self, plan_dir: Path) -> None:
        """Slow writer holds lock; fast reader observes consistent seq counter state."""
        writer = EventWriter(plan_dir)
        writer.emit(EventKind.INIT)  # seed

        slow_writing = threading.Event()
        seqs_seen: list[int] = []

        def _slow_writer() -> None:
            slow_writing.set()
            time.sleep(0.05)  # give reader a head start
            for _ in range(5):
                writer.emit(EventKind.NOTE_ADDED, payload={})

        def _reader() -> None:
            slow_writing.wait()
            for _ in range(5):
                events = list(read_events(plan_dir))
                seqs_seen.append(events[-1]["seq"] if events else -1)
                time.sleep(0.02)

        wt = threading.Thread(target=_slow_writer)
        rt = threading.Thread(target=_reader)
        wt.start()
        rt.start()
        wt.join()
        rt.join()

        # Final verification: all lines parse and seqs are 0..N
        events = list(read_events(plan_dir))
        seqs = [e["seq"] for e in events]
        assert sorted(seqs) == list(range(len(seqs)))


def test_atomic_write_text_logs_warning_when_artifact_emit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    target = tmp_path / "artifact.txt"

    def _raise_emit(*args, **kwargs):
        raise RuntimeError("emit broke")

    monkeypatch.setattr("megaplan.observability.events.emit", _raise_emit)
    caplog.set_level("WARNING", logger="megaplan")

    atomic_write_text(target, "payload", _plan_dir=plan_dir)

    assert target.read_text(encoding="utf-8") == "payload"
    assert any("M3A_WARN_EMIT_ARTIFACT_WRITTEN" in record.getMessage() for record in caplog.records)


def test_evaluand_recorded_is_registered_event_kind() -> None:
    assert EventKind.EVALUAND_RECORDED == "evaluand_recorded"
    assert EventKind.EVALUAND_RECORDED in _ALL_EVENT_KINDS
    # M5-cal adds CAPABILITY_CLAIM and CALIBRATION_EXPERIMENT; R1 authority also
    # registers STATE_CACHE_DRIFT.
    assert len(_ALL_EVENT_KINDS) == 33
