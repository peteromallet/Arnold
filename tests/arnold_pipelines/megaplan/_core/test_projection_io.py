"""Focused unit tests for projection primitives in ``_core/io.py``.

Covers T4 requirements:

* Stable serialization — ``_projection_canonical_dumps`` produces
  deterministic JSON regardless of dict-insertion order.
* Digest stability — the same record, round-tripped through
  ``to_dict``/``from_dict``, yields an identical ``source_digest``.
* Append ordering — ``append_projection_event`` writes records in
  order and ``load_projection_history`` returns them in order.
* Monotonic cursor rejection — ``_validate_projection_cursor`` rejects
  regressed record counts and (under strict mode) digest rewrites;
  ``append_projection_event`` raises ``ProjectionCursorMismatchError``.
* Deterministic replay — ``deterministic_projection_replay`` produces
  the same final state for the same history independent of timing.
* Atomic rebuild — ``rebuild_projection_atomically`` never exposes a
  partial snapshot; temp-file rename is atomic.
* Snapshot naming — ``projection_history_path`` and
  ``projection_snapshot_path`` use the prescribed suffixes and IDs.
* Mismatch recovery artifacts — ``ProjectionCursorMismatchError``
  carries projection_id, cursors, and preserved_snapshot_path;
  ``recover_projection_from_cursor_mismatch`` restores from
  preserved prior snapshots.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    ProjectionRecord,
    _projection_canonical_bytes,
    _projection_canonical_dumps,
    _RECOVERY_DIRNAME,
    _validate_projection_cursor,
    append_projection_event,
    deterministic_projection_replay,
    latest_projection_cursor,
    load_projection_history,
    projection_history_path,
    projection_snapshot_path,
    rebuild_projection_atomically,
    recover_projection_from_cursor_mismatch,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _cursor(
    path: str = "/tmp/source.jsonl",
    count: int = 3,
    digest: str = "sha256:abc123",
) -> ProjectionCursor:
    return ProjectionCursor(
        source_path=path,
        source_record_count=count,
        source_digest=digest,
        computed_at="2026-07-21T00:00:00Z",
    )


def _record(
    event_type: str = "snapshot_built",
    event_id: str = "evt-1",
    payload: dict | None = None,
    *,
    cursor: ProjectionCursor | None = None,
    idempotency_key: str = "",
) -> ProjectionRecord:
    return ProjectionRecord(
        event_type=event_type,
        event_id=event_id,
        payload=payload or {"key": "value"},
        occurred_at="2026-07-21T00:00:00Z",
        cursor=cursor,
        idempotency_key=idempotency_key,
    )


# ── Stable serialization ────────────────────────────────────────────────────


class TestStableSerialization:
    """``_projection_canonical_dumps`` must produce deterministic output."""

    def test_keys_are_sorted_recursively(self) -> None:
        obj = {"z": 1, "a": {"c": 3, "b": 2}}
        result = _projection_canonical_dumps(obj)
        assert result == '{"a":{"b":2,"c":3},"z":1}'

    def test_no_ascii_escaping(self) -> None:
        obj = {"name": "Jürgen"}
        result = _projection_canonical_dumps(obj)
        assert "Jürgen" in result
        assert "\\u" not in result

    def test_no_trailing_whitespace(self) -> None:
        obj = {"a": 1}
        result = _projection_canonical_dumps(obj)
        assert not result.endswith(" ")
        assert not result.endswith("\n")

    def test_bytes_variant_equals_utf8_encoded_dumps(self) -> None:
        obj = {"a": 1, "b": [2, 3]}
        assert _projection_canonical_bytes(obj) == _projection_canonical_dumps(
            obj
        ).encode("utf-8")

    def test_deterministic_across_dict_insertion_order(self) -> None:
        # Build two dicts with different insertion order but same content
        d1: dict[str, int] = {}
        d1["z"] = 3
        d1["a"] = 1
        d2: dict[str, int] = {}
        d2["a"] = 1
        d2["z"] = 3
        assert _projection_canonical_dumps(d1) == _projection_canonical_dumps(d2)

    def test_null_handled_correctly(self) -> None:
        obj = {"a": None, "b": 1}
        result = _projection_canonical_dumps(obj)
        parsed = json.loads(result)
        assert parsed["a"] is None


# ── Digest stability ────────────────────────────────────────────────────────


class TestDigestStability:
    """Round-tripped records must produce the same source digest."""

    def test_same_record_same_digest(self) -> None:
        rec1 = _record(event_id="evt-1", payload={"x": 1})
        d1 = _projection_canonical_dumps(rec1.to_dict())
        dig1 = "sha256:" + hashlib.sha256(d1.encode("utf-8")).hexdigest()

        rec2 = ProjectionRecord.from_dict(rec1.to_dict())
        d2 = _projection_canonical_dumps(rec2.to_dict())
        dig2 = "sha256:" + hashlib.sha256(d2.encode("utf-8")).hexdigest()

        assert dig1 == dig2

    def test_different_payload_produces_different_digest(self) -> None:
        rec1 = _record(event_id="evt-1", payload={"x": 1})
        rec2 = _record(event_id="evt-1", payload={"x": 2})
        d1 = _projection_canonical_dumps(rec1.to_dict())
        d2 = _projection_canonical_dumps(rec2.to_dict())
        assert d1 != d2

    def test_cursor_to_dict_from_dict_roundtrip(self) -> None:
        c = _cursor(path="/tmp/src.jsonl", count=5, digest="sha256:def456")
        data = c.to_dict()
        c2 = ProjectionCursor.from_dict(data)
        assert c2.source_path == c.source_path
        assert c2.source_record_count == c.source_record_count
        assert c2.source_digest == c.source_digest
        assert c2.computed_at == c.computed_at

    def test_record_to_dict_from_dict_roundtrip_with_cursor(self) -> None:
        c = _cursor()
        rec = _record(cursor=c, idempotency_key="idem-1")
        data = rec.to_dict()
        rec2 = ProjectionRecord.from_dict(data)
        assert rec2.event_type == rec.event_type
        assert rec2.event_id == rec.event_id
        assert rec2.payload == rec.payload
        assert rec2.occurred_at == rec.occurred_at
        assert rec2.idempotency_key == rec.idempotency_key
        assert rec2.cursor is not None
        assert rec2.cursor.source_path == c.source_path

    def test_record_to_dict_from_dict_roundtrip_without_cursor(self) -> None:
        rec = _record()
        data = rec.to_dict()
        rec2 = ProjectionRecord.from_dict(data)
        assert rec2.cursor is None
        assert rec2.idempotency_key == ""

    def test_optional_fields_elided_from_dict(self) -> None:
        rec = ProjectionRecord(
            event_type="test",
            event_id="evt-99",
            payload={},
            occurred_at="2026-07-21T00:00:00Z",
        )
        data = rec.to_dict()
        assert "cursor" not in data
        assert "idempotency_key" not in data
        assert "source_digest" not in data

    def test_payload_is_copied_in_to_dict(self) -> None:
        """to_dict must copy the payload so callers can't mutate the serialized form."""
        payload = {"key": "value"}
        rec = ProjectionRecord(
            event_type="test",
            event_id="evt-1",
            payload=payload,
            occurred_at="2026-07-21T00:00:00Z",
        )
        # The to_dict output must be a copy, not the original reference
        data = rec.to_dict()
        payload["key"] = "changed"
        assert data["payload"]["key"] == "value"


