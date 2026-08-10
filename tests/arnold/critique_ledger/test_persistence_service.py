"""Contract tests for the CL2 validated persistence write surface."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace
from typing import Any

import pytest

from arnold.critique_ledger.persistence_service import (
    AttemptAlreadyTerminalError,
    CL2_KIND_DISPOSITION,
    CL2_KIND_OCCURRENCE,
    CL2_KIND_RECONCILIATION,
    LedgerEventContext,
    LedgerPersistenceService,
    LedgerReconciliationResult,
    RECONCILE_STATUS_COMPLETE,
    RECONCILE_STATUS_INDETERMINATE,
    RECONCILE_STATUS_ORDERING_VIOLATION,
    RECONCILE_STATUS_PERSISTENCE_FAILED,
    RECONCILE_STATUS_SEQUENCE_GAP,
)
from arnold.critique_ledger.schemas import (
    CritiqueOccurrenceEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
)
from arnold.workflow.attempt_ledger_store import (
    DivergentDuplicateError,
    DuplicateTerminalError,
    GapEntry,
    MissingStartEventError,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    RuntimeAdapter,
    VersionSet,
    validate_ledger_event_ordering,
)


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-test"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-06T00:00:00+00:00",
        observed_at="2026-08-06T00:00:01+00:00",
    )


def _lifecycle_event(
    context: LedgerEventContext,
    event_type: AttemptEventType,
    sequence: int,
    idempotency_key: str,
) -> LedgerEvent:
    outcome = None
    if event_type == AttemptEventType.COMPLETED:
        outcome = AttemptOutcome.SUCCEEDED
    elif event_type == AttemptEventType.FAILED:
        outcome = AttemptOutcome.FAILED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=context.identity,
        provenance=context.provenance,
        adapter=context.adapter,
        versions=context.versions,
        grant_ref=context.grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=sequence - 1,
        append_position=sequence - 1,
        occurred_at=context.occurred_at,
        observed_at=context.observed_at,
        outcome=outcome,
    )


@pytest.fixture
def ledger(tmp_path: Any) -> tuple[
    SqliteAttemptLedgerStore, LedgerPersistenceService, str, LedgerEventContext
]:
    store = SqliteAttemptLedgerStore(tmp_path / "cl2-ledger.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    return store, LedgerPersistenceService(store), attempt_id, context


def _start(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    context: LedgerEventContext,
) -> None:
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "start"),
    )


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def test_all_cl1_records_round_trip_as_outcome_payloads(ledger: Any) -> None:
    store, service, attempt_id, context = ledger
    occurrence = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-1",
        attempt_id=attempt_id,
        round_label="round-1",
        finding_id="finding-1",
        semantic_finding_id="semantic-1",
        producer_id="critic-1",
        model_id="model-1",
        metadata={"domain": "correctness"},
    )
    reconciliation = FindingReconciliationEvent(
        reconciliation_id="reconciliation-1",
        canonical_finding_id="finding-1",
        semantic_finding_id="semantic-1",
        occurrence_ids=("occ-1",),
        reason="evaluator supplied",
    )
    disposition = FindingDispositionEvent(
        disposition_id="disposition-1",
        semantic_finding_id="semantic-1",
        family="acted-on",
        severity="high",
        action_taken=True,
        accountable_scope="critic execution",
    )

    _start(store, attempt_id, context)
    service.record_intent(
        attempt_id,
        {"briefing_ref": "durable://briefing/1"},
        idempotency_key="intent",
        context=context,
    )
    service.persist_occurrence(
        attempt_id, occurrence, idempotency_key="occurrence", context=context
    )
    service.persist_reconciliation(
        attempt_id,
        reconciliation,
        idempotency_key="reconciliation",
        context=context,
    )
    service.persist_disposition(
        attempt_id, disposition, idempotency_key="disposition", context=context
    )
    store.append_completed(
        attempt_id,
        _lifecycle_event(
            context, AttemptEventType.COMPLETED, 6, "completed"
        ),
    )

    events = store.read_events(attempt_id)
    outcomes = [
        event
        for event in events
        if event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
    ]
    assert [event.payload["cl2_kind"] for event in outcomes] == [  # type: ignore[index]
        CL2_KIND_OCCURRENCE,
        CL2_KIND_RECONCILIATION,
        CL2_KIND_DISPOSITION,
    ]
    assert all(
        event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
        for event in outcomes
    )

    record_types = (
        CritiqueOccurrenceEnvelope,
        FindingReconciliationEvent,
        FindingDispositionEvent,
    )
    originals = (occurrence, reconciliation, disposition)
    for event, record_type, original in zip(outcomes, record_types, originals):
        assert isinstance(event.payload, dict)
        reconstructed = record_type.from_dict(event.payload["envelope"])
        assert _canonical(reconstructed.to_dict()) == _canonical(original.to_dict())


def test_outcome_without_prior_intent_is_rejected(ledger: Any) -> None:
    store, service, attempt_id, context = ledger
    _start(store, attempt_id, context)
    occurrence = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-no-intent", attempt_id=attempt_id
    )

    with pytest.raises(MissingStartEventError, match="external_effect_intent"):
        service.persist_occurrence(
            attempt_id,
            occurrence,
            idempotency_key="occ-no-intent",
            context=context,
        )

    assert store.event_count(attempt_id) == 1


def test_exact_retry_deduplicates_even_after_terminal(ledger: Any) -> None:
    store, service, attempt_id, context = ledger
    occurrence = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-retry", attempt_id=attempt_id
    )
    _start(store, attempt_id, context)
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    first = service.persist_occurrence(
        attempt_id, occurrence, idempotency_key="stable-occ", context=context
    )
    store.append_completed(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.COMPLETED, 4, "completed"),
    )

    retry = service.persist_occurrence(
        attempt_id, occurrence, idempotency_key="stable-occ", context=context
    )

    assert first.is_duplicate is False
    assert retry.is_duplicate is True
    assert retry.sequence == first.sequence == 3
    assert store.event_count(attempt_id) == 4


def test_divergent_duplicate_is_rejected_without_second_append(ledger: Any) -> None:
    store, service, attempt_id, context = ledger
    original = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-divergent",
        attempt_id=attempt_id,
        finding_id="finding-original",
    )
    _start(store, attempt_id, context)
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(
        attempt_id, original, idempotency_key="stable-occ", context=context
    )

    with pytest.raises(DivergentDuplicateError, match="divergent content"):
        service.persist_occurrence(
            attempt_id,
            replace(original, finding_id="finding-changed"),
            idempotency_key="stable-occ",
            context=context,
        )

    assert store.event_count(attempt_id) == 3


def test_terminal_guard_rejects_new_outcome_and_double_terminal(ledger: Any) -> None:
    store, service, attempt_id, context = ledger
    _start(store, attempt_id, context)
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    store.append_completed(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.COMPLETED, 3, "completed"),
    )

    with pytest.raises(PostTerminalAppendError):
        service.persist_disposition(
            attempt_id,
            FindingDispositionEvent(disposition_id="too-late"),
            idempotency_key="late-disposition",
            context=context,
        )
    with pytest.raises(DuplicateTerminalError):
        store.append_failed(
            attempt_id,
            _lifecycle_event(context, AttemptEventType.FAILED, 4, "failed"),
        )

    assert store.event_count(attempt_id) == 3


@pytest.mark.parametrize(
    ("record", "method_name"),
    [
        (
            CritiqueOccurrenceEnvelope(
                schema_version="cl.schema.v99", occurrence_id="future-occ"
            ),
            "persist_occurrence",
        ),
        (
            FindingReconciliationEvent(
                schema_version="cl.schema.v99", reconciliation_id="future-rec"
            ),
            "persist_reconciliation",
        ),
        (
            FindingDispositionEvent(
                schema_version="cl.schema.v99", disposition_id="future-disp"
            ),
            "persist_disposition",
        ),
    ],
)
def test_all_domain_writes_validate_via_v1_from_dict_round_trip(
    ledger: Any, record: Any, method_name: str
) -> None:
    store, service, attempt_id, context = ledger
    _start(store, attempt_id, context)
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    if isinstance(record, CritiqueOccurrenceEnvelope):
        record = replace(record, attempt_id=attempt_id)

    with pytest.raises(ValueError, match="Unsupported schema_version"):
        getattr(service, method_name)(
            attempt_id, record, idempotency_key="future", context=context
        )

    assert store.event_count(attempt_id) == 2


# ── T2: lifecycle reservation / STARTED / terminal ─────────────────────────


def test_start_attempt_reserves_durably_before_start(ledger: Any) -> None:
    """Reservation is durable and precedes the STARTED append.

    The returned AttemptReservation is the pre-start observable snapshot
    (event_count/last_sequence 0 before START), and the STARTED event lands
    on the next contiguous sequence.
    """
    store, service, attempt_id, context = ledger

    # Pre-start snapshot: the attempt is not yet observable in the event
    # stream, but the reservation is durable.
    reservation = service.start_attempt(
        attempt_id, context=context, idempotency_key="started"
    )

    assert reservation.attempt_id == attempt_id
    assert reservation.is_new is True
    # The reservation captured the pre-start state (0 events, sequence 0).
    assert reservation.event_count == 0
    assert reservation.last_sequence == 0
    assert reservation.has_terminal is False
    assert reservation.reservation_count == 1

    # Post-start counts: exactly one STARTED event persisted on sequence 1.
    assert store.event_count(attempt_id) == 1
    assert store.has_terminal_event(attempt_id) is False
    events = store.read_events(attempt_id)
    assert events[0].event_type == AttemptEventType.STARTED
    assert events[0].sequence == 1
    assert events[0].idempotency_key == "started"


def test_start_attempt_rejects_already_terminal_reservation(ledger: Any) -> None:
    """An already-terminal attempt cannot begin a second lifecycle.

    start_attempt raises BEFORE appending any STARTED event, so the terminal
    stream is never disturbed.
    """
    store, service, attempt_id, context = ledger
    service.start_attempt(
        attempt_id, context=context, idempotency_key="started"
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.complete_attempt(
        attempt_id, context=context, idempotency_key="completed"
    )
    pre_count = store.event_count(attempt_id)
    assert store.has_terminal_event(attempt_id) is True

    with pytest.raises(AttemptAlreadyTerminalError, match="already terminal"):
        service.start_attempt(
            attempt_id, context=context, idempotency_key="restart"
        )

    # No STARTED was appended: count unchanged, still exactly one terminal.
    assert store.event_count(attempt_id) == pre_count


def test_outcome_before_intent_is_rejected_after_start(ledger: Any) -> None:
    """An OUTCOME without a prior INTENT is rejected even after a clean start.

    Uses the lifecycle start_attempt entry point (not the raw store helper).
    """
    store, service, attempt_id, context = ledger
    service.start_attempt(
        attempt_id, context=context, idempotency_key="started"
    )
    occurrence = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-no-intent", attempt_id=attempt_id
    )

    with pytest.raises(MissingStartEventError, match="external_effect_intent"):
        service.persist_occurrence(
            attempt_id,
            occurrence,
            idempotency_key="occ-no-intent",
            context=context,
        )

    # Only STARTED survived — no half-written outcome.
    assert store.event_count(attempt_id) == 1


def test_complete_attempt_appends_exactly_one_terminal(ledger: Any) -> None:
    """complete_attempt routes through public store terminal methods and
    the exactly-one-terminal guard rejects double completion."""
    store, service, attempt_id, context = ledger
    service.start_attempt(
        attempt_id, context=context, idempotency_key="started"
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )

    completed = service.complete_attempt(
        attempt_id, context=context, idempotency_key="completed"
    )
    assert completed.is_duplicate is False
    assert completed.event.event_type == AttemptEventType.COMPLETED
    assert completed.event.outcome == AttemptOutcome.SUCCEEDED
    assert store.has_terminal_event(attempt_id) is True
    assert store.event_count(attempt_id) == 3

    # A second terminal with a new idempotency key is rejected by the store's
    # exactly-one-terminal guard (PostTerminalAppendError, which the store
    # raises as the DuplicateTerminalError lineage for second terminals).
    with pytest.raises(PostTerminalAppendError):
        service.complete_attempt(
            attempt_id, context=context, idempotency_key="second-completed"
        )

    # The double-completion left no extra event.
    assert store.event_count(attempt_id) == 3

    # Exact-retry of the same terminal idempotency key deduplicates (dedup
    # wins over post-terminal rejection) without raising.
    retry = service.complete_attempt(
        attempt_id, context=context, idempotency_key="completed"
    )
    assert retry.is_duplicate is True
    assert retry.sequence == completed.sequence
    assert store.event_count(attempt_id) == 3


def test_complete_attempt_failed_routes_through_append_failed(ledger: Any) -> None:
    """A FAILED completion uses append_failed and records the failed outcome."""
    store, service, attempt_id, context = ledger
    service.start_attempt(
        attempt_id, context=context, idempotency_key="started"
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )

    failed = service.complete_attempt(
        attempt_id, context=context, idempotency_key="failed", succeeded=False
    )
    assert failed.event.event_type == AttemptEventType.FAILED
    assert failed.event.outcome == AttemptOutcome.FAILED
    assert store.has_terminal_event(attempt_id) is True
    assert store.event_count(attempt_id) == 3


# ── T3: restart reconciliation ──────────────────────────────────────────────


def _make_event(
    context: LedgerEventContext,
    event_type: AttemptEventType,
    sequence: int,
    idempotency_key: str,
    *,
    causal_predecessor: int | None = None,
    append_position: int | None = None,
    payload: dict[str, Any] | None = None,
    outcome: AttemptOutcome | None = None,
) -> LedgerEvent:
    """Build a LedgerEvent with explicit causal/append fields.

    Defaults to the mapper convention (``causal_predecessor = sequence - 1``
    and ``append_position = sequence - 1``) but lets callers override both so
    a deliberately-gapped stream can keep a *valid* causal chain.
    """
    if causal_predecessor is None:
        causal_predecessor = sequence - 1
    if append_position is None:
        append_position = sequence - 1
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=context.identity,
        provenance=context.provenance,
        adapter=context.adapter,
        versions=context.versions,
        grant_ref=context.grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor,
        append_position=append_position,
        occurred_at=context.occurred_at,
        observed_at=context.observed_at,
        payload=payload if payload is not None else {},
        outcome=outcome,
    )


def _inject_event_directly(
    store: SqliteAttemptLedgerStore, attempt_id: str, event: LedgerEvent
) -> None:
    """Append an event via direct SQL, bypassing ``_append_tx`` invariants.

    Used only to inject corruption (sequence gaps / ordering violations) that
    the public append path can never produce.  The event is serialized exactly
    as the store serializes it so ``read_events`` round-trips it.
    """
    store.conn.execute(
        """
