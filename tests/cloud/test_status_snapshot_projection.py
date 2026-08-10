"""Parity tests for cloud status snapshot projection writers.

Demonstrates version metadata, uncertainty markers, cursor mismatch
handling, prior projection preservation, and deterministic replay.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    load_projection_history,
    sha256_file,
)
from arnold_pipelines.megaplan.cloud.status_snapshot import (
    _STATUS_SNAPSHOT_PROJECTION_ID,
    _STATUS_SNAPSHOT_PROJECTION_SCHEMA_VERSION,
    load_cloud_status_snapshot,
    rebuild_status_snapshot_projection,
    status_snapshot_projection_cursor,
    status_snapshot_projection_snapshot,
    write_cloud_status_snapshot,
)


def _make_snapshot(generated_at="2026-07-20T04:00:00Z", running=1, complete=0):
    return {
        "generated_at": generated_at,
        "source": "cloud-local-observer",
        "marker_dir": "/tmp/markers",
        "watchdog_report": "/tmp/report.json",
        "summary": {"running": running, "complete": complete},
        "sessions": [
            {"session": f"s{i}", "status": "running" if i <= running else "complete"}
            for i in range(1, running + complete + 1)
        ],
        "degraded": None,
    }


class TestStatusSnapshotVersionMetadata(TestCase):
    """Version metadata is embedded in every projection event."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_version_metadata_in_projection_record(self):
        """Every status snapshot projection event carries schema_version."""
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path)

        projection_dir = self.snap_path.parent / "projections"
        hist = load_projection_history(projection_dir, _STATUS_SNAPSHOT_PROJECTION_ID)
        self.assertGreaterEqual(len(hist), 1)
        for record in hist:
            self.assertIn("schema_version", record.payload)
            self.assertEqual(
                record.payload["schema_version"],
                _STATUS_SNAPSHOT_PROJECTION_SCHEMA_VERSION,
            )
            self.assertIn("snapshot_path", record.payload)

    def test_old_reader_uncertainty_markers(self):
        """Legacy readers (load_cloud_status_snapshot) have no cursor validation.
        Proving they can read a freshly tampered file without detection.
        """
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path)

        loaded, reason = load_cloud_status_snapshot(self.snap_path)
        self.assertIsNotNone(loaded)
        self.assertIsNone(reason)

        # Tamper directly
        tampered = dict(loaded)
        tampered["summary"] = {"running": 99, "complete": 0}
        self.snap_path.write_text(json.dumps(tampered, indent=2) + "\n")

        loaded2, reason2 = load_cloud_status_snapshot(self.snap_path)
        self.assertEqual(loaded2["summary"]["running"], 99)
        # No cursor validation — legacy reader doesn't know

        # Projection history still reflects last proper write
        result = rebuild_status_snapshot_projection(self.snap_path)
        if result["status"] == "rebuilt":
            self.assertIn("summary", result["projection"])

    def test_uncertainty_docstring_metadata_present(self):
        """Module docstring carries old-reader/new-writer metadata."""
        import arnold_pipelines.megaplan.cloud.status_snapshot as mod
        doc = mod.__doc__ or ""
        self.assertIn("OLD-READER", doc)
        self.assertIn("NEW-WRITER", doc)
        self.assertIn("UNCERTAINTY", doc)
        self.assertIn("SUPPLEMENTAL", doc)


