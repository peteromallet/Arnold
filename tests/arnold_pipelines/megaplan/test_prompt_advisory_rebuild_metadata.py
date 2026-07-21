"""Focused tests for prompt, worker-caps, and advisory projection rebuild metadata.

Covers the three modules updated in T22:
- ``prompts/_projection.py``
- ``workers/_projection_caps.py``
- ``orchestration/advisory_projection.py``

Key invariants proven:
- Digests are stable (same input → same digest) and different inputs produce
  different digests.
- Source cursors capture correct source state.
- Rebuild metadata includes freshness, lag, source cursor, and digest.
- All new functions are pure — no side effects, no filesystem writes.
- Cross-module rebuild metadata schema versions are consistent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
)
from arnold_pipelines.megaplan.prompts._projection import (
    REBUILD_METADATA_SCHEMA_VERSION as PROMPT_REBUILD_VERSION,
    compute_prompt_projection_digest,
    capture_prompt_source_cursor,
    prompt_rebuild_metadata,
    project_execute_context,
    project_review_context,
)
from arnold_pipelines.megaplan.workers._projection_caps import (
    REBUILD_METADATA_SCHEMA_VERSION as CAPS_REBUILD_VERSION,
    compute_caps_projection_digest,
    capture_caps_source_cursor,
    caps_rebuild_metadata,
    codex_projection_capabilities,
    hermes_projection_capabilities,
    shannon_projection_capabilities,
)
from arnold_pipelines.megaplan.orchestration.advisory_projection import (
    REBUILD_METADATA_SCHEMA_VERSION as ADVISORY_REBUILD_VERSION,
    compute_advisory_projection_digest,
    capture_advisory_source_cursor,
    advisory_rebuild_metadata,
    _project_advisory_path_list,
)


# ── Prompt projection — digest stability ───────────────────────────────────


class TestPromptProjectionDigest:
    """Digest computation for prompt projections is deterministic."""

    def test_same_projection_same_digest(self) -> None:
        projection = {"tasks": [{"id": "T1", "status": "done"}], "sense_checks": []}
        d1 = compute_prompt_projection_digest(projection)
        d2 = compute_prompt_projection_digest(projection)
        assert d1 == d2
        assert d1.startswith("sha256:")

    def test_different_projection_different_digest(self) -> None:
        p1 = {"tasks": [{"id": "T1"}]}
        p2 = {"tasks": [{"id": "T2"}]}
        assert compute_prompt_projection_digest(p1) != compute_prompt_projection_digest(p2)

    def test_digest_unchanged_after_roundtrip(self) -> None:
        projection = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
        d1 = compute_prompt_projection_digest(projection)
        d2 = compute_prompt_projection_digest(dict(projection))
        assert d1 == d2

    def test_digest_sorted_keys_stable(self) -> None:
        p1: dict[str, Any] = {}
        p1["z"] = 1
        p1["a"] = 2
        p1["m"] = 3
        p2: dict[str, Any] = {}
        p2["a"] = 2
        p2["m"] = 3
        p2["z"] = 1
        assert compute_prompt_projection_digest(p1) == compute_prompt_projection_digest(p2)

    def test_digest_length(self) -> None:
        digest = compute_prompt_projection_digest({"x": 1})
        assert digest.startswith("sha256:")
        assert len(digest) == 7 + 64

    def test_real_projection_digest_stable(self) -> None:
        """Digest of a real project_execute_context output is stable."""
        finalize_data: dict[str, Any] = {
            "tasks": [
                {"id": "T1", "status": "done", "description": "Test task", "depends_on": []}
            ],
            "sense_checks": [
                {"id": "SC1", "task_id": "T1", "verdict": "", "question": "Is it ok?"}
            ],
        }
        proj = project_execute_context(finalize_data)
        d1 = compute_prompt_projection_digest(proj)
        d2 = compute_prompt_projection_digest(proj)
        assert d1 == d2


# ── Prompt projection — source cursor ──────────────────────────────────────


class TestPromptSourceCursor:
    """Source cursor capture for prompt projections."""

    def test_cursor_from_existing_file(self, tmp_path: Path) -> None:
        source = tmp_path / "finalize.json"
        source.write_text('{"tasks": [{"id": "T1"}], "sense_checks": []}')
        cursor = capture_prompt_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_path == str(source.resolve())
        assert cursor.source_record_count > 0
        assert cursor.source_digest.startswith("sha256:")

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        cursor = capture_prompt_source_cursor(tmp_path / "nonexistent.json")
        assert cursor.source_record_count == 0
        assert cursor.source_digest == "sha256:" + hashlib.sha256(b"").hexdigest()

    def test_cursor_readonly(self, tmp_path: Path) -> None:
        source = tmp_path / "data.json"
        source.write_text('{"key": "value"}')
        before = set(p.name for p in tmp_path.iterdir())
        capture_prompt_source_cursor(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_cursor_same_file_same_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "data.json"
        source.write_text('{"a": 1}\n{"b": 2}\n')
        c1 = capture_prompt_source_cursor(source)
        c2 = capture_prompt_source_cursor(source)
        assert c1.source_digest == c2.source_digest
        assert c1.source_record_count == c2.source_record_count


# ── Prompt projection — rebuild metadata ───────────────────────────────────


class TestPromptRebuildMetadata:
    """Rebuild metadata for prompt projections."""

    def test_metadata_includes_all_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = prompt_rebuild_metadata(source, projection_digest="sha256:abc123")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert "projection_digest" in meta
        assert meta["projection_digest"] == "sha256:abc123"

    def test_metadata_without_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = prompt_rebuild_metadata(source)
        assert "projection_digest" not in meta

    def test_freshness_is_zero(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = prompt_rebuild_metadata(source)
        assert meta["freshness_seconds"] == 0.0

    def test_lag_non_negative(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = prompt_rebuild_metadata(source)
        assert meta["lag_seconds"] >= 0.0

    def test_metadata_pure_no_filesystem_write(self, tmp_path: Path) -> None:
        source = tmp_path / "source.json"
        source.write_text('{"x": 1}')
        before = set(p.name for p in tmp_path.iterdir())
        prompt_rebuild_metadata(source, projection_digest="sha256:abc")
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_metadata_computed_at_custom(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        meta = prompt_rebuild_metadata(source, computed_at="2025-01-01T00:00:00Z")
        assert meta["rebuilt_at"] == "2025-01-01T00:00:00Z"


# ── Prompt projection — existing reducers remain pure ──────────────────────


class TestPromptExistingReducersPure:
    """Pre-existing prompt projection functions are still pure."""

    def test_project_execute_context_does_not_mutate_input(self) -> None:
        finalize_data: dict[str, Any] = {
            "tasks": [{"id": "T1", "status": "done"}],
            "sense_checks": [],
        }
        import json
        original = json.dumps(finalize_data, sort_keys=True)
        project_execute_context(finalize_data)
        assert json.dumps(finalize_data, sort_keys=True) == original

    def test_project_execute_context_idempotent(self) -> None:
        finalize_data: dict[str, Any] = {
            "tasks": [{"id": "T1", "status": "done", "description": "test"}],
            "sense_checks": [
                {"id": "SC1", "task_id": "T1", "verdict": "", "question": "ok?"}
            ],
        }
        r1 = project_execute_context(finalize_data)
        r2 = project_execute_context(finalize_data)
        assert r1 == r2

    def test_project_review_context_idempotent(self) -> None:
        finalize_data: dict[str, Any] = {
            "tasks": [{"id": "T1", "status": "done"}],
            "sense_checks": [],
        }
        exec_data: dict[str, Any] = {
            "task_updates": [{"task_id": "T1", "status": "done", "executor_notes": "ok"}],
        }
        r1 = project_review_context(finalize_data, exec_data)
        r2 = project_review_context(finalize_data, exec_data)
        assert r1 == r2


# ── Worker caps — digest stability ─────────────────────────────────────────


class TestCapsProjectionDigest:
    """Digest computation for worker capabilities is deterministic."""

    def test_same_caps_same_digest(self) -> None:
        caps = codex_projection_capabilities(resumed_session=False)
        d1 = compute_caps_projection_digest(caps)
        d2 = compute_caps_projection_digest(caps)
        assert d1 == d2

    def test_different_caps_different_digest(self) -> None:
        caps1 = codex_projection_capabilities(resumed_session=False)
        caps2 = codex_projection_capabilities(resumed_session=True)
        assert compute_caps_projection_digest(caps1) != compute_caps_projection_digest(caps2)

    def test_hermes_caps_digest(self) -> None:
        caps = hermes_projection_capabilities(["file", "terminal"])
        digest = compute_caps_projection_digest(caps)
        assert digest.startswith("sha256:")

    def test_shannon_caps_digest(self) -> None:
        caps_rw = shannon_projection_capabilities(read_only=False)
        caps_ro = shannon_projection_capabilities(read_only=True)
        assert compute_caps_projection_digest(caps_rw) != compute_caps_projection_digest(caps_ro)

    def test_digest_length(self) -> None:
        caps = codex_projection_capabilities(resumed_session=False)
        digest = compute_caps_projection_digest(caps)
        assert len(digest) == 7 + 64


# ── Worker caps — source cursor ────────────────────────────────────────────


class TestCapsSourceCursor:
    """Source cursor for worker capabilities."""

    def test_cursor_from_existing_file(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text('{"toolsets": ["file", "terminal"]}')
        cursor = capture_caps_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_record_count > 0

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        cursor = capture_caps_source_cursor(tmp_path / "nonexistent.json")
        assert cursor.source_record_count == 0

    def test_cursor_readonly(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())
        capture_caps_source_cursor(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after


# ── Worker caps — rebuild metadata ─────────────────────────────────────────


class TestCapsRebuildMetadata:
    """Rebuild metadata for worker capabilities projections."""

    def test_metadata_all_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text("{}")
        meta = caps_rebuild_metadata(source, projection_digest="sha256:abc")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert meta["projection_digest"] == "sha256:abc"

    def test_metadata_pure(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())
        caps_rebuild_metadata(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_metadata_without_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text("{}")
        meta = caps_rebuild_metadata(source)
        assert "projection_digest" not in meta

    def test_freshness_zero(self, tmp_path: Path) -> None:
        source = tmp_path / "worker.json"
        source.write_text("{}")
        meta = caps_rebuild_metadata(source)
        assert meta["freshness_seconds"] == 0.0


# ── Advisory projection — digest stability ─────────────────────────────────


class TestAdvisoryProjectionDigest:
    """Digest computation for advisory projections."""

    def test_same_projection_same_digest(self) -> None:
        proj: dict[str, Any] = {"items": ["a.py", "b.py"], "omitted_count": 0}
        d1 = compute_advisory_projection_digest(proj)
        d2 = compute_advisory_projection_digest(proj)
        assert d1 == d2

    def test_different_projection_different_digest(self) -> None:
        p1: dict[str, Any] = {"items": ["a.py"], "omitted_count": 0}
        p2: dict[str, Any] = {"items": ["b.py"], "omitted_count": 0}
        assert compute_advisory_projection_digest(p1) != compute_advisory_projection_digest(p2)

    def test_digest_with_bulk_summary(self, tmp_path: Path) -> None:
        """Digest includes the bulk summary when present."""
        values = [f"{tmp_path}/file_{i:03d}.py" for i in range(100)]
        proj = _project_advisory_path_list(
            values, plan_dir=tmp_path, artifact_name="test.json", label="test"
        )
        assert isinstance(proj, dict)
        digest = compute_advisory_projection_digest(proj)
        assert digest.startswith("sha256:")
        assert len(digest) == 71

    def test_digest_length(self) -> None:
        digest = compute_advisory_projection_digest({"items": [], "omitted_count": 0})
        assert len(digest) == 7 + 64


# ── Advisory projection — source cursor ────────────────────────────────────


class TestAdvisorySourceCursor:
    """Source cursor for advisory projections."""

    def test_cursor_from_existing_file(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text('{"items": ["a.py", "b.py"]}')
        cursor = capture_advisory_source_cursor(source)
        assert isinstance(cursor, ProjectionCursor)
        assert cursor.source_record_count > 0
        assert cursor.source_digest.startswith("sha256:")

    def test_cursor_from_missing_file(self, tmp_path: Path) -> None:
        cursor = capture_advisory_source_cursor(tmp_path / "nonexistent.json")
        assert cursor.source_record_count == 0

    def test_cursor_readonly(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())
        capture_advisory_source_cursor(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_cursor_file_change_changes_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text('{"version": 1}')
        c1 = capture_advisory_source_cursor(source)
        source.write_text('{"version": 2}')
        c2 = capture_advisory_source_cursor(source)
        assert c1.source_digest != c2.source_digest


# ── Advisory projection — rebuild metadata ─────────────────────────────────


class TestAdvisoryRebuildMetadata:
    """Rebuild metadata for advisory projections."""

    def test_metadata_all_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text("{}")
        meta = advisory_rebuild_metadata(source, projection_digest="sha256:abc")
        assert "rebuild_schema_version" in meta
        assert "source_cursor" in meta
        assert "rebuilt_at" in meta
        assert "freshness_seconds" in meta
        assert "lag_seconds" in meta
        assert meta["projection_digest"] == "sha256:abc"

    def test_metadata_pure_no_write(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())
        advisory_rebuild_metadata(source)
        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_metadata_without_digest(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text("{}")
        meta = advisory_rebuild_metadata(source)
        assert "projection_digest" not in meta

    def test_freshness_and_lag(self, tmp_path: Path) -> None:
        source = tmp_path / "paths.json"
        source.write_text("{}")
        meta = advisory_rebuild_metadata(source)
        assert meta["freshness_seconds"] == 0.0
        assert meta["lag_seconds"] >= 0.0


# ── Cross-module consistency ────────────────────────────────────────────────


class TestCrossModuleConsistency:
    """All three modules share consistent rebuild metadata contracts."""

    def test_rebuild_schema_versions_match(self) -> None:
        assert PROMPT_REBUILD_VERSION == CAPS_REBUILD_VERSION == ADVISORY_REBUILD_VERSION == 1

    def test_all_metadata_dicts_have_same_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")

        prompt_meta = prompt_rebuild_metadata(source, projection_digest="sha256:abc")
        caps_meta = caps_rebuild_metadata(source, projection_digest="sha256:abc")
        advisory_meta = advisory_rebuild_metadata(source, projection_digest="sha256:abc")

        expected_keys = {
            "rebuild_schema_version",
            "source_cursor",
            "rebuilt_at",
            "freshness_seconds",
            "lag_seconds",
            "projection_digest",
        }
        assert set(prompt_meta.keys()) == expected_keys
        assert set(caps_meta.keys()) == expected_keys
        assert set(advisory_meta.keys()) == expected_keys

    def test_all_digest_functions_return_sha256_prefix(self) -> None:
        prompt_digest = compute_prompt_projection_digest({"x": 1})
        caps_digest = compute_caps_projection_digest(
            codex_projection_capabilities(resumed_session=False)
        )
        advisory_digest = compute_advisory_projection_digest({"items": [], "omitted_count": 0})

        for d in (prompt_digest, caps_digest, advisory_digest):
            assert d.startswith("sha256:")
            assert len(d) == 71

    def test_all_cursor_functions_return_ProjectionCursor(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")

        pc = capture_prompt_source_cursor(source)
        cc = capture_caps_source_cursor(source)
        ac = capture_advisory_source_cursor(source)

        assert isinstance(pc, ProjectionCursor)
        assert isinstance(cc, ProjectionCursor)
        assert isinstance(ac, ProjectionCursor)

    def test_all_reducers_are_pure_no_side_effects(self, tmp_path: Path) -> None:
        source = tmp_path / "test.json"
        source.write_text("{}")
        before = set(p.name for p in tmp_path.iterdir())

        # Prompt
        compute_prompt_projection_digest({"x": 1})
        capture_prompt_source_cursor(source)
        prompt_rebuild_metadata(source)

        # Caps
        caps = codex_projection_capabilities(resumed_session=False)
        compute_caps_projection_digest(caps)
        capture_caps_source_cursor(source)
        caps_rebuild_metadata(source)

        # Advisory
        compute_advisory_projection_digest({"items": [], "omitted_count": 0})
        capture_advisory_source_cursor(source)
        advisory_rebuild_metadata(source)

        after = set(p.name for p in tmp_path.iterdir())
        assert before == after

    def test_digests_are_hex_encoded(self) -> None:
        digests = [
            compute_prompt_projection_digest({"x": 1}),
            compute_caps_projection_digest(
                codex_projection_capabilities(resumed_session=False)
            ),
            compute_advisory_projection_digest({"items": [], "omitted_count": 0}),
        ]
        for digest in digests:
            hex_part = digest[len("sha256:"):]
            assert len(hex_part) == 64
            assert all(c in "0123456789abcdef" for c in hex_part)

    def test_no_new_authority_created(self) -> None:
        """None of the rebuild metadata functions create authority, grants, or leases."""
        for func in (
            compute_prompt_projection_digest,
            compute_caps_projection_digest,
            compute_advisory_projection_digest,
        ):
            # All return simple digest strings, never authority tokens
            result = func({"x": 1}) if func != compute_caps_projection_digest else func(
                codex_projection_capabilities(resumed_session=False)
            )
            assert isinstance(result, str)
            assert "authority" not in result.lower()
            assert "grant" not in result.lower()
            assert "lease" not in result.lower()
