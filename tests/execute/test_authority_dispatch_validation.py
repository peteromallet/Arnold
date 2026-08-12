from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pytest

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
from arnold_pipelines.megaplan.custody.action_validator import (
    GateResult,
    adapter_effect_authorized,
)
from arnold_pipelines.megaplan.execute import merge as merge_module
from arnold_pipelines.megaplan.execute.merge import _grant_aware_validate_entries
from arnold_pipelines.run_authority import CASExpectation, EvidenceEnvelope
from arnold_pipelines.run_authority import reducer as generic_reducer


class _UnknownGateResult(StrEnum):
    AUTHORIZED = "authorized"


@pytest.mark.parametrize(
    "gate_result",
    [
        None,
        RuntimeError("gate failed"),
        _UnknownGateResult.AUTHORIZED,
        "authorized",
        {"gate_result": "authorized"},
    ],
)
def test_adapter_effect_authorization_denies_absent_exceptional_or_malformed_results(
    gate_result: object,
) -> None:
    assert adapter_effect_authorized(gate_result) is False


@pytest.mark.parametrize(
    "gate_result",
    [result for result in GateResult if result.name.startswith("BLOCKED_")],
)
def test_adapter_effect_authorization_denies_every_blocked_verdict(
    gate_result: GateResult,
) -> None:
    assert adapter_effect_authorized(gate_result) is False


@pytest.mark.parametrize("gate_result", [GateResult.SHADOW_PASS, GateResult.ERROR])
def test_adapter_effect_authorization_denies_non_authoritative_gate_outcomes(
    gate_result: GateResult,
) -> None:
    assert adapter_effect_authorized(gate_result) is False


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


def test_validator_quarantines_scoped_legacy_task_without_dispatch_authority() -> None:
    entry = _task_entry()
    issues, outcomes = _validate([entry], payload={})

    assert outcomes == ("quarantined",)
    assert entry["authority_validation"]["reason"] == "missing_dispatch_identity"
    assert any("missing_dispatch_identity" in issue for issue in issues)


def test_validator_quarantines_sense_check_without_result_envelopes() -> None:
    entry = _sense_check_entry()
    issues, outcomes = _validate_sense_checks(
        [entry], payload={"dispatch_identity": _task_envelope(_task_entry()).dispatch.to_dict()}
    )

    assert outcomes == ("quarantined",)
    assert entry["authority_validation"]["reason"] == "missing_result_envelope"
    assert any("missing_result_envelope" in issue for issue in issues)


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


def test_retired_execute_authority_paths_are_not_executable() -> None:
    from arnold_pipelines.megaplan.orchestration import execution_evidence
    from arnold_pipelines.megaplan.workers import hermes

    merge_source = inspect.getsource(merge_module)
    hermes_source = inspect.getsource(hermes)
    evidence_source = inspect.getsource(execution_evidence)
    assert "legacy_no_authority_metadata" not in merge_source
    assert "execute_batch_*_output.json" not in hermes_source
    assert "apply_authoritative_execute_overrides" not in evidence_source


# ── T-0019: ExecuteEffectGate closes effects behind the frozen contract ──────


@dataclass
class _Reservation:
    global_logical_effect_key: str


class _RecordingProtocol:
    """EffectProtocol spy: records every effect call without side effects."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def reserve_and_start(self, **kwargs: Any) -> _Reservation:
        self.calls.append(("reserve_and_start",))
        return _Reservation(global_logical_effect_key="glek-exec-test")

    def persist_intent(self, **kwargs: Any) -> None:
        self.calls.append(("persist_intent",))

    def accept_outcome(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("accept_outcome",))


def _effect_target() -> Any:
    from arnold_pipelines.megaplan.execute.effect_gate import (
        ExecuteEffectFamily,
        ExecuteTarget,
    )

    return ExecuteTarget(
        family=ExecuteEffectFamily.LOCAL_WORKSPACE,
        batch_number=1,
        task_ids=("T1",),
        action="write_artifact",
    )


def _route_with_gate(
    *,
    gate_builder: Any,
    applied: list[Any],
) -> Any:
    from arnold_pipelines.megaplan.execute.effect_gate import ExecuteEffectGate

    protocol = _RecordingProtocol()
    kwargs = {} if gate_builder is None else {"action_gate_check": gate_builder}
    gate = ExecuteEffectGate(protocol, **kwargs)
    return protocol, gate.route(
        target=_effect_target(),
        intent_payload={"data": 1},
        apply_fn=lambda payload: applied.append(payload) or {"written": True},
    )


@pytest.mark.parametrize(
    "gate_builder,verdict_label",
    [
        pytest.param(None, "missing", id="no-gate-installed"),
        pytest.param(
            lambda f, t: (_ for _ in ()).throw(RuntimeError("gate failed")),
            "error",
            id="gate-raises-exception",
        ),
        pytest.param(
            lambda f, t: GateResult.SHADOW_PASS,
            "shadow_pass",
            id="shadow-pass",
        ),
        pytest.param(
            lambda f, t: GateResult.ERROR,
            "error",
            id="gate-error-verdict",
        ),
        pytest.param(
            lambda f, t: GateResult.BLOCKED_NO_LEASE,
            "blocked_no_lease",
            id="blocked-verdict",
        ),
        pytest.param(
            lambda f, t: "authorized",
            "str",
            id="malformed-string",
        ),
        pytest.param(
            lambda f, t: _UnknownGateResult.AUTHORIZED,
            "_UnknownGateResult",
            id="foreign-enum",
        ),
    ],
)
def test_execute_effect_gate_denies_before_any_protocol_or_effect_call(
    gate_builder: Any,
    verdict_label: str,
) -> None:
    applied: list[Any] = []
    protocol, outcome = _route_with_gate(
        gate_builder=gate_builder,
        applied=applied,
    )

    assert outcome.ok is False
    assert outcome.glek == ""
    assert outcome.outcome_kind == "FAILED"
    assert outcome.error is not None
    assert outcome.error.startswith("Action gate denied")
    assert outcome.evidence["gate_verdict"] == verdict_label
    assert protocol.calls == []  # no reserve/start, intent, or outcome write
    assert applied == []  # workspace/process/terminal mutation never ran


def test_execute_effect_gate_completes_when_authorized() -> None:
    from arnold_pipelines.megaplan.execute.effect_gate import ExecuteEffectGate

    protocol = _RecordingProtocol()
    gate = ExecuteEffectGate(
        protocol,
        action_gate_check=lambda f, t: GateResult.AUTHORIZED,
    )
    applied: list[Any] = []
    outcome = gate.route(
        target=_effect_target(),
        intent_payload={"data": 1},
        apply_fn=lambda payload: applied.append(payload) or {"written": True},
    )

    assert outcome.ok is True
    assert outcome.glek == "glek-exec-test"
    assert outcome.outcome_kind == "COMPLETED"
    assert [call[0] for call in protocol.calls] == [
        "reserve_and_start",
        "persist_intent",
        "accept_outcome",
    ]
    assert applied == [{"data": 1}]


def test_execute_effect_gate_missing_gate_is_typed_denial_not_shadow() -> None:
    applied: list[Any] = []
    protocol, outcome = _route_with_gate(gate_builder=None, applied=applied)

    assert outcome.ok is False
    assert outcome.evidence["gate_verdict"] == "missing"
    assert "no action gate installed" in (outcome.error or "")
    assert protocol.calls == []
    assert applied == []


# ── T-0019 (G4): production construction requires an explicit gate ──────────


def test_execute_effect_gate_production_without_gate_raises_at_construction() -> None:
    """T-0019: production_enabled=True without an explicit action_gate_check
    is a wiring error — the constructor raises a typed error before any
    dispatch, so an ungated production gate can never be installed."""
    from arnold_pipelines.megaplan.execute.effect_gate import (
        ExecuteEffectGate,
        ExecuteEffectGateError,
    )

    with pytest.raises(ExecuteEffectGateError) as excinfo:
        ExecuteEffectGate(_RecordingProtocol(), production_enabled=True)
    assert "action_gate_check" in str(excinfo.value)


def test_execute_effect_gate_production_with_explicit_gate_routes() -> None:
    """T-0019: production_enabled=True with an explicit gate constructs and
    routes through the gate exactly like observation mode."""
    from arnold_pipelines.megaplan.execute.effect_gate import ExecuteEffectGate

    protocol = _RecordingProtocol()
    gate = ExecuteEffectGate(
        protocol,
        production_enabled=True,
        action_gate_check=lambda f, t: GateResult.AUTHORIZED,
    )
    applied: list[Any] = []
    outcome = gate.route(
        target=_effect_target(),
        intent_payload={"data": 1},
        apply_fn=lambda payload: applied.append(payload) or {"written": True},
    )

    assert outcome.ok is True
    assert outcome.outcome_kind == "COMPLETED"
    assert [call[0] for call in protocol.calls] == [
        "reserve_and_start",
        "persist_intent",
        "accept_outcome",
    ]
    assert applied == [{"data": 1}]


def test_execute_effect_gate_observation_flag_without_gate_fails_closed() -> None:
    """T-0019: observation-only construction (production_enabled=False) may
    omit the gate — routing still fails closed as a typed denial."""
    from arnold_pipelines.megaplan.execute.effect_gate import ExecuteEffectGate

    protocol = _RecordingProtocol()
    gate = ExecuteEffectGate(protocol, production_enabled=False)
    applied: list[Any] = []
    outcome = gate.route(
        target=_effect_target(),
        intent_payload={"data": 1},
        apply_fn=lambda payload: applied.append(payload) or {"written": True},
    )

    assert outcome.ok is False
    assert outcome.outcome_kind == "FAILED"
    assert outcome.evidence["gate_verdict"] == "missing"
    assert protocol.calls == []
    assert applied == []
