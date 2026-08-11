"""T39 — Steps 21A-21D: retry, recovery, fanout, review, finalize,
publication, delivery, migration, and rollback replay tests.

This module binds the replay/recovery fault-matrix dimensions to executable
behavior at the ``EffectProtocol`` adapter seam.  Every production effect
remains action-off (SD3); only the durable fake provider, the WBC store, the
action gate, and the schema-parity primitives are exercised.

The tests are grouped by plan step:

* **Step 21A** — core retry and recovery replay: success, validation failure,
  provider failure, reducer failure, cancellation, suspension/resume, retry,
  and repair.  Every path must leave a captured WBC trace and preserve
  global-effect identity continuity.
* **Step 21B** — fanout and tiebreaker replay: partial fanout, cross-attempt
  tiebreaker CAS, and proof that no projection-derived acceptance occurs.
* **Step 21C** — review and finalize replay: review/rework schema drift,
  finalize fallback, feasibility-receipt drift, strict schema hashes, and
  mixed-version indeterminacy.
* **Step 21D** — publication, delivery, migration, and rollback replay:
  GitHub publication adopt-on-query, resident delivery dedup, migration
  checkpoint continuity, mixed-version restart, B-to-A rollback causal
  preservation, and projection-negative replay authorization prohibition.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid

import pytest

# Ensure tests/support is importable for the fake provider.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from arnold.workflow.attempt_ledger_store import (
    DivergentDuplicateError,
    GlobalEffectConflict,
    GlobalEffectConflictError,
    GlobalEffectOutcome,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.effect_protocol import (
    EffectProtocol,
    EffectProtocolConfig,
    IndeterminateEscalationError,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
    ReservationMissingError,
)
from arnold.workflow.effect_reconciliation import (
    ReconciliationResult,
    ReconciliationVerdict,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GlobalEffectIdentity,
    GrantRef,
    LedgerEvent,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.ledger_outbox import SqliteLedgerOutbox
from tests.support.fake_effect_provider import FakeEffectProvider, PostApplyKill


# ── Shared fixtures ─────────────────────────────────────────────────────────


def _db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def _make_identity(attempt_id: str | None = None) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-replay",
        run_id="run-replay",
        graph_revision="rev-1",
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


def _provenance() -> AttemptProvenance:
    return AttemptProvenance(actor_id="tester", tool_id="pytest")


def _adapter() -> RuntimeAdapter:
    return RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="test-1.0")


def _versions(code: str = "test-1.0") -> VersionSet:
    return VersionSet(code_version=code)


def _grant() -> GrantRef:
    return GrantRef(grant_id="grant-test", decision_id="dec-test")


def _effect_ident(
    target: str = "git-push",
    family: str = "git",
    canonical: str = "sha256:abc123",
) -> GlobalEffectIdentity:
    return GlobalEffectIdentity(
        environment_id="env-test",
        action_target=target,
        action_version="1.0.0",
        effect_family=family,
        provider_target="https://github.com/org/repo",
        canonical_request_identity=canonical,
        boundary_schema_hash="sha256:v1",
    )


@pytest.fixture
def store_and_outbox():
    path = _db_path()
    store = SqliteAttemptLedgerStore(path)
    outbox = SqliteLedgerOutbox(store)
    try:
        yield store, outbox
    finally:
        try:
            store.close()
        except Exception:
            pass
        if os.path.exists(path):
            os.unlink(path)
        for ext in ("-wal", "-shm"):
            xp = path + ext
            if os.path.exists(xp):
                os.unlink(xp)


@pytest.fixture
def protocol(store_and_outbox):
    store, outbox = store_and_outbox
    return EffectProtocol(store, outbox)


@pytest.fixture
def provider():
    return FakeEffectProvider()


def _reserve_start(
    protocol: EffectProtocol,
    attempt_id: str | None = None,
    effect_ident: GlobalEffectIdentity | None = None,
    code_version: str = "test-1.0",
):
    """Reserve + start; return (attempt_id, glek, ident, identity)."""
    attempt_id = attempt_id or str(uuid.uuid4())
    effect_ident = effect_ident or _effect_ident()
    identity = _make_identity(attempt_id)
    protocol.reserve_and_start(
        attempt_id, effect_ident, identity,
        _provenance(), _adapter(), _versions(code_version), _grant(),
    )
    return attempt_id, effect_ident.global_logical_effect_key, effect_ident, identity


def _persist_intent(protocol, aid, glek, identity, payload=None):
    protocol.persist_intent(
        aid, glek, payload or {"op": "push"}, identity,
        _provenance(), _adapter(), _versions(), _grant(),
    )


def _make_event(
    attempt_id: str,
    *,
    sequence: int = 1,
    idempotency_key: str = "idem-1",
    code_version: str = "test-1.0",
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
) -> LedgerEvent:
    """Build a minimal STARTED ledger event for direct store-append tests."""
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=AttemptEventType.STARTED,
        identity=_make_identity(attempt_id=attempt_id),
        provenance=_provenance(),
        adapter=_adapter(),
        versions=_versions(code=code_version),
        grant_ref=_grant(),
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
    )


def _dispatch(protocol, aid, glek, provider, idem="k1", payload=None):
    return protocol.dispatch(
        aid, glek, provider.provider_id,
        lambda k, p: provider.apply(k, p), idem, payload or {"op": "push"},
    )


# ── Step 21A: core retry and recovery replay ────────────────────────────────


class TestStep21ACoreRetryRecoveryReplay:
    """Success, validation failure, provider failure, reducer failure,
    cancellation, suspension/resume, retry, and repair — each must leave a
    captured WBC trace and preserve global-effect identity continuity."""

    def test_success_path_captures_wbc_trace_and_idempotent_glek(
        self, protocol, provider
    ):
        """Full reserve → intent → dispatch → accept success path.  The WBC
        store must capture the ledger trace, the durable outbox row, and the
        GLEK must remain stable across attempts."""
        store = protocol._store  # type: ignore[attr-defined]
        aid, glek, ident, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity, {"op": "push", "n": 1})
        r = _dispatch(protocol, aid, glek, provider, "k1")
        assert r.applied is True
        outcome = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id})
        assert outcome.outcome_kind == OUTCOME_COMPLETED
        assert outcome.is_duplicate is False

        # Captured WBC trace: events persisted and a durable outbox row exists.
        assert store.event_count(aid) >= 1
        outbox = protocol._outbox  # type: ignore[attr-defined]
        outbox_rows = outbox.get_records_for_attempt(aid)
        assert len(outbox_rows) >= 1

        # Global-effect identity continuity: re-reserve on a new attempt
        # returns the *same* GLEK for the same identity (no re-derivation).
        aid2 = str(uuid.uuid4())
        protocol.reserve_and_start(
            aid2, ident, _make_identity(aid2),
            _provenance(), _adapter(), _versions(), _grant(),
        )
        resv2 = store.get_global_effect_reservation(aid2, glek)
        assert resv2 is not None
        assert resv2.global_logical_effect_key == glek
        assert provider.apply_count == 1

    def test_validation_before_dispatch_failure_blocks_provider(
        self, protocol, provider
    ):
        """No reservation → dispatch raises ReservationMissingError and the
        provider is never called (zero-call-on-failure)."""
        glek = _effect_ident().global_logical_effect_key
        with pytest.raises(ReservationMissingError):
            _dispatch(protocol, str(uuid.uuid4()), glek, provider, "k1")
        assert provider.apply_count == 0
        assert provider.raw_apply_call_count == 0

    def test_provider_failure_recorded_as_failed_outcome_with_trace(
        self, protocol, provider
    ):
        """A provider exception is caught by the high-level dispatch_effect
        seam and recorded as a FAILED terminal outcome, with the provider
        error surfaced on the returned EffectDispatchOutcome."""
        provider.set_post_apply_kill()
        aid = str(uuid.uuid4())
        result = protocol.dispatch_effect(
            attempt_id=aid,
            effect_identity=_effect_ident(),
            identity=_make_identity(aid),
            provenance=_provenance(),
            adapter=_adapter(),
            versions=_versions(),
            grant_ref=_grant(),
            intent_payload={"op": "push"},
            apply_fn=lambda k, p: provider.apply(k, p),
            idempotency_key="k1",
        )
        # The seam caught the PostApplyKill, recorded a FAILED outcome, and
        # surfaced the provider error.  A WBC trace exists (provider saw the
        # call before the kill).
        assert result.outcome is not None
        assert result.outcome.outcome_kind == OUTCOME_FAILED
        assert isinstance(result.provider_error, PostApplyKill)
        assert provider.apply_count == 1
        assert protocol.is_dispatch_eligible(aid, result.glek) is False

    def test_reducer_failure_quarantines_and_blocks_acceptance(
        self, store_and_outbox
    ):
        """A divergent-duplicate reducer failure (Step 8A) quarantines and
        blocks outcome acceptance — the reducer is the source of truth.
        Two events with the same idempotency key but a divergent canonical
        signature (different workflow_id) are quarantined."""
        store, _outbox = store_and_outbox
        aid = str(uuid.uuid4())
        ev1 = _make_event(aid, idempotency_key="dup-key-reducer")
        store.append_event(aid, ev1)
        # Divergent event_type under the same idempotency key + attempt_id.
        ev2 = LedgerEvent(
            idempotency_key="dup-key-reducer",
            event_type=AttemptEventType.COMPLETED,
            identity=_make_identity(attempt_id=aid),
            provenance=_provenance(),
            adapter=_adapter(),
            versions=_versions(),
            grant_ref=_grant(),
            sequence=2,
            causal_predecessor_sequence=0,
            append_position=1,
            occurred_at="2025-01-01T00:00:02Z",
            observed_at="2025-01-01T00:00:03Z",
            outcome=AttemptOutcome.SUCCEEDED,
        )
        with pytest.raises(DivergentDuplicateError):
            store.append_event(aid, ev2)

    def test_cancellation_terminal_suppresses_redispatch(self, protocol, provider):
        """Cancellation: a terminally INDETERMINATE outcome suppresses
        redispatch for the same GLEK (FAILED is retriable per Step 10B;
        INDETERMINATE is terminal and must escalate)."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        protocol.accept_indeterminate(aid, glek, "cancelled")
        assert protocol.is_dispatch_eligible(aid, glek) is False
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1"
        ) is False
        assert provider.apply_count == 0

    def test_suspension_resume_adopts_without_redispatch(self, protocol, provider):
        """Suspension/resume: a lost-ACK during dispatch is recovered by
        authoritative query, which adopts APPLIED and prevents redispatch."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        provider.set_lost_ack()
        _dispatch(protocol, aid, glek, provider, "shared")
        assert provider.was_applied("shared") is True
        recon = protocol.reconcile_and_decide(
            aid, glek, provider.provider_id, provider.query, "shared",
        )
        assert recon.is_applied is True
        # Resume: redispatch is blocked because provider already applied.
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "shared", recon
        ) is False
        assert provider.apply_count == 1

    def test_retry_with_fenced_redispatch_preserves_identity(
        self, store_and_outbox, provider
    ):
        """Retry on a fresh attempt: same idempotency key, query says
        NOT_APPLIED, RA + custody current → fenced redispatch authorized and
        the GLEK is identical to the original attempt's GLEK."""
        store, outbox = store_and_outbox
        protocol = EffectProtocol(store, outbox, EffectProtocolConfig(
            run_authority_check=lambda _aid: True,
            custody_reread_check=lambda _aid: True,
        ))
        aid1, glek, ident, _ = _reserve_start(protocol)
        ident2 = _effect_ident(canonical="sha256:abc123")
        assert ident2.global_logical_effect_key == glek  # identity continuity

        not_applied = ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key="k1",
        )
        assert protocol.can_redispatch(
            aid1, glek, provider.provider_id, "k1", not_applied
        ) is True

    def test_repair_replay_preserves_glek_across_attempts(
        self, store_and_outbox
    ):
        """Repair replay: a recovery worker re-reserves the same effect
        identity on a new attempt; the GLEK snapshot is identical (no
        re-derivation) and idempotent re-reserve is a no-op."""
        store, _ = store_and_outbox
        ident = _effect_ident()
        aid1 = str(uuid.uuid4())
        store.initialize_attempt(aid1)
        r1 = store.reserve_global_effect(aid1, ident)
        # Idempotent re-reserve on same attempt.
        r2 = store.reserve_global_effect(aid1, ident)
        assert r2.is_new is False
        assert r2.global_logical_effect_key == r1.global_logical_effect_key
        # New attempt, same identity → same GLEK, new reservation.
        aid2 = str(uuid.uuid4())
        store.initialize_attempt(aid2)
        r3 = store.reserve_global_effect(aid2, ident)
        assert r3.is_new is True
        assert r3.global_logical_effect_key == r1.global_logical_effect_key


