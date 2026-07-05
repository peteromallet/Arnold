"""Tests for ``arnold.runtime.event_journal`` reader APIs.

Covers both :func:`read_event_journal` (eager) and
:func:`stream_event_journal` (lazy iterator), proving parity on
in-order fixtures and correct handling of missing files, blank lines,
and JSON-decode errors.
"""

from __future__ import annotations

import json
from pathlib import Path
import threading

from arnold.runtime.event_journal import (
    BackendEventJournal,
    BackendEventSink,
    read_event_journal,
    read_event_journal_paged,
    stream_event_journal,
)


def _write_ndjson(artifact_root: Path, lines: list[str]) -> None:
    """Write lines to ``events.ndjson`` under *artifact_root*."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    ndjson = artifact_root / "events.ndjson"
    ndjson.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_event(seq: int, kind: str = "test", **extra) -> dict:
    """Return a minimal event dict with *seq* and *kind*."""
    event: dict = {
        "seq": seq,
        "schema_version": 1,
        "ts_utc": "2026-01-01T00:00:00+00:00",
        "ts_rel_init_s": 0.0,
        "kind": kind,
        "payload": {},
    }
    event.update(extra)
    return event


# ── Missing-file behaviour ─────────────────────────────────────────────


def test_read_event_journal_missing_file_returns_empty_list(tmp_path: Path) -> None:
    result = read_event_journal(tmp_path / "nonexistent")
    assert result == []


def test_stream_event_journal_missing_file_yields_nothing(tmp_path: Path) -> None:
    result = list(stream_event_journal(tmp_path / "nonexistent"))
    assert result == []


# ── Round-trip parity ───────────────────────────────────────────────────


def test_stream_and_eager_parity_on_ordered_fixture(tmp_path: Path) -> None:
    events = [
        _make_event(0, kind="init", payload={"phase": "start"}),
        _make_event(1, kind="step", payload={"step": "plan"}),
        _make_event(2, kind="step", payload={"step": "review"}),
        _make_event(3, kind="halt"),
    ]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))

    assert eager == streamed
    assert len(eager) == 4
    assert [e["seq"] for e in eager] == [0, 1, 2, 3]


def test_stream_and_eager_parity_single_event(tmp_path: Path) -> None:
    event = _make_event(0, kind="single")
    _write_ndjson(tmp_path, [json.dumps(event, sort_keys=True)])

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))

    assert eager == streamed
    assert len(eager) == 1


# ── Blank-line skipping ─────────────────────────────────────────────────


def test_blank_lines_skipped_in_eager_read(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0, kind="first"), sort_keys=True),
        "   ",
        json.dumps(_make_event(1, kind="second"), sort_keys=True),
        "",
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal(tmp_path)
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["first", "second"]


def test_blank_lines_skipped_in_stream(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0, kind="first"), sort_keys=True),
        "   ",
        json.dumps(_make_event(1, kind="second"), sort_keys=True),
        "",
    ]
    _write_ndjson(tmp_path, lines)

    result = list(stream_event_journal(tmp_path))
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["first", "second"]


def test_blank_lines_parity(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0), sort_keys=True),
        "    ",
        "",
        json.dumps(_make_event(1), sort_keys=True),
        "",
    ]
    _write_ndjson(tmp_path, lines)

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))
    assert eager == streamed


# ── JSON-decode error skipping ──────────────────────────────────────────


def test_bad_json_lines_skipped_in_eager_read(tmp_path: Path) -> None:
    lines = [
        json.dumps(_make_event(0, kind="ok"), sort_keys=True),
        "{not valid json",
        json.dumps(_make_event(1, kind="also_ok"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal(tmp_path)
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["ok", "also_ok"]


def test_bad_json_lines_skipped_in_stream(tmp_path: Path) -> None:
    lines = [
        json.dumps(_make_event(0, kind="ok"), sort_keys=True),
        "{not valid json",
        json.dumps(_make_event(1, kind="also_ok"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = list(stream_event_journal(tmp_path))
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["ok", "also_ok"]


def test_bad_json_parity(tmp_path: Path) -> None:
    lines = [
        json.dumps(_make_event(0), sort_keys=True),
        "{broken",
        "[also broken",
        json.dumps(_make_event(1), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))
    assert eager == streamed


# ── Empty file ──────────────────────────────────────────────────────────


def test_empty_file_returns_empty(tmp_path: Path) -> None:
    _write_ndjson(tmp_path, [])

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))

    assert eager == []
    assert streamed == []


# ── Lazy iteration proof ────────────────────────────────────────────────


def test_stream_is_lazy(tmp_path: Path) -> None:
    """Prove stream_event_journal yields lazily without consuming all."""
    events = [_make_event(i) for i in range(10)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    stream = stream_event_journal(tmp_path)
    # Consume only the first 3 events.
    first_three = []
    for i, event in enumerate(stream):
        first_three.append(event)
        if i >= 2:
            break

    assert len(first_three) == 3
    assert [e["seq"] for e in first_three] == [0, 1, 2]


def test_stream_yields_in_file_order(tmp_path: Path) -> None:
    """Events are yielded in file order, matching monotonic seq."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    streamed = list(stream_event_journal(tmp_path))
    assert [e["seq"] for e in streamed] == [0, 1, 2, 3, 4]


