from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from arnold_pipelines.run_authority import (
    CASExpectation,
    CapabilityGrant,
    Claim,
    COHERENT,
    ContractError,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    INCOHERENT,
    IdempotencyConflict,
    IdempotencyKey,
    IdentityConflict,
    ObservationEnvelope,
    PayloadConflict,
    ProjectionMetadata,
    QuarantineRecord,
    RUNTIME_OBSERVATION_FIELDS,
    RevisionConflict,
    SubjectAttempt,
    UNKNOWN,
    assert_idempotent,
    contract_from_dict,
    evaluate_runtime_observation,
    validate_scope_binding,
    validate_relationships,
)


def _coherent_capture():
    return {
        "recorded_engine_root": "/workspace/arnold",
        "manifest_runtime_root": "/workspace/arnold",
        "manifest_expected_head": "a" * 40,
        "live_import_root": "/workspace/arnold",
        "wrapper_digest": "b" * 64,
        "dependency_generation": "v3-r7",
        "environment_identity": "env-a",
        "session_identity": "env-a",
    }


def _capture_observation(
    observation_id="obs-coherent",
    *,
    source_identity="collector://one",
    source_version="1.2.3",
    source_cursor=7,
    content_hash="c" * 64,
    **capture_changes,
):
    capture = _coherent_capture()
    capture.update(capture_changes)
    return ObservationEnvelope.capture(
        observation_id=observation_id,
        run_id="run-1",
        run_revision="rev-2",
        observation_type="runtime",
        source="collector://one",
        runtime_observation=capture,
        source_identity=source_identity,
        source_version=source_version,
        source_cursor=source_cursor,
        content_hash=content_hash,
    )


def _records():
    evidence = EvidenceEnvelope(
        evidence_id="ev-1",
        run_id="run-1",
        run_revision="rev-2",
        evidence_type="result",
        source="worker://one",
        payload={"z": [2, 1], "a": {"valid": True}},
    )
    observation = ObservationEnvelope(
        observation_id="obs-1",
        run_id="run-1",
        run_revision="rev-2",
        observation_type="heartbeat",
        source="collector://one",
        evidence_ids=("ev-1", "ev-1"),
        payload={"alive": True},
    )
    fence = CoordinatorFence("run-1", "rev-2", "coord-3", 7)
    grant = CapabilityGrant(
        grant_id="grant-1",
        run_id="run-1",
        run_revision="rev-2",
        coordinator_attempt_id="coord-3",
        fence_token=7,
        subject_ids=("subject-b", "subject-a", "subject-a"),
        capabilities=("write", "read"),
        evidence_ids=(),
    )
    attempt = SubjectAttempt("attempt-1", "run-1", "rev-2", "subject-a", "grant-1", "coord-3", 7, 1)
    claim = Claim(
        claim_id="claim-1",
        run_id="run-1",
        run_revision="rev-2",
        subject_id="subject-a",
        attempt_id="attempt-1",
        grant_id="grant-1",
        coordinator_attempt_id="coord-3",
        fence_token=7,
        claim_type="result",
        evidence_ids=("ev-1",),
        idempotency_key="result:attempt-1",
        payload={"status": "complete"},
    )
    decision = Decision(
        decision_id="decision-1",
        run_id="run-1",
        run_revision="rev-2",
        subject_id="subject-a",
        attempt_id="attempt-1",
        grant_id="grant-1",
        coordinator_attempt_id="coord-3",
        fence_token=7,
        claim_id="claim-1",
        outcome="accepted",
        evidence_ids=("ev-1",),
        idempotency_key="decision:claim-1",
        payload={"reason": "verified"},
    )
    quarantine = QuarantineRecord(
        "quarantine-1", "run-1", "rev-2", "claim", "claim-2", "wrong revision",
        "artifact://claim-2", ("ev-1",), {"observed_revision": "rev-1"},
    )
    projection = ProjectionMetadata("run-1", "rev-2", 4, "evidence-digest", "view-hash")
    cas = CASExpectation("run-1", "rev-2", 4)
    key = IdempotencyKey("result:attempt-1", claim.payload_hash)
    return evidence, observation, fence, grant, attempt, claim, decision, quarantine, projection, cas, key


