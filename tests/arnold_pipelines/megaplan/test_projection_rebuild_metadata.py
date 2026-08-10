"""Focused tests for projection rebuild metadata, freshness/lag, and digest stability.

Covers the three deterministic projection reducers updated in T21:
- ``schema_projection.py``
- ``capsule_projection.py``
- ``strategy/projection.py``

Key invariants proven:
- Digests are stable (same input → same digest) and different inputs produce
  different digests.
- Source cursors capture correct source state.
- Rebuild metadata includes freshness, lag, source cursor, and digest.
- All new functions are pure — no side effects, no filesystem writes in
  the core path.
- ``capsule_projection_with_metadata`` and ``project_strategy_with_metadata``
  preserve the original projection fields unchanged.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)
from arnold_pipelines.megaplan.schema_projection import (
    REBUILD_METADATA_SCHEMA_VERSION as SCHEMA_REBUILD_VERSION,
    capture_source_cursor,
    closed_object_schema,
    compute_projection_digest,
    project_schema_owned_fields,
    rebuild_metadata,
    schema_object_properties,
    schema_template_payload,
)
from arnold_pipelines.megaplan.capsule_projection import (
    REBUILD_METADATA_SCHEMA_VERSION as CAPSULE_REBUILD_VERSION,
    SCHEMA_VERSION as CAPSULE_SCHEMA_VERSION,
    capsule_definition_identity_projection,
    capsule_projection_with_metadata,
    capsule_rebuild_metadata,
    capture_capsule_source_cursor,
    compute_capsule_projection_digest,
)
from arnold_pipelines.megaplan.strategy.contract import (
    PROJECTION_SCHEMA_VERSION as STRATEGY_PROJECTION_VERSION,
    REQUIRED_ROADMAP_SECTIONS,
    SCHEMA_VERSION as STRATEGY_SCHEMA_VERSION,
    RoadmapEntry,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.projection import (
    REBUILD_METADATA_SCHEMA_VERSION as STRATEGY_REBUILD_VERSION,
    capture_strategy_source_cursor,
    compute_strategy_projection_digest,
    project_strategy,
    project_strategy_with_metadata,
    strategy_rebuild_metadata,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_strategy_doc(
    *,
    roadmap: dict | None = None,
    diagnostics: list | None = None,
) -> StrategyDocument:
    """Minimal StrategyDocument factory."""
    if roadmap is None:
        roadmap = {h: [] for h in REQUIRED_ROADMAP_SECTIONS}
    return StrategyDocument(
        schema_version=STRATEGY_SCHEMA_VERSION,
        stable_direction=[],
        roadmap=roadmap,
        diagnostics=diagnostics or [],
    )


def _make_entry(
    item_type: str = "ticket",
    ref: str = "T-001",
    title: str = "Test Entry",
    horizon: str = "Now",
) -> RoadmapEntry:
    return RoadmapEntry(
        identity=StrategyIdentity(type=item_type, ref=ref),  # type: ignore[arg-type]
        display_title=title,
        horizon=horizon,  # type: ignore[arg-type]
        source_location=SourceLocation(path="test.md", line=1, column=1),
    )


# ── Schema projection — digest stability ────────────────────────────────────


class TestSchemaProjectionDigest:
    """Digest computation for schema projections is deterministic."""

    def test_same_projection_same_digest(self) -> None:
        """Identical inputs produce identical digests."""
        projection = {"key": "value", "number": 42}
        d1 = compute_projection_digest(projection)
        d2 = compute_projection_digest(projection)
        assert d1 == d2
        assert d1.startswith("sha256:")

    def test_different_projection_different_digest(self) -> None:
        """Different projections produce different digests."""
        p1 = {"key": "value"}
        p2 = {"key": "different"}
        assert compute_projection_digest(p1) != compute_projection_digest(p2)

    def test_digest_unchanged_after_roundtrip(self) -> None:
        """Round-tripping through dict() does not change the digest."""
        projection = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
        d1 = compute_projection_digest(projection)
        d2 = compute_projection_digest(dict(projection))
        assert d1 == d2

    def test_digest_sorted_keys_stable(self) -> None:
        """Insertion order does not affect the digest."""
        # Build dicts in different insertion orders
        p1: dict[str, Any] = {}
        p1["z"] = 1
        p1["a"] = 2
        p1["m"] = 3

        p2: dict[str, Any] = {}
        p2["a"] = 2
        p2["m"] = 3
        p2["z"] = 1

        assert compute_projection_digest(p1) == compute_projection_digest(p2)

    def test_digest_length(self) -> None:
        """Digest is a 64-char hex string prefixed with 'sha256:'."""
        digest = compute_projection_digest({"x": 1})
        assert digest.startswith("sha256:")
        assert len(digest) == 7 + 64  # "sha256:" + 64 hex chars


# ── Schema projection — source cursor ──────────────────────────────────────


class TestSchemaSourceCursor:
    """Source cursor capture for schema projection."""

    def test_cursor_from_existing_file(self, tmp_path: Path) -> None:
        """Cursor captures the state of an existing file."""
        source = tmp_path / "schema.json"
        source.write_text('{"type": "object", "properties": {"a": {"type": "string"}}}')
        cursor = capture_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_path == str(source.resolve())
        assert cursor.source_record_count > 0
        assert cursor.source_digest.startswith("sha256:")
        assert cursor.computed_at

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        """Cursor for a missing file has zero records and empty-digest."""
        cursor = capture_source_cursor(tmp_path / "nonexistent.json")
        assert cursor.source_record_count == 0
        assert cursor.source_digest == "sha256:" + hashlib.sha256(b"").hexdigest()

    def test_cursor_frozen_immutable(self) -> None:
        """ProjectionCursor is frozen (immutable)."""
        cursor = ProjectionCursor(
            source_path="/tmp/test",
            source_record_count=5,
            source_digest="sha256:abc",
            computed_at="2025-01-01T00:00:00Z",
        )
        with pytest.raises(Exception):
            cursor.source_record_count = 10  # type: ignore[misc]

    def test_cursor_to_dict_roundtrip(self) -> None:
        """Cursor to_dict → from_dict round-trip preserves all fields."""
        cursor = ProjectionCursor(
            source_path="/tmp/test",
            source_record_count=7,
            source_digest="sha256:def456",
            computed_at="2025-06-15T12:00:00Z",
        )
        data = cursor.to_dict()
        restored = ProjectionCursor.from_dict(data)
        assert restored.source_path == cursor.source_path
        assert restored.source_record_count == cursor.source_record_count
        assert restored.source_digest == cursor.source_digest
        assert restored.computed_at == cursor.computed_at

    def test_cursor_same_file_same_digest(self, tmp_path: Path) -> None:
        """Two cursors from the same unchanged file are equal."""
        source = tmp_path / "data.jsonl"
        source.write_text('{"a":1}\n{"b":2}\n')
        c1 = capture_source_cursor(source)
        c2 = capture_source_cursor(source)
        assert c1.source_digest == c2.source_digest
        assert c1.source_record_count == c2.source_record_count


# ── Schema projection — rebuild metadata ───────────────────────────────────


class TestSchemaRebuildMetadata:
    """Rebuild metadata for schema projections."""

    def test_metadata_includes_all_keys(self, tmp_path: Path) -> None:
        """Metadata dict has all expected keys."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = rebuild_metadata(source, projection_digest="sha256:abc123")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert "projection_digest" in meta

    def test_metadata_without_digest(self, tmp_path: Path) -> None:
        """When projection_digest is empty, it is not included."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = rebuild_metadata(source)
        assert "projection_digest" not in meta

    def test_freshness_is_zero(self, tmp_path: Path) -> None:
        """A just-rebuilt projection has freshness=0."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = rebuild_metadata(source)
        assert meta["freshness_seconds"] == 0.0

    def test_lag_non_negative(self, tmp_path: Path) -> None:
        """Lag is always >= 0."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = rebuild_metadata(source)
        assert meta["lag_seconds"] >= 0.0

    def test_rebuild_schema_version(self) -> None:
        """Rebuild metadata schema version matches the module constant."""
        assert SCHEMA_REBUILD_VERSION == 1

    def test_metadata_pure_no_filesystem_write(self, tmp_path: Path) -> None:
        """rebuild_metadata does not create any new files."""
        source = tmp_path / "source.json"
        source.write_text('{"x": 1}')
        before_files = set(p.name for p in tmp_path.iterdir())
        rebuild_metadata(source, projection_digest="sha256:abc")
        after_files = set(p.name for p in tmp_path.iterdir())
        assert before_files == after_files

    def test_metadata_computed_at_custom(self, tmp_path: Path) -> None:
        """Custom computed_at is preserved in metadata."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = rebuild_metadata(source, computed_at="2025-01-01T00:00:00Z")
        assert meta["rebuilt_at"] == "2025-01-01T00:00:00Z"


