"""Focused registry tests for projection rebuild module.

Covers T6 requirements:

* Registry registration / unregistration / duplicate-rejection.
* Source cursor vector capture across all registered projections.
* Ordered view digesting — deterministic, stable across same-input calls.
* Delete/rebuild comparison — parity detection, mismatch detection,
  missing-projection handling.
* Builder purity — same records produce same digest.
* Never-mutates-source-evidence — rebuild operations are read-only.
* Reuses fold/reduce patterns — builders accept source records and
  accumulate into a projection view.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import pytest

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
)
from arnold_pipelines.megaplan.observability.projection_rebuild import (
    ProjectionBuilderFn,
    ProjectionRegistry,
    RebuildComparisonReport,
    SourceLoaderFn,
    capture_source_cursor_vector,
    compare_all_projections,
    compare_rebuild,
    compute_projection_digest,
    rebuild_all_projections,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _identity_builder(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Builder that returns records unchanged (wrapped in a dict)."""
    return {"records": [dict(r) for r in records], "count": len(records)}


def _accumulating_builder(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Builder that folds records into an accumulated view (reducer pattern)."""
    acc: Dict[str, Any] = {"total": 0, "keys_seen": []}
    for r in records:
        acc["total"] += r.get("value", 0)
        key = r.get("key")
        if key is not None:
            acc["keys_seen"].append(key)
    return acc


def _make_source_file(tmp_path: Path, *lines: str) -> Path:
    """Create a JSONL source file with the given lines."""
    path = tmp_path / "source.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return path


def _fresh_registry() -> ProjectionRegistry:
    """Return a new, empty registry."""
    return ProjectionRegistry()


# ── Registry tests ──────────────────────────────────────────────────────────


class TestRegistration:
    """Registration, unregistration, and queries."""

    def test_register_and_lookup(self, tmp_path: Path):
        """Registered projections should be queryable."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("proj-a", _identity_builder, source_path=src)

        assert registry.is_registered("proj-a")
        assert "proj-a" in registry.list_registered()

    def test_register_duplicate_raises(self, tmp_path: Path):
        """Registering the same ID twice should raise ValueError."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("p1", _identity_builder, source_path=src)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("p1", _identity_builder, source_path=src)

    def test_unregister(self, tmp_path: Path):
        """Unregister should remove the projection."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("p1", _identity_builder, source_path=src)
        registry.unregister("p1")
        assert not registry.is_registered("p1")
        assert "p1" not in registry.list_registered()

    def test_unregister_idempotent(self):
        """Unregister of non-existent ID should not raise."""
        registry = _fresh_registry()
        registry.unregister("nonexistent")  # no-op

    def test_list_registered_sorted(self, tmp_path: Path):
        """list_registered should return sorted IDs."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        for pid in ("proj-c", "proj-a", "proj-b"):
            registry.register(pid, _identity_builder, source_path=src)
        assert registry.list_registered() == ("proj-a", "proj-b", "proj-c")

    def test_source_path_lookup(self, tmp_path: Path):
        """source_path should return the registered path."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"x": 1}')
        registry.register("p1", _identity_builder, source_path=src)
        assert registry.source_path("p1") == src.resolve()

    def test_source_path_missing_raises(self):
        """source_path for non-existent ID should raise KeyError."""
        registry = _fresh_registry()
        with pytest.raises(KeyError):
            registry.source_path("missing")

    def test_builder_lookup(self, tmp_path: Path):
        """builder() should return the registered builder function."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("p1", _identity_builder, source_path=src)
        assert registry.builder("p1") is _identity_builder

    def test_builder_missing_raises(self):
        """builder() for non-existent ID should raise KeyError."""
        registry = _fresh_registry()
        with pytest.raises(KeyError):
            registry.builder("missing")

    def test_custom_source_loader(self, tmp_path: Path):
        """Custom source loader should be used when provided."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')

        def _custom_loader(path: Path) -> Sequence[Mapping[str, Any]]:
            return ({"custom": True, "path": str(path)},)

        registry.register(
            "p1", _identity_builder, source_path=src, source_loader=_custom_loader
        )
        result = registry.rebuild("p1")
        assert result["records"] == [{"custom": True, "path": str(src.resolve())}]

    def test_multiple_independent_registrations(self, tmp_path: Path):
        """Multiple projections can coexist with different source paths."""
        registry = _fresh_registry()
        src_a = _make_source_file(tmp_path / "a", '{"v": 1}')
        src_b = _make_source_file(tmp_path / "b", '{"v": 2}')
        registry.register("a", _identity_builder, source_path=src_a)
        registry.register("b", _identity_builder, source_path=src_b)

        assert registry.list_registered() == ("a", "b")
        assert registry.source_path("a") != registry.source_path("b")


# ── Rebuild tests ───────────────────────────────────────────────────────────


class TestRebuild:
    """Rebuild operations via the registry."""

    def test_rebuild_uses_registered_builder(self, tmp_path: Path):
        """Rebuild should call the registered builder with source records."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}', '{"key": "b", "value": 20}')
        registry.register("acc", _accumulating_builder, source_path=src)

        result = registry.rebuild("acc")
        assert result["total"] == 30
        assert result["keys_seen"] == ["a", "b"]

    def test_rebuild_with_preloaded_records(self, tmp_path: Path):
        """Pre-loaded records should be used instead of reading from disk."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "disk"}')  # won't be read
        registry.register("p1", _identity_builder, source_path=src)

        preloaded = ({"key": "injected"},)
        result = registry.rebuild("p1", source_records=preloaded)
        assert result["records"] == [{"key": "injected"}]

    def test_rebuild_missing_projection_raises(self):
        """Rebuilding an unregistered projection should raise KeyError."""
        registry = _fresh_registry()
        with pytest.raises(KeyError):
            registry.rebuild("missing")

    def test_builder_purity(self, tmp_path: Path):
        """Same source records should produce the same rebuild (deterministic builder)."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}')
        registry.register("p1", _accumulating_builder, source_path=src)

        result1 = registry.rebuild("p1")
        result2 = registry.rebuild("p1")
        assert result1 == result2

    def test_builder_receives_records_in_order(self, tmp_path: Path):
        """Builder should receive records in file order."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path,
            '{"seq": 1}', '{"seq": 2}', '{"seq": 3}',
        )
        registry.register("p1", _identity_builder, source_path=src)

        result = registry.rebuild("p1")
        assert result["records"][0]["seq"] == 1
        assert result["records"][1]["seq"] == 2
        assert result["records"][2]["seq"] == 3


