"""Tests for machine-readable ledger traces with stable content-addressed digests.

Proves:
* Append, query, and reconciliation traces have stable content-addressed
  SHA-256 digests.
* Every trace binds contract version, store/API revision, code/config
  versions, adapter identity, run, attempt, tenant (workflow_id), and
  causal identity (parent_attempt_id + causal_lineage).
* Traces are non-authoritative evidence — they never mint authority,
  leases, completion, or delivery decisions.
* Digest stability: identical inputs produce identical digests; different
  inputs produce different digests.
* Round-trip JSON serialization/deserialization preserves all fields.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import pytest

from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
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
from arnold.workflow.ledger_trace import (
    LEDGER_TRACE_SCHEMA_VERSION,
    _STORE_VERSION,
    LedgerTrace,
    TraceOperation,
    compute_trace_digest,
    make_append_trace,
    make_query_trace,
    make_reconcile_trace,
    make_trace_with_digest,
    trace_from_json,
    trace_to_json,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _aid() -> str:
    """Generate a fresh UUID for attempt_id."""
    return str(uuid.uuid4())


def _make_identity(
    *,
    workflow_id: str = "wf-test",
    run_id: str = "",
    attempt_id: str = "",
    step_id: str | None = None,
    boundary_id: str | None = None,
    invocation_id: str | None = None,
) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id=workflow_id,
        run_id=run_id or _aid(),
        graph_revision="abc123",
        step_id=step_id,
        boundary_id=boundary_id,
        invocation_id=invocation_id,
        attempt_ordinal=1,
        attempt_id=attempt_id or _aid(),
    )


def _make_provenance(
    *,
    parent_attempt_id: str | None = None,
    causal_lineage: tuple[str, ...] = (),
    actor_id: str | None = "actor-1",
    tool_id: str | None = "tool-1",
) -> AttemptProvenance:
    """Build an AttemptProvenance, auto-consistent when needed.

    AttemptProvenance enforces that parent_attempt_id and
    causal_lineage are consistent: if one is non-empty/non-None,
    the other must also be.
    """
    # Auto-consistency: if one is set and the other isn't, provide defaults.
    if parent_attempt_id is not None and not causal_lineage:
        causal_lineage = (parent_attempt_id,)
    elif causal_lineage and parent_attempt_id is None:
        parent_attempt_id = causal_lineage[-1]
    return AttemptProvenance(
        parent_attempt_id=parent_attempt_id,
        causal_lineage=causal_lineage,
        actor_id=actor_id,
        tool_id=tool_id,
    )


def _make_adapter(kind: AdapterKind = AdapterKind.NATIVE, version: str = "1.0.0") -> RuntimeAdapter:
    return RuntimeAdapter(adapter_kind=kind, adapter_version=version)


def _make_versions(code: str = "v1.2.3", config: str = "cfg-4", template: str = "tmpl-5") -> VersionSet:
    return VersionSet(code_version=code, config_version=config, template_version=template)


def _make_event(
    *,
    attempt_id: str = "",
    event_type: AttemptEventType = AttemptEventType.STARTED,
    sequence: int = 1,
    idempotency_key: str = "",
    workflow_id: str = "wf-test",
    run_id: str = "",
    parent_attempt_id: str | None = None,
    causal_lineage: tuple[str, ...] = (),
    adapter_kind: AdapterKind = AdapterKind.NATIVE,
    adapter_version: str = "1.0.0",
    code_version: str = "v1.2.3",
    config_version: str = "cfg-4",
    **kwargs: Any,
) -> LedgerEvent:
    """Build a LedgerEvent with all required fields using sensible defaults."""
    identity = _make_identity(
        workflow_id=workflow_id,
        run_id=run_id,
        attempt_id=attempt_id,
    )
    provenance = _make_provenance(
        parent_attempt_id=parent_attempt_id,
        causal_lineage=causal_lineage,
    )
    adapter = _make_adapter(kind=adapter_kind, version=adapter_version)
    versions = _make_versions(code=code_version, config=config_version)

    # Compute default outcome only when not explicitly provided via kwargs.
    outcome = kwargs.pop("outcome", None)
    if outcome is None and event_type in (
        AttemptEventType.COMPLETED, AttemptEventType.FAILED, AttemptEventType.CANCELLED
    ):
        outcome = AttemptOutcome.SUCCEEDED

    return LedgerEvent(
        idempotency_key=idempotency_key or _aid(),
        event_type=event_type,
        identity=identity,
        provenance=provenance,
        adapter=adapter,
        versions=versions,
        grant_ref=GrantRef(grant_id="grant-test-default"),
        sequence=sequence,
        causal_predecessor_sequence=sequence - 1,
        append_position=0,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        **kwargs,
    )


# ── Test: trace dataclass invariants ──────────────────────────────────────


class TestLedgerTraceInvariants:
    """LedgerTrace frozen dataclass invariants."""

    def test_default_authority_is_evidence_only(self) -> None:
        """Authority field must default to 'evidence-only'."""
        trace = LedgerTrace()
        assert trace.authority == "evidence-only"

    def test_non_evidence_authority_raises(self) -> None:
        """Setting authority to anything but 'evidence-only' must raise."""
        with pytest.raises(ValueError, match="evidence-only"):
            LedgerTrace(authority="authoritative")

    def test_frozen_dataclass(self) -> None:
        """LedgerTrace must be frozen — setting fields after construction raises."""
        trace = LedgerTrace()
        with pytest.raises(Exception):
            trace.authority = "changed"  # type: ignore[misc]

    def test_trace_schema_version_pinned(self) -> None:
        """Trace schema version must be the pinned constant."""
        trace = LedgerTrace()
        assert trace.trace_schema_version == LEDGER_TRACE_SCHEMA_VERSION


# ── Test: content-addressed digest stability ──────────────────────────────


class TestContentAddressedDigestStability:
    """SHA-256 digest must be stable for identical inputs."""

    def test_identical_inputs_produce_identical_digest(self) -> None:
        """Two traces built from identical inputs must have the same digest."""
        event = _make_event(event_type=AttemptEventType.STARTED, sequence=1)
        t1 = make_append_trace(event, sequence=1, event_type_str="started")
        t2 = make_append_trace(event, sequence=1, event_type_str="started")
        assert t1.digest == t2.digest

    def test_digest_is_64_char_hex(self) -> None:
        """Digest must be a 64-character hex string."""
        event = _make_event()
        trace = make_append_trace(event)
        assert len(trace.digest) == 64
        assert all(c in "0123456789abcdef" for c in trace.digest)

    def test_digest_changes_when_attempt_id_differs(self) -> None:
        """Different attempt_id must produce different digest."""
        e1 = _make_event(attempt_id=_aid())
        e2 = _make_event(attempt_id=_aid())
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_event_type_differs(self) -> None:
        """Different event_type in payload must produce different digest."""
        e1 = _make_event(event_type=AttemptEventType.STARTED, sequence=1)
        t1 = make_append_trace(e1, sequence=1, event_type_str="started")
        t2 = make_append_trace(e1, sequence=1, event_type_str="completed")
        assert t1.digest != t2.digest

    def test_digest_changes_when_workflow_id_differs(self) -> None:
        """Different workflow_id (tenant) must produce different digest."""
        e1 = _make_event(workflow_id="tenant-a")
        e2 = _make_event(workflow_id="tenant-b")
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_run_id_differs(self) -> None:
        """Different run_id must produce different digest."""
        e1 = _make_event(run_id=_aid())
        e2 = _make_event(run_id=_aid())
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_causal_lineage_differs(self) -> None:
        """Different causal_lineage must produce different digest."""
        pid1 = _aid()
        pid2 = _aid()
        e1 = _make_event(
            parent_attempt_id=pid1, causal_lineage=(_aid(), pid1)
        )
        e2 = _make_event(
            parent_attempt_id=pid2, causal_lineage=(_aid(), _aid(), pid2)
        )
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_parent_attempt_id_differs(self) -> None:
        """Different parent_attempt_id must produce different digest."""
        pid1 = _aid()
        pid2 = _aid()
        e1 = _make_event(
            parent_attempt_id=pid1, causal_lineage=(pid1,)
        )
        e2 = _make_event(
            parent_attempt_id=pid2, causal_lineage=(pid2,)
        )
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_adapter_kind_differs(self) -> None:
        """Different adapter_kind must produce different digest."""
        e1 = _make_event(adapter_kind=AdapterKind.NATIVE)
        e2 = _make_event(adapter_kind=AdapterKind.MEGAPLAN_PHASE)
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_code_version_differs(self) -> None:
        """Different code_version must produce different digest."""
        e1 = _make_event(code_version="v1.0.0")
        e2 = _make_event(code_version="v2.0.0")
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_changes_when_config_version_differs(self) -> None:
        """Different config_version must produce different digest."""
        e1 = _make_event(config_version="cfg-a")
        e2 = _make_event(config_version="cfg-b")
        t1 = make_append_trace(e1, sequence=1)
        t2 = make_append_trace(e2, sequence=1)
        assert t1.digest != t2.digest

    def test_digest_excludes_itself_and_timing_from_preimage(self) -> None:
        """The digest and emitted_at_ns fields must NOT be part of the hash pre-image.

        This is proven by constructing a trace, computing its digest, then
        manually computing the digest over the canonical payload (which
        excludes ``digest`` and ``emitted_at_ns``) and confirming they match.
        """
        event = _make_event()
        trace = make_append_trace(event, sequence=1)
        canonical = trace._canonical_json()
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert trace.digest == expected

    def test_timing_does_not_affect_digest(self) -> None:
        """Emitted_at_ns changes must NOT change digest — timing is excluded."""
        event = _make_event(attempt_id=_aid(), sequence=1)
        t1 = make_append_trace(event, sequence=1)
        import time
        time.sleep(0.001)
        t2 = make_append_trace(event, sequence=1)
        # Same semantic content, different timing → same digest.
        assert t1.digest == t2.digest
        # But emitted_at_ns values may differ.
        # (not asserting on timing since they may actually be the same)


# ── Test: append traces bind all identity fields ──────────────────────────


class TestAppendTraceIdentityBinding:
    """Append traces must bind all required identity fields."""

    def test_binds_contract_version(self) -> None:
        event = _make_event()
        trace = make_append_trace(event)
        assert trace.contract_version == LEDGER_SCHEMA_VERSION

    def test_binds_store_version(self) -> None:
        event = _make_event()
        trace = make_append_trace(event)
        assert trace.store_version == _STORE_VERSION

    def test_binds_code_version(self) -> None:
        event = _make_event(code_version="my-code-v1")
        trace = make_append_trace(event)
        assert trace.code_version == "my-code-v1"

    def test_binds_config_version(self) -> None:
        event = _make_event(config_version="my-config-v2")
        trace = make_append_trace(event)
        assert trace.config_version == "my-config-v2"

    def test_binds_adapter_kind(self) -> None:
        event = _make_event(adapter_kind=AdapterKind.MEGAPLAN_PHASE)
        trace = make_append_trace(event)
        assert trace.adapter_kind == "megaplan.phase"

    def test_binds_adapter_version(self) -> None:
        event = _make_event(adapter_version="2.3.4")
        trace = make_append_trace(event)
        assert trace.adapter_version == "2.3.4"

    def test_binds_run_id(self) -> None:
        rid = _aid()
        event = _make_event(run_id=rid)
        trace = make_append_trace(event)
        assert trace.run_id == rid

    def test_binds_attempt_id(self) -> None:
        aid = _aid()
        event = _make_event(attempt_id=aid)
        trace = make_append_trace(event)
        assert trace.attempt_id == aid

    def test_binds_workflow_id_as_tenant(self) -> None:
        event = _make_event(workflow_id="tenant-xyz")
        trace = make_append_trace(event)
        assert trace.workflow_id == "tenant-xyz"

    def test_binds_parent_attempt_id(self) -> None:
        pid = _aid()
        event = _make_event(parent_attempt_id=pid, causal_lineage=(pid,))
        trace = make_append_trace(event)
        assert trace.parent_attempt_id == pid

    def test_binds_parent_attempt_id_none(self) -> None:
        event = _make_event(parent_attempt_id=None, causal_lineage=())
        trace = make_append_trace(event)
        assert trace.parent_attempt_id is None

    def test_binds_causal_lineage(self) -> None:
        lineage = (_aid(), _aid())
        pid = lineage[-1]
        event = _make_event(parent_attempt_id=pid, causal_lineage=lineage)
        trace = make_append_trace(event)
        assert trace.causal_lineage == lineage

    def test_binds_empty_causal_lineage(self) -> None:
        event = _make_event(parent_attempt_id=None, causal_lineage=())
        trace = make_append_trace(event)
        assert trace.causal_lineage == ()

    def test_binds_event_type_in_payload(self) -> None:
        event = _make_event(
            event_type=AttemptEventType.COMPLETED,
            sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        trace = make_append_trace(event, event_type_str="completed")
        assert trace.payload["event_type"] == "completed"

    def test_binds_sequence_in_payload(self) -> None:
        event = _make_event(sequence=42)
        trace = make_append_trace(event, sequence=42)
        assert trace.payload["sequence"] == 42

    def test_binds_is_duplicate_in_payload(self) -> None:
        event = _make_event()
        t_dup = make_append_trace(event, is_duplicate=True, sequence=1)
        t_new = make_append_trace(event, is_duplicate=False, sequence=1)
        assert t_dup.payload["is_duplicate"] is True
        assert t_new.payload["is_duplicate"] is False
        assert t_dup.digest != t_new.digest

    def test_binds_idempotency_key_in_payload(self) -> None:
        key = "idem-key-abc"
        event = _make_event(idempotency_key=key)
        trace = make_append_trace(event)
        assert trace.payload["idempotency_key"] == key

    def test_operation_is_append(self) -> None:
        event = _make_event()
        trace = make_append_trace(event)
        assert trace.operation == TraceOperation.APPEND

    def test_authority_is_evidence_only(self) -> None:
        event = _make_event()
        trace = make_append_trace(event)
        assert trace.authority == "evidence-only"


# ── Test: query traces ────────────────────────────────────────────────────


class TestQueryTrace:
    """Query traces for diagnostic/cursor/reconciliation reads."""

    def test_query_trace_binds_all_identity_fields(self) -> None:
        trace = make_query_trace(
            attempt_id=_aid(),
            query_kind="gaps",
            run_id="run-xyz",
            workflow_id="wf-abc",
            parent_attempt_id="parent-1",
            causal_lineage=("anc-1",),
            adapter_kind="native",
            adapter_version="1.0",
            code_version="code-v1",
            config_version="cfg-v1",
            query_params={"limit": 50},
            result_summary={"gap_count": 2},
        )
        assert trace.operation == TraceOperation.QUERY
        assert trace.run_id == "run-xyz"
        assert trace.workflow_id == "wf-abc"
        assert trace.parent_attempt_id == "parent-1"
        assert trace.causal_lineage == ("anc-1",)
        assert trace.adapter_kind == "native"
        assert trace.adapter_version == "1.0"
        assert trace.code_version == "code-v1"
        assert trace.config_version == "cfg-v1"
        assert trace.payload["query_kind"] == "gaps"
        assert trace.payload["query_params"] == {"limit": 50}
        assert trace.payload["result_summary"] == {"gap_count": 2}
        assert trace.contract_version == LEDGER_SCHEMA_VERSION
        assert trace.store_version == _STORE_VERSION
        assert trace.authority == "evidence-only"

    def test_query_trace_digest_stable(self) -> None:
        kwargs: dict[str, Any] = dict(
            attempt_id=_aid(),
            query_kind="source_cursor",
            run_id="q-run",
            workflow_id="q-wf",
            adapter_kind="container",
            adapter_version="3.0",
            code_version="c1",
            config_version="c2",
        )
        t1 = make_query_trace(**kwargs)
        t2 = make_query_trace(**kwargs)
        assert t1.digest == t2.digest

    def test_query_trace_different_kinds_different_digests(self) -> None:
        aid = _aid()
        t1 = make_query_trace(attempt_id=aid, query_kind="gaps")
        t2 = make_query_trace(attempt_id=aid, query_kind="persistence_diagnostics")
        assert t1.digest != t2.digest

    def test_query_trace_defaults(self) -> None:
        trace = make_query_trace(attempt_id=_aid(), query_kind="gaps")
        assert trace.run_id == ""
        assert trace.workflow_id == ""
        assert trace.parent_attempt_id is None
        assert trace.causal_lineage == ()

    def test_query_trace_can_use_event_identity(self) -> None:
        """Query traces can be built from event identity fields."""
        event = _make_event(
            attempt_id=_aid(),
            run_id=_aid(),
            workflow_id="from-wf",
            parent_attempt_id=None,
            causal_lineage=(),
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="4.5.6",
            code_version="cv1",
            config_version="cv2",
        )
        trace = make_query_trace(
            attempt_id=event.identity.attempt_id,
            query_kind="reconciliation_state",
            run_id=event.identity.run_id,
            workflow_id=event.identity.workflow_id,
            parent_attempt_id=event.provenance.parent_attempt_id,
            causal_lineage=event.provenance.causal_lineage,
            adapter_kind=event.adapter.adapter_kind.value,
            adapter_version=event.adapter.adapter_version,
            code_version=event.versions.code_version,
            config_version=event.versions.config_version,
        )
        assert trace.attempt_id == event.identity.attempt_id
        assert trace.run_id == event.identity.run_id
        assert trace.workflow_id == "from-wf"
        assert trace.parent_attempt_id is None
        assert trace.causal_lineage == ()


# ── Test: reconcile traces ────────────────────────────────────────────────


class TestReconcileTrace:
    """Reconcile traces for durable gate evaluations."""

    def test_reconcile_trace_binds_all_identity_fields(self) -> None:
        trace = make_reconcile_trace(
            attempt_id=_aid(),
            reconcile_kind="start_verified",
            gate_status="verified",
            run_id="rec-run",
            workflow_id="rec-wf",
            parent_attempt_id="rec-parent",
            causal_lineage=("rec-anc",),
            adapter_kind="native",
            adapter_version="2.0",
            code_version="rec-code",
            config_version="rec-cfg",
            detail={"event_count": 1, "start_exists": True},
        )
        assert trace.operation == TraceOperation.RECONCILE
        assert trace.run_id == "rec-run"
        assert trace.workflow_id == "rec-wf"
        assert trace.parent_attempt_id == "rec-parent"
        assert trace.causal_lineage == ("rec-anc",)
        assert trace.payload["reconcile_kind"] == "start_verified"
        assert trace.payload["gate_status"] == "verified"
        assert trace.payload["detail"] == {"event_count": 1, "start_exists": True}
        assert trace.authority == "evidence-only"

    def test_reconcile_trace_digest_stable(self) -> None:
        kwargs: dict[str, Any] = dict(
            attempt_id=_aid(),
            reconcile_kind="terminal_or_indeterminate_verified",
            gate_status="incomplete",
            run_id="r-r",
            workflow_id="r-w",
        )
        t1 = make_reconcile_trace(**kwargs)
        t2 = make_reconcile_trace(**kwargs)
        assert t1.digest == t2.digest

    def test_reconcile_trace_different_gates_different_digests(self) -> None:
        aid = _aid()
        t1 = make_reconcile_trace(
            attempt_id=aid, reconcile_kind="start_verified", gate_status="verified"
        )
        t2 = make_reconcile_trace(
            attempt_id=aid, reconcile_kind="terminal_or_indeterminate_verified", gate_status="verified"
        )
        assert t1.digest != t2.digest

    def test_reconcile_trace_different_statuses_different_digests(self) -> None:
        aid = _aid()
        t1 = make_reconcile_trace(
            attempt_id=aid, reconcile_kind="start_verified", gate_status="verified"
        )
        t2 = make_reconcile_trace(
            attempt_id=aid, reconcile_kind="start_verified", gate_status="indeterminate"
        )
        assert t1.digest != t2.digest


# ── Test: JSON round-trip ─────────────────────────────────────────────────


class TestTraceJsonRoundTrip:
    """Traces must survive JSON serialization/deserialization round-trip."""

    def test_append_trace_round_trip(self) -> None:
        lineage = (_aid(), _aid())
        pid = lineage[-1]
        event = _make_event(
            attempt_id=_aid(),
            event_type=AttemptEventType.COMPLETED,
            sequence=5,
            parent_attempt_id=pid,
            causal_lineage=lineage,
            workflow_id="rt-wf",
            run_id=_aid(),
            outcome=AttemptOutcome.SUCCEEDED,
        )

        original = make_append_trace(event, is_duplicate=False, sequence=5, event_type_str="completed")
        json_str = trace_to_json(original)
        restored = trace_from_json(json_str)

        assert restored.operation == original.operation
        assert restored.digest == original.digest
        assert restored.attempt_id == original.attempt_id
        assert restored.run_id == original.run_id
        assert restored.workflow_id == original.workflow_id
        assert restored.parent_attempt_id == original.parent_attempt_id
        assert restored.causal_lineage == original.causal_lineage
        assert restored.adapter_kind == original.adapter_kind
        assert restored.adapter_version == original.adapter_version
        assert restored.code_version == original.code_version
        assert restored.config_version == original.config_version
        assert restored.contract_version == original.contract_version
        assert restored.store_version == original.store_version
        assert restored.payload == original.payload
        assert restored.authority == "evidence-only"

    def test_query_trace_round_trip(self) -> None:
        original = make_query_trace(
            attempt_id=_aid(),
            query_kind="gaps",
            run_id="q-run",
            workflow_id="q-wf",
            parent_attempt_id="q-parent",
            causal_lineage=("q-anc",),
            adapter_kind="container",
            adapter_version="9.9",
            code_version="q-code",
            config_version="q-cfg",
            query_params={"mode": "strict"},
            result_summary={"total": 3},
        )
        json_str = trace_to_json(original)
        restored = trace_from_json(json_str)
        assert restored.digest == original.digest
        assert restored.operation == TraceOperation.QUERY
        assert restored.payload["query_kind"] == "gaps"

    def test_reconcile_trace_round_trip(self) -> None:
        original = make_reconcile_trace(
            attempt_id=_aid(),
            reconcile_kind="start_verified",
            gate_status="incomplete",
            detail={"reason": "no events"},
        )
        json_str = trace_to_json(original)
        restored = trace_from_json(json_str)
        assert restored.digest == original.digest
        assert restored.operation == TraceOperation.RECONCILE
        assert restored.payload["gate_status"] == "incomplete"

    def test_json_is_valid_and_deterministic(self) -> None:
        """trace_to_json must produce valid, deterministic JSON."""
        event = _make_event(attempt_id=_aid())
        trace = make_append_trace(event)
        j1 = trace_to_json(trace)
        j2 = trace_to_json(trace)
        assert j1 == j2  # deterministic
        parsed = json.loads(j1)
        assert isinstance(parsed, dict)
        assert "digest" in parsed

    def test_round_trip_preserves_digest(self) -> None:
        """After round-trip, the digest must match — no recomputation."""
        event = _make_event()
        original = make_append_trace(event)
        restored = trace_from_json(trace_to_json(original))
        assert restored.digest == original.digest
        # Also verify that the restored trace's canonical JSON produces
        # the same digest.
        recomputed = compute_trace_digest(restored)
        assert recomputed == original.digest

    def test_empty_causal_lineage_round_trip(self) -> None:
        """Empty causal_lineage must survive round-trip as empty tuple."""
        event = _make_event(parent_attempt_id=None, causal_lineage=())
        original = make_append_trace(event)
        restored = trace_from_json(trace_to_json(original))
        assert restored.causal_lineage == ()

    def test_none_parent_attempt_id_round_trip(self) -> None:
        """None parent_attempt_id must survive round-trip."""
        event = _make_event(parent_attempt_id=None, causal_lineage=())
        original = make_append_trace(event)
        restored = trace_from_json(trace_to_json(original))
        assert restored.parent_attempt_id is None


# ── Test: non-authoritative evidence ──────────────────────────────────────


class TestNonAuthoritativeEvidence:
    """Traces are evidence, not authority."""

    def test_authority_field_is_hardcoded(self) -> None:
        """No code path may set authority to anything but 'evidence-only'."""
        for constructor in [
            lambda: make_append_trace(_make_event()),
            lambda: make_query_trace(attempt_id=_aid(), query_kind="gaps"),
            lambda: make_reconcile_trace(
                attempt_id=_aid(), reconcile_kind="start_verified", gate_status="verified"
            ),
        ]:
            trace = constructor()
            assert trace.authority == "evidence-only"

    def test_authority_field_present_in_json(self) -> None:
        """The authority marker must be visible in the JSON output."""
        trace = make_append_trace(_make_event())
        j = trace_to_json(trace)
        assert '"authority":"evidence-only"' in j

    def test_trace_does_not_contain_authoritative_markers(self) -> None:
        """JSON output must not contain misleading authority markers."""
        trace = make_reconcile_trace(
            attempt_id=_aid(), reconcile_kind="start_verified", gate_status="verified"
        )
        j = trace_to_json(trace)
        assert "authoritative" not in j
        assert '"granting"' not in j
        assert '"leasing"' not in j

    def test_to_dict_includes_authority(self) -> None:
        """to_dict must include the authority field."""
        trace = make_append_trace(_make_event())
        d = trace.to_dict()
        assert d["authority"] == "evidence-only"


# ── Test: trace payload completeness ──────────────────────────────────────


class TestTracePayloadCompleteness:
    """Trace payloads must capture operation-specific detail."""

    def test_append_payload_includes_graph_revision(self) -> None:
        event = _make_event()
        trace = make_append_trace(event)
        assert "graph_revision" in trace.payload
        assert trace.payload["graph_revision"] == event.identity.graph_revision

    def test_append_payload_includes_step_boundary_invocation(self) -> None:
        identity = _make_identity(
            step_id="step-1", boundary_id="bound-1", invocation_id="inv-1"
        )
        event = _make_event()
        object.__setattr__(event, "identity", identity)
        trace = make_append_trace(event)
        assert trace.payload["step_id"] == "step-1"
        assert trace.payload["boundary_id"] == "bound-1"
        assert trace.payload["invocation_id"] == "inv-1"

    def test_append_payload_includes_actor_tool_ids(self) -> None:
        provenance = _make_provenance(actor_id="actor-x", tool_id="tool-y")
        event = _make_event()
        object.__setattr__(event, "provenance", provenance)
        trace = make_append_trace(event)
        assert trace.payload["actor_id"] == "actor-x"
        assert trace.payload["tool_id"] == "tool-y"

    def test_append_payload_includes_template_version(self) -> None:
        versions = _make_versions(template="tmpl-99")
        event = _make_event()
        object.__setattr__(event, "versions", versions)
        trace = make_append_trace(event)
        assert trace.payload["template_version"] == "tmpl-99"

    def test_query_payload_defaults(self) -> None:
        trace = make_query_trace(attempt_id=_aid(), query_kind="gaps")
        assert trace.payload["query_params"] == {}
        assert trace.payload["result_summary"] == {}

    def test_reconcile_payload_defaults(self) -> None:
        trace = make_reconcile_trace(
            attempt_id=_aid(), reconcile_kind="start_verified", gate_status="verified"
        )
        assert trace.payload["detail"] == {}


# ── Test: digest computation edge cases ───────────────────────────────────


class TestDigestEdgeCases:
    """Digest computation under edge-case inputs."""

    def test_very_long_lineage(self) -> None:
        """Causal lineage with many entries must still produce stable digest."""
        lineage = tuple(_aid() for _ in range(100))
        pid = lineage[-1]
        event = _make_event(parent_attempt_id=pid, causal_lineage=lineage)
        t1 = make_append_trace(event)
        t2 = make_append_trace(event)
        assert t1.digest == t2.digest
        assert len(t1.digest) == 64

    def test_unicode_in_identity(self) -> None:
        """Unicode characters in identity fields must not break digest."""
        event = _make_event(workflow_id="wf-\u65e5\u672c\u8a9e")
        trace = make_append_trace(event)
        assert len(trace.digest) == 64

    def test_special_characters_in_idempotency_key(self) -> None:
        """Special characters in idempotency_key must not break digest."""
        event = _make_event(idempotency_key="key/with:special chars!")
        trace = make_append_trace(event)
        assert len(trace.digest) == 64

    def test_compute_trace_digest_explicit(self) -> None:
        """compute_trace_digest must match the trace's own digest."""
        trace = LedgerTrace(attempt_id="explicit-test")
        digest = compute_trace_digest(trace)
        assert len(digest) == 64
        # make_trace_with_digest should set the same digest.
        traced = make_trace_with_digest(trace)
        assert traced.digest == digest

    def test_digest_present_in_to_dict(self) -> None:
        """to_dict must include the digest field."""
        trace = make_append_trace(_make_event())
        d = trace.to_dict()
        assert "digest" in d
        assert d["digest"] == trace.digest

    def test_emitted_at_ns_is_set(self) -> None:
        """Every trace must have a non-zero emitted_at_ns timestamp."""
        trace = make_append_trace(_make_event())
        assert trace.emitted_at_ns > 0


