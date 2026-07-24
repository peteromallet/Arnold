from __future__ import annotations

import pytest

from arnold.kernel import (
    JudgeManifestCrossReference,
    JudgeManifestRelationship,
    derive_pipeline_identity,
    derive_workflow_tenant_id as kernel_derive_workflow_tenant_id,
)
from arnold.pipeline.discovery.trust import (
    TrustGrade,
    WorkflowTrustDecision,
    WorkflowTrustEvidenceKind,
    classify,
    classify_workflow_trust,
    derive_tenant_id,
    derive_workflow_tenant_id,
)


MANIFEST_HASH = "sha256:" + "a" * 64


def _judge_reference(manifest_hash: str = MANIFEST_HASH) -> JudgeManifestCrossReference:
    return JudgeManifestCrossReference(
        relationship=JudgeManifestRelationship.JUDGES_WORKFLOW,
        manifest_hash=manifest_hash,
        piece_version="piece:workflow.plan@sha256:abc",
        judge_version="judge:review@sha256:def",
        rubric_hash="sha256:" + "b" * 64,
    )


def test_workflow_trust_decisions_for_all_grades_carry_identity_anchor() -> None:
    for grade in TrustGrade:
        decision = classify_workflow_trust(
            grade,
            alias="planning",
            manifest_hash=MANIFEST_HASH,
        )

        assert decision.grade is grade
        assert decision.alias == "planning"
        assert decision.manifest_hash == MANIFEST_HASH
        assert decision.pipeline_identity == derive_pipeline_identity(
            "planning", MANIFEST_HASH
        )
        assert decision.tenant_id == kernel_derive_workflow_tenant_id(
            "planning", MANIFEST_HASH
        )
        assert decision.workflow_identity.pipeline_identity == decision.pipeline_identity


def test_workflow_tenant_derivation_delegates_to_kernel_identity() -> None:
    assert derive_workflow_tenant_id(
        "planning", MANIFEST_HASH
    ) == kernel_derive_workflow_tenant_id("planning", MANIFEST_HASH)
    assert derive_workflow_tenant_id("planning", MANIFEST_HASH).startswith("workflow_")


def test_path_derived_discovery_apis_are_package_metadata_only(tmp_path) -> None:
    root = tmp_path / "myapp" / "pipelines"
    root.mkdir(parents=True)
    module = root / "workflow.py"
    module.write_text("", encoding="utf-8")

    grade = classify(module, in_tree_path_fragment="myapp/pipelines")
    tenant_id = derive_tenant_id("planning", module)

    assert grade is TrustGrade.AUTO_EXEC
    assert tenant_id.startswith("pipeline_")
    assert not tenant_id.startswith("workflow_")
    assert tenant_id != derive_workflow_tenant_id("planning", MANIFEST_HASH)
    assert derive_tenant_id("planning", root / "other.py") != tenant_id


def test_workflow_trust_requires_manifest_hash_backed_inputs() -> None:
    with pytest.raises(TypeError):
        classify_workflow_trust(TrustGrade.AUTO_EXEC, alias="planning")

    with pytest.raises(ValueError, match="manifest_hash"):
        classify_workflow_trust(TrustGrade.AUTO_EXEC, alias="planning", manifest_hash="")

    with pytest.raises(ValueError, match="manifest_hash"):
        classify_workflow_trust(
            TrustGrade.AUTO_EXEC,
            alias="planning",
            manifest_hash="not-a-sha",
        )

    with pytest.raises(ValueError, match="workflow alias"):
        classify_workflow_trust(
            TrustGrade.AUTO_EXEC,
            alias="/tmp/package.py",
            manifest_hash=MANIFEST_HASH,
        )


def test_path_derived_classification_cannot_satisfy_manifest_aware_trust(tmp_path) -> None:
    module = tmp_path / "myapp" / "pipelines" / "workflow.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")

    package_grade = classify(module, in_tree_path_fragment="myapp/pipelines")
    package_tenant_id = derive_tenant_id("planning", module)

    with pytest.raises(ValueError, match="workflow alias"):
        classify_workflow_trust(
            package_grade,
            alias=str(module),
            manifest_hash=MANIFEST_HASH,
        )

    with pytest.raises(ValueError, match="manifest_hash"):
        classify_workflow_trust(
            package_grade,
            alias="planning",
            manifest_hash=package_tenant_id,
        )

    decision = classify_workflow_trust(
        package_grade,
        alias="planning",
        manifest_hash=MANIFEST_HASH,
    )
    assert decision.tenant_id != package_tenant_id


def test_workflow_trust_rejects_mismatched_precomputed_identity() -> None:
    with pytest.raises(ValueError, match="pipeline_identity"):
        WorkflowTrustDecision(
            grade=TrustGrade.AUTO_EXEC,
            alias="planning",
            manifest_hash=MANIFEST_HASH,
            pipeline_identity=derive_pipeline_identity("other", MANIFEST_HASH),
            tenant_id=kernel_derive_workflow_tenant_id("planning", MANIFEST_HASH),
        )

    with pytest.raises(ValueError, match="tenant_id"):
        WorkflowTrustDecision(
            grade=TrustGrade.AUTO_EXEC,
            alias="planning",
            manifest_hash=MANIFEST_HASH,
            pipeline_identity=derive_pipeline_identity("planning", MANIFEST_HASH),
            tenant_id=kernel_derive_workflow_tenant_id("other", MANIFEST_HASH),
        )


def test_judge_backed_workflow_trust_requires_cross_reference() -> None:
    with pytest.raises(ValueError, match="JudgeManifestCrossReference"):
        classify_workflow_trust(
            TrustGrade.BLESSED,
            alias="planning",
            manifest_hash=MANIFEST_HASH,
            evidence_kind=WorkflowTrustEvidenceKind.JUDGE,
        )

    with pytest.raises(ValueError, match="manifest_hash must match"):
        classify_workflow_trust(
            TrustGrade.BLESSED,
            alias="planning",
            manifest_hash=MANIFEST_HASH,
            evidence_kind=WorkflowTrustEvidenceKind.JUDGE,
            judge_manifest_cross_reference=_judge_reference("sha256:" + "c" * 64),
        )

    decision = classify_workflow_trust(
        TrustGrade.BLESSED,
        alias="planning",
        manifest_hash=MANIFEST_HASH,
        evidence_kind=WorkflowTrustEvidenceKind.JUDGE,
        judge_manifest_cross_reference=_judge_reference(),
    )

    assert decision.judge_manifest_cross_reference == _judge_reference()
    assert decision.pipeline_identity == derive_pipeline_identity(
        "planning", MANIFEST_HASH
    )


def test_package_promotion_evidence_is_metadata_not_identity_anchor() -> None:
    decision = classify_workflow_trust(
        TrustGrade.BLESSED,
        alias="planning",
        manifest_hash=MANIFEST_HASH,
        evidence_kind=WorkflowTrustEvidenceKind.PACKAGE_PROMOTION,
        package_promotion_evidence={
            "module_path": "/tmp/promoted.py",
            "legacy_tenant_id": "pipeline_pathderived",
        },
    )

    assert decision.package_promotion_evidence == {
        "legacy_tenant_id": "pipeline_pathderived",
        "module_path": "/tmp/promoted.py",
    }
    assert decision.pipeline_identity == derive_pipeline_identity(
        "planning", MANIFEST_HASH
    )

    with pytest.raises(TypeError):
        classify_workflow_trust(
            TrustGrade.BLESSED,
            package_promotion_evidence={"module_path": "/tmp/promoted.py"},
        )
