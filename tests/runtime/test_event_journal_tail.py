"""Step 18 — bounded tail reads and durable journal cursor semantics.

Verifies that ``read_event_journal_tail`` bounds memory by *limit* (not by
journal size) and preserves append order, and that ``journal_cursor`` derives
a rebuildable cursor purely from durable ``events.ndjson`` content — never
from the ``.events.seq`` sidecar, labels, or liveness.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold.runtime.event_journal import (
    JournalCursor,
    journal_cursor,
    read_event_journal,
    read_event_journal_tail,
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


# ── Bounded tail read ──────────────────────────────────────────────────────


def test_large_journal_tail_read_is_bounded(tmp_path: Path) -> None:
    """A tail read over a large journal returns only *limit* events in order.

    The journal has 5 000 events; requesting ``limit=10`` must return exactly
    the last 10 in append order — proving the read is bounded by *limit*, not
    by journal size.
    """
    total = 5000
    limit = 10
    events = [_make_event(i, kind=f"k{i}") for i in range(total)]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    _write_ndjson(tmp_path, lines)

    tail = read_event_journal_tail(tmp_path, limit)

    # Bounded: only *limit* events returned.
    assert len(tail) == limit
    # Append order preserved: the last *limit* seqs.
    assert [e["seq"] for e in tail] == list(range(total - limit, total))
    assert [e["kind"] for e in tail] == [f"k{i}" for i in range(total - limit, total)]

    # Cross-check against the eager reader to prove the tail is correct.
    full = read_event_journal(tmp_path)
    assert tail == full[-limit:]


def test_tail_limit_zero_returns_empty_without_reading(tmp_path: Path) -> None:
    """A limit of 0 short-circuits before touching the file."""
    _write_ndjson(tmp_path, [json.dumps(_make_event(0), sort_keys=True)])
    assert read_event_journal_tail(tmp_path, 0) == []


def test_tail_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_event_journal_tail(tmp_path / "nope", 5) == []


def test_tail_limit_exceeds_journal_returns_all(tmp_path: Path) -> None:
    events = [_make_event(i) for i in range(3)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    tail = read_event_journal_tail(tmp_path, 100)
    assert [e["seq"] for e in tail] == [0, 1, 2]


def test_tail_skips_bad_lines(tmp_path: Path) -> None:
    lines = [
        json.dumps(_make_event(0, kind="a"), sort_keys=True),
        "[bad json",
        json.dumps(_make_event(1, kind="b"), sort_keys=True),
    ]
    _write_ndjson(tmp_path, lines)
    tail = read_event_journal_tail(tmp_path, 5)
    assert [e["kind"] for e in tail] == ["a", "b"]


# ── Durable journal cursor ─────────────────────────────────────────────────


def test_journal_cursor_derived_from_durable_content(tmp_path: Path) -> None:
    """The cursor is reproducible from the durable file, not the sidecar."""
    events = [_make_event(i) for i in range(5)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])

    cursor = journal_cursor(tmp_path)
    assert isinstance(cursor, JournalCursor)
    assert cursor.record_count == 5
    assert cursor.last_seq == 4
    assert cursor.digest.startswith("sha256:")

    # Stale sidecar must NOT change the cursor — it is derived from the file.
    (tmp_path / ".events.seq").write_text("999", encoding="ascii")
    cursor2 = journal_cursor(tmp_path)
    assert cursor2.record_count == 5
    assert cursor2.last_seq == 4
    assert cursor2.digest == cursor.digest


def test_journal_cursor_empty_journal(tmp_path: Path) -> None:
    cursor = journal_cursor(tmp_path)
    assert cursor.record_count == 0
    assert cursor.last_seq is None


def test_journal_cursor_roundtrip(tmp_path: Path) -> None:
    events = [_make_event(i) for i in range(3)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    cursor = journal_cursor(tmp_path)
    restored = JournalCursor.from_dict(cursor.to_dict())
    assert restored == cursor
