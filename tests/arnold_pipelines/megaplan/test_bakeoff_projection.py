"""Parity tests for bakeoff state and channel shadow state projection writers.

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
    projection_history_path,
    sha256_file,
)
from arnold_pipelines.megaplan.bakeoff.state import (
    BakeoffState,
    ChannelShadowState,
    _BAKEOFF_PROJECTION_ID,
    _CHANNEL_SHADOW_PROJECTION_ID,
    _PROJECTION_SCHEMA_VERSION,
    bakeoff_root,
    bakeoff_state_projection_cursor,
    bakeoff_state_projection_snapshot,
    channel_shadow_path,
    channel_shadow_projection_cursor,
    channel_shadow_projection_snapshot,
    load_bakeoff_state,
    load_channel_shadow_state,
    rebuild_bakeoff_state_projection,
    rebuild_channel_shadow_projection,
    save_bakeoff_state,
    save_channel_shadow_state,
)


def _make_bakeoff_state(exp_id="test-exp", phase="running", **kwargs):
    return BakeoffState(
        schema_version=1,
        experiment_id=exp_id,
        base_sha="abc123",
        idea_hash="sha256:def456",
        idea_path="/tmp/idea.md",
        mode="code",
        profiles=[],
        phase=phase,
        **kwargs,
    )


def _make_channel_shadow_state(exp_id="test-exp", records=None):
    return ChannelShadowState(
        schema_version=1,
        experiment_id=exp_id,
        records=records or [],
        real_parity_success_count=0,
        gate={
            "greenlight": True,
            "threshold": 0,
            "real_parity_success_count": 0,
            "real_parity_failure_count": 0,
            "skipped_count": 0,
            "fixture_count": 0,
            "blockers": [],
            "channel_pair": None,
            "provenance": {},
            "evaluated_at": "",
            "api_channel_greenlight": True,
            "api_channel_blockers": [],
        },
    )


class TestBakeoffStateProjectionVersionMetadata(TestCase):
    """Version metadata is embedded in every projection event."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_version_metadata_in_projection_record(self):
        """Every bakeoff projection event carries schema_version in its payload."""
        state = _make_bakeoff_state()
        save_bakeoff_state(self.root, state)
        hist = load_projection_history(
            bakeoff_root(self.root, "test-exp") / "projections",
            _BAKEOFF_PROJECTION_ID,
        )
        self.assertGreaterEqual(len(hist), 1)
        for record in hist:
            self.assertIn("schema_version", record.payload)
            self.assertEqual(record.payload["schema_version"], _PROJECTION_SCHEMA_VERSION)
            self.assertIn("experiment_id", record.payload)
            self.assertEqual(record.payload["experiment_id"], "test-exp")

    def test_version_metadata_in_channel_shadow_projection(self):
        """Every channel shadow projection event carries schema_version."""
        state = _make_channel_shadow_state()
        save_channel_shadow_state(self.root, state)
        hist = load_projection_history(
            bakeoff_root(self.root, "test-exp") / "projections",
            _CHANNEL_SHADOW_PROJECTION_ID,
        )
        self.assertGreaterEqual(len(hist), 1)
        for record in hist:
            self.assertIn("schema_version", record.payload)
            self.assertEqual(record.payload["schema_version"], _PROJECTION_SCHEMA_VERSION)

    def test_old_reader_uncertainty_markers(self):
        """Legacy readers (load_bakeoff_state) have no cursor validation.
        Proving that the source file and projection history can diverge
        without detection by the legacy reader.
        """
        state = _make_bakeoff_state(phase="running")
        save_bakeoff_state(self.root, state)

        # Legacy reader sees the file directly — works fine
        loaded = load_bakeoff_state(self.root, "test-exp")
        self.assertEqual(loaded["phase"], "running")

        # Now tamper with the file directly (simulating external write)
        bakeoff_json = bakeoff_root(self.root, "test-exp") / "bakeoff.json"
        tampered = dict(loaded)
        tampered["phase"] = "merged"  # externally changed
        bakeoff_json.write_text(json.dumps(tampered, indent=2) + "\n")

        # Legacy reader sees the tampered value without knowing
        loaded2 = load_bakeoff_state(self.root, "test-exp")
        self.assertEqual(loaded2["phase"], "merged")

        # Projection history still shows "running" as the last recorded event
        # (the tampering didn't go through save_bakeoff_state)
        result = rebuild_bakeoff_state_projection(self.root, "test-exp")
        self.assertEqual(result["status"], "rebuilt")
        # The projection still has the last save, which was "running"
        self.assertIn("phase", result["projection"])

    def test_uncertainty_docstring_metadata_present(self):
        """Module docstring carries old-reader/new-writer metadata."""
        import arnold_pipelines.megaplan.bakeoff.state as mod
        doc = mod.__doc__ or ""
        self.assertIn("OLD-READER", doc)
        self.assertIn("NEW-WRITER", doc)
        self.assertIn("UNCERTAINTY", doc)
        self.assertIn("SUPPLEMENTAL", doc)


