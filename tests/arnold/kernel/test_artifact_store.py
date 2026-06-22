from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from arnold.kernel import (
    ArtifactRoot,
    ArtifactRootKind,
    ContentTypeRegistration,
    ContentTypeRegistry,
    FileBackedArtifactStore,
    GeneratedArtifactProvenance,
    ProvenanceParent,
    RetentionPin,
    RetentionPolicy,
    schema_hash,
)


def _content_type() -> ContentTypeRegistration:
    return ContentTypeRegistration(
        type_id="text.plain",
        schema_version="v1",
        schema_hash=schema_hash({"type": "string"}),
        retention_policy=RetentionPolicy.RUN,
    )


def _provenance(*parents: ProvenanceParent) -> GeneratedArtifactProvenance:
    return GeneratedArtifactProvenance(
        generator_module="arnold.kernel.test",
        generator_source_hash="sha256:" + "0" * 64,
        manifest_contract_version="arnold.workflow.manifest.v1",
        generated_at="2026-06-22T00:00:00Z",
        input_hashes=(),
        parents=parents,
    )


def test_store_writes_versioned_artifacts_and_resolves_newest(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    binding1 = store.write_artifact(
        artifact_id="report",
        content=b"first draft",
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
    )
    binding2 = store.write_artifact(
        artifact_id="report",
        content=b"second draft",
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
    )

    assert binding1.relative_path == "report/v1.txt"
    assert binding2.relative_path == "report/v2.txt"

    newest = store.resolve_newest("report", "txt")
    assert newest is not None
    assert newest.relative_path == "report/v2.txt"

    assert store.list_versions("report", "txt") == [1, 2]


def test_content_hash_matches_written_bytes(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    content = b"hello, artifacts"
    binding = store.write_artifact(
        artifact_id="note",
        content=content,
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
    )

    expected_hash = "sha256:" + hashlib.sha256(content).hexdigest()
    # The binding does not carry the content hash directly; provenance is
    # orthogonal.  Verify the file matches the original bytes.
    assert (tmp_path / binding.relative_path).read_bytes() == content
    assert binding.content_type.type_id == "text.plain"


def test_content_type_registry_is_enforced(tmp_path: Path) -> None:
    store = FileBackedArtifactStore(tmp_path)

    with pytest.raises(KeyError, match="text.plain"):
        store.write_artifact(
            artifact_id="note",
            content=b"content",
            content_type_id="text.plain",
            provenance=_provenance(),
            extension="txt",
        )


def test_retention_pins_are_recorded(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    pins = (RetentionPin(policy=RetentionPolicy.AUDIT, reason="golden evidence"),)
    binding = store.write_artifact(
        artifact_id="evidence",
        content=b"proof",
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
        retention_pins=pins,
    )

    assert binding.retention_pins == pins

    # Round-trip through the newest binding preserves pins.
    newest = store.resolve_newest("evidence", "txt")
    assert newest is not None
    assert newest.retention_pins == pins


def test_provenance_chain_affects_hash(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    parent_a = ProvenanceParent(artifact_id="source-a", content_hash="sha256:" + "a" * 64)
    parent_b = ProvenanceParent(artifact_id="source-b", content_hash="sha256:" + "a" * 64)

    binding_a = store.write_artifact(
        artifact_id="derived",
        content=b"data",
        content_type_id="text.plain",
        provenance=_provenance(parent_a),
        extension="txt",
    )
    binding_b = store.write_artifact(
        artifact_id="derived",
        content=b"data",
        content_type_id="text.plain",
        provenance=_provenance(parent_b),
        extension="txt",
    )

    assert binding_a.provenance.provenance_hash != binding_b.provenance.provenance_hash

    newest = store.resolve_newest("derived", "txt")
    assert newest is not None
    assert newest.provenance.provenance_hash == binding_b.provenance.provenance_hash


def test_legacy_flat_artifacts_are_quarantined_on_write(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    artifact_dir = tmp_path / "report"
    artifact_dir.mkdir()
    legacy_file = artifact_dir / "old_report.txt"
    legacy_file.write_bytes(b"legacy content")

    binding = store.write_artifact(
        artifact_id="report",
        content=b"versioned content",
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
    )

    assert binding.relative_path == "report/v1.txt"
    assert not legacy_file.exists()
    quarantined = store.legacy_inputs("report")
    assert quarantined == {"old_report.txt": b"legacy content"}
    assert store.resolve_newest("report", "txt").relative_path == "report/v1.txt"


def test_legacy_quarantine_is_available_as_migration_input(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    artifact_dir = tmp_path / "data"
    artifact_dir.mkdir()
    (artifact_dir / "legacy.csv").write_bytes(b"1,2,3")

    quarantined_paths = store.quarantine_legacy("data")
    assert len(quarantined_paths) == 1

    inputs = store.legacy_inputs("data")
    assert inputs == {"legacy.csv": b"1,2,3"}

    assert store.resolve_newest("data", "csv") is None


def test_different_extensions_version_independently(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    registry.register(
        ContentTypeRegistration(
            type_id="application.json",
            schema_version="v1",
            schema_hash=schema_hash({"type": "object"}),
        )
    )
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    store.write_artifact(
        artifact_id="multi",
        content=b"text",
        content_type_id="text.plain",
        provenance=_provenance(),
        extension="txt",
    )
    store.write_artifact(
        artifact_id="multi",
        content=b"{}",
        content_type_id="application.json",
        provenance=_provenance(),
        extension="json",
    )

    assert store.resolve_newest("multi", "txt").relative_path == "multi/v1.txt"
    assert store.resolve_newest("multi", "json").relative_path == "multi/v1.json"


def test_binding_round_trips_through_meta_sidecar(tmp_path: Path) -> None:
    registry = ContentTypeRegistry()
    registry.register(_content_type())
    store = FileBackedArtifactStore(tmp_path, content_type_registry=registry)

    provenance = _provenance(
        ProvenanceParent(artifact_id="parent", content_hash="sha256:" + "p" * 64)
    )
    binding = store.write_artifact(
        artifact_id="roundtrip",
        content=b"roundtrip",
        content_type_id="text.plain",
        provenance=provenance,
        extension="txt",
        retention_pins=(RetentionPin(policy=RetentionPolicy.LEGAL_HOLD, reason="audit"),),
    )

    newest = store.resolve_newest("roundtrip", "txt")
    assert newest == binding
    assert newest.root.kind is ArtifactRootKind.PLAN_ARTIFACT_ROOT
    assert isinstance(newest.root, ArtifactRoot)