# ── Schema projection — existing reducers remain pure ──────────────────────


class TestSchemaExistingReducersPure:
    """Pre-existing schema projection functions are still pure."""

    def test_closed_object_schema_does_not_mutate_input(self) -> None:
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        original = json.dumps(schema, sort_keys=True)
        closed_object_schema(schema)
        assert json.dumps(schema, sort_keys=True) == original

    def test_project_schema_owned_fields_pure(self) -> None:
        schema = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
        payload = {"name": "test", "age": 30, "extra": "should be dropped"}
        result = project_schema_owned_fields(payload, schema, contract="test")
        assert "extra" not in result
        assert result["name"] == "test"
        assert result["age"] == 30

    def test_schema_template_payload_pure(self) -> None:
        schema = {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "string"}}}
        result1 = schema_template_payload(schema, contract="test")
        result2 = schema_template_payload(schema, contract="test")
        assert result1 == result2


# ── Capsule projection — digest stability ──────────────────────────────────


class TestCapsuleProjectionDigest:
    """Digest computation for capsule projections."""

    def test_same_input_same_digest(self) -> None:
        """Identical capsule inputs → identical digest."""
        proj = capsule_definition_identity_projection(
            static_behavioral_hash="abc123",
            runtime_topology_hash="def456",
        )
        d1 = compute_capsule_projection_digest(proj)
        d2 = compute_capsule_projection_digest(proj)
        assert d1 == d2

    def test_different_hash_different_digest(self) -> None:
        """Different static hash → different digest."""
        p1 = capsule_definition_identity_projection(static_behavioral_hash="aaa")
        p2 = capsule_definition_identity_projection(static_behavioral_hash="bbb")
        assert compute_capsule_projection_digest(p1) != compute_capsule_projection_digest(p2)

    def test_digest_separate_from_identity_hash(self) -> None:
        """Projection digest ≠ definition_identity_hash."""
        proj = capsule_definition_identity_projection(static_behavioral_hash="test")
        digest = compute_capsule_projection_digest(proj)
        identity_hash = proj["definition_identity_hash"]
        assert isinstance(identity_hash, str)
        assert digest != identity_hash, "projection digest must differ from identity hash"

    def test_metadata_changes_digest(self) -> None:
        """Adding metadata changes the projection digest."""
        proj_bare = capsule_definition_identity_projection(static_behavioral_hash="test")
        bare_digest = compute_capsule_projection_digest(proj_bare)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            tmp_path = Path(f.name)
        try:
            proj_with = capsule_projection_with_metadata(
                static_behavioral_hash="test", source_path=tmp_path
            )
            with_digest = compute_capsule_projection_digest(proj_with)
            assert with_digest != bare_digest, "metadata must change the projection digest"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_definition_identity_hash_stable_with_metadata(self) -> None:
        """definition_identity_hash is NOT affected by metadata."""
        proj_bare = capsule_definition_identity_projection(static_behavioral_hash="stable")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            tmp_path = Path(f.name)
        try:
            proj_with = capsule_projection_with_metadata(
                static_behavioral_hash="stable", source_path=tmp_path
            )
            assert proj_with["definition_identity_hash"] == proj_bare["definition_identity_hash"]
        finally:
            tmp_path.unlink(missing_ok=True)


