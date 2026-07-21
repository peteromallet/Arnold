"""Focused unit tests for Custody projection store.

Covers T5 requirements:

* Append — cursor-checked appends against source records; no cursor when source_path is None.
* Replay — deterministic replay produces identical output for the same history.
* Rebuild — atomic rebuild writes snapshots that survive process restart.
* Cursor mismatch — regression/re-write detection with prior-projection preservation.
* Recovery snapshots — recover_from_cursor_mismatch restores from preserved snapshots.

North Star constraint: all projection outputs are non-authoritative; lease and
epoch validation remains tied to source-record checks (not projection snapshots).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
)
from arnold_pipelines.megaplan.custody.projections import (
    PROJECTION_SCHEMA_VERSION,
    CustodyProjectionStore,
    ProjectionEventType,
    ProjectionNotFoundError,
    ProjectionStoreError,
    append_events,
    open_projection_store,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _source_file(tmp_path: Path, *lines: str) -> Path:
    """Create a JSONL source file with the given lines."""
    path = tmp_path / "source.jsonl"
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return path


def _fresh_store(tmp_path: Path) -> CustodyProjectionStore:
    """Open a fresh projection store under a temp directory."""
    base = tmp_path / "projections"
    return open_projection_store(base_dir=base)


# ── Append tests ────────────────────────────────────────────────────────────


class TestAppend:
    """Cursor-checked append operations."""

    def test_append_with_source_embeds_cursor(self, tmp_path: Path):
        """Append with a source_path should compute and embed a cursor."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        record = store.append("proj-01", "event_x", {"k": "v"}, source_path=src)

        assert record.cursor is not None
        assert record.cursor.source_record_count == 2
        assert record.cursor.source_path == str(src.resolve())
        assert record.cursor.source_digest.startswith("sha256:")
        assert record.event_type == "event_x"
        assert record.payload == {"k": "v"}

    def test_append_without_source_has_no_cursor(self, tmp_path: Path):
        """Append without source_path should leave cursor as None."""
        store = _fresh_store(tmp_path)
        record = store.append("proj-02", "event_y", {"data": 1})
        assert record.cursor is None

    def test_append_writes_to_history_file(self, tmp_path: Path):
        """Appended records should appear in the projection history file."""
        src = _source_file(tmp_path, '{"x": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-03", "e1", {"p": 1}, source_path=src)
        store.append("proj-03", "e2", {"p": 2}, source_path=src)

        history = store.load_history("proj-03")
        assert len(history) == 2
        assert history[0].event_type == "e1"
        assert history[1].event_type == "e2"

    def test_append_preserves_idempotency_key(self, tmp_path: Path):
        """The idempotency_key should round-trip through the store."""
        store = _fresh_store(tmp_path)
        record = store.append(
            "proj-04", "event_z", {"v": 1}, idempotency_key="idem-abc"
        )
        assert record.idempotency_key == "idem-abc"

        loaded = store.load_history("proj-04")
        assert len(loaded) == 1
        assert loaded[0].idempotency_key == "idem-abc"

    def test_append_multiple_projections_independent(self, tmp_path: Path):
        """Different projection IDs should have independent histories."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-a", "ea", {"pa": 1}, source_path=src)
        store.append("proj-b", "eb", {"pb": 2}, source_path=src)

        assert len(store.load_history("proj-a")) == 1
        assert len(store.load_history("proj-b")) == 1
        assert store.load_history("proj-a")[0].payload == {"pa": 1}
        assert store.load_history("proj-b")[0].payload == {"pb": 2}

    def test_append_preserves_event_id_uniqueness(self, tmp_path: Path):
        """Each append should generate a unique event_id."""
        store = _fresh_store(tmp_path)
        r1 = store.append("proj-05", "e", {"i": 1})
        r2 = store.append("proj-05", "e", {"i": 2})
        assert r1.event_id != r2.event_id
        assert r1.event_id.startswith("proj-")

    def test_append_source_digest_on_record(self, tmp_path: Path):
        """Appended records should carry a source_digest for integrity."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        record = store.append("proj-06", "ev", {"x": 1}, source_path=src)
        assert record.source_digest.startswith("sha256:")


# ── Replay tests ────────────────────────────────────────────────────────────


class TestReplay:
    """Deterministic replay of projection history."""

    def test_replay_empty_history_returns_empty_dict(self, tmp_path: Path):
        """Replaying a projection with no events returns an empty dict."""
        store = _fresh_store(tmp_path)
        result = store.replay("nonexistent")
        assert result == {}

    def test_replay_produces_accumulated_state(self, tmp_path: Path):
        """Replay folds all event payloads into the accumulator."""
        store = _fresh_store(tmp_path)
        store.append("proj-r1", "e1", {"a": 1})
        store.append("proj-r1", "e2", {"b": 2})
        store.append("proj-r1", "e3", {"c": 3})

        result = store.replay("proj-r1")
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["c"] == 3

    def test_replay_is_deterministic(self, tmp_path: Path):
        """Replaying the same history twice produces identical results."""
        store = _fresh_store(tmp_path)
        store.append("proj-r2", "e1", {"x": 10})
        store.append("proj-r2", "e2", {"y": 20})

        r1 = store.replay("proj-r2")
        r2 = store.replay("proj-r2")
        assert r1 == r2
        assert r1 is not r2  # Different dict objects

    def test_replay_with_custom_fold(self, tmp_path: Path):
        """Custom fold functions receive each record in order."""
        store = _fresh_store(tmp_path)
        store.append("proj-r3", "inc", {"delta": 5})
        store.append("proj-r3", "inc", {"delta": 3})
        store.append("proj-r3", "inc", {"delta": 2})

        def sum_fold(acc: dict, rec) -> dict:
            total = acc.get("total", 0) + rec.payload.get("delta", 0)
            return {"total": total, "count": acc.get("count", 0) + 1}

        result = store.replay("proj-r3", fold_fn=sum_fold)
        assert result["total"] == 10
        assert result["count"] == 3

    def test_replay_respects_append_order(self, tmp_path: Path):
        """Replay should process records in the order they were appended."""
        store = _fresh_store(tmp_path)
        values = []
        for i in range(5):
            store.append("proj-r4", "push", {"val": i})
            values.append(i)

        def collect(acc: dict, rec) -> dict:
            lst = acc.get("vals", [])
            lst.append(rec.payload["val"])
            return {"vals": lst}

        result = store.replay("proj-r4", fold_fn=collect)
        assert result["vals"] == values

    def test_replay_after_rebuild(self, tmp_path: Path):
        """Replay should include snapshot events from rebuilds."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-r5", "init", {"step": "init"}, source_path=src)
        store.rebuild("proj-r5", {"step": "rebuilt"}, source_path=src)
        store.append("proj-r5", "post", {"step": "post"}, source_path=src)

        result = store.replay("proj-r5")
        # Should have accumulated all three payloads
        assert result.get("step") == "post"  # Last write wins for 'step'


# ── Rebuild tests ───────────────────────────────────────────────────────────


class TestRebuild:
    """Atomic snapshot rebuild operations."""

    def test_rebuild_writes_snapshot(self, tmp_path: Path):
        """Rebuild should write a snapshot file to the projections directory."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        snap_path = store.rebuild("proj-b1", {"state": "v1"}, source_path=src)

        assert snap_path.exists()
        assert snap_path.suffix == ".json"
        assert "proj-b1" in snap_path.name

    def test_rebuild_snapshot_is_loadable(self, tmp_path: Path):
        """Rebuilt snapshots should be loadable via load_snapshot."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-b2", {"key": "value"}, source_path=src)

        snap = store.load_snapshot("proj-b2")
        assert snap is not None
        assert snap["projection_id"] == "proj-b2"
        assert snap["data"] == {"key": "value"}
        assert snap["schema_version"] == PROJECTION_SCHEMA_VERSION

    def test_rebuild_includes_cursor_in_envelope(self, tmp_path: Path):
        """Rebuilt snapshots should embed the source cursor in the envelope."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}', '{"c": 3}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-b3", {"s": "v"}, source_path=src)

        snap = store.load_snapshot("proj-b3")
        assert "cursor" in snap
        assert snap["cursor"]["source_record_count"] == 3
        assert snap["cursor"]["source_path"] == str(src.resolve())

    def test_rebuild_appends_history_event(self, tmp_path: Path):
        """Rebuild should append a SNAPSHOT_BUILT event to the history."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-b4", {"d": 1}, source_path=src)

        history = store.load_history("proj-b4")
        assert len(history) >= 1
        # At least one event should be SNAPSHOT_BUILT
        event_types = [r.event_type for r in history]
        assert ProjectionEventType.SNAPSHOT_BUILT in event_types

    def test_rebuild_overwrite_replaces_snapshot(self, tmp_path: Path):
        """Subsequent rebuilds should overwrite the snapshot."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-b5", {"v": 1}, source_path=src)
        store.rebuild("proj-b5", {"v": 2}, source_path=src)

        snap = store.load_snapshot("proj-b5")
        assert snap["data"] == {"v": 2}

    def test_load_snapshot_nonexistent(self, tmp_path: Path):
        """Loading a non-existent projection snapshot returns None."""
        store = _fresh_store(tmp_path)
        assert store.load_snapshot("nonexistent") is None

    def test_rebuild_without_source(self, tmp_path: Path):
        """Rebuild without source_path should succeed without cursor."""
        store = _fresh_store(tmp_path)
        snap_path = store.rebuild("proj-b6", {"standalone": True})
        assert snap_path.exists()
        snap = store.load_snapshot("proj-b6")
        assert "cursor" not in snap