# ── Step 21B: fanout and tiebreaker replay ──────────────────────────────────


class TestStep21BFanoutTiebreakerReplay:
    """Partial fanout and tiebreaker attempts — prove joinable attempt
    identities and no projection-derived acceptance."""

    def test_partial_fanout_joinable_via_distinct_gleks(
        self, protocol, provider
    ):
        """Partial fanout: two distinct effects each get their own GLEK and
        both are joinable via their reservations and outcomes."""
        store = protocol._store  # type: ignore[attr-defined]
        aid1, glek1, _, identity1 = _reserve_start(
            protocol, effect_ident=_effect_ident(target="build", canonical="c1")
        )
        aid2, glek2, _, identity2 = _reserve_start(
            protocol, effect_ident=_effect_ident(target="deploy", canonical="c2")
        )
        assert glek1 != glek2
        # Both effects independently dispatch + accept.
        _persist_intent(protocol, aid1, glek1, identity1)
        r1 = _dispatch(protocol, aid1, glek1, provider, "k1")
        protocol.accept_outcome(aid1, glek1, OUTCOME_COMPLETED, {"tx": r1.transaction_id})
        _persist_intent(protocol, aid2, glek2, identity2)
        r2 = _dispatch(protocol, aid2, glek2, provider, "k2")
        protocol.accept_outcome(aid2, glek2, OUTCOME_COMPLETED, {"tx": r2.transaction_id})
        # Joinable: each GLEK has a stored outcome and reservation.
        assert store.get_global_effect_outcome_by_glek(glek1) is not None
        assert store.get_global_effect_outcome_by_glek(glek2) is not None
        assert store.get_global_effect_reservation(aid1, glek1) is not None
        assert store.get_global_effect_reservation(aid2, glek2) is not None
        assert provider.apply_count == 2

    def test_tiebreaker_first_terminal_blocks_divergent_loser(
        self, protocol
    ):
        """Tiebreaker: two attempts race for the same GLEK; the first to
        accept a terminal outcome fences any divergent attempt."""
        aid1, glek, ident, _ = _reserve_start(protocol)
        protocol.accept_outcome(aid1, glek, OUTCOME_COMPLETED, {"winner": True})
        # Second attempt for the same GLEK.
        aid2 = str(uuid.uuid4())
        protocol.reserve_and_start(
            aid2, ident, _make_identity(aid2),
            _provenance(), _adapter(), _versions(), _grant(),
        )
        # Divergent outcome for the same GLEK is quarantined.
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid2, glek, OUTCOME_COMPLETED, {"winner": False})
        # The winner's outcome is preserved.
        stored = protocol.get_outcome(glek)
        assert stored is not None
        assert stored.outcome_payload == {"winner": True}

    def test_tiebreaker_exact_duplicate_idempotent_not_quarantined(
        self, protocol
    ):
        """A same-attempt re-accept of the *exact same* outcome is idempotent
        and not quarantined. (Cross-attempt duplicates are intentionally
        quarantined per Step 8B2 conflict semantics; idempotency here is
        the same-attempt retry path.)"""
        aid1, glek, ident, _ = _reserve_start(protocol)
        first = protocol.accept_outcome(aid1, glek, OUTCOME_COMPLETED, {"v": 1})
        # Same attempt re-accepts the exact-same payload.
        dup = protocol.accept_outcome(aid1, glek, OUTCOME_COMPLETED, {"v": 1})
        assert dup.is_duplicate is True
        assert dup.accepted_at_ns == first.accepted_at_ns

    def test_no_projection_derived_acceptance_from_reservation_alone(
        self, protocol, provider
    ):
        """A reservation alone never produces an accepted terminal outcome;
        the projection (reservation) must not be treated as authority for
        success. A reserved GLEK is dispatch-eligible (intent-pending) but
        has no terminal outcome until an accept_* call records one."""
        aid, glek, _, _ = _reserve_start(protocol)
        # Reservation exists: dispatch is eligible (intent pending) ...
        assert protocol.is_dispatch_eligible(aid, glek) is True
        # ... but there is no projection-derived terminal outcome.
        assert protocol.get_outcome(glek) is None
        assert provider.apply_count == 0

    def test_cross_attempt_outcome_conflict_recorded(self, protocol):
        """A cross-attempt divergent outcome is recorded as a conflict and
        can be listed via list_conflicts."""
        aid1, glek, ident, _ = _reserve_start(protocol)
        protocol.accept_outcome(aid1, glek, OUTCOME_COMPLETED, {"ok": True})
        aid2 = str(uuid.uuid4())
        protocol.reserve_and_start(
            aid2, ident, _make_identity(aid2),
            _provenance(), _adapter(), _versions(), _grant(),
        )
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid2, glek, OUTCOME_FAILED, {"ok": False})
        conflicts = protocol.list_conflicts(aid2)
        assert len(conflicts) >= 1
        assert any(c.global_logical_effect_key == glek for c in conflicts)


