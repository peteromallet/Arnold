from __future__ import annotations

import inspect
from typing import Any

from arnold_pipelines.megaplan.authority.batch_scope import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
)
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    ResultEnvelope,
    SENSE_CHECK_ACK_CLAIM,
    SENSE_CHECK_RESULT_CAPABILITY,
    SenseCheckAttempt,
    SenseCheckClaim,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.execute import merge as merge_module
from arnold_pipelines.megaplan.execute.merge import _grant_aware_validate_entries
from arnold_pipelines.run_authority import CASExpectation, EvidenceEnvelope
from arnold_pipelines.run_authority import reducer as generic_reducer


def _task_entry(
    task_id: str = "T1",
    *,
    executor_notes: str = "validated",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "done",
        "executor_notes": executor_notes,
        "files_changed": [],
        "commands_run": [],
    }


def _task_envelope(
    entry: dict[str, Any],
    *,
    subject_id: str = "T1",
    run_revision: str = "revision-1",
    dispatch_id: str = "dispatch-1",
    prerequisite_digest: str = "prereq-1",
    worker_id: str = "worker-1",
    ordinal: int = 1,
    expected_cursor: int | None = None,
) -> ResultEnvelope:
    dispatch = DispatchIdentity.create(
        dispatch_id=dispatch_id,
        run_id="run-1",
        run_revision=run_revision,
        coordinator_attempt_id="coordinator-1",
        fence_token=3,
        subject_ids=(subject_id,),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest=prerequisite_digest,
        worker_id=worker_id,
        expected_cursor=expected_cursor,
    )
    base_id = f"{dispatch_id}:task:{subject_id}:{ordinal}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:evidence",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        evidence_type="megaplan.task_update",
        source="test",
        payload={"entry": entry},
    )
    attempt = TaskAttempt(
        attempt_id=f"{base_id}:attempt",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        ordinal=ordinal,
    )
    claim = TaskClaim(
        claim_id=f"{base_id}:claim",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        attempt_id=attempt.attempt_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{dispatch_id}:task:{subject_id}:claim",
        payload={"entry": entry},
    )
    return ResultEnvelope(
        dispatch=dispatch,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )


def _sense_check_entry(
    sense_check_id: str = "SC1",
    *,
    executor_note: str = "acknowledged",
) -> dict[str, Any]:
    return {
        "sense_check_id": sense_check_id,
        "executor_note": executor_note,
    }


def _sense_check_envelope(
    entry: dict[str, Any],
    *,
    subject_id: str = "SC1",
    run_revision: str = "revision-1",
    dispatch_id: str = "dispatch-1",
    prerequisite_digest: str = "prereq-1",
    worker_id: str = "worker-1",
    ordinal: int = 1,
) -> ResultEnvelope:
    dispatch = DispatchIdentity.create(
        dispatch_id=dispatch_id,
        run_id="run-1",
        run_revision=run_revision,
        coordinator_attempt_id="coordinator-1",
        fence_token=3,
        subject_ids=(subject_id,),
        capabilities=(SENSE_CHECK_RESULT_CAPABILITY,),
        prerequisite_digest=prerequisite_digest,
        worker_id=worker_id,
    )
    base_id = f"{dispatch_id}:sense_check:{subject_id}:{ordinal}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:evidence",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        evidence_type="megaplan.sense_check_acknowledgment",
        source="test",
        payload={"entry": entry},
    )
    attempt = SenseCheckAttempt(
        attempt_id=f"{base_id}:attempt",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        ordinal=ordinal,
    )
    claim = SenseCheckClaim(
        claim_id=f"{base_id}:claim",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        attempt_id=attempt.attempt_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        claim_type=SENSE_CHECK_ACK_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{dispatch_id}:sense_check:{subject_id}:claim",
        payload={"entry": entry},
    )
    return ResultEnvelope(
        dispatch=dispatch,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )


def _stamp_entry(entry: dict[str, Any], envelope: ResultEnvelope) -> dict[str, Any]:
    entry["authority"] = {
        "envelope_digest": envelope.digest(),
        "dispatch_id": envelope.dispatch_id,
        "run_revision": envelope.run_revision,
        "plan_revision": envelope.plan_revision,
        "fence": envelope.dispatch.fence.to_dict(),
        "scope": {
            "subject_ids": list(envelope.dispatch.subject_ids),
            "capabilities": list(envelope.dispatch.capabilities),
        },
        "prerequisite_digest": envelope.prerequisite_digest,
        "worker_id": envelope.worker_id,
        "attempt": envelope.attempt.to_dict(),
    }
    return entry


def _payload(envelopes: list[ResultEnvelope]) -> dict[str, Any]:
    assert envelopes
    return {
        DISPATCH_IDENTITY_KEY: envelopes[0].dispatch.to_dict(),
        RESULT_ENVELOPES_KEY: [envelope.to_dict() for envelope in envelopes],
    }


