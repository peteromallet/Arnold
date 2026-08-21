"""Focused proof tests for the M5 exact-version owner read adapters (Steps 7-9).

Proves the read-only injected query adapters over Run Authority accepted
outcomes and WBC/work evidence (Step 7 / T7), Custody and Native
proof/quality evidence (Step 8 / T8), and the open-ticket snapshot and
dispatch-receipt high-water reads (Step 9 / T9):

* reads return immutable locators, digests, cursors, and before/after source
  versions — owner payloads are never embedded or copied;
* version tears and mid-read mutations yield typed ``INCOHERENT`` facts with
  ``VERSION_TEAR`` and exact before/after coordinates preserved;
* WBC cursor gaps yield typed ``INCOHERENT`` facts with ``CURSOR_GAP``;
* unavailable sources yield typed ``UNKNOWN`` facts with
  ``SOURCE_UNAVAILABLE`` and no evidence references;
* open-ticket snapshots prove exact-version ticket identity (including the
  stable no-match identity) and torn ticket reads are typed UNKNOWN;
* dispatch-receipt reads carry byte/row high-water coordinates plus
  before/after file stats, with mid-read mutation and cursor mismatch typed
  UNKNOWN;
* active repair custody is retained only as reference/covariate coordinates
  (``repair_custody`` owner refs), never claimed;
* reads call ONLY the named read/query/version APIs (no mutation surface)
  and digests are stable/replayable across identical inputs.

The adapters reuse the existing before/after source coordinates
(:class:`SourceVersionVector`, :class:`WbcEventRef`,
:class:`SourceCursorRef`) from ``maintenance/sources.py``.
"""

from __future__ import annotations

import re

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import SourceVersionVector
from arnold_pipelines.megaplan.maintenance import efficiency_analysis as ea
from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance import efficiency_sources as es
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Fakes / spies (mirror the source-adapter proof fakes)
# ---------------------------------------------------------------------------


class _Decision:
    def __init__(self, decision_id: str, payload: str = "") -> None:
        self.decision_id = decision_id
        self.payload = payload

    def to_dict(self) -> dict:
        return {"decision_id": self.decision_id, "payload": self.payload}


class _Claim:
    def __init__(self, claim_id: str, payload: str = "") -> None:
        self.claim_id = claim_id
        self.payload = payload

    def to_dict(self) -> dict:
        return {"claim_id": self.claim_id, "payload": self.payload}


class _View:
    """Minimal RunAuthorityView-shaped read source."""

    def __init__(self, view_hash: str = "a" * 64) -> None:
        self.view_hash = view_hash
        self.run_id = "run-1"
        self.run_revision = "rev-1"
        self.journal_cursor = 7
        self.evidence_set_digest = "b" * 64
        self.decisions = [_Decision("d-1", payload="DECISION-PAYLOAD")]
        self.claims = [_Claim("c-1")]
        self.grants = []
        self.fences = []
        self.attempts = []
        self.quarantines = []
        self.diagnostics = []


class _TearingViewProvider:
    """Provider whose view hash changes between the before and after reads."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> _View:
        self._calls += 1
        if self._calls == 1:
            return _View(view_hash="a" * 64)
        return _View(view_hash="c" * 64)


class _BrokenProvider:
    def __call__(self) -> _View:
        raise RuntimeError("source unavailable")


class _Lease:
    def __init__(self, lease_id: str, payload: str = "") -> None:
        self.lease_id = lease_id
        self.payload = payload

    def to_dict(self) -> dict:
        return {"lease_id": self.lease_id, "payload": self.payload}


class _EventType:
    def __init__(self, value: str) -> None:
        self.value = value


class _Event:
    def __init__(
        self, sequence: int, event_type: str = "started", idempotency_key: str | None = None
    ) -> None:
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
    def __init__(
        self,
        cursor_key: str = "default",
        last_sequence: int = 0,
        last_position: str | None = None,
    ) -> None:
        self.cursor_key = cursor_key
        self.last_sequence = last_sequence
        self.last_position = last_position

    def to_dict(self) -> dict:
        return {
            "cursor_key": self.cursor_key,
            "last_sequence": self.last_sequence,
            "last_position": self.last_position,
        }


class _SpyStore:
    """Exposes ONLY the WBC read/query/version API surface; records calls."""

    def __init__(
        self,
        *,
        events: list[_Event] | None = None,
        ledger: _Ledger | None = None,
        gaps: list[_Gap] | None = None,
        cursor: _Cursor | None = None,
        contract: str = "c1",
        store: str = "s1",
    ) -> None:
        self._events = events if events is not None else []
        self._ledger = ledger
        self._gaps = gaps if gaps is not None else []
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
        return None

    def query_gaps(self, attempt_id: str) -> list[_Gap]:
        self.calls.append("query_gaps")
        return self._gaps

    def query_source_cursor(self, attempt_id: str, cursor_key: str) -> _Cursor | None:
        self.calls.append("query_source_cursor")
        return self._cursor


class _TearingStore(_SpyStore):
    """Store whose version advances between the before and after reads."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._version_calls = 0

    def get_store_version(self) -> str:
        self.calls.append("get_store_version")
        self._version_calls += 1
        if self._version_calls == 1:
            return "s1"
        return "s2"


class _BrokenStore(_SpyStore):
    def read_events(self, attempt_id: str) -> list[_Event]:
        self.calls.append("read_events")
        raise RuntimeError("store unavailable")