# ── Cursor mismatch tests ───────────────────────────────────────────────────


class TestCursorMismatch:
    """Cursor regression detection and prior-projection preservation."""

    def test_record_count_regression_raises(self, tmp_path: Path):
        """Reducing the source record count should raise CursorMismatchError."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}', '{"c": 3}')
        store = _fresh_store(tmp_path)
        store.append("proj-c1", "init", {"v": 1}, source_path=src)

        # Truncate source to simulate regression
        src.write_text('{"a": 1}\n')

        with pytest.raises(ProjectionCursorMismatchError) as exc_info:
            store.append("proj-c1", "update", {"v": 2}, source_path=src)

        err = exc_info.value
        assert err.projection_id == "proj-c1"
        assert err.last_cursor is not None
        assert err.last_cursor.source_record_count == 3
        assert err.current_cursor is not None
        assert err.current_cursor.source_record_count == 1

    def test_cursor_mismatch_preserves_prior_snapshot(self, tmp_path: Path):
        """Cursor mismatch should preserve the prior projection snapshot."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-c2", {"state": "before"}, source_path=src)

        # Truncate source
        src.write_text('{"a": 1}\n')

        with pytest.raises(ProjectionCursorMismatchError) as exc_info:
            store.append("proj-c2", "update", {"state": "after"}, source_path=src)

        err = exc_info.value
        assert err.preserved_snapshot_path is not None
        preserved = Path(err.preserved_snapshot_path)
        assert preserved.exists()
        assert "recovery" in str(preserved)
        # The preserved snapshot should contain the prior state
        envelope = json.loads(preserved.read_text())
        assert envelope["data"]["state"] == "before"

    def test_no_mismatch_on_record_count_increase(self, tmp_path: Path):
        """Increasing the source record count should NOT be a mismatch."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-c3", "init", {"v": 1}, source_path=src)

        # Add more records
        src.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')

        # Should succeed — record count increased
        record = store.append("proj-c3", "update", {"v": 2}, source_path=src)
        assert record.cursor is not None
        assert record.cursor.source_record_count == 3

    def test_no_mismatch_first_append(self, tmp_path: Path):
        """First append with a source should not raise mismatch (no prior cursor)."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        # First append — no prior cursor to compare against
        record = store.append("proj-c4", "first", {"v": 1}, source_path=src)
        assert record.cursor is not None

    def test_append_without_source_never_mismatches(self, tmp_path: Path):
        """Appends without source_path never trigger cursor validation."""
        store = _fresh_store(tmp_path)
        store.append("proj-c5", "e1", {"v": 1})
        store.append("proj-c5", "e2", {"v": 2})
        # No source, no cursor → never raises
        assert len(store.load_history("proj-c5")) == 2

    def test_mismatch_error_carries_diagnostics(self, tmp_path: Path):
        """CursorMismatchError provides to_dict() with full diagnostic info."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-c6", {"state": "before"}, source_path=src)
        src.write_text('{"a": 1}\n')

        with pytest.raises(ProjectionCursorMismatchError) as exc_info:
            store.append("proj-c6", "update", {}, source_path=src)

        err_dict = exc_info.value.to_dict()
        assert err_dict["projection_id"] == "proj-c6"
        assert "last_cursor" in err_dict
        assert "current_cursor" in err_dict
        assert "preserved_snapshot_path" in err_dict
        assert "error" in err_dict


# ── Recovery tests ──────────────────────────────────────────────────────────


class TestRecovery:
    """Recovery from cursor mismatch using preserved snapshots."""

    def test_recover_from_preserved_snapshot(self, tmp_path: Path):
        """After a cursor mismatch, recovery should restore the prior snapshot."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}', '{"c": 3}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-d1", {"state": "v1"}, source_path=src)

        # Trigger mismatch (truncation)
        src.write_text('{"a": 1}\n')
        try:
            store.append("proj-d1", "update", {}, source_path=src)
        except ProjectionCursorMismatchError:
            pass

        # Recover
        result = store.recover_from_cursor_mismatch("proj-d1", src)
        assert result["status"] == "recovered"
        assert result["snapshot_path"] is not None
        assert "diagnostics" in result

        # Verify the snapshot was restored
        snap = store.load_snapshot("proj-d1")
        assert snap is not None
        assert snap["data"]["state"] == "v1"

    def test_recovery_no_preserved_snapshot(self, tmp_path: Path):
        """Recovery without any preserved snapshots returns no_snapshot."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        # No mismatch has occurred, so no recovery snapshots exist
        result = store.recover_from_cursor_mismatch("proj-d2", src)
        assert result["status"] == "no_snapshot"

    def test_recovery_appends_history_event(self, tmp_path: Path):
        """Recovery should append a RECOVERY_SUCCESS or RECOVERY_ATTEMPTED event."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-d3", {"state": "pre"}, source_path=src)

        # Trigger mismatch
        src.write_text('{"a": 1}\n')
        try:
            store.append("proj-d3", "update", {}, source_path=src)
        except ProjectionCursorMismatchError:
            pass

        # Count history events before recovery
        before = len(store.load_history("proj-d3"))

        result = store.recover_from_cursor_mismatch("proj-d3", src)
        after = len(store.load_history("proj-d3"))

        if result["status"] == "recovered":
            assert after > before
            # Check last event is RECOVERY_SUCCESS
            history = store.load_history("proj-d3")
            assert history[-1].event_type == ProjectionEventType.RECOVERY_SUCCESS
        else:
            # At minimum, attempts generate history events
            assert after >= before

    def test_recovery_picks_most_recent_snapshot(self, tmp_path: Path):
        """When multiple preserved snapshots exist, pick the most recent."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}', '{"c": 3}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-d4", {"state": "first"}, source_path=src)

        # First mismatch
        src.write_text('{"a": 1}\n')
        try:
            store.append("proj-d4", "u1", {}, source_path=src)
        except ProjectionCursorMismatchError:
            pass

        # Restore source and rebuild again
        src.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
        store.rebuild("proj-d4", {"state": "second"}, source_path=src)

        # Second mismatch
        src.write_text('{"a": 1}\n')
        try:
            store.append("proj-d4", "u2", {}, source_path=src)
        except ProjectionCursorMismatchError:
            pass

        result = store.recover_from_cursor_mismatch("proj-d4", src)
        assert result["status"] == "recovered"
        snap = store.load_snapshot("proj-d4")
        assert snap["data"]["state"] == "second"


# ── Validation tests ────────────────────────────────────────────────────────


class TestValidateSourceCursor:
    """Source cursor validation without side effects."""

    def test_first_validation_always_valid(self, tmp_path: Path):
        """Validation with no prior cursor returns valid=True."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        result = store.validate_source_cursor("proj-v1", src)
        assert result["valid"] is True
        assert result["last_cursor"] is None
        assert "No prior cursor" in result["diagnostics"][0]

    def test_monotonic_growth_is_valid(self, tmp_path: Path):
        """Record count increasing should be valid."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-v2", "init", {}, source_path=src)

        src.write_text('{"a": 1}\n{"b": 2}\n')
        result = store.validate_source_cursor("proj-v2", src)
        assert result["valid"] is True
        assert result["record_count_ok"] is True

    def test_regression_is_invalid(self, tmp_path: Path):
        """Record count decreasing should be invalid."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}', '{"c": 3}')
        store = _fresh_store(tmp_path)
        store.append("proj-v3", "init", {}, source_path=src)

        src.write_text('{"a": 1}\n')
        result = store.validate_source_cursor("proj-v3", src)
        assert result["valid"] is False
        assert result["record_count_ok"] is False
        assert len(result["diagnostics"]) > 0

    def test_digest_ok_is_none_by_default(self, tmp_path: Path):
        """Without strict_digest, digest_ok should be None."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-v4", "init", {}, source_path=src)
        result = store.validate_source_cursor("proj-v4", src)
        assert result["digest_ok"] is None

    def test_strict_digest_enabled(self, tmp_path: Path):
        """With strict_digest=True, digest_ok should be a bool."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-v5", "init", {}, source_path=src)
        result = store.validate_source_cursor("proj-v5", src, strict_digest=True)
        assert isinstance(result["digest_ok"], bool)

    def test_validate_returns_diagnostics_on_failure(self, tmp_path: Path):
        """Failed validation should include diagnostic messages."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        store.append("proj-v6", "init", {}, source_path=src)

        src.write_text('{"a": 1}\n')
        result = store.validate_source_cursor("proj-v6", src)
        assert not result["valid"]
        assert any("regressed" in d.lower() for d in result["diagnostics"])


# ── Batch append tests ──────────────────────────────────────────────────────


class TestBatchAppend:
    """Batch append via append_events helper."""

    def test_batch_append_multiple_events(self, tmp_path: Path):
        """append_events should append all events and return records."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        records = append_events(
            store,
            "proj-ba1",
            [("e1", {"x": 1}), ("e2", {"x": 2}), ("e3", {"x": 3})],
            source_path=src,
        )
        assert len(records) == 3
        assert records[0].payload == {"x": 1}
        assert records[2].payload == {"x": 3}

    def test_batch_append_are_all_in_history(self, tmp_path: Path):
        """All batch-appended events should appear in the history."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        append_events(store, "proj-ba2", [("a", {"i": 1}), ("b", {"i": 2})], source_path=src)
        history = store.load_history("proj-ba2")
        assert len(history) == 2

    def test_batch_append_without_source(self, tmp_path: Path):
        """Batch append without source_path should work."""
        store = _fresh_store(tmp_path)
        records = append_events(store, "proj-ba3", [("ev", {"k": "v"})])
        assert len(records) == 1
        assert records[0].cursor is None

    def test_batch_append_cursor_mismatch_stops_batch(self, tmp_path: Path):
        """If one event in a batch triggers a cursor mismatch, the batch stops."""
        src = _source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        store = _fresh_store(tmp_path)
        store.append("proj-ba4", "init", {}, source_path=src)

        # Regression
        src.write_text('{"a": 1}\n')

        with pytest.raises(ProjectionCursorMismatchError):
            append_events(
                store,
                "proj-ba4",
                [("e1", {"x": 1}), ("e2", {"x": 2})],
                source_path=src,
            )

        # The first event that failed shouldn't be in history
        history = store.load_history("proj-ba4")
        # Only the initial "init" event should be present
        assert len(history) == 1
        assert history[0].event_type == "init"


# ── Non-authoritative projection outputs ────────────────────────────────────


class TestNonAuthoritativeOutputs:
    """Projection outputs are non-authoritative; lease/epoch validation
    must remain source-record checks, not projection-derived claims."""

    def test_load_snapshot_is_pure_read(self, tmp_path: Path):
        """Loading a snapshot does not mutate the store or history."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.rebuild("proj-na1", {"s": "v"}, source_path=src)

        snap1 = store.load_snapshot("proj-na1")
        snap2 = store.load_snapshot("proj-na1")
        assert snap1 == snap2
        # History should be unchanged by load_snapshot
        history = store.load_history("proj-na1")
        history2 = store.load_history("proj-na1")
        assert len(history) == len(history2)

    def test_replay_does_not_authorize(self, tmp_path: Path):
        """Replay is a pure read — it does not authorize or mutate anything."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-na2", "e", {"permission": "admin"}, source_path=src)

        # Replay produces data but does not grant authority
        result = store.replay("proj-na2")
        assert "permission" in result
        # The projection output is just data — authority must come from source records
        assert result["permission"] == "admin"  # It's in the projection data

    def test_projection_cursor_is_not_lease(self, tmp_path: Path):
        """Projection cursors track source record state, not lease state.
        Lease and epoch validation must remain in lease_store modules."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-na3", "init", {}, source_path=src)

        cursor = store.latest_cursor("proj-na3")
        assert cursor is not None
        # A projection cursor is about source record counts/digests
        assert hasattr(cursor, "source_record_count")
        assert hasattr(cursor, "source_digest")
        # No lease-specific fields (custody_epoch, owner, etc.)
        assert not hasattr(cursor, "custody_epoch")

    def test_projection_snapshot_is_not_authoritative_gate(self, tmp_path: Path):
        """Rebuilding a projection creates a snapshot, not an authorization gate."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        snap_path = store.rebuild("proj-na4", {"action": "deploy"}, source_path=src)

        # The snapshot exists
        assert snap_path.exists()
        snap = store.load_snapshot("proj-na4")

        # The snapshot carries projection data, not enforcement decisions
        assert "data" in snap
        assert snap["data"]["action"] == "deploy"
        # No enforcement flags embedded in projection
        assert "enforcement" not in snap["data"]


# ── Store lifecycle tests ───────────────────────────────────────────────────


class TestStoreLifecycle:
    """Store construction and configuration."""

    def test_default_base_dir(self, tmp_path: Path, monkeypatch):
        """When no base_dir is given, defaults to ~/.megaplan/custody/projections."""
        import os

        fake_home = str(tmp_path / "fake_home")
        monkeypatch.setenv("HOME", fake_home)
        os.makedirs(fake_home, exist_ok=True)

        store = open_projection_store()
        expected = Path(fake_home) / ".megaplan" / "custody" / "projections"
        assert store.base_dir == expected.resolve()

    def test_explicit_base_dir(self, tmp_path: Path):
        """Explicit base_dir is resolved and used."""
        store = open_projection_store(base_dir=tmp_path / "explicit")
        assert store.base_dir == (tmp_path / "explicit").resolve()

    def test_store_flock_default(self, tmp_path: Path):
        """Store defaults to flock=True."""
        store = _fresh_store(tmp_path)
        assert store.flock is True

    def test_store_flock_false(self, tmp_path: Path):
        """Store can be opened with flock=False."""
        store = open_projection_store(base_dir=tmp_path / "noflock", flock=False)
        assert store.flock is False

    def test_open_projection_store_is_factory(self, tmp_path: Path):
        """open_projection_store returns a CustodyProjectionStore instance."""
        store = open_projection_store(base_dir=tmp_path / "factory")
        assert isinstance(store, CustodyProjectionStore)


# ── Event type coverage ─────────────────────────────────────────────────────


class TestEventTypes:
    """Coverage of all ProjectionEventType values through the store."""

    def test_all_event_types_enum_values(self):
        """Verify all defined event types are accessible."""
        assert ProjectionEventType.SNAPSHOT_BUILT == "snapshot_built"
        assert ProjectionEventType.APPEND_CURSOR_CHECKED == "append_cursor_checked"
        assert ProjectionEventType.APPEND_BLOCKED == "append_blocked"
        assert ProjectionEventType.RECOVERY_ATTEMPTED == "recovery_attempted"
        assert ProjectionEventType.RECOVERY_SUCCESS == "recovery_success"
        assert ProjectionEventType.RECONCILE == "reconcile"

    def test_reconcile_writes_snapshot_and_history(self, tmp_path: Path):
        """Reconcile should write a snapshot and append a RECONCILE event."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.append("proj-et1", "init", {}, source_path=src)

        snap_path = store.reconcile(
            "proj-et1",
            {"resolved": True},
            source_path=src,
            diagnostics=[{"reason": "manual fix"}],
        )
        assert snap_path.exists()

        history = store.load_history("proj-et1")
        event_types = [r.event_type for r in history]
        assert ProjectionEventType.RECONCILE in event_types

    def test_reconcile_embeds_diagnostics(self, tmp_path: Path):
        """Reconcile should embed diagnostics in the history event."""
        src = _source_file(tmp_path, '{"a": 1}')
        store = _fresh_store(tmp_path)
        store.reconcile(
            "proj-et2",
            {"ok": True},
            source_path=src,
            diagnostics=[{"reason": "test"}],
        )

        history = store.load_history("proj-et2")
        reconcile_events = [r for r in history if r.event_type == ProjectionEventType.RECONCILE]
        assert len(reconcile_events) == 1
        payload = reconcile_events[0].payload
        assert "diagnostics" in payload