# ── Combined edge cases ─────────────────────────────────────────────────


def test_mixed_valid_blank_and_bad_lines(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0, kind="a"), sort_keys=True),
        "{bad",
        "   ",
        json.dumps(_make_event(1, kind="b"), sort_keys=True),
        "",
        "[also bad",
        json.dumps(_make_event(2, kind="c"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    eager = read_event_journal(tmp_path)
    streamed = list(stream_event_journal(tmp_path))

    assert eager == streamed
    assert len(eager) == 3
    assert [e["kind"] for e in eager] == ["a", "b", "c"]


# ── read_event_journal_paged: missing-file ──────────────────────────────


def test_paged_missing_file_returns_empty(tmp_path: Path) -> None:
    result = read_event_journal_paged(tmp_path / "nonexistent")
    assert result == []


def test_paged_missing_file_with_cursor_returns_empty(tmp_path: Path) -> None:
    result = read_event_journal_paged(tmp_path / "nonexistent", since_seq=0)
    assert result == []


# ── read_event_journal_paged: cursor reads (since_seq) ──────────────────


def test_paged_since_seq_excludes_boundary(tmp_path: Path) -> None:
    """since_seq=1 returns only events with seq > 1."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, since_seq=1)
    assert [e["seq"] for e in result] == [2, 3, 4]


def test_paged_since_seq_all_excluded(tmp_path: Path) -> None:
    """since_seq=4 with only seq 0-4 returns empty."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, since_seq=4)
    assert result == []


def test_paged_since_seq_negative(tmp_path: Path) -> None:
    """since_seq=-1 returns all events (all seq >= 0 > -1)."""
    events = [_make_event(i) for i in range(3)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, since_seq=-1)
    assert len(result) == 3


# ── read_event_journal_paged: range reads (from_seq + to_seq) ───────────


def test_paged_from_seq_inclusive(tmp_path: Path) -> None:
    """from_seq=2 includes event with seq=2."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=2)
    assert [e["seq"] for e in result] == [2, 3, 4]


def test_paged_to_seq_exclusive(tmp_path: Path) -> None:
    """to_seq=3 excludes event with seq=3 (half-open [from_seq, to_seq))."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=1, to_seq=3)
    assert [e["seq"] for e in result] == [1, 2]


def test_paged_range_empty_when_from_equals_to(tmp_path: Path) -> None:
    """[2, 2) is empty."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=2, to_seq=2)
    assert result == []


def test_paged_range_open_upper(tmp_path: Path) -> None:
    """from_seq with no to_seq includes all from that point."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=3)
    assert [e["seq"] for e in result] == [3, 4]


def test_paged_to_seq_only_returns_all_below(tmp_path: Path) -> None:
    """to_seq without from_seq returns all events with seq < to_seq."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, to_seq=3)
    assert [e["seq"] for e in result] == [0, 1, 2]


# ── read_event_journal_paged: limits ─────────────────────────────────────


def test_paged_limit_truncates(tmp_path: Path) -> None:
    events = [_make_event(i) for i in range(10)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, limit=3)
    assert len(result) == 3
    assert [e["seq"] for e in result] == [0, 1, 2]


def test_paged_limit_with_range(tmp_path: Path) -> None:
    """limit applies after filtering to the range window."""
    events = [_make_event(i) for i in range(10)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=3, to_seq=10, limit=2)
    assert len(result) == 2
    assert [e["seq"] for e in result] == [3, 4]


def test_paged_limit_larger_than_window_returns_all(tmp_path: Path) -> None:
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, from_seq=1, to_seq=3, limit=10)
    assert len(result) == 2
    assert [e["seq"] for e in result] == [1, 2]


def test_paged_limit_zero_returns_one_event(tmp_path: Path) -> None:
    """limit=0: code appends-first-then-checks, so the first event sneaks in."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, limit=0)
    # Current implementation appends then checks len(page) >= limit,
    # so with limit=0 the first event is returned before the break.
    assert len(result) == 1


def test_paged_limit_reached_exact(tmp_path: Path) -> None:
    """When limit matches exactly the number of events, returns all."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, limit=5)
    assert len(result) == 5


# ── read_event_journal_paged: sort_page ──────────────────────────────────


def test_paged_sort_page_false_returns_file_order(tmp_path: Path) -> None:
    """Default sort_page=False returns file order (which is monotonic seq)."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, sort_page=False)
    assert [e["seq"] for e in result] == [0, 1, 2, 3, 4]


def test_paged_sort_page_true_sorts_by_seq(tmp_path: Path) -> None:
    """sort_page=True sorts events by seq ascending."""
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path, sort_page=True)
    assert [e["seq"] for e in result] == [0, 1, 2, 3, 4]


def test_paged_sort_page_distinguishes_file_order_from_sorted_order(
    tmp_path: Path,
) -> None:
    """Write events in reverse seq order, prove file-order ≠ sorted-order."""
    # Write seq 4,3,2,1,0 in that file order.
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in reversed(events)]
    _write_ndjson(tmp_path, lines)

    unsorted = read_event_journal_paged(tmp_path, sort_page=False)
    assert [e["seq"] for e in unsorted] == [4, 3, 2, 1, 0]

    sorted_result = read_event_journal_paged(tmp_path, sort_page=True)
    assert [e["seq"] for e in sorted_result] == [0, 1, 2, 3, 4]


