from __future__ import annotations

import pytest

from arnold.kernel import (
    ArtifactBinding,
    ArtifactRoot,
    ArtifactRootKind,
    ContentTypeRegistration,
    ContentTypeRegistry,
    FileBackedArtifactStore,
    GeneratedArtifactProvenance,
    ProvenanceParent,
    RetentionPin,
    RetentionPolicy,
    latest_version,
    next_version_path,
    schema_hash,
    validate_safe_relative_subpath,
    versioned_artifact_name,
)


def test_versioned_artifact_naming_and_next_path() -> None:
    existing = ("artifacts/v1.md", "artifacts/v2.md", "artifacts/report.v9.md")

    assert versioned_artifact_name("", 3, ".md") == "v3.md"
    assert latest_version(existing, "md") == 2
    assert next_version_path("artifacts", "", "md", existing) == "artifacts/v3.md"
    with pytest.raises(ValueError):
        versioned_artifact_name("report", 1, "md")


def test_latest_version_is_extension_specific_and_next_starts_at_v1() -> None:
    existing = ("artifacts/v1.md", "artifacts/v4.json", "artifacts/v2.md.tmp")

    assert latest_version(existing, "md") == 1
    assert latest_version(existing, ".json") == 4
    assert latest_version((), "md") is None
    assert next_version_path("artifacts", "", ".json", ()) == "artifacts/v1.json"


def test_content_type_registry_hashes_schema_and_rejects_conflicts() -> None:
    schema = {"required": ["body"], "type": "object"}
    registration = ContentTypeRegistration(
        type_id="markdown.report",
        schema_version="v1",
        schema_hash=schema_hash(schema),
        retention_policy=RetentionPolicy.AUDIT,
    )
    registry = ContentTypeRegistry()

    assert registry.register(registration) == registration
    assert registry.require("markdown.report") == registration
    assert (
        schema_hash({"type": "object", "required": ["body"]})
        == registration.schema_hash
    )

    with pytest.raises(ValueError):
        registry.register(
            ContentTypeRegistration(
                type_id="markdown.report",
                schema_version="v2",
                schema_hash=schema_hash({"type": "string"}),
            )
        )


def test_artifact_binding_carries_logical_root_and_provenance() -> None:
    content_type = ContentTypeRegistration(
        type_id="markdown.report",
        schema_version="v1",
        schema_hash="sha256:" + "2" * 64,
        retention_policy=RetentionPolicy.AUDIT,
    )
    provenance = GeneratedArtifactProvenance(
        generator_module="arnold.docs.generator",
        generator_source_hash="sha256:" + "3" * 64,
        manifest_contract_version="arnold.workflow.manifest.v1",
        generated_at="2026-06-22T00:00:00Z",
        input_hashes=("sha256:" + "4" * 64,),
        parents=(
            ProvenanceParent(
                artifact_id="source-report",
                content_hash="sha256:" + "5" * 64,
            ),
        ),
    )
    binding = ArtifactBinding(
        artifact_id="report",
        root=ArtifactRoot(
            "repo-megaplan",
            ".megaplan/reports",
            kind=ArtifactRootKind.REPO_ARTIFACT_ROOT,
        ),
        relative_path="v1.md",
        content_type=content_type,
        provenance=provenance,
        retention_pins=(
            RetentionPin(policy=RetentionPolicy.AUDIT, reason="golden evidence"),
        ),
    )

    assert binding.root.root_id == "repo-megaplan"
    assert binding.root.kind == ArtifactRootKind.REPO_ARTIFACT_ROOT
    assert binding.relative_path == "v1.md"
    assert binding.retention_pins[0].policy == RetentionPolicy.AUDIT
    assert provenance.provenance_hash.startswith("sha256:")
    assert binding.root.to_dict() == {
        "kind": "repo_artifact_root",
        "path": ".megaplan/reports",
        "root_id": "repo-megaplan",
    }
    assert binding.to_dict()["root"] == binding.root.to_dict()


def test_artifact_root_serializes_repo_and_plan_roots_deterministically() -> None:
    repo_root = ArtifactRoot(
        "repo-root",
        ".arnold/artifacts",
        kind=ArtifactRootKind.REPO_ARTIFACT_ROOT,
    )
    plan_root = ArtifactRoot(
        "plan-root",
        "runs/run-1/artifacts",
        kind=ArtifactRootKind.PLAN_ARTIFACT_ROOT,
    )

    assert repo_root.to_dict() == {
        "kind": "repo_artifact_root",
        "path": ".arnold/artifacts",
        "root_id": "repo-root",
    }
    assert plan_root.to_dict() == {
        "kind": "plan_artifact_root",
        "path": "runs/run-1/artifacts",
        "root_id": "plan-root",
    }


def test_provenance_parent_artifact_id_participates_in_hash() -> None:
    base = GeneratedArtifactProvenance(
        generator_module="arnold.docs.generator",
        generator_source_hash="sha256:" + "3" * 64,
        manifest_contract_version="arnold.workflow.manifest.v1",
        generated_at="2026-06-22T00:00:00Z",
        parents=(
            ProvenanceParent("source-a", "sha256:" + "5" * 64),
        ),
    )
    changed_parent = GeneratedArtifactProvenance(
        generator_module=base.generator_module,
        generator_source_hash=base.generator_source_hash,
        manifest_contract_version=base.manifest_contract_version,
        generated_at=base.generated_at,
        parents=(
            ProvenanceParent("source-b", "sha256:" + "5" * 64),
        ),
    )

    assert base.provenance_hash != changed_parent.provenance_hash


def test_artifact_root_rejects_invalid_logical_ids_and_paths() -> None:
    with pytest.raises(ValueError, match="logical root id"):
        ArtifactRoot("bad root", ".megaplan/reports")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("../escape.md")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("/absolute.md")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("reports/./v1.md")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("reports//v1.md")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("reports\\v1.md")

    with pytest.raises(ValueError, match="relative artifact path"):
        validate_safe_relative_subpath("reports/\x00/v1.md")

    assert validate_safe_relative_subpath("reports/v1.md") == "reports/v1.md"


def test_file_backed_store_rejects_unsafe_artifact_ids(tmp_path) -> None:
    registry = ContentTypeRegistry()
    registry.register(
        ContentTypeRegistration(
            type_id="markdown.report",
            schema_version="v1",
            schema_hash="sha256:" + "2" * 64,
        )
    )
    store = FileBackedArtifactStore(tmp_path, registry)
    provenance = GeneratedArtifactProvenance(
        generator_module="arnold.docs.generator",
        generator_source_hash="sha256:" + "3" * 64,
        manifest_contract_version="arnold.workflow.manifest.v1",
        generated_at="2026-06-22T00:00:00Z",
    )

    with pytest.raises(ValueError, match="logical root id"):
        store.write_artifact(
            "../escape",
            b"hello",
            "markdown.report",
            provenance,
            "md",
        )