def test_all_contracts_round_trip_canonically_and_are_deeply_immutable() -> None:
    records = _records()
    for record in records:
        encoded = record.to_json()
        assert encoded == record.to_json()
        assert encoded == json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        assert type(record).from_json(encoded) == record
        assert contract_from_dict(record.to_dict()) == record
        assert len(record.digest()) == 64

    evidence, observation, _, grant, *_ = records
    assert grant.subject_ids == ("subject-a", "subject-b")
    assert observation.evidence_ids == ("ev-1",)
    with pytest.raises(TypeError):
        evidence.payload["new"] = "mutation"
    with pytest.raises(FrozenInstanceError):
        evidence.source = "other"


def test_payload_hashes_are_order_independent_and_tampering_is_rejected() -> None:
    left = EvidenceEnvelope("ev", "run", "rev", "kind", "source", {"b": 2, "a": [1, {"x": True}]})
    right = EvidenceEnvelope("ev", "run", "rev", "kind", "source", {"a": [1, {"x": True}], "b": 2})
    assert left.payload_hash == right.payload_hash
    assert left.to_json() == right.to_json()

    tampered = left.to_dict()
    tampered["payload"]["b"] = 3
    with pytest.raises(PayloadConflict):
        EvidenceEnvelope.from_dict(tampered)
    with pytest.raises(ContractError):
        EvidenceEnvelope("ev", "run", "rev", "kind", "source", {"bad": float("nan")})


def test_complete_relationship_chain_accepts_and_all_identity_links_reject_conflicts() -> None:
    evidence, _, fence, grant, attempt, claim, decision, *_ = _records()
    validate_relationships(
        fence=fence,
        grant=grant,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
        decision=decision,
    )

    conflicts = (
        ("fence", replace(fence, run_id="other"), IdentityConflict),
        ("grant", replace(grant, run_revision="stale"), RevisionConflict),
        ("grant", replace(grant, coordinator_attempt_id="other"), IdentityConflict),
        ("attempt", replace(attempt, grant_id="other"), IdentityConflict),
        ("attempt", replace(attempt, subject_id="off-scope"), IdentityConflict),
        ("attempt", replace(attempt, fence_token=6), IdentityConflict),
        ("claim", replace(claim, attempt_id="other"), IdentityConflict),
        ("claim", replace(claim, evidence_ids=("missing",)), IdentityConflict),
        ("decision", replace(decision, claim_id="other"), IdentityConflict),
        ("evidence", replace(evidence, run_revision="stale"), RevisionConflict),
    )
    base = {"fence": fence, "grant": grant, "attempt": attempt, "claim": claim, "decision": decision}
    for target, replacement, error in conflicts:
        values = dict(base)
        evidence_items = (evidence,)
        if target == "evidence":
            evidence_items = (replacement,)
        else:
            values[target] = replacement
        with pytest.raises(error):
            validate_relationships(**values, evidence=evidence_items)


def test_validate_scope_binding_requires_current_grant_subject_and_capability() -> None:
    _, _, fence, grant, *_ = _records()

    validate_scope_binding(
        grant=grant,
        fence=fence,
        expected_grant_id=grant.grant_id,
        subject_id="subject-a",
        fence_token=fence.token,
        required_capability="read",
    )

    with pytest.raises(RevisionConflict):
        validate_scope_binding(
            grant=grant,
            fence=fence,
            expected_grant_id="stale-grant",
            subject_id="subject-a",
            fence_token=fence.token,
            required_capability="read",
        )
    with pytest.raises(IdentityConflict):
        validate_scope_binding(
            grant=grant,
            fence=fence,
            expected_grant_id=grant.grant_id,
            subject_id="subject-z",
            fence_token=fence.token,
            required_capability="read",
        )
    with pytest.raises(IdentityConflict):
        validate_scope_binding(
            grant=grant,
            fence=fence,
            expected_grant_id=grant.grant_id,
            subject_id="subject-a",
            fence_token=fence.token,
            required_capability="publish",
        )


