from __future__ import annotations

from arnold.kernel import (
    ArtifactBinding,
    ArtifactRoot,
    ContentTypeRegistration,
    GeneratedArtifactProvenance,
    RetentionPolicy,
    latest_version,
    next_version_path,
    versioned_artifact_name,
)


def test_versioned_artifact_naming_and_next_path() -> None:
    existing = ("artifacts/report.v1.md", "artifacts/report.v2.md")

    assert versioned_artifact_name("report", 3, ".md") == "report.v3.md"
    assert latest_version(existing, "md") == 2
    assert next_version_path("artifacts", "report", "md", existing) == "artifacts/report.v3.md"


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
    )
    binding = ArtifactBinding(
        artifact_id="report",
        root=ArtifactRoot("repo-megaplan", ".megaplan/reports"),
        relative_path="report.v1.md",
        content_type=content_type,
        provenance=provenance,
    )

    assert binding.root.root_id == "repo-megaplan"
    assert provenance.provenance_hash.startswith("sha256:")
