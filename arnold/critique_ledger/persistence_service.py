"""Validated CL2 writes over the existing WBC attempt-ledger store.

CL1 domain records are payload content, not attempt lifecycle transitions.
Every record is therefore stored as an ``EXTERNAL_EFFECT_OUTCOME`` with a
``cl2_kind`` discriminator.  The unchanged attempt-ledger store remains the
authority for ordering, idempotency, and terminal-state enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.critique_ledger.schemas import (
    CritiqueOccurrenceEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
)
from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    AttemptReservation,
    GapEntry,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
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


CL2_KIND_OCCURRENCE = "occurrence"
CL2_KIND_RECONCILIATION = "reconciliation"
CL2_KIND_DISPOSITION = "disposition"

# ── Restart-reconciliation statuses ────────────────────────────────────────
#
# ``LedgerReconciliationResult.status`` is one of these literals.  The split is
# deliberate and matches the two distinct failure detectors:
#
# * ``ordering_violation`` is produced ONLY by ``validate_ledger_event_ordering``
#   (monotonicity, causal chain, append-position, lifecycle precedence).
# * ``sequence_gap`` is produced ONLY by ``store.query_gaps`` (non-contiguous
#   sequences).  ``validate_ledger_event_ordering`` uses a *strictly*
#   monotonic comparison and intentionally does NOT detect non-contiguous
#   gaps; ``query_gaps`` is the sole gap detector.
#
# Reconciliation results carry no authority: they are an observable
# projection of persisted state used to decide recovery, never to authorize.

RECONCILE_STATUS_COMPLETE = "complete"
RECONCILE_STATUS_PERSISTENCE_FAILED = "persistence_failed"
RECONCILE_STATUS_INDETERMINATE = "indeterminate"
RECONCILE_STATUS_ORDERING_VIOLATION = "ordering_violation"
RECONCILE_STATUS_SEQUENCE_GAP = "sequence_gap"

#: Terminal lifecycle event types (used to derive ``has_terminal``).
_TERMINAL_EVENT_TYPES = frozenset(
    {
        AttemptEventType.COMPLETED,
        AttemptEventType.FAILED,
        AttemptEventType.CANCELLED,
    }
)


class AttemptAlreadyTerminalError(RuntimeError):
    """Raised by ``start_attempt`` when the reservation is already terminal.

    A second lifecycle cannot begin over a terminal attempt; this is raised
    *before* any STARTED write so the terminal stream is never disturbed.
    """

    def __init__(self, attempt_id: str) -> None:
        super().__init__(
            f"Attempt {attempt_id!r} is already terminal; cannot start_attempt"
        )
        self.attempt_id = attempt_id


@dataclass(frozen=True)
class LedgerEventContext:
    """Immutable WBC metadata shared by an attempt's ledger events."""

    identity: AttemptIdentity
    provenance: AttemptProvenance
    adapter: RuntimeAdapter
    versions: VersionSet
    grant_ref: GrantRef
    occurred_at: str
    observed_at: str


@dataclass(frozen=True)
class LedgerReconciliationResult:
    """Typed restart-reconciliation classification for one attempt stream.

    A NEW type, deliberately distinct from the two existing
    ``ReconciliationResult`` dataclasses (the WBC effect-reconciliation result
    and the migration-reconciliation result).  This result is **evidence
    only** — it carries no authority, grant, or completion power; it is the
    observable projection consumed by a restart worker to decide recovery.

    Fields:
        attempt_id: the attempt stream classified.
        status: one of the ``RECONCILE_STATUS_*`` literals.  The split mirrors
            the two failure detectors: ``ordering_violation`` comes ONLY from
            :func:`validate_ledger_event_ordering`; ``sequence_gap`` comes ONLY
            from :meth:`SqliteAttemptLedgerStore.query_gaps`.
        issues: human-readable issue strings (ordering violations and/or gap
            descriptions).  Empty when ``status`` is ``complete``.
        event_snapshot: a stable, JSON-serializable snapshot of the persisted
            stream (keys: ``attempt_id``, ``is_reserved``, ``is_new``,
            ``reservation_count``, ``event_count``, ``last_sequence``,
            ``has_started``, ``has_terminal``, ``sequences``, ``event_types``).
    """

    attempt_id: str
    status: str
    issues: list[str]
    event_snapshot: dict[str, Any]


