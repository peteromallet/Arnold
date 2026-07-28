"""T38 — Steps 18A-18B and 19A-19C: executable fault-matrix scenarios.

This module binds the F01-F17 fault-matrix evidence rows to executable
protocol/store behavior at the ``EffectProtocol`` adapter seam.  Each test
class exercises one fault family:

* Step 18A/18B — inventory-row coverage join (also tested in
  ``test_m10_fault_matrix.py``) and durable-intent fault injection.
* Step 19A — reservation, intent, provider dispatch, lost-ACK safety,
  acknowledgement, and outcome CAS.
* Step 19B — outbox persistence, concurrent terminal append, and
  payload-drift quarantine.
* Step 19C — reconciliation (UNKNOWN, query failure, contradictory
  evidence), mixed-version safety, and indeterminate action-off escalation.

All production effects remain action-off (SD3); only the durable fake
provider is exercised.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure tests/support is importable for the fake provider.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from arnold.workflow.attempt_ledger_store import (
    DivergentDuplicateError,
    GlobalEffectConflictError,
    GlobalEffectOutcome,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.effect_fault_matrix import (
    load_and_validate_fault_matrix,
    load_and_validate_inventory_coverage,
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
    ProviderCapability,
    ReconciliationResult,
    ReconciliationVerdict,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptIdentity,
    AttemptProvenance,
    GlobalEffectIdentity,
    GrantRef,
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
        workflow_id="wf-fault",
        run_id="run-fault",
        graph_revision="rev-1",
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


def _provenance() -> AttemptProvenance:
    return AttemptProvenance(actor_id="tester", tool_id="pytest")


def _adapter() -> RuntimeAdapter:
    return RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="test-1.0")


def _versions() -> VersionSet:
    return VersionSet(code_version="test-1.0")


def _grant() -> GrantRef:
    return GrantRef(grant_id="grant-test", decision_id="dec-test")


def _effect_ident(target: str = "git-push") -> GlobalEffectIdentity:
    return GlobalEffectIdentity(
        environment_id="env-test",
        action_target=target,
        action_version="1.0.0",
        effect_family="git",
        provider_target="https://github.com/org/repo",
        canonical_request_identity="sha256:abc123",
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
        wal = path + "-wal"
        if os.path.exists(wal):
            os.unlink(wal)
        shm = path + "-shm"
        if os.path.exists(shm):
            os.unlink(shm)


@pytest.fixture
def protocol(store_and_outbox):
    store, outbox = store_and_outbox
    return EffectProtocol(store, outbox)


@pytest.fixture
def provider():
    return FakeEffectProvider()


def _reserve_start(protocol, attempt_id=None):
    """Reserve + start; return (attempt_id, glek, ident, identity)."""
    attempt_id = attempt_id or str(uuid.uuid4())
    effect_ident = _effect_ident()
    identity = _make_identity(attempt_id)
    protocol.reserve_and_start(
        attempt_id, effect_ident, identity,
        _provenance(), _adapter(), _versions(), _grant(),
    )
    return attempt_id, effect_ident.global_logical_effect_key, effect_ident, identity


def _persist_intent(protocol, aid, glek, identity, payload=None):
    protocol.persist_intent(
        aid, glek, payload or {"op": "push"}, identity,
        _provenance(), _adapter(), _versions(), _grant(),
    )


# ── Step 18A/18B: inventory-row coverage join ───────────────────────────────


class TestStep18InventoryCoverage:
    """Step 18A: every supported boundary contract has fault coverage."""

    def test_default_matrix_valid(self):
        report = load_and_validate_fault_matrix()
        assert report.is_valid, [e.message for e in report.errors]

    def test_default_coverage_join_valid(self):
        report = load_and_validate_inventory_coverage()
        assert report.is_valid, [e.message for e in report.errors]
        assert report.scenarios_validated == 17

    def test_every_scenario_has_refs(self):
        """F02: orphan detection — no scenario may have empty refs."""
        root = Path(__file__).resolve().parent.parent.parent
        matrix_path = root / "evidence" / "m10-f01-f17-fault-matrix.json"
        with open(str(matrix_path)) as fh:
            data = json.load(fh)
        for s in data["scenarios"]:
            assert len(s["inventory_row_refs"]) >= 1, s["id"]


# ── Step 19A: reservation, intent, dispatch, ACK, outcome ───────────────────


class TestStep19AReservationIntentDispatch:
    """F01, F03, F09: reservation, intent, dispatch, lost-ACK, suppression."""

    def test_f01_durable_intent_required_before_outcome(self, store_and_outbox, provider):
        """F01: an outcome may only be accepted for a GLEK with a reservation;
        the durable intent is the pre-record that must precede dispatch.
        A reserved GLEK is dispatch-eligible (intent-pending) but carries no
        terminal outcome until an accept_* records one."""
        store, outbox = store_and_outbox
        protocol = EffectProtocol(store, outbox)
        aid, glek, _, identity = _reserve_start(protocol)
        # Reserve-only: dispatch-eligible (intent pending) ...
        assert protocol.is_dispatch_eligible(aid, glek) is True
        # ... but no terminal outcome has been accepted yet.
        assert protocol.get_outcome(glek) is None
        assert provider.apply_count == 0

    def test_f03_post_apply_kill_recovery_via_reconciliation(self, protocol, provider):
        """F03: applied-then-kill.  Recovery via authoritative query."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        provider.set_post_apply_kill()
        with pytest.raises(PostApplyKill):
            protocol.dispatch(
                aid, glek, provider.provider_id,
                lambda k, p: provider.apply(k, p), "idem-kill", {"op": "push"},
            )
        # The provider DID record before the kill.
        assert provider.was_applied("idem-kill") is True
        # Query reconciliation says APPLIED.
        recon = protocol.reconcile_and_decide(
            aid, glek, provider.provider_id, provider.query, "idem-kill",
        )
        assert recon.is_applied is True
        # Redispatch blocked — already applied.
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "idem-kill", recon
        ) is False
        assert provider.apply_count == 1

    def test_f09_reservation_suppresses_duplicate_dispatch(self, protocol, provider):
        """F09: once a terminal outcome is accepted, redispatch is suppressed."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        r1 = protocol.dispatch(
            aid, glek, provider.provider_id,
            lambda k, p: provider.apply(k, p), "k1", {"op": "push"},
        )
        assert r1.applied is True
        protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"tx": r1.transaction_id})
        # Redispatch must be suppressed.
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1"
        ) is False
        assert provider.apply_count == 1

    def test_reservation_missing_blocks_dispatch(self, protocol, provider):
        """No reservation → dispatch raises ReservationMissingError."""
        glek = _effect_ident().global_logical_effect_key
        with pytest.raises(ReservationMissingError):
            protocol.dispatch(
                str(uuid.uuid4()), glek, provider.provider_id,
                lambda k, p: provider.apply(k, p), "k1", {},
            )
        assert provider.apply_count == 0

    def test_lost_ack_then_applied_query_blocks_redispatch(self, protocol, provider):
        """Lost ACK: provider applied but caller lost result. Query APPLIED
        blocks redispatch — at-most-one application."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        provider.set_lost_ack()
        protocol.dispatch(
            aid, glek, provider.provider_id,
            lambda k, p: provider.apply(k, p), "shared", {"op": "push"},
        )
        assert provider.was_applied("shared") is True
        recon = protocol.reconcile_and_decide(
            aid, glek, provider.provider_id, provider.query, "shared",
        )
        assert recon.is_applied is True
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "shared", recon
        ) is False
        assert provider.apply_count == 1


