from __future__ import annotations

import pytest

from arnold.kernel import (
    JudgeManifestCrossReference,
    JudgeManifestRelationship,
    derive_idempotency_key,
    derive_pipeline_identity,
)


def test_pipeline_identity_derives_from_alias_and_manifest_hash() -> None:
    manifest_hash = "sha256:" + "a" * 64

    assert derive_pipeline_identity("planning", manifest_hash) == derive_pipeline_identity(
        "planning", manifest_hash
    )
    assert derive_pipeline_identity("planning", manifest_hash) != derive_pipeline_identity(
        "other", manifest_hash
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
