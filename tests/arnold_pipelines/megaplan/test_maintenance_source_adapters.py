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

import re
from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import SourceVersionVector
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HANDOFF_IDS,
    ApprovalState,
    HandoffRegistry,
    HandoffResolutionReason,
    HandoffResolutionState,
    HandoffRow,
    WbcCoordinates,
    build_handoff_view,
    default_handoff_registry,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    canonical_digest,
    canonical_dumps,
)
from arnold_pipelines.megaplan.maintenance.sources import (
    ConformanceAdapter,
    CustodyAdapter,
    NativeManifestAdapter,
    RunAuthorityAdapter,
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
                    schema_identity=f"schema-{hid}",
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
) -> HandoffRow:
    return HandoffRow(
        id=handoff_id,
        source_path=source_path,
        schema_identity=schema_identity,
        digest=digest,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=(handoff_id == "M6A"),
        wbc_coordinates=wbc,
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
