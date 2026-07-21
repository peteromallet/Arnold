"""Tests proving chain terminal/completion reads derive from canonical WBC
terminal/gap queries and exact source cursors (M9 — T10).

These tests pin the contract that:

* terminal and completion status reads derive from canonical WBC terminal/gap
  queries when supplied, while legacy chain JSON remains a compatibility
  projection only;
* drift records are emitted when live active attempts (canonical WBC terminal
  query ``INCOMPLETE`` — no durable terminal event) invalidate stale chain
  terminal labels;
* other run-state dimensions (pause, PR-merge, runner liveness, policy gates)
  are preserved during drift — drift never collapses them into a single state;
* the WBC envelopes and source cursor vector never grant dispatch, completion,
  cancellation, publication, or delivery authority; and
* legacy behaviour is fully preserved when no WBC evidence is supplied.

The canonical envelopes are constructed from real ``WbcTerminalEnvelope`` /
``WbcGapEnvelope`` dataclasses driven by a real ``SqliteAttemptLedgerStore`` so
the integration is exercised end-to-end, not stubbed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from arnold.runtime.durable_ops import OperationState
from arnold.workflow.attempt_ledger_store import (
    GateStatus,
    GapEntry,
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
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.wbc_queries import (
    WbcGapEnvelope,
    WbcTerminalEnvelope,
)
from arnold_pipelines.megaplan.chain import operator_pause as _pause_mod
from arnold_pipelines.megaplan.chain.spec import ChainState
from arnold_pipelines.megaplan.chain.status import classify_chain_status

_ATTEMPT_ID = str(uuid.uuid4())


# ── Fixtures ────────────────────────────────────────────────────────────────


def _identity(attempt_id: str = _ATTEMPT_ID) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-test",
        run_id="run-test",
        graph_revision="rev-test",
        step_id="step-1",
        boundary_id=None,
        invocation_id="inv-1",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _ledger_event(
    event_type: AttemptEventType,
    *,
    sequence: int,
    attempt_id: str = _ATTEMPT_ID,
) -> LedgerEvent:
    """Build a minimal well-formed LedgerEvent for the WBC-backed tests."""
    if event_type is AttemptEventType.COMPLETED:
        outcome: AttemptOutcome | None = AttemptOutcome.SUCCEEDED
    elif event_type is AttemptEventType.FAILED:
        outcome = AttemptOutcome.FAILED
    elif event_type is AttemptEventType.CANCELLED:
        outcome = AttemptOutcome.CANCELLED
    else:
        outcome = None
    return LedgerEvent(
        idempotency_key=f"key-{event_type.value}-{sequence}",
        event_type=event_type,
        identity=_identity(attempt_id),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c"),
        grant_ref=GrantRef(grant_id="grant-1", decision_id="decision-1"),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=max(sequence - 1, 0),
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
    )


@pytest.fixture
def store(tmp_path: Path) -> SqliteAttemptLedgerStore:
    """Return a fresh on-disk store backed by a temp file (no manual init)."""
    return SqliteAttemptLedgerStore(tmp_path / "ledger.db")


def _seed_started(store: SqliteAttemptLedgerStore, attempt_id: str = _ATTEMPT_ID) -> None:
    store.append_started(attempt_id, _ledger_event(AttemptEventType.STARTED, sequence=1))


def _seed_terminal(
    store: SqliteAttemptLedgerStore,
    event_type: AttemptEventType,
    attempt_id: str = _ATTEMPT_ID,
) -> None:
    _seed_started(store, attempt_id)
    store.append_event(attempt_id, _ledger_event(event_type, sequence=2))


def _terminal_envelope(
    store: SqliteAttemptLedgerStore, attempt_id: str = _ATTEMPT_ID
) -> WbcTerminalEnvelope:
    gate = store.terminal_or_indeterminate_verified(attempt_id)
    return WbcTerminalEnvelope.from_gate_result(
        gate,
        attempt_id=attempt_id,
        environment="env-1",
        session="sess-1",
        chain="CHAIN-01",
        plan_revision="rev-1",
        phase="phase-1",
        task="task-1",
    )


def _gap_envelope(
    store: SqliteAttemptLedgerStore, attempt_id: str = _ATTEMPT_ID
) -> WbcGapEnvelope:
    gaps = store.query_gaps(attempt_id)
    return WbcGapEnvelope.from_gaps(
        gaps,
        attempt_id=attempt_id,
        environment="env-1",
        session="sess-1",
        chain="CHAIN-01",
        plan_revision="rev-1",
        phase="phase-1",
        task="task-1",
    )


def _chain_state_stub(
    last_state: str | None, completed=(), current_index: int = 0
) -> ChainState:
    """A real ``ChainState`` so ``is_paused`` and other reads work unchanged."""
    return ChainState(
        last_state=last_state,
        completed=list(completed),
        current_milestone_index=current_index,
    )


def _paused_chain_state(last_state: str | None = "done") -> ChainState:
    """A ``ChainState`` carrying an active operator-pause record."""
    state = ChainState(last_state=last_state)
    state.metadata[_pause_mod.AUTHORITY_KEY] = {"active": True}
    return state


_BASE_KWARGS = dict(
    launch_state=None,
    spec=None,
    plan_status={"status": "missing"},
    human_verification={},
    runner={"status": "dead"},
    policy={},
    sync={},
)


# ── 1. Legacy compatibility preserved (no WBC evidence) ─────────────────────


class TestLegacyCompatPreserved:
    def test_terminal_authority_is_legacy_chain_compat_without_wbc(self):
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("done"),
            **_BASE_KWARGS,
        )
        assert c.metadata["terminal_authority"] == "legacy_chain_compat"

    def test_no_drift_records_without_wbc(self):
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("done"),
            **_BASE_KWARGS,
        )
        assert c.metadata["drift"] == []

    def test_no_wbc_refs_without_wbc(self):
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("done"),
            **_BASE_KWARGS,
        )
        assert c.metadata["wbc_refs"] == []
        assert c.metadata["wbc_refs_authority"] == "evidence_extracted_non_authoritative"

    def test_absent_source_cursor_without_vector(self):
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("done"),
            **_BASE_KWARGS,
        )
        assert c.metadata["source_cursor_vector"]["authority"] == "absent"

    def test_terminal_classification_unaffected_without_wbc(self):
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub(None),
            **_BASE_KWARGS,
        )
        assert c.operation_state is OperationState.SUCCEEDED
        assert c.reason == "terminal_operation_state"


# ── 2. Terminal reads derive from canonical WBC queries ─────────────────────


class TestTerminalReadDerivesFromWbcCanonical:
    def test_terminal_authority_is_wbc_canonical_with_envelope(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)  # INCOMPLETE — no terminal event
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.metadata["terminal_authority"] == "wbc_canonical"

    def test_wbc_refs_carry_terminal_query(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        refs = c.metadata["wbc_refs"]
        assert len(refs) == 1
        assert refs[0]["query"] == "terminal"
        assert refs[0]["status"] == "INCOMPLETE"
        assert refs[0]["attempt_id"] == _ATTEMPT_ID

    def test_source_cursor_vector_threaded_as_display_only(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1", "digest": "sha256:abc"},
            **_BASE_KWARGS,
        )
        sc = c.metadata["source_cursor_vector"]
        assert sc["authority"] == "evidence_extracted_display_only"
        assert sc["value"]["ledger"] == "seq=1"
        assert sc["value"]["digest"] == "sha256:abc"


# ── 3. Drift on stale terminal labels invalidated by live active attempts ───


class TestDriftOnStaleTerminalLabel:
    def test_stale_done_label_invalidated_by_incomplete_terminal(self, store):
        # WBC shows attempt in-flight (STARTED, no terminal); chain says "done".
        _seed_started(store)
        env = _terminal_envelope(store)
        assert env.status is GateStatus.INCOMPLETE
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        # Terminal read must NOT be trusted -> falls through to non-terminal.
        assert c.operation_state is not OperationState.SUCCEEDED
        drift = c.metadata["drift"]
        assert any(
            d["kind"] == "live_active_attempt_contradicts_stale_terminal_label"
            and d["chain_terminal_label"] == "succeeded"
            and d["wbc_status"] == "INCOMPLETE"
            for d in drift
        )

    def test_stale_terminal_operation_state_invalidated(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.FAILED,
            chain_state=_chain_state_stub(None),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.operation_state is not OperationState.FAILED
        drift = c.metadata["drift"]
        assert any(
            d["kind"] == "live_active_attempt_contradicts_stale_terminal_label"
            for d in drift
        )

    def test_drift_record_carries_evidence_and_source_cursor(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        drift = c.metadata["drift"]
        rec = drift[0]
        assert rec["authority"] == "evidence_only_non_authoritative"
        assert rec["wbc_terminal_envelope"]["attempt_id"] == _ATTEMPT_ID
        assert rec["source_cursor_vector"]["value"]["ledger"] == "seq=1"

    def test_wbc_indeterminate_invalidates_terminal_label(self, store):
        env = WbcTerminalEnvelope(status=GateStatus.INDETERMINATE, attempt_id=_ATTEMPT_ID)
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.operation_state is not OperationState.SUCCEEDED
        assert any(
            d["kind"] == "wbc_terminal_unverifiable_invalidates_chain_label"
            and d["wbc_status"] == "INDETERMINATE"
            for d in c.metadata["drift"]
        )

    def test_wbc_incoherent_invalidates_terminal_label(self):
        env = WbcTerminalEnvelope(status=GateStatus.INCOHERENT, attempt_id=_ATTEMPT_ID)
        c = classify_chain_status(
            operation_state=OperationState.CANCELLED,
            chain_state=_chain_state_stub("cancelled"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.operation_state is not OperationState.CANCELLED
        assert any(d["wbc_status"] == "INCOHERENT" for d in c.metadata["drift"])


# ── 4. No drift when WBC agrees with chain labels ───────────────────────────


class TestNoDriftWhenWbcAgrees:
    def test_verified_completed_does_not_drift(self, store):
        _seed_terminal(store, AttemptEventType.COMPLETED)
        env = _terminal_envelope(store)
        assert env.status is GateStatus.VERIFIED
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=2"},
            **_BASE_KWARGS,
        )
        # VERIFIED terminal -> terminal read trusted, no drift.
        assert c.operation_state is OperationState.SUCCEEDED
        assert c.reason == "terminal_operation_state"
        assert c.metadata["drift"] == []

    def test_verified_terminal_carries_event_type(self, store):
        _seed_terminal(store, AttemptEventType.FAILED)
        env = _terminal_envelope(store)
        assert env.status is GateStatus.VERIFIED
        c = classify_chain_status(
            operation_state=OperationState.FAILED,
            chain_state=_chain_state_stub("failed"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=2"},
            **_BASE_KWARGS,
        )
        assert c.operation_state is OperationState.FAILED
        refs = c.metadata["wbc_refs"]
        assert refs[0]["terminal_event_type"] == "failed"


# ── 5. Other run-state dimensions preserved during drift ────────────────────


class TestOtherDimensionsPreservedDuringDrift:
    def test_pause_dimension_preserved_when_wbc_invalidates_terminal(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        # Paused chain state with last_state="done" (stale terminal label).
        paused = _paused_chain_state(last_state="done")
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=paused,
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        # Pause is checked before terminal — it wins, dimensions preserved.
        assert c.operation_state is OperationState.SUSPENDED
        assert c.reason == "operator_pause"

    def test_runner_alive_dimension_preserved_when_wbc_invalidates_terminal(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **{**_BASE_KWARGS, "runner": {"status": "alive"}},
        )
        # Stale "done" invalidated -> falls through to runner_alive (RUNNING).
        assert c.operation_state is OperationState.RUNNING
        assert c.reason == "runner_alive"
        assert any(
            d["kind"] == "live_active_attempt_contradicts_stale_terminal_label"
            for d in c.metadata["drift"]
        )

    def test_drift_does_not_collapse_into_single_new_state(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        # Non-terminal plan status preserved after terminal invalidation.
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **{**_BASE_KWARGS, "plan_status": {"status": "executing"}},
        )
        # Falls through to "active_plan_without_live_runner" (stale_bookkeeping),
        # NOT collapsed to a fabricated drift-only state.
        assert c.effective_status == "stale_bookkeeping"
        assert c.reason == "active_plan_without_live_runner"


# ── 6. Gap-envelope drift ───────────────────────────────────────────────────


class TestGapEnvelopeDrift:
    def test_gap_envelope_with_gaps_records_drift(self):
        # Construct an explicit gap envelope to guarantee deterministic coverage.
        explicit = WbcGapEnvelope(
            status=GateStatus.VERIFIED,
            gaps=(GapEntry(attempt_id=_ATTEMPT_ID, gap_start=2, gap_end=4, missing_count=3),),
            attempt_id=_ATTEMPT_ID,
        )
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_gap_envelope=explicit,
            source_cursor_vector={"ledger": "seq=5"},
            **_BASE_KWARGS,
        )
        assert any(
            d["kind"] == "wbc_gap_detected_in_ledger_sequence" for d in c.metadata["drift"]
        )
        refs = c.metadata["wbc_refs"]
        assert any(r["query"] == "gap" and r["gap_count"] == 1 for r in refs)

    def test_gap_envelope_without_gaps_records_no_gap_drift(self):
        env = WbcGapEnvelope(status=GateStatus.INCOMPLETE, gaps=(), attempt_id=_ATTEMPT_ID)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_gap_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert not any(
            d["kind"] == "wbc_gap_detected_in_ledger_sequence" for d in c.metadata["drift"]
        )


# ── 7. Non-authoritative guarantees ─────────────────────────────────────────


class TestNonAuthoritativeGuarantees:
    def test_wbc_refs_marked_non_authoritative(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.metadata["wbc_refs_authority"] == "evidence_extracted_non_authoritative"

    def test_drift_records_marked_evidence_only(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        for d in c.metadata["drift"]:
            assert d["authority"] == "evidence_only_non_authoritative"

    def test_terminal_invalidation_does_not_mint_completion(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.SUCCEEDED,
            chain_state=_chain_state_stub("done"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.operation_state is not OperationState.SUCCEEDED

    def test_source_cursor_marked_display_only(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        assert c.metadata["source_cursor_vector"]["authority"] == "evidence_extracted_display_only"


# ── 8. to_dict round-trip carries M9 fields ─────────────────────────────────


class TestToDictCarriesM9Fields:
    def test_to_dict_includes_m9_metadata(self, store):
        _seed_started(store)
        env = _terminal_envelope(store)
        c = classify_chain_status(
            operation_state=OperationState.RUNNING,
            chain_state=_chain_state_stub("running"),
            wbc_terminal_envelope=env,
            source_cursor_vector={"ledger": "seq=1"},
            **_BASE_KWARGS,
        )
        d = c.to_dict()
        assert "terminal_authority" in d["metadata"]
        assert "drift" in d["metadata"]
        assert "wbc_refs" in d["metadata"]
        assert "source_cursor_vector" in d["metadata"]
        assert d["metadata"]["terminal_authority"] == "wbc_canonical"
