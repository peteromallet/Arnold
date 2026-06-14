from __future__ import annotations

from arnold.pipelines.megaplan.orchestration.evidence_contract import (
    ARTIFACT_REF_SCHEMA,
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    EVIDENCE_REF_SCHEMA,
    EVIDENCE_REF_SCHEMA_VERSION,
    TRANSITION_DECISION_SCHEMA,
    TRANSITION_DECISION_SCHEMA_VERSION,
    ArtifactRef,
    EvidenceRef,
    EvidenceStatus,
    TransitionDecision,
    TrustClass,
    normalize_evidence_status,
)


def test_evidence_status_vocabulary_is_canonical():
    assert {status.value for status in EvidenceStatus} == {
        "satisfied",
        "unsatisfied",
        "unknown",
        "not_applicable",
        "waived",
    }


def test_trust_class_vocabulary_is_canonical():
    assert {trust_class.value for trust_class in TrustClass} == {
        "claim",
        "evidence",
        "judgment",
        "routing",
    }


def test_normalize_evidence_status_preserves_legacy_diagnostics():
    normalized = normalize_evidence_status("fail-not-success")

    assert normalized.status == EvidenceStatus.unsatisfied
    assert normalized.diagnostics == {
        "status_normalization": "legacy_alias",
        "legacy_status": "fail-not-success",
        "canonical_status": "unsatisfied",
    }


def test_normalize_evidence_status_maps_legacy_not_evaluated_to_unknown():
    normalized = normalize_evidence_status("not_evaluated")

    assert normalized.status == EvidenceStatus.unknown
    assert normalized.diagnostics["legacy_status"] == "not_evaluated"
    assert normalized.diagnostics["canonical_status"] == "unknown"


def test_evidence_ref_preserves_old_constructor_contract():
    ref = EvidenceRef("green_suite", EvidenceStatus.satisfied, "passed", {"status": "passed"})

    assert ref.kind == "green_suite"
    assert ref.status == EvidenceStatus.satisfied
    assert ref.summary == "passed"
    assert ref.details == {"status": "passed"}
    assert ref.trust_class is None
    assert ref.artifact is None


def test_artifact_ref_round_trips_with_canonical_schema_fields():
    artifact = ArtifactRef(
        path="verification/raw.log",
        sha256="abc",
        artifact_type="suite_log",
        schema=ARTIFACT_REF_SCHEMA,
        schema_version=1,
        uri="file:///tmp/raw.log",
    )

    payload = artifact.to_dict()

    assert payload == {
        "schema": ARTIFACT_REF_SCHEMA,
        "schema_version": 1,
        "path": "verification/raw.log",
        "sha256": "abc",
        "artifact_type": "suite_log",
        "uri": "file:///tmp/raw.log",
    }
    assert ArtifactRef.from_dict(payload) == artifact


def test_evidence_ref_from_dict_normalizes_legacy_status_and_keeps_diagnostics():
    ref = EvidenceRef.from_dict(
        {
            "kind": "review_disposition",
            "status": "fail-not-success",
            "summary": "force-proceed at rework cap",
            "details": {"review_verdict": "fail-not-success"},
        }
    )

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details["review_verdict"] == "fail-not-success"
    assert ref.details["diagnostics"]["legacy_status"] == "fail-not-success"
    assert ref.details["diagnostics"]["canonical_status"] == "unsatisfied"


def test_evidence_ref_round_trips_canonical_serialization_with_provenance():
    ref = EvidenceRef(
        kind="green_suite",
        status=EvidenceStatus.satisfied,
        summary="verification passed",
        details={"run_id": "r1"},
        trust_class=TrustClass.evidence,
        provider="green_suite",
        provider_version="1",
        source="suite_runs.ndjson",
        subject="plan:demo",
        observed_at="2026-06-07T00:00:00Z",
        code_hash="abc123",
        artifact=ArtifactRef(
            path="verification/raw.log",
            sha256="abc",
            artifact_type="suite_log",
            schema=ARTIFACT_REF_SCHEMA,
            schema_version=1,
        ),
    )

    payload = ref.to_dict()
    loaded = EvidenceRef.from_dict(payload)

    assert payload["schema"] == EVIDENCE_REF_SCHEMA
    assert payload["schema_version"] == EVIDENCE_REF_SCHEMA_VERSION
    assert payload["evidence_contract_version"] == EVIDENCE_CONTRACT_SCHEMA_VERSION
    assert payload["trust_class"] == "evidence"
    assert loaded == ref
    assert loaded.artifact == ArtifactRef(
        path="verification/raw.log",
        sha256="abc",
        artifact_type="suite_log",
        schema=ARTIFACT_REF_SCHEMA,
        schema_version=1,
    )


def test_evidence_ref_from_dict_maps_unknown_status_to_unknown_with_diagnostics():
    ref = EvidenceRef.from_dict(
        {
            "kind": "green_suite",
            "status": "mystery-state",
            "summary": "provider emitted unknown status",
            "details": {"raw_status": "mystery-state"},
        }
    )

    assert ref.status == EvidenceStatus.unknown
    assert ref.details["raw_status"] == "mystery-state"
    assert ref.details["diagnostics"] == {
        "status_normalization": "unknown",
        "legacy_status": "mystery-state",
        "canonical_status": "unknown",
    }


def test_transition_decision_is_schema_only_and_round_trips_evidence_refs():
    decision = TransitionDecision(
        decision_id="d1",
        subject="plan:demo",
        from_state="active",
        to_state="done",
        action="transition",
        status="would_block",
        evidence=(
            EvidenceRef(
                "review_disposition",
                EvidenceStatus.unsatisfied,
                "legacy force-proceed",
                {"diagnostics": {"legacy_status": "fail-not-success"}},
                trust_class=TrustClass.judgment,
            ),
        ),
        would_block_reasons=("review_disposition:legacy force-proceed",),
        invocation_id="inv1",
        phase="finalize",
        iteration=3,
        base_sha="base",
        head_sha="head",
        code_hash="hash",
        routing_provider="completion_contract",
        routing_provenance={"mode": "shadow"},
    )

    payload = decision.to_dict()
    loaded = TransitionDecision.from_dict(payload)

    assert payload["schema"] == TRANSITION_DECISION_SCHEMA
    assert payload["schema_version"] == TRANSITION_DECISION_SCHEMA_VERSION
    assert loaded == decision