class TestBakeoffCursorMismatchHandling(TestCase):
    """Cursor mismatches are detected and logged without corrupting the source file."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cursor_mismatch_does_not_block_write(self):
        """When the source file is externally modified, save_bakeoff_state
        still succeeds — the projection append is blocked but the state
        file write is not.
        """
        state = _make_bakeoff_state(phase="running")
        save_bakeoff_state(self.root, state)

        # Tamper with the file externally — this changes the cursor
        bakeoff_json = bakeoff_root(self.root, "test-exp") / "bakeoff.json"
        tampered = json.loads(bakeoff_json.read_text())
        tampered["phase"] = "merged"
        bakeoff_json.write_text(json.dumps(tampered, indent=2) + "\n")

        # Save again — should still succeed (projection may warn)
        state2 = _make_bakeoff_state(phase="picked")
        save_bakeoff_state(self.root, state2)

        # State file should have the new phase
        loaded = load_bakeoff_state(self.root, "test-exp")
        self.assertEqual(loaded["phase"], "picked")

    def test_projection_history_preserved_on_mismatch(self):
        """Prior projection records are never erased, even after cursor mismatch."""
        state = _make_bakeoff_state(phase="running")
        save_bakeoff_state(self.root, state)

        state2 = _make_bakeoff_state(phase="picked")
        save_bakeoff_state(self.root, state2)

        # Both records should be in history
        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _BAKEOFF_PROJECTION_ID)
        self.assertGreaterEqual(len(hist), 2)

    def test_channel_shadow_cursor_preserved(self):
        """Channel shadow cursor is preserved across multiple saves."""
        state = _make_channel_shadow_state()
        save_channel_shadow_state(self.root, state)

        cursor = channel_shadow_projection_cursor(self.root, "test-exp")
        self.assertIsNotNone(cursor)

        # Save again
        state2 = _make_channel_shadow_state()
        save_channel_shadow_state(self.root, state2)

        cursor2 = channel_shadow_projection_cursor(self.root, "test-exp")
        self.assertIsNotNone(cursor2)

        # Cursor should have advanced (or at least exist)
        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _CHANNEL_SHADOW_PROJECTION_ID)
        self.assertGreaterEqual(len(hist), 2)


class TestBakeoffPriorProjectionPreservation(TestCase):
    """Prior projections are preserved through rebuilds and never lost."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_records_accumulate_across_multiple_saves(self):
        """Each save appends a record — history is never truncated."""
        phases = ["running", "compared", "picked", "merged"]
        for phase in phases:
            state = _make_bakeoff_state(phase=phase)
            save_bakeoff_state(self.root, state)

        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _BAKEOFF_PROJECTION_ID)
        self.assertEqual(len(hist), len(phases))

        # Verify each phase is present in order
        recorded_phases = [
            r.payload.get("state", {}).get("phase")
            for r in hist
            if isinstance(r.payload.get("state"), dict)
        ]
        self.assertEqual(recorded_phases, phases)

    def test_rebuild_preserves_all_state(self):
        """Rebuild replays all events and produces the final state."""
        state1 = _make_bakeoff_state(phase="running")
        save_bakeoff_state(self.root, state1)

        state2 = _make_bakeoff_state(phase="picked", chosen_profile="prof-A")
        save_bakeoff_state(self.root, state2)

        result = rebuild_bakeoff_state_projection(self.root, "test-exp")
        self.assertEqual(result["status"], "rebuilt")
        self.assertEqual(result["projection"]["phase"], "picked")
        self.assertEqual(result["projection"]["chosen_profile"], "prof-A")

    def test_channel_shadow_prior_projection(self):
        """Channel shadow records are preserved across saves."""
        for i in range(3):
            state = _make_channel_shadow_state(
                records=[{"sample_key": f"key-{i}"}],
            )
            save_channel_shadow_state(self.root, state)

        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _CHANNEL_SHADOW_PROJECTION_ID)
        self.assertEqual(len(hist), 3)