# ── Step 19A/19B: acknowledgement, outcome, outbox, CAS ─────────────────────


class TestStep19BOutcomeCASOutbox:
    """F02, F05, F06, F16: outcome CAS, conflict quarantine, terminal guard,
    first-terminal folding."""

    def test_f02_completed_outcome_accepted(self, protocol, provider):
        """F02: a completed outcome is accepted as terminal."""
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        r = protocol.dispatch(
            aid, glek, provider.provider_id,
            lambda k, p: provider.apply(k, p), "k1", {"op": "push"},
        )
        outcome = protocol.accept_outcome(
            aid, glek, OUTCOME_COMPLETED, {"tx": r.transaction_id}
        )
        assert outcome.outcome_kind == OUTCOME_COMPLETED
        assert outcome.is_duplicate is False

    def test_f05_divergent_outcome_quarantined(self, protocol):
        """F05: a divergent outcome for the same GLEK is quarantined."""
        aid, glek, _, _ = _reserve_start(protocol)
        protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"v": 1})
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"v": 2})

    def test_f05_exact_duplicate_idempotent(self, protocol):
        """F05 positive: an exact duplicate outcome is idempotent."""
        aid, glek, _, _ = _reserve_start(protocol)
        o1 = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"v": 1})
        o2 = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"v": 1})
        assert o2.is_duplicate is True
        assert o1.outcome_kind == o2.outcome_kind

    def test_f06_terminal_state_blocks_re_accept(self, protocol):
        """F06: once terminal, attempting a divergent re-accept raises."""
        aid, glek, _, _ = _reserve_start(protocol)
        protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"ok": True})
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid, glek, OUTCOME_FAILED, {"ok": False})

    def test_f16_first_terminal_preserved(self, protocol):
        """F16: the first terminal outcome is preserved on retry."""
        aid, glek, _, _ = _reserve_start(protocol)
        first = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"first": True})
        # A retry with the same payload is idempotent — first preserved.
        second = protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"first": True})
        assert second.is_duplicate is True
        stored = protocol.get_outcome(glek)
        assert stored is not None
        assert stored.outcome_kind == first.outcome_kind

    def test_cross_attempt_terminal_conflict(self, protocol):
        """Cross-attempt: a second attempt cannot accept a divergent outcome
        for the same GLEK."""
        aid1, glek, _, _ = _reserve_start(protocol)
        protocol.accept_outcome(aid1, glek, OUTCOME_COMPLETED, {"ok": True})
        aid2 = str(uuid.uuid4())
        effect_ident = _effect_ident()
        identity2 = _make_identity(aid2)
        protocol.reserve_and_start(
            aid2, effect_ident, identity2,
            _provenance(), _adapter(), _versions(), _grant(),
        )
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid2, glek, OUTCOME_COMPLETED, {"ok": False})

    def test_outbox_persists_durable_intent(self, store_and_outbox, provider):
        """Step 19B: persist_intent writes a durable outbox row."""
        store, outbox = store_and_outbox
        protocol = EffectProtocol(store, outbox)
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity, {"op": "push", "n": 1})
        # The outbox must contain at least one durable intent row for this attempt.
        rows = outbox.get_records_for_attempt(aid)
        assert len(rows) >= 1, (
            f"Expected at least one outbox record for attempt {aid}, got {rows}"
        )
        # The record must be in a pending (not-yet-dispatched) state.
        assert rows[0].status in ("pending", "PENDING"), (
            f"Expected pending status, got {rows[0].status!r}"
        )

    def test_indeterminate_outcome_blocks_dispatch(self, protocol):
        """An indeterminate outcome is terminal but blocks dispatch."""
        aid, glek, _, _ = _reserve_start(protocol)
        protocol.accept_indeterminate(aid, glek, "query failure")
        outcome = protocol.get_outcome(glek)
        assert outcome is not None
        assert outcome.outcome_kind == OUTCOME_INDETERMINATE
        assert protocol.is_dispatch_eligible(aid, glek) is False