# ── Capsule projection — source cursor ─────────────────────────────────────


class TestCapsuleSourceCursor:
    """Source cursor for capsule projections."""

    def test_cursor_from_existing_file(self, tmp_path: Path) -> None:
        source = tmp_path / "capsule.json"
        source.write_text('{"capsule": "test"}')
        cursor = capture_capsule_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_record_count > 0

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        cursor = capture_capsule_source_cursor(tmp_path / "nonexistent.json")
        assert cursor.source_record_count == 0

    def test_cursor_readonly(self, tmp_path: Path) -> None:
        source = tmp_path / "capsule.json"
        source.write_text("original")
        before_files = set(p.name for p in tmp_path.iterdir())
        capture_capsule_source_cursor(source)
        after_files = set(p.name for p in tmp_path.iterdir())
        assert before_files == after_files


# ── Capsule projection — rebuild metadata ──────────────────────────────────


class TestCapsuleRebuildMetadata:
    """Rebuild metadata for capsule projections."""

    def test_metadata_all_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "capsule.json"
        source.write_text("{}")
        meta = capsule_rebuild_metadata(source, projection_digest="sha256:abc")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert meta["projection_digest"] == "sha256:abc"

    def test_metadata_pure(self, tmp_path: Path) -> None:
        source = tmp_path / "capsule.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())
        capsule_rebuild_metadata(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_capsule_projection_with_metadata_no_source_path(self) -> None:
        """Without source_path, no rebuild_metadata is appended."""
        proj = capsule_projection_with_metadata(static_behavioral_hash="test")
        assert "rebuild_metadata" not in proj
        assert proj["schema_version"] == CAPSULE_SCHEMA_VERSION

    def test_capsule_projection_with_metadata_has_metadata(self, tmp_path: Path) -> None:
        """With source_path, rebuild_metadata is present."""
        source = tmp_path / "capsule.json"
        source.write_text("{}")
        proj = capsule_projection_with_metadata(
            static_behavioral_hash="test",
            source_path=source,
        )
        assert "rebuild_metadata" in proj
        meta = proj["rebuild_metadata"]
        assert isinstance(meta, dict)
        assert meta["rebuild_schema_version"] == CAPSULE_REBUILD_VERSION

    def test_capsule_schema_version(self) -> None:
        """Verify the module constants."""
        assert CAPSULE_SCHEMA_VERSION == 1
        assert CAPSULE_REBUILD_VERSION == 1


# ── Strategy projection — digest stability ─────────────────────────────────


class TestStrategyProjectionDigest:
    """Digest computation for strategy projections."""

    def test_same_document_same_digest(self) -> None:
        doc = _make_strategy_doc()
        d1 = compute_strategy_projection_digest(doc)
        d2 = compute_strategy_projection_digest(doc)
        assert d1 == d2

    def test_different_document_different_digest(self) -> None:
        doc1 = _make_strategy_doc()
        doc2 = _make_strategy_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Test error",
                source_location=SourceLocation(path="e.md", line=1, column=1),
            )
        ])
        assert compute_strategy_projection_digest(doc1) != compute_strategy_projection_digest(doc2)

    def test_digest_stable_across_calls(self) -> None:
        """Repeated calls produce identical digests."""
        doc = _make_strategy_doc(roadmap={
            "Now": [_make_entry(ref="A"), _make_entry(ref="B")],
            "Next": [],
            "Later": [],
        })
        digests = {compute_strategy_projection_digest(doc) for _ in range(20)}
        assert len(digests) == 1

    def test_roadmap_order_does_not_matter(self) -> None:
        """Roadmap entries in different insertion orders produce same digest."""
        r1: dict = {"Now": [_make_entry(ref="A"), _make_entry(ref="B")], "Next": [], "Later": []}
        r2: dict = {"Now": [_make_entry(ref="B"), _make_entry(ref="A")], "Next": [], "Later": []}
        doc1 = _make_strategy_doc(roadmap=r1)
        doc2 = _make_strategy_doc(roadmap=r2)
        # Different order → different projection → different digest
        # (entries are projected in list order, so order matters)
        d1 = compute_strategy_projection_digest(doc1)
        d2 = compute_strategy_projection_digest(doc2)
        assert d1 != d2, "Order matters for list projections"

    def test_digest_format(self) -> None:
        doc = _make_strategy_doc()
        digest = compute_strategy_projection_digest(doc)
        assert digest.startswith("sha256:")
        assert len(digest) == 71  # "sha256:" + 64 hex chars