# ── Source cursor vector tests ──────────────────────────────────────────────


class TestSourceCursorVector:
    """capture_source_cursor_vector tests."""

    def test_captures_all_registered(self, tmp_path: Path):
        """Should compute a cursor for every registered projection."""
        registry = _fresh_registry()
        src_a = _make_source_file(tmp_path / "a", '{"a": 1}')
        src_b = _make_source_file(tmp_path / "b", '{"b": 1}', '{"b": 2}')
        registry.register("a", _identity_builder, source_path=src_a)
        registry.register("b", _identity_builder, source_path=src_b)

        vector = capture_source_cursor_vector(registry)
        assert set(vector.keys()) == {"a", "b"}
        assert vector["a"].source_record_count == 1
        assert vector["b"].source_record_count == 2

    def test_empty_registry(self):
        """Empty registry should produce empty vector."""
        registry = _fresh_registry()
        vector = capture_source_cursor_vector(registry)
        assert vector == {}

    def test_cursor_includes_digest(self, tmp_path: Path):
        """Each cursor should carry a source digest."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"x": 1}')
        registry.register("p1", _identity_builder, source_path=src)

        vector = capture_source_cursor_vector(registry)
        assert vector["p1"].source_digest.startswith("sha256:")

    def test_cursor_for_missing_file(self, tmp_path: Path):
        """Cursor for non-existent source file should have record_count=0."""
        registry = _fresh_registry()
        missing_path = tmp_path / "does_not_exist.jsonl"
        registry.register("p1", _identity_builder, source_path=missing_path)

        vector = capture_source_cursor_vector(registry)
        assert vector["p1"].source_record_count == 0
        # sha256 of empty content
        assert vector["p1"].source_digest == "sha256:" + hashlib.sha256(b"").hexdigest()


# ── Ordered view digest tests ───────────────────────────────────────────────


class TestOrderedViewDigest:
    """compute_projection_digest tests."""

    def test_same_view_same_digest(self):
        """Two calls with the same view dict should produce the same digest."""
        view = {"a": 1, "b": 2}
        d1 = compute_projection_digest(view)
        d2 = compute_projection_digest(view)
        assert d1 == d2

    def test_different_views_different_digests(self):
        """Different views should produce different digests."""
        d1 = compute_projection_digest({"a": 1})
        d2 = compute_projection_digest({"a": 2})
        assert d1 != d2

    def test_dict_insertion_order_does_not_matter(self):
        """Insertion order of keys should not affect digest (canonical serialization)."""
        # Build two dicts with same content but different insertion orders
        view1: Dict[str, Any] = {}
        view1["b"] = 2
        view1["a"] = 1

        view2: Dict[str, Any] = {}
        view2["a"] = 1
        view2["b"] = 2

        assert compute_projection_digest(view1) == compute_projection_digest(view2)

    def test_digest_format(self):
        """Digest should be a sha256: prefix + 64 hex chars."""
        digest = compute_projection_digest({"x": 1})
        assert digest.startswith("sha256:")
        assert len(digest) == 7 + 64  # "sha256:" + 64 hex chars

    def test_empty_view_digest(self):
        """Empty view should produce a valid digest."""
        digest = compute_projection_digest({})
        assert digest.startswith("sha256:")
        assert len(digest) == 71

    def test_nested_dict_digest_stable(self):
        """Nested dicts should produce stable digests."""
        view = {"nested": {"deep": [1, 2, 3]}}
        d1 = compute_projection_digest(view)
        d2 = compute_projection_digest(view)
        assert d1 == d2

    def test_nested_dict_different_values(self):
        """Different nested values should produce different digests."""
        d1 = compute_projection_digest({"n": {"v": 1}})
        d2 = compute_projection_digest({"n": {"v": 2}})
        assert d1 != d2


# ── Compare rebuild tests ───────────────────────────────────────────────────


class TestCompareRebuild:
    """compare_rebuild tests."""

    def test_parity_when_digests_match(self, tmp_path: Path):
        """When rebuild matches existing, parity should be True."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}')
        registry.register("p1", _accumulating_builder, source_path=src)

        # Build the "existing" view from the same source
        existing_view = _accumulating_builder(
            registry.source_loader("p1")(registry.source_path("p1"))
        )

        report = compare_rebuild(registry, "p1", existing_projection_view=existing_view)
        assert report.parity is True
        assert report.rebuild_digest == report.existing_digest

    def test_mismatch_when_digests_differ(self, tmp_path: Path):
        """When rebuild differs from existing, parity should be False."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}')
        registry.register("p1", _accumulating_builder, source_path=src)

        # A different existing view
        existing_view = {"total": 999, "keys_seen": ["other"]}

        report = compare_rebuild(registry, "p1", existing_projection_view=existing_view)
        assert report.parity is False
        assert report.rebuild_digest != report.existing_digest

    def test_no_existing_view(self, tmp_path: Path):
        """Without existing view, parity is False with diagnostic."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}')
        registry.register("p1", _accumulating_builder, source_path=src)

        report = compare_rebuild(registry, "p1")
        assert report.parity is False
        assert report.existing_digest is None
        assert any("No existing" in d for d in report.diagnostics)

    def test_unregistered_projection(self):
        """Comparing an unregistered projection returns error report."""
        registry = _fresh_registry()
        report = compare_rebuild(registry, "missing")
        assert report.parity is False
        assert report.rebuild_digest == ""
        assert any("not registered" in d for d in report.diagnostics)

    def test_report_includes_source_cursor(self, tmp_path: Path):
        """Report should carry the source cursor at rebuild time."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        registry.register("p1", _identity_builder, source_path=src)

        report = compare_rebuild(registry, "p1")
        assert report.source_cursor is not None
        assert report.source_cursor.source_record_count == 2

    def test_preloaded_records_skip_disk_read(self, tmp_path: Path):
        """With preloaded records, source is not re-read."""
        registry = _fresh_registry()
        # Create a source file that differs from what we'll preload
        src = _make_source_file(tmp_path, '{"on_disk": true}')
        registry.register("p1", _identity_builder, source_path=src)

        preloaded = ({"injected": True},)
        report = compare_rebuild(registry, "p1", source_records=preloaded)
        # The rebuild should use preloaded records (injected=True), not disk
        assert report.parity is False  # no existing to compare
        assert report.rebuild_digest != ""

    def test_report_to_dict(self, tmp_path: Path):
        """RebuildComparisonReport.to_dict should produce serializable output."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("p1", _identity_builder, source_path=src)

        report = compare_rebuild(registry, "p1")
        d = report.to_dict()
        assert d["projection_id"] == "p1"
        assert isinstance(d["parity"], bool)
        assert "rebuild_digest" in d
        if d.get("source_cursor"):
            assert isinstance(d["source_cursor"], dict)

    def test_never_mutates_source_file(self, tmp_path: Path):
        """compare_rebuild must not modify the source file."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}', '{"b": 2}')
        original_content = src.read_bytes()
        original_mtime = src.stat().st_mtime

        registry.register("p1", _identity_builder, source_path=src)
        compare_rebuild(registry, "p1")

        # Source file must be unchanged
        assert src.read_bytes() == original_content
        assert src.stat().st_mtime == original_mtime


# ── Bulk rebuild / compare tests ────────────────────────────────────────────


class TestBulkRebuild:
    """rebuild_all_projections and compare_all_projections tests."""

    def test_rebuild_all(self, tmp_path: Path):
        """Should rebuild every registered projection."""
        registry = _fresh_registry()
        src_a = _make_source_file(tmp_path / "a", '{"key": "a", "value": 10}')
        src_b = _make_source_file(tmp_path / "b", '{"key": "b", "value": 20}')
        registry.register("a", _accumulating_builder, source_path=src_a)
        registry.register("b", _accumulating_builder, source_path=src_b)

        results = rebuild_all_projections(registry)
        assert set(results.keys()) == {"a", "b"}
        assert results["a"]["total"] == 10
        assert results["b"]["total"] == 20

    def test_rebuild_all_empty_registry(self):
        """Empty registry should produce empty results."""
        registry = _fresh_registry()
        results = rebuild_all_projections(registry)
        assert results == {}

    def test_compare_all_parity(self, tmp_path: Path):
        """When all rebuilds match existing, all parity should be True."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 42}')
        registry.register("p1", _accumulating_builder, source_path=src)

        existing_view = _accumulating_builder(
            registry.source_loader("p1")(registry.source_path("p1"))
        )
        reports = compare_all_projections(
            registry, existing_views={"p1": existing_view}
        )
        assert reports["p1"].parity is True

    def test_compare_all_mixed(self, tmp_path: Path):
        """Mixed parity should report correctly."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"key": "a", "value": 10}')
        registry.register("p1", _accumulating_builder, source_path=src)

        # Existing view that differs
        reports = compare_all_projections(
            registry, existing_views={"p1": {"total": 999}}
        )
        assert reports["p1"].parity is False


# ── Fold/reducer pattern tests ──────────────────────────────────────────────


class TestReducerPatterns:
    """Verify that builder functions follow fold/reduce patterns."""

    def test_accumulating_builder_folds_over_records(self, tmp_path: Path):
        """The accumulating builder should fold records into a summary (reducer pattern)."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path,
            '{"key": "first", "value": 10}',
            '{"key": "second", "value": 15}',
            '{"key": "third", "value": 5}',
        )
        registry.register("acc", _accumulating_builder, source_path=src)
        result = registry.rebuild("acc")

        assert result["total"] == 30  # 10 + 15 + 5
        assert result["keys_seen"] == ["first", "second", "third"]

    def test_empty_source_produces_base_accumulator(self, tmp_path: Path):
        """Empty source records should produce the base accumulator state."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path)  # empty
        registry.register("acc", _accumulating_builder, source_path=src)

        result = registry.rebuild("acc")
        assert result["total"] == 0
        assert result["keys_seen"] == []

    def test_identity_builder_preserves_all_records(self, tmp_path: Path):
        """Identity builder should return all source records unchanged."""
        registry = _fresh_registry()
        records = ('{"id": 1}', '{"id": 2}', '{"id": 3}')
        src = _make_source_file(tmp_path, *records)
        registry.register("id", _identity_builder, source_path=src)

        result = registry.rebuild("id")
        assert result["count"] == 3
        assert result["records"][0]["id"] == 1
        assert result["records"][1]["id"] == 2
        assert result["records"][2]["id"] == 3

    def test_builder_never_mutates_input_records(self, tmp_path: Path):
        """Builder must not mutate the source records it receives."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"value": 10}')
        registry.register("p1", _identity_builder, source_path=src)

        source_records = registry.source_loader("p1")(registry.source_path("p1"))
        original = [dict(r) for r in source_records]

        result = registry.rebuild("p1")
        # Source records should be unchanged
        assert [dict(r) for r in source_records] == original
        # Result should be a copy, not the same objects
        assert result["records"] is not source_records


