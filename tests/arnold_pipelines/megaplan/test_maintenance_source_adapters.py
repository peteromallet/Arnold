"""Focused Maintenance source-adapter proof tests (M2, T23).

These tests prove the read-only owner adapters against spies/fakes for the
exact canonical read APIs:

* Run Authority adapter over ``RunAuthorityView`` + ``evaluate_current_source``;
* WBC adapter over the exact ``AttemptLedgerStore`` read/query/version APIs;
* Custody adapter over M7 lease history/current-lease/validator evidence;
* Conformance adapter over accepted M10/M11 validation + predecessor evidence;
* Native manifest adapter over the C1/C2/S1/S2R neutral manifest surface.

Coverage matrix (per the T23 task):

* exact API spies (no mutation surface, only named read/query/version calls);
* stable, deterministic digests and replayable reads;
* no embedded owner payloads (references stay locator/digest/cursor);
* missing/unapproved handoffs resolve to typed UNKNOWN with no references;
* path/schema/digest/identity mismatches resolve to typed UNKNOWN (no exception);
* owner coordinates (record_type / identity / schema_version) are populated;
* before/after version coordinates and the adapter-level ``torn`` flag;
* deterministic M3 approved/pending/schema/adapter/projection/fixture reporting.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import SourceVersionVector
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HANDOFF_IDS,
    ApprovalEvidence,
    ApprovalState,
    HandoffAcceptedEntry,
    HandoffDriftEntry,
    HandoffRegistry,
    HandoffResolutionReason,
    HandoffResolutionState,
    HandoffRow,
    MaintenanceHandoffView,
    WbcCoordinates,
    build_handoff_view,
    default_handoff_registry,
    verify_handoff_drift,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.sources import (
    ConformanceAdapter,
    CustodyAdapter,
    NativeManifestAdapter,
    ProofAdapter,
    ProofRead,
    RUNTIME_SOURCE_PATHS,
    RunAuthorityAdapter,
    RuntimeAdapter,
    RuntimeRead,
    WbcAdapter,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

UTC = timezone.utc


def _ts() -> datetime:
    return datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fakes / spies
# ---------------------------------------------------------------------------


class _Grant:
    def __init__(self, grant_id: str, payload: str = "") -> None:
        self.grant_id = grant_id
        self.payload = payload

    def to_dict(self) -> dict:
        return {"grant_id": self.grant_id, "payload": self.payload}


class _Decision:
    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id

    def to_dict(self) -> dict:
        return {"decision_id": self.decision_id}


class _Fence:
    def __init__(self, coordinator_attempt_id: str, token: str) -> None:
        self.coordinator_attempt_id = coordinator_attempt_id
        self.token = token

    def to_dict(self) -> dict:
        return {"coordinator_attempt_id": self.coordinator_attempt_id, "token": self.token}


class _Attempt:
    def __init__(self, attempt_id: str) -> None:
        self.attempt_id = attempt_id

    def to_dict(self) -> dict:
        return {"attempt_id": self.attempt_id}


class _Quarantine:
    def __init__(self, quarantine_id: str) -> None:
        self.quarantine_id = quarantine_id

    def to_dict(self) -> dict:
        return {"quarantine_id": self.quarantine_id}


class _Diagnostic:
    def __init__(self, record_type: str, record_id: str) -> None:
        self.record_type = record_type
        self.record_id = record_id

    def to_dict(self) -> dict:
        return {"record_type": self.record_type, "record_id": self.record_id}


class _View:
    """Minimal RunAuthorityView-shaped read source."""

    def __init__(self, view_hash: str = "a" * 64) -> None:
        self.view_hash = view_hash
        self.run_id = "run-1"
        self.run_revision = "rev-1"
        self.journal_cursor = 7
        self.evidence_set_digest = "b" * 64
        self.grants = [_Grant("g-1", payload="PAYLOAD-SECRET")]
        self.decisions = [_Decision("d-1")]
        self.fences = [_Fence("att-9", "tok-1")]
        self.attempts = [_Attempt("a-1")]
        self.quarantines = [_Quarantine("q-1")]
        self.diagnostics = [_Diagnostic("diag", "r-1")]


class _EventType:
    def __init__(self, value: str) -> None:
        self.value = value


class _Event:
    def __init__(self, sequence: int, event_type: str = "started", idempotency_key: str | None = None) -> None:
        self.sequence = sequence
        self.event_type = _EventType(event_type)
        self.idempotency_key = idempotency_key or f"key-{sequence}"

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "idempotency_key": self.idempotency_key,
        }


class _Ledger:
    def __init__(self, last_event: _Event | None = None) -> None:
        self.last_event = last_event

    def to_dict(self) -> dict:
        return {"last_sequence": self.last_event.sequence if self.last_event else 0}


class _Gap:
    def __init__(self, gap_start: int, gap_end: int) -> None:
        self.gap_start = gap_start
        self.gap_end = gap_end

    def to_dict(self) -> dict:
        return {"gap_start": self.gap_start, "gap_end": self.gap_end}


class _Cursor:
    def __init__(self, cursor_key: str = "default", last_sequence: int = 0, last_position: str | None = None) -> None:
        self.cursor_key = cursor_key
        self.last_sequence = last_sequence
        self.last_position = last_position

    def to_dict(self) -> dict:
        return {
            "cursor_key": self.cursor_key,
            "last_sequence": self.last_sequence,
            "last_position": self.last_position,
        }


class _PersistenceDiag:
    def __init__(self, target_event_sequence: int = 0) -> None:
        self.target_event_sequence = target_event_sequence

    def to_dict(self) -> dict:
        return {"target_event_sequence": self.target_event_sequence}


class _Lease:
    def __init__(self, custody_epoch: int = 1, payload: str = "") -> None:
        self.custody_epoch = custody_epoch
        self.payload = payload

    def to_dict(self) -> dict:
        return {"custody_epoch": self.custody_epoch, "payload": self.payload}


class _Evidence:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def to_dict(self) -> dict:
        return {"payload": self.payload}


class _Manifest:
    def __init__(self, digest: str, *, schema_identity: str | None = None, identity: str | None = None) -> None:
        self._digest = digest
        self.schema_identity = schema_identity
        self.identity = identity

    def digest(self) -> str:
        return self._digest


class _SpyStore:
    """Records every call; exposes ONLY the read/query/version API surface."""

    def __init__(
        self,
        *,
        events: list[_Event] | None = None,
        ledger: _Ledger | None = None,
        terminal: _Event | None = None,
        gaps: list[_Gap] | None = None,
        diagnostics: list[_PersistenceDiag] | None = None,
        reconciliation: list[_PersistenceDiag] | None = None,
        cursor: _Cursor | None = None,
        contract: str = "c1",
        store: str = "s1",
    ) -> None:
        self._events = events if events is not None else []
        self._ledger = ledger
        self._terminal = terminal
        self._gaps = gaps if gaps is not None else []
        self._diagnostics = diagnostics if diagnostics is not None else []
        self._reconciliation = reconciliation if reconciliation is not None else []
        self._cursor = cursor
        self._contract = contract
        self._store = store
        self.calls: list[str] = []

    def get_contract_version(self) -> str:
        self.calls.append("get_contract_version")
        return self._contract

    def get_store_version(self) -> str:
        self.calls.append("get_store_version")
        return self._store

    def read_events(self, attempt_id: str) -> list[_Event]:
        self.calls.append("read_events")
        return self._events

    def read_ledger(self, attempt_id: str) -> _Ledger | None:
        self.calls.append("read_ledger")
        return self._ledger

    def get_terminal_event(self, attempt_id: str) -> _Event | None:
        self.calls.append("get_terminal_event")
        return self._terminal

    def query_gaps(self, attempt_id: str) -> list[_Gap]:
        self.calls.append("query_gaps")
        return self._gaps

    def query_persistence_diagnostics(self, attempt_id: str) -> list[_PersistenceDiag]:
        self.calls.append("query_persistence_diagnostics")
        return self._diagnostics

    def query_reconciliation_state(self, attempt_id: str) -> list[_PersistenceDiag]:
        self.calls.append("query_reconciliation_state")
        return self._reconciliation

    def query_source_cursor(self, attempt_id: str, cursor_key: str) -> _Cursor | None:
        self.calls.append("query_source_cursor")
        return self._cursor


_ALLOWED_WBC_CALLS = {
    "get_contract_version",
    "get_store_version",
    "read_events",
    "read_ledger",
    "get_terminal_event",
    "query_gaps",
    "query_persistence_diagnostics",
    "query_reconciliation_state",
    "query_source_cursor",
}

_MUTATION_VERBS = (
    "append",
    "reserve",
    "update",
    "write",
    "delete",
    "remove",
    "create",
    "acquire",
    "renew",
    "transfer",
    "release",
    "expire",
    "fence",
    "migrate",
    "insert",
)


def _assert_no_mutation_surface(adapter: object) -> None:
    for name in dir(adapter):
        if name.startswith("_"):
            continue
        if not callable(getattr(adapter, name, None)):
            continue
        low = name.lower()
        assert not any(verb in low for verb in _MUTATION_VERBS), (
            f"adapter exposes a mutation surface: {name}"
        )


def _registry(accepted: dict[str, HandoffRow] | None = None) -> HandoffRegistry:
    """A full 8-row registry; *accepted* overrides rows that become accepted."""
    overrides = accepted or {}
    rows: list[HandoffRow] = []
    for hid in HANDOFF_IDS:
        if hid in overrides:
            rows.append(overrides[hid])
        else:
            rows.append(
                HandoffRow(
                    id=hid,
                    source_path=f"pending/{hid}",
                    schema_identity=f"schema-{hid}.v1",
                    owner_api_identity=f"owner.api.{hid}",
                    schema_version="v1",
                    digest=None,
                    approval=ApprovalState.PENDING_HUMAN_APPROVAL,
                    requires_wbc_coordinates=(hid == "M6A"),
                )
            )
    return HandoffRegistry(rows=tuple(rows))


def _accepted_row(
    handoff_id: str,
    *,
    source_path: str,
    schema_identity: str,
    digest: str,
    wbc: WbcCoordinates | None = None,
    owner_api_identity: str | None = None,
    schema_version: str = "v1",
    approval_evidence: ApprovalEvidence | None = None,
) -> HandoffRow:
    return HandoffRow(
        id=handoff_id,
        source_path=source_path,
        schema_identity=schema_identity,
        owner_api_identity=owner_api_identity or f"owner.api.{handoff_id}",
        schema_version=schema_version,
        digest=digest,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=(handoff_id == "M6A"),
        wbc_coordinates=wbc,
        approval_evidence=approval_evidence
        or ApprovalEvidence(
            approver="approver-1",
            approved_at=_ts(),
            evidence_ref=f"approval://{handoff_id}/1",
            digest="c" * 64,
        ),
    )


def _evidence(handoff_id: str, *, approver: str = "approver-1") -> ApprovalEvidence:
    return ApprovalEvidence(
        approver=approver,
        approved_at=_ts(),
        evidence_ref=f"approval://{handoff_id}/1",
        digest="c" * 64,
    )


# ---------------------------------------------------------------------------
# OwnerRef coordinate contract (T1 follow-through)
# ---------------------------------------------------------------------------


def test_owner_ref_carries_all_frozen_coordinates() -> None:
    ref = OwnerRef(
        owner="run_authority",
        record_type="grant",
        identity="run-1",
        schema_version="1",
        locator="grant://g-1",
        digest="c" * 64,
        cursor="journal:7",
    )
    assert {"owner", "record_type", "identity", "schema_version", "cursor", "digest", "locator"} <= set(
        OwnerRef.model_fields
    )
    assert ref.record_type == "grant"
    assert ref.identity == "run-1"
    assert ref.schema_version == "1"
    # The enrichment coordinates survive canonical serialization (all seven
    # OwnerRef coordinates are retained byte-stably).
    dumped = canonical_dumps(ref)
    assert '"record_type"' in dumped
    assert '"identity"' in dumped
    assert '"schema_version"' in dumped
    assert '"digest"' in dumped and '"locator"' in dumped


# ---------------------------------------------------------------------------
# Run Authority adapter
# ---------------------------------------------------------------------------


def test_run_authority_adapter_reads_immutable_refs_without_payloads() -> None:
    view = _View()
    calls: list[str] = []

    def provider():
        calls.append("view")
        return view

    adapter = RunAuthorityAdapter(provider, environment="production")
    read = adapter.read()
    assert _SHA256.fullmatch(read.digest)
    assert read.torn is False
    assert calls == ["view", "view"]  # before + after around the read

    grant = read.grants[0]
    assert grant.owner == "run_authority"
    assert grant.record_type == "grant"
    assert grant.identity == "run-1"
    assert grant.schema_version == "1"
    assert _SHA256.fullmatch(grant.digest or "")

    # The owner record payload is never embedded in the read result.
    dumped = canonical_dumps(read)
    assert "PAYLOAD-SECRET" not in dumped

    # Stable / replayable digest.
    assert read.digest == canonical_digest(read)
    read2 = adapter.read()
    assert read2.digest == read.digest
    _assert_no_mutation_surface(adapter)


# ---------------------------------------------------------------------------
# WBC adapter
# ---------------------------------------------------------------------------


def _wbc_store() -> _SpyStore:
    events = [_Event(1, "started", "key-1"), _Event(2, "completed", "key-2")]
    return _SpyStore(
        events=events,
        ledger=_Ledger(last_event=events[-1]),
        terminal=events[-1],
        gaps=[_Gap(1, 2)],
        diagnostics=[_PersistenceDiag(1)],
        reconciliation=[_PersistenceDiag(2)],
        cursor=_Cursor("default", 2, "pos-2"),
    )


def test_wbc_adapter_calls_only_read_query_version_apis() -> None:
    store = _wbc_store()
    adapter = WbcAdapter(store)
    read = adapter.read_attempt("att-1")
    assert store.calls
    assert set(store.calls) <= _ALLOWED_WBC_CALLS
    assert _SHA256.fullmatch(read.digest)
    assert read.torn is False
    # Every WBC reference carries owner coordinates.
    assert read.ledger_ref is not None
    assert read.ledger_ref.record_type == "ledger"
    assert read.ledger_ref.identity == "att-1"
    assert read.ledger_ref.schema_version == "1"
    assert read.gap_refs and read.gap_refs[0].record_type == "gap"
    _assert_no_mutation_surface(adapter)


def test_wbc_adapter_emits_before_after_coordinates() -> None:
    store = _wbc_store()
    read = WbcAdapter(store).read_attempt("att-1")
    vector = read.version_vector
    assert vector.owner == "wbc"
    assert vector.before == "contract:c1|store:s1"
    assert vector.after == "contract:c1|store:s1"
    assert read.contract_version_before == "c1"
    assert read.store_version_after == "s1"


# ---------------------------------------------------------------------------
# Custody / Conformance / Native: missing + unapproved -> UNKNOWN
# ---------------------------------------------------------------------------


def test_custody_unapproved_handoff_is_unknown_with_no_refs() -> None:
    adapter = CustodyAdapter(
        current_lease_provider=lambda _lease_id: _Lease(payload="LEASE-PAYLOAD"),
        history_provider=lambda _lease_id: [_Lease(1)],
    )
    read = adapter.read("lease-1")
    assert read.handoff is not None
    assert read.handoff.state is not HandoffResolutionState.ACCEPTED
    assert read.current_lease_ref is None
    assert read.history_refs == ()
    assert read.validator_evidence_refs == ()
    assert "LEASE-PAYLOAD" not in canonical_dumps(read)
    _assert_no_mutation_surface(adapter)


def test_conformance_unapproved_handoff_is_unknown_with_no_refs() -> None:
    adapter = ConformanceAdapter(
        validation_evidence_provider=lambda _subject: [_Evidence("EVIDENCE-PAYLOAD")],
    )
    read = adapter.read("subject-1")
    assert read.handoffs
    assert all(h.state is not HandoffResolutionState.ACCEPTED for h in read.handoffs)
    assert read.validation_refs == ()
    assert read.predecessor_wrapper_refs == ()
    _assert_no_mutation_surface(adapter)


def test_native_unapproved_handoff_is_unknown_with_no_refs() -> None:
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest("d" * 64),
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is not HandoffResolutionState.ACCEPTED
    assert read.manifest_ref is None
    _assert_no_mutation_surface(adapter)


# ---------------------------------------------------------------------------
# Native: accepted path/schema/digest/identity validation (fail-closed)
# ---------------------------------------------------------------------------


def _native_registry(
    *,
    source_path: str = "native/completion/c1",
    schema_identity: str = "native.completion.c1.v1",
    digest: str = "a" * 64,
) -> HandoffRegistry:
    return _registry(
        accepted={
            "C1": _accepted_row(
                "C1",
                source_path=source_path,
                schema_identity=schema_identity,
                digest=digest,
            )
        }
    )


def test_native_path_mismatch_returns_typed_unknown() -> None:
    registry = _native_registry(source_path="wrong/path")
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest("a" * 64), registry=registry
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.handoff.reason is HandoffResolutionReason.PATH_MISMATCH
    assert read.manifest_ref is None


def test_native_digest_mismatch_returns_typed_unknown() -> None:
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest("b" * 64),
        registry=_native_registry(digest="a" * 64),
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.handoff.reason is HandoffResolutionReason.DIGEST_MISMATCH
    assert read.manifest_ref is None


def test_native_schema_mismatch_returns_typed_unknown() -> None:
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest("a" * 64, schema_identity="wrong.schema"),
        registry=_native_registry(),
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.handoff.reason is HandoffResolutionReason.SCHEMA_MISMATCH
    assert read.manifest_ref is None


def test_native_identity_mismatch_returns_typed_unknown() -> None:
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest("a" * 64, identity="other-subject"),
        registry=_native_registry(),
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.handoff.reason is HandoffResolutionReason.IDENTITY_MISMATCH
    assert read.manifest_ref is None


def test_native_accepted_manifest_emits_reference_with_coordinates() -> None:
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest(
            "a" * 64, schema_identity="native.completion.c1.v1", identity="subject-1"
        ),
        registry=_native_registry(),
    )
    read = adapter.read("C1", "subject-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.ACCEPTED
    assert read.manifest_ref is not None
    assert read.manifest_ref.owner == "native_manifest"
    assert read.manifest_ref.record_type == "manifest"
    assert read.manifest_ref.identity == "subject-1"
    assert read.schema_identity == "native.completion.c1.v1"
    assert read.owner_api_identity == "owner.api.C1"
    assert read.owner_schema_version == "v1"
    assert read.version_vector.before == "a" * 64
    assert read.version_vector.after == "a" * 64
    assert read.torn is False


# ---------------------------------------------------------------------------
# Custody / Conformance: accepted path + coordinates + before/after
# ---------------------------------------------------------------------------


def test_custody_accepted_read_emits_coordinates_and_before_after() -> None:
    registry = _registry(
        accepted={
            "M7": _accepted_row(
                "M7",
                source_path="megaplan/controlled_writers",
                schema_identity="megaplan.controlled_writers.v1",
                digest="e" * 64,
            )
        }
    )
    adapter = CustodyAdapter(
        current_lease_provider=lambda _lease_id: _Lease(custody_epoch=3),
        history_provider=lambda _lease_id: [_Lease(1)],
        registry=registry,
    )
    read = adapter.read("lease-1")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.ACCEPTED
    assert read.current_lease_ref is not None
    assert read.current_lease_ref.record_type == "current_lease"
    assert read.current_lease_ref.identity == "lease-1"
    assert read.owner_api_identity == "owner.api.M7"
    assert read.owner_schema_version == "v1"
    assert read.history_refs and read.history_refs[0].record_type == "lease_event"
    assert read.version_vector.before == read.version_vector.after
    assert read.torn is False
    # Probe is owner-backed and stable for an unchanged lease.
    assert adapter.probe("lease-1") == read.version_vector.before


def test_conformance_accepted_read_emits_coordinates_and_before_after() -> None:
    registry = _registry(
        accepted={
            "M10": _accepted_row(
                "M10",
                source_path="megaplan/watchdog_auditor",
                schema_identity="megaplan.watchdog_auditor.v1",
                digest="f" * 64,
            ),
            "M11": _accepted_row(
                "M11",
                source_path="megaplan/conformance",
                schema_identity="megaplan.conformance.v1",
                digest="f" * 64,
            ),
        }
    )
    adapter = ConformanceAdapter(
        validation_evidence_provider=lambda _subject: [_Evidence("ev-1")],
        registry=registry,
    )
    read = adapter.read("subject-1")
    assert all(h.state is HandoffResolutionState.ACCEPTED for h in read.handoffs)
    assert read.owner_api_identities == ("owner.api.M10", "owner.api.M11")
    assert read.owner_schema_versions == ("v1", "v1")
    assert read.validation_refs and read.validation_refs[0].record_type == "validation"
    assert read.validation_refs[0].identity == "subject-1"
    assert read.version_vector.before == read.version_vector.after
    assert read.torn is False


# ---------------------------------------------------------------------------
# M3 deterministic reporting
# ---------------------------------------------------------------------------


def test_m3_handoff_view_is_deterministic_and_enforcement_disabled() -> None:
    v1 = build_handoff_view()
    v2 = build_handoff_view()
    assert v1.digest == v2.digest
    assert _SHA256.fullmatch(v1.registry_digest)
    assert v1.enforcement_enabled is False
    assert v1.shadow_operation_enabled is True
    assert v1.enforcement_blocked is True
    assert v1.pending_blocker_count == len(HANDOFF_IDS)
    assert v1.approved_handoff_ids == ()
    assert set(v1.pending_handoff_ids) == set(HANDOFF_IDS)
    assert set(v1.schema_digests) >= {
        "identity",
        "contracts",
        "events",
        "handoffs",
        "sources",
        "boundaries",
        "observation",
        "projections",
        "ledger",
        "authority.coherence",
    }
    assert set(v1.adapter_versions) == {
        "RunAuthorityAdapter",
        "WbcAdapter",
        "CustodyAdapter",
        "ConformanceAdapter",
        "NativeManifestAdapter",
    }
    assert set(v1.projection_api_versions) == {
        "operational_custody",
        "verification",
        "efficiency_analysis",
    }
    assert set(v1.fixture_digests) == {"coherent_join", "torn_join", "recurrence_replay"}


def test_m3_handoff_view_reports_accepted_handoffs() -> None:
    registry = _registry(
        accepted={
            "M6A": _accepted_row(
                "M6A",
                source_path="wbc/attempt_ledger_store",
                schema_identity="wbc.attempt_ledger_store.v1",
                digest="a" * 64,
                wbc=WbcCoordinates(incarnation="inc-1", restore_generation="gen-1", high_water="hw-1"),
            )
        }
    )
    view = build_handoff_view(registry=registry)
    assert view.approved_handoff_ids == ("M6A",)
    assert "M6A" not in view.pending_handoff_ids
    assert view.pending_blocker_count == len(HANDOFF_IDS) - 1
    assert view.enforcement_blocked is True  # still blocked by the remaining 7


# ---------------------------------------------------------------------------
# M3 Step 1: exact owner identity / schema version / digest / approval
# evidence; frozen accepted vector and drift (T1)
# ---------------------------------------------------------------------------


def test_handoff_row_records_exact_owner_coordinates_and_round_trips() -> None:
    row = HandoffRow(
        id="M6A",
        source_path="wbc/attempt_ledger_store",
        schema_identity="wbc.attempt_ledger_store.v1",
        owner_api_identity="arnold.workflow.attempt_ledger_store.AttemptLedgerStore",
        schema_version="v1",
        digest="a" * 64,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=True,
        wbc_coordinates=WbcCoordinates(
            incarnation="inc-1", restore_generation="gen-1", high_water="hw-1"
        ),
        approval_evidence=_evidence("M6A"),
    )
    assert row.owner_api_identity == (
        "arnold.workflow.attempt_ledger_store.AttemptLedgerStore"
    )
    assert row.schema_version == "v1"
    assert row.digest == "a" * 64
    assert row.approval_evidence is not None
    assert row.approval_evidence.approver == "approver-1"
    assert row.is_complete is True
    assert row.acceptance_eligible is True
    decoded = strict_loads(HandoffRow, canonical_dumps(row))
    assert decoded == row
    assert canonical_digest(decoded) == canonical_digest(row)


def test_handoff_row_rejects_pending_row_with_production_data() -> None:
    with pytest.raises(ValueError, match="must not carry digest"):
        HandoffRow(
            id="M6A",
            source_path="wbc/attempt_ledger_store",
            schema_identity="wbc.attempt_ledger_store.v1",
            owner_api_identity="wbc.AttemptLedgerStore",
            schema_version="v1",
            digest="a" * 64,  # production data on a pending row
            approval=ApprovalState.PENDING_HUMAN_APPROVAL,
            requires_wbc_coordinates=True,
        )
    with pytest.raises(ValueError, match="requires approval=approved"):
        HandoffRow(
            id="M7",
            source_path="megaplan/controlled_writers",
            schema_identity="megaplan.controlled_writers.v1",
            owner_api_identity="megaplan.CustodyLeaseStore",
            schema_version="v1",
            approval=ApprovalState.PENDING_HUMAN_APPROVAL,
            approval_evidence=_evidence("M7"),  # evidence on a pending row
        )


def test_handoff_row_rejects_approval_evidence_without_approved_state() -> None:
    with pytest.raises(ValueError, match="requires approval=approved"):
        HandoffRow(
            id="M7",
            source_path="megaplan/controlled_writers",
            schema_identity="megaplan.controlled_writers.v1",
            owner_api_identity="megaplan.CustodyLeaseStore",
            schema_version="v1",
            approval=ApprovalState.UNKNOWN,
            approval_evidence=_evidence("M7"),
        )


def test_handoff_row_rejects_contradictory_schema_version() -> None:
    with pytest.raises(ValueError, match="must end with"):
        HandoffRow(
            id="M7",
            source_path="megaplan/controlled_writers",
            schema_identity="megaplan.controlled_writers.v1",
            owner_api_identity="megaplan.CustodyLeaseStore",
            schema_version="v2",  # contradicts schema_identity .v1
            approval=ApprovalState.PENDING_HUMAN_APPROVAL,
        )


def test_handoff_registry_resolves_missing_handoff_to_typed_unknown() -> None:
    registry = _registry()
    resolution = registry.resolve("NOPE")
    assert resolution.state is HandoffResolutionState.UNKNOWN
    assert resolution.reason is HandoffResolutionReason.MISSING_HANDOFF
    assert resolution.approval is ApprovalState.UNKNOWN
    assert resolution.row is None
    # Missing is never acceptance: no accepted-vector entry appears.
    assert registry.accepted_vector() == ()


def test_approved_row_without_approval_evidence_is_missing_field() -> None:
    # A claimed approval without its recorded evidence is never acceptance:
    # the row is complete only when digest AND approval evidence are present.
    row = HandoffRow(
        id="C1",
        source_path="native/completion/c1",
        schema_identity="native.completion.c1.v1",
        owner_api_identity="native.completion.c1.kernel",
        schema_version="v1",
        digest="a" * 64,
        approval=ApprovalState.APPROVED,
        approval_evidence=None,
    )
    assert row.acceptance_eligible is False
    resolution = _registry(accepted={"C1": row}).resolve("C1")
    assert resolution.state is HandoffResolutionState.UNKNOWN
    assert resolution.reason is HandoffResolutionReason.MISSING_FIELD
    # Non-dispatchable: no reference may be emitted for a MISSING_FIELD row.
    adapter = NativeManifestAdapter(
        manifest_provider=lambda _hid, _sub: _Manifest(
            "a" * 64, schema_identity="native.completion.c1.v1", identity="subject-1"
        ),
        registry=_registry(accepted={"C1": row}),
    )
    read = adapter.read("C1", "subject-1")
    assert read.manifest_ref is None
    assert read.owner_api_identity is None


def test_m3_view_exposes_frozen_accepted_vector_and_drift() -> None:
    registry = _registry(
        accepted={
            "M6A": _accepted_row(
                "M6A",
                source_path="wbc/attempt_ledger_store",
                schema_identity="wbc.attempt_ledger_store.v1",
                digest="a" * 64,
                owner_api_identity="arnold.workflow.attempt_ledger_store.AttemptLedgerStore",
                wbc=WbcCoordinates(
                    incarnation="inc-1", restore_generation="gen-1", high_water="hw-1"
                ),
            )
        }
    )
    view = build_handoff_view(registry=registry)
    # The frozen accepted vector exposes the exact accepted coordinates.
    assert len(view.accepted_vector) == 1
    entry = view.accepted_vector[0]
    assert isinstance(entry, HandoffAcceptedEntry)
    assert entry.handoff_id == "M6A"
    assert entry.owner_api_identity == (
        "arnold.workflow.attempt_ledger_store.AttemptLedgerStore"
    )
    assert entry.schema_identity == "wbc.attempt_ledger_store.v1"
    assert entry.schema_version == "v1"
    assert entry.digest == "a" * 64
    assert entry.wbc_coordinates is not None
    assert entry.wbc_coordinates.incarnation == "inc-1"
    assert entry.approval_evidence.approver == "approver-1"
    assert view.approved_handoff_ids == ("M6A",)
    # Drift covers every consumed source; pending rows never match.
    assert len(view.drift) == len(HANDOFF_IDS)
    by_id = {entry.handoff_id: entry for entry in view.drift}
    assert set(by_id) == set(HANDOFF_IDS)
    assert all(isinstance(e, HandoffDriftEntry) for e in view.drift)
    assert by_id["M6A"].recorded_digest == "a" * 64
    assert by_id["M6A"].matches is False  # no live artifact read in the pure view
    assert by_id["M7"].recorded_digest is None
    # The view is deterministic and round-trips through the strict codec.
    assert view.digest == canonical_digest(strict_loads(MaintenanceHandoffView, canonical_dumps(view)))


def test_verify_handoff_drift_reports_live_match_and_mismatch(tmp_path) -> None:
    artifact = tmp_path / "wbc" / "attempt_ledger_store"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("owner-artifact-bytes", encoding="utf-8")
    matching = hashlib.sha256(artifact.read_bytes()).hexdigest()
    registry = _registry(
        accepted={
            "M6A": _accepted_row(
                "M6A",
                source_path="wbc/attempt_ledger_store",
                schema_identity="wbc.attempt_ledger_store.v1",
                digest=matching,
                owner_api_identity="arnold.workflow.attempt_ledger_store.AttemptLedgerStore",
                wbc=WbcCoordinates(
                    incarnation="inc-1", restore_generation="gen-1", high_water="hw-1"
                ),
            )
        }
    )
    drift = verify_handoff_drift(registry, project_root=tmp_path)
    by_id = {entry.handoff_id: entry for entry in drift}
    assert by_id["M6A"].recorded_digest == matching
    assert by_id["M6A"].live_digest == matching
    assert by_id["M6A"].matches is True
    # Missing artifacts and pending rows report drift without promotion.
    assert by_id["M7"].live_digest is None
    assert by_id["M7"].matches is False
    # A digest mismatch is reported as data — never accepted.
    artifact.write_text("changed-bytes", encoding="utf-8")
    drift2 = verify_handoff_drift(registry, project_root=tmp_path)
    by_id2 = {entry.handoff_id: entry for entry in drift2}
    assert by_id2["M6A"].live_digest != matching
    assert by_id2["M6A"].matches is False
    # The live drift can be injected into the view.
    view = build_handoff_view(registry=registry, drift=drift2)
    view_by_id = {entry.handoff_id: entry for entry in view.drift}
    assert view_by_id["M6A"].matches is False
    assert view_by_id["M6A"].live_digest is not None


# ---------------------------------------------------------------------------
# C2 proof and S1/S2R runtime/source adapters (T6_impl, M3 Step 5)
# ---------------------------------------------------------------------------


def _proof_record(digest: str, *, schema_identity: str | None = None, identity: str | None = None) -> _Manifest:
    return _Manifest(digest, schema_identity=schema_identity, identity=identity)


def _accepted_c2_row(digest: str = "d" * 64) -> HandoffRow:
    return _accepted_row(
        "C2",
        source_path="native/completion/c2",
        schema_identity="native.completion.c2.v1",
        digest=digest,
    )


def _accepted_runtime_row(handoff_id: str, digest: str = "d" * 64) -> HandoffRow:
    source_path = RUNTIME_SOURCE_PATHS[handoff_id]
    return _accepted_row(
        handoff_id,
        source_path=source_path,
        schema_identity=f"native.runtime.{handoff_id.lower()}.v1",
        digest=digest,
    )


def test_proof_adapter_unapproved_handoff_is_unknown_with_no_refs() -> None:
    adapter = ProofAdapter(
        proof_provider=lambda proof_id: _proof_record("d" * 64),
        registry=_registry(),
        environment="production",
    )
    read = adapter.read("proof-1", "chain:session")
    assert isinstance(read, ProofRead)
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.proof_ref is None
    assert read.control_refs == ()
    assert adapter.probe("proof-1") is None


def test_proof_adapter_accepted_read_emits_refs_and_versions() -> None:
    adapter = ProofAdapter(
        proof_provider=lambda proof_id: _proof_record("d" * 64),
        control_provider=lambda proof_id: [_Evidence("control-1")],
        registry=_registry({"C2": _accepted_c2_row()}),
        environment="production",
    )
    read = adapter.read("proof-1", "chain:session")
    assert read.handoff.state is HandoffResolutionState.ACCEPTED
    assert read.proof_ref is not None
    assert read.proof_ref.owner == "native_manifest"
    assert read.proof_ref.digest == "d" * 64
    assert len(read.control_refs) == 1
    assert read.owner_api_identity == "owner.api.C2"
    assert read.version_vector.before == read.version_vector.after == "d" * 64
    assert read.torn is False
    assert adapter.probe("proof-1") == "d" * 64
    _assert_no_mutation_surface(adapter)


def test_proof_adapter_schema_identity_digest_mismatches_are_typed_unknown() -> None:
    adapter = ProofAdapter(
        proof_provider=lambda proof_id: _proof_record("e" * 64),
        registry=_registry({"C2": _accepted_c2_row()}),
        environment="production",
    )
    read = adapter.read("proof-1", "chain:session")
    assert read.handoff.reason is HandoffResolutionReason.DIGEST_MISMATCH
    assert read.proof_ref is None

    schema_wrong = ProofAdapter(
        proof_provider=lambda proof_id: _proof_record(
            "d" * 64, schema_identity="native.completion.c2.v9"
        ),
        registry=_registry({"C2": _accepted_c2_row()}),
    )
    read2 = schema_wrong.read("proof-1", "chain:session")
    assert read2.handoff.reason is HandoffResolutionReason.SCHEMA_MISMATCH
    assert read2.proof_ref is None

    identity_wrong = ProofAdapter(
        proof_provider=lambda proof_id: _proof_record(
            "d" * 64, identity="chain:other"
        ),
        registry=_registry({"C2": _accepted_c2_row()}),
    )
    read3 = identity_wrong.read("proof-1", "chain:session")
    assert read3.handoff.reason is HandoffResolutionReason.IDENTITY_MISMATCH
    assert read3.proof_ref is None


def test_proof_adapter_torn_proof_read_is_flagged() -> None:
    calls = {"n": 0}

    def provider(proof_id: str):
        calls["n"] += 1
        return _proof_record("d" * 64) if calls["n"] <= 2 else _proof_record("e" * 64)

    adapter = ProofAdapter(
        proof_provider=provider,
        registry=_registry({"C2": _accepted_c2_row()}),
    )
    read = adapter.read("proof-1", "chain:session")
    assert read.torn is True
    assert read.version_vector.before != read.version_vector.after


def test_runtime_adapter_unapproved_handoff_is_unknown_with_no_refs() -> None:
    adapter = RuntimeAdapter(
        runtime_provider=lambda hid, subject: _proof_record("d" * 64),
        registry=_registry(),
        environment="production",
    )
    for handoff_id in ("S1", "S2R"):
        read = adapter.read(handoff_id, "chain:session")
        assert isinstance(read, RuntimeRead)
        assert read.handoff.state is HandoffResolutionState.UNKNOWN
        assert read.runtime_ref is None and read.source_ref is None
        assert adapter.probe(handoff_id, "chain:session") is None


def test_runtime_adapter_accepted_read_emits_runtime_and_source_refs() -> None:
    adapter = RuntimeAdapter(
        runtime_provider=lambda hid, subject: _proof_record("d" * 64),
        source_provider=lambda hid, subject: _Evidence("source-manifest"),
        registry=_registry(
            {
                "S1": _accepted_runtime_row("S1"),
                "S2R": _accepted_runtime_row("S2R"),
            }
        ),
        environment="production",
    )
    for handoff_id in ("S1", "S2R"):
        read = adapter.read(handoff_id, "chain:session")
        assert read.handoff.state is HandoffResolutionState.ACCEPTED
        assert read.runtime_ref is not None
        assert read.runtime_ref.locator == f"{RUNTIME_SOURCE_PATHS[handoff_id]}//chain:session"
        assert read.source_ref is not None
        assert read.torn is False
        assert adapter.probe(handoff_id, "chain:session") == "d" * 64
    _assert_no_mutation_surface(adapter)


def test_runtime_adapter_rejects_unknown_handoff_id() -> None:
    adapter = RuntimeAdapter(
        runtime_provider=lambda hid, subject: _proof_record("d" * 64),
        registry=_registry(),
    )
    with pytest.raises(ValueError, match="unknown runtime handoff id"):
        adapter.read("S9", "chain:session")
    assert adapter.probe("S9", "chain:session") is None


def test_view_rejects_drift_that_does_not_cover_every_source() -> None:
    registry = _registry()
    incomplete = list(registry.recorded_drift())[:-1]
    with pytest.raises(ValueError, match="drift must cover exactly"):
        build_handoff_view(registry=registry, drift=incomplete)