class LedgerEventMapper:
    """Pure mapping from validated CL1 records to WBC ledger events."""

    @staticmethod
    def _event(
        *,
        event_type: AttemptEventType,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
        payload: dict[str, Any],
        outcome: AttemptOutcome | None = None,
    ) -> LedgerEvent:
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
            payload=payload,
            outcome=outcome,
        )

    @staticmethod
    def _validated_payload(
        record: CritiqueOccurrenceEnvelope
        | FindingReconciliationEvent
        | FindingDispositionEvent,
        record_type: type[
            CritiqueOccurrenceEnvelope
            | FindingReconciliationEvent
            | FindingDispositionEvent
        ],
        cl2_kind: str,
    ) -> dict[str, Any]:
        if not isinstance(record, record_type):
            raise TypeError(
                f"Expected {record_type.__name__}, got {type(record).__name__}"
            )

        serialized = record.to_dict()
        # This is the CL1 schema/version gate.  Persist the reconstructed
        # representation so the bytes stored are exactly those validated.
        validated = record_type.from_dict(serialized)
        envelope = validated.to_dict()
        if envelope != serialized:
            raise ValueError(
                f"{record_type.__name__} changed during from_dict round-trip"
            )
        return {"cl2_kind": cl2_kind, "envelope": envelope}

    @classmethod
    def occurrence(
        cls,
        envelope: CritiqueOccurrenceEnvelope,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
    ) -> LedgerEvent:
        """Map one validated occurrence to an outcome payload."""
        return cls._event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload=cls._validated_payload(
                envelope, CritiqueOccurrenceEnvelope, CL2_KIND_OCCURRENCE
            ),
        )

    @classmethod
    def reconciliation(
        cls,
        event: FindingReconciliationEvent,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
    ) -> LedgerEvent:
        """Map a domain reconciliation to an outcome, not a lifecycle event."""
        return cls._event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload=cls._validated_payload(
                event, FindingReconciliationEvent, CL2_KIND_RECONCILIATION
            ),
        )

    @classmethod
    def disposition(
        cls,
        event: FindingDispositionEvent,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
    ) -> LedgerEvent:
        """Map a domain disposition to an outcome, not terminal completion."""
        return cls._event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload=cls._validated_payload(
                event, FindingDispositionEvent, CL2_KIND_DISPOSITION
            ),
        )

    @classmethod
    def intent(
        cls,
        intent_payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
    ) -> LedgerEvent:
        """Map the critic input/briefing reference to durable intent."""
        return cls._event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload={"cl2_kind": "critic_intent", "intent": dict(intent_payload)},
        )

    @classmethod
    def started(
        cls,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
    ) -> LedgerEvent:
        """Build a lifecycle STARTED event (no domain payload)."""
        return cls._event(
            event_type=AttemptEventType.STARTED,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload={},
        )

    @classmethod
    def terminal(
        cls,
        event_type: AttemptEventType,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
        sequence: int,
        outcome: AttemptOutcome,
    ) -> LedgerEvent:
        """Build a lifecycle terminal event carrying its outcome."""
        if event_type not in (
            AttemptEventType.COMPLETED,
            AttemptEventType.FAILED,
        ):
            raise ValueError(
                f"terminal() only maps COMPLETED/FAILED, got {event_type!r}"
            )
        # Outcome must be supplied at construction: LedgerEvent.__post_init__
        # requires terminal events to carry their outcome.
        return cls._event(
            event_type=event_type,
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
            payload={},
            outcome=outcome,
        )