INSERT INTO attempt_events
    (attempt_id, sequence, idempotency_key, event_type, event_json, appended_at_ns)
VALUES (?, ?, ?, ?, ?, ?)
""",
        (
            attempt_id,
            event.sequence,
            event.idempotency_key,
            event.event_type.value,
            json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False),
            time.time_ns(),
        ),
    )
    store.conn.commit()


def test_reconcile_clean_completed_attempt_is_complete(ledger: Any) -> None:
    """A fully completed attempt with no defects reconciles to ``complete``."""
    store, service, attempt_id, context = ledger
    service.start_attempt(attempt_id, context=context, idempotency_key="started")
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(
        attempt_id,
        CritiqueOccurrenceEnvelope(occurrence_id="occ-1", attempt_id=attempt_id),
        idempotency_key="occ-1",
        context=context,
    )
    service.complete_attempt(
        attempt_id, context=context, idempotency_key="completed"
    )

    result = service.reconcile_on_restart(attempt_id)

    assert isinstance(result, LedgerReconciliationResult)
    assert result.attempt_id == attempt_id
    assert result.status == RECONCILE_STATUS_COMPLETE
    assert result.issues == []
    snap = result.event_snapshot
    assert snap["attempt_id"] == attempt_id
    assert snap["is_reserved"] is True
    assert snap["has_started"] is True
    assert snap["has_terminal"] is True
    assert snap["event_count"] == 4
    assert snap["last_sequence"] == 4
    assert snap["sequences"] == [1, 2, 3, 4]
    assert snap["event_types"] == [
        AttemptEventType.STARTED.value,
        AttemptEventType.EXTERNAL_EFFECT_INTENT.value,
        AttemptEventType.EXTERNAL_EFFECT_OUTCOME.value,
        AttemptEventType.COMPLETED.value,
    ]
    # Stable snapshot is JSON-serializable (no dataclass / enum leaks).
    json.dumps(snap)


def test_reconcile_reservation_only_is_persistence_failed(ledger: Any) -> None:
    """Reserved but no STARTED durable -> ``persistence_failed`` (unstarted)."""
    store, service, attempt_id, context = ledger
    # Reserve directly without appending STARTED (simulates a crash between
    # reserve_attempt and append_started).
    store.reserve_attempt(attempt_id)

    result = service.reconcile_on_restart(attempt_id)

    assert result.status == RECONCILE_STATUS_PERSISTENCE_FAILED
    assert result.issues == []
    assert result.event_snapshot["is_reserved"] is True
    assert result.event_snapshot["has_started"] is False
    assert result.event_snapshot["has_terminal"] is False
    assert result.event_snapshot["event_count"] == 0


def test_reconcile_in_flight_is_indeterminate(ledger: Any) -> None:
    """STARTED with outcomes but no terminal -> ``indeterminate`` (in-flight)."""
    store, service, attempt_id, context = ledger
    service.start_attempt(attempt_id, context=context, idempotency_key="started")
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(
        attempt_id,
        CritiqueOccurrenceEnvelope(occurrence_id="occ-flight", attempt_id=attempt_id),
        idempotency_key="occ-flight",
        context=context,
    )

    result = service.reconcile_on_restart(attempt_id)

    assert result.status == RECONCILE_STATUS_INDETERMINATE
    assert result.issues == []
    assert result.event_snapshot["has_started"] is True
    assert result.event_snapshot["has_terminal"] is False
    assert result.event_snapshot["event_count"] == 3


def test_reconcile_ordering_violation_from_lifecycle_precedence(
    ledger: Any,
) -> None:
    """An OUTCOME without a prior INTENT is an ordering (lifecycle) violation.

    The public append path rejects this, so the violation is injected via direct
    SQL.  ``validate_ledger_event_ordering`` flags the missing lifecycle
    predecessor; ``query_gaps`` reports no gap (sequences are contiguous).
    """
    store, service, attempt_id, context = ledger
    store.reserve_attempt(attempt_id)
    _inject_event_directly(
        store,
        attempt_id,
        _make_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    # OUTCOME at sequence 2 with NO prior INTENT -- lifecycle precedence break.
    _inject_event_directly(
        store,
        attempt_id,
        _make_event(
            context,
            AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            2,
            "outcome-no-intent",
            payload={"cl2_kind": "occurrence", "envelope": {}},
        ),
    )

    # Positive: the validator flags the lifecycle precedence issue.
    events = store.read_events(attempt_id)
    ordering_issues = validate_ledger_event_ordering(events)
    assert any("external_effect_intent" in issue for issue in ordering_issues)
    # No sequence gap (contiguous 1, 2).
    assert store.query_gaps(attempt_id) == []

    result = service.reconcile_on_restart(attempt_id)
    assert result.status == RECONCILE_STATUS_ORDERING_VIOLATION
    assert result.issues == ordering_issues
    assert all("gap" not in issue for issue in result.issues)


def test_reconcile_sequence_gap_uses_query_gaps_and_negative_validator(
    ledger: Any,
) -> None:
    """A non-contiguous gap is detected by ``query_gaps`` only.

    Inject sequences 1, 2, 4 via direct SQL with a *valid* causal chain
    (event at seq 4 references the persisted seq 2, not the missing seq 3).
    The negative assertion: ``validate_ledger_event_ordering`` returns an
    empty list because it only checks strict monotonicity, not contiguity.
    The positive assertion: ``query_gaps`` detects the missing sequence 3 and
    ``reconcile_on_restart`` surfaces ``sequence_gap`` with the actually-missing
    range ``gap_start+1..gap_end-1`` (here ``3..3``).
    """
    store, service, attempt_id, context = ledger
    store.reserve_attempt(attempt_id)
    _inject_event_directly(
        store,
        attempt_id,
        _make_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    _inject_event_directly(
        store,
        attempt_id,
        _make_event(
            context, AttemptEventType.EXTERNAL_EFFECT_INTENT, 2, "intent"
        ),
    )
    # Sequence 4 with causal_predecessor=2 (persisted) so the causal chain is
    # valid even though sequence 3 is missing -- this is the corruption the
    # monotonicity check cannot see.
    _inject_event_directly(
        store,
        attempt_id,
        _make_event(
            context,
            AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            4,
            "outcome-after-gap",
            causal_predecessor=2,
            append_position=3,
            payload={"cl2_kind": "occurrence", "envelope": {}},
        ),
    )

    events = store.read_events(attempt_id)

    # NEGATIVE: the ordering validator does NOT detect the non-contiguous gap.
    assert validate_ledger_event_ordering(events) == []

    # POSITIVE: query_gaps detects the missing sequence 3.
    gaps = store.query_gaps(attempt_id)
    assert gaps == [
        GapEntry(
            attempt_id=attempt_id,
            gap_start=2,
            gap_end=4,
            missing_count=1,
        )
    ]

    result = service.reconcile_on_restart(attempt_id)
    assert result.status == RECONCILE_STATUS_SEQUENCE_GAP
    # Actually-missing range formatted as gap_start+1..gap_end-1 (here 3..3).
    assert result.issues == ["gap 3..3 (missing 1)"]
