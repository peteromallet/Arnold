"""Typed canonical query facade over the ``AttemptLedgerStore``.

This module provides immutable WBC (Workflow Boundary Contract) query
envelopes that wrap the durable gate and query results from
:class:`AttemptLedgerStore` / :class:`SqliteAttemptLedgerStore`.  Each
envelope is a non-authoritative projection — it carries exact identity,
cursor, and evidence metadata but does NOT create or imply a second
authority store, bearer authorization object, or dispatch grant.

Envelope states
---------------

Every envelope carries a ``status`` drawn from :class:`GateStatus`:

* ``VERIFIED``    — durable evidence confirms the query condition.
* ``INCOMPLETE``  — no matching evidence exists yet (normal in-flight).
* ``INDETERMINATE`` — evidence is ambiguous or the query could not be
  completed (corrupt JSON, store error, schema drift).
* ``INCOHERENT``  — evidence contradicts the query contract (multiple
  rows where at most one is expected, etc.).

These are the same states used by :class:`StartGateResult`,
:class:`TerminalGateResult`, and the store's gate methods — the WBC
envelopes extend them with richer metadata without mutating semantics.

Metadata carried by every envelope
----------------------------------

Every envelope optionally captures:

* ``environment`` / ``session`` — runtime surface identifiers.
* ``chain`` — plan chain identifier (e.g. ``CHAIN-01``).
* ``plan_revision`` — manifest/topology revision.
* ``phase`` / ``task`` — megaplan phase or task label.
* ``attempt_id`` — the ledger attempt id being queried.
* ``boundary_id`` — the boundary contract id when scoped.
* ``ledger_sequence`` — the last durable sequence observed.
* ``content_digest`` — integrity digest of the returned evidence
  (sha256:…), computed over the canonical JSON of the inner result.
* ``evidence_ids`` — set of diagnostic/reconciliation evidence ids
  referenced in the result.
* ``source_cursor`` — the :class:`SourceCursor` position observed by
  the query caller (evidence-only; never authority).

Facade contract
---------------

:class:`WbcQueries` is a read-only query facade.  It delegates every
operation to the underlying :class:`AttemptLedgerStore`.  It never
writes, reserves, appends, or mints authority.  Callers that need
authority decisions must use the store's append/gate methods directly
and cross-reference the query envelopes as evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from arnold.workflow.attempt_ledger_store import (
    AttemptLedgerStore,
    GapEntry,
    GateStatus,
    SourceCursor,
    StartGateResult,
    TerminalGateResult,
)
from arnold.workflow.execution_attempt_ledger import (
    ExecutionAttemptLedger,
    LedgerEvent,
)

# ── WBC query schema version ───────────────────────────────────────────────

_WBC_QUERIES_SCHEMA: str = "arnold.workflow.wbc_queries.v1"


# ── Canonical JSON helper ──────────────────────────────────────────────────


def _canonical_json(obj: Any) -> bytes:
    """Serialize *obj* to canonical UTF-8 JSON (sorted keys, no trailing
    newline) for digest computation."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _compute_digest(json_bytes: bytes) -> str:
    """Return ``sha256:<hex>`` for the given canonical JSON bytes."""
    return "sha256:" + hashlib.sha256(json_bytes).hexdigest()


# ── Immutable WBC query envelopes ──────────────────────────────────────────