def _validate(
    entries: list[dict[str, Any]],
    *,
    payload: dict[str, Any],
    target_subject_ids: set[str] | None = None,
    state: dict[str, Any] | None = None,
    source_path: str = "<merge-payload>",
) -> tuple[list[str], tuple[str, ...]]:
    issues: list[str] = []
    result = _grant_aware_validate_entries(
        entries,
        payload={**payload, "task_updates": entries},
        target_subject_ids=target_subject_ids or {"T1"},
        id_field="task_id",
        entry_kind="task_update",
        expected_claim_type=TASK_COMPLETION_CLAIM,
        expected_capability=TASK_RESULT_CAPABILITY,
        issues=issues,
        state=state,
        source_path=source_path,
    )
    return issues, tuple(decision.outcome for decision in result.decisions)


def _validate_sense_checks(
    entries: list[dict[str, Any]],
    *,
    payload: dict[str, Any],
    target_subject_ids: set[str] | None = None,
    state: dict[str, Any] | None = None,
    source_path: str = "<merge-payload>",
) -> tuple[list[str], tuple[str, ...]]:
    issues: list[str] = []
    result = _grant_aware_validate_entries(
        entries,
        payload={**payload, "sense_check_acknowledgments": entries},
        target_subject_ids=target_subject_ids or {"SC1"},
        id_field="sense_check_id",
        entry_kind="sense_check_acknowledgment",
        expected_claim_type=SENSE_CHECK_ACK_CLAIM,
        expected_capability=SENSE_CHECK_RESULT_CAPABILITY,
        issues=issues,
        state=state,
        source_path=source_path,
    )
    return issues, tuple(decision.outcome for decision in result.decisions)


def test_validator_accepts_current_enveloped_task_update() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry)
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={
            "run_revision": "revision-1",
            "coordinator_attempt_id": "coordinator-1",
            "fence_token": 3,
            "prerequisite_digest": "prereq-1",
            "worker_id": "worker-1",
        },
    )

    assert outcomes == ("accepted",)
    assert entry["authority_validation"]["reason"] == "task_update_authority_valid"
    assert not issues


def test_validator_rejects_worker_identity_mismatch_without_accepting_entry() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry, worker_id="worker-1")
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={"worker_id": "worker-2"},
    )

    assert outcomes == ("rejected",)
    assert entry["authority_validation"]["reason"] == "worker_identity_mismatch"
    assert any("worker_identity_mismatch" in issue for issue in issues)


def test_validator_rejects_wrong_dispatch_id_echo_with_source_diagnostic() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry)
    _stamp_entry(entry, envelope)
    entry["authority"]["dispatch_id"] = "dispatch-from-another-batch"
    source_path = "/tmp/plan/execute_batches/batch_1/tasks_1f93603db53b.json"

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        source_path=source_path,
    )

    validation = entry["authority_validation"]
    assert outcomes == ("rejected",)
    assert validation["reason"] == "dispatch_id_echo_mismatch"
    assert validation["source_path"] == source_path
    assert any("dispatch_id_echo_mismatch" in issue for issue in issues)
    assert any(source_path in issue for issue in issues)


def test_validator_quarantines_entry_missing_result_envelope() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry)
    _stamp_entry(entry, envelope)
    payload = {
        DISPATCH_IDENTITY_KEY: envelope.dispatch.to_dict(),
        RESULT_ENVELOPES_KEY: [],
    }

    issues, outcomes = _validate([entry], payload=payload)

    assert outcomes == ("quarantined",)
    assert entry["authority_validation"]["reason"] == "missing_result_envelope"
    assert any("missing_result_envelope" in issue for issue in issues)


def test_validator_quarantines_result_with_insufficient_evidence() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry)
    _stamp_entry(entry, envelope)
    source_path = "/tmp/plan/execute_batches/batch_1/tasks_1f93603db53b.json"
    tampered = envelope.to_dict()
    tampered["claim"]["evidence_ids"] = ["missing-worker-result-evidence"]

    issues, outcomes = _validate(
        [entry],
        payload={
            DISPATCH_IDENTITY_KEY: envelope.dispatch.to_dict(),
            RESULT_ENVELOPES_KEY: [tampered],
        },
        source_path=source_path,
    )

    validation = entry["authority_validation"]
    assert outcomes == ("quarantined",)
    assert validation["reason"] == "malformed_result_envelopes"
    assert validation["source_path"] == source_path
    assert any("malformed_result_envelopes" in issue for issue in issues)
    assert any(source_path in issue for issue in issues)


def test_validator_marks_exact_replay_duplicate_idempotent() -> None:
    first = _task_entry(executor_notes="accepted once")
    duplicate = dict(first)
    first_envelope = _task_envelope(first, ordinal=1)
    duplicate_envelope = _task_envelope(duplicate, ordinal=1)
    _stamp_entry(first, first_envelope)
    _stamp_entry(duplicate, duplicate_envelope)

    issues, outcomes = _validate(
        [first, duplicate],
        payload=_payload([first_envelope, duplicate_envelope]),
    )

    assert outcomes == ("accepted", "duplicate-idempotent")
    assert duplicate["authority_validation"]["reason"] == "duplicate_idempotency_key"
    assert any("duplicate-idempotent" in issue for issue in issues)


def test_validator_rejects_off_scope_task_update_before_merge() -> None:
    entry = _task_entry("T2")
    envelope = _task_envelope(entry, subject_id="T2")
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        target_subject_ids={"T1"},
    )

    assert outcomes == ("rejected",)
    assert entry["authority_validation"]["reason"] == "subject_outside_dispatched_batch"
    assert any("subject_outside_dispatched_batch" in issue for issue in issues)


def test_validator_rejects_off_scope_sense_check_acknowledgment_before_merge() -> None:
    entry = _sense_check_entry("SC2")
    envelope = _sense_check_envelope(entry, subject_id="SC2")
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate_sense_checks(
        [entry],
        payload=_payload([envelope]),
        target_subject_ids={"SC1"},
    )

    assert outcomes == ("rejected",)
    assert entry["authority_validation"]["reason"] == "subject_outside_dispatched_batch"
    assert any("subject_outside_dispatched_batch" in issue for issue in issues)


def test_validator_marks_stale_revision_superseded_or_conflicting() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry, run_revision="old-revision")
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={"run_revision": "current-revision"},
    )

    assert outcomes == ("superseded-or-conflicting",)
    assert entry["authority_validation"]["reason"] == "plan_revision_mismatch"
    assert any("plan_revision_mismatch" in issue for issue in issues)


def test_validator_marks_stale_coordinator_fence_superseded_or_conflicting() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry)
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={"coordinator_attempt_id": "coordinator-1", "fence_token": 4},
    )

    assert outcomes == ("superseded-or-conflicting",)
    assert entry["authority_validation"]["reason"] == "coordinator_fence_mismatch"
    assert any("coordinator_fence_mismatch" in issue for issue in issues)


def test_validator_marks_stale_prerequisite_digest_superseded_or_conflicting() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry, prerequisite_digest="old-prereq-digest")
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={"prerequisite_digest": "current-prereq-digest"},
    )

    assert outcomes == ("superseded-or-conflicting",)
    assert entry["authority_validation"]["reason"] == "prerequisite_digest_mismatch"
    assert any("prerequisite_digest_mismatch" in issue for issue in issues)


def test_validator_marks_conflicting_idempotency_key_superseded_or_conflicting() -> None:
    first = _task_entry(executor_notes="first payload")
    conflicting = _task_entry(executor_notes="different payload")
    first_envelope = _task_envelope(first, ordinal=1)
    conflicting_envelope = _task_envelope(conflicting, ordinal=2)
    _stamp_entry(first, first_envelope)
    _stamp_entry(conflicting, conflicting_envelope)

    issues, outcomes = _validate(
        [first, conflicting],
        payload=_payload([first_envelope, conflicting_envelope]),
    )

    assert outcomes == ("accepted", "superseded-or-conflicting")
    assert conflicting["authority_validation"]["reason"] == "idempotency_key_conflict"
    assert any("idempotency_key_conflict" in issue for issue in issues)


def test_validator_marks_stale_cas_expectation_superseded_or_conflicting() -> None:
    entry = _task_entry()
    envelope = _task_envelope(entry, expected_cursor=7)
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
        state={"authority_journal_cursor": 8},
    )

    assert outcomes == ("superseded-or-conflicting",)
    assert entry["authority_validation"]["reason"] == "cas_expectation_mismatch"
    assert any("cas_expectation_mismatch" in issue for issue in issues)


def test_validator_marks_conflicting_cas_expectations_superseded_or_conflicting() -> None:
    entry = _task_entry()
    base = _task_envelope(entry, expected_cursor=7)
    envelope = ResultEnvelope(
        dispatch=base.dispatch,
        attempt=base.attempt,
        claim=base.claim,
        evidence=base.evidence,
        cas_expectation=CASExpectation("run-1", "revision-1", 8),
    )
    _stamp_entry(entry, envelope)

    issues, outcomes = _validate(
        [entry],
        payload=_payload([envelope]),
    )

    assert outcomes == ("superseded-or-conflicting",)
    assert entry["authority_validation"]["reason"] == "cas_expectation_conflict"
    assert any("cas_expectation_conflict" in issue for issue in issues)


def test_megaplan_policy_stays_outside_generic_reducer() -> None:
    reducer_source = inspect.getsource(generic_reducer)
    merge_source = inspect.getsource(merge_module)

    forbidden_generic_terms = (
        "megaplan",
        "task_id",
        "sense_check",
        "batch_scope",
        "next_ready_wave",
        "prerequisite_digest",
        "worker_id",
    )
    assert not any(term in reducer_source for term in forbidden_generic_terms)
    assert "TASK_RESULT_CAPABILITY" in merge_source
    assert "prerequisite_digest" in merge_source