# ── Integration-style tests ─────────────────────────────────────────────────


class TestIntegration:
    """End-to-end scenarios combining registry, cursors, digest, and comparison."""

    def test_full_rebuild_compare_cycle(self, tmp_path: Path):
        """Register -> rebuild -> digest -> compare -> parity check."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path,
            '{"event": "init", "data": {"x": 1}}',
            '{"event": "update", "data": {"x": 2}}',
        )

        def _project_events(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
            """Simulate a simple event projection fold."""
            state: Dict[str, Any] = {"events": [], "final_x": None}
            for r in records:
                state["events"].append(r["event"])
                data = r.get("data", {})
                if "x" in data:
                    state["final_x"] = data["x"]
            return state

        registry.register("events", _project_events, source_path=src)

        # Capture cursor vector
        vector = capture_source_cursor_vector(registry)
        assert vector["events"].source_record_count == 2

        # Rebuild
        rebuilt = registry.rebuild("events")
        assert rebuilt["final_x"] == 2
        assert rebuilt["events"] == ["init", "update"]

        # Compute digest
        digest = compute_projection_digest(rebuilt)
        assert digest.startswith("sha256:")

        # Compare against self → parity
        report = compare_rebuild(
            registry, "events", existing_projection_view=rebuilt
        )
        assert report.parity is True

    def test_source_cursor_changes_when_source_grows(self, tmp_path: Path):
        """Cursor should reflect source file growth."""
        registry = _fresh_registry()
        src = _make_source_file(tmp_path, '{"a": 1}')
        registry.register("p1", _identity_builder, source_path=src)

        cursor1 = capture_source_cursor_vector(registry)["p1"]
        assert cursor1.source_record_count == 1

        # Add more records
        src.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
        cursor2 = capture_source_cursor_vector(registry)["p1"]
        assert cursor2.source_record_count == 3
        assert cursor2.source_digest != cursor1.source_digest