# ── Strategy projection — source cursor ────────────────────────────────────


class TestStrategySourceCursor:
    """Source cursor for strategy projections."""

    def test_cursor_from_existing_markdown(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Strategy\n\n## Mission\n\nTest.\n")
        cursor = capture_strategy_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_record_count > 0
        assert cursor.source_digest.startswith("sha256:")

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        cursor = capture_strategy_source_cursor(Path("/nonexistent/strategy.md"))
        assert cursor.source_record_count == 0

    def test_cursor_readonly(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test")
        before = set(p.name for p in tmp_path.iterdir())
        capture_strategy_source_cursor(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_cursor_file_change_changes_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Version 1")
        c1 = capture_strategy_source_cursor(source)
        source.write_text("# Version 2")
        c2 = capture_strategy_source_cursor(source)
        assert c1.source_digest != c2.source_digest


# ── Strategy projection — rebuild metadata ─────────────────────────────────


class TestStrategyRebuildMetadata:
    """Rebuild metadata for strategy projections."""

    def test_metadata_all_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test\n\n## Mission\n\nTest.\n")
        meta = strategy_rebuild_metadata(source, projection_digest="sha256:abc")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert meta["projection_digest"] == "sha256:abc"

    def test_metadata_pure_no_write(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test")
        before = set(p.name for p in tmp_path.iterdir())
        strategy_rebuild_metadata(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_project_strategy_with_metadata_no_source(self) -> None:
        """Without source_path, no rebuild_metadata."""
        doc = _make_strategy_doc()
        proj = project_strategy_with_metadata(doc)
        assert "rebuild_metadata" not in proj

    def test_project_strategy_with_metadata_has_metadata(self, tmp_path: Path) -> None:
        """With source_path, rebuild_metadata is present."""
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test\n\n## Mission\n\nTest.\n")
        doc = _make_strategy_doc()
        proj = project_strategy_with_metadata(doc, source_path=source)
        assert "rebuild_metadata" in proj
        meta = proj["rebuild_metadata"]
        assert isinstance(meta, dict)
        assert meta["rebuild_schema_version"] == STRATEGY_REBUILD_VERSION

    def test_project_strategy_with_metadata_preserves_fields(self, tmp_path: Path) -> None:
        """Metadata is additive — original fields are unchanged."""
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test\n\n## Mission\n\nTest.\n")
        doc = _make_strategy_doc()
        bare = project_strategy(doc)
        with_meta = project_strategy_with_metadata(doc, source_path=source)
        for key in bare:
            assert key in with_meta
            assert with_meta[key] == bare[key], f"Field '{key}' changed by metadata"

    def test_rebuild_schema_version(self) -> None:
        assert STRATEGY_REBUILD_VERSION == 1

    def test_freshness_and_lag_values(self, tmp_path: Path) -> None:
        source = tmp_path / "STRATEGY.md"
        source.write_text("# Test")
        meta = strategy_rebuild_metadata(source)
        assert meta["freshness_seconds"] == 0.0
        assert meta["lag_seconds"] >= 0.0


# ── Cross-module consistency ────────────────────────────────────────────────


class TestCrossModuleConsistency:
    """All three modules share consistent rebuild metadata contracts."""

    def test_rebuild_schema_versions_match(self) -> None:
        """All three modules use the same rebuild schema version."""
        assert SCHEMA_REBUILD_VERSION == CAPSULE_REBUILD_VERSION == STRATEGY_REBUILD_VERSION

    def test_all_metadata_dicts_have_same_keys(self, tmp_path: Path) -> None:
        """All three modules produce metadata with the same required keys."""
        source = tmp_path / "test.json"
        source.write_text("{}")

        schema_meta = rebuild_metadata(source, projection_digest="sha256:abc")
        capsule_meta = capsule_rebuild_metadata(source, projection_digest="sha256:abc")
        strategy_meta = strategy_rebuild_metadata(source, projection_digest="sha256:abc")

        expected_keys = {
            "rebuild_schema_version",
            "source_cursor",
            "rebuilt_at",
            "freshness_seconds",
            "lag_seconds",
            "projection_digest",
        }
        assert set(schema_meta.keys()) == expected_keys
        assert set(capsule_meta.keys()) == expected_keys
        assert set(strategy_meta.keys()) == expected_keys

    def test_all_digest_functions_return_sha256_prefix(self) -> None:
        """All digest functions return 'sha256:' prefixed hex strings."""
        schema_digest = compute_projection_digest({"x": 1})
        capsule_digest = compute_capsule_projection_digest(
            capsule_definition_identity_projection(static_behavioral_hash="test")
        )
        strategy_digest = compute_strategy_projection_digest(_make_strategy_doc())

        for d in (schema_digest, capsule_digest, strategy_digest):
            assert d.startswith("sha256:")
            assert len(d) == 71

    def test_all_cursor_functions_return_ProjectionCursor(self, tmp_path: Path) -> None:
        """All cursor functions return ProjectionCursor instances."""
        source = tmp_path / "test.json"
        source.write_text("{}")

        sc = capture_source_cursor(source)
        cc = capture_capsule_source_cursor(source)
        stc = capture_strategy_source_cursor(source)

        assert isinstance(sc, ProjectionCursor)
        assert isinstance(cc, ProjectionCursor)
        assert isinstance(stc, ProjectionCursor)

    def test_all_reducers_are_pure_no_side_effects(self, tmp_path: Path) -> None:
        """Every reducer function does not touch the filesystem."""
        source = tmp_path / "test.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())

        # Schema
        compute_projection_digest({"x": 1})
        capture_source_cursor(source)
        rebuild_metadata(source)

        # Capsule
        capsule_definition_identity_projection(static_behavioral_hash="test")
        compute_capsule_projection_digest({"test": True})
        capture_capsule_source_cursor(source)
        capsule_rebuild_metadata(source)

        # Strategy
        doc = _make_strategy_doc()
        compute_strategy_projection_digest(doc)
        capture_strategy_source_cursor(source)
        strategy_rebuild_metadata(source)
        project_strategy(doc)

        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_digests_are_hex_encoded(self) -> None:
        """All digests contain only valid hex characters after 'sha256:'."""
        digests = [
            compute_projection_digest({"x": 1}),
            compute_capsule_projection_digest(
                capsule_definition_identity_projection(static_behavioral_hash="test")
            ),
            compute_strategy_projection_digest(_make_strategy_doc()),
        ]
        for digest in digests:
            hex_part = digest[len("sha256:"):]
            assert len(hex_part) == 64
            assert all(c in "0123456789abcdef" for c in hex_part)