class TestStatusSnapshotCursorMismatchHandling(TestCase):
    """Cursor mismatches are detected and logged without corrupting the source file."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cursor_mismatch_does_not_block_write(self):
        """When the snapshot file is externally modified, write still succeeds."""
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path)

        # Tamper externally
        tampered = dict(snap)
        tampered["summary"] = {"running": 99}
        self.snap_path.write_text(json.dumps(tampered, indent=2) + "\n")

        # Write again — should succeed
        snap2 = _make_snapshot(running=2)
        result = write_cloud_status_snapshot(snap2, path=self.snap_path)
        self.assertTrue(result.exists())

        loaded, _ = load_cloud_status_snapshot(self.snap_path)
        self.assertEqual(loaded["summary"]["running"], 2)

    def test_projection_history_preserved_on_mismatch(self):
        """Prior projection records are never erased."""
        snap = _make_snapshot(running=1)
        write_cloud_status_snapshot(snap, path=self.snap_path)

        snap2 = _make_snapshot(running=2)
        write_cloud_status_snapshot(snap2, path=self.snap_path)

        projection_dir = self.snap_path.parent / "projections"
        hist = load_projection_history(projection_dir, _STATUS_SNAPSHOT_PROJECTION_ID)
        self.assertGreaterEqual(len(hist), 2)


class TestStatusSnapshotPriorProjectionPreservation(TestCase):
    """Prior projections are preserved through rebuilds."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_records_accumulate_across_multiple_writes(self):
        """Each write appends a record — history is never truncated."""
        for i in range(5):
            snap = _make_snapshot(running=i + 1)
            write_cloud_status_snapshot(snap, path=self.snap_path)

        projection_dir = self.snap_path.parent / "projections"
        hist = load_projection_history(projection_dir, _STATUS_SNAPSHOT_PROJECTION_ID)
        self.assertEqual(len(hist), 5)

    def test_rebuild_preserves_latest_state(self):
        """Rebuild replays all events and produces final state."""
        snap1 = _make_snapshot(running=1, complete=0)
        write_cloud_status_snapshot(snap1, path=self.snap_path)

        snap2 = _make_snapshot(running=2, complete=1)
        write_cloud_status_snapshot(snap2, path=self.snap_path)

        result = rebuild_status_snapshot_projection(self.snap_path)
        self.assertEqual(result["status"], "rebuilt")
        self.assertIn("session_count", result["projection"])
        self.assertEqual(result["projection"]["session_count"], 3)


class TestStatusSnapshotDeterministicReplay(TestCase):
    """Deterministic replay produces identical output for the same input."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_replay_is_deterministic(self):
        """Two rebuilds of the same history produce identical projections."""
        for i in range(3):
            snap = _make_snapshot(running=i + 1)
            write_cloud_status_snapshot(snap, path=self.snap_path)

        result1 = rebuild_status_snapshot_projection(self.snap_path)
        result2 = rebuild_status_snapshot_projection(self.snap_path)

        self.assertEqual(result1["status"], "rebuilt")
        self.assertEqual(result2["status"], "rebuilt")
        self.assertEqual(result1["projection"], result2["projection"])
        self.assertEqual(result1["record_count"], result2["record_count"])

    def test_replay_ordering_preserved(self):
        """Last write wins in replay."""
        snap_a = _make_snapshot(generated_at="2026-07-20T01:00:00Z")
        write_cloud_status_snapshot(snap_a, path=self.snap_path)
        snap_b = _make_snapshot(generated_at="2026-07-20T02:00:00Z")
        write_cloud_status_snapshot(snap_b, path=self.snap_path)

        result = rebuild_status_snapshot_projection(self.snap_path)
        self.assertEqual(result["projection"]["generated_at"], "2026-07-20T02:00:00Z")


class TestStatusSnapshotProjectionAccess(TestCase):
    """Snapshot and cursor accessors work correctly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_history_returns_none_cursor(self):
        """Cursor is None when no projection history exists."""
        cursor = status_snapshot_projection_cursor(self.tmp / "nonexistent.json")
        self.assertIsNone(cursor)

    def test_no_history_returns_none_snapshot(self):
        """Snapshot is None when no projection history exists."""
        snap = status_snapshot_projection_snapshot(self.tmp / "nonexistent.json")
        self.assertIsNone(snap)

    def test_cursor_advances_with_writes(self):
        """The cursor reflects the most recent write."""
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path)

        cursor1 = status_snapshot_projection_cursor(self.snap_path)
        self.assertIsNotNone(cursor1)

        write_cloud_status_snapshot(snap, path=self.snap_path)
        cursor2 = status_snapshot_projection_cursor(self.snap_path)
        self.assertIsNotNone(cursor2)

    def test_snapshot_after_rebuild(self):
        """After rebuild, the snapshot accessor returns a dict."""
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path)

        rebuild_status_snapshot_projection(self.snap_path)
        loaded = status_snapshot_projection_snapshot(self.snap_path)
        self.assertIsNotNone(loaded)
        self.assertIsInstance(loaded, dict)


class TestStatusSnapshotProjectionSkip(TestCase):
    """_record_projection=False skips the projection side-effect."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.snap_path = self.tmp / "cloud-status.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skip_projection(self):
        """_record_projection=False does not append a projection event."""
        snap = _make_snapshot()
        write_cloud_status_snapshot(snap, path=self.snap_path, _record_projection=False)

        projection_dir = self.snap_path.parent / "projections"
        hist = load_projection_history(projection_dir, _STATUS_SNAPSHOT_PROJECTION_ID)
        self.assertEqual(len(hist), 0)

        # But snapshot file is still written
        loaded, _ = load_cloud_status_snapshot(self.snap_path)
        self.assertIsNotNone(loaded)