class LedgerPersistenceService:
    """Sole validated CL2 write surface over ``SqliteAttemptLedgerStore``."""

    def __init__(
        self,
        store: SqliteAttemptLedgerStore,
        mapper: type[LedgerEventMapper] = LedgerEventMapper,
    ) -> None:
        self._store = store
        self._mapper = mapper

    def _next_sequence(self, attempt_id: str, context: LedgerEventContext) -> int:
        if context.identity.attempt_id != attempt_id:
            raise ValueError(
                f"Context attempt_id {context.identity.attempt_id!r} does not "
                f"match requested attempt_id {attempt_id!r}"
            )
        return self._store.last_sequence(attempt_id) + 1

    def record_intent(
        self,
        attempt_id: str,
        intent_payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        context: LedgerEventContext,
    ) -> AppendResult:
        event = self._mapper.intent(
            intent_payload,
            idempotency_key=idempotency_key,
            context=context,
            sequence=self._next_sequence(attempt_id, context),
        )
        return self._store.append_event(attempt_id, event)

    def persist_occurrence(
        self,
        attempt_id: str,
        envelope: CritiqueOccurrenceEnvelope,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
    ) -> AppendResult:
        if envelope.attempt_id != attempt_id:
            raise ValueError(
                f"Occurrence attempt_id {envelope.attempt_id!r} does not "
                f"match requested attempt_id {attempt_id!r}"
            )
        event = self._mapper.occurrence(
            envelope,
            idempotency_key=idempotency_key,
            context=context,
            sequence=self._next_sequence(attempt_id, context),
        )
        return self._store.append_event(attempt_id, event)

    def persist_reconciliation(
        self,
        attempt_id: str,
        reconciliation: FindingReconciliationEvent,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
    ) -> AppendResult:
        event = self._mapper.reconciliation(
            reconciliation,
            idempotency_key=idempotency_key,
            context=context,
            sequence=self._next_sequence(attempt_id, context),
        )
        return self._store.append_event(attempt_id, event)

    def persist_disposition(
        self,
        attempt_id: str,
        disposition: FindingDispositionEvent,
        *,
        idempotency_key: str,
        context: LedgerEventContext,
    ) -> AppendResult:
        event = self._mapper.disposition(
            disposition,
            idempotency_key=idempotency_key,
            context=context,
            sequence=self._next_sequence(attempt_id, context),
        )
        return self._store.append_event(attempt_id, event)

    def start_attempt(
        self,
        attempt_id: str,
        *,
        context: LedgerEventContext,
        idempotency_key: str,
    ) -> AttemptReservation:
        """Reserve ``attempt_id`` durably, then append the STARTED event.

        Reservation always precedes the STARTED append so a crash between the
        two is observable on restart (reserved-but-not-started).  An attempt
        that is *already terminal* is rejected before any STARTED write so a
        second lifecycle cannot begin.  Returns the durable pre-/post-start
        :class:`AttemptReservation` projection (evidence only — no authority).
        """
        reservation = self._store.reserve_attempt(attempt_id)
        if reservation.has_terminal:
            raise AttemptAlreadyTerminalError(attempt_id)
        # ``reservation.last_sequence`` is the durable high-water mark observed
        # before START; the STARTED event is the next contiguous sequence.
        sequence = reservation.last_sequence + 1
        started = self._mapper.started(
            idempotency_key=idempotency_key,
            context=context,
            sequence=sequence,
        )
        self._store.append_started(attempt_id, started)
        return reservation

    def complete_attempt(
        self,
        attempt_id: str,
        *,
        context: LedgerEventContext,
        idempotency_key: str,
        succeeded: bool = True,
    ) -> AppendResult:
        """Append exactly one terminal event (COMPLETED or FAILED).

        Routes through the public ``append_completed`` / ``append_failed``
        store methods, which enforce the exactly-one-terminal invariant:
        a second terminal with a new idempotency key raises
        :class:`PostTerminalAppendError`.
        """
        if succeeded:
            event = self._mapper.terminal(
                AttemptEventType.COMPLETED,
                idempotency_key=idempotency_key,
                context=context,
                sequence=self._next_sequence(attempt_id, context),
                outcome=AttemptOutcome.SUCCEEDED,
            )
            return self._store.append_completed(attempt_id, event)
        event = self._mapper.terminal(
            AttemptEventType.FAILED,
            idempotency_key=idempotency_key,
            context=context,
            sequence=self._next_sequence(attempt_id, context),
            outcome=AttemptOutcome.FAILED,
        )
        return self._store.append_failed(attempt_id, event)

    # ── restart reconciliation ───────────────────────────────────────────

    @staticmethod
    def _format_gap(gap: GapEntry) -> str:
        """Format the actually-missing sequence range.

        Per the ``GapEntry`` contract ``gap_start`` is the highest persisted
        sequence *before* the gap (it is NOT itself a missing sequence) and
        ``gap_end`` is the lowest persisted sequence *after* the gap (exclusive
        upper bound).  The actually-missing range is therefore
        ``gap_start+1`` through ``gap_end-1`` inclusive, e.g. for persisted
        sequences ``[1, 2, 4]`` the gap is ``gap_start=2, gap_end=4`` and the
        missing range renders as ``3..3``.
        """
        return f"gap {gap.gap_start + 1}..{gap.gap_end - 1} (missing {gap.missing_count})"

    def _event_snapshot(
        self,
        attempt_id: str,
        events: list[LedgerEvent],
        reservation: AttemptReservation | None,
    ) -> dict[str, Any]:
        """Build the stable, JSON-serializable persisted-stream snapshot."""
        has_started = any(
            event.event_type == AttemptEventType.STARTED for event in events
        )
        has_terminal = any(
            event.event_type in _TERMINAL_EVENT_TYPES for event in events
        )
        return {
            "attempt_id": attempt_id,
            "is_reserved": reservation is not None,
            "is_new": bool(reservation.is_new) if reservation is not None else True,
            "reservation_count": (
                reservation.reservation_count if reservation is not None else 0
            ),
            "event_count": len(events),
            "last_sequence": events[-1].sequence if events else 0,
            "has_started": has_started,
            "has_terminal": has_terminal,
            "sequences": [event.sequence for event in events],
            "event_types": [event.event_type.value for event in events],
        }

    def reconcile_on_restart(
        self, attempt_id: str
    ) -> LedgerReconciliationResult:
        """Classify one persisted attempt stream for restart recovery.

        Read-only.  Never reserves, appends, or authorizes.  The status is
        derived from two distinct detectors:

        * :func:`validate_ledger_event_ordering` — monotonicity, causal chain,
          append-position, and lifecycle-precedence violations
          (status ``ordering_violation``).  It uses a *strictly* monotonic
          comparison and deliberately does NOT detect non-contiguous gaps.
        * :meth:`SqliteAttemptLedgerStore.query_gaps` — non-contiguous
          sequence gaps (status ``sequence_gap``).

        Lifecycle classification (only reached when no ordering/gap defect is
        present):

        * reserved but no STARTED → ``persistence_failed`` (unstarted);
        * STARTED but no terminal → ``indeterminate`` (in-flight);
        * STARTED with exactly one terminal and no defects → ``complete``.
        """
        events = self._store.read_events(attempt_id)
        # ``get_reservation`` is read-only (never bumps reservation_count).
        reservation = self._store.get_reservation(attempt_id)
        snapshot = self._event_snapshot(attempt_id, events, reservation)

        issues: list[str] = []

        # (1) Ordering / monotonicity / causal / append-position / lifecycle
        #     issues — the ONLY thing validate_ledger_event_ordering is used
        #     for.  It does NOT detect non-contiguous gaps.
        ordering_issues = validate_ledger_event_ordering(events)
        issues.extend(ordering_issues)

        # (2) Non-contiguous sequence gaps — the ONLY thing query_gaps is used
        #     for.  The public append path always produces contiguous
        #     sequences, so a non-empty gap list indicates corruption.
        gaps = self._store.query_gaps(attempt_id)
        issues.extend(self._format_gap(gap) for gap in gaps)

        if ordering_issues:
            status = RECONCILE_STATUS_ORDERING_VIOLATION
        elif gaps:
            status = RECONCILE_STATUS_SEQUENCE_GAP
        elif reservation is None:
            # Nothing was ever reserved for this attempt: clean slate.
            status = RECONCILE_STATUS_COMPLETE
        elif not snapshot["has_started"]:
            # Reserved but no STARTED durable — start persistence failed.
            status = RECONCILE_STATUS_PERSISTENCE_FAILED
        elif not snapshot["has_terminal"]:
            # STARTED but no terminal — the attempt is still in flight.
            status = RECONCILE_STATUS_INDETERMINATE
        else:
            status = RECONCILE_STATUS_COMPLETE

        return LedgerReconciliationResult(
            attempt_id=attempt_id,
            status=status,
            issues=issues,
            event_snapshot=snapshot,
        )


__all__ = [
    "CL2_KIND_DISPOSITION",
    "CL2_KIND_OCCURRENCE",
    "CL2_KIND_RECONCILIATION",
    "AttemptAlreadyTerminalError",
    "LedgerEventContext",
    "LedgerEventMapper",
    "LedgerPersistenceService",
    "LedgerReconciliationResult",
    "RECONCILE_STATUS_COMPLETE",
    "RECONCILE_STATUS_INDETERMINATE",
    "RECONCILE_STATUS_ORDERING_VIOLATION",
    "RECONCILE_STATUS_PERSISTENCE_FAILED",
    "RECONCILE_STATUS_SEQUENCE_GAP",
]