# ── Test: trace from event disambiguation ─────────────────────────────────


class TestTraceIdentityDisambiguation:
    """Traces must disambiguate events correctly."""

    def test_two_events_same_attempt_different_sequence(self) -> None:
        """Two events with different sequences in the same attempt must
        produce different digests."""
        aid = _aid()
        e1 = _make_event(
            attempt_id=aid, sequence=1, event_type=AttemptEventType.STARTED,
            idempotency_key="key-1",
        )
        e2 = _make_event(
            attempt_id=aid, sequence=2, event_type=AttemptEventType.COMPLETED,
            idempotency_key="key-2",
            outcome=AttemptOutcome.SUCCEEDED,
        )
        t1 = make_append_trace(e1, sequence=1, event_type_str="started")
        t2 = make_append_trace(e2, sequence=2, event_type_str="completed")
        assert t1.digest != t2.digest

    def test_same_event_dedup_vs_new(self) -> None:
        """Same event, one marked duplicate, one marked new — different digests."""
        event = _make_event(sequence=1)
        t_dup = make_append_trace(event, is_duplicate=True, sequence=1)
        t_new = make_append_trace(event, is_duplicate=False, sequence=1)
        assert t_dup.digest != t_new.digest

    def test_different_adapter_kinds_produce_different_digests(self) -> None:
        """Native vs megaplan_phase adapter must produce different digests."""
        e_native = _make_event(adapter_kind=AdapterKind.NATIVE)
        e_megaplan = _make_event(adapter_kind=AdapterKind.MEGAPLAN_PHASE)
        t_n = make_append_trace(e_native)
        t_m = make_append_trace(e_megaplan)
        assert t_n.digest != t_m.digest
