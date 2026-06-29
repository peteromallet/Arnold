from __future__ import annotations

import pytest

from arnold.kernel import (
    JudgeManifestCrossReference,
    JudgeManifestRelationship,
    WorkflowIdentity,
    derive_discovery_pipeline_id,
    derive_generated_artifact_identity_header_fields,
    derive_idempotency_key,
    derive_judge_sidecar_cross_reference_identity,
    derive_pipeline_identity,
    derive_registry_runtime_id,
    derive_workflow_tenant_id,
    workflow_identity_from_manifest,
)


def test_pipeline_identity_derives_from_alias_and_manifest_hash() -> None:
    manifest_hash = "sha256:" + "a" * 64

    assert derive_pipeline_identity("planning", manifest_hash) == derive_pipeline_identity(
        "planning", manifest_hash
    )
    assert derive_pipeline_identity("planning", manifest_hash) != derive_pipeline_identity(
        "other", manifest_hash
    )


def test_workflow_identity_derived_surfaces_share_only_alias_and_manifest_hash() -> None:
    alias = "planning"
    manifest_hash = "sha256:" + "a" * 64
    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)

    assert identity.pipeline_identity == derive_pipeline_identity(alias, manifest_hash)
    assert identity.registry_runtime_id == derive_registry_runtime_id(alias, manifest_hash)
    assert identity.discovery_pipeline_id == derive_discovery_pipeline_id(alias, manifest_hash)
    assert identity.tenant_id == derive_workflow_tenant_id(alias, manifest_hash)
    assert identity.generated_artifact_identity_header_fields == {
        "workflow_alias": alias,
        "manifest_hash": manifest_hash,
        "pipeline_identity": identity.pipeline_identity,
    }
    assert identity.generated_artifact_identity_header_fields == (
        derive_generated_artifact_identity_header_fields(alias, manifest_hash)
    )
    assert identity.judge_sidecar_cross_reference_identity == (
        derive_judge_sidecar_cross_reference_identity(alias, manifest_hash)
    )


def test_runtime_identity_surfaces_change_only_when_alias_or_manifest_hash_changes() -> None:
    alias = "planning"
    manifest_hash = "sha256:" + "a" * 64
    other_hash = "sha256:" + "b" * 64
    surfaces = (
        derive_pipeline_identity,
        derive_registry_runtime_id,
        derive_discovery_pipeline_id,
        derive_workflow_tenant_id,
        derive_judge_sidecar_cross_reference_identity,
    )

    for derive in surfaces:
        assert derive(alias, manifest_hash) == derive(alias, manifest_hash)
        assert derive(alias, manifest_hash) != derive("other", manifest_hash)
        assert derive(alias, manifest_hash) != derive(alias, other_hash)

    assert derive_generated_artifact_identity_header_fields(alias, manifest_hash) == {
        "workflow_alias": alias,
        "manifest_hash": manifest_hash,
        "pipeline_identity": derive_pipeline_identity(alias, manifest_hash),
    }
    assert derive_generated_artifact_identity_header_fields(alias, manifest_hash) != (
        derive_generated_artifact_identity_header_fields(alias, other_hash)
    )


def test_workflow_identity_adapter_ignores_version_path_and_discovery_metadata() -> None:
    manifest_hash = "sha256:" + "a" * 64

    class ManifestLike:
        id = "planning"
        manifest_hash = manifest_hash
        version = "v1"
        module_path = "/packages/one/pipeline.py"
        discovery_manifest_hash = "sha256:" + "b" * 64
        piece_version = "piece:one"
        judge_version = "judge:one"

    class SameRuntimeIdentityWithDifferentMetadata:
        id = "planning"
        manifest_hash = manifest_hash
        version = "v999"
        module_path = "/packages/two/pipeline.py"
        discovery_manifest_hash = "sha256:" + "c" * 64
        piece_version = "piece:two"
        judge_version = "judge:two"

    assert workflow_identity_from_manifest(ManifestLike) == workflow_identity_from_manifest(
        SameRuntimeIdentityWithDifferentMetadata
    )
    assert workflow_identity_from_manifest(ManifestLike).pipeline_identity == (
        derive_pipeline_identity("planning", manifest_hash)
    )