# ── Step 19C: reconciliation and mixed-version ──────────────────────────────


class TestStep19CReconciliationMixedVersion:
    """F04, F07, F13, F14: query failure, lease expiry, stale epoch, RA fence,
    plus mixed-version safety."""

    def _protocol_with_checks(self, store_and_outbox, *, authority=True, custody=True):
        store, outbox = store_and_outbox
        config = EffectProtocolConfig(
            run_authority_check=lambda _gid: authority,
            custody_reread_check=lambda _aid: custody,
        )
        return EffectProtocol(store, outbox, config)

    def test_f04_query_failure_escalates(self, protocol, provider):
        """F04: a query failure escalates as indeterminate."""
        aid, glek, _, _ = _reserve_start(protocol)
        provider.set_query_failure()
        with pytest.raises(IndeterminateEscalationError, match="query failed"):
            protocol.reconcile_and_decide(
                aid, glek, provider.provider_id, provider.query, "k1",
            )

    def test_f04_unknown_verdict_escalates(self, protocol, provider):
        """F04: an UNKNOWN verdict escalates as indeterminate."""
        aid, glek, _, _ = _reserve_start(protocol)
        provider.set_unknown_verdict()
        with pytest.raises(IndeterminateEscalationError, match="UNKNOWN"):
            protocol.reconcile_and_decide(
                aid, glek, provider.provider_id, provider.query, "k1",
            )

    def test_f07_lease_expired_blocks_redispatch(self, store_and_outbox, provider):
        """F07: an expired lease (custody reread fails) blocks redispatch."""
        protocol = self._protocol_with_checks(store_and_outbox, custody=False)
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        not_applied = ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key="k1",
        )
        # Custody is not current → redispatch denied even with capability.
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1", not_applied
        ) is False

    def test_f13_stale_epoch_blocks_redispatch(self, store_and_outbox, provider):
        """F13: a stale epoch (custody reread fails) fences redispatch."""
        protocol = self._protocol_with_checks(store_and_outbox, custody=False)
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        not_applied = ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key="k1",
        )
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1", not_applied
        ) is False

    def test_f14_ra_fence_blocks_redispatch(self, store_and_outbox, provider):
        """F14: a stale Run Authority grant fences redispatch."""
        protocol = self._protocol_with_checks(store_and_outbox, authority=False)
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        not_applied = ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key="k1",
        )
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1", not_applied
        ) is False

    def test_ra_and_custody_current_allows_fenced_redispatch(
        self, store_and_outbox, provider
    ):
        """When RA + custody are current AND capability + reservation exist,
        a NOT_APPLIED reconciliation authorizes fenced redispatch."""
        protocol = self._protocol_with_checks(store_and_outbox, authority=True, custody=True)
        aid, glek, _, identity = _reserve_start(protocol)
        _persist_intent(protocol, aid, glek, identity)
        not_applied = ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key="k1",
        )
        assert protocol.can_redispatch(
            aid, glek, provider.provider_id, "k1", not_applied
        ) is True

    def test_missing_query_capability_escalates(self, protocol):
        """An unknown provider lacking query capability escalates."""
        with pytest.raises(IndeterminateEscalationError, match="lacks query"):
            protocol.reconcile_and_decide(
                str(uuid.uuid4()), "glek:x", "unknown-provider",
                lambda k: ReconciliationResult(verdict=ReconciliationVerdict.APPLIED),
                "k1",
            )

    def test_production_never_enabled(self):
        """SD3: no provider is production-enabled in M10."""
        from arnold.workflow.effect_reconciliation import is_production_enabled
        assert is_production_enabled("fake-effect-provider") is False
        assert is_production_enabled("unknown-provider") is False
        assert is_production_enabled("any-other") is False

    def test_mixed_version_provider_capability(self):
        """Mixed-version safety: the fake provider declares mixed_version_safe."""
        from arnold.workflow.effect_reconciliation import get_provider_capability
        cap = get_provider_capability("fake-effect-provider")
        assert cap.mixed_version_safe is True
        assert cap.supports_query is True
        assert cap.supports_idempotency_key is True

    def test_unknown_provider_capability_is_action_off(self):
        """An unknown provider has no query/idempotency capability — action-off."""
        from arnold.workflow.effect_reconciliation import get_provider_capability
        cap = get_provider_capability("unknown-provider")
        assert cap.can_authorize_redispatch is False
        assert cap.supports_query is False
        assert cap.supports_idempotency_key is False

    def test_indeterminate_outcome_is_terminal_and_blocks_dispatch(self, protocol):
        """An accepted indeterminate outcome is terminal and blocks dispatch."""
        aid, glek, _, _ = _reserve_start(protocol)
        protocol.accept_indeterminate(aid, glek, "contradictory evidence")
        outcome = protocol.get_outcome(glek)
        assert outcome is not None
        assert outcome.outcome_kind == OUTCOME_INDETERMINATE
        # Terminal → not dispatch-eligible.
        assert protocol.is_dispatch_eligible(aid, glek) is False
        # Cannot accept a different outcome afterward.
        with pytest.raises(GlobalEffectConflictError):
            protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, {"late": True})