# ── Append ordering ─────────────────────────────────────────────────────────


class TestAppendOrdering:
    """Append writes records in order; load returns them in order."""

    def test_load_returns_records_in_append_order(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        for i in range(5):
            rec = _record(event_id=f"evt-{i}", payload={"seq": i})
            append_projection_event(base_dir, pid, rec)

        history = load_projection_history(base_dir, pid)
        assert len(history) == 5
        for i, rec in enumerate(history):
            assert rec.payload["seq"] == i

    def test_load_empty_history_returns_empty_tuple(self, tmp_path: Path) -> None:
        history = load_projection_history(tmp_path / "nonexistent", "no-proj")
        assert history == ()

    def test_history_file_uses_jsonl_format(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        append_projection_event(base_dir, pid, _record(event_id="evt-1"))
        append_projection_event(base_dir, pid, _record(event_id="evt-2"))

        path = projection_history_path(base_dir, pid)
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "event_type" in parsed
            assert "event_id" in parsed

    def test_loaded_record_has_source_digest_set_on_returned_record(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"
        rec = _record(event_id="evt-1")
        appended = append_projection_event(base_dir, pid, rec)

        # The returned record should have a source_digest (set in-memory)
        assert appended.source_digest.startswith("sha256:")

        # Loading from file: source_digest is intentionally excluded from
        # serialization (it's computed from the rest of the fields) so the
        # loaded record will NOT have it — that's by design.
        history = load_projection_history(base_dir, pid)
        loaded = history[0]
        # The loaded record won't have source_digest set (it's not serialized)
        assert loaded.source_digest == ""
        # But the payload, event_id etc. are preserved
        assert loaded.event_id == "evt-1"
        assert loaded.payload == {"key": "value"}

    def test_latest_cursor_returns_most_recent(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        # Cursor is derived from source_path, not from the record
        source = tmp_path / "source.jsonl"

        source.write_text("r1\nr2\nr3\n", encoding="utf-8")
        append_projection_event(
            base_dir, pid, _record(event_id="evt-1"), source_path=source
        )

        source.write_text("r1\nr2\nr3\nr4\nr5\n", encoding="utf-8")
        append_projection_event(
            base_dir, pid, _record(event_id="evt-2"), source_path=source
        )

        source.write_text("r1\nr2\nr3\nr4\nr5\nr6\nr7\n", encoding="utf-8")
        append_projection_event(
            base_dir, pid, _record(event_id="evt-3"), source_path=source
        )

        latest = latest_projection_cursor(base_dir, pid)
        assert latest is not None
        assert latest.source_record_count == 7

    def test_latest_cursor_skips_null_cursors(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        # Append a record with source (gets a cursor)
        source = tmp_path / "source.jsonl"
        source.write_text("r1\n", encoding="utf-8")
        append_projection_event(base_dir, pid, _record(event_id="evt-1"), source_path=source)
        # Append a record without source (no cursor)
        append_projection_event(base_dir, pid, _record(event_id="evt-2"), source_path=None)

        latest = latest_projection_cursor(base_dir, pid)
        assert latest is not None
        assert latest.source_record_count == 1

    def test_skips_malformed_lines_in_history(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        # Write a valid record
        append_projection_event(base_dir, pid, _record(event_id="evt-1"))

        # Append garbage line
        path = projection_history_path(base_dir, pid)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("not valid json\n")

        history = load_projection_history(base_dir, pid)
        # Only the valid record should be loaded
        assert len(history) == 1
        assert history[0].event_id == "evt-1"


# ── ProjectionCursor immutability ───────────────────────────────────────────


class TestProjectionCursorImmutability:
    """ProjectionCursor is frozen; it cannot be mutated."""

    def test_cursor_is_frozen(self) -> None:
        c = _cursor()
        with pytest.raises(Exception):
            c.source_record_count = 99  # type: ignore[misc]

    def test_cursor_hashable(self) -> None:
        c1 = _cursor()
        c2 = _cursor()
        # Frozen dataclasses with same values should hash the same
        assert hash(c1) == hash(c2)
        s = {c1, c2}
        assert len(s) == 1


# ── Monotonic cursor validation ─────────────────────────────────────────────


class TestMonotonicCursorValidation:
    """Cursors must be monotonic; regressions are rejected."""

    def test_valid_when_count_increases(self) -> None:
        last = _cursor(count=3)
        cur = _cursor(count=5)
        assert _validate_projection_cursor(last, cur) is True

    def test_valid_when_count_same(self) -> None:
        last = _cursor(count=3, digest="sha256:abc")
        cur = _cursor(count=3, digest="sha256:abc")
        assert _validate_projection_cursor(last, cur) is True

    def test_rejects_regressed_count(self) -> None:
        last = _cursor(count=5)
        cur = _cursor(count=3)
        assert _validate_projection_cursor(last, cur) is False

    def test_strict_digest_rejects_same_count_different_digest(self) -> None:
        last = _cursor(count=3, digest="sha256:abc")
        cur = _cursor(count=3, digest="sha256:xyz")
        assert _validate_projection_cursor(last, cur, strict_digest=True) is False

    def test_strict_digest_always_checks_digest_equality(self) -> None:
        # strict_digest mode always checks digest, even when count grows
        last = _cursor(count=3, digest="sha256:abc")
        cur = _cursor(count=5, digest="sha256:xyz")
        assert _validate_projection_cursor(last, cur, strict_digest=True) is False

    def test_strict_digest_accepts_same_digest_growing_count(self) -> None:
        last = _cursor(count=3, digest="sha256:abc")
        cur = _cursor(count=5, digest="sha256:abc")
        assert _validate_projection_cursor(last, cur, strict_digest=True) is True

    def test_non_strict_mode_accepts_different_digest_same_count(self) -> None:
        last = _cursor(count=3, digest="sha256:abc")
        cur = _cursor(count=3, digest="sha256:xyz")
        # Non-strict: only checks count monotonicity, not digest
        assert _validate_projection_cursor(last, cur, strict_digest=False) is True


# ── Append with cursor checking raises on regression ────────────────────────


class TestAppendProjectionEventCursorChecking:
    """append_projection_event validates cursors and raises on mismatch."""

    def test_append_with_source_path_sets_cursor(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        # Create a source file
        source = tmp_path / "source.jsonl"
        source.write_text("record1\nrecord2\nrecord3\n", encoding="utf-8")

        rec = _record(event_id="evt-1")
        result = append_projection_event(
            base_dir, pid, rec, source_path=source, snapshot_dir=snapshot_dir
        )
        assert result.cursor is not None
        assert result.cursor.source_record_count == 3

    def test_raises_on_cursor_regression(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        # First, append with 3 records in source
        source = tmp_path / "source.jsonl"
        source.write_text("r1\nr2\nr3\n", encoding="utf-8")
        append_projection_event(
            base_dir,
            pid,
            _record(event_id="evt-1"),
            source_path=source,
            snapshot_dir=snapshot_dir,
        )

        # Now truncate source to 1 record (regression)
        source.write_text("r1\n", encoding="utf-8")

        with pytest.raises(ProjectionCursorMismatchError) as exc_info:
            append_projection_event(
                base_dir,
                pid,
                _record(event_id="evt-2"),
                source_path=source,
                snapshot_dir=snapshot_dir,
            )

        err = exc_info.value
        assert err.projection_id == pid
        assert err.last_cursor is not None
        assert err.last_cursor.source_record_count == 3
        assert err.current_cursor is not None
        assert err.current_cursor.source_record_count == 1

    def test_append_accepts_same_count_different_digest_by_default(self, tmp_path: Path) -> None:
        """By default (non-strict), same-count digest changes are allowed.
        Only count regressions are rejected. strict_digest is not enabled in append."""
        base_dir = tmp_path / "projections"
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        source = tmp_path / "source.jsonl"
        source.write_text("r1\nr2\nr3\n", encoding="utf-8")
        append_projection_event(
            base_dir,
            pid,
            _record(event_id="evt-1"),
            source_path=source,
            snapshot_dir=snapshot_dir,
        )

        # Rewrite with same count but different content — this does NOT raise
        # because append uses non-strict validation (count only).
        source.write_text("x1\nx2\nx3\n", encoding="utf-8")
        result = append_projection_event(
            base_dir,
            pid,
            _record(event_id="evt-2"),
            source_path=source,
            snapshot_dir=snapshot_dir,
        )
        assert result.cursor is not None
        assert result.cursor.source_record_count == 3

    def test_mismatch_preserves_snapshot_to_recovery(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        # Create a prior snapshot
        rebuild_projection_atomically(
            snapshot_dir, pid, {"state": "before"},
            cursor=_cursor(count=3, digest="sha256:abc"),
        )

        source = tmp_path / "source.jsonl"
        source.write_text("r1\nr2\nr3\n", encoding="utf-8")
        append_projection_event(
            base_dir,
            pid,
            _record(event_id="evt-1"),
            source_path=source,
            snapshot_dir=snapshot_dir,
        )

        # Trigger regression
        source.write_text("r1\n", encoding="utf-8")
        preserved_path = None
        try:
            append_projection_event(
                base_dir,
                pid,
                _record(event_id="evt-2"),
                source_path=source,
                snapshot_dir=snapshot_dir,
            )
        except ProjectionCursorMismatchError as exc:
            preserved_path = exc.preserved_snapshot_path

        assert preserved_path is not None
        assert Path(preserved_path).exists()
        assert "recovery" in str(preserved_path)
        assert "pre-mismatch" in Path(preserved_path).name

    def test_no_error_when_no_prior_cursor(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        source = tmp_path / "source.jsonl"
        source.write_text("r1\nr2\n", encoding="utf-8")

        # First append should work fine (no prior cursor)
        result = append_projection_event(
            base_dir,
            pid,
            _record(event_id="evt-1"),
            source_path=source,
            snapshot_dir=snapshot_dir,
        )
        assert result.cursor is not None
        assert result.cursor.source_record_count == 2


# ── Deterministic replay ────────────────────────────────────────────────────


class TestDeterministicReplay:
    """Replay must produce the same result for the same history every time."""

    def test_replay_produces_same_result_twice(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        for i in range(3):
            append_projection_event(
                base_dir, pid, _record(event_id=f"evt-{i}", payload={"step": i})
            )

        result1 = deterministic_projection_replay(base_dir, pid)
        result2 = deterministic_projection_replay(base_dir, pid)
        assert result1 == result2

    def test_default_fold_merges_payloads(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        append_projection_event(
            base_dir, pid, _record(event_id="evt-1", payload={"a": 1})
        )
        append_projection_event(
            base_dir, pid, _record(event_id="evt-2", payload={"b": 2})
        )

        result = deterministic_projection_replay(base_dir, pid)
        assert result == {"a": 1, "b": 2}

    def test_custom_fold_function(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        for i in range(1, 4):
            append_projection_event(
                base_dir,
                pid,
                _record(event_id=f"evt-{i}", payload={"val": i}),
            )

        def sum_fold(acc: dict, rec: ProjectionRecord) -> dict:
            total = acc.get("total", 0) + rec.payload["val"]
            return {"total": total}

        result = deterministic_projection_replay(base_dir, pid, fold_fn=sum_fold)
        assert result == {"total": 6}

    def test_replay_empty_history_returns_empty_dict(self, tmp_path: Path) -> None:
        result = deterministic_projection_replay(tmp_path / "nonexistent", "no-proj")
        assert result == {}

    def test_replay_respects_append_order(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        # Append in order: set x=1, then x=2, then x=3
        for i in [1, 2, 3]:
            append_projection_event(
                base_dir,
                pid,
                _record(event_id=f"evt-{i}", payload={"x": i}),
            )

        result = deterministic_projection_replay(base_dir, pid)
        # Last write wins with default fold
        assert result == {"x": 3}

    def test_replay_preserves_accumulator_isolation(self, tmp_path: Path) -> None:
        """Each replay call starts with a fresh empty dict accumulator."""
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        append_projection_event(
            base_dir, pid, _record(event_id="evt-1", payload={"a": 1})
        )
        result1 = deterministic_projection_replay(base_dir, pid)
        append_projection_event(
            base_dir, pid, _record(event_id="evt-2", payload={"b": 2})
        )
        result2 = deterministic_projection_replay(base_dir, pid)

        assert result1 == {"a": 1}
        assert result2 == {"a": 1, "b": 2}


# ── Atomic rebuild ──────────────────────────────────────────────────────────


class TestAtomicRebuild:
    """rebuild_projection_atomically must never expose partial writes."""

    def test_snapshot_is_written(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        path = rebuild_projection_atomically(
            snapshot_dir, pid, {"key": "value"}
        )
        assert path.exists()
        assert path == projection_snapshot_path(snapshot_dir, pid)

    def test_snapshot_contains_envelope(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        rebuild_projection_atomically(snapshot_dir, pid, {"key": "value"})
        path = projection_snapshot_path(snapshot_dir, pid)
        content = json.loads(path.read_text(encoding="utf-8"))

        assert content["projection_id"] == pid
        assert content["schema_version"] == 1
        assert "built_at" in content
        assert content["data"] == {"key": "value"}

    def test_snapshot_includes_cursor_when_provided(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"
        c = _cursor()

        rebuild_projection_atomically(snapshot_dir, pid, {"x": 1}, cursor=c)
        path = projection_snapshot_path(snapshot_dir, pid)
        content = json.loads(path.read_text(encoding="utf-8"))

        assert "cursor" in content
        assert content["cursor"]["source_record_count"] == 3
        assert content["cursor"]["source_digest"] == "sha256:abc123"

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        rebuild_projection_atomically(snapshot_dir, pid, {"x": 1})

        # No .tmp file should remain
        tmp_files = list(snapshot_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_overwrite_updates_in_place(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        rebuild_projection_atomically(snapshot_dir, pid, {"v": 1})
        first_stat = projection_snapshot_path(snapshot_dir, pid).stat()

        # Second write
        rebuild_projection_atomically(snapshot_dir, pid, {"v": 2})
        content = json.loads(
            projection_snapshot_path(snapshot_dir, pid).read_text(encoding="utf-8")
        )
        assert content["data"] == {"v": 2}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "deep" / "nested" / "snapshots"
        pid = "test-proj"

        path = rebuild_projection_atomically(snapshot_dir, pid, {"x": 1})
        assert path.exists()
        assert path.parent == snapshot_dir


# ── Snapshot naming ─────────────────────────────────────────────────────────


class TestSnapshotNaming:
    """Path helpers use the prescribed suffixes and IDs."""

    def test_projection_history_path_suffix(self) -> None:
        path = projection_history_path(Path("/tmp/base"), "my-projection")
        assert path.name == "my-projection.projection.jsonl"
        assert path.parent == Path("/tmp/base")

    def test_projection_snapshot_path_suffix(self) -> None:
        path = projection_snapshot_path(Path("/tmp/snap"), "my-projection")
        assert path.name == "my-projection.snapshot.json"
        assert path.parent == Path("/tmp/snap")

    def test_different_projections_have_different_paths(self) -> None:
        base = Path("/tmp/base")
        snap = Path("/tmp/snap")
        assert projection_history_path(base, "proj-a") != projection_history_path(
            base, "proj-b"
        )
        assert projection_snapshot_path(snap, "proj-a") != projection_snapshot_path(
            snap, "proj-b"
        )

    def test_recovery_dir_name_is_recovery(self) -> None:
        assert _RECOVERY_DIRNAME == "recovery"


# ── ProjectionCursorMismatchError diagnostics ───────────────────────────────


class TestCursorMismatchError:
    """The error carries complete diagnostic state."""

    def test_error_carries_projection_id(self) -> None:
        err = ProjectionCursorMismatchError(
            "test error",
            projection_id="proj-1",
            last_cursor=_cursor(count=3),
            current_cursor=_cursor(count=1),
        )
        assert err.projection_id == "proj-1"

    def test_error_carries_both_cursors(self) -> None:
        last = _cursor(count=5, digest="sha256:old")
        cur = _cursor(count=2, digest="sha256:new")
        err = ProjectionCursorMismatchError(
            "test",
            projection_id="p",
            last_cursor=last,
            current_cursor=cur,
        )
        assert err.last_cursor is last
        assert err.current_cursor is cur

    def test_error_to_dict_includes_cursors(self) -> None:
        last = _cursor(count=5, digest="sha256:old")
        cur = _cursor(count=2, digest="sha256:new")
        err = ProjectionCursorMismatchError(
            "mismatch occurred",
            projection_id="p",
            last_cursor=last,
            current_cursor=cur,
            preserved_snapshot_path="/tmp/recovery/p.pre-mismatch.json",
        )
        d = err.to_dict()
        assert d["error"] == "mismatch occurred"
        assert d["projection_id"] == "p"
        assert d["last_cursor"]["source_record_count"] == 5
        assert d["current_cursor"]["source_record_count"] == 2
        assert d["preserved_snapshot_path"] == "/tmp/recovery/p.pre-mismatch.json"

    def test_error_with_none_cursors_to_dict(self) -> None:
        err = ProjectionCursorMismatchError(
            "no cursors",
            projection_id="p",
            last_cursor=None,
            current_cursor=None,
        )
        d = err.to_dict()
        assert d["projection_id"] == "p"
        assert "last_cursor" not in d
        assert "current_cursor" not in d

    def test_error_is_runtime_error_subclass(self) -> None:
        err = ProjectionCursorMismatchError(
            "test", projection_id="p", last_cursor=None, current_cursor=None
        )
        assert isinstance(err, RuntimeError)


# ── Cursor-mismatch recovery ────────────────────────────────────────────────


class TestCursorMismatchRecovery:
    """recover_projection_from_cursor_mismatch restores from preserved snapshots."""

    def test_recovers_from_preserved_snapshot(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        # Create a snapshot
        rebuild_projection_atomically(
            snapshot_dir, pid, {"state": "before"},
            cursor=_cursor(count=3, digest="sha256:abc"),
        )

        # Simulate a mismatch preservation (manually copy to recovery)
        recovery_dir = snapshot_dir / "recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        import shutil

        src = projection_snapshot_path(snapshot_dir, pid)
        dest = recovery_dir / f"{pid}.pre-mismatch-20260721T000000Z.snapshot.json"
        shutil.copy2(src, dest)

        # Now "corrupt" the current snapshot
        rebuild_projection_atomically(snapshot_dir, pid, {"state": "corrupted"})

        # Recover
        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "recovered"
        assert result["snapshot_path"] is not None

        # Verify the snapshot was restored
        current = json.loads(
            projection_snapshot_path(snapshot_dir, pid).read_text(encoding="utf-8")
        )
        assert current["data"] == {"state": "before"}

    def test_no_recovery_dir_returns_no_snapshot(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "no_snapshot"

    def test_empty_recovery_dir_returns_no_snapshot(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"
        (snapshot_dir / "recovery").mkdir(parents=True)

        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "no_snapshot"

    def test_corrupted_snapshot_returns_empty_snapshot(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        recovery_dir = snapshot_dir / "recovery"
        recovery_dir.mkdir(parents=True)
        dest = recovery_dir / f"{pid}.pre-mismatch-20260721T000000Z.snapshot.json"
        dest.write_text("not valid json", encoding="utf-8")

        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "empty_snapshot"

    def test_empty_envelope_returns_empty_snapshot(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        recovery_dir = snapshot_dir / "recovery"
        recovery_dir.mkdir(parents=True)
        dest = recovery_dir / f"{pid}.pre-mismatch-20260721T000000Z.snapshot.json"
        dest.write_text(json.dumps({"projection_id": pid}), encoding="utf-8")

        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "empty_snapshot"

    def test_recovery_returns_diagnostics(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        rebuild_projection_atomically(
            snapshot_dir, pid, {"state": "ok"},
            cursor=_cursor(count=3, digest="sha256:abc"),
        )
        import shutil

        recovery_dir = snapshot_dir / "recovery"
        recovery_dir.mkdir(parents=True)
        shutil.copy2(
            projection_snapshot_path(snapshot_dir, pid),
            recovery_dir / f"{pid}.pre-mismatch-20260721T000000Z.snapshot.json",
        )

        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert "diagnostics" in result
        assert len(result["diagnostics"]) >= 1
        assert "cursor" in result

    def test_multiple_preserved_snapshots_picks_most_recent(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        # Create a snapshot with a known state
        rebuild_projection_atomically(
            snapshot_dir, pid, {"version": 1},
            cursor=_cursor(count=1),
        )

        import shutil

        recovery_dir = snapshot_dir / "recovery"
        recovery_dir.mkdir(parents=True)

        # Write two preserved snapshots
        dest_old = recovery_dir / f"{pid}.pre-mismatch-20260720T000000Z.snapshot.json"
        shutil.copy2(projection_snapshot_path(snapshot_dir, pid), dest_old)

        # Change the current snapshot, then preserve the "newer" version
        rebuild_projection_atomically(
            snapshot_dir, pid, {"version": 2},
            cursor=_cursor(count=2),
        )
        dest_new = recovery_dir / f"{pid}.pre-mismatch-20260721T000000Z.snapshot.json"
        shutil.copy2(projection_snapshot_path(snapshot_dir, pid), dest_new)

        # Corrupt current
        rebuild_projection_atomically(snapshot_dir, pid, {"version": "corrupted"})

        # Recover should pick the most recent (20260721)
        result = recover_projection_from_cursor_mismatch(snapshot_dir, pid)
        assert result["status"] == "recovered"

        current = json.loads(
            projection_snapshot_path(snapshot_dir, pid).read_text(encoding="utf-8")
        )
        assert current["data"] == {"version": 2}


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and edge-case behavior."""

    def test_empty_source_file_yields_zero_count(self, tmp_path: Path) -> None:
        source = tmp_path / "empty.jsonl"
        source.write_text("", encoding="utf-8")

        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

        cursor = _projection_cursor_from_path(source)
        assert cursor.source_record_count == 0

    def test_missing_source_file_yields_zero_count(self, tmp_path: Path) -> None:
        source = tmp_path / "nonexistent.jsonl"

        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

        cursor = _projection_cursor_from_path(source)
        assert cursor.source_record_count == 0
        # Should use empty-content digest
        assert cursor.source_digest == "sha256:" + hashlib.sha256(b"").hexdigest()

    def test_source_with_no_trailing_newline(self, tmp_path: Path) -> None:
        source = tmp_path / "source.jsonl"
        source.write_text("line1\nline2\nline3", encoding="utf-8")

        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

        cursor = _projection_cursor_from_path(source)
        # Three lines, no trailing newline -> still 3 records
        assert cursor.source_record_count == 3

    def test_source_with_only_newlines(self, tmp_path: Path) -> None:
        source = tmp_path / "source.jsonl"
        source.write_text("\n\n\n", encoding="utf-8")

        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

        cursor = _projection_cursor_from_path(source)
        assert cursor.source_record_count == 3

    def test_projection_history_written_even_without_source(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        rec = _record(event_id="evt-1")
        result = append_projection_event(base_dir, pid, rec, source_path=None)

        assert result.cursor is None
        history = load_projection_history(base_dir, pid)
        assert len(history) == 1

    def test_append_returns_record_with_source_digest(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        rec = _record(event_id="evt-1")
        result = append_projection_event(base_dir, pid, rec)

        assert result.source_digest.startswith("sha256:")
        assert len(result.source_digest) == len("sha256:") + 64

    def test_multiple_projections_are_independent(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"

        append_projection_event(base_dir, "proj-a", _record(event_id="a-1", payload={"proj": "a"}))
        append_projection_event(base_dir, "proj-b", _record(event_id="b-1", payload={"proj": "b"}))

        history_a = load_projection_history(base_dir, "proj-a")
        history_b = load_projection_history(base_dir, "proj-b")

        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0].payload["proj"] == "a"
        assert history_b[0].payload["proj"] == "b"

    def test_idempotency_key_is_preserved(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        rec = _record(event_id="evt-1", idempotency_key="idem-unique-123")
        append_projection_event(base_dir, pid, rec)

        history = load_projection_history(base_dir, pid)
        assert history[0].idempotency_key == "idem-unique-123"


# ── Non-regression: reload + re-serialize stability ─────────────────────────


class TestReloadReserializeStability:
    """Round-trip through file ensures serialization fidelity."""

    def test_record_serialization_round_trip_through_file(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "projections"
        pid = "test-proj"

        # Cursor comes from source_path, not the record
        source = tmp_path / "source.jsonl"
        source.write_text("r1\nr2\nr3\nr4\nr5\n", encoding="utf-8")

        original = _record(
            event_type="custom_event",
            event_id="evt-roundtrip",
            payload={"nested": {"deep": True}, "list": [1, 2, 3]},
            idempotency_key="roundtrip-key",
        )

        appended = append_projection_event(base_dir, pid, original, source_path=source)
        loaded = load_projection_history(base_dir, pid)[0]

        # Re-serialize and compare — source_digest is intentionally excluded
        # from serialization (its self-referential hash), so loaded won't have it.
        # Compare the structural fields instead.
        assert loaded.event_id == appended.event_id
        assert loaded.event_type == appended.event_type
        assert loaded.payload == appended.payload
        assert loaded.occurred_at == appended.occurred_at
        assert loaded.idempotency_key == appended.idempotency_key
        assert loaded.cursor is not None
        assert loaded.cursor.source_record_count == 5
        # source_digest computed by append is non-empty, loaded is empty (by design)
        assert appended.source_digest.startswith("sha256:")
        assert loaded.source_digest == ""

    def test_cursor_serialization_is_stable_across_reloads(self, tmp_path: Path) -> None:
        snapshot_dir = tmp_path / "snapshots"
        pid = "test-proj"

        c = _cursor(
            path="/data/source.jsonl", count=42,
            digest="sha256:abcdef1234567890abcdef1234567890abcdef12",
        )
        rebuild_projection_atomically(snapshot_dir, pid, {"x": 1}, cursor=c)

        path = projection_snapshot_path(snapshot_dir, pid)
        content = json.loads(path.read_text(encoding="utf-8"))
        c2 = ProjectionCursor.from_dict(content["cursor"])
        assert c2.source_record_count == 42
        assert c2.source_digest == c.source_digest
        assert c2.source_path == c.source_path