def test_cas_idempotency_and_payload_conflict_semantics_are_explicit() -> None:
    records = _records()
    claim = records[5]
    decision = records[6]
    cas = records[9]
    key = records[10]
    cas.assert_matches(run_id="run-1", revision="rev-2", cursor=4)
    with pytest.raises(IdentityConflict):
        cas.assert_matches(run_id="other", revision="rev-2", cursor=4)
    with pytest.raises(RevisionConflict):
        cas.assert_matches(run_id="run-1", revision="rev-1", cursor=4)
    with pytest.raises(RevisionConflict):
        cas.assert_matches(run_id="run-1", revision="rev-2", cursor=3)

    key.assert_compatible(IdempotencyKey(key.value, key.payload_hash))
    with pytest.raises(IdempotencyConflict):
        key.assert_compatible(IdempotencyKey(key.value, "different"))
    assert_idempotent(claim, replace(claim))
    with pytest.raises(IdempotencyConflict):
        assert_idempotent(claim, replace(claim, payload={"status": "failed"}))
    # Different operations may legitimately have different payloads.
    assert_idempotent(claim, replace(claim, idempotency_key="another-operation", payload={"status": "failed"}))
    assert decision.outcome == "accepted"


def test_contract_package_has_no_megaplan_or_persistence_policy() -> None:
    package = Path(__file__).parents[3] / "arnold_pipelines" / "run_authority"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))).lower()
    forbidden = (
        "megaplan", "taskattempt", "dispatchgrant", "sense_check", "ready_wave",
        "finalize.json", "state.json", "pathlib", "sqlite", "repository", "journal.append",
    )
    assert all(term not in source for term in forbidden)


def test_runtime_capture_complete_agreement_is_coherent_and_dispatchable() -> None:
    envelope = _capture_observation()

    assert envelope.coherence == COHERENT
    assert envelope.is_dispatchable is True
    assert envelope.coherence_reasons == ()
    # A coherent envelope must carry the capture that backs the verdict.
    assert envelope.runtime_observation is not None
    assert envelope.runtime_observation["live_import_root"] == "/workspace/arnold"

    # The typed capture fields survive a canonical round trip unchanged.
    encoded = envelope.to_json()
    decoded = ObservationEnvelope.from_json(encoded)
    assert decoded == envelope
    assert decoded.coherence == COHERENT
    assert decoded.is_dispatchable is True
    assert contract_from_dict(envelope.to_dict()) == envelope


def test_missing_runtime_source_is_unknown_and_never_dispatchable() -> None:
    envelope = _capture_observation(observation_id="obs-missing", live_import_root=None)

    assert envelope.coherence == UNKNOWN
    assert envelope.is_dispatchable is False
    assert "missing_runtime_observation_field:live_import_root" in envelope.coherence_reasons

    # Removing a whole capture is unknown, not coherent and not an error.
    assert evaluate_runtime_observation(None) == (UNKNOWN, ("missing_runtime_observation",))


def test_disagreeing_engine_roots_are_incoherent_and_never_dispatchable() -> None:
    envelope = _capture_observation(
        observation_id="obs-torn", live_import_root="/workspace/other",
    )

    assert envelope.coherence == INCOHERENT
    assert envelope.is_dispatchable is False
    assert "engine_root_mismatch" in envelope.coherence_reasons


def test_cross_environment_capture_is_incoherent() -> None:
    envelope = _capture_observation(
        observation_id="obs-cross-env", session_identity="env-b",
    )

    assert envelope.coherence == INCOHERENT
    assert envelope.is_dispatchable is False
    assert "environment_session_identity_mismatch" in envelope.coherence_reasons


def test_stale_or_invalid_capture_is_unknown() -> None:
    stale = _capture_observation(observation_id="obs-stale", stale=True)
    assert stale.coherence == UNKNOWN
    assert stale.is_dispatchable is False
    assert "stale_runtime_observation" in stale.coherence_reasons

    invalid = _capture_observation(
        observation_id="obs-invalid", dependency_generation=42,
    )
    assert invalid.coherence == UNKNOWN
    assert invalid.is_dispatchable is False
    assert "invalid_runtime_observation_field:dependency_generation" in invalid.coherence_reasons


def test_legacy_observation_dict_deserializes_only_as_typed_unknown() -> None:
    legacy = ObservationEnvelope(
        "legacy-1", "run-1", "old-revision", "terminal_status_label",
        "legacy://state", (), {"status": "complete"},
    )
    legacy_dict = {
        "contract_type": "observation",
        "schema_version": 1,
        "observation_id": "legacy-1",
        "run_id": "run-1",
        "run_revision": "old-revision",
        "observation_type": "terminal_status_label",
        "source": "legacy://state",
        "evidence_ids": [],
        "payload": {"status": "complete"},
        "payload_hash": legacy.payload_hash,
    }

    decoded = ObservationEnvelope.from_dict(legacy_dict)

    # The legacy record is preserved, but only as explicitly typed unknown
    # evidence: it is never coherent and never dispatchable.
    assert decoded.observation_id == "legacy-1"
    assert decoded.coherence == UNKNOWN
    assert decoded.is_dispatchable is False
    assert "legacy_record_without_coherence_fields" in decoded.coherence_reasons
    assert decoded.runtime_observation is None
    # The typed-unknown legacy record round trips deterministically.
    assert ObservationEnvelope.from_dict(decoded.to_dict()) == decoded


def test_legacy_positional_construction_stays_typed_unknown() -> None:
    legacy = ObservationEnvelope(
        "legacy-2", "run-1", "old-revision", "terminal_status_label",
        "legacy://state", (), {"status": "done"},
    )

    assert legacy.coherence == UNKNOWN
    assert legacy.is_dispatchable is False
    assert legacy.runtime_observation is None
    assert legacy.coherence_reasons


def test_coherent_envelope_cannot_be_constructed_from_incomplete_input() -> None:
    incomplete = _coherent_capture()
    del incomplete["wrapper_digest"]

    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, coherence=COHERENT, runtime_observation=incomplete,
        )
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, coherence=COHERENT,
        )
    # A verdict that contradicts the capture is never silently accepted.
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-lying", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, coherence=UNKNOWN, runtime_observation=_coherent_capture(),
            source_identity="collector://one", source_version="1.2.3",
            source_cursor=7, content_hash="c" * 64,
        )


def test_missing_provenance_is_unknown_and_never_dispatchable() -> None:
    # A fully agreeing runtime capture without any provenance is UNKNOWN, not
    # COHERENT: an envelope lacking source identity/version/cursor and content
    # hash can never authorize dispatch.
    bare = _capture_observation(
        observation_id="obs-no-provenance",
        source_identity=None, source_version=None,
        source_cursor=None, content_hash=None,
    )

    assert bare.coherence == UNKNOWN
    assert bare.is_dispatchable is False
    for name in ("source_identity", "source_version", "source_cursor", "content_hash"):
        assert f"missing_provenance_field:{name}" in bare.coherence_reasons

    # Partially filled provenance is UNKNOWN too, never COHERENT.
    partial = _capture_observation(
        observation_id="obs-partial-provenance",
        source_cursor=None, content_hash=None,
    )
    assert partial.coherence == UNKNOWN
    assert partial.is_dispatchable is False
    assert "missing_provenance_field:source_cursor" in partial.coherence_reasons
    assert "missing_provenance_field:content_hash" in partial.coherence_reasons
    assert "missing_provenance_field:source_identity" not in partial.coherence_reasons


def test_validated_capture_fields_reject_malformed_values() -> None:
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, coherence="MAYBE",
        )
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, content_hash="not-a-hash",
        )
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, source_cursor=-1,
        )
    with pytest.raises(ContractError):
        ObservationEnvelope(
            "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
            {}, source_cursor=True,
        )

    envelope = ObservationEnvelope(
        "obs-1", "run-1", "rev-2", "runtime", "collector://one", (),
        {}, source_identity="collector://one", source_version="1.2.3",
        source_cursor=7, content_hash="c" * 64,
    )
    assert envelope.source_cursor == 7
    assert envelope.content_hash == "c" * 64
    assert envelope.coherence == UNKNOWN


def test_runtime_observation_fields_cover_every_agreement_dimension() -> None:
    expected = {
        "recorded_engine_root", "manifest_runtime_root", "manifest_expected_head",
        "live_import_root", "wrapper_digest", "dependency_generation",
        "environment_identity", "session_identity",
    }
    assert set(RUNTIME_OBSERVATION_FIELDS) == expected
    assert len(RUNTIME_OBSERVATION_FIELDS) == len(expected)
