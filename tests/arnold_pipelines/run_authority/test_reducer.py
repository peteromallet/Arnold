from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from arnold_pipelines.run_authority import (
    CapabilityGrant,
    Claim,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyKey,
    ObservationEnvelope,
    SubjectAttempt,
    reduce_run_authority,
)


def _chain():
    evidence = EvidenceEnvelope("ev-1", "run-1", "rev-2", "result", "worker://one", {"ok": True})
    fence = CoordinatorFence("run-1", "rev-2", "coord-1", 3)
    grant = CapabilityGrant(
        "grant-1", "run-1", "rev-2", "coord-1", 3, ("subject-1",), ("submit",), ("ev-1",)
    )
    attempt = SubjectAttempt("attempt-1", "run-1", "rev-2", "subject-1", "grant-1", "coord-1", 3, 1)
    claim = Claim(
        "claim-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "result", ("ev-1",), "claim-key", {"state": "complete"},
    )
    decision = Decision(
        "decision-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "claim-1", "accepted", ("ev-1",), "decision-key", {"reason": "verified"},
    )
    return (
        evidence,
        fence,
        grant,
        attempt,
        IdempotencyKey("claim-key", claim.payload_hash),
        claim,
        IdempotencyKey("decision-key", decision.payload_hash),
        decision,
    )


def _reasons(view) -> set[str]:
    return {record.reason for record in view.quarantines}


def test_complete_chain_projects_stably_and_repeat_projection_is_idempotent() -> None:
    records = _chain()
    first = reduce_run_authority(records, run_id="run-1", run_revision="rev-2", journal_cursor=8)
    repeated = reduce_run_authority(records + records, run_id="run-1", run_revision="rev-2", journal_cursor=8)

    assert first.to_dict() == repeated.to_dict()
    assert first.to_json() == json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"))
    assert len(first.evidence_set_digest) == len(first.view_hash) == 64
    assert [item.claim_id for item in first.claims] == ["claim-1"]
    assert [item.decision_id for item in first.decisions] == ["decision-1"]
    assert first.quarantines == ()
    with pytest.raises(FrozenInstanceError):
        first.run_id = "changed"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda records: tuple(replace(item, run_revision="old") if isinstance(item, Claim) else item for item in records), "missing_matching_revision"),
        (lambda records: tuple(item for item in records if not isinstance(item, SubjectAttempt)), "missing_matching_attempt"),
        (lambda records: tuple(item for item in records if not isinstance(item, CapabilityGrant)), "missing_matching_grant"),
        (lambda records: tuple(item for item in records if not isinstance(item, CoordinatorFence)), "missing_matching_fence"),
        (lambda records: tuple(item for item in records if not isinstance(item, EvidenceEnvelope)), "missing_matching_evidence"),
        (lambda records: tuple(item for item in records if not (isinstance(item, IdempotencyKey) and item.value == "claim-key")), "missing_matching_idempotency_identity"),
    ],
)
def test_every_incompletely_linked_claim_is_deterministically_quarantined(mutate, reason: str) -> None:
    view = reduce_run_authority(mutate(_chain()), run_id="run-1", run_revision="rev-2")

    assert view.claims == ()
    assert reason in _reasons(view)
    assert view.decisions == ()
    assert "missing_authoritative_claim" in _reasons(view)
    assert all(record.source.startswith("contract://") for record in view.quarantines)


def test_legacy_observations_are_preserved_but_never_create_authority() -> None:
    legacy = ObservationEnvelope(
        "legacy-1", "run-1", "old-revision", "legacy_terminal_label",
        "legacy://state", (), {"status": "complete"},
    )
    view = reduce_run_authority((legacy,), run_id="run-1", run_revision="rev-2")

    assert view.observations == (legacy,)
    assert view.claims == ()
    assert view.decisions == ()
    assert view.quarantines == ()


def test_conflicting_record_and_idempotency_keys_are_excluded_independent_of_order() -> None:
    records = _chain()
    claim = next(item for item in records if isinstance(item, Claim))
    conflicting_claim = replace(claim, payload={"state": "failed"})
    conflicting_key = IdempotencyKey("claim-key", conflicting_claim.payload_hash)
    mixed = records + (conflicting_claim, conflicting_key)

    forward = reduce_run_authority(mixed, run_id="run-1", run_revision="rev-2", journal_cursor=10)
    reverse = reduce_run_authority(tuple(reversed(mixed)), run_id="run-1", run_revision="rev-2", journal_cursor=10)

    assert forward.to_dict() == reverse.to_dict()
    conflicts = [item for item in forward.diagnostics if item.code == "conflicting_duplicate_key"]
    assert {(item.record_type, item.record_id) for item in conflicts} == {
        ("claim", "claim-1"), ("idempotency_key", "claim-key")
    }
    assert forward.claims == ()
    assert forward.decisions == ()


def test_reducer_leaves_mutable_input_container_and_contract_payloads_unchanged() -> None:
    records = list(_chain())
    before = [item.to_json() for item in records]
    container_ids = [id(item) for item in records]

    first = reduce_run_authority(records, run_id="run-1", run_revision="rev-2")
    second = reduce_run_authority(records, run_id="run-1", run_revision="rev-2")

    assert [item.to_json() for item in records] == before
    assert [id(item) for item in records] == container_ids
    assert first.to_dict() == second.to_dict()
    with pytest.raises(TypeError):
        records[0].payload["mutated"] = True


def test_reducer_source_has_no_external_or_domain_specific_reads() -> None:
    import arnold_pipelines.run_authority.reducer as reducer

    source = reducer.__loader__.get_source(reducer.__name__).lower()
    forbidden = (
        "pathlib", "open(", "requests", "subprocess", "datetime", "time.",
        "import git", "megaplan", "finalize.json", "state.json", "os.environ",
    )
    assert all(term not in source for term in forbidden)
