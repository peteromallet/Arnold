from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from arnold_pipelines.run_authority import (
    CASExpectation,
    CapabilityGrant,
    Claim,
    ContractError,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyConflict,
    IdempotencyKey,
    IdentityConflict,
    ObservationEnvelope,
    PayloadConflict,
    ProjectionMetadata,
    QuarantineRecord,
    RevisionConflict,
    SubjectAttempt,
    assert_idempotent,
    contract_from_dict,
    validate_relationships,
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