_ALLOWED_WBC_CALLS = {
    "get_contract_version",
    "get_store_version",
    "read_events",
    "read_ledger",
    "get_terminal_event",
    "query_gaps",
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


def _wbc_store(**overrides: object) -> _SpyStore:
    events = [_Event(1, "started", "key-1"), _Event(2, "completed", "key-2")]
    base: dict[str, object] = {
        "events": events,
        "ledger": _Ledger(last_event=events[-1]),
        "gaps": [],
        "cursor": _Cursor("default", 2, "pos-2"),
    }
    base.update(overrides)
    return _SpyStore(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Run Authority accepted-outcome adapter
# ---------------------------------------------------------------------------


def test_run_authority_adapter_returns_immutable_exact_version_refs() -> None:
    view = _View()
    adapter = es.RunAuthorityAcceptedOutcomeAdapter(
        lambda: view, environment="production"
    )
    read = adapter.read()

    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.disposition_reason is None
    assert read.torn is False
    assert read.run_id == "run-1"
    assert read.run_revision == "rev-1"
    assert read.journal_cursor == 7
    assert read.environment is not None and read.environment.root == "production"
    # Exact before/after source versions are captured around the read.
    assert read.before_view_hash == "a" * 64
    assert read.after_view_hash == "a" * 64
    vector = read.version_vector
    assert isinstance(vector, SourceVersionVector)
    assert vector.owner == "run_authority"
    assert vector.before == "a" * 64
    assert vector.after == "a" * 64

    # Immutable locators/digests/cursors for every accepted outcome.
    assert len(read.accepted_outcome_refs) == 2
    decision = next(
        ref for ref in read.accepted_outcome_refs if ref.record_type == "decision"
    )
    assert decision.owner == "run_authority"
    assert decision.identity == "run-1"
    assert decision.locator == "decision://d-1"
    assert _SHA256.fullmatch(decision.digest or "")
    assert decision.cursor == "journal:7"
    claim = next(ref for ref in read.accepted_outcome_refs if ref.record_type == "claim")
    assert claim.locator == "claim://c-1"

    # The owner record payload is never embedded in the read result.
    dumped = canonical_dumps(read)
    assert "DECISION-PAYLOAD" not in dumped

    # Replayable digest and frozen immutability.
    assert read.digest == canonical_digest(read)
    read2 = adapter.read()
    assert read2.digest == read.digest
    with pytest.raises(Exception):
        read.journal_cursor = 99  # type: ignore[misc]
    _assert_no_mutation_surface(adapter)


def test_run_authority_version_tear_is_typed_incoherent() -> None:
    adapter = es.RunAuthorityAcceptedOutcomeAdapter(_TearingViewProvider())
    read = adapter.read()
    assert read.disposition is es.SourceReadDisposition.INCOHERENT
    assert read.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert read.torn is True
    # Exact before/after versions are preserved for the join to inspect.
    assert read.before_view_hash == "a" * 64
    assert read.after_view_hash == "c" * 64
    assert read.version_vector.before == "a" * 64
    assert read.version_vector.after == "c" * 64
    # The torn read still carries its references but can never support a
    # finding (disposition is INCOHERENT).
    assert len(read.accepted_outcome_refs) == 2


def test_run_authority_unavailable_source_is_typed_unknown() -> None:
    adapter = es.RunAuthorityAcceptedOutcomeAdapter(_BrokenProvider())
    read = adapter.read()
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.SOURCE_UNAVAILABLE
    assert read.torn is False
    assert read.accepted_outcome_refs == ()
    assert read.before_view_hash is None
    assert read.after_view_hash is None


def test_run_authority_active_custody_is_reference_only() -> None:
    view = _View()
    adapter = es.RunAuthorityAcceptedOutcomeAdapter(
        lambda: view,
        active_custody_provider=lambda: [_Lease("lease-1", payload="LEASE-PAYLOAD")],
    )
    read = adapter.read()
    assert read.active_custody_present is True
    assert len(read.active_custody_refs) == 1
    custody = read.active_custody_refs[0]
    assert custody.owner == "repair_custody"
    assert custody.record_type == "active_lease"
    assert custody.locator == "repair-custody://lease-1"
    assert _SHA256.fullmatch(custody.digest or "")
    # The lease payload is never embedded.
    assert "LEASE-PAYLOAD" not in canonical_dumps(read)


def test_run_authority_no_active_custody_is_explicit_absence() -> None:
    read = es.RunAuthorityAcceptedOutcomeAdapter(lambda: _View()).read()
    assert read.active_custody_present is False
    assert read.active_custody_refs == ()
    assert '"active_custody_refs":[]' in canonical_dumps(read)


def test_run_authority_read_round_trips_through_strict_decode() -> None:
    read = es.RunAuthorityAcceptedOutcomeAdapter(lambda: _View()).read()
    decoded = strict_loads(es.RunAuthorityAcceptedOutcomeRead, canonical_dumps(read))
    assert decoded == read
    assert decoded.digest == read.digest


def test_run_authority_unknown_read_rejects_evidence_refs() -> None:
    with pytest.raises(ValueError):
        es.RunAuthorityAcceptedOutcomeRead(
            version_vector=SourceVersionVector(owner="run_authority", source="run_authority.view"),
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.SOURCE_UNAVAILABLE,
            accepted_outcome_refs=[OwnerRef(owner="run_authority", locator="decision://d-1")],
        )


def test_run_authority_torn_model_requires_matching_disposition() -> None:
    with pytest.raises(ValueError):
        es.RunAuthorityAcceptedOutcomeRead(
            run_id="run-1",
            run_revision="rev-1",
            journal_cursor=7,
            before_view_hash="a" * 64,
            after_view_hash="c" * 64,
            version_vector=SourceVersionVector(
                owner="run_authority",
                source="run_authority.view",
                before="a" * 64,
                after="c" * 64,
            ),
            torn=True,
            disposition=es.SourceReadDisposition.COHERENT,
        )


# ---------------------------------------------------------------------------
# WBC work-evidence adapter
# ---------------------------------------------------------------------------


def test_wbc_adapter_returns_immutable_exact_version_refs() -> None:
    store = _wbc_store()
    adapter = es.WbcWorkEvidenceAdapter(store, environment="production")
    read = adapter.read("att-1")

    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.disposition_reason is None
    assert read.torn is False
    assert read.attempt_id == "att-1"
    assert read.environment is not None and read.environment.root == "production"
    # Exact before/after source versions are captured around the read.
    assert read.contract_version_before == "c1"
    assert read.contract_version_after == "c1"
    assert read.store_version_before == "s1"
    assert read.store_version_after == "s1"
    vector = read.version_vector
    assert vector.owner == "wbc"
    assert vector.before == "contract:c1|store:s1"
    assert vector.after == "contract:c1|store:s1"

    # Immutable locators/digests/cursors for events, ledger, and cursor.
    assert [ref.sequence for ref in read.event_refs] == [1, 2]
    assert read.event_refs[0].locator == "wbc://att-1/1"
    assert _SHA256.fullmatch(read.event_refs[0].digest)
    assert read.ledger_ref is not None
    assert read.ledger_ref.owner == "wbc"
    assert read.ledger_ref.locator == "ledger://att-1"
    assert read.source_cursor is not None
    assert read.source_cursor.cursor_key == "default"
    assert read.source_cursor.last_sequence == 2
    assert read.gap_refs == ()

    # Only the named read/query/version APIs were called.
    assert set(store.calls) <= _ALLOWED_WBC_CALLS

    # Replayable digest and frozen immutability.
    assert read.digest == canonical_digest(read)
    assert adapter.read("att-1").digest == read.digest
    with pytest.raises(Exception):
        read.attempt_id = "other"  # type: ignore[misc]
    _assert_no_mutation_surface(adapter)


def test_wbc_cursor_gap_is_typed_incoherent() -> None:
    store = _wbc_store(gaps=[_Gap(1, 2)])
    read = es.WbcWorkEvidenceAdapter(store).read("att-1")
    assert read.disposition is es.SourceReadDisposition.INCOHERENT
    assert read.disposition_reason is es.SourceReadFailure.CURSOR_GAP
    assert read.torn is False
    assert len(read.gap_refs) == 1
    gap = read.gap_refs[0]
    assert gap.owner == "wbc"
    assert gap.record_type == "gap"
    assert gap.locator == "gap://att-1/1:2"
    assert read.contract_version_before == "c1"
    assert read.contract_version_after == "c1"


def test_wbc_version_tear_is_typed_incoherent() -> None:
    store = _TearingStore()
    read = es.WbcWorkEvidenceAdapter(store).read("att-1")
    assert read.disposition is es.SourceReadDisposition.INCOHERENT
    assert read.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert read.torn is True
    assert read.store_version_before == "s1"
    assert read.store_version_after == "s2"
    assert read.version_vector.before == "contract:c1|store:s1"
    assert read.version_vector.after == "contract:c1|store:s2"


def test_wbc_unavailable_source_is_typed_unknown() -> None:
    store = _BrokenStore()
    read = es.WbcWorkEvidenceAdapter(store).read("att-1")
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.SOURCE_UNAVAILABLE
    assert read.torn is False
    assert read.event_refs == ()
    assert read.ledger_ref is None
    assert read.source_cursor is None
    assert read.contract_version_before is None
    assert read.contract_version_after is None


def test_wbc_active_custody_is_reference_only() -> None:
    store = _wbc_store()
    adapter = es.WbcWorkEvidenceAdapter(
        store,
        active_custody_provider=lambda: [_Lease("lease-9", payload="LEASE-PAYLOAD")],
    )
    read = adapter.read("att-1")
    assert read.active_custody_present is True
    custody = read.active_custody_refs[0]
    assert custody.owner == "repair_custody"
    assert custody.locator == "repair-custody://lease-9"
    assert "LEASE-PAYLOAD" not in canonical_dumps(read)


def test_wbc_read_round_trips_through_strict_decode() -> None:
    read = es.WbcWorkEvidenceAdapter(_wbc_store()).read("att-1")
    decoded = strict_loads(es.WbcWorkEvidenceRead, canonical_dumps(read))
    assert decoded == read
    assert decoded.digest == read.digest


def test_wbc_cursor_gap_model_requires_gap_refs() -> None:
    with pytest.raises(ValueError):
        es.WbcWorkEvidenceRead(
            attempt_id="att-1",
            contract_version_before="c1",
            contract_version_after="c1",
            store_version_before="s1",
            store_version_after="s1",
            version_vector=SourceVersionVector(
                owner="wbc",
                source="wbc.attempt_ledger_store",
                before="contract:c1|store:s1",
                after="contract:c1|store:s1",
            ),
            disposition=es.SourceReadDisposition.INCOHERENT,
            disposition_reason=es.SourceReadFailure.CURSOR_GAP,
        )


def test_wbc_torn_model_requires_matching_disposition() -> None:
    with pytest.raises(ValueError):
        es.WbcWorkEvidenceRead(
            attempt_id="att-1",
            contract_version_before="c1",
            contract_version_after="c1",
            store_version_before="s1",
            store_version_after="s2",
            version_vector=SourceVersionVector(
                owner="wbc",
                source="wbc.attempt_ledger_store",
                before="contract:c1|store:s1",
                after="contract:c1|store:s2",
            ),
            torn=True,
            disposition=es.SourceReadDisposition.COHERENT,
        )


class _MutatingWbcStore(_SpyStore):
    """Required WBC reads plus a writer; must be refused at construction."""

    def append(self, *_args: object, **_kwargs: object) -> None:
        self.calls.append("append")


class _MutatingCallableProvider:
    """Callable read provider that also exposes a writer method."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, *_args: object, **_kwargs: object) -> object:
        self.calls.append("__call__")
        raise AssertionError("mutation-capable provider must not be invoked")

    def append(self, *_args: object, **_kwargs: object) -> None:
        self.calls.append("append")


def _public_callables(obj: object) -> set[str]:
    return {
        name
        for name in dir(obj)
        if not name.startswith("_") and callable(getattr(obj, name, None))
    }


def test_wbc_mutation_capable_store_is_rejected_before_any_read() -> None:
    store = _MutatingWbcStore()
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.WbcWorkEvidenceAdapter(store)
    assert store.calls == []
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.read_wbc_work_evidence(store, "att-1")
    assert store.calls == []


def test_wbc_pure_read_store_is_sealed_and_not_retained() -> None:
    store = _wbc_store()
    adapter = es.WbcWorkEvidenceAdapter(store)
    assert adapter._store is not store
    assert _public_callables(adapter._store) == _ALLOWED_WBC_CALLS
    read = adapter.read("att-1")
    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert set(store.calls) <= _ALLOWED_WBC_CALLS
    assert "append" not in store.calls


def test_sibling_callable_provider_with_writer_is_rejected() -> None:
    provider = _MutatingCallableProvider()
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.OpenTicketLookupAdapter(provider)
    assert provider.calls == []
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.RunAuthorityAcceptedOutcomeAdapter(provider)
    assert provider.calls == []
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.DispatchReceiptsAdapter(provider)
    assert provider.calls == []
    with pytest.raises(es.ProviderAdmissionError, match="append"):
        es.NativeProofQualityAdapter(proof_provider=provider)
    assert provider.calls == []


def test_all_source_adapters_use_the_same_sealed_admission_boundary() -> None:
    mutating_store = _MutatingWbcStore()
    mutating_callable = _MutatingCallableProvider()

    class _MutatingCustodyProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def load_history(self, lease_id: str) -> list[object]:
            self.calls.append("load_history")
            return []

        def replay_history(self, lease_id: str) -> None:
            self.calls.append("replay_history")
            return None

        def append(self, *_args: object, **_kwargs: object) -> None:
            self.calls.append("append")

    mutating_custody = _MutatingCustodyProvider()

    refusals: list[object] = []
    constructors = (
        lambda: es.WbcWorkEvidenceAdapter(mutating_store),
        lambda: es.CustodyLeaseHistoryAdapter(mutating_custody),
        lambda: es.RunAuthorityAcceptedOutcomeAdapter(mutating_callable),
        lambda: es.OpenTicketLookupAdapter(mutating_callable),
        lambda: es.DispatchReceiptsAdapter(mutating_callable),
        lambda: es.NativeProofQualityAdapter(proof_provider=mutating_callable),
        lambda: es.RunAuthorityAcceptedOutcomeAdapter(
            lambda: _View(),
            active_custody_provider=mutating_callable,
        ),
        lambda: es.WbcWorkEvidenceAdapter(
            _wbc_store(),
            active_custody_provider=mutating_callable,
        ),
    )
    for construct in constructors:
        with pytest.raises(es.ProviderAdmissionError):
            construct()
        refusals.append(True)
    assert len(refusals) == 8
    assert mutating_store.calls == []
    assert mutating_custody.calls == []
    assert mutating_callable.calls == []

    sealed = es.WbcWorkEvidenceAdapter(_wbc_store())
    assert _public_callables(sealed._store) == _ALLOWED_WBC_CALLS


# ---------------------------------------------------------------------------
# Convenience entry points
# ---------------------------------------------------------------------------


def test_convenience_readers_match_adapter_results() -> None:
    view = _View()
    ra = es.read_run_authority_accepted_outcomes(lambda: view)
    assert ra == es.RunAuthorityAcceptedOutcomeAdapter(lambda: view).read()
    store = _wbc_store()
    wbc = es.read_wbc_work_evidence(store, "att-1")
    assert wbc == es.WbcWorkEvidenceAdapter(store).read("att-1")
    assert wbc.disposition is es.SourceReadDisposition.COHERENT


# ---------------------------------------------------------------------------
# Custody lease/history adapter (Step 8 / T8)
# ---------------------------------------------------------------------------


class _LeaseEvent:
    """Minimal CustodyLeaseEvent-shaped read record (locator-only capture)."""

    def __init__(
        self,
        sequence: int,
        event_type: str = "acquire",
        payload: dict | None = None,
    ) -> None:
        self.event_id = f"evt-{sequence}"
        self.lease_id = "lease-1"
        self.sequence = sequence
        self.event_type = event_type
        self.occurred_at = "2026-08-18T00:00:00Z"
        self.custody_epoch = 1
        self.owner_host = "host-1"
        self.owner_pid = "pid-1"
        self.owner_boot_id = "boot-1"
        self.run_authority_grant_id = "grant-1"
        self.coordinator_fence_token = 7
        self.wbc_attempt_reference = "att-1"
        self.occurrence_digest = "d" * 64
        self.idempotency_key = f"key-{sequence}"
        self.causal_predecessor = ""
        self.payload = payload or {}
        self.payload_hash = "e" * 64

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "lease_id": self.lease_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "custody_epoch": self.custody_epoch,
            "owner_host": self.owner_host,
            "owner_pid": self.owner_pid,
            "owner_boot_id": self.owner_boot_id,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "occurrence_digest": self.occurrence_digest,
            "idempotency_key": self.idempotency_key,
            "causal_predecessor": self.causal_predecessor,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
        }


class _CustodyLease:
    """Minimal CustodyLease-shaped current state record."""

    def __init__(self, lease_id: str = "lease-1") -> None:
        self.lease_id = lease_id
        self.occurrence_key = {"target": {"environment": "production"}, "run_id": "run-1"}
        self.owner_host = "host-1"
        self.owner_pid = "pid-1"
        self.owner_boot_id = "boot-1"
        self.run_authority_grant_id = "grant-1"
        self.coordinator_fence_token = 7
        self.wbc_attempt_reference = "att-1"
        self.custody_epoch = 1
        self.acquired_at = "2026-08-18T00:00:00Z"
        self.expires_at = "2026-08-18T01:00:00Z"
        self.idempotency_key = "key-1"
        self.causal_predecessor = ""

    def to_dict(self) -> dict:
        return {
            "lease_id": self.lease_id,
            "occurrence_key": self.occurrence_key,
            "owner_host": self.owner_host,
            "owner_pid": self.owner_pid,
            "owner_boot_id": self.owner_boot_id,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "custody_epoch": self.custody_epoch,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "idempotency_key": self.idempotency_key,
            "causal_predecessor": self.causal_predecessor,
        }


class _CustodyStore:
    """Exposes ONLY the custody read/replay API surface; records calls."""

    def __init__(
        self,
        *,
        events: list[_LeaseEvent] | None = None,
        lease: _CustodyLease | None = None,
        environment: str | None = None,
    ) -> None:
        self._events = events if events is not None else []
        self._lease = lease
        self.environment = environment
        self.calls: list[str] = []

    def load_history(self, lease_id: str) -> list[_LeaseEvent]:
        self.calls.append("load_history")
        return list(self._events)

    def replay_history(self, lease_id: str) -> _CustodyLease | None:
        self.calls.append("replay_history")
        return self._lease


class _TearingCustodyStore(_CustodyStore):
    """Store whose history grows between the before and after reads."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._load_calls = 0

    def load_history(self, lease_id: str) -> list[_LeaseEvent]:
        self.calls.append("load_history")
        self._load_calls += 1
        if self._load_calls == 1:
            return list(self._events)
        return list(self._events) + [_LeaseEvent(99, "renew")]


class _BrokenCustodyStore(_CustodyStore):
    def load_history(self, lease_id: str) -> list[_LeaseEvent]:
        self.calls.append("load_history")
        raise RuntimeError("custody store unavailable")


_CUSTODY_READ_CALLS = {"load_history", "replay_history"}

_CUSTODY_MUTATION_VERBS = (
    "acquire",
    "renew",
    "transfer",
    "release",
    "expire",
    "fence",
    "reclaim",
    "record_event",
    "write",
    "delete",
    "append",
)


def _assert_no_custody_mutation_surface(adapter: object) -> None:
    for name in dir(adapter):
        if name.startswith("_"):
            continue
        if not callable(getattr(adapter, name, None)):
            continue
        low = name.lower()
        assert not any(verb in low for verb in _CUSTODY_MUTATION_VERBS), (
            f"custody adapter exposes a mutation surface: {name}"
        )


def _custody_store(**overrides: object) -> _CustodyStore:
    events = [
        _LeaseEvent(1, "acquire", {"occurrence_key": {"run_id": "run-1"}}),
        _LeaseEvent(2, "renew"),
    ]
    base: dict[str, object] = {
        "events": events,
        "lease": _CustodyLease(),
        "environment": None,
    }
    base.update(overrides)
    return _CustodyStore(**base)  # type: ignore[arg-type]


def test_custody_adapter_returns_locator_only_lease_and_history_refs() -> None:
    store = _custody_store()
    adapter = es.CustodyLeaseHistoryAdapter(store, environment="production")
    read = adapter.read("lease-1")

    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.disposition_reason is None
    assert read.torn is False
    assert read.lease_id == "lease-1"
    assert read.environment is not None and read.environment.root == "production"
    # Exact before/after history digests are captured around the read.
    assert read.history_version_before == read.history_version_after
    assert len(read.history_version_before or "") == 64
    vector = read.version_vector
    assert vector.owner == "custody"
    assert vector.source == "custody.lease_store"
    assert vector.before == read.history_version_before
    assert vector.after == read.history_version_after

    # Active custody availability is retained as a typed flag.
    assert read.active_lease_present is True
    assert read.lease_ref is not None
    assert read.lease_ref.owner == "custody"
    assert read.lease_ref.record_type == "lease"
    assert read.lease_ref.locator == "custody://lease-1"
    assert _SHA256.fullmatch(read.lease_ref.digest or "")

    # Locator-only history event refs — the lease payload is never embedded.
    assert [ref.record_type for ref in read.history_refs] == [
        "lease_event",
        "lease_event",
    ]
    assert read.history_refs[0].locator == "custody://lease-1/1"
    assert read.history_refs[1].locator == "custody://lease-1/2"
    dumped = canonical_dumps(read)
    assert '"occurrence_key"' not in dumped
    assert '"owner_boot_id"' not in dumped

    # Only the named read/replay APIs were called.
    assert set(store.calls) <= _CUSTODY_READ_CALLS
    assert adapter._store is not store
    assert _public_callables(adapter._store) == _CUSTODY_READ_CALLS

    # Replayable digest and frozen immutability; no mutation surface.
    assert read.digest == canonical_digest(read)
    assert adapter.read("lease-1").digest == read.digest
    with pytest.raises(Exception):
        read.lease_id = "other"  # type: ignore[misc]
    _assert_no_custody_mutation_surface(adapter)


def test_custody_terminated_lease_is_not_active_but_still_referenced() -> None:
    for terminal in ("release", "expire", "fence"):
        events = [_LeaseEvent(1, "acquire"), _LeaseEvent(2, terminal)]
        read = es.CustodyLeaseHistoryAdapter(
            _custody_store(events=events, lease=_CustodyLease())
        ).read("lease-1")
        assert read.disposition is es.SourceReadDisposition.COHERENT
        assert read.active_lease_present is False
        # The terminated lease state is still referenced (append-only history).
        assert read.lease_ref is not None


def test_custody_absent_lease_is_explicit_coherent_absence() -> None:
    store = _CustodyStore(events=[], lease=None)
    read = es.CustodyLeaseHistoryAdapter(store).read("lease-1")
    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.active_lease_present is False
    assert read.lease_ref is None
    assert read.history_refs == ()
    assert read.conflict_count == 0


def test_custody_conflict_count_is_retained() -> None:
    events = [
        _LeaseEvent(1, "acquire"),
        _LeaseEvent(2, "conflict", {"quarantined": True}),
    ]
    read = es.CustodyLeaseHistoryAdapter(
        _custody_store(events=events, lease=_CustodyLease())
    ).read("lease-1")
    assert read.conflict_count == 1
    assert read.active_lease_present is True  # conflict is not a terminal event


def test_custody_missing_cost_quality_model_are_typed_unknown() -> None:
    read = es.CustodyLeaseHistoryAdapter(_custody_store()).read("lease-1")
    assert read.cost is None
    assert read.quality is None
    assert read.model is None
    assert set(read.unknown_evidence) == {
        es.EvidenceUnknownKind.COST,
        es.EvidenceUnknownKind.QUALITY,
        es.EvidenceUnknownKind.MODEL,
    }
    # Explicit nulls, never zero — the typed-unknown contract survives strict
    # decode.
    decoded = strict_loads(es.CustodyLeaseHistoryRead, canonical_dumps(read))
    assert decoded.cost is None
    assert decoded.quality is None
    assert decoded.model is None
    assert set(decoded.unknown_evidence) == set(read.unknown_evidence)


def test_custody_version_tear_is_typed_incoherent() -> None:
    store = _TearingCustodyStore()
    read = es.CustodyLeaseHistoryAdapter(store).read("lease-1")
    assert read.disposition is es.SourceReadDisposition.INCOHERENT
    assert read.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert read.torn is True
    assert read.history_version_before != read.history_version_after
    assert read.version_vector.before != read.version_vector.after


def test_custody_unavailable_source_is_typed_unknown() -> None:
    read = es.CustodyLeaseHistoryAdapter(_BrokenCustodyStore()).read("lease-1")
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.SOURCE_UNAVAILABLE
    assert read.torn is False
    assert read.lease_ref is None
    assert read.history_refs == ()
    assert read.history_version_before is None
    assert read.history_version_after is None


def test_custody_cross_environment_join_fails_closed() -> None:
    store = _custody_store(environment="staging")
    read = es.CustodyLeaseHistoryAdapter(store, environment="production").read(
        "lease-1"
    )
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.CROSS_ENVIRONMENT
    assert read.lease_ref is None
    assert read.history_refs == ()
    # Same-environment joins stay coherent.
    coherent = es.CustodyLeaseHistoryAdapter(
        store, environment="staging"
    ).read("lease-1")
    assert coherent.disposition is es.SourceReadDisposition.COHERENT


def test_custody_read_round_trips_through_strict_decode() -> None:
    read = es.CustodyLeaseHistoryAdapter(_custody_store()).read("lease-1")
    decoded = strict_loads(es.CustodyLeaseHistoryRead, canonical_dumps(read))
    assert decoded == read
    assert decoded.digest == read.digest


def test_custody_model_rejects_inconsistent_states() -> None:
    vector = SourceVersionVector(owner="custody", source="custody.lease_store")
    with pytest.raises(ValueError):
        es.CustodyLeaseHistoryRead(
            lease_id="lease-1",
            version_vector=vector,
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.SOURCE_UNAVAILABLE,
            lease_ref=OwnerRef(owner="custody", locator="custody://lease-1"),
        )
    with pytest.raises(ValueError):
        es.CustodyLeaseHistoryRead(
            lease_id="lease-1",
            history_version_before="a" * 64,
            history_version_after="b" * 64,
            version_vector=SourceVersionVector(
                owner="custody",
                source="custody.lease_store",
                before="a" * 64,
                after="b" * 64,
            ),
            torn=True,
            disposition=es.SourceReadDisposition.COHERENT,
        )
    with pytest.raises(ValueError):
        es.CustodyLeaseHistoryRead(
            lease_id="lease-1",
            history_version_before="a" * 64,
            history_version_after="a" * 64,
            version_vector=vector,
            active_lease_present=True,
        )
    with pytest.raises(ValueError):
        es.CustodyLeaseHistoryRead(
            lease_id="lease-1",
            history_version_before="a" * 64,
            history_version_after="a" * 64,
            version_vector=vector,
            cost=1.0,
            unknown_evidence=[es.EvidenceUnknownKind.COST],
        )


# ---------------------------------------------------------------------------
# Native proof/quality adapter (Step 8 / T8)
# ---------------------------------------------------------------------------


class _Proof:
    """Minimal Native C2 negative-control proof-shaped record."""

    def __init__(self, proof_id: str, payload: str = "PROOF-PAYLOAD") -> None:
        self.proof_id = proof_id
        self.schema_identity = "c2.v1"
        self.identity = "subject-1"
        self.payload = payload

    def to_dict(self) -> dict:
        return {
            "proof_id": self.proof_id,
            "schema_identity": self.schema_identity,
            "identity": self.identity,
            "payload": self.payload,
        }


class _QualityRecord:
    """Minimal Native quality-shaped record with optional cost/quality/model."""

    def __init__(
        self,
        *,
        cost: float | None = None,
        quality: float | None = None,
        model: str | None = None,
        payload: str = "QUALITY-PAYLOAD",
    ) -> None:
        self.cost = cost
        self.quality_score = quality
        self.model = model
        self.payload = payload

    def to_dict(self) -> dict:
        return {
            "cost": self.cost,
            "quality_score": self.quality_score,
            "model": self.model,
            "payload": self.payload,
        }


class _SensitiveRecord:
    def __init__(self, index: int, payload: str = "SENSITIVE-PROMPT") -> None:
        self.index = index
        self.payload = payload

    def to_dict(self) -> dict:
        return {"index": self.index, "payload": self.payload}


class _TearingProofProvider:
    """Provider whose proof record changes between the before and after reads."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self, proof_id: str) -> _Proof:
        self._calls += 1
        if self._calls == 1:
            return _Proof(proof_id, payload="BEFORE-PAYLOAD")
        return _Proof(proof_id, payload="AFTER-PAYLOAD")


class _BrokenProofProvider:
    def __call__(self, proof_id: str) -> _Proof:
        raise RuntimeError("native source unavailable")


class _EnvironmentDeclaringProvider:
    """Provider that declares an owner environment for join checks."""

    def __init__(self, environment: str) -> None:
        self.environment = environment

    def __call__(self, proof_id: str) -> _Proof:
        return _Proof(proof_id)


def _native_adapter(
    *,
    proof_provider=None,
    quality_provider=None,
    sensitive_provider=None,
    environment=None,
) -> es.NativeProofQualityAdapter:
    return es.NativeProofQualityAdapter(
        proof_provider=proof_provider or (lambda pid: _Proof(pid)),
        quality_provider=quality_provider,
        sensitive_provider=sensitive_provider,
        environment=environment,
    )


def test_native_adapter_returns_locator_only_proof_and_quality_refs() -> None:
    quality = _QualityRecord(cost=12.5, quality=0.9, model="model-1")
    adapter = _native_adapter(
        quality_provider=lambda pid: quality, environment="production"
    )
    read = adapter.read("proof-1", "subject-1")

    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.disposition_reason is None
    assert read.torn is False
    assert read.environment is not None and read.environment.root == "production"
    # Exact before/after proof digests are captured around the read.
    assert read.proof_version_before == read.proof_version_after
    vector = read.version_vector
    assert vector.owner == "native_manifest"
    assert vector.source == "native/proof_quality"

    # Locator-only proof/quality refs — records are never embedded.
    assert read.proof_ref is not None
    assert read.proof_ref.owner == "native_manifest"
    assert read.proof_ref.record_type == "negative_control_proof"
    assert read.proof_ref.locator == "native/proof_quality//subject-1"
    assert _SHA256.fullmatch(read.proof_ref.digest or "")
    assert len(read.quality_refs) == 1
    assert read.quality_refs[0].record_type == "quality"
    dumped = canonical_dumps(read)
    assert "PROOF-PAYLOAD" not in dumped
    assert "QUALITY-PAYLOAD" not in dumped

    # Present cost/quality/model are carried exactly; nothing is unknown.
    assert read.cost == 12.5
    assert read.quality == 0.9
    assert read.model is not None and read.model.root == "model-1"
    assert read.unknown_evidence == ()

    # Replayable digest and no mutation surface.
    assert read.digest == canonical_digest(read)
    assert adapter.read("proof-1", "subject-1").digest == read.digest
    _assert_no_mutation_surface(adapter)


def test_native_missing_cost_quality_model_are_typed_unknown() -> None:
    read = _native_adapter(quality_provider=lambda pid: _QualityRecord()).read(
        "proof-1", "subject-1"
    )
    assert read.cost is None
    assert read.quality is None
    assert read.model is None
    assert set(read.unknown_evidence) == {
        es.EvidenceUnknownKind.COST,
        es.EvidenceUnknownKind.QUALITY,
        es.EvidenceUnknownKind.MODEL,
    }


def test_native_absent_quality_record_is_typed_unknown() -> None:
    read = _native_adapter().read("proof-1", "subject-1")
    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.quality_refs == ()
    assert read.cost is None
    assert read.quality is None
    assert read.model is None
    assert set(read.unknown_evidence) == {
        es.EvidenceUnknownKind.COST,
        es.EvidenceUnknownKind.QUALITY,
        es.EvidenceUnknownKind.MODEL,
    }


def test_native_sensitive_evidence_is_availability_plus_locator_refs() -> None:
    sensitive = [_SensitiveRecord(0, payload="SENSITIVE-PROMPT-RAW")]
    adapter = _native_adapter(sensitive_provider=lambda pid: sensitive)
    read = adapter.read("proof-1", "subject-1")
    assert read.sensitive_evidence_present is True
    assert len(read.sensitive_evidence_refs) == 1
    ref = read.sensitive_evidence_refs[0]
    assert ref.owner == "native_manifest"
    assert ref.record_type == "sensitive_evidence"
    assert ref.locator == "native/proof_quality//subject-1/sensitive/0"
    assert _SHA256.fullmatch(ref.digest or "")
    # The raw sensitive payload is never copied into the read result.
    dumped = canonical_dumps(read)
    assert "SENSITIVE-PROMPT-RAW" not in dumped


def test_native_version_tear_is_typed_incoherent() -> None:
    read = _native_adapter(proof_provider=_TearingProofProvider()).read(
        "proof-1", "subject-1"
    )
    assert read.disposition is es.SourceReadDisposition.INCOHERENT
    assert read.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert read.torn is True
    assert read.proof_version_before != read.proof_version_after


def test_native_missing_proof_is_typed_unknown_record_missing() -> None:
    read = _native_adapter(proof_provider=lambda pid: None).read("proof-1", "subject-1")
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.RECORD_MISSING
    assert read.proof_ref is None
    assert read.quality_refs == ()
    assert read.sensitive_evidence_refs == ()


def test_native_unavailable_source_is_typed_unknown() -> None:
    read = _native_adapter(proof_provider=_BrokenProofProvider()).read(
        "proof-1", "subject-1"
    )
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.SOURCE_UNAVAILABLE
    assert read.proof_ref is None
    assert read.proof_version_before is None
    assert read.proof_version_after is None


def test_native_cross_environment_join_fails_closed() -> None:
    provider = _EnvironmentDeclaringProvider("staging")
    read = _native_adapter(
        proof_provider=provider, environment="production"
    ).read("proof-1", "subject-1")
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.CROSS_ENVIRONMENT
    assert read.proof_ref is None
    coherent = _native_adapter(
        proof_provider=provider, environment="staging"
    ).read("proof-1", "subject-1")
    assert coherent.disposition is es.SourceReadDisposition.COHERENT


def test_native_read_round_trips_through_strict_decode() -> None:
    read = _native_adapter(
        quality_provider=lambda pid: _QualityRecord(cost=1.0, quality=0.5, model="m")
    ).read("proof-1", "subject-1")
    decoded = strict_loads(es.NativeProofQualityRead, canonical_dumps(read))
    assert decoded == read
    assert decoded.digest == read.digest
    assert decoded.cost == 1.0


def test_native_model_rejects_inconsistent_states() -> None:
    vector = SourceVersionVector(owner="native_manifest", source="native/proof_quality")
    with pytest.raises(ValueError):
        es.NativeProofQualityRead(
            proof_id="proof-1",
            subject="subject-1",
            version_vector=vector,
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.RECORD_MISSING,
            proof_ref=OwnerRef(owner="native_manifest", locator="native/proof_quality//s"),
        )
    with pytest.raises(ValueError):
        es.NativeProofQualityRead(
            proof_id="proof-1",
            subject="subject-1",
            proof_version_before="a" * 64,
            proof_version_after="a" * 64,
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source="native/proof_quality",
                before="a" * 64,
                after="a" * 64,
            ),
            sensitive_evidence_present=True,
        )
    with pytest.raises(ValueError):
        es.NativeProofQualityRead(
            proof_id="proof-1",
            subject="subject-1",
            proof_version_before="a" * 64,
            proof_version_after="a" * 64,
            version_vector=vector,
            quality=1.5,
        )
    with pytest.raises(ValueError):
        es.NativeProofQualityRead(
            proof_id="proof-1",
            subject="subject-1",
            proof_version_before="a" * 64,
            proof_version_after="a" * 64,
            version_vector=vector,
            cost=3.0,
            unknown_evidence=[es.EvidenceUnknownKind.COST],
        )


def test_custody_and_native_convenience_readers_match_adapters() -> None:
    store = _custody_store()
    custody = es.read_custody_lease_history(store, "lease-1", environment="production")
    assert custody == es.CustodyLeaseHistoryAdapter(
        store, environment="production"
    ).read("lease-1")
    quality = _QualityRecord(cost=2.0, quality=0.8, model="model-1")
    native = es.read_native_proof_quality(
        "proof-1",
        "subject-1",
        proof_provider=lambda pid: _Proof(pid),
        quality_provider=lambda pid: quality,
    )
    assert native == _native_adapter(quality_provider=lambda pid: quality).read(
        "proof-1", "subject-1"
    )
    assert native.cost == 2.0


# ---------------------------------------------------------------------------
# Plan Step 9 / T9: open-ticket snapshot and dispatch-receipt high-water reads
# ---------------------------------------------------------------------------


class _FakeTicketSnapshot:
    def __init__(
        self,
        *,
        stable: bool = True,
        ticket_id: str | None = "ticket-1",
        row_count: int = 1,
        reason: str | None = None,
    ) -> None:
        before = (("t.md", 100, 10),) if ticket_id or row_count else ()
        self.ticket_id = ticket_id
        self.row_count = row_count
        self.content_digest = "a" * 64
        self.file_stats_before = before
        self.file_stats_after = before if stable else (("t.md", 200, 10),)
        self.stable = stable
        self.reason = reason


class _FakeHighWater:
    def __init__(
        self,
        *,
        stable: bool = True,
        reason: str | None = None,
        byte_high_water: int = 40,
        row_high_water: int = 2,
    ) -> None:
        self.byte_high_water = byte_high_water
        self.row_high_water = row_high_water
        self.content_digest = "b" * 64
        self.row_digests = ((1, "c" * 64), (2, "d" * 64)) if stable else ()
        self.stat_before = (100, byte_high_water)
        self.stat_after = self.stat_before if stable else (200, byte_high_water)
        self.stable = stable
        self.reason = reason


def _fake_snapshot(
    *,
    stable: bool = True,
    ticket_id: str | None = "ticket-1",
    row_count: int = 1,
    reason: str | None = None,
) -> _FakeTicketSnapshot:
    return _FakeTicketSnapshot(
        stable=stable,
        ticket_id=ticket_id,
        row_count=row_count,
        reason=reason,
    )


def _fake_high_water(
    *,
    stable: bool = True,
    reason: str | None = None,
    byte_high_water: int = 40,
    row_high_water: int = 2,
) -> _FakeHighWater:
    return _FakeHighWater(
        stable=stable,
        reason=reason,
        byte_high_water=byte_high_water,
        row_high_water=row_high_water,
    )






def test_open_ticket_no_match_is_stable_identity() -> None:
    read = es.OpenTicketLookupAdapter(
        lambda: _fake_snapshot(ticket_id=None, row_count=0),
        environment="production",
    ).read()
    assert read.disposition is es.SourceReadDisposition.COHERENT
    assert read.matched is False
    assert read.ticket_identity == es.NO_MATCH_TICKET_IDENTITY
    assert read.ticket_ref is None
    assert read.row_count == 0
    # The no-match identity is stable across strict-decode round trips.
    decoded = strict_loads(es.OpenTicketSnapshotRead, canonical_dumps(read))
    assert decoded.ticket_identity == es.NO_MATCH_TICKET_IDENTITY
    assert decoded == read


def test_open_ticket_torn_read_is_typed_unknown() -> None:
    read = es.OpenTicketLookupAdapter(
        lambda: _fake_snapshot(stable=False, ticket_id=None, row_count=0, reason="mid_read_mutation"),
        environment="production",
    ).read()
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.MID_READ_MUTATION
    assert read.ticket_identity is None
    assert read.matched is False
    assert read.ticket_ref is None
    assert read.snapshot_version_before is None
    assert read.snapshot_version_after is None



def test_open_ticket_model_rejects_inconsistent_states() -> None:
    vector = SourceVersionVector(owner="plan", source="tickets.open_ticket_snapshot")
    # UNKNOWN reads cannot carry a ticket identity.
    with pytest.raises(ValueError):
        es.OpenTicketSnapshotRead(
            environment="production",
            version_vector=vector,
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.MID_READ_MUTATION,
            ticket_identity=es.NO_MATCH_TICKET_IDENTITY,
        )
    # A coherent no-match must carry the stable no-match identity.
    with pytest.raises(ValueError):
        es.OpenTicketSnapshotRead(
            environment="production",
            snapshot_version_before="a" * 64,
            snapshot_version_after="a" * 64,
            version_vector=vector,
            ticket_identity="some-ticket",
            matched=False,
        )
    # matched=True requires a locator-only ticket_ref.
    with pytest.raises(ValueError):
        es.OpenTicketSnapshotRead(
            environment="production",
            snapshot_version_before="a" * 64,
            snapshot_version_after="a" * 64,
            version_vector=vector,
            ticket_identity="t1",
            matched=True,
        )




def test_dispatch_receipts_mid_read_mutation_is_typed_unknown() -> None:
    read = es.DispatchReceiptsAdapter(
        lambda: _fake_high_water(stable=False, reason="mid_read_mutation"),
        environment="production",
    ).read()
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.MID_READ_MUTATION
    assert read.receipt_refs == ()
    assert read.row_high_water == 0
    assert read.content_digest is None


def test_dispatch_receipts_cursor_mismatch_is_typed_unknown() -> None:
    read = es.DispatchReceiptsAdapter(
        lambda: _fake_high_water(stable=False, reason="cursor_mismatch"),
        environment="production",
    ).read()
    assert read.disposition is es.SourceReadDisposition.UNKNOWN
    assert read.disposition_reason is es.SourceReadFailure.CURSOR_MISMATCH
    assert read.receipt_refs == ()



def test_dispatch_receipt_model_rejects_inconsistent_states() -> None:
    vector = SourceVersionVector(owner="plan", source="receipts.high_water")
    # UNKNOWN reads cannot carry coordinates.
    with pytest.raises(ValueError):
        es.DispatchReceiptHighWaterRead(
            environment="production",
            version_vector=vector,
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.CURSOR_MISMATCH,
            row_high_water=1,
        )
    # CURSOR_MISMATCH must be typed UNKNOWN.
    with pytest.raises(ValueError):
        es.DispatchReceiptHighWaterRead(
            environment="production",
            file_version_before="a" * 64,
            file_version_after="a" * 64,
            version_vector=vector,
            disposition=es.SourceReadDisposition.COHERENT,
            disposition_reason=es.SourceReadFailure.CURSOR_MISMATCH,
        )


def test_open_ticket_and_receipt_adapters_have_no_mutation_surface() -> None:
    _assert_no_mutation_surface(
        es.OpenTicketLookupAdapter(lambda: _fake_snapshot())
    )
    _assert_no_mutation_surface(es.DispatchReceiptsAdapter(lambda: _fake_high_water()))



# ---------------------------------------------------------------------------
# Plan Step 10 / T10: coherent single-environment ObservationEnvelope join
# ---------------------------------------------------------------------------


class _NoAcceptedOutcomeView(_View):
    """Run Authority view carrying NO accepted decisions/claims."""

    def __init__(self, view_hash: str = "a" * 64) -> None:
        super().__init__(view_hash=view_hash)
        self.decisions = []
        self.claims = []


def _coherent_reads(**overrides: object) -> dict[str, object]:
    """Six version-coherent owner reads over the SAME environment."""
    base: dict[str, object] = {
        "accepted_outcome_read": es.RunAuthorityAcceptedOutcomeAdapter(
            lambda: _View(), environment="production"
        ).read(),
        "wbc_read": es.WbcWorkEvidenceAdapter(
            _wbc_store(), environment="production"
        ).read("attempt-1"),
        "custody_read": es.CustodyLeaseHistoryAdapter(
            _custody_store(), environment="production"
        ).read("lease-1"),
        "native_read": es.NativeProofQualityAdapter(
            proof_provider=lambda pid: _Proof(pid),
            quality_provider=lambda pid: _QualityRecord(
                cost=1.0, quality=0.9, model="model-1"
            ),
            environment="production",
        ).read("proof-1", "subject-1"),
        "ticket_read": es.OpenTicketLookupAdapter(
            lambda: _fake_snapshot(), environment="production"
        ).read(),
        "receipt_read": es.DispatchReceiptsAdapter(
            lambda: _fake_high_water(), environment="production"
        ).read(),
    }
    base.update(overrides)
    return base


def _join(**overrides: object) -> es.CoherentObservationEnvelope:
    reads = _coherent_reads(**overrides)
    return es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        **reads,  # type: ignore[arg-type]
    )


def test_envelope_join_binds_coherent_single_environment_page() -> None:
    envelope = _join(
        expected_model="model-exp",
        resolved_model="model-res",
        robustness="thorough",
        profile="profile-1",
    )
    assert envelope.disposition is es.SourceReadDisposition.COHERENT
    assert envelope.disposition_reason is None
    assert envelope.supports_finding is True
    assert envelope.supports_proposal is True
    assert not (envelope.torn or envelope.stale or envelope.incomplete or
                envelope.gapped or envelope.contaminated)

    # Normalized route/robustness/environment/classifier coordinates bind.
    assert envelope.task_or_milestone_identity == "task-m1"
    assert envelope.stage == "finalize"
    assert envelope.profile == "profile-1"
    assert envelope.expected_model is not None and envelope.expected_model.root == "model-exp"
    assert envelope.resolved_model is not None and envelope.resolved_model.root == "model-res"
    assert envelope.provider_actual_model is not None and envelope.provider_actual_model.root == "model-1"
    assert envelope.robustness is es.RobustnessKind.THOROUGH
    assert envelope.environment is not None and envelope.environment.root == "production"
    assert envelope.classifier_version == "cls-v1"

    # Exact accepted-outcome identity is bound from the Run Authority read.
    assert envelope.accepted_outcome_identity == "run-1@rev-1"

    # Owner version vectors: one per source, all single-environment.
    assert len(envelope.owner_versions) == 6
    sources = {vector.source for vector in envelope.owner_versions}
    assert sources == {
        "run_authority.view",
        "wbc.attempt_ledger_store",
        "custody.lease_store",
        "native/proof_quality",
        "tickets.open_ticket_snapshot",
        "receipts.high_water",
    }
    assert all(vector.environment is not None for vector in envelope.owner_versions)
    assert all(vector.before == vector.after for vector in envelope.owner_versions)

    # Immutable refs bind across the six owners; WBC event/cursor refs keep
    # their own typed family.
    assert envelope.immutable_refs
    owners = {ref.owner for ref in envelope.immutable_refs}
    assert "run_authority" in owners
    assert "wbc" in owners
    assert "custody" in owners
    assert "native_manifest" in owners
    assert "plan" in owners
    assert len(envelope.wbc_event_refs) == 2
    assert envelope.wbc_source_cursor is not None
    # Owner payloads are never copied into the envelope.
    dumped = canonical_dumps(envelope)
    assert "DECISION-PAYLOAD" not in dumped
    assert "PROOF-PAYLOAD" not in dumped

    # Replayable digest and strict-decode round trip.
    assert envelope.digest == canonical_digest(envelope)
    decoded = strict_loads(es.CoherentObservationEnvelope, canonical_dumps(envelope))
    assert decoded == envelope
    assert decoded.supports_finding is True
    assert decoded.supports_proposal is True


def test_envelope_join_identity_is_stable_across_identical_pages() -> None:
    first = _join()
    second = _join()
    assert first.envelope_id == second.envelope_id
    assert first.digest == second.digest
    # The identity derives from the normalized identity, not owner
    # occurrence coordinates.
    assert first.envelope_id.startswith("daily_efficiency_envelope|")
    assert "task-m1" not in first.envelope_id  # hashed, never embedded


@pytest.mark.parametrize(
    "torn_read",
    [
        es.RunAuthorityAcceptedOutcomeAdapter(
            _TearingViewProvider(), environment="production"
        ).read(),
        es.WbcWorkEvidenceAdapter(
            _TearingStore(), environment="production"
        ).read("attempt-1"),
        es.CustodyLeaseHistoryAdapter(
            _TearingCustodyStore(), environment="production"
        ).read("lease-1"),
        es.NativeProofQualityAdapter(
            proof_provider=_TearingProofProvider(), environment="production"
        ).read("proof-1", "subject-1"),
    ],
    ids=["run_authority", "wbc", "custody", "native"],
)
def test_envelope_join_any_torn_page_is_a_non_supporting_fact(torn_read: object) -> None:
    key = {
        "run_authority": "accepted_outcome_read",
        "wbc": "wbc_read",
        "custody": "custody_read",
        "native_manifest": "native_read",
    }[torn_read.version_vector.owner]  # type: ignore[attr-defined]
    envelope = _join(**{key: torn_read})
    assert envelope.disposition is es.SourceReadDisposition.INCOHERENT
    assert envelope.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert envelope.torn is True
    # SC11: a torn page supports neither a finding nor a proposal and
    # carries no owner versions or immutable references.
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.owner_versions == ()
    assert envelope.immutable_refs == ()
    assert envelope.wbc_event_refs == ()
    assert envelope.wbc_source_cursor is None


def test_envelope_join_cursor_gapped_page_is_non_supporting() -> None:
    gapped_store = _wbc_store(gaps=[_Gap(3, 5)])
    envelope = _join(
        wbc_read=es.WbcWorkEvidenceAdapter(
            gapped_store, environment="production"
        ).read("attempt-1")
    )
    assert envelope.disposition is es.SourceReadDisposition.INCOHERENT
    assert envelope.disposition_reason is es.SourceReadFailure.CURSOR_GAP
    assert envelope.gapped is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.immutable_refs == ()


def test_envelope_join_torn_ticket_and_receipt_pages_fail_closed() -> None:
    # A torn open-ticket snapshot is typed UNKNOWN/MID_READ_MUTATION.
    envelope = _join(
        ticket_read=es.OpenTicketLookupAdapter(
            lambda: _fake_snapshot(stable=False, ticket_id=None, row_count=0, reason="mid_read_mutation"),
            environment="production",
        ).read()
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.MID_READ_MUTATION
    assert envelope.gapped is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False

    # A cursor-mismatched dispatch-receipt page fails the same way.
    envelope = _join(
        receipt_read=es.DispatchReceiptsAdapter(
            lambda: _fake_high_water(stable=False, reason="cursor_mismatch"),
            environment="production",
        ).read()
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.CURSOR_MISMATCH
    assert envelope.gapped is True
    assert envelope.immutable_refs == ()


def test_envelope_join_cross_environment_contamination_fails_closed() -> None:
    # One owner declares a different environment than the rest.
    staging_custody = es.CustodyLeaseHistoryAdapter(
        _custody_store(environment="staging"), environment="production"
    ).read("lease-1")
    envelope = _join(custody_read=staging_custody)
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.CROSS_ENVIRONMENT
    assert envelope.contaminated is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.immutable_refs == ()

    # An explicitly expected environment that disagrees with the owner
    # reads is the same contamination.
    envelope = _join(
        **{
            "expected_environment": "staging",
        }
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.CROSS_ENVIRONMENT
    assert envelope.contaminated is True


def test_envelope_join_stale_page_is_non_supporting() -> None:
    # The authoritative boundary captured an older WBC store version; the
    # page moved since, so the join must not mix stale evidence.
    stale_reads = _coherent_reads()
    wbc_vector = stale_reads["wbc_read"].version_vector  # type: ignore[attr-defined]
    envelope = es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        expected_versions={wbc_vector.source: "contract:c1|store:OLD"},
        **{k: v for k, v in stale_reads.items() if k != "expected_environment"},  # type: ignore[arg-type]
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.STALE
    assert envelope.stale is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.immutable_refs == ()

    # Matching expected versions keep the page coherent.
    fresh = es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        expected_versions={wbc_vector.source: wbc_vector.after or ""},
        **{k: v for k, v in stale_reads.items() if k != "expected_environment"},  # type: ignore[arg-type]
    )
    assert fresh.disposition is es.SourceReadDisposition.COHERENT
    assert fresh.supports_finding is True


def test_envelope_join_incomplete_page_is_non_supporting() -> None:
    # A Run Authority read with NO accepted outcome anchor is incomplete.
    no_outcome = es.RunAuthorityAcceptedOutcomeAdapter(
        lambda: _NoAcceptedOutcomeView(), environment="production"
    ).read()
    envelope = _join(accepted_outcome_read=no_outcome)
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.INCOMPLETE
    assert envelope.incomplete is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.immutable_refs == ()

    # An envelope with no environment coordinate at all cannot prove the
    # single-environment binding and stays incomplete.
    no_env_reads = _coherent_reads()
    for key in ("accepted_outcome_read", "wbc_read", "custody_read",
                "native_read", "ticket_read", "receipt_read"):
        no_env_reads[key] = no_env_reads[key].model_copy(  # type: ignore[attr-defined]
            update={"environment": None}
        )
    envelope = es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        **{k: v for k, v in no_env_reads.items() if k != "expected_environment"},  # type: ignore[arg-type]
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.INCOMPLETE
    assert envelope.incomplete is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False


def test_envelope_join_missing_wbc_environment_cannot_be_filled() -> None:
    reads = _coherent_reads()
    wbc = reads["wbc_read"]
    reads["wbc_read"] = wbc.model_copy(  # type: ignore[attr-defined]
        update={
            "environment": None,
            "version_vector": wbc.version_vector.model_copy(
                update={"environment": None}
            ),
        }
    )
    envelope = es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        expected_environment="production",
        **reads,  # type: ignore[arg-type]
    )
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.INCOMPLETE
    assert envelope.incomplete is True
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.environment is None
    assert envelope.owner_versions == ()
    assert envelope.immutable_refs == ()


def test_envelope_join_unavailable_source_fails_closed() -> None:
    broken = es.WbcWorkEvidenceAdapter(
        _BrokenStore(), environment="production"
    ).read("attempt-1")
    envelope = _join(wbc_read=broken)
    assert envelope.disposition is es.SourceReadDisposition.UNKNOWN
    assert envelope.disposition_reason is es.SourceReadFailure.SOURCE_UNAVAILABLE
    assert envelope.supports_finding is False
    assert envelope.supports_proposal is False
    assert envelope.owner_versions == ()
    assert envelope.immutable_refs == ()


def test_envelope_model_rejects_inconsistent_states() -> None:
    vector = SourceVersionVector(
        owner="run_authority",
        source="run_authority.view",
        environment="production",
        before="a" * 64,
        after="a" * 64,
    )
    ref = OwnerRef(owner="run_authority", locator="decision://d-1")
    # Coherent envelopes cannot carry failure flags.
    with pytest.raises(ValueError):
        es.CoherentObservationEnvelope(
            envelope_id="e-1",
            task_or_milestone_identity="task-m1",
            stage="finalize",
            environment="production",
            classifier_version="cls-v1",
            accepted_outcome_identity="run-1@rev-1",
            owner_versions=[vector],
            immutable_refs=[ref],
            disposition=es.SourceReadDisposition.COHERENT,
            torn=True,
        )
    # Non-coherent envelopes cannot carry references (non-supporting facts).
    with pytest.raises(ValueError):
        es.CoherentObservationEnvelope(
            envelope_id="e-1",
            task_or_milestone_identity="task-m1",
            stage="finalize",
            classifier_version="cls-v1",
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.STALE,
            immutable_refs=[ref],
        )
    # Non-coherent envelopes require a typed reason.
    with pytest.raises(ValueError):
        es.CoherentObservationEnvelope(
            envelope_id="e-1",
            task_or_milestone_identity="task-m1",
            stage="finalize",
            classifier_version="cls-v1",
            disposition=es.SourceReadDisposition.UNKNOWN,
            stale=True,
        )
    # Torn envelopes must be typed INCOHERENT/VERSION_TEAR.
    with pytest.raises(ValueError):
        es.CoherentObservationEnvelope(
            envelope_id="e-1",
            task_or_milestone_identity="task-m1",
            stage="finalize",
            classifier_version="cls-v1",
            disposition=es.SourceReadDisposition.UNKNOWN,
            disposition_reason=es.SourceReadFailure.SOURCE_UNAVAILABLE,
            torn=True,
        )
    # Coherent envelopes require the exact accepted-outcome identity.
    with pytest.raises(ValueError):
        es.CoherentObservationEnvelope(
            envelope_id="e-1",
            task_or_milestone_identity="task-m1",
            stage="finalize",
            environment="production",
            classifier_version="cls-v1",
            owner_versions=[vector],
            immutable_refs=[ref],
        )


# ---------------------------------------------------------------------------
# Plan Step 11 / T11: normalized work-fact layer (non-content features +
# immutable references only)
# ---------------------------------------------------------------------------


def _work_facts(**overrides: object) -> es.WorkEvidenceFacts:
    base: dict[str, object] = {
        "calls": [
            es.CallFacts(
                call_id="call-1",
                stage="gate",
                outcome=ea.CallOutcome.FAILED,
                failure_signature="north_star_actions-schema",
                elapsed_seconds=900.0,
            ),
            es.CallFacts(
                call_id="call-2",
                stage="gate",
                outcome=ea.CallOutcome.FAILED,
                failure_signature="north_star_actions-schema",
                elapsed_seconds=300.0,
            ),
        ],
        "dwell_legs": [
            es.DwellLegFacts(
                observation_id="gap-79min",
                kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
                stage="finalize",
                elapsed_seconds=4740.0,
            ),
        ],
        "handoffs": [
            es.HandoffFacts(
                observation_id="h-1",
                from_stage="finalize",
                to_stage="review",
                idle_seconds=3600.0,
            ),
        ],
        "repair_occurrences": [
            es.RepairOccurrenceFacts(
                observation_id="rep-1",
                affected_contract="north_star_actions",
                repair_signature="gate-schema-failure",
            ),
        ],
        "cost": 1.0,
        "tokens": 100,
        "time_seconds": 900.0,
        "quality": 0.9,
        "unknown_evidence": (),
    }
    base.update(overrides)
    return es.WorkEvidenceFacts(**base)  # type: ignore[arg-type]


def test_normalize_observation_facts_binds_calls_to_envelope_refs() -> None:
    envelope = _join()
    normalized = es.normalize_observation_facts(envelope, _work_facts())

    assert normalized.supports_finding is True
    assert normalized.disposition is es.SourceReadDisposition.COHERENT
    assert normalized.disposition_reason is None
    assert normalized.envelope_id == envelope.envelope_id
    assert normalized.envelope_digest == envelope.digest
    assert normalized.classifier_version == "cls-v1"

    # Every normalized call binds the envelope's exact accepted-outcome
    # anchor and the partitioned immutable references.
    assert len(normalized.calls) == 2
    call = normalized.calls[0]
    assert call.accepted_outcome_id == envelope.accepted_outcome_identity
    assert call.accepted_resolution_refs
    assert all(ref.owner == "run_authority" for ref in call.accepted_resolution_refs)
    assert call.refs
    assert all(ref.owner != "run_authority" for ref in call.refs)
    # Problem signatures stay separate from operational occurrence IDs.
    assert call.call_id == "call-1"
    assert call.failure_signature == "north_star_actions-schema"
    assert call.stage == "gate"
    assert call.outcome is ea.CallOutcome.FAILED
    assert call.elapsed_seconds == 900.0


def test_normalize_observation_facts_preserves_censored_measures() -> None:
    envelope = _join()
    facts = _work_facts(
        calls=[],
        dwell_legs=[
            es.DwellLegFacts(
                observation_id="gap-79min",
                kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
                stage="finalize",
                elapsed_seconds=4740.0,
            ),
            es.DwellLegFacts(
                observation_id="gap-176min",
                kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
                stage="finalize",
                censored=True,
                lower_bound_seconds=10560.0,
            ),
        ],
        handoffs=[],
        repair_occurrences=[],
    )
    normalized = es.normalize_observation_facts(envelope, facts)
    assert len(normalized.dwell_legs) == 2
    completed = next(
        leg for leg in normalized.dwell_legs if leg.observation_id == "gap-79min"
    )
    assert completed.censored is False
    assert completed.elapsed_seconds == 4740.0
    assert completed.lower_bound_seconds is None
    censored = next(
        leg for leg in normalized.dwell_legs if leg.observation_id == "gap-176min"
    )
    # SC12: the censored leg is NEVER coerced to a completion or to zero.
    assert censored.censored is True
    assert censored.elapsed_seconds is None
    assert censored.lower_bound_seconds == 10560.0


def test_normalize_observation_facts_typed_exclusion_flags() -> None:
    envelope = _join()
    facts = _work_facts(
        calls=[],
        dwell_legs=[
            es.DwellLegFacts(
                observation_id="gate-human",
                kind=ec.DwellFindingKind.GATE,
                stage="finalize",
                elapsed_seconds=5000.0,
                human_gate=True,
            ),
            es.DwellLegFacts(
                observation_id="gate-avoidable",
                kind=ec.DwellFindingKind.GATE,
                stage="finalize",
                elapsed_seconds=600.0,
            ),
        ],
        handoffs=[],
        repair_occurrences=[],
    )
    normalized = es.normalize_observation_facts(envelope, facts)
    by_id = {leg.observation_id: leg for leg in normalized.dwell_legs}
    # SC14: a flag requires its typed exclusion reason.
    assert by_id["gate-human"].excluded_reason is ea.DwellExclusionReason.HUMAN_GATE
    assert by_id["gate-human"].human_gate is True
    assert by_id["gate-avoidable"].excluded_reason is None
    # Multiple flags are rejected — one normalized fact, one typed reason.
    with pytest.raises(ValueError):
        es.normalize_observation_facts(
            envelope,
            _work_facts(
                calls=[],
                dwell_legs=[
                    es.DwellLegFacts(
                        observation_id="both",
                        kind=ec.DwellFindingKind.GATE,
                        stage="finalize",
                        elapsed_seconds=10.0,
                        human_gate=True,
                        configured_backoff=True,
                    )
                ],
                handoffs=[],
                repair_occurrences=[],
            ),
        )


def test_normalize_observation_facts_handoffs_and_repairs_reference_only() -> None:
    reads = _coherent_reads(
        accepted_outcome_read=es.RunAuthorityAcceptedOutcomeAdapter(
            lambda: _View(),
            active_custody_provider=lambda: [_Lease("lease-1")],
            environment="production",
        ).read()
    )
    envelope = es.join_observation_envelope(
        task_or_milestone_identity="task-m1",
        stage="finalize",
        **reads,  # type: ignore[arg-type]
    )
    facts = _work_facts(
        calls=[],
        dwell_legs=[],
        handoffs=[
            es.HandoffFacts(
                observation_id="h-1",
                from_stage="finalize",
                to_stage="review",
                idle_seconds=3600.0,
            ),
            es.HandoffFacts(
                observation_id="h-2",
                from_stage="finalize",
                to_stage="review",
                censored=True,
                lower_bound_seconds=7200.0,
            ),
        ],
        repair_occurrences=[
            es.RepairOccurrenceFacts(
                observation_id="rep-1",
                affected_contract="north_star_actions",
                repair_signature="gate-schema-failure",
            )
        ],
    )
    normalized = es.normalize_observation_facts(envelope, facts)
    assert len(normalized.handoffs) == 2
    handoff = next(h for h in normalized.handoffs if h.observation_id == "h-1")
    assert handoff.from_stage == "finalize"
    assert handoff.to_stage == "review"
    assert handoff.idle_seconds == 3600.0
    assert handoff.accepted_outcome_id == envelope.accepted_outcome_identity
    # SC16: active custody is reference/covariate only — never claimed.
    assert handoff.active_custody_refs
    assert handoff.active_custody_refs[0].owner == "repair_custody"
    censored_handoff = next(
        h for h in normalized.handoffs if h.observation_id == "h-2"
    )
    assert censored_handoff.censored is True
    assert censored_handoff.idle_seconds is None
    assert censored_handoff.lower_bound_seconds == 7200.0
    # Repair occurrences keep the normalized signature separate from IDs.
    assert len(normalized.repair_occurrences) == 1
    occurrence = normalized.repair_occurrences[0]
    assert occurrence.affected_contract == "north_star_actions"
    assert occurrence.repair_signature == "gate-schema-failure"
    assert occurrence.accepted_outcome_id == envelope.accepted_outcome_identity


def test_normalize_observation_facts_economics_unknowns_never_zero() -> None:
    envelope = _join()
    # Missing cost/tokens/time/quality are preserved as None with their
    # typed unknown reasons — never coerced to zero (SC12).
    facts = _work_facts(
        calls=[],
        dwell_legs=[],
        handoffs=[],
        repair_occurrences=[],
        cost=None,
        tokens=None,
        time_seconds=None,
        quality=None,
        unknown_evidence=(
            es.EvidenceUnknownKind.COST,
            es.EvidenceUnknownKind.QUALITY,
            es.EvidenceUnknownKind.MODEL,
        ),
    )
    normalized = es.normalize_observation_facts(envelope, facts)
    assert normalized.economics is not None
    economics = normalized.economics
    assert economics.accepted_outcome_count == 1
    assert economics.cost is None
    assert economics.tokens is None
    assert economics.time_seconds is None
    assert economics.quality is None
    assert set(economics.unknown_evidence) == {
        es.EvidenceUnknownKind.COST,
        es.EvidenceUnknownKind.QUALITY,
        es.EvidenceUnknownKind.MODEL,
    }
    dumped = canonical_dumps(normalized)
    assert '"cost":null' in dumped
    assert '"tokens":null' in dumped
    # A present coordinate cannot be typed unknown (machine-checked).
    with pytest.raises(ValueError):
        es.WorkEvidenceFacts(cost=5.0, unknown_evidence=(es.EvidenceUnknownKind.COST,))
    with pytest.raises(ValueError):
        es.WorkEvidenceFacts(quality=0.9, unknown_evidence=(es.EvidenceUnknownKind.QUALITY,))


def test_normalize_observation_facts_economics_present_when_coordinates() -> None:
    envelope = _join()
    facts = _work_facts(
        calls=[],
        dwell_legs=[],
        handoffs=[],
        repair_occurrences=[],
        cost=2.5,
        tokens=1200,
        time_seconds=300.0,
        quality=0.8,
        unknown_evidence=(),
    )
    normalized = es.normalize_observation_facts(envelope, facts)
    assert normalized.economics is not None
    assert normalized.economics.cost == 2.5
    assert normalized.economics.tokens == 1200
    assert normalized.economics.time_seconds == 300.0
    assert normalized.economics.quality == 0.8
    assert normalized.economics.unknown_evidence == ()


def test_normalize_observation_facts_non_coherent_envelope_is_empty() -> None:
    torn = es.CoherentObservationEnvelope(
        envelope_id=es.derive_envelope_id("task-m1", stage="finalize"),
        task_or_milestone_identity="task-m1",
        stage="finalize",
        classifier_version="cls-v1",
        disposition=es.SourceReadDisposition.INCOHERENT,
        disposition_reason=es.SourceReadFailure.VERSION_TEAR,
        torn=True,
    )
    normalized = es.normalize_observation_facts(torn, _work_facts())
    # SC11: a torn page supports no finding and invents no facts.
    assert normalized.supports_finding is False
    assert normalized.disposition is es.SourceReadDisposition.INCOHERENT
    assert normalized.disposition_reason is es.SourceReadFailure.VERSION_TEAR
    assert normalized.calls == ()
    assert normalized.dwell_legs == ()
    assert normalized.handoffs == ()
    assert normalized.repair_occurrences == ()
    assert normalized.economics is None
    assert normalized.envelope_digest == torn.digest


def test_normalize_observation_facts_never_copies_sensitive_content() -> None:
    envelope = _join()
    normalized = es.normalize_observation_facts(envelope, _work_facts())
    dumped = canonical_dumps(normalized)
    # Owner payloads are never embedded in the normalized bundle.
    assert "DECISION-PAYLOAD" not in dumped
    assert "PROOF-PAYLOAD" not in dumped


def test_normalize_observation_facts_is_input_order_independent() -> None:
    envelope = _join()
    forward = es.normalize_observation_facts(envelope, _work_facts())
    reversed_facts = _work_facts(
        calls=list(reversed(_work_facts().calls)),
        dwell_legs=list(reversed(_work_facts().dwell_legs)),
        handoffs=list(reversed(_work_facts().handoffs)),
        repair_occurrences=list(reversed(_work_facts().repair_occurrences)),
    )
    backward = es.normalize_observation_facts(envelope, reversed_facts)
    assert forward == backward
    assert forward.digest == backward.digest


def test_normalize_observation_facts_roundtrips_and_hashes() -> None:
    envelope = _join()
    normalized = es.normalize_observation_facts(envelope, _work_facts())
    decoded = strict_loads(es.NormalizedWorkFacts, canonical_dumps(normalized))
    assert decoded == normalized
    assert decoded.digest == normalized.digest
    # The analyzer fact shapes strict-decode as well (Step 11 shape).
    call_decoded = strict_loads(ea.NormalizedCall, canonical_dumps(normalized.calls[0]))
    assert call_decoded == normalized.calls[0]


def test_normalize_observation_facts_feeds_analyzer_contracts() -> None:
    # The Step 11 normalized calls are directly consumable by the Step 14
    # analyzers: two equivalent gate failures cluster into ONE finding whose
    # identity derives from the problem signature, never from call IDs.
    envelope = _join()
    normalized = es.normalize_observation_facts(envelope, _work_facts())
    findings = ea.analyze_equivalent_failures(normalized.calls)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.attempt_count == 2
    assert "call-1" not in finding.finding_id and "call-2" not in finding.finding_id
    assert finding.economics is not None
    assert finding.economics.accepted_outcome_count == 1


def test_normalize_observation_facts_fact_contract_discipline() -> None:
    # Empty signatures are rejected (signatures are normalized, never blank).
    with pytest.raises(ValueError):
        es.CallFacts(
            call_id="c-1", stage="gate", outcome=ea.CallOutcome.FAILED,
            failure_signature="",
        )
    # Censored legs require an explicit lower bound and never a completion.
    with pytest.raises(ValueError):
        es.DwellLegFacts(
            observation_id="d-1",
            kind=ec.DwellFindingKind.GATE,
            stage="finalize",
            censored=True,
        )
    with pytest.raises(ValueError):
        es.DwellLegFacts(
            observation_id="d-2",
            kind=ec.DwellFindingKind.GATE,
            stage="finalize",
            censored=True,
            elapsed_seconds=10.0,
            lower_bound_seconds=5.0,
        )
    # Completed legs require an exact elapsed duration (never coerced).
    with pytest.raises(ValueError):
        es.DwellLegFacts(
            observation_id="d-3",
            kind=ec.DwellFindingKind.GATE,
            stage="finalize",
            elapsed_seconds=None,
        )
    # Handoff stages must differ.
    with pytest.raises(ValueError):
        es.HandoffFacts(
            observation_id="h-1",
            from_stage="finalize",
            to_stage="finalize",
            idle_seconds=10.0,
        )