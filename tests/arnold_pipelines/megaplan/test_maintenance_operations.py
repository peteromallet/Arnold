"""Focused proof tests for the M3 reference-only operational contracts (T2).

Covers the immutable occurrence-bound contracts (M7 occurrence/lease, Run
Authority grant/fence, M6A WBC attempt, policy, target, producer, owner
receipts, recurrence, escalation) and the closed operational lifecycle
vocabulary (request/source-change/install/retrigger/progress/checkpoint/
terminal/recurrence/escalation) from Plan Step 2:

* every owner coordinate is a locator-only OwnerRef — no owner payloads;
* all nine actions are DISTINCT events for one occurrence and a generic
  success receipt does not exist;
* recurrence requires a fresh canonical occurrence; escalation is a human
  gate reference that never waives;
* terminal verification can never be authored by a repair producer;
* Maintenance modules never import or construct owner authority stores.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointVerificationPayload,
    CheckpointWindowKind,
    HumanEscalationPayload,
    InstallationPayload,
    OperationalActionKind,
    OperationalEvent,
    ProgressObservationPayload,
    RecurrencePayload,
    RepairRequestPayload,
    RetriggerPayload,
    SIX_HOUR_ALIAS,
    SourceChangePayload,
    TerminalVerificationPayload,
    VerifierProvenance,
    canonical_checkpoint_window,
    operational_event_digest,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    EscalationReference,
    LeaseCoordinates,
    OccurrenceCoordinates,
    OwnerReceipts,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RecurrenceReference,
    RunAuthorityCoordinates,
    WbcAttemptCoordinates,
    assert_reference_only_contract,
)

UTC = timezone.utc

#: Owner stores / seams Maintenance domain modules must never import or
#: instantiate (mutation orchestration stays in the cloud adapter).
_FORBIDDEN_OWNER_IMPORTS = (
    "lease_store",
    "action_validator",
    "attempt_ledger_store",
    "repair_requests",
    "simple_fixer",
    "completion_engine",
    "transition_writer",
    "repair_queue",
    "controlled_writers",
)


def _ts() -> datetime:
    return datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _ref(owner: str = "custody", record_type: str = "lease", locator: str = "lease://l-1") -> OwnerRef:
    return OwnerRef(
        owner=owner,
        record_type=record_type,
        identity="occ-1",
        schema_version="1",
        locator=locator,
        digest="a" * 64,
        cursor="epoch:1",
    )


def _occurrence(occurrence_id: str = "occ-1") -> OccurrenceCoordinates:
    return OccurrenceCoordinates(
        occurrence_id=occurrence_id,
        canonical_digest="b" * 64,
        occurrence_ref=_ref("repair_custody", "occurrence", f"occurrence://{occurrence_id}"),
    )


def _lease() -> LeaseCoordinates:
    return LeaseCoordinates(
        lease_id="lease-1",
        custody_epoch=1,
        lease_digest="c" * 64,
        lease_ref=_ref("custody", "current_lease", "lease://lease-1"),
    )


def _run_authority() -> RunAuthorityCoordinates:
    return RunAuthorityCoordinates(
        run_id="run-1",
        satisfied=True,
        grant_ref=_ref("run_authority", "grant", "grant://g-1"),
        fence_ref=_ref("run_authority", "fence", "fence://att-1/1"),
    )


def _wbc() -> WbcAttemptCoordinates:
    return WbcAttemptCoordinates(
        attempt_id="att-1",
        attempt_ref=_ref("wbc", "attempt", "attempt://att-1"),
    )


def _policy() -> PolicyVersionCoordinates:
    return PolicyVersionCoordinates(policy_version="policy-v1", policy_digest="d" * 64)


def _target() -> ActionTarget:
    return ActionTarget(target="path/to/target", target_type="path")


def _producer(role: ProducerRole = ProducerRole.SCHEDULER) -> ProducerPrincipal:
    return ProducerPrincipal(principal="principal-1", role=role)


def _build(
    payload,
    *,
    producer: ProducerPrincipal | None = None,
    occurrence: OccurrenceCoordinates | None = None,
) -> OperationalEvent:
    return OperationalEvent.build(
        event_id=f"evt-{payload.kind}",
        occurrence=occurrence if occurrence is not None else _occurrence(),
        lease=_lease(),
        run_authority=_run_authority(),
        policy=_policy(),
        target=_target(),
        producer=producer if producer is not None else _producer(),
        payload=payload,
        observed_at=_ts(),
        wbc_attempt=_wbc(),
    )


# ---------------------------------------------------------------------------
# Reference-only contracts
# ---------------------------------------------------------------------------


def test_operational_coordinates_are_frozen_reference_only_and_round_trip() -> None:
    occurrence = _occurrence()
    lease = _lease()
    authority = _run_authority()
    wbc = _wbc()
    policy = _policy()
    target = _target()
    producer = _producer()
    receipts = OwnerReceipts(
        receipt_refs=[
            _ref("repair_custody", "receipt", "receipt://r-1"),
            _ref("plan", "receipt", "receipt://r-2"),
        ]
    )
    for model in (occurrence, lease, authority, wbc, policy, target, producer, receipts):
        assert_reference_only_contract(model)
        decoded = strict_loads(type(model), canonical_dumps(model))
        assert decoded == model
        assert canonical_digest(decoded) == canonical_digest(model)
    # Receipts are stored in deterministic (owner, locator) order and never
    # embed payloads.
    assert [r.locator for r in receipts.receipt_refs] == [
        "receipt://r-2",
        "receipt://r-1",
    ]
    assert "PAYLOAD" not in canonical_dumps(receipts)


def test_occurrence_coordinates_require_canonical_digest() -> None:
    with pytest.raises(ValueError, match="sha256"):
        OccurrenceCoordinates(occurrence_id="occ-1", canonical_digest="not-a-digest")


def test_recurrence_reference_is_analytical_grouping_only() -> None:
    recurrence = RecurrenceReference(
        predecessor_occurrence_id="occ-0",
        predecessor_event_id="evt-0",
        root_cause_cluster="cluster-1",
    )
    assert recurrence.predecessor_occurrence_id == "occ-0"
    assert recurrence.root_cause_cluster == "cluster-1"


def test_escalation_reference_is_human_gate_without_waiver() -> None:
    escalation = EscalationReference(
        reason="ambiguous blocker",
        escalation_owner="owner-1",
        escalation_ref=_ref("plan", "escalation", "escalation://owner-1/1"),
    )
    assert escalation.human_gate is True
    assert escalation.escalation_owner == "owner-1"
    with pytest.raises(ValueError, match="human gate"):
        EscalationReference(
            reason="waiver attempt",
            escalation_owner="owner-1",
            human_gate=False,
        )


# ---------------------------------------------------------------------------
# Closed action vocabulary and envelope
# ---------------------------------------------------------------------------


def test_closed_action_vocabulary_has_exactly_nine_distinct_actions() -> None:
    assert {action.value for action in OperationalActionKind} == {
        "repair_request",
        "source_change",
        "installation",
        "retrigger",
        "progress_observation",
        "checkpoint_verification",
        "terminal_verification",
        "recurrence",
        "human_escalation",
    }
    # There is deliberately NO generic success action.
    assert "success" not in {action.value for action in OperationalActionKind}


def _payload_for(kind: OperationalActionKind):
    if kind is OperationalActionKind.REPAIR_REQUEST:
        return RepairRequestPayload(request_id="req-1", request_ref=_ref("repair_custody", "request"))
    if kind is OperationalActionKind.SOURCE_CHANGE:
        return SourceChangePayload(change_ref=_ref("plan", "source_change"), source_digest="e" * 64)
    if kind is OperationalActionKind.INSTALLATION:
        return InstallationPayload(install_ref=_ref("plan", "installation"), install_digest="f" * 64)
    if kind is OperationalActionKind.RETRIGGER:
        return RetriggerPayload(retrigger_ref=_ref("repair_custody", "retrigger"), reason="retry")
    if kind is OperationalActionKind.PROGRESS_OBSERVATION:
        return ProgressObservationPayload(progress_refs=[_ref("status_projection", "progress")])
    if kind is OperationalActionKind.CHECKPOINT_VERIFICATION:
        return CheckpointVerificationPayload(
            checkpoint=CheckpointWindowKind.IMMEDIATE,
            checkpoint_ref=_ref("maintenance", "checkpoint"),
        )
    if kind is OperationalActionKind.TERMINAL_VERIFICATION:
        return TerminalVerificationPayload(
            verifier=VerifierProvenance(
                principal="verifier-1",
                runtime_digest="1" * 64,
                source_digest="2" * 64,
                observed_at=_ts(),
                direct_read_refs=[_ref("run_authority", "grant", "grant://g-1")],
            ),
            terminal_reason="blocker cleared",
            negative_control_refs=[_ref("conformance", "validation")],
        )
    if kind is OperationalActionKind.RECURRENCE:
        return RecurrencePayload(
            recurrence=RecurrenceReference(
                predecessor_occurrence_id="occ-0",
                predecessor_event_id="evt-0",
                root_cause_cluster="cluster-1",
            )
        )
    if kind is OperationalActionKind.HUMAN_ESCALATION:
        return HumanEscalationPayload(
            escalation=EscalationReference(reason="blocked", escalation_owner="owner-1")
        )
    raise AssertionError(f"unhandled action kind {kind}")


def test_every_action_kind_builds_a_distinct_operational_event() -> None:
    for kind in OperationalActionKind:
        event = _build(_payload_for(kind))
        assert event.action_kind is kind
        assert event.payload.kind == kind.value
        assert event.schema_version == 1
        assert event.occurrence.occurrence_id == "occ-1"
        assert event.lease.custody_epoch == 1
        assert event.run_authority.grant_ref is not None
        assert event.wbc_attempt is not None
        decoded = strict_loads(OperationalEvent, canonical_dumps(event))
        assert decoded == event
        assert operational_event_digest(decoded) == operational_event_digest(event)


def test_distinct_actions_coexist_for_one_occurrence_and_exact_retries_match() -> None:
    # Request, source-change, install, retrigger, progress, checkpoint, and
    # terminal actions for ONE occurrence are all valid and distinct.
    occurrence = _occurrence()
    events = [
        _build(_payload_for(kind), occurrence=occurrence)
        for kind in (
            OperationalActionKind.REPAIR_REQUEST,
            OperationalActionKind.SOURCE_CHANGE,
            OperationalActionKind.INSTALLATION,
            OperationalActionKind.RETRIGGER,
            OperationalActionKind.PROGRESS_OBSERVATION,
            OperationalActionKind.CHECKPOINT_VERIFICATION,
            OperationalActionKind.TERMINAL_VERIFICATION,
        )
    ]
    assert len({event.action_kind for event in events}) == 7
    assert len({operational_event_digest(event) for event in events}) == 7
    # An exact retry of one action deduplicates to the identical digest.
    retry = _build(_payload_for(OperationalActionKind.INSTALLATION), occurrence=occurrence)
    assert operational_event_digest(retry) == operational_event_digest(events[2])


def test_action_kind_mismatch_is_rejected() -> None:
    # No generic success receipt: a checkpoint payload cannot ride on a
    # different action kind (direct construction).
    with pytest.raises(ValueError, match="does not match payload kind"):
        OperationalEvent(
            schema_version=1,
            event_id="evt-1",
            action_kind=OperationalActionKind.REPAIR_REQUEST,
            occurrence=_occurrence(),
            lease=_lease(),
            run_authority=_run_authority(),
            policy=_policy(),
            target=_target(),
            producer=_producer(),
            observed_at=_ts(),
            payload=CheckpointVerificationPayload(checkpoint=CheckpointWindowKind.IMMEDIATE),
        )


def test_recurrence_requires_fresh_canonical_occurrence() -> None:
    # A recurrence that points back at its own occurrence is rejected.
    payload = RecurrencePayload(
        recurrence=RecurrenceReference(
            predecessor_occurrence_id="occ-1",  # equals the enclosing occurrence
            predecessor_event_id="evt-0",
        )
    )
    with pytest.raises(ValueError, match="fresh canonical occurrence"):
        _build(payload)


def test_terminal_verification_rejects_repair_producer() -> None:
    payload = _payload_for(OperationalActionKind.TERMINAL_VERIFICATION)
    with pytest.raises(ValueError, match="cannot be authored by a repair producer"):
        _build(payload, producer=_producer(ProducerRole.REPAIR_PRODUCER))
    # A distinct verifier principal is accepted.
    event = _build(payload, producer=_producer(ProducerRole.VERIFIER))
    assert event.payload.verifier.principal == "verifier-1"


def test_checkpoint_window_vocabulary_and_six_hour_alias() -> None:
    assert canonical_checkpoint_window("immediate") is CheckpointWindowKind.IMMEDIATE
    assert canonical_checkpoint_window("five_minute") is CheckpointWindowKind.FIVE_MINUTE
    assert canonical_checkpoint_window("one_hour") is CheckpointWindowKind.ONE_HOUR
    assert canonical_checkpoint_window("next_three_hour") is CheckpointWindowKind.NEXT_THREE_HOUR
    # Legacy six_hour is a READ alias for next_three_hour, never a separate
    # authority window.
    assert SIX_HOUR_ALIAS == "six_hour"
    assert canonical_checkpoint_window(SIX_HOUR_ALIAS) is CheckpointWindowKind.NEXT_THREE_HOUR
    with pytest.raises(ValueError, match="unknown checkpoint window"):
        canonical_checkpoint_window("four_hour")


# ---------------------------------------------------------------------------
# Maintenance never constructs owner authority records
# ---------------------------------------------------------------------------


def test_operational_modules_never_import_owner_authority_stores() -> None:
    root = Path(__file__).resolve().parents[3]
    for module in ("operations.py", "events.py"):
        source = (root / "arnold_pipelines/megaplan/maintenance" / module).read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        lowered = " ".join(imported).lower()
        for forbidden in _FORBIDDEN_OWNER_IMPORTS:
            assert forbidden not in lowered, (
                f"{module} imports an owner authority seam: {forbidden}"
            )