# ── read_event_journal_paged: malformed-line / blank-line skipping ───────


def test_paged_skips_blank_lines(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0, kind="a"), sort_keys=True),
        "   ",
        json.dumps(_make_event(1, kind="b"), sort_keys=True),
        "",
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path)
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["a", "b"]


def test_paged_skips_bad_json_lines(tmp_path: Path) -> None:
    lines = [
        json.dumps(_make_event(0, kind="ok"), sort_keys=True),
        "{not valid json",
        json.dumps(_make_event(1, kind="also_ok"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path)
    assert len(result) == 2
    assert [e["kind"] for e in result] == ["ok", "also_ok"]


def test_paged_skips_mixed_blank_and_bad_lines(tmp_path: Path) -> None:
    lines = [
        "",
        json.dumps(_make_event(0, kind="a"), sort_keys=True),
        "{bad",
        "   ",
        json.dumps(_make_event(1, kind="b"), sort_keys=True),
        "",
        "[also bad",
        json.dumps(_make_event(2, kind="c"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path)
    assert len(result) == 3
    assert [e["kind"] for e in result] == ["a", "b", "c"]


# ── read_event_journal_paged: error conditions ───────────────────────────


def test_paged_since_seq_and_from_seq_mutually_exclusive(tmp_path: Path) -> None:
    import pytest

    events = [_make_event(i) for i in range(3)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    with pytest.raises(ValueError, match="mutually exclusive"):
        read_event_journal_paged(tmp_path, since_seq=1, from_seq=1)


def test_paged_negative_limit_raises_value_error(tmp_path: Path) -> None:
    import pytest

    events = [_make_event(i) for i in range(3)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    with pytest.raises(ValueError, match="limit must be non-negative"):
        read_event_journal_paged(tmp_path, limit=-1)


# ── read_event_journal_paged: edge cases ─────────────────────────────────


def test_paged_no_args_returns_all_events_in_file_order(tmp_path: Path) -> None:
    events = [_make_event(i) for i in range(5)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal_paged(tmp_path)
    assert len(result) == 5
    assert [e["seq"] for e in result] == [0, 1, 2, 3, 4]


# ── Public re-export imports ─────────────────────────────────────────────


def test_read_event_journal_paged_importable_from_event_journal() -> None:
    from arnold.runtime.event_journal import read_event_journal_paged as r

    assert callable(r)


def test_read_event_journal_paged_importable_from_runtime() -> None:
    from arnold.runtime import read_event_journal_paged as r

    assert callable(r)


def test_read_event_journal_paged_importable_from_kernel_fold() -> None:
    from arnold.kernel.fold import read_event_journal_paged as r

    assert callable(r)


def test_all_three_readers_in_runtime_all() -> None:
    from arnold.runtime import __all__ as runtime_all

    assert "read_event_journal" in runtime_all
    assert "stream_event_journal" in runtime_all
    assert "read_event_journal_paged" in runtime_all


# ── read_event_journal: full-list sort preservation ──────────────────────


def test_read_event_journal_sorts_even_when_lines_out_of_order(
    tmp_path: Path,
) -> None:
    """read_event_journal must sort by seq regardless of file order."""
    events = [_make_event(i) for i in range(5)]
    # Write in reverse order: seq 4, 3, 2, 1, 0
    lines = [json.dumps(e, sort_keys=True) for e in reversed(events)]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal(tmp_path)
    assert [e["seq"] for e in result] == [0, 1, 2, 3, 4]


def test_read_event_journal_sorts_out_of_order_with_bad_line_skipped(
    tmp_path: Path,
) -> None:
    """Eager read sorts all parsed events and skips bad lines."""
    lines = [
        json.dumps(_make_event(3, kind="c"), sort_keys=True),
        "",  # blank
        json.dumps(_make_event(0, kind="a"), sort_keys=True),
        "{bad json",
        json.dumps(_make_event(1, kind="b"), sort_keys=True),
        "   ",  # whitespace-only
        json.dumps(_make_event(2, kind="d"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal(tmp_path)
    # Should have 4 valid events sorted by seq.
    assert len(result) == 4
    assert [e["seq"] for e in result] == [0, 1, 2, 3]
    assert [e["kind"] for e in result] == ["a", "b", "d", "c"]


def test_read_event_journal_sorts_with_duplicate_seqs_present(tmp_path: Path) -> None:
    """When duplicate seq values exist, sort is stable (by insertion order)."""
    # Two events with seq=1 — sort should keep relative file order.
    lines = [
        json.dumps(_make_event(1, kind="first_of_one"), sort_keys=True),
        json.dumps(_make_event(1, kind="second_of_one"), sort_keys=True),
        json.dumps(_make_event(0, kind="zero"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)

    result = read_event_journal(tmp_path)
    assert len(result) == 3
    assert result[0]["seq"] == 0
    assert result[1]["seq"] == 1
    assert result[2]["seq"] == 1


class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[object, list[dict]] = {}

    def emit_event(
        self,
        scope,
        *,
        kind,
        payload=None,
        phase=None,
        idempotency_key=None,
        event_scope=None,
    ):
        with self._lock:
            events = self._events.setdefault(scope, [])
            event = {
                "seq": len(events),
                "schema_version": 1,
                "kind": kind,
                "payload": dict(payload or {}),
            }
            if phase is not None:
                event["phase"] = phase
            if idempotency_key is not None:
                event["idempotency_key"] = idempotency_key
            if event_scope is not None:
                event["scope"] = event_scope
            events.append(event)
        return type("Row", (), {"sequence": event["seq"], "payload": dict(event), "kind": kind})()

    def read_events(self, scope, *, since_sequence=None, to_sequence=None, limit=None):
        rows = []
        for event in self._events.get(scope, []):
            seq = event["seq"]
            if since_sequence is not None and seq <= since_sequence:
                continue
            if to_sequence is not None and seq >= to_sequence:
                continue
            rows.append(type("Row", (), {"sequence": seq, "payload": dict(event), "kind": event["kind"]})())
            if limit is not None and len(rows) >= limit:
                break
        return rows


def test_backend_event_journal_assigns_monotonic_unique_sequences() -> None:
    backend = _MemoryBackend()
    journal = BackendEventJournal(backend, scope="trace")

    events: list[dict] = []

    def _emit(index: int) -> None:
        events.append(journal.emit("tick", payload={"n": index}))

    threads = [threading.Thread(target=_emit, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    seqs = sorted(event["seq"] for event in events)
    assert seqs == list(range(8))
    assert [event["seq"] for event in journal.read()] == list(range(8))


def test_backend_event_sink_delegates_emit_and_scope() -> None:
    backend = _MemoryBackend()
    sink = BackendEventSink(backend, scope="trace", default_scope="native-trace")

    event = sink.emit("phase.end", payload={"phase": "review"})

    assert event["kind"] == "phase.end"
    assert event["scope"] == "native-trace"