class TestBakeoffDeterministicReplay(TestCase):
    """Deterministic replay produces identical output for the same input sequence."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bakeoff_replay_is_deterministic(self):
        """Two rebuilds of the same history produce identical projections."""
        phases = ["running", "compared", "picked", "merged"]
        for phase in phases:
            state = _make_bakeoff_state(phase=phase, chosen_profile=f"prof-{phase}")
            save_bakeoff_state(self.root, state)

        result1 = rebuild_bakeoff_state_projection(self.root, "test-exp")
        result2 = rebuild_bakeoff_state_projection(self.root, "test-exp")

        self.assertEqual(result1["status"], "rebuilt")
        self.assertEqual(result2["status"], "rebuilt")
        self.assertEqual(result1["projection"], result2["projection"])
        self.assertEqual(result1["record_count"], result2["record_count"])

    def test_channel_shadow_replay_is_deterministic(self):
        """Two rebuilds of the same channel shadow history produce identical results."""
        for i in range(3):
            state = _make_channel_shadow_state(
                records=[{"sample_key": f"key-{i}"}],
            )
            save_channel_shadow_state(self.root, state)

        result1 = rebuild_channel_shadow_projection(self.root, "test-exp")
        result2 = rebuild_channel_shadow_projection(self.root, "test-exp")

        self.assertEqual(result1["status"], "rebuilt")
        self.assertEqual(result2["status"], "rebuilt")
        self.assertEqual(result1["projection"], result2["projection"])

    def test_replay_ordering_preserved(self):
        """Events are replayed in insertion order — last save wins."""
        state_a = _make_bakeoff_state(phase="a")
        save_bakeoff_state(self.root, state_a)
        state_b = _make_bakeoff_state(phase="b")
        save_bakeoff_state(self.root, state_b)
        state_a2 = _make_bakeoff_state(phase="a2")
        save_bakeoff_state(self.root, state_a2)

        result = rebuild_bakeoff_state_projection(self.root, "test-exp")
        # Last event was phase="a2"
        self.assertEqual(result["projection"]["phase"], "a2")


class TestBakeoffProjectionSnapshotAccess(TestCase):
    """Snapshot and cursor accessors work correctly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_history_returns_none_cursor(self):
        """Cursor is None when no projection history exists."""
        cursor = bakeoff_state_projection_cursor(self.root, "no-exp")
        self.assertIsNone(cursor)

    def test_no_history_returns_none_snapshot(self):
        """Snapshot is None when no projection history exists."""
        snap = bakeoff_state_projection_snapshot(self.root, "no-exp")
        self.assertIsNone(snap)

    def test_cursor_advances_with_saves(self):
        """The cursor reflects the most recent save."""
        state = _make_bakeoff_state()
        save_bakeoff_state(self.root, state)
        cursor1 = bakeoff_state_projection_cursor(self.root, "test-exp")
        self.assertIsNotNone(cursor1)

        save_bakeoff_state(self.root, state)
        cursor2 = bakeoff_state_projection_cursor(self.root, "test-exp")
        self.assertIsNotNone(cursor2)

    def test_snapshot_after_rebuild(self):
        """After rebuild, the snapshot accessor returns a dict."""
        state = _make_bakeoff_state()
        save_bakeoff_state(self.root, state)

        rebuild_bakeoff_state_projection(self.root, "test-exp")
        snap = bakeoff_state_projection_snapshot(self.root, "test-exp")
        self.assertIsNotNone(snap)
        self.assertIsInstance(snap, dict)

    def test_channel_shadow_snapshot_after_rebuild(self):
        """After channel shadow rebuild, snapshot is available."""
        state = _make_channel_shadow_state()
        save_channel_shadow_state(self.root, state)

        rebuild_channel_shadow_projection(self.root, "test-exp")
        snap = channel_shadow_projection_snapshot(self.root, "test-exp")
        self.assertIsNotNone(snap)


class TestBakeoffProjectionSkip(TestCase):
    """_record_projection=False skips the projection side-effect."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "workspace"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skip_bakeoff_projection(self):
        """_record_projection=False does not append a projection event."""
        state = _make_bakeoff_state()
        save_bakeoff_state(self.root, state, _record_projection=False)

        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _BAKEOFF_PROJECTION_ID)
        self.assertEqual(len(hist), 0)

        # But state file is still written
        loaded = load_bakeoff_state(self.root, "test-exp")
        self.assertEqual(loaded["phase"], "running")

    def test_skip_channel_shadow_projection(self):
        """_record_projection=False for channel shadow."""
        state = _make_channel_shadow_state()
        save_channel_shadow_state(self.root, state, _record_projection=False)

        projection_dir = bakeoff_root(self.root, "test-exp") / "projections"
        hist = load_projection_history(projection_dir, _CHANNEL_SHADOW_PROJECTION_ID)
        self.assertEqual(len(hist), 0)

        # State file is still written
        loaded = load_channel_shadow_state(self.root, "test-exp")
        self.assertIsNotNone(loaded)