@dataclass(frozen=True)
class WbcStartEnvelope:
    """Canonical query result for a STARTED-gate query.

    Wraps a :class:`StartGateResult` with additional environment, cursor,
    and evidence metadata.  This is a non-authoritative projection — it
    does not grant dispatch or completion power.
    """

    status: GateStatus
    """Gate status from the durable store query."""

    started_event: Optional[LedgerEvent] = None
    """The verified STARTED event when ``status`` is ``VERIFIED``, else ``None``."""

    evidence: str = ""
    """Human-readable evidence string from the underlying gate result."""

    # ── metadata carried on every envelope ──────────────────────────────

    attempt_id: str = ""
    environment: Optional[str] = None
    session: Optional[str] = None
    chain: Optional[str] = None
    plan_revision: Optional[str] = None
    phase: Optional[str] = None
    task: Optional[str] = None
    boundary_id: Optional[str] = None
    ledger_sequence: int = 0
    content_digest: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()
    source_cursor: Optional[SourceCursor] = None

    @classmethod
    def from_gate_result(
        cls,
        gate: StartGateResult,
        *,
        attempt_id: str = "",
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        ledger_sequence: int = 0,
        evidence_ids: tuple[str, ...] = (),
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcStartEnvelope:
        """Construct an envelope from a raw :class:`StartGateResult`.

        When the gate is ``VERIFIED`` and ``started_event`` is present,
        the ``content_digest`` is computed over the event's canonical
        ``to_dict()`` representation.
        """
        content_digest: Optional[str] = None
        if gate.status == GateStatus.VERIFIED and gate.started_event is not None:
            content_digest = _compute_digest(
                _canonical_json(gate.started_event.to_dict())
            )

        return cls(
            status=gate.status,
            started_event=gate.started_event,
            evidence=gate.evidence,
            attempt_id=attempt_id or gate.attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            ledger_sequence=ledger_sequence,
            content_digest=content_digest,
            evidence_ids=evidence_ids,
            source_cursor=source_cursor,
        )


@dataclass(frozen=True)
class WbcTerminalEnvelope:
    """Canonical query result for a terminal-gate query.

    Wraps a :class:`TerminalGateResult` with additional environment,
    cursor, and evidence metadata.  Non-authoritative projection.
    """

    status: GateStatus
    terminal_event: Optional[LedgerEvent] = None
    evidence: str = ""

    attempt_id: str = ""
    environment: Optional[str] = None
    session: Optional[str] = None
    chain: Optional[str] = None
    plan_revision: Optional[str] = None
    phase: Optional[str] = None
    task: Optional[str] = None
    boundary_id: Optional[str] = None
    ledger_sequence: int = 0
    content_digest: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()
    source_cursor: Optional[SourceCursor] = None

    @classmethod
    def from_gate_result(
        cls,
        gate: TerminalGateResult,
        *,
        attempt_id: str = "",
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        ledger_sequence: int = 0,
        evidence_ids: tuple[str, ...] = (),
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcTerminalEnvelope:
        """Construct an envelope from a raw :class:`TerminalGateResult`."""
        content_digest: Optional[str] = None
        if gate.status == GateStatus.VERIFIED and gate.terminal_event is not None:
            content_digest = _compute_digest(
                _canonical_json(gate.terminal_event.to_dict())
            )

        return cls(
            status=gate.status,
            terminal_event=gate.terminal_event,
            evidence=gate.evidence,
            attempt_id=attempt_id or gate.attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            ledger_sequence=ledger_sequence,
            content_digest=content_digest,
            evidence_ids=evidence_ids,
            source_cursor=source_cursor,
        )


@dataclass(frozen=True)
class WbcLedgerEnvelope:
    """Canonical query result for a full-ledger read.

    Wraps the reconstructed :class:`ExecutionAttemptLedger` (or the raw
    event list) with metadata.  When the ledger cannot be safely
    reconstructed the ``status`` is set to ``INDETERMINATE`` or
    ``INCOHERENT`` rather than returning a partial ledger.
    """

    status: GateStatus
    ledger: Optional[ExecutionAttemptLedger] = None
    events: tuple[LedgerEvent, ...] = ()
    evidence: str = ""

    attempt_id: str = ""
    environment: Optional[str] = None
    session: Optional[str] = None
    chain: Optional[str] = None
    plan_revision: Optional[str] = None
    phase: Optional[str] = None
    task: Optional[str] = None
    boundary_id: Optional[str] = None
    ledger_sequence: int = 0
    content_digest: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()
    source_cursor: Optional[SourceCursor] = None

    @classmethod
    def from_ledger(
        cls,
        ledger: ExecutionAttemptLedger,
        *,
        attempt_id: str = "",
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcLedgerEnvelope:
        """Construct a ``VERIFIED`` envelope from a successfully read ledger."""
        events = ledger.events
        last_seq = events[-1].sequence if events else 0
        content_digest = _compute_digest(_canonical_json(ledger.to_dict()))

        return cls(
            status=GateStatus.VERIFIED,
            ledger=ledger,
            events=events,
            evidence=f"Ledger reconstructed with {len(events)} event(s).",
            attempt_id=attempt_id or ledger.attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            ledger_sequence=last_seq,
            content_digest=content_digest,
            source_cursor=source_cursor,
        )

    @classmethod
    def indeterminate(
        cls,
        attempt_id: str,
        reason: str,
        *,
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcLedgerEnvelope:
        """Construct an ``INDETERMINATE`` envelope when the store cannot be read."""
        return cls(
            status=GateStatus.INDETERMINATE,
            evidence=reason,
            attempt_id=attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            source_cursor=source_cursor,
        )

    @classmethod
    def incomplete(
        cls,
        attempt_id: str,
        *,
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcLedgerEnvelope:
        """Construct an ``INCOMPLETE`` envelope when the ledger is empty."""
        return cls(
            status=GateStatus.INCOMPLETE,
            evidence="No events found in durable store.",
            attempt_id=attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            source_cursor=source_cursor,
        )


@dataclass(frozen=True)
class WbcGapEnvelope:
    """Canonical query result for sequence-gap detection.

    Wraps the list of :class:`GapEntry` instances with metadata.
    """

    status: GateStatus
    gaps: tuple[GapEntry, ...] = ()
    evidence: str = ""

    attempt_id: str = ""
    environment: Optional[str] = None
    session: Optional[str] = None
    chain: Optional[str] = None
    plan_revision: Optional[str] = None
    phase: Optional[str] = None
    task: Optional[str] = None
    boundary_id: Optional[str] = None
    ledger_sequence: int = 0
    content_digest: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()
    source_cursor: Optional[SourceCursor] = None

    @classmethod
    def from_gaps(
        cls,
        gaps: list[GapEntry],
        attempt_id: str,
        *,
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        ledger_sequence: int = 0,
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcGapEnvelope:
        """Construct an envelope from a list of :class:`GapEntry` items."""
        gaps_tuple = tuple(gaps)
        if gaps_tuple:
            status = GateStatus.VERIFIED  # gaps are detected, not an error
            evidence = f"Found {len(gaps_tuple)} gap(s) in event stream."
        else:
            status = GateStatus.INCOMPLETE  # no gaps found = no gap evidence
            evidence = "No sequence gaps detected."

        content_digest: Optional[str] = None
        if gaps_tuple:
            gap_dicts = [
                {
                    "attempt_id": g.attempt_id,
                    "gap_start": g.gap_start,
                    "gap_end": g.gap_end,
                    "missing_count": g.missing_count,
                }
                for g in gaps_tuple
            ]
            content_digest = _compute_digest(_canonical_json(gap_dicts))

        return cls(
            status=status,
            gaps=gaps_tuple,
            evidence=evidence,
            attempt_id=attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            ledger_sequence=ledger_sequence,
            content_digest=content_digest,
            source_cursor=source_cursor,
        )

    @classmethod
    def indeterminate(
        cls,
        attempt_id: str,
        reason: str,
        *,
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
        source_cursor: Optional[SourceCursor] = None,
    ) -> WbcGapEnvelope:
        """Construct an ``INDETERMINATE`` envelope when gap query fails."""
        return cls(
            status=GateStatus.INDETERMINATE,
            evidence=reason,
            attempt_id=attempt_id,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            source_cursor=source_cursor,
        )


@dataclass(frozen=True)
class WbcSourceCursorEnvelope:
    """Canonical query result for a source-cursor read.

    Wraps the :class:`SourceCursor` (or its absence) with metadata.
    """

    status: GateStatus
    cursor: Optional[SourceCursor] = None
    evidence: str = ""

    attempt_id: str = ""
    cursor_key: str = "default"
    environment: Optional[str] = None
    session: Optional[str] = None
    chain: Optional[str] = None
    plan_revision: Optional[str] = None
    phase: Optional[str] = None
    task: Optional[str] = None
    boundary_id: Optional[str] = None
    ledger_sequence: int = 0
    content_digest: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()
    source_cursor: Optional[SourceCursor] = None

    @classmethod
    def from_cursor(
        cls,
        cursor: Optional[SourceCursor],
        attempt_id: str,
        cursor_key: str = "default",
        *,
        environment: Optional[str] = None,
        session: Optional[str] = None,
        chain: Optional[str] = None,
        plan_revision: Optional[str] = None,
        phase: Optional[str] = None,
        task: Optional[str] = None,
        boundary_id: Optional[str] = None,
    ) -> WbcSourceCursorEnvelope:
        """Construct an envelope from an optional :class:`SourceCursor`."""
        if cursor is not None:
            status = GateStatus.VERIFIED
            evidence = (
                f"Source cursor at sequence {cursor.last_sequence} "
                f"(updated at {cursor.updated_at_ns})."
            )
            content_digest = _compute_digest(
                _canonical_json(
                    {
                        "attempt_id": cursor.attempt_id,
                        "cursor_key": cursor.cursor_key,
                        "last_sequence": cursor.last_sequence,
                        "last_position": cursor.last_position,
                        "updated_at_ns": cursor.updated_at_ns,
                    }
                )
            )
            ledger_sequence = cursor.last_sequence
        else:
            status = GateStatus.INCOMPLETE
            evidence = "No source cursor recorded for this attempt."
            content_digest = None
            ledger_sequence = 0

        return cls(
            status=status,
            cursor=cursor,
            evidence=evidence,
            attempt_id=attempt_id,
            cursor_key=cursor_key,
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            boundary_id=boundary_id,
            ledger_sequence=ledger_sequence,
            content_digest=content_digest,
            source_cursor=cursor,
        )


# ── Facade: WbcQueries ─────────────────────────────────────────────────────


class WbcQueries:
    """Typed canonical query facade over an :class:`AttemptLedgerStore`.

    This facade is a **read-only projection**.  Every method delegates to
    the underlying store and wraps the result in a typed, immutable
    envelope carrying exact identity, cursor, and evidence metadata.

    It does NOT create a second authority store, bearer authorization
    object, or dispatch grant.  It does not write, reserve, append, or
    mint authority.  Callers that need authority decisions must use the
    store's append/gate methods directly and cross-reference these
    envelopes as evidence.

    *context* is an optional metadata dictionary whose keys populate the
    corresponding envelope fields (``environment``, ``session``, ``chain``,
    ``plan_revision``, ``phase``, ``task``, ``boundary_id``).  Callers
    should pass the relevant surface-level metadata so every envelope
    carries full traceability.
    """

    def __init__(
        self,
        store: AttemptLedgerStore,
        *,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        self._store = store
        self._context: dict[str, Any] = dict(context) if context else {}

    # ── context helpers ─────────────────────────────────────────────────

    def _ctx(self, **overrides: Any) -> dict[str, Any]:
        """Merge the stored context with per-call overrides."""
        merged = dict(self._context)
        merged.update({k: v for k, v in overrides.items() if v is not None})
        return merged

    @staticmethod
    def _ctx_str(ctx: dict[str, Any], key: str) -> Optional[str]:
        val = ctx.get(key)
        return str(val) if val is not None else None

    # ── gate queries ────────────────────────────────────────────────────

    def query_start_gate(
        self,
        attempt_id: str,
        **ctx_overrides: Any,
    ) -> WbcStartEnvelope:
        """Query the durable STARTED gate and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.start_verified`.
        """
        ctx = self._ctx(**ctx_overrides)
        raw = self._store.start_verified(attempt_id)
        source_cursor = self._read_source_cursor(attempt_id)

        # Gather evidence ids from the started event's identity if present.
        evidence_ids: tuple[str, ...] = ()
        if raw.status == GateStatus.VERIFIED and raw.started_event is not None:
            ev = raw.started_event
            ids: list[str] = [ev.idempotency_key]
            if ev.identity.attempt_id:
                ids.append(ev.identity.attempt_id)
            evidence_ids = tuple(ids)

        ledger_sequence = (
            raw.started_event.sequence
            if raw.status == GateStatus.VERIFIED and raw.started_event is not None
            else 0
        )

        return WbcStartEnvelope.from_gate_result(
            raw,
            attempt_id=attempt_id,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
            ledger_sequence=ledger_sequence,
            evidence_ids=evidence_ids,
            source_cursor=source_cursor,
        )

    def query_terminal_gate(
        self,
        attempt_id: str,
        **ctx_overrides: Any,
    ) -> WbcTerminalEnvelope:
        """Query the durable terminal gate and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.terminal_or_indeterminate_verified`.
        """
        ctx = self._ctx(**ctx_overrides)
        raw = self._store.terminal_or_indeterminate_verified(attempt_id)
        source_cursor = self._read_source_cursor(attempt_id)

        evidence_ids: tuple[str, ...] = ()
        if raw.status == GateStatus.VERIFIED and raw.terminal_event is not None:
            ev = raw.terminal_event
            ids: list[str] = [ev.idempotency_key]
            if ev.identity.attempt_id:
                ids.append(ev.identity.attempt_id)
            if ev.grant_ref.decision_id:
                ids.append(ev.grant_ref.decision_id)
            evidence_ids = tuple(ids)

        ledger_sequence = (
            raw.terminal_event.sequence
            if raw.status == GateStatus.VERIFIED and raw.terminal_event is not None
            else 0
        )

        return WbcTerminalEnvelope.from_gate_result(
            raw,
            attempt_id=attempt_id,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
            ledger_sequence=ledger_sequence,
            evidence_ids=evidence_ids,
            source_cursor=source_cursor,
        )

    # ── ledger queries ──────────────────────────────────────────────────

    def query_ledger(
        self,
        attempt_id: str,
        **ctx_overrides: Any,
    ) -> WbcLedgerEnvelope:
        """Read the full attempt ledger and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.read_ledger`.  Returns an
        ``INDETERMINATE`` envelope on any store error.
        """
        ctx = self._ctx(**ctx_overrides)
        source_cursor = self._read_source_cursor(attempt_id)

        try:
            ledger = self._store.read_ledger(attempt_id)
        except Exception as exc:
            return WbcLedgerEnvelope.indeterminate(
                attempt_id,
                f"Failed to read ledger: {exc}",
                environment=self._ctx_str(ctx, "environment"),
                session=self._ctx_str(ctx, "session"),
                chain=self._ctx_str(ctx, "chain"),
                plan_revision=self._ctx_str(ctx, "plan_revision"),
                phase=self._ctx_str(ctx, "phase"),
                task=self._ctx_str(ctx, "task"),
                boundary_id=self._ctx_str(ctx, "boundary_id"),
                source_cursor=source_cursor,
            )

        if ledger.is_empty:
            return WbcLedgerEnvelope.incomplete(
                attempt_id,
                environment=self._ctx_str(ctx, "environment"),
                session=self._ctx_str(ctx, "session"),
                chain=self._ctx_str(ctx, "chain"),
                plan_revision=self._ctx_str(ctx, "plan_revision"),
                phase=self._ctx_str(ctx, "phase"),
                task=self._ctx_str(ctx, "task"),
                boundary_id=self._ctx_str(ctx, "boundary_id"),
                source_cursor=source_cursor,
            )

        return WbcLedgerEnvelope.from_ledger(
            ledger,
            attempt_id=attempt_id,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
            source_cursor=source_cursor,
        )

    def query_events(
        self,
        attempt_id: str,
        **ctx_overrides: Any,
    ) -> WbcLedgerEnvelope:
        """Read the raw event list and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.read_events`.  Returns an
        ``INDETERMINATE`` envelope on any store error.
        """
        ctx = self._ctx(**ctx_overrides)
        source_cursor = self._read_source_cursor(attempt_id)

        try:
            events = self._store.read_events(attempt_id)
        except Exception as exc:
            return WbcLedgerEnvelope.indeterminate(
                attempt_id,
                f"Failed to read events: {exc}",
                environment=self._ctx_str(ctx, "environment"),
                session=self._ctx_str(ctx, "session"),
                chain=self._ctx_str(ctx, "chain"),
                plan_revision=self._ctx_str(ctx, "plan_revision"),
                phase=self._ctx_str(ctx, "phase"),
                task=self._ctx_str(ctx, "task"),
                boundary_id=self._ctx_str(ctx, "boundary_id"),
                source_cursor=source_cursor,
            )

        if not events:
            return WbcLedgerEnvelope.incomplete(
                attempt_id,
                environment=self._ctx_str(ctx, "environment"),
                session=self._ctx_str(ctx, "session"),
                chain=self._ctx_str(ctx, "chain"),
                plan_revision=self._ctx_str(ctx, "plan_revision"),
                phase=self._ctx_str(ctx, "phase"),
                task=self._ctx_str(ctx, "task"),
                boundary_id=self._ctx_str(ctx, "boundary_id"),
                source_cursor=source_cursor,
            )

        # Construct an ExecutionAttemptLedger for the from_ledger path.
        from arnold.workflow.execution_attempt_ledger import (
            LEDGER_SCHEMA_VERSION,
        )

        ledger = ExecutionAttemptLedger(
            attempt_id=attempt_id,
            events=tuple(events),
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
        )
        return WbcLedgerEnvelope.from_ledger(
            ledger,
            attempt_id=attempt_id,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
            source_cursor=source_cursor,
        )

    # ── gap queries ─────────────────────────────────────────────────────

    def query_gaps(
        self,
        attempt_id: str,
        **ctx_overrides: Any,
    ) -> WbcGapEnvelope:
        """Detect sequence gaps and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.query_gaps`.
        """
        ctx = self._ctx(**ctx_overrides)
        source_cursor = self._read_source_cursor(attempt_id)

        try:
            gaps = self._store.query_gaps(attempt_id)
        except Exception as exc:
            return WbcGapEnvelope.indeterminate(
                attempt_id,
                f"Failed to query gaps: {exc}",
                environment=self._ctx_str(ctx, "environment"),
                session=self._ctx_str(ctx, "session"),
                chain=self._ctx_str(ctx, "chain"),
                plan_revision=self._ctx_str(ctx, "plan_revision"),
                phase=self._ctx_str(ctx, "phase"),
                task=self._ctx_str(ctx, "task"),
                boundary_id=self._ctx_str(ctx, "boundary_id"),
                source_cursor=source_cursor,
            )

        # Determine ledger_sequence from the max persisted sequence.
        try:
            ledger_sequence = self._store.last_sequence(attempt_id)
        except Exception:
            ledger_sequence = 0

        return WbcGapEnvelope.from_gaps(
            gaps,
            attempt_id,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
            ledger_sequence=ledger_sequence,
            source_cursor=source_cursor,
        )

    # ── source cursor queries ───────────────────────────────────────────

    def query_source_cursor(
        self,
        attempt_id: str,
        cursor_key: str = "default",
        **ctx_overrides: Any,
    ) -> WbcSourceCursorEnvelope:
        """Read the source cursor and return an enriched envelope.

        Delegates to :meth:`AttemptLedgerStore.query_source_cursor`.
        """
        ctx = self._ctx(**ctx_overrides)

        try:
            cursor = self._store.query_source_cursor(attempt_id, cursor_key)
        except Exception:
            cursor = None

        return WbcSourceCursorEnvelope.from_cursor(
            cursor,
            attempt_id,
            cursor_key=cursor_key,
            environment=self._ctx_str(ctx, "environment"),
            session=self._ctx_str(ctx, "session"),
            chain=self._ctx_str(ctx, "chain"),
            plan_revision=self._ctx_str(ctx, "plan_revision"),
            phase=self._ctx_str(ctx, "phase"),
            task=self._ctx_str(ctx, "task"),
            boundary_id=self._ctx_str(ctx, "boundary_id"),
        )

    # ── diagnostic queries ──────────────────────────────────────────────

    def query_persistence_diagnostics(
        self,
        attempt_id: str,
    ) -> list[Any]:
        """Read persistence-failure diagnostics (passthrough).

        Delegates to :meth:`AttemptLedgerStore.query_persistence_diagnostics`.
        Returns the raw diagnostic list — callers that need enriched
        metadata should wrap in their own evidence envelope.
        """
        try:
            return self._store.query_persistence_diagnostics(attempt_id)
        except Exception:
            return []

    def query_reconciliation_state(
        self,
        attempt_id: str,
    ) -> list[Any]:
        """Read reconciliation diagnostics (passthrough).

        Delegates to :meth:`AttemptLedgerStore.query_reconciliation_state`.
        """
        try:
            return self._store.query_reconciliation_state(attempt_id)
        except Exception:
            return []

    # ── internal helpers ────────────────────────────────────────────────

    def _read_source_cursor(
        self, attempt_id: str, cursor_key: str = "default"
    ) -> Optional[SourceCursor]:
        """Best-effort source cursor read; never raises."""
        try:
            return self._store.query_source_cursor(attempt_id, cursor_key)
        except Exception:
            return None


# ── Public API surface ─────────────────────────────────────────────────────

__all__ = [
    "WbcGapEnvelope",
    "WbcLedgerEnvelope",
    "WbcQueries",
    "WbcSourceCursorEnvelope",
    "WbcStartEnvelope",
    "WbcTerminalEnvelope",
]