def test_judge_sidecar_lineage_fields_do_not_change_runtime_identity() -> None:
    alias = "planning"
    manifest_hash = "sha256:" + "a" * 64
    first_reference = JudgeManifestCrossReference(
        relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
        manifest_hash=manifest_hash,
        piece_version="piece:workflow.plan@sha256:111",
        judge_version="judge:review@sha256:222",
        rubric_hash="sha256:" + "b" * 64,
    )
    second_reference = JudgeManifestCrossReference(
        relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
        manifest_hash=manifest_hash,
        piece_version="piece:workflow.plan@sha256:333",
        judge_version="judge:review@sha256:444",
        rubric_hash="sha256:" + "c" * 64,
    )

    assert first_reference != second_reference
    assert derive_judge_sidecar_cross_reference_identity(alias, manifest_hash) == (
        derive_judge_sidecar_cross_reference_identity(alias, manifest_hash)
    )
    assert derive_pipeline_identity(alias, first_reference.manifest_hash) == (
        derive_pipeline_identity(alias, second_reference.manifest_hash)
    )


def test_idempotency_key_is_ordered_and_fail_closed() -> None:
    assert derive_idempotency_key("run", "node", "effect") != derive_idempotency_key(
        "effect", "node", "run"
    )
    with pytest.raises(ValueError):
        derive_idempotency_key("run", "")


def test_judge_manifest_cross_reference_is_validated_and_deterministic() -> None:
    reference = JudgeManifestCrossReference(
        relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
        manifest_hash="sha256:" + "a" * 64,
        piece_version="piece:workflow.plan@sha256:abc",
        judge_version="judge:review@sha256:def",
        rubric_hash="sha256:" + "b" * 64,
    )

    assert reference.to_dict() == {
        "judge_version": "judge:review@sha256:def",
        "manifest_hash": "sha256:" + "a" * 64,
        "piece_version": "piece:workflow.plan@sha256:abc",
        "relationship": "judges_workflow",
        "rubric_hash": "sha256:" + "b" * 64,
    }

    with pytest.raises(ValueError, match="rubric_hash"):
        JudgeManifestCrossReference(
            relationship=JudgeManifestRelationship.REVIEWED_BY_JUDGE,
            manifest_hash="sha256:" + "a" * 64,
            piece_version="piece:workflow.plan@sha256:abc",
            judge_version="judge:review@sha256:def",
            rubric_hash="not-a-hash",
        )


def test_judge_manifest_cross_reference_rejects_missing_and_whitespace_fields() -> None:
    for field_name in ("piece_version", "judge_version"):
        kwargs = {
            "relationship": JudgeManifestRelationship.JUDGES_WORKFLOW,
            "manifest_hash": "sha256:" + "a" * 64,
            "piece_version": "piece:workflow.plan@sha256:abc",
            "judge_version": "judge:review@sha256:def",
            "rubric_hash": "sha256:" + "b" * 64,
        }
        kwargs[field_name] = " "
        with pytest.raises(ValueError, match=field_name):
            JudgeManifestCrossReference(**kwargs)

    with pytest.raises(ValueError, match="manifest_hash"):
        JudgeManifestCrossReference(
            relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
            manifest_hash="",
            piece_version="piece",
            judge_version="judge",
            rubric_hash="sha256:" + "b" * 64,
        )


def test_judge_manifest_cross_reference_validates_relationship_enum() -> None:
    with pytest.raises(ValueError, match="relationship"):
        JudgeManifestCrossReference(
            relationship="not-a-relationship",
            manifest_hash="sha256:" + "a" * 64,
            piece_version="piece",
            judge_version="judge",
            rubric_hash="sha256:" + "b" * 64,
        )

    reference = JudgeManifestCrossReference(
        relationship="reviewed_by_judge",
        manifest_hash="sha256:" + "a" * 64,
        piece_version="piece",
        judge_version="judge",
        rubric_hash="sha256:" + "b" * 64,
    )
    assert reference.relationship is JudgeManifestRelationship.REVIEWED_BY_JUDGE


def test_judge_manifest_cross_reference_accepts_discovery_sidecar_versions() -> None:
    from arnold.pipeline.discovery.judge_manifest import (
        compute_judge_version,
        compute_piece_version,
        compute_rubric_hash,
    )

    rubric_hash = compute_rubric_hash({"checks": ["manifest identity"]})
    piece_version = compute_piece_version(
        implementation="arnold.judges.workflow:review",
        arnold_api_version="v1",
        source_hash="sha256:" + "c" * 64,
    )
    judge_version = compute_judge_version(
        piece_version=piece_version,
        model_identity="judge-model",
        rubric_hash=rubric_hash,
    )

    reference = JudgeManifestCrossReference(
        relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
        manifest_hash="sha256:" + "a" * 64,
        piece_version=piece_version,
        judge_version=judge_version,
        rubric_hash="sha256:" + rubric_hash,
    )

    assert reference.piece_version == piece_version
    assert reference.judge_version == judge_version
