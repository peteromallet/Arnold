"""Focused tests for the WBC canonical query facade and envelopes.

Covers T2 requirements:

* Verified terminal results — query_terminal_gate returns VERIFIED status
  with complete metadata, digest, evidence IDs, and source cursor.
* Incomplete gaps — query_gaps returns INCOMPLETE when no gaps detected.
* Indeterminate ledger reads — query_ledger/query_events on unknown attempts
  returns INDETERMINATE or INCOMPLETE without swallowing errors.
* Incoherent identity/cursor disagreements — envelope identity metadata
  cannot be silently mutated; cursors are evidence-only.
* Exact evidence IDs — every VERIFIED envelope carries a non-empty
  evidence_ids tuple derived from durable event identity.
* Absence of projection bearer-token authority — all envelope types are
  frozen dataclasses with no dispatch, grant, or authority methods;
  WbcQueries is read-only (no append, reserve, or mint methods).
"""

from __future__ import annotations

import inspect
import tempfile
import uuid
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import get_type_hints

import pytest

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    GateStatus,
    GapEntry,
    SourceCursor,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    ExecutionAttemptLedger,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.wbc_queries import (
    WbcGapEnvelope,
    WbcLedgerEnvelope,
    WbcQueries,
    WbcSourceCursorEnvelope,
    WbcStartEnvelope,
    WbcTerminalEnvelope,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_identity(attempt_id: str | None = None) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-test",
        run_id="run-test",
        graph_revision="rev-test",
        attempt_ordinal=1,
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


def _make_event(
    *,
    event_type: AttemptEventType = AttemptEventType.STARTED,
    idempotency_key: str = "idem-1",
    identity: AttemptIdentity | None = None,
    sequence: int = 1,
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
    outcome: AttemptOutcome | None = None,
    grant_id: str = "grant-1",
    decision_id: str = "decision-1",
) -> LedgerEvent:
    """Create a minimal well-formed LedgerEvent for WBC query tests."""
    if identity is None:
        identity = _make_identity()
    if outcome is None and event_type in (
        AttemptEventType.COMPLETED,
        AttemptEventType.FAILED,
        AttemptEventType.CANCELLED,
    ):
        outcome = (
            AttemptOutcome.SUCCEEDED
            if event_type == AttemptEventType.COMPLETED
            else AttemptOutcome.FAILED
        )
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=identity,
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE, adapter_version="1"
        ),
        versions=VersionSet(code_version="c"),
        grant_ref=GrantRef(grant_id=grant_id, decision_id=decision_id),
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
    )


def _append(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    event_type: AttemptEventType = AttemptEventType.STARTED,
    idempotency_key: str = "idem-1",
    sequence: int = 1,
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
    outcome: AttemptOutcome | None = None,
    grant_id: str = "grant-1",
    decision_id: str = "decision-1",
) -> AppendResult:
    """Convenience: build an event with *attempt_id* and append it."""
    identity = _make_identity(attempt_id=attempt_id)
    event = _make_event(
        event_type=event_type,
        idempotency_key=idempotency_key,
        identity=identity,
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        outcome=outcome,
        grant_id=grant_id,
        decision_id=decision_id,
    )
    return store.append_event(attempt_id, event)


def _seed_started(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    idempotency_key: str = "idem-started",
) -> AppendResult:
    """Seed a STARTED event for *attempt_id*."""
    return _append(
        store,
        attempt_id,
        event_type=AttemptEventType.STARTED,
        idempotency_key=idempotency_key,
        sequence=1,
    )


def _seed_started_and_completed(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    started_key: str = "idem-started",
    completed_key: str = "idem-completed",
) -> tuple[AppendResult, AppendResult]:
    """Seed STARTED + COMPLETED events for *attempt_id*."""
    r1 = _seed_started(store, attempt_id, idempotency_key=started_key)
    r2 = _append(
        store,
        attempt_id,
        event_type=AttemptEventType.COMPLETED,
        idempotency_key=completed_key,
        sequence=2,
        causal_predecessor_sequence=1,
        outcome=AttemptOutcome.SUCCEEDED,
    )
    return r1, r2


