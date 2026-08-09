"""Durable cutover quiesce and in-flight attempt drain (CL5 Step 12b).

This module implements the quiesce half of the cutover. Quiesce is the
fail-closed transition from "admitting new attempts" to "cutover in
progress":

1. :func:`quiesce` atomically engages the durable ``cutover_in_progress``
   admission fence on the SQLite ledger store. From that moment on no NEW
   attempt stream may be admitted — the store rejects new reservations and
   the first event of any new stream with
   :class:`~arnold.workflow.attempt_ledger_store.CutoverInProgressError`.
   It then enumerates every in-flight attempt via
   :meth:`~arnold.workflow.attempt_ledger_store.AttemptLedgerStore.list_in_flight_attempts`
   and classifies each through the exhaustive drain map.

2. :func:`drain` waits for naturally-draining attempts to reach a terminal
   event within the timeout, then marks every remaining attempt
   ``INDETERMINATE`` (fail-closed) via the durable mark table.

The fence is persisted in the SQLite store's metadata so a crash during
cutover preserves the admission-closed state: reopening the database sees
the fence still set, continues to reject new admissions, and the surviving
in-flight set can be re-enumerated and drained.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from arnold.critique_ledger.cutover.drain_map import (
    DrainCategory,
    classify_drain,
    indeterminate_outcome,
)
from arnold.adapters.ledger_store_adapter import AttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    AttemptOutcome,
)

#: Default drain poll interval (seconds).
DEFAULT_POLL_INTERVAL_SECONDS: float = 0.05


@dataclass(frozen=True)
class InFlightAttempt:
    """A single enumerated in-flight attempt with its drain classification."""

    attempt_id: str
    last_event_type: AttemptEventType
    last_event_sequence: int
    drain_category: DrainCategory


@dataclass(frozen=True)
class QuiesceResult:
    """Result of :func:`quiesce`.

    ``cutover_in_progress`` is always ``True`` after a successful quiesce
    (the fence is now engaged). ``previously_in_progress`` records whether
    the fence was ALREADY engaged before this call, which lets a resuming
    caller (e.g. after a crash) detect that it is re-entering an in-progress
    cutover rather than starting a fresh one.
    """

    cutover_in_progress: bool
    previously_in_progress: bool
    in_flight: tuple[InFlightAttempt, ...]


@dataclass(frozen=True)
class IndeterminateMarkRecord:
    """An attempt that was marked ``INDETERMINATE`` by the drain."""

    attempt_id: str
    last_event_type: str
    last_event_sequence: int
    drain_category: str
    resolved_outcome: str


@dataclass(frozen=True)
class DrainResult:
    """Result of :func:`drain`.

    ``drained`` lists the attempt_ids that reached a natural terminal event
    within the timeout. ``marked_indeterminate`` lists the attempts that
    failed to drain and were durably resolved to ``INDETERMINATE``.
    ``timed_out`` is ``True`` when at least one attempt was still in-flight
    when the deadline elapsed.
    """

    drained: tuple[str, ...]
    marked_indeterminate: tuple[IndeterminateMarkRecord, ...]
    timed_out: bool


def _enumerate_in_flight(store: AttemptLedgerStore) -> list[InFlightAttempt]:
    """Enumerate and drain-classify every in-flight attempt.

    Re-reads each attempt's last event so the classification reflects the
    durable stream at enumeration time (not a stale cache).
    """
    result: list[InFlightAttempt] = []
    for attempt_id in store.list_in_flight_attempts():
        events = store.read_events(attempt_id)
        if not events:
            # No events yet — cannot be in-flight per the SQL filter (which
            # requires at least one event), but guard defensively.
            continue
        last_event = events[-1]
        result.append(
            InFlightAttempt(
                attempt_id=attempt_id,
                last_event_type=last_event.event_type,
                last_event_sequence=last_event.sequence,
                drain_category=classify_drain(last_event.event_type),
            )
        )
    return result


def quiesce(store: AttemptLedgerStore) -> QuiesceResult:
    """Engage the cutover admission fence and enumerate in-flight attempts.

    Atomically (in one durable metadata write) engages the
    ``cutover_in_progress`` fence, then enumerates every in-flight attempt
    via ``list_in_flight_attempts`` and classifies each through the
    exhaustive drain map. Once this returns, new admissions are rejected by
    the store; the returned in-flight set is what :func:`drain` will
    resolve.

    Idempotent: calling :func:`quiesce` again after a crash reports
    ``previously_in_progress=True`` and re-enumerates the surviving
    in-flight set.
    """
    previously = store.set_cutover_in_progress()
    in_flight = tuple(_enumerate_in_flight(store))
    return QuiesceResult(
        cutover_in_progress=True,
        previously_in_progress=previously,
        in_flight=in_flight,
    )


def drain(
    store: AttemptLedgerStore,
    timeout_seconds: float = 0.0,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> DrainResult:
    """Wait for draining attempts to terminate, then mark the rest ``INDETERMINATE``.

    Polls every in-flight attempt until each reaches a natural terminal event
    (``COMPLETED``/``FAILED``/``CANCELLED``) or the ``timeout_seconds``
    deadline elapses. Attempts that drain are reported in ``drained``. Every
    remaining attempt is durably marked ``INDETERMINATE`` (fail-closed) via
    :meth:`~arnold.workflow.attempt_ledger_store.AttemptLedgerStore.mark_attempt_indeterminate`,
    recording its last non-terminal event type and drain category so a
    post-cutover operator or reconciliation policy can inspect the resolution.

    An attempt whose last event type is fail-closed (e.g.
    ``PERSISTENCE_FAILED``) resolves to ``INDETERMINATE`` via the
    ``persistence_fail_closed`` drain category; every other non-terminal
    attempt resolves via the ``indeterminate`` category. Both resolve to the
    same ``INDETERMINATE`` outcome.

    ``clock`` and ``sleep`` are injectable for deterministic testing.
    """
    deadline = clock() + max(0.0, timeout_seconds)

    # Snapshot the in-flight set at drain entry.
    pending = {a.attempt_id: a for a in _enumerate_in_flight(store)}
    drained: list[str] = []

    while pending:
        for attempt_id in list(pending):
            if store.has_terminal_event(attempt_id):
                drained.append(attempt_id)
                del pending[attempt_id]
        if not pending:
            break
        if clock() >= deadline:
            break
        sleep(max(0.0, poll_interval_seconds))

    timed_out = bool(pending)

    # Mark every remaining attempt as INDETERMINATE (fail-closed). Re-read the
    # last event at mark time so the recorded classification is accurate even
    # if a non-terminal event landed during the drain window.
    marked: list[IndeterminateMarkRecord] = []
    for attempt_id in pending:
        events = store.read_events(attempt_id)
        if not events:
            continue
        # A terminal event may have landed between the last poll and now; if
        # so the attempt drained and must NOT be marked indeterminate.
        if store.has_terminal_event(attempt_id):
            drained.append(attempt_id)
            continue
        last_event = events[-1]
        category = classify_drain(last_event.event_type)
        outcome = indeterminate_outcome(last_event.event_type)
        # Defensive: only non-terminal categories reach here, so outcome is
        # always INDETERMINATE. Assert the fail-closed contract explicitly.
        assert outcome is AttemptOutcome.INDETERMINATE, (
            f"drain marked attempt {attempt_id!r} with non-indeterminate "
            f"outcome {outcome!r}; drain must be fail-closed."
        )
        store.mark_attempt_indeterminate(
            attempt_id=attempt_id,
            last_event_type=last_event.event_type.value,
            last_event_sequence=last_event.sequence,
            drain_category=category.value,
            resolved_outcome=outcome.value,
            mark_reason="cutover_drain_timeout",
        )
        marked.append(
            IndeterminateMarkRecord(
                attempt_id=attempt_id,
                last_event_type=last_event.event_type.value,
                last_event_sequence=last_event.sequence,
                drain_category=category.value,
                resolved_outcome=outcome.value,
            )
        )

    return DrainResult(
        drained=tuple(drained),
        marked_indeterminate=tuple(marked),
        timed_out=timed_out,
    )


__all__ = [
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DrainResult",
    "InFlightAttempt",
    "IndeterminateMarkRecord",
    "QuiesceResult",
    "drain",
    "quiesce",
]