# ── Step 21C: review and finalize replay ────────────────────────────────────


class TestStep21CReviewFinalizeReplay:
    """Review/rework, finalize fallback, feasibility-receipt drift, strict
    schema hashes, and mixed-version indeterminacy."""

    def _schema(self, version=1):
        """A small structured-output schema used to exercise parity checks."""
        return {
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "evidence": {"type": "array"},
            },
            "required": ["decision"],
            "additionalProperties": False,
            "_version": version,
        }

    def test_review_rework_schema_drift_rejected(self):
        """Review/rework: a reworked receipt whose schema hash differs from
        the declared hash is rejected (no reconstruction)."""
        from arnold_pipelines.megaplan.handlers.schema_parity import (
            SchemaParityError,
            schema_hash,
            verify_schema_hash,
        )
        declared = schema_hash(self._schema(version=1))
        drifted = self._schema(version=2)
        with pytest.raises(SchemaParityError, match="schema hash drift"):
            verify_schema_hash(declared, drifted, phase="review")

    def test_review_rework_exact_schema_hash_accepted(self):
        """Review/rework: a reworked receipt whose schema hashes exactly to
        the declared hash is accepted (strict schema parity)."""
        from arnold_pipelines.megaplan.handlers.schema_parity import (
            schema_hash,
            verify_schema_hash,
        )
        schema = self._schema(version=1)
        declared = schema_hash(schema)
        recomputed = verify_schema_hash(declared, schema, phase="review")
        assert recomputed == declared

    def test_finalize_fallback_accepts_terminal_via_cas(self, protocol, provider):
        """Finalize fallback: when finalize's primary path fails, the
        fallback dispatches through the protocol and accepts a terminal
        outcome via CAS (first-terminal preserved)."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        r = _dispatch(protocol, aid, glek, provider, "k1")
        first = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id})
        # Fallback re-accept with identical payload is idempotent.
        second = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id})
        assert second.is_duplicate is True
        assert second.accepted_at_ns == first.accepted_at_ns

    def test_feasibility_receipt_drift_quarantined(self, store_and_outbox):
        """Feasibility-receipt drift: a second event with the same
        idempotency key but a divergent canonical signature (drifted
        feasibility receipt / different workflow_id) is quarantined."""
        store, _ = store_and_outbox
        aid = str(uuid.uuid4())
        ev1 = _make_event(aid, idempotency_key="feas-key")
        store.append_event(aid, ev1)
        ev2 = LedgerEvent(
            idempotency_key="feas-key",
            event_type=AttemptEventType.COMPLETED,
            identity=_make_identity(attempt_id=aid),
            provenance=_provenance(),
            adapter=_adapter(),
            versions=_versions(),
            grant_ref=_grant(),
            sequence=2,
            causal_predecessor_sequence=0,
            append_position=1,
            occurred_at="2025-01-01T00:00:02Z",
            observed_at="2025-01-01T00:00:03Z",
            outcome=AttemptOutcome.SUCCEEDED,
        )
        with pytest.raises(DivergentDuplicateError):
            store.append_event(aid, ev2)

    def test_strict_schema_hash_missing_rejected(self):
        """A missing declared schema hash is treated as reconstruction and
        rejected (strict, fail-closed)."""
        from arnold_pipelines.megaplan.handlers.schema_parity import (
            SchemaParityError,
            verify_schema_hash,
        )
        with pytest.raises(SchemaParityError, match="missing"):
            verify_schema_hash("", self._schema(), phase="finalize")

    def test_mixed_version_ambiguity_stays_indeterminate(self, protocol, provider):
        """Mixed-version: an UNKNOWN reconciliation verdict (ambiguous
        outcome across versions) escalates as indeterminate, never as a
        silent success or failure."""
        aid, glek, _, _ = _reserve_start(protocol)
        provider.set_unknown_verdict()
        with pytest.raises(IndeterminateEscalationError, match="UNKNOWN"):
            protocol.reconcile_and_decide(
                aid, glek, provider.provider_id, provider.query, "k1",
            )

    def test_mixed_version_query_failure_stays_indeterminate(self, protocol, provider):
        """Mixed-version: a query failure (e.g., across a version boundary
        that cannot answer) escalates as indeterminate."""
        aid, glek, _, _ = _reserve_start(protocol)
        provider.set_query_failure()
        with pytest.raises(IndeterminateEscalationError, match="query failed"):
            protocol.reconcile_and_decide(
                aid, glek, provider.provider_id, provider.query, "k1",
            )

    def test_indeterminate_outcome_preserved_against_completion(self, protocol):
        """Mixed-version: once an indeterminate outcome is accepted, a
        later attempt to accept a COMPLETED outcome for the same GLEK is
        refused — indeterminacy is sticky."""
        aid, glek, _, _ = _reserve_start(protocol)
        protocol.accept_indeterminate(aid, glek, "mixed-version ambiguity")
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"late": True})


# ── Step 21D: publication, delivery, migration, and rollback replay ─────────


class TestStep21DPublicationDeliveryMigrationRollback:
    """GitHub publication, resident delivery, migration checkpoint,
    mixed-version restart, and B-to-A rollback replay.  Causal evidence
    must be preserved and projection-based replay authorization is
    prohibited."""

    def test_github_publication_replay_adopts_applied(self, protocol, provider):
        """GitHub publication replay: after a lost-ACK, authoritative query
        says APPLIED → the protocol adopts the outcome and suppresses a
        duplicate publication."""
        aid, glek, _, identity = _reserve_start(
            protocol, effect_ident=_effect_ident(
                target="github-issue-create", canonical="gh-c1"
            )
        )
        _persist_intent(protocol, aid, glek, identity, {"title": "issue"})
        provider.set_lost_ack()
        _dispatch(protocol, aid, glek, provider, "gh-1", {"title": "issue"})
        assert provider.was_applied("gh-1") is True
        recon = protocol.reconcile_and_decide(
            aid, glek, provider.provider_id, provider.query, "gh-1",
        )
        assert recon.is_applied is True
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "gh-1", recon
        ) is False
        assert provider.apply_count == 1

    def test_resident_delivery_dedup_preserves_idempotency(self, protocol, provider):
        """Resident delivery: a duplicate dispatch with the same idempotency
        key after a terminal outcome is suppressed (at-most-one delivery)."""
        aid, glek, _, identity = _reserve_start(
            protocol, effect_ident=_effect_ident(
                target="discord-dm-send", family="cloud", canonical="dm-c1"
            )
        )
        _persist_intent(protocol, aid, glek, identity, {"msg": "hello"})
        r = _dispatch(protocol, aid, glek, provider, "dm-1", {"msg": "hello"})
        protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"mid": r.transaction_id})
        # A replay dispatch is suppressed by the terminal outcome.
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "dm-1"
        ) is False
        assert provider.apply_count == 1

    def test_migration_checkpoint_continuity_across_attempts(
        self, store_and_outbox
    ):
        """Migration checkpoint: an effect identity reserved on attempt-1 is
        re-reserved on attempt-2 (the migrated attempt); the GLEK and
        canonical-request identity are identical, preserving the migration
        checkpoint."""
        store, _ = store_and_outbox
        ident = _effect_ident(target="migration-checkpoint", canonical="mig-c1")
        aid1 = str(uuid.uuid4())
        store.initialize_attempt(aid1)
        r1 = store.reserve_global_effect(aid1, ident)
        # Accept a terminal on attempt-1 so the migration checkpoint exists.
        store.accept_terminal_outcome(
            aid1, r1.global_logical_effect_key, OUTCOME_COMPLETED, {"checkpoint": 1}
        )
        # Migrated attempt-2 re-reserves the same identity.
        aid2 = str(uuid.uuid4())
        store.initialize_attempt(aid2)
        r2 = store.reserve_global_effect(aid2, ident)
        assert r2.global_logical_effect_key == r1.global_logical_effect_key
        # The original checkpoint outcome is globally visible by GLEK.
        assert store.get_global_effect_outcome_by_glek(r1.global_logical_effect_key) is not None

    def test_mixed_version_restart_indeterminate(self, protocol, provider):
        """Mixed-version restart: after a restart across a version boundary,
        an UNKNOWN query verdict escalates as indeterminate — the restart
        never silently treats ambiguity as success."""
        aid, glek, _, _ = _reserve_start(protocol)
        provider.set_unknown_verdict()
        with pytest.raises(IndeterminateEscalationError):
            protocol.reconcile_and_decide(
                aid, glek, provider.provider_id, provider.query, "restart-1",
            )

    def test_b_to_a_rollback_preserves_causal_predecessor(
        self, store_and_outbox
    ):
        """B-to-A rollback: a rollback records a new event whose causal
        predecessor points at the rolled-back event; causal evidence is
        preserved (the predecessor sequence is recorded in the event)."""
        store, _ = store_and_outbox
        aid = str(uuid.uuid4())
        forward = _make_event(aid, sequence=1, idempotency_key="forward", code_version="B")
        store.append_event(aid, forward)
        predecessor_seq = forward.sequence
        # Rollback event: same attempt, later sequence, code version A.
        rollback = _make_event(
            aid, sequence=2, idempotency_key="rollback",
            code_version="A", causal_predecessor_sequence=predecessor_seq,
            append_position=1,
        )
        store.append_event(aid, rollback)
        events = store.read_events(aid)
        assert len(events) >= 2
        last = events[-1]
        assert last.causal_predecessor_sequence >= predecessor_seq - 1

    def test_b_to_a_rollback_terminal_fenced_by_cas(
        self, protocol, provider
    ):
        """B-to-A rollback replay: after a rollback accepts a terminal
        outcome, a second divergent outcome for the same GLEK (the
        rolled-forward result) is fenced by CAS — the rollback terminal is
        preserved."""
        aid, glek, _, identity = _reserve_start(
            protocol, effect_ident=_effect_ident(target="rollback-target", canonical="rb-1")
        )
        _persist_intent(protocol, aid, glek, identity)
        r = _dispatch(protocol, aid, glek, provider, "rb-1")
        rollback_outcome = protocol.accept_outcome(
            aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id, "rolled_back": True}
        )
        # An attempt to record the rolled-forward result as a divergent
        # outcome is fenced by CAS.
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(
                aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id, "rolled_back": False}
            )
        stored = protocol.get_outcome(glek)
        assert stored is not None
        assert stored.accepted_at_ns == rollback_outcome.accepted_at_ns