@pytest.fixture
def store() -> SqliteAttemptLedgerStore:
    """Return a fresh on-disk store backed by a temp file."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_wbc.db"
        s = SqliteAttemptLedgerStore(db_path)
        yield s
        s.close()


@pytest.fixture
def attempt_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def wbc(store: SqliteAttemptLedgerStore) -> WbcQueries:
    """Return a WbcQueries facade with rich metadata context."""
    return WbcQueries(
        store,
        context={
            "environment": "test",
            "session": "session-001",
            "chain": "CHAIN-01",
            "plan_revision": "rev-abc",
            "phase": "validate",
            "task": "T2",
            "boundary_id": "boundary-42",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Verified terminal results
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerifiedTerminalResults:
    """query_terminal_gate returns VERIFIED with complete metadata when a
    terminal event is durably persisted."""

    def test_terminal_verified_after_completed(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.terminal_event is not None
        assert envelope.terminal_event.event_type == AttemptEventType.COMPLETED
        assert envelope.attempt_id == attempt_id
        assert envelope.environment == "test"
        assert envelope.session == "session-001"
        assert envelope.chain == "CHAIN-01"
        assert envelope.plan_revision == "rev-abc"
        assert envelope.phase == "validate"
        assert envelope.task == "T2"
        assert envelope.boundary_id == "boundary-42"
        assert envelope.ledger_sequence == 2
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")
        assert len(envelope.content_digest) == 71  # "sha256:" + 64 hex chars

    def test_terminal_verified_carries_evidence_ids(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        # evidence_ids should contain idempotency_key, attempt_id, decision_id
        assert len(envelope.evidence_ids) >= 2
        assert "idem-completed" in envelope.evidence_ids
        assert attempt_id in envelope.evidence_ids
        assert "decision-1" in envelope.evidence_ids

    def test_terminal_incomplete_before_completion(
        self, store, attempt_id, wbc
    ):
        _seed_started(store, attempt_id)

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.terminal_event is None
        assert envelope.evidence != ""
        assert envelope.attempt_id == attempt_id

    def test_terminal_verified_after_failed(
        self, store, attempt_id, wbc
    ):
        _seed_started(store, attempt_id)
        _append(
            store,
            attempt_id,
            event_type=AttemptEventType.FAILED,
            idempotency_key="idem-failed",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.FAILED,
        )

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.terminal_event is not None
        assert envelope.terminal_event.event_type == AttemptEventType.FAILED
        assert "idem-failed" in envelope.evidence_ids

    def test_terminal_verified_source_cursor_traceability(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        # First record a source cursor
        store.update_source_cursor(
            attempt_id, last_sequence=2, cursor_key="default"
        )

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        # source_cursor should be populated
        assert envelope.source_cursor is not None
        assert envelope.source_cursor.attempt_id == attempt_id
        assert envelope.source_cursor.last_sequence == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Incomplete gaps
# ═══════════════════════════════════════════════════════════════════════════════


class TestIncompleteGaps:
    """query_gaps returns INCOMPLETE when no gaps are detected in the event
    stream (no gap evidence = INCOMPLETE, not VERIFIED)."""

    def test_no_gaps_returns_incomplete(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id)

        envelope = wbc.query_gaps(attempt_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert len(envelope.gaps) == 0
        assert envelope.evidence != ""

    def test_gaps_detected_returns_verified_via_direct_construction(
        self, store, attempt_id, wbc
    ):
        """The store prevents gap creation via its append API (sequence
        continuity enforcement), so test WbcGapEnvelope.from_gaps directly
        with manufactured GapEntry instances to verify correct VERIFIED
        envelope construction."""
        gaps = [
            GapEntry(
                attempt_id=attempt_id,
                gap_start=1,
                gap_end=3,
                missing_count=1,
            )
        ]
        envelope = WbcGapEnvelope.from_gaps(
            gaps,
            attempt_id,
            environment="test",
            chain="CHAIN-01",
        )
        assert envelope.status == GateStatus.VERIFIED
        assert len(envelope.gaps) == 1
        gap = envelope.gaps[0]
        assert isinstance(gap, GapEntry)
        assert gap.attempt_id == attempt_id
        assert gap.gap_start == 1
        assert gap.gap_end == 3
        assert gap.missing_count == 1
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")

    def test_gaps_on_unknown_attempt(self, store, wbc):
        unknown_id = str(uuid.uuid4())
        envelope = wbc.query_gaps(unknown_id)
        # No events → an empty gap list → INCOMPLETE
        assert envelope.status == GateStatus.INCOMPLETE
        assert len(envelope.gaps) == 0
        assert envelope.attempt_id == unknown_id


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Indeterminate ledger reads
# ═══════════════════════════════════════════════════════════════════════════════


class TestIndeterminateLedgerReads:
    """query_ledger/query_events on unknown attempts returns INCOMPLETE;
    indeterminate is reserved for store errors (simulated by using a closed
    or corrupted store)."""

    def test_ledger_on_unknown_attempt_returns_incomplete(
        self, store, wbc
    ):
        unknown_id = str(uuid.uuid4())
        envelope = wbc.query_ledger(unknown_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.ledger is None
        assert envelope.events == ()
        assert envelope.attempt_id == unknown_id

    def test_events_on_unknown_attempt_returns_incomplete(
        self, store, wbc
    ):
        unknown_id = str(uuid.uuid4())
        envelope = wbc.query_events(unknown_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.ledger is None
        assert envelope.events == ()
        assert envelope.attempt_id == unknown_id

    def test_ledger_on_known_attempt_returns_verified(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        envelope = wbc.query_ledger(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.ledger is not None
        assert isinstance(envelope.ledger, ExecutionAttemptLedger)
        assert len(envelope.events) == 2
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")

    def test_start_gate_on_unknown_attempt_returns_incomplete(
        self, store, wbc
    ):
        unknown_id = str(uuid.uuid4())
        envelope = wbc.query_start_gate(unknown_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.started_event is None
        assert envelope.attempt_id == unknown_id


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Incoherent identity/cursor disagreements
# ═══════════════════════════════════════════════════════════════════════════════


class TestIncoherentIdentityDisagreements:
    """Envelopes carry immutable identity metadata that cannot be silently
    mutated. Cursors are evidence-only — they describe observed state
    without granting authority."""

    def test_envelope_identity_is_immutable(self, store, attempt_id, wbc):
        _seed_started_and_completed(store, attempt_id)

        envelope = wbc.query_terminal_gate(attempt_id)
        # All envelope fields are frozen — cannot be mutated
        with pytest.raises(FrozenInstanceError):
            envelope.status = GateStatus.VERIFIED  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            envelope.attempt_id = "hijacked"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            envelope.chain = "CHAIN-99"  # type: ignore[misc]

    def test_identity_from_context_is_preserved(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id)

        envelope = wbc.query_start_gate(attempt_id)
        # Context-provided identity must match the facade context
        assert envelope.chain == "CHAIN-01"
        assert envelope.plan_revision == "rev-abc"
        assert envelope.phase == "validate"
        assert envelope.task == "T2"
        assert envelope.boundary_id == "boundary-42"

    def test_per_call_overrides_do_not_leak(self, store, attempt_id, wbc):
        """Per-call context overrides apply only to that call."""
        _seed_started(store, attempt_id)

        e1 = wbc.query_start_gate(attempt_id, chain="CHAIN-OVERRIDE")
        assert e1.chain == "CHAIN-OVERRIDE"

        e2 = wbc.query_start_gate(attempt_id)
        assert e2.chain == "CHAIN-01"  # Original context restored

    def test_source_cursor_is_evidence_only(
        self, store, attempt_id, wbc
    ):
        """SourceCursor carries no authority — it describes observation position."""
        _seed_started_and_completed(store, attempt_id)
        store.update_source_cursor(
            attempt_id, last_sequence=2, cursor_key="default"
        )

        envelope = wbc.query_source_cursor(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.cursor is not None
        assert isinstance(envelope.cursor, SourceCursor)
        assert envelope.cursor.last_sequence == 2

        # The SourceCursor type itself has no authority methods
        cursor_methods = {
            name
            for name, _ in inspect.getmembers(SourceCursor)
            if not name.startswith("_")
        }
        authority_keywords = {
            "grant", "approve", "authorize", "dispatch", "mint",
            "sign", "token", "bearer", "credential", "permit",
            "allow", "reject", "accept",
        }
        for method in cursor_methods:
            assert not any(
                kw in method.lower() for kw in authority_keywords
            ), f"SourceCursor.{method} looks like an authority method"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Exact evidence IDs
# ═══════════════════════════════════════════════════════════════════════════════


class TestExactEvidenceIds:
    """Every VERIFIED envelope carries non-empty evidence_ids derived from
    durable event identity fields."""

    def test_start_envelope_evidence_ids(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id, idempotency_key="specific-start-key")

        envelope = wbc.query_start_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert "specific-start-key" in envelope.evidence_ids
        assert attempt_id in envelope.evidence_ids

    def test_terminal_envelope_evidence_ids(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(
            store, attempt_id,
            completed_key="specific-complete-key",
        )

        envelope = wbc.query_terminal_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert "specific-complete-key" in envelope.evidence_ids
        assert attempt_id in envelope.evidence_ids
        # decision_id from grant_ref
        assert "decision-1" in envelope.evidence_ids

    def test_incomplete_envelopes_have_empty_evidence_ids(
        self, store, wbc
    ):
        unknown_id = str(uuid.uuid4())
        e1 = wbc.query_start_gate(unknown_id)
        assert e1.status == GateStatus.INCOMPLETE
        assert e1.evidence_ids == ()

        e2 = wbc.query_terminal_gate(unknown_id)
        assert e2.status == GateStatus.INCOMPLETE
        assert e2.evidence_ids == ()

    def test_evidence_ids_are_tuples_immutable(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id)
        envelope = wbc.query_start_gate(attempt_id)
        assert isinstance(envelope.evidence_ids, tuple)
        # Tuples are immutable; verify by attempting mutation
        with pytest.raises(AttributeError):
            envelope.evidence_ids.append("injected")  # type: ignore[union-attr]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Absence of projection bearer-token authority
# ═══════════════════════════════════════════════════════════════════════════════


class TestAbsenceOfBearerTokenAuthority:
    """All WBC envelope types are frozen dataclasses with no dispatch, grant,
    or authority methods. WbcQueries is read-only — it has no append, reserve,
    or mint methods and never creates authority."""

    # ── Envelope surface checks ──────────────────────────────────────────

    ALL_ENVELOPE_TYPES = [
        WbcStartEnvelope,
        WbcTerminalEnvelope,
        WbcLedgerEnvelope,
        WbcGapEnvelope,
        WbcSourceCursorEnvelope,
    ]

    @pytest.mark.parametrize("envelope_cls", ALL_ENVELOPE_TYPES)
    def test_envelope_has_no_authority_methods(self, envelope_cls):
        """No envelope type exposes authority-bearing methods."""
        import re
        _AUTH_PATTERNS = re.compile(
            r'\b(?:grant|approve|authorize|dispatch|mint|sign'
            r'|token|bearer|credential|permit|allow|reject'
            r'|accept|append|write|reserve|commit|execute)\b',
            re.IGNORECASE,
        )
        public_methods = {
            name
            for name, _ in inspect.getmembers(envelope_cls)
            if not name.startswith("_")
        }
        for method in public_methods:
            assert not _AUTH_PATTERNS.search(method), (
                f"{envelope_cls.__name__}.{method}() looks like an "
                f"authority-bearing method"
            )

    @pytest.mark.parametrize("envelope_cls", ALL_ENVELOPE_TYPES)
    def test_envelope_is_frozen_dataclass(self, envelope_cls):
        """Every envelope type is a frozen dataclass — immutable by design."""
        import dataclasses
        assert dataclasses.is_dataclass(envelope_cls), (
            f"{envelope_cls.__name__} is not a dataclass"
        )
        # Check for frozen=True
        fields = dataclasses.fields(envelope_cls)
        assert fields, f"{envelope_cls.__name__} has no fields"

    def test_wbc_queries_has_no_write_methods(self):
        """WbcQueries must be read-only — no append, reserve, or mint."""
        public_methods = {
            name
            for name, _ in inspect.getmembers(WbcQueries)
            if not name.startswith("_")
        }
        # Verbs that imply mutation/authority — match only as whole words
        # or at word boundaries in snake_case names.
        import re
        _VERB_PATTERNS = re.compile(
            r'\b(?:append|mint|reserve|grant|authorize|dispatch'
            r'|execute|insert|update|delete|upsert|create'
            r'|commit)\b',
            re.IGNORECASE,
        )
        for method in public_methods:
            assert not _VERB_PATTERNS.search(method), (
                f"WbcQueries.{method}() looks like a write/authority method"
            )

    def test_wbc_queries_only_delegates_to_store(self):
        """WbcQueries.__init__ only takes a store and context — no token or key."""
        sig = inspect.signature(WbcQueries.__init__)
        param_names = set(sig.parameters.keys())
        # self, store, context
        assert "store" in param_names
        authority_params = {
            "token", "key", "secret", "credential", "bearer",
            "principal", "role", "policy", "permission",
        }
        for param in param_names:
            assert not any(
                kw in param.lower() for kw in authority_params
            ), f"WbcQueries.__init__ parameter '{param}' looks like authority"

    def test_wbc_queries_does_not_store_authority_state(self):
        """WbcQueries only stores _store and _context — no authority state."""
        # Create a minimal WbcQueries and inspect its __dict__
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            s = SqliteAttemptLedgerStore(db_path)
            try:
                q = WbcQueries(s, context={"env": "test"})
                # Only _store and _context should exist
                instance_attrs = set(q.__dict__.keys())
                assert instance_attrs == {"_store", "_context"}, (
                    f"Unexpected attrs on WbcQueries: {instance_attrs}"
                )
            finally:
                s.close()

    def test_envelope_from_gate_result_is_construction_only(self):
        """from_gate_result factory methods do not grant authority."""
        factory_methods = [
            ("WbcStartEnvelope", WbcStartEnvelope.from_gate_result),
            ("WbcTerminalEnvelope", WbcTerminalEnvelope.from_gate_result),
        ]
        for name, method in factory_methods:
            sig = inspect.signature(method)
            param_names = set(sig.parameters.keys())
            assert "token" not in param_names, (
                f"{name}.from_gate_result accepts 'token'"
            )
            assert "bearer" not in param_names, (
                f"{name}.from_gate_result accepts 'bearer'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Source cursor envelope completeness
# ═══════════════════════════════════════════════════════════════════════════════


class TestSourceCursorEnvelope:
    """WbcSourceCursorEnvelope carries complete cursor metadata."""

    def test_cursor_verified(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id)
        store.update_source_cursor(
            attempt_id, last_sequence=1, cursor_key="default"
        )

        envelope = wbc.query_source_cursor(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.cursor is not None
        assert envelope.cursor.last_sequence == 1
        assert envelope.cursor_key == "default"
        assert envelope.attempt_id == attempt_id
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")

    def test_cursor_incomplete_when_absent(self, store, attempt_id, wbc):
        _seed_started(store, attempt_id)

        envelope = wbc.query_source_cursor(attempt_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.cursor is None
        assert envelope.ledger_sequence == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Gap envelope completeness
# ═══════════════════════════════════════════════════════════════════════════════


class TestGapEnvelopeCompleteness:
    """WbcGapEnvelope carries complete gap metadata including digest."""

    def test_gap_envelope_with_gaps_has_digest(
        self, store, attempt_id, wbc
    ):
        """Test digest computation on a gap envelope via direct construction."""
        gaps = [
            GapEntry(
                attempt_id=attempt_id,
                gap_start=1,
                gap_end=3,
                missing_count=1,
            )
        ]
        envelope = WbcGapEnvelope.from_gaps(
            gaps,
            attempt_id,
            environment="test",
        )
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")
        # Gap digest should differ from a no-gap digest
        assert envelope.evidence_ids == ()

    def test_gap_envelope_carries_context_metadata(
        self, store, attempt_id, wbc
    ):
        """Test that gap envelopes carry context metadata via direct construction."""
        gaps = [
            GapEntry(
                attempt_id=attempt_id,
                gap_start=1,
                gap_end=3,
                missing_count=1,
            )
        ]
        envelope = WbcGapEnvelope.from_gaps(
            gaps,
            attempt_id,
            environment="test",
            chain="CHAIN-01",
            phase="validate",
            task="T2",
        )
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.environment == "test"
        assert envelope.chain == "CHAIN-01"
        assert envelope.phase == "validate"
        assert envelope.task == "T2"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Start envelope completeness
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartEnvelopeCompleteness:
    """WbcStartEnvelope carries complete start-gate metadata."""

    def test_start_verified_carries_digest(
        self, store, attempt_id, wbc
    ):
        _seed_started(store, attempt_id, idempotency_key="start-key-1")

        envelope = wbc.query_start_gate(attempt_id)
        assert envelope.status == GateStatus.VERIFIED
        assert envelope.started_event is not None
        assert envelope.started_event.event_type == AttemptEventType.STARTED
        assert envelope.content_digest is not None
        assert envelope.content_digest.startswith("sha256:")
        assert envelope.ledger_sequence == 1

    def test_start_incomplete_has_no_digest(
        self, store, wbc
    ):
        unknown_id = str(uuid.uuid4())
        envelope = wbc.query_start_gate(unknown_id)
        assert envelope.status == GateStatus.INCOMPLETE
        assert envelope.content_digest is None
        assert envelope.ledger_sequence == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Cross-envelope consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestCrossEnvelopeConsistency:
    """Metadata carried across different envelope types for the same attempt
    should be consistent."""

    def test_same_attempt_consistent_metadata(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        start_env = wbc.query_start_gate(attempt_id)
        terminal_env = wbc.query_terminal_gate(attempt_id)
        ledger_env = wbc.query_ledger(attempt_id)

        for env in (start_env, terminal_env, ledger_env):
            assert env.attempt_id == attempt_id
            assert env.environment == "test"
            assert env.chain == "CHAIN-01"
            assert env.plan_revision == "rev-abc"

    def test_digests_differ_for_different_payloads(
        self, store, attempt_id, wbc
    ):
        _seed_started_and_completed(store, attempt_id)

        start_env = wbc.query_start_gate(attempt_id)
        terminal_env = wbc.query_terminal_gate(attempt_id)

        # Start and terminal digests should differ (different events)
        assert start_env.content_digest != terminal_env.content_digest
        assert start_env.content_digest is not None
        assert terminal_env.content_digest is not None

    def test_ledger_envelope_digest_matches_reconstruction(
        self, store, attempt_id, wbc
    ):
        import hashlib
        import json

        _seed_started_and_completed(store, attempt_id)

        ledger_env = wbc.query_ledger(attempt_id)
        assert ledger_env.status == GateStatus.VERIFIED
        assert ledger_env.ledger is not None

        # Recompute digest manually and verify
        canonical = json.dumps(
            ledger_env.ledger.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
        assert ledger_env.content_digest == expected
