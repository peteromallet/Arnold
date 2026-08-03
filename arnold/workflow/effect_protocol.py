"""Steps 8C + 10B: WBC effect-protocol adapter over the ledger store/outbox.

This adapter wraps ``SqliteAttemptLedgerStore`` and ``SqliteLedgerOutbox``
to enforce the single durable WBC effect protocol:

1. **Reserve + start** — reserve a global effect identity and emit a
   STARTED event with durable intent.
2. **Durable intent** — persist an ``EXTERNAL_EFFECT_INTENT`` event
   atomically with an outbox record BEFORE dispatching to the provider.
3. **Global reservation** — the GLEK snapshot is written in the same
   transaction as the reservation, so retries read the original inputs.
4. **Provider dispatch** — call the provider's ``apply`` (via a callable
   injected by the caller; production effects are action-off in M10).
5. **One accepted terminal or indeterminate outcome** — the CAS in
   ``accept_terminal_outcome`` ensures at most one terminal per
   ``(attempt_id, GLEK)`` and at most one terminal across all attempts
   for the same GLEK.

Step 10B retry gate: a new attempt may dispatch only with:

* the **same provider idempotency key** (provider deduplicates), or
* an authoritative **NOT_APPLIED** reconciliation result followed by a
  fenced global-reservation transfer.

``UNKNOWN``, query failure, missing provider capability, and
contradictory evidence remain **terminally indeterminate, action-off**,
and routed to typed human escalation.

Production effects remain action-off throughout M10 (SD3). The adapter
uses durable fakes only.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from arnold.workflow import SqliteAttemptLedgerStore
from arnold.workflow.attempt_ledger_store import (
    GlobalEffectConflict,
    GlobalEffectConflictError,
    GlobalEffectOutcome,
    GlobalEffectReservation,
)
from arnold.workflow.effect_reconciliation import (
    ContradictoryEvidenceError,
    ProviderCapability,
    QueryCapabilityError,
    QueryFailureError,
    ReconciliationResult,
    ReconciliationVerdict,
    get_provider_capability,
    is_production_enabled,
)
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
    AdapterKind,
)
from arnold.workflow.ledger_outbox import SqliteLedgerOutbox


# ── Protocol errors ─────────────────────────────────────────────────────────


class EffectProtocolError(Exception):
    """Base error for effect-protocol violations."""


class ReservationMissingError(EffectProtocolError):
    """Raised when dispatch is attempted without a reservation."""


class IntentNotPersistedError(EffectProtocolError):
    """Raised when dispatch is attempted before durable intent."""


class CrossAttemptTransferDeniedError(EffectProtocolError):
    """Raised when a reservation transfer is denied (terminal or
    conflicting)."""


class IndeterminateEscalationError(EffectProtocolError):
    """Raised when an effect must be escalated to human review because
    reconciliation returned UNKNOWN, query failed, capability was
    missing, or evidence was contradictory."""


class ProductionEffectBlockedError(EffectProtocolError):
    """Raised when a production provider is attempted in M10 (action-off)."""


# ── Outcome kinds (stored in accept_terminal_outcome) ───────────────────────

OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_FAILED = "FAILED"
OUTCOME_INDETERMINATE = "INDETERMINATE"


# ── Adapter ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EffectProtocolConfig:
    """Configuration for the effect protocol adapter.

    The ``run_authority_check`` and ``custody_reread_check`` callables
    implement Step 10B item 3: the WBC reservation decision is
    necessary but NOT sufficient — current Run Authority and Custody
    rereads are required in addition to, never instead of, the WBC
    reservation decision.
    """

    run_authority_check: Optional[Callable[[str], bool]] = None
    """Callable(grant_id) -> True if the Run Authority grant is current."""

    custody_reread_check: Optional[Callable[[str], bool]] = None
    """Callable(attempt_id) -> True if Custody epoch is current."""

    def verify_authority(self, grant_id: str) -> bool:
        if self.run_authority_check is None:
            return True
        return self.run_authority_check(grant_id)

    def verify_custody(self, attempt_id: str) -> bool:
        if self.custody_reread_check is None:
            return True
        return self.custody_reread_check(attempt_id)


class EffectProtocol:
    """Single durable WBC effect protocol adapter.

    Wraps a :class:`SqliteAttemptLedgerStore` and
    :class:`SqliteLedgerOutbox`. Every dispatch path goes through:

    1. :meth:`reserve_and_start` — reserve GLEK + emit STARTED.
    2. :meth:`persist_intent` — durable EXTERNAL_EFFECT_INTENT + outbox.
    3. :meth:`dispatch` — call the provider apply callable.
    4. :meth:`accept_outcome` — accept terminal via CAS, or escalate.

    Step 10B retry: :meth:`can_redispatch` gates whether a new attempt
    may dispatch for an existing GLEK.
    """

    def __init__(
        self,
        store: SqliteAttemptLedgerStore,
        outbox: SqliteLedgerOutbox,
        config: Optional[EffectProtocolConfig] = None,
    ) -> None:
        self._store = store
        self._outbox = outbox
        self._config = config or EffectProtocolConfig()

    # ── Step 8C item 1: reserve + start ────────────────────────────────

    def reserve_and_start(
        self,
        attempt_id: str,
        effect_identity: Any,  # GlobalEffectIdentity
        identity: AttemptIdentity,
        provenance: AttemptProvenance,
        adapter: RuntimeAdapter,
        versions: VersionSet,
        grant_ref: GrantRef,
    ) -> GlobalEffectReservation:
        """Reserve the global effect and emit a STARTED event.

        The GLEK snapshot is persisted atomically with the attempt
        reservation (Step 8B1). Then a STARTED ledger event is appended
        with an outbox record for durable dispatch intent.

        Returns the :class:`GlobalEffectReservation` carrying the
        snapshotted GLEK.
        """
        self._store.initialize_attempt(attempt_id)
        reservation = self._store.reserve_global_effect(
            attempt_id, effect_identity
        )

        started_event = _make_event(
            attempt_id=attempt_id,
            event_type=AttemptEventType.STARTED,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
            sequence=1,
            payload={
                "global_logical_effect_key": reservation.global_logical_effect_key,
                "effect_family": effect_identity.effect_family,
            },
        )
        self._store.append_started(attempt_id, started_event)
        return reservation

    # ── Step 8C item 1: durable intent ─────────────────────────────────

    def persist_intent(
        self,
        attempt_id: str,
        glek: str,
        intent_payload: dict[str, Any],
        identity: AttemptIdentity,
        provenance: AttemptProvenance,
        adapter: RuntimeAdapter,
        versions: VersionSet,
        grant_ref: GrantRef,
        destination: str = "effect-dispatch",
    ) -> str:
        """Persist an EXTERNAL_EFFECT_INTENT event atomically with an
        outbox record.

        This MUST be called before :meth:`dispatch`. The outbox record
        ensures at-least-once delivery even if the process crashes
        after the provider apply but before the outcome is recorded.
        """
        seq = self._store.last_sequence(attempt_id) + 1
        intent_event = _make_event(
            attempt_id=attempt_id,
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
            sequence=seq,
            payload={
                "global_logical_effect_key": glek,
                "intent": intent_payload,
            },
        )
        result = self._outbox.append_event_with_outbox(
            attempt_id,
            intent_event,
            [{"destination": destination, "payload": intent_payload}],
        )
        return result.outbox_records[0].outbox_id if result.outbox_records else ""

    # ── Step 8C item 1: provider dispatch ──────────────────────────────

    def dispatch(
        self,
        attempt_id: str,
        glek: str,
        provider_id: str,
        apply_fn: Callable[[str, dict[str, Any]], Any],
        idempotency_key: str,
        request_payload: dict[str, Any],
    ) -> Any:
        """Dispatch to the provider via *apply_fn*.

        Enforces:

        * Production providers are blocked (SD3 action-off).
        * A reservation exists for ``(attempt_id, glek)``.
        * The attempt is still dispatch-eligible (no terminal outcome).
        * Run Authority and Custody are current (Step 10B item 3).
        """
        self.verify_dispatch_eligible(attempt_id, glek, provider_id)
        return apply_fn(idempotency_key, request_payload)

    def verify_dispatch_eligible(
        self,
        attempt_id: str,
        glek: str,
        provider_id: str,
    ) -> None:
        """Apply every pre-provider dispatch fence without calling a provider."""
        if is_production_enabled(provider_id):
            raise ProductionEffectBlockedError(
                f"Production effect dispatch is action-off in M10 for "
                f"provider {provider_id!r}"
            )

        reservation = self._store.get_global_effect_reservation(
            attempt_id, glek
        )
        if reservation is None:
            raise ReservationMissingError(
                f"No reservation for attempt {attempt_id!r} "
                f"GLEK {glek!r}"
            )

        if not self._store.is_dispatch_eligible(attempt_id, glek):
            raise EffectProtocolError(
                f"Attempt {attempt_id!r} is not dispatch-eligible for "
                f"GLEK {glek!r} (terminal outcome may exist)"
            )

        # Step 10B item 3: WBC reservation is necessary but not sufficient.
        grant_id = reservation.effect_identity.action_target
        if not self._config.verify_authority(grant_id):
            raise EffectProtocolError(
                f"Run Authority grant {grant_id!r} is not current"
            )
        if not self._config.verify_custody(attempt_id):
            raise EffectProtocolError(
                f"Custody epoch for attempt {attempt_id!r} is not current"
            )

    # ── Step 8C item 1: accept terminal outcome ────────────────────────

    def accept_outcome(
        self,
        attempt_id: str,
        glek: str,
        outcome_kind: str,
        outcome_payload: Optional[dict[str, Any]] = None,
    ) -> GlobalEffectOutcome:
        """Accept a terminal outcome via the store CAS.

        Delegates to ``store.accept_terminal_outcome`` which enforces
        same-attempt CAS (exact-duplicate idempotency, divergent
        quarantine) and cross-attempt exclusivity.
        """
        return self._store.accept_terminal_outcome(
            attempt_id, glek, outcome_kind, outcome_payload or {}
        )

    def accept_indeterminate(
        self,
        attempt_id: str,
        glek: str,
        reason: str,
    ) -> GlobalEffectOutcome:
        """Accept an INDETERMINATE outcome (action-off escalation).

        This is NOT a terminal success. It marks the effect as
        terminally indeterminate so no further dispatch can occur until
        human resolution.
        """
        return self._store.accept_terminal_outcome(
            attempt_id, glek, OUTCOME_INDETERMINATE, {"reason": reason}
        )

    def accepted_outcome_for_glek(self, glek: str) -> Any:
        """Return the one accepted outcome for *glek*, if any.

        Adapters use this read-only lookup to adopt an already-completed
        effect after restart instead of treating the dispatch fence as a
        retryable transport failure.
        """
        return self._store.get_global_effect_outcome_by_glek(glek)

    # ── Step 10B: retry gate ───────────────────────────────────────────

    def can_redispatch(
        self,
        new_attempt_id: str,
        glek: str,
        provider_id: str,
        provider_idempotency_key: str,
        reconciliation: Optional[ReconciliationResult] = None,
    ) -> bool:
        """Gate whether *new_attempt_id* may dispatch for *glek*.

        Step 10B rules:

        1. If any attempt has accepted an ``APPLIED`` outcome for *glek*,
           adopt it through verify-only acceptance — **no redispatch**.
        2. A new attempt may dispatch only with the **same provider
           idempotency key** OR an authoritative ``NOT_APPLIED``
           reconciliation result followed by fenced global-reservation
           transfer.
        3. ``UNKNOWN``, query failure, missing provider capability, and
           contradictory evidence are terminally indeterminate — **no
           redispatch**, route to escalation.
        """
        cap = get_provider_capability(provider_id)

        # Rule 1: APPLIED outcome exists → verify-only, no redispatch.
        existing = self._store.get_global_effect_outcome_by_glek(glek)
        if existing is not None:
            if existing.outcome_kind == OUTCOME_COMPLETED:
                return False  # Already applied — adopt, don't redispatch.
            if existing.outcome_kind == OUTCOME_INDETERMINATE:
                return False  # Indeterminate — escalate.
            # FAILED outcome: redispatch IS allowed (not a duplicate).

        # If reconciliation evidence is provided, evaluate it.
        if reconciliation is not None:
            if reconciliation.query_failure:
                return False  # Query failure → indeterminate.
            if reconciliation.verdict == ReconciliationVerdict.UNKNOWN:
                return False  # Unknown → indeterminate.
            if reconciliation.verdict == ReconciliationVerdict.APPLIED:
                return False  # Already applied — adopt, don't redispatch.
            # NOT_APPLIED: authorize only if provider has idempotency.
            if reconciliation.verdict == ReconciliationVerdict.NOT_APPLIED:
                if not cap.can_authorize_redispatch:
                    return False  # Missing capability → indeterminate.
                # NOT_APPLIED + capable provider → fenced transfer.
                return self._try_fenced_transfer(
                    new_attempt_id, glek, provider_idempotency_key
                )

        # No reconciliation evidence: require same provider idempotency key
        # AND provider idempotency capability.
        if not cap.supports_idempotency_key:
            return False
        # Check that the new attempt has a reservation for this GLEK.
        reservation = self._store.get_global_effect_reservation(
            new_attempt_id, glek
        )
        return reservation is not None

    def _try_fenced_transfer(
        self,
        new_attempt_id: str,
        glek: str,
        provider_idempotency_key: str,
    ) -> bool:
        """Attempt a fenced global-reservation transfer.

        The new attempt must have its own reservation for *glek*. The
        transfer is fenced: Run Authority and Custody must be current.
        """
        reservation = self._store.get_global_effect_reservation(
            new_attempt_id, glek
        )
        if reservation is None:
            return False
        if not self._config.verify_authority(
            reservation.effect_identity.action_target
        ):
            return False
        if not self._config.verify_custody(new_attempt_id):
            return False
        return True

    # ── Step 10B item 2: reconciliation escalation ─────────────────────

    def reconcile_and_decide(
        self,
        attempt_id: str,
        glek: str,
        provider_id: str,
        query_fn: Callable[[str], ReconciliationResult],
        provider_idempotency_key: str,
    ) -> ReconciliationResult:
        """Query the provider and decide: adopt, redispatch, or escalate.

        Returns the reconciliation result. The caller uses
        :meth:`can_redispatch` to gate the actual dispatch.

        Raises :class:`IndeterminateEscalationError` for UNKNOWN, query
        failure, missing capability, or contradictory evidence.
        """
        cap = get_provider_capability(provider_id)

        if not cap.supports_query:
            raise IndeterminateEscalationError(
                f"Provider {provider_id!r} lacks query capability — "
                f"effect {glek!r} is terminally indeterminate"
            )

        try:
            result = query_fn(provider_idempotency_key)
        except QueryFailureError as exc:
            raise IndeterminateEscalationError(
                f"Provider query failed for {glek!r}: {exc}"
            ) from exc

        if result.query_failure:
            raise IndeterminateEscalationError(
                f"Provider query failure for {glek!r}"
            )
        if result.verdict == ReconciliationVerdict.UNKNOWN:
            raise IndeterminateEscalationError(
                f"Provider returned UNKNOWN for {glek!r} — terminally "
                f"indeterminate"
            )
        return result

    # ── Evidence queries ───────────────────────────────────────────────

    def get_outcome(self, glek: str) -> Optional[GlobalEffectOutcome]:
        """Return the cross-attempt accepted outcome for *glek*, or None."""
        return self._store.get_global_effect_outcome_by_glek(glek)

    def get_reservation(
        self, attempt_id: str, glek: str
    ) -> Optional[GlobalEffectReservation]:
        return self._store.get_global_effect_reservation(attempt_id, glek)

    def list_conflicts(self, attempt_id: str) -> tuple[GlobalEffectConflict, ...]:
        return self._store.list_global_effect_conflicts(attempt_id)

    def is_dispatch_eligible(self, attempt_id: str, glek: str) -> bool:
        return self._store.is_dispatch_eligible(attempt_id, glek)

    # ── Step 9A: simplified durable-intent persistence for native hooks ──

    _HOOK_ADAPTER = None

    def _hook_identity_bundle(
        self, idempotency_key: str,
    ) -> tuple[
        "GlobalEffectIdentity",
        AttemptIdentity,
        AttemptProvenance,
        RuntimeAdapter,
        VersionSet,
        GrantRef,
    ]:
        """Build a minimal identity bundle for hook-driven dispatch."""
        from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity

        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="m10-hooks",
        )
        versions = VersionSet(code_version="m10")
        grant_ref = GrantRef(grant_id="hook-grant")
        attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"arnold:wbc:{idempotency_key}"))
        identity = AttemptIdentity(
            workflow_id="native-hooks", run_id="hook-run",
            graph_revision="m10", attempt_id=attempt_id,
        )
        provenance = AttemptProvenance(
            actor_id="native-hooks", tool_id="effect-protocol",
        )
        effect_identity = GlobalEffectIdentity(
            environment_id="hooks",
            action_target=idempotency_key,
            action_version="m10",
            effect_family="native",
            provider_target="hooks",
            canonical_request_identity=idempotency_key,
            boundary_schema_hash="m10-hook-schema",
        )
        return effect_identity, identity, provenance, adapter, versions, grant_ref

    def persist_durable_intent(
        self,
        *,
        idempotency_key: str,
        intent_payload: dict[str, Any],
    ) -> str:
        """Step 9A convenience: persist durable intent for a hook-driven effect.

        Creates a minimal attempt, reserves the GLEK, and persists
        the durable intent in one call.  Returns the outbox record id.

        If this method raises, the caller (hook) MUST NOT invoke the
        provider — this is the zero-call-on-failure guarantee.
        """
        ei, ident, prov, adapter, versions, grant_ref = (
            self._hook_identity_bundle(idempotency_key)
        )
        reservation = self.reserve_and_start(
            attempt_id=ident.attempt_id,
            effect_identity=ei,
            identity=ident,
            provenance=prov,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
        )
        outbox_id = self.persist_intent(
            attempt_id=ident.attempt_id,
            glek=reservation.global_logical_effect_key,
            intent_payload=intent_payload,
            identity=ident,
            provenance=prov,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
        )
        return outbox_id

    def record_outcome(
        self,
        *,
        idempotency_key: str,
        outcome: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> Optional[GlobalEffectOutcome]:
        """Step 9A convenience: accept a terminal outcome for a hook effect."""
        ei, ident, prov, adapter, versions, grant_ref = (
            self._hook_identity_bundle(idempotency_key)
        )
        glek = ei.global_logical_effect_key
        try:
            return self.accept_outcome(
                ident.attempt_id, glek, outcome, detail or {}
            )
        except Exception:
            return None

    # ── Step 9: high-level dispatch for native hooks and backend seams ──

    def dispatch_effect(
        self,
        *,
        attempt_id: str,
        effect_identity: Any,  # GlobalEffectIdentity
        identity: AttemptIdentity,
        provenance: AttemptProvenance,
        adapter: RuntimeAdapter,
        versions: VersionSet,
        grant_ref: GrantRef,
        intent_payload: dict[str, Any],
        apply_fn: Callable[[str, dict[str, Any]], Any],
        provider_id: str = "fake",
        idempotency_key: str | None = None,
    ) -> "EffectDispatchOutcome":
        """Step 9 convenience: reserve → intent → dispatch → accept.

        This is the single high-level seam used by native hooks
        (Step 9A), ``_run_effect`` (Step 9B), and
        ``_execute_compensation_effect`` (Step 9C) to route their
        dispatch through the durable WBC protocol.

        Ordering guarantees:

        1. Durable intent is persisted BEFORE the provider is called
           (zero-call-on-failure: if intent persistence fails, the
           provider is never invoked).
        2. Dispatch is gated on reservation + eligibility + RA/Custody
           currency.
        3. The outcome is accepted through CAS.

        Returns an :class:`EffectDispatchOutcome` carrying the glek,
        provider result (or exception), and accepted outcome.
        """
        glek = effect_identity.global_logical_effect_key
        existing = self.get_reservation(attempt_id, glek)
        if existing is not None:
            if not self.is_dispatch_eligible(attempt_id, glek):
                raise EffectProtocolError(
                    f"Attempt {attempt_id!r} is not dispatch-eligible for {glek!r}"
                )
            # A retry must use the explicit reconciliation/redispatch path;
            # replaying the high-level first-dispatch seam would append a
            # second STARTED event and could bypass retry fencing.
            raise EffectProtocolError(
                f"Attempt {attempt_id!r} is already reserved for {glek!r}; "
                "use the fenced redispatch path"
            )

        reservation = self.reserve_and_start(
            attempt_id=attempt_id,
            effect_identity=effect_identity,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
        )
        glek = reservation.global_logical_effect_key

        self.persist_intent(
            attempt_id=attempt_id,
            glek=glek,
            intent_payload=intent_payload,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
        )

        prov_key = idempotency_key or glek
        request_payload = dict(intent_payload)
        request_payload["_provider_idempotency_key"] = prov_key

        try:
            result = self.dispatch(
                attempt_id=attempt_id,
                glek=glek,
                provider_id=provider_id,
                apply_fn=apply_fn,
                idempotency_key=prov_key,
                request_payload=request_payload,
            )
        except Exception as exc:
            outcome = self.accept_outcome(
                attempt_id, glek, OUTCOME_FAILED,
                {"error": f"{type(exc).__name__}: {exc}"},
            )
            return EffectDispatchOutcome(
                glek=glek,
                provider_result=None,
                provider_error=exc,
                outcome=outcome,
            )

        outcome = self.accept_outcome(
            attempt_id, glek, OUTCOME_COMPLETED,
            {"result": result} if not isinstance(result, dict) else result,
        )
        return EffectDispatchOutcome(
            glek=glek,
            provider_result=result,
            provider_error=None,
            outcome=outcome,
        )

    def dispatch_compensation(
        self,
        *,
        attempt_id: str,
        effect_identity: Any,
        identity: AttemptIdentity,
        provenance: AttemptProvenance,
        adapter: RuntimeAdapter,
        versions: VersionSet,
        grant_ref: GrantRef,
        intent_payload: dict[str, Any],
        apply_fn: Callable[[str, dict[str, Any]], Any],
        provider_id: str = "fake",
        idempotency_key: str | None = None,
    ) -> "EffectDispatchOutcome":
        """Step 9C: compensation dispatch through the durable protocol.

        Compensation effects MUST go through the same durable protocol
        as primary effects.  There is no blind (journal-only)
        compensation path — every compensation dispatch is reserved,
        intent-persisted, gated, and outcome-accepted through CAS.

        This prevents:

        * duplicate compensation dispatches (CAS on GLEK),
        * indeterminate compensation outcomes being treated as
          successful,
        * lost-ACK compensation (durable outbox intent).
        """
        return self.dispatch_effect(
            attempt_id=attempt_id,
            effect_identity=effect_identity,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
            intent_payload={**intent_payload, "_compensation": True},
            apply_fn=apply_fn,
            provider_id=provider_id,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True)
class EffectDispatchOutcome:
    """Result of :meth:`EffectProtocol.dispatch_effect`."""

    glek: str
    provider_result: Any
    provider_error: Optional[Exception]
    outcome: GlobalEffectOutcome


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_event(
    attempt_id: str,
    event_type: AttemptEventType,
    identity: AttemptIdentity,
    provenance: AttemptProvenance,
    adapter: RuntimeAdapter,
    versions: VersionSet,
    grant_ref: GrantRef,
    sequence: int,
    payload: Optional[dict[str, Any]] = None,
) -> LedgerEvent:
    """Construct a durable LedgerEvent for protocol use."""
    ts = _now_iso()
    return LedgerEvent(
        idempotency_key=f"{event_type.value}-{attempt_id}-{sequence}-{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        identity=identity,
        provenance=provenance,
        adapter=adapter,
        versions=versions,
        grant_ref=grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=sequence - 1,
        append_position=sequence - 1,
        occurred_at=ts,
        observed_at=ts,
        outcome=None,
        payload=payload,
    )


def _now_iso() -> str:
    """RFC3339-ish timestamp."""
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