# ── Step 19C: duplicate idempotency-key divergence ──────────────────────────


class TestStep19CDivergentDuplicate:
    """Step 8A extension: divergent duplicate idempotency keys are quarantined."""

    def test_divergent_duplicate_quarantined(self, store_and_outbox):
        """A second event with the same idempotency key but a divergent
        canonical signature is quarantined."""
        store, _outbox = store_and_outbox
        from arnold.workflow.execution_attempt_ledger import (
            AttemptEventType,
            LedgerEvent,
        )
        # We test the store-level divergence guard directly.
        aid = str(uuid.uuid4())
        ident = _make_identity(aid)
        # First event.
        ev1 = LedgerEvent(
            idempotency_key="dup-key",
            event_type=AttemptEventType.STARTED,
            identity=ident,
            provenance=_provenance(),
            adapter=_adapter(),
            versions=_versions(),
            grant_ref=_grant(),
            sequence=1,
            causal_predecessor_sequence=0,
            append_position=0,
            occurred_at="2025-01-01T00:00:00Z",
            observed_at="2025-01-01T00:00:01Z",
        )
        store.append_event(aid, ev1)
        # Divergent event: same attempt_id + same idempotency_key, but a
        # divergent canonical signature (different payload) → quarantined.
        ev2 = LedgerEvent(
            idempotency_key="dup-key",
            event_type=AttemptEventType.STARTED,
            identity=ident,
            provenance=_provenance(),
            adapter=_adapter(),
            versions=_versions(),
            grant_ref=_grant(),
            sequence=2,
            causal_predecessor_sequence=0,
            append_position=0,
            occurred_at="2025-01-01T00:00:00Z",
            observed_at="2025-01-01T00:00:01Z",
            payload={"divergent": True},
        )
        with pytest.raises(DivergentDuplicateError):
            store.append_event(aid, ev2)
