"""Cloud adapter tests: occurrence-bound repair-request bridge (M3 Step 9 / T10).

These tests prove the cloud adapter ``maintenance_recovery``:

* translates the canonical M7 identity into
  ``enqueue_occurrence_bound_repair_request`` (the owner seam is injected
  as a spy; the real seam is the module default);
* joins an existing identical request (``coalesced``) and appends its
  immutable reference to the Maintenance ledger exactly once;
* re-reads a coherent direct owner-source envelope BEFORE any authority
  increase and refuses pending handoffs, stale epochs or fences, missing
  WBC attempts, and non-dispatchable observations without touching the
  enqueue seam;
* proves concurrent/replayed submissions produce one canonical request
  and exactly one Maintenance request event;
* never reimplements a queue, lease store, or claim store (the module
  delegates exclusively to the canonical seam and the Maintenance ledger).
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.cloud.maintenance_recovery import (
    EffectKind,
    EffectOutcome,
    EffectRejectReason,
    EffectRoutingResult,
    EscalationOutcome,
    EscalationRejectReason,
    ExpectedRequestAuthority,
    HumanEscalationResult,
    RecurrenceAdmissionOutcome,
    RecurrenceAdmissionResult,
    RecurrenceRejectReason,
    RequestOutcome,
    RequestRejectReason,
    RequestSubmissionResult,
    admit_verified_recurrence,
    boundary_inputs_from_identity,
    evaluate_request_eligibility,
    record_human_escalation,
    route_allowlisted_effect,
    submit_occurrence_bound_repair_request,
    submit_terminal_verification,
    translate_occurrence_identity,
    TerminalOutcome,
    TerminalRejectReason,
    TerminalSubmissionResult,
)
from arnold_pipelines.megaplan.cloud.repair_effect_allowlist import (
    AllowlistCheckResult,
    AllowlistVerdict,
    RepairEffectClass,
)
from arnold_pipelines.megaplan.cloud.repair_effect_ledger import MutationReservation
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegationResult,
)
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryResult,
    GateResult,
)
from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
)
from arnold_pipelines.megaplan.maintenance.events import (
    OccurrenceBudget,
    OperationalEvent,
    ProgressObservationPayload,
    RecurrencePayload,
    RepairRequestPayload,
    TerminalVerificationPayload,
    VerifierProvenance,
)
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HANDOFF_IDS,
    ApprovalEvidence,
    ApprovalState,
    HandoffRegistry,
    HandoffResolutionReason,
    HandoffResolutionState,
    HandoffRow,
    WbcCoordinates,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_json,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import MaintenanceLedger
from arnold_pipelines.megaplan.maintenance.observation import (
    custody_source,
    run_authority_source,
    wbc_source,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    LeaseCoordinates,
    OccurrenceCoordinates,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RunAuthorityCoordinates,
    WbcAttemptCoordinates,
)
from arnold_pipelines.megaplan.maintenance.projections import (
    CustodyProjection,
    reduce_custody,
)

UTC = timezone.utc


def _ts() -> datetime:
    return datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Owner read fakes (mirror the canonical read APIs exactly)
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

    def __init__(self, view_hash: str = "a" * 64, run_id: str = "run-1") -> None:
        self.view_hash = view_hash
        self.run_id = run_id
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


class _SpyStore:
    """Read/query/version-only WBC AttemptLedgerStore-shaped fake."""

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


class _Lease:
    """M7 current-lease-shaped fake (epoch + occurrence + fence)."""

    def __init__(
        self,
        custody_epoch: int = 3,
        occurrence_id: str = "occ-1",
        fencing_token: str = "tok-1",
    ) -> None:
        self.custody_epoch = custody_epoch
        self.occurrence_id = occurrence_id
        self.fencing_token = fencing_token

    def to_dict(self) -> dict:
        return {
            "custody_epoch": self.custody_epoch,
            "occurrence_id": self.occurrence_id,
            "fencing_token": self.fencing_token,
        }


def _lease_digest(lease: _Lease) -> str:
    return hashlib.sha256(canonical_json(lease.to_dict()).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Accepted handoff registry (M7 + M6A approved; the rest pending)
# ---------------------------------------------------------------------------


def _registry(accepted: dict[str, HandoffRow] | None = None) -> HandoffRegistry:
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
) -> HandoffRow:
    return HandoffRow(
        id=handoff_id,
        source_path=source_path,
        schema_identity=schema_identity,
        owner_api_identity=f"owner.api.{handoff_id}",
        schema_version=schema_identity.rsplit(".", 1)[-1],
        digest=digest,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=(handoff_id == "M6A"),
        wbc_coordinates=wbc,
        approval_evidence=ApprovalEvidence(
            approver="approver-1",
            approved_at=_ts(),
            evidence_ref=f"approval://{handoff_id}/1",
            digest="c" * 64,
        ),
    )


def _accepted_registry() -> HandoffRegistry:
    return _registry(
        {
            "M7": _accepted_row(
                "M7",
                source_path="megaplan/controlled_writers",
                schema_identity="m7.custody.v1",
                digest="d" * 64,
            ),
            "M6A": _accepted_row(
                "M6A",
                source_path="megaplan/attempt_ledger_store",
                schema_identity="m6a.attempts.v1",
                digest="e" * 64,
                wbc=WbcCoordinates(incarnation="inc-1", restore_generation="rg-1", high_water="hw-1"),
            ),
        }
    )


# ---------------------------------------------------------------------------
# Decision coordinates + canonical M7 identity envelope
# ---------------------------------------------------------------------------


OCCURRENCE_ID = "occ-1"
LEASE_ID = "lease-1"
RUN_ID = "run-1"
ATTEMPT_ID = "att-1"
FENCE = "tok-1"
TARGET_ID = "target-1"


def _coordinates(*, lease_digest: str | None = None) -> dict[str, Any]:
    return {
        "occurrence": OccurrenceCoordinates(
            occurrence_id=OCCURRENCE_ID,
            canonical_digest="1" * 64,
        ),
        "lease": LeaseCoordinates(
            lease_id=LEASE_ID,
            custody_epoch=3,
            lease_digest=lease_digest,
        ),
        "run_authority": RunAuthorityCoordinates(run_id=RUN_ID, satisfied=True),
        "policy": PolicyVersionCoordinates(policy_version="p1", policy_digest="2" * 64),
        "target": ActionTarget(target=TARGET_ID, target_type="path"),
        "producer": ProducerPrincipal(principal="producer-1", role=ProducerRole.REPAIR_PRODUCER),
        "wbc_attempt": WbcAttemptCoordinates(attempt_id=ATTEMPT_ID),
    }


def _identity(*, lease_id: str = LEASE_ID, epoch: int = 3, occurrence_digest: str = "1" * 64, run_id: str = RUN_ID) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "occurrence": {
            "contract_type": "repair_occurrence_key",
            "target": {
                "environment": "production",
                "session": "sess-1",
                "chain": "plan-1",
                "plan_revision": "plan-1",
                "phase": "repair",
                "task": TARGET_ID,
                "attempt": ATTEMPT_ID,
                "normalized_failure_kind": "maintenance_effect",
                "blocker_or_phase_result_hash": "req-1",
                "fence": "7",
            },
            "run_id": run_id,
            "run_revision": "rev-1",
            "coordinator_attempt_id": ATTEMPT_ID,
            "fence_token": 7,
            "wbc_attempt_reference": ATTEMPT_ID,
            "occurrence_digest": occurrence_digest,
        },
        "run_incarnation_id": "inc-1",
        "run_authority_grant_id": "g-1",
        "lease_id": lease_id,
        "custody_epoch": epoch,
    }


# ---------------------------------------------------------------------------
# Enqueue seam spy
# ---------------------------------------------------------------------------


class _EnqueueSpy:
    def __init__(self, status: str = "accepted", request_id: str = "req-1") -> None:
        self.status = status
        self.request_id = request_id
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.status in ("zero_authority_rejected",):
            return {
                "status": "zero_authority_rejected",
                "outcome": "zero_authority_rejected",
                "evidence": {"reason": "identity not accepted", "source": "test"},
            }
        record = {
            "schema_version": "claimable-repair-request-v1",
            "kind": "repair_request",
            "request_id": self.request_id,
            "session": str(kwargs.get("session") or ""),
            "problem_signature_key": "sig-key-1",
            "repair_identity_key": "sha256:" + "f" * 64,
            "source": str(kwargs.get("source") or ""),
        }
        if self.status in ("stale", "superseded"):
            return {
                "status": self.status,
                "request": record,
                "path": f"{self.request_id}.json",
                "decision": {"decision": self.status},
            }
        return {
            "status": self.status,
            "request": record,
            "path": f"{self.request_id}.json",
            "decision": {"decision": "accepted" if self.status == "accepted" else "coalesced"},
        }


# ---------------------------------------------------------------------------
# Sources (coherent direct owner-source reads)
# ---------------------------------------------------------------------------


def _sources(
    *,
    registry: HandoffRegistry,
    view: _View | None = None,
    store: _SpyStore | None = None,
    lease: _Lease | None = None,
    lease_id: str = LEASE_ID,
) -> list[Any]:
    view = view if view is not None else _View()
    store = store if store is not None else _SpyStore(ledger=_Ledger(_Event(1)))
    lease = lease if lease is not None else _Lease()
    return [
        run_authority_source(
            lambda: view,
            environment="production",
            stale_probe=lambda _read: False,
        ),
        wbc_source(
            store,
            ATTEMPT_ID,
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
        custody_source(
            lease_id,
            current_lease_provider=lambda _lease_id: lease,
            history_provider=lambda _lease_id: [],
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
    ]


def _submit_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    spy: _EnqueueSpy,
    view: _View | None = None,
    store: _SpyStore | None = None,
    lease: _Lease | None = None,
    expected: ExpectedRequestAuthority | None = None,
    identity: Mapping[str, Any] | None = None,
    sources: list[Any] | None = None,
    lease_digest: str | None = None,
    ledger: MaintenanceLedger | None = None,
) -> dict[str, Any]:
    coords = _coordinates(lease_digest=lease_digest)
    expected = expected if expected is not None else ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest=lease_digest or _lease_digest(lease if lease is not None else _Lease()),
        fencing_token=FENCE,
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )
    return {
        **coords,
        "observed_at": UtcTime(_ts()),
        "occurrence_identity": identity if identity is not None else _identity(),
        "sources": sources if sources is not None else _sources(registry=registry, view=view, store=store, lease=lease),
        "environment": "production",
        "run": RUN_ID,
        "attempt": ATTEMPT_ID,
        "expected": expected,
        "handoff_resolver": registry.resolve,
        "enqueue_fn": spy,
        "ledger": ledger if ledger is not None else MaintenanceLedger(tmp_path),
        "queue_root": tmp_path / "requests",
        "session": "sess-1",
        "problem_signature": {"kind": "blocker", "digest": "3" * 64},
        "source": "maintenance_recovery",
        "root_cause_hint": {"summary": "blocker"},
        "marker_dir": tmp_path / "markers",
        "target_mapping": {"plan": "plan-1", "phase": "repair"},
        "workspace": tmp_path / "ws",
        "run_kind": "maintenance",
        "evidence_cursor_digest": "4" * 64,
    }


def _event_rows(ledger: MaintenanceLedger, event_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = ledger.events_path
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            payload = record.get("payload") or {}
            if payload.get("event_id") == event_id:
                rows.append(record)
    return rows


# ---------------------------------------------------------------------------
# Accepted path: enqueue-or-join + single immutable reference
# ---------------------------------------------------------------------------


def test_accepted_submission_translates_identity_and_appends_once(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="accepted", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger)
    )

    assert result.outcome is RequestOutcome.ACCEPTED
    assert result.reasons == ()
    assert result.request_id == "req-1"
    assert result.enqueue_status == "accepted"
    assert result.event_replayed is False
    assert result.event_id is not None and result.event_digest is not None
    assert result.envelope_digest is not None

    # 1. The canonical M7 identity was translated to the seam exactly once.
    assert len(spy.calls) == 1
    translated = spy.calls[0]["occurrence_identity"]
    assert translated["lease_id"] == LEASE_ID
    assert translated["custody_epoch"] == 3
    assert translated["occurrence"]["occurrence_digest"] == "1" * 64
    assert translated["occurrence"]["run_id"] == RUN_ID

    # 2. The immutable request reference was appended exactly once.
    assert result.request_ref is not None
    assert result.request_ref.owner == "repair_custody"
    assert result.request_ref.record_type == "request"
    assert result.request_ref.locator == "repair_request://req-1"
    assert result.request_ref.digest is not None
    rows = _event_rows(ledger, result.event_id)
    assert len(rows) == 1
    event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert event.action_kind.value == "repair_request"
    assert event.payload.request_id == "req-1"
    assert event.payload.request_ref == result.request_ref
    assert canonical_digest(event) == result.event_digest


def test_coalesced_submission_joins_identical_request(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="coalesced", request_id="req-9")
    result = submit_occurrence_bound_repair_request(**_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy))

    assert result.outcome is RequestOutcome.JOINED
    assert result.enqueue_status == "coalesced"
    assert result.request_id == "req-9"
    assert result.request_ref is not None
    assert result.request_ref.locator == "repair_request://req-9"
    assert len(_event_rows(MaintenanceLedger(tmp_path), result.event_id)) == 1


def test_replay_appends_identical_reference_once(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="coalesced", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    kwargs = _submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger)

    first = submit_occurrence_bound_repair_request(**kwargs)
    second = submit_occurrence_bound_repair_request(**kwargs)

    assert first.outcome is RequestOutcome.JOINED
    assert second.outcome is RequestOutcome.JOINED
    assert second.request_id == first.request_id == "req-1"
    assert second.event_id == first.event_id
    # The journal boundary deduplicated the exact retry: still one row, and
    # the replayed submission reports it.
    assert len(_event_rows(ledger, first.event_id)) == 1
    assert second.event_replayed is True


def test_concurrent_submissions_produce_one_request_and_one_event(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="coalesced", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    kwargs = _submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger)

    results: list[RequestSubmissionResult] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def run() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(submit_occurrence_bound_repair_request(**kwargs))
        except BaseException as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors
    assert len(results) == 2
    assert all(result.outcome is RequestOutcome.JOINED for result in results)
    # One canonical request (identical request id) and one Maintenance event.
    assert results[0].request_id == results[1].request_id == "req-1"
    assert results[0].event_id == results[1].event_id
    assert len(_event_rows(ledger, results[0].event_id)) == 1
    # The canonical seam was consulted by every submission but coalesced.
    assert len(spy.calls) == 2
    assert {call["occurrence_identity"]["lease_id"] for call in spy.calls} == {LEASE_ID}


# ---------------------------------------------------------------------------
# Fail-closed gates: nothing enqueues before the previous step is satisfied
# ---------------------------------------------------------------------------


def test_refuses_pending_handoff_before_enqueue(tmp_path: Path) -> None:
    registry = _registry()  # every row pending (M7 and M6A unresolved)
    spy = _EnqueueSpy()
    result = submit_occurrence_bound_repair_request(**_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy))

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.PENDING_HANDOFF in result.reasons
    assert "M7" in result.pending_handoffs and "M6A" in result.pending_handoffs
    assert result.request_ref is None and result.event_id is None
    assert spy.calls == []  # the authority-increasing seam was never touched
    assert not MaintenanceLedger(tmp_path).events_path.exists()


def test_refuses_stale_epoch_when_lease_digest_is_pinned(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    lease = _Lease(custody_epoch=3, occurrence_id=OCCURRENCE_ID, fencing_token=FENCE)
    stale_expected = ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest="f" * 64,  # pinned digest does not match the live lease record
        fencing_token=FENCE,
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            lease=lease,
            expected=stale_expected,
            lease_digest="f" * 64,
        )
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.STALE_AUTHORITY in result.reasons
    assert spy.calls == []


def test_refuses_stale_fence_contradictory_read(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    # The live lease carries a NEWER fence than the expected authority.
    lease = _Lease(custody_epoch=3, occurrence_id=OCCURRENCE_ID, fencing_token="tok-2")
    expected = ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest=_lease_digest(lease),
        fencing_token=FENCE,  # expected "tok-1"; live read exposes "tok-2"
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            lease=lease,
            expected=expected,
            lease_digest=_lease_digest(lease),
        )
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.STALE_AUTHORITY in result.reasons
    assert spy.calls == []


def test_refuses_missing_wbc_attempt(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    # The WBC store exposes no ledger record: the capture carries no WBC
    # attempt reference even though the envelope itself is coherent.
    store = _SpyStore(ledger=None)
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, store=store)
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.MISSING_WBC in result.reasons
    assert spy.calls == []


def test_refuses_stale_source_observation(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    view = _View()

    def stale_probe(_read: Any) -> bool:
        return True

    sources = [
        run_authority_source(lambda: view, environment="production", stale_probe=stale_probe),
        wbc_source(
            _SpyStore(ledger=_Ledger(_Event(1))),
            ATTEMPT_ID,
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
        custody_source(
            LEASE_ID,
            current_lease_provider=lambda _lease_id: _Lease(),
            history_provider=lambda _lease_id: [],
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
    ]
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, sources=sources)
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.STALE_AUTHORITY in result.reasons
    assert spy.calls == []


def test_refuses_torn_envelope(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    import itertools

    hashes = itertools.cycle(["a" * 64, "b" * 64])
    view = _View(view_hash="a" * 64)

    def provider() -> _View:
        # Every probe/read pair observes a DIFFERENT view hash: a permanent
        # version tear across the whole capture budget.
        view.view_hash = next(hashes)
        return view

    sources = [
        run_authority_source(provider, environment="production", stale_probe=lambda _read: False),
        wbc_source(
            _SpyStore(ledger=_Ledger(_Event(1))),
            ATTEMPT_ID,
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
        custody_source(
            LEASE_ID,
            current_lease_provider=lambda _lease_id: _Lease(),
            history_provider=lambda _lease_id: [],
            registry=registry,
            environment="production",
            stale_probe=lambda _read: False,
        ),
    ]
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, sources=sources)
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.TORN_ENVELOPE in result.reasons
    assert spy.calls == []


def test_refuses_identity_mismatch_before_enqueue(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy()
    identity = _identity(lease_id="lease-OTHER")
    result = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy, identity=identity)
    )

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.IDENTITY_MISMATCH in result.reasons
    assert spy.calls == []


def test_refuses_enqueue_rejection_without_append(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="zero_authority_rejected")
    result = submit_occurrence_bound_repair_request(**_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy))

    assert result.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.ENQUEUE_REJECTED in result.reasons
    assert result.enqueue_status == "zero_authority_rejected"
    assert result.event_id is None
    assert len(spy.calls) == 1
    assert not MaintenanceLedger(tmp_path).events_path.exists()


def test_refuses_divergent_reuse_of_the_occurrence_action(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    spy_first = _EnqueueSpy(status="accepted", request_id="req-1")
    first = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy_first, ledger=ledger)
    )
    assert first.outcome is RequestOutcome.ACCEPTED

    # A replayed decision that resolves to a DIFFERENT request reuses the
    # same lifecycle action key with different content: the ledger rejects
    # the divergent duplicate without appending.
    spy_second = _EnqueueSpy(status="accepted", request_id="req-2")
    second = submit_occurrence_bound_repair_request(
        **_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy_second, ledger=ledger)
    )

    assert second.outcome is RequestOutcome.REJECTED
    assert RequestRejectReason.DIVERGENT_REUSE in second.reasons
    assert len(_event_rows(ledger, first.event_id)) == 1


# ---------------------------------------------------------------------------
# Pure eligibility and identity-translation contracts
# ---------------------------------------------------------------------------


def test_evaluate_request_eligibility_pure_fail_closed_mapping() -> None:
    # A coherent-but-stale envelope is STALE_AUTHORITY, never dispatchable.
    stale = ObservationEnvelope.build(
        observed_at=UtcTime(_ts()),
        environment="production",
        run=RUN_ID,
        attempt=ATTEMPT_ID,
        version_vectors=(),
        references=(),
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.STALE,
        coherence=CoherenceState.COHERENT,
    )
    reasons = evaluate_request_eligibility(
        envelope=stale, wbc_present=True, lease_present=True, lease_digest_matches=True
    )
    assert reasons == (RequestRejectReason.STALE_AUTHORITY,)

    # A torn envelope maps to TORN_ENVELOPE.
    torn = ObservationEnvelope.build(
        observed_at=UtcTime(_ts()),
        environment="production",
        version_vectors=(),
        references=(),
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.INCOHERENT,
        coherence_reasons=(CoherenceReason.VERSION_TEAR,),
    )
    reasons = evaluate_request_eligibility(
        envelope=torn, wbc_present=True, lease_present=True, lease_digest_matches=True
    )
    assert reasons == (RequestRejectReason.TORN_ENVELOPE,)

    # Missing WBC and missing lease are typed even when the envelope is clean.
    clean = ObservationEnvelope.build(
        observed_at=UtcTime(_ts()),
        environment="production",
        run=RUN_ID,
        attempt=ATTEMPT_ID,
        version_vectors=(),
        references=(),
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.COHERENT,
    )
    reasons = evaluate_request_eligibility(
        envelope=clean, wbc_present=False, lease_present=False, lease_digest_matches=None
    )
    assert RequestRejectReason.MISSING_WBC in reasons
    assert RequestRejectReason.MISSING_LEASE in reasons


def test_translate_occurrence_identity_rejects_contradictory_coordinates() -> None:
    coords = _coordinates()
    translated, reasons = translate_occurrence_identity(
        identity=_identity(),
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
    )
    assert translated is not None and reasons == ()

    missing, missing_reasons = translate_occurrence_identity(
        identity={},
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
    )
    assert missing is None
    assert missing_reasons == (RequestRejectReason.MISSING_OCCURRENCE_IDENTITY,)

    bad, bad_reasons = translate_occurrence_identity(
        identity=_identity(epoch=9),
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
    )
    assert bad is None
    assert RequestRejectReason.IDENTITY_MISMATCH in bad_reasons


def test_submission_result_round_trips_through_strict_codec(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="accepted", request_id="req-1")
    result = submit_occurrence_bound_repair_request(**_submit_kwargs(tmp_path=tmp_path, registry=registry, spy=spy))
    decoded = strict_loads(RequestSubmissionResult, result.model_dump(mode="json"))
    assert decoded.outcome is RequestOutcome.ACCEPTED
    assert decoded.request_id == "req-1"
    assert decoded.request_ref == result.request_ref
    assert canonical_digest(decoded) == canonical_digest(result)


def test_module_never_reimplements_owner_stores() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "maintenance_recovery.py"
    ).read_text(encoding="utf-8")
    # The adapter delegates to the canonical seam; it defines no queue,
    # lease store, effect ledger, or claim store of its own.
    for banned in (
        "class RepairQueue",
        "class LeaseStore",
        "class EffectLedger",
        "class ClaimStore",
        "def enqueue_repair_request",
        "def acquire_lease",
        "def release_lease",
    ):
        assert banned not in source, f"maintenance_recovery.py reimplements {banned!r}"
    # The canonical seam must be the module default for the enqueue call.
    assert "enqueue_occurrence_bound_repair_request" in source


# ---------------------------------------------------------------------------
# Plan Step 10 / T11: allowlisted effect routing through the unified fixer
# ---------------------------------------------------------------------------


class _GateSpy:
    """Injected master/path mutation-gate predicate."""

    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized
        self.calls: list[str] = []

    def __call__(self, path: str) -> bool:
        self.calls.append(path)
        return self.authorized


class _AllowlistSpy:
    """Injected M10 repair-effect allowlist check."""

    def __init__(self, verdict: AllowlistVerdict = AllowlistVerdict.APPROVED) -> None:
        self.verdict = verdict
        self.calls: list[Any] = []

    def __call__(self, effect_class: str | RepairEffectClass) -> AllowlistCheckResult:
        self.calls.append(effect_class)
        resolved = (
            RepairEffectClass(effect_class)
            if isinstance(effect_class, str)
            else effect_class
        )
        return AllowlistCheckResult(
            effect_class=resolved,
            verdict=self.verdict,
            reason="spy",
        )


class _BoundarySpy:
    """Injected fresh M7 action-boundary validator."""

    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> ActionBoundaryResult:
        self.calls.append(kwargs)
        return ActionBoundaryResult(
            gate_result=(
                GateResult.AUTHORIZED if self.authorized else GateResult.BLOCKED_STALE_GRANT
            ),
            action_type="repair",
            target_digest="a" * 64,
            checks=(),
            enforcement_enabled=self.authorized,
        )


class _DelegationSpy:
    """Injected unified-fixer delegation (delegate_to_simple_fixer shaped)."""

    def __init__(
        self,
        outcome: str = "delegated",
        *,
        reservation_id: str = "res-1",
        repair_identity_key: str = "key-1",
        state: str = "COMPLETED",
    ) -> None:
        self.outcome = outcome
        self.reservation_id = reservation_id
        self.repair_identity_key = repair_identity_key
        self.state = state
        self.calls: list[dict[str, Any]] = []

    def __call__(self, delegation: Any, **kwargs: Any) -> RepairDelegationResult:
        self.calls.append({"delegation": delegation, **kwargs})
        if self.outcome != "delegated":
            return RepairDelegationResult(
                outcome=self.outcome,
                evidence={"reason": "spy rejection"},
            )
        return RepairDelegationResult(
            outcome="delegated",
            occurrence_fingerprint="fp-1",
            simple_fixer_outcome="attempted",
            evidence={
                "simple_fixer_outcome": "attempted",
                "effect_ledger": {
                    "repair_identity_key": self.repair_identity_key,
                    "state": self.state,
                    "reservation_id": self.reservation_id,
                    "total_attempts": 1,
                    "unchanged_attempts": 0,
                    "effect_outcome": "changed",
                },
            },
        )


class _ReceiptsSpy:
    """Injected canonical effect-ledger receipt query."""

    def __init__(
        self,
        prior: MutationReservation | None = None,
        *,
        error: bool = False,
    ) -> None:
        self.prior = prior
        self.error = error
        self.calls: list[Any] = []

    def __call__(self, identity: Mapping[str, Any]) -> MutationReservation | None:
        self.calls.append(identity)
        if self.error:
            raise ValueError("receipt query failed")
        return self.prior


def _reservation(
    *,
    state: str = "RESERVED",
    reservation_id: str = "res-1",
    repair_identity_key: str = "key-1",
) -> MutationReservation:
    return MutationReservation(
        decision="observed",
        repair_identity_key=repair_identity_key,
        state=state,
        reservation_id=reservation_id,
        total_attempts=1,
        unchanged_attempts=0,
        effect_outcome="changed" if state != "RESERVED" else "",
        after_fingerprint="fp-1" if state != "RESERVED" else "",
    )


def _effect_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    effect_kind: EffectKind | str = EffectKind.SOURCE_CHANGE,
    gate: _GateSpy | None = None,
    allowlist: _AllowlistSpy | None = None,
    boundary: _BoundarySpy | None = None,
    delegation: _DelegationSpy | None = None,
    receipts: _ReceiptsSpy | None = None,
    view: _View | None = None,
    store: _SpyStore | None = None,
    lease: _Lease | None = None,
    lease_digest: str | None = None,
    expected: ExpectedRequestAuthority | None = None,
    identity: Mapping[str, Any] | None = None,
    sources: list[Any] | None = None,
    ledger: MaintenanceLedger | None = None,
    mutate: Callable[[Any], str] | None = None,
    source_digest: str | None = None,
    install_digest: str | None = None,
    reason: str = "",
    effect_class: str | RepairEffectClass = RepairEffectClass.MUTATE,
) -> dict[str, Any]:
    coords = _coordinates(lease_digest=lease_digest)
    expected = expected if expected is not None else ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest=lease_digest or _lease_digest(lease if lease is not None else _Lease()),
        fencing_token="tok-1",
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )
    return {
        **coords,
        "effect_kind": effect_kind,
        "observed_at": UtcTime(_ts()),
        "repair_identity": identity if identity is not None else _identity(),
        "sources": sources if sources is not None else _sources(registry=registry, view=view, store=store, lease=lease),
        "environment": "production",
        "run": RUN_ID,
        "attempt": ATTEMPT_ID,
        "expected": expected,
        "handoff_resolver": registry.resolve,
        "ledger": ledger if ledger is not None else MaintenanceLedger(tmp_path),
        "queue_root": tmp_path / "requests",
        "request_id": "req-1",
        "session": "sess-1",
        "effect_class": effect_class,
        "mutate": mutate if mutate is not None else (lambda occ: "changed"),
        "source_digest": source_digest,
        "install_digest": install_digest,
        "reason": reason,
        "wbc_attempt": coords["wbc_attempt"],
        "mutation_gate_fn": gate if gate is not None else _GateSpy(True),
        "allowlist_fn": allowlist if allowlist is not None else _AllowlistSpy(),
        "boundary_fn": boundary if boundary is not None else _BoundarySpy(),
        "delegation_fn": delegation if delegation is not None else _DelegationSpy(),
        "receipts_fn": receipts if receipts is not None else _ReceiptsSpy(),
    }


def test_effect_route_delegates_source_change_and_appends_once(tmp_path: Path) -> None:
    registry = _accepted_registry()
    gate = _GateSpy(True)
    allowlist = _AllowlistSpy()
    boundary = _BoundarySpy(True)
    delegation = _DelegationSpy(outcome="delegated", reservation_id="res-1")
    receipts = _ReceiptsSpy(None)
    ledger = MaintenanceLedger(tmp_path)
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            gate=gate,
            allowlist=allowlist,
            boundary=boundary,
            delegation=delegation,
            receipts=receipts,
            ledger=ledger,
            source_digest="a" * 64,
        )
    )

    assert result.outcome is EffectOutcome.DELEGATED
    assert result.reasons == ()
    assert result.reservation_id == "res-1"
    assert result.effect_ref is not None
    assert result.effect_ref.owner == "repair_custody"
    assert result.effect_ref.record_type == "effect_receipt"
    assert result.effect_ref.identity == "res-1"
    assert result.effect_ref.locator == "repair_effect://key-1:res-1"
    assert result.event_id is not None and result.event_digest is not None
    assert result.event_replayed is False
    assert result.gate_result is None and result.allowlist_verdict is None

    # Every gate ran exactly once before the unified fixer.
    assert gate.calls == ["l1"]
    assert len(allowlist.calls) == 1
    assert len(boundary.calls) == 1
    # The exact occurrence was delegated through delegate_to_simple_fixer.
    assert len(delegation.calls) == 1
    call = delegation.calls[0]
    assert call["queue_dir"] == str(tmp_path / "requests")
    assert call["request_id"] == "req-1"
    assert call["session_id"] == "sess-1"
    assert call["kind"] == "immediate_trigger"
    # No prior canonical outcome existed.
    assert len(receipts.calls) == 1 and receipts.calls[0] is not None

    # Exactly one source_change event row carrying the separate owner receipt.
    rows = _event_rows(ledger, result.event_id)
    assert len(rows) == 1
    event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert event.action_kind.value == "source_change"
    assert event.payload.kind == "source_change"
    assert event.payload.change_ref == result.effect_ref
    assert event.payload.source_digest == "a" * 64
    assert len(event.owner_receipts.receipt_refs) == 1
    assert event.owner_receipts.receipt_refs[0] == result.effect_ref
    assert canonical_digest(event) == result.event_digest


def test_effect_route_refuses_master_gate_off_before_any_seam(tmp_path: Path) -> None:
    gate = _GateSpy(False)
    allowlist = _AllowlistSpy()
    boundary = _BoundarySpy(True)
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            gate=gate,
            allowlist=allowlist,
            boundary=boundary,
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.MUTATION_DISABLED in result.reasons
    assert result.event_id is None and result.effect_ref is None
    assert allowlist.calls == [] and boundary.calls == [] and delegation.calls == []
    assert not MaintenanceLedger(tmp_path).events_path.exists()


def test_effect_route_refuses_non_allowlisted_effect(tmp_path: Path) -> None:
    allowlist = _AllowlistSpy(verdict=AllowlistVerdict.ACTION_OFF)
    boundary = _BoundarySpy(True)
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            allowlist=allowlist,
            boundary=boundary,
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.EFFECT_NOT_ALLOWLISTED in result.reasons
    assert result.allowlist_verdict == "action_off"
    assert boundary.calls == [] and delegation.calls == []


def test_effect_route_refuses_blocked_action_boundary(tmp_path: Path) -> None:
    boundary = _BoundarySpy(authorized=False)
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            boundary=boundary,
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.ACTION_BOUNDARY_BLOCKED in result.reasons
    assert result.gate_result == "blocked_stale_grant"
    assert delegation.calls == []
    assert len(boundary.calls) == 1
    # The fresh M7 validation received the exact canonical coordinates.
    call = boundary.calls[0]
    assert call["action_type"] == "repair"
    assert call["run_authority_grant_id"] == "g-1"
    assert call["coordinator_fence_token"] == 7
    assert call["wbc_attempt_reference"] == ATTEMPT_ID


def test_effect_route_refuses_missing_boundary_inputs(tmp_path: Path) -> None:
    identity = _identity()
    del identity["run_authority_grant_id"]
    boundary = _BoundarySpy(True)
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            boundary=boundary,
            identity=identity,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.BOUNDARY_INPUTS_MISSING in result.reasons
    assert boundary.calls == []


def test_effect_route_refuses_stale_authority_before_delegation(tmp_path: Path) -> None:
    registry = _accepted_registry()
    delegation = _DelegationSpy()
    lease = _Lease(custody_epoch=3, occurrence_id=OCCURRENCE_ID, fencing_token="tok-1")
    stale_expected = ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest="f" * 64,  # pinned digest does not match the live lease record
        fencing_token="tok-1",
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            lease=lease,
            expected=stale_expected,
            lease_digest="f" * 64,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.STALE_AUTHORITY in result.reasons
    assert delegation.calls == []


def test_effect_route_adopts_reserved_receipt_without_redriving(tmp_path: Path) -> None:
    registry = _accepted_registry()
    delegation = _DelegationSpy(outcome="delegated", reservation_id="res-9")
    receipts = _ReceiptsSpy(_reservation(state="RESERVED", reservation_id="res-9"))
    ledger = MaintenanceLedger(tmp_path)
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            receipts=receipts,
            ledger=ledger,
        )
    )

    assert result.outcome is EffectOutcome.ADOPTED
    assert result.adopted_state == "RESERVED"
    assert result.reservation_id == "res-9"
    assert result.effect_ref is not None and result.effect_ref.identity == "res-9"
    # The unified fixer was NEVER invoked: the effect is not redriven.
    assert delegation.calls == []
    # The adopted outcome is appended once as a separate owner receipt.
    rows = _event_rows(ledger, result.event_id)
    assert len(rows) == 1
    event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert event.action_kind.value == "source_change"
    assert event.payload.change_ref == result.effect_ref


def test_effect_route_adopts_terminal_outcome_and_appends_once(tmp_path: Path) -> None:
    registry = _accepted_registry()
    delegation = _DelegationSpy()
    receipts = _ReceiptsSpy(
        _reservation(state="COMPLETED", reservation_id="res-2", repair_identity_key="key-2")
    )
    ledger = MaintenanceLedger(tmp_path)
    kwargs = _effect_kwargs(
        tmp_path=tmp_path,
        registry=registry,
        delegation=delegation,
        receipts=receipts,
        ledger=ledger,
    )

    first = route_allowlisted_effect(**kwargs)
    second = route_allowlisted_effect(**kwargs)

    assert first.outcome is EffectOutcome.ADOPTED
    assert first.adopted_state == "COMPLETED"
    assert second.outcome is EffectOutcome.ADOPTED
    assert second.event_id == first.event_id
    assert second.event_replayed is True
    # One event row for the exact retry (crash before Maintenance append).
    assert len(_event_rows(ledger, first.event_id)) == 1
    # The effect was never redriven on either attempt.
    assert delegation.calls == []
    assert len(receipts.calls) == 2


def test_effect_route_delegation_rejection_never_appends(tmp_path: Path) -> None:
    delegation = _DelegationSpy(outcome="delegation_failed")
    ledger = MaintenanceLedger(tmp_path)
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            delegation=delegation,
            ledger=ledger,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.DELEGATION_REJECTED in result.reasons
    assert result.delegation_outcome == "delegation_failed"
    assert result.event_id is None
    assert not ledger.events_path.exists()


def test_effect_route_missing_effect_receipt_after_delegation(tmp_path: Path) -> None:
    class _NoReceiptDelegation(_DelegationSpy):
        def __call__(self, delegation: Any, **kwargs: Any) -> RepairDelegationResult:
            self.calls.append({"delegation": delegation, **kwargs})
            return RepairDelegationResult(
                outcome="delegated",
                evidence={"simple_fixer_outcome": "attempted"},
            )

    delegation = _NoReceiptDelegation()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.MISSING_EFFECT_RECEIPT in result.reasons
    assert result.delegation_outcome == "delegated"
    assert result.event_id is None


def test_effect_route_receipt_query_failure_fails_closed(tmp_path: Path) -> None:
    receipts = _ReceiptsSpy(None, error=True)
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            delegation=delegation,
            receipts=receipts,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.RECEIPT_UNAVAILABLE in result.reasons
    assert delegation.calls == []


def test_effect_route_rejects_wrong_install_hash_before_delegation(tmp_path: Path) -> None:
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            effect_kind=EffectKind.INSTALLATION,
            install_digest="not-a-sha256-digest",
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.INVALID_INSTALL_DIGEST in result.reasons
    assert delegation.calls == []


def test_effect_route_rejects_empty_retrigger_reason(tmp_path: Path) -> None:
    delegation = _DelegationSpy()
    result = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=_accepted_registry(),
            effect_kind=EffectKind.RETRIGGER,
            reason="   ",
            delegation=delegation,
        )
    )

    assert result.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.INVALID_RETRIGGER_REASON in result.reasons
    assert delegation.calls == []


def test_effect_route_install_and_retrigger_append_distinct_references(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    install = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            effect_kind=EffectKind.INSTALLATION,
            delegation=_DelegationSpy(reservation_id="res-i"),
            install_digest="b" * 64,
            ledger=ledger,
        )
    )
    retrigger = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            effect_kind=EffectKind.RETRIGGER,
            delegation=_DelegationSpy(reservation_id="res-r"),
            reason="verification failed",
            ledger=ledger,
        )
    )

    assert install.outcome is EffectOutcome.DELEGATED
    assert retrigger.outcome is EffectOutcome.DELEGATED
    assert install.event_id != retrigger.event_id
    rows = _event_rows(ledger, install.event_id)
    assert len(rows) == 1
    install_event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert install_event.action_kind.value == "installation"
    assert install_event.payload.kind == "installation"
    assert install_event.payload.install_ref == install.effect_ref
    assert install_event.payload.install_digest == "b" * 64
    retrigger_event = strict_loads(
        OperationalEvent, _event_rows(ledger, retrigger.event_id)[0]["payload"]
    )
    assert retrigger_event.action_kind.value == "retrigger"
    assert retrigger_event.payload.kind == "retrigger"
    assert retrigger_event.payload.retrigger_ref == retrigger.effect_ref
    assert retrigger_event.payload.reason == "verification failed"
    # Distinct lifecycle actions coexist for ONE occurrence.
    assert install_event.occurrence.occurrence_id == OCCURRENCE_ID
    assert retrigger_event.occurrence.occurrence_id == OCCURRENCE_ID


def test_effect_route_rejects_divergent_reuse_of_the_occurrence_action(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    first = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            delegation=_DelegationSpy(reservation_id="res-1"),
            ledger=ledger,
        )
    )
    assert first.outcome is EffectOutcome.DELEGATED

    # A retried route that resolves to a DIFFERENT canonical reservation
    # reuses the same lifecycle action key with different content: the
    # journal rejects the divergent duplicate without appending.
    second = route_allowlisted_effect(
        **_effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            delegation=_DelegationSpy(reservation_id="res-2"),
            ledger=ledger,
        )
    )

    assert second.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.DIVERGENT_REUSE in second.reasons
    assert second.event_id is None
    assert len(_event_rows(ledger, first.event_id)) == 1


def test_effect_result_round_trips_through_strict_codec(tmp_path: Path) -> None:
    result = route_allowlisted_effect(
        **_effect_kwargs(tmp_path=tmp_path, registry=_accepted_registry())
    )
    decoded = strict_loads(EffectRoutingResult, result.model_dump(mode="json"))
    assert decoded.outcome is EffectOutcome.DELEGATED
    assert decoded.effect_ref == result.effect_ref
    assert decoded.event_id == result.event_id
    assert canonical_digest(decoded) == canonical_digest(result)


def test_boundary_inputs_from_identity_pure_extraction() -> None:
    grant, fence, wbc_ref = boundary_inputs_from_identity(_identity())
    assert grant == "g-1"
    assert fence == 7
    assert wbc_ref == ATTEMPT_ID

    missing, missing_fence, _ = boundary_inputs_from_identity({})
    assert missing is None and missing_fence is None


def test_module_delegates_only_through_the_unified_fixer() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "maintenance_recovery.py"
    ).read_text(encoding="utf-8")
    # The effect edges consume the canonical seams as module defaults.
    assert "delegate_to_simple_fixer" in source
    assert "validate_action_boundary_simple" in source
    assert "check_effect_class" in source
    assert "mutation_authorized" in source
    # ... and never spawn a fixer, run a raw command, or write an effect
    # ledger of their own.
    for banned in (
        "subprocess",
        "os.system",
        "Popen(",
        "class RepairEffectLedger",
        "class SimpleFixer",
        "def reserve(",
        "def complete(",
    ):
        assert banned not in source, f"maintenance_recovery.py reimplements {banned!r}"


# ---------------------------------------------------------------------------
# Plan Step 12 / T13: verified recurrence admission + human escalation
# ---------------------------------------------------------------------------


def _escalation_owner_ref(identity: str = "esc-1") -> OwnerRef:
    """One immutable locator-only reference to a durable escalation record."""
    return OwnerRef(
        owner="maintenance",
        record_type="escalation",
        identity=identity,
        schema_version="1",
        locator=f"escalation://{identity}",
        digest="e" * 64,
    )


def _predecessor_events(
    occurrence_id: str = "occ-1",
    request_id: str = "req-1",
    *,
    closure_event_id: str = "terminal_verification:occ-1:t1",
) -> list[OperationalEvent]:
    """A closed predecessor: repair_request + terminal-verification closure."""
    coords = _coordinates()
    occurrence = OccurrenceCoordinates(
        occurrence_id=occurrence_id, canonical_digest="1" * 64
    )
    request_ref = OwnerRef(
        owner="repair_custody",
        record_type="request",
        identity=request_id,
        schema_version="1",
        locator=f"repair_request://{request_id}",
        digest="d" * 64,
    )
    repair_request = OperationalEvent.build(
        event_id=f"repair_request:{occurrence_id}:{request_id}",
        occurrence=occurrence,
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(
            principal="producer-1", role=ProducerRole.REPAIR_PRODUCER
        ),
        payload=RepairRequestPayload(request_id=request_id, request_ref=request_ref),
        observed_at=UtcTime(_ts()),
    )
    terminal = OperationalEvent.build(
        event_id=closure_event_id,
        occurrence=occurrence,
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(
            principal="verifier-1", role=ProducerRole.VERIFIER
        ),
        payload=TerminalVerificationPayload(
            verifier=VerifierProvenance(
                principal="verifier-1",
                runtime_digest="b" * 64,
                source_digest="c" * 64,
                observed_at=UtcTime(_ts()),
            ),
            terminal_reason="recovered",
        ),
        observed_at=UtcTime(_ts()),
    )
    return [repair_request, terminal]


def _seed_predecessor(
    ledger: MaintenanceLedger,
    *,
    occurrence_id: str = "occ-1",
    request_id: str = "req-1",
    closure_event_id: str = "terminal_verification:occ-1:t1",
) -> None:
    for event in _predecessor_events(
        occurrence_id, request_id, closure_event_id=closure_event_id
    ):
        ledger.append(event)


def _recurrence_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    spy: _EnqueueSpy | Any,
    ledger: MaintenanceLedger,
    predecessor_occurrence_id: str = "occ-1",
    predecessor_event_id: str = "terminal_verification:occ-1:t1",
    root_cause_cluster: str | None = "cluster-1",
    budget: OccurrenceBudget | None = None,
    new_occurrence_id: str = "occ-2",
    new_lease_id: str = "lease-2",
    new_epoch: int = 4,
    new_run_id: str = "run-2",
    request_id: str = "req-2",
    identity: Mapping[str, Any] | None = None,
    expected: ExpectedRequestAuthority | None = None,
    sources: list[Any] | None = None,
    lease: _Lease | None = None,
    view: _View | None = None,
) -> dict[str, Any]:
    """Kwargs that admit a recurrence onto FRESH occurrence occ-2 / lease-2."""
    occurrence = OccurrenceCoordinates(
        occurrence_id=new_occurrence_id, canonical_digest="9" * 64
    )
    lease = lease if lease is not None else _Lease(
        custody_epoch=new_epoch, occurrence_id=new_occurrence_id, fencing_token="tok-2"
    )
    run_authority = RunAuthorityCoordinates(run_id=new_run_id, satisfied=True)
    policy = PolicyVersionCoordinates(policy_version="p1", policy_digest="2" * 64)
    target = ActionTarget(target=TARGET_ID, target_type="path")
    producer = ProducerPrincipal(principal="verifier-1", role=ProducerRole.VERIFIER)
    expected = expected if expected is not None else ExpectedRequestAuthority(
        occurrence_id=new_occurrence_id,
        lease_id=new_lease_id,
        lease_digest=_lease_digest(lease),
        fencing_token="tok-2",
        run_id=new_run_id,
        attempt_id=ATTEMPT_ID,
    )
    identity = identity if identity is not None else _identity(
        lease_id=new_lease_id,
        epoch=new_epoch,
        occurrence_digest="9" * 64,
        run_id=new_run_id,
    )
    sources = sources if sources is not None else _sources(
        registry=registry,
        view=view if view is not None else _View(run_id=new_run_id),
        store=_SpyStore(ledger=_Ledger(_Event(1))),
        lease=lease,
        lease_id=new_lease_id,
    )
    return {
        "occurrence": occurrence,
        "lease": LeaseCoordinates(
            lease_id=new_lease_id,
            custody_epoch=new_epoch,
            lease_digest=_lease_digest(lease),
        ),
        "run_authority": run_authority,
        "policy": policy,
        "target": target,
        "producer": producer,
        "observed_at": UtcTime(_ts()),
        "occurrence_identity": identity,
        "sources": sources,
        "predecessor_occurrence_id": predecessor_occurrence_id,
        "predecessor_event_id": predecessor_event_id,
        "root_cause_cluster": root_cause_cluster,
        "budget": budget,
        "environment": "production",
        "run": new_run_id,
        "attempt": ATTEMPT_ID,
        "expected": expected,
        "handoff_resolver": registry.resolve,
        "enqueue_fn": spy,
        "ledger": ledger,
        "wbc_attempt": WbcAttemptCoordinates(attempt_id=ATTEMPT_ID),
        "queue_root": tmp_path / "requests",
        "session": "sess-1",
        "problem_signature": {"kind": "blocker", "digest": "3" * 64},
        "source": "maintenance_recovery",
        "root_cause_hint": {"summary": "recurrence"},
        "marker_dir": tmp_path / "markers",
        "target_mapping": {"plan": "plan-1", "phase": "repair"},
        "workspace": tmp_path / "ws",
        "run_kind": "maintenance",
        "evidence_cursor_digest": "4" * 64,
    }


class _CoalescingEnqueueSpy:
    """Canonical seam spy: first call accepts, identical calls coalesce."""

    def __init__(self, request_id: str = "req-2") -> None:
        self.request_id = request_id
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            first = len(self.calls) == 0
            self.calls.append(kwargs)
        status = "accepted" if first else "coalesced"
        record = {
            "schema_version": "claimable-repair-request-v1",
            "kind": "repair_request",
            "request_id": self.request_id,
            "session": str(kwargs.get("session") or ""),
            "problem_signature_key": "sig-key-1",
            "repair_identity_key": "sha256:" + "f" * 64,
            "source": str(kwargs.get("source") or ""),
        }
        return {
            "status": status,
            "request": record,
            "path": f"{self.request_id}.json",
            "decision": {"decision": "accepted" if first else "coalesced"},
        }


def test_recurrence_admission_creates_fresh_occurrence_with_new_authority_and_budget(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")
    budget = OccurrenceBudget(max_attempts=3, attempts_used=0)
    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=ledger,
            budget=budget,
        )
    )

    assert result.outcome is RecurrenceAdmissionOutcome.ADMITTED
    assert result.reasons == ()
    assert result.predecessor_occurrence_id == "occ-1"
    assert result.predecessor_event_id == "terminal_verification:occ-1:t1"
    assert result.new_occurrence_id == "occ-2"
    assert result.request_id == "req-2"
    assert result.request_ref is not None
    assert result.request_ref.identity == "req-2"  # a FRESH receipt, never req-1
    assert result.event_id is not None and result.event_digest is not None
    assert result.event_replayed is False
    assert result.budget == {"max_attempts": 3, "attempts_used": 0}

    # 1. The canonical seam was called exactly once with the NEW lease/epoch/keys.
    assert len(spy.calls) == 1
    translated = spy.calls[0]["occurrence_identity"]
    assert translated["lease_id"] == "lease-2"
    assert translated["custody_epoch"] == 4
    assert translated["occurrence"]["occurrence_digest"] == "9" * 64
    assert translated["occurrence"]["run_id"] == "run-2"

    # 2. One fresh repair_request event AND one recurrence event were appended.
    assert len(_event_rows(ledger, result.request_event_id)) == 1
    recurrence_rows = _event_rows(ledger, result.event_id)
    assert len(recurrence_rows) == 1
    event = strict_loads(OperationalEvent, recurrence_rows[0]["payload"])
    assert event.action_kind.value == "recurrence"
    assert isinstance(event.payload, RecurrencePayload)
    assert event.payload.recurrence.predecessor_occurrence_id == "occ-1"
    assert event.payload.recurrence.predecessor_event_id == "terminal_verification:occ-1:t1"
    assert event.payload.recurrence.root_cause_cluster == "cluster-1"
    assert canonical_digest(event) == result.event_digest

    # 3. The fresh occurrence coordinates are bound: new lease/epoch/run and a
    #    fresh operational action key derived from the NEW occurrence digest.
    assert event.occurrence.occurrence_id == "occ-2"
    assert event.occurrence.canonical_digest == "9" * 64
    assert event.lease.lease_id == "lease-2"
    assert event.lease.custody_epoch == 4
    assert event.run_authority.run_id == "run-2"
    assert event.producer.role is ProducerRole.VERIFIER

    # 4. Prior receipts are NEVER reused: the only owner receipt is the fresh
    #    request-2 reference, not the predecessor's request-1 reference.
    assert tuple(ref.identity for ref in event.owner_receipts.receipt_refs) == ("req-2",)
    assert event.owner_receipts.receipt_refs[0] == result.request_ref

    # 5. The fresh occurrence-scoped budget rides on the recurrence event.
    assert event.extensions is not None
    assert event.extensions.root["occurrence_budget"] == {
        "max_attempts": 3,
        "attempts_used": 0,
    }

    # 6. The recurrence reduces into custody as a fresh causally-linked
    #    occurrence with the recurrence chain, never the predecessor's state.
    custody = reduce_custody(
        event, CustodyProjection(), cursor=1, event_digest=canonical_digest(event)
    )
    assert custody.occurrence_id == "occ-2"
    assert custody.lease_id == "lease-2"
    assert custody.custody_epoch == 4
    assert custody.run_id == "run-2"
    assert len(custody.recurrences) == 1
    assert custody.recurrences[0].predecessor_occurrence_id == "occ-1"
    assert custody.recurrences[0].predecessor_event_id == "terminal_verification:occ-1:t1"
    assert custody.recurrences[0].verified is True
    assert custody.open is True


def test_recurrence_admission_rejects_missing_predecessor(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")
    kwargs = _recurrence_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
    )
    kwargs["predecessor_occurrence_id"] = ""
    kwargs["predecessor_event_id"] = ""

    result = admit_verified_recurrence(**kwargs)

    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.MISSING_PREDECESSOR in result.reasons
    assert spy.calls == []  # the seam was never consulted


def test_recurrence_admission_rejects_same_occurrence_reuse(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")
    # The "fresh" occurrence IS the predecessor occurrence: not a recurrence.
    kwargs = _recurrence_kwargs(
        tmp_path=tmp_path,
        registry=registry,
        spy=spy,
        ledger=ledger,
        new_occurrence_id="occ-1",
        new_lease_id="lease-1",
        new_epoch=3,
        new_run_id="run-1",
    )

    result = admit_verified_recurrence(**kwargs)

    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.SAME_OCCURRENCE_REUSE in result.reasons
    assert spy.calls == []


def test_recurrence_admission_requires_predecessor_closure(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="accepted", request_id="req-2")

    # (a) The ledger has no closure at all: PREDECESSOR_NOT_CLOSED.
    empty_ledger = MaintenanceLedger(tmp_path / "empty")
    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=empty_ledger,
        )
    )
    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.PREDECESSOR_NOT_CLOSED in result.reasons
    assert spy.calls == []

    # (b) An event with the claimed id exists but is NOT a terminal
    #     verification: the predecessor is not closed.
    ledger = MaintenanceLedger(tmp_path / "open")
    coords = _coordinates()
    occurrence = OccurrenceCoordinates(
        occurrence_id="occ-1", canonical_digest="1" * 64
    )
    ledger.append(
        OperationalEvent.build(
            event_id="terminal_verification:occ-1:t1",
            occurrence=occurrence,
            lease=coords["lease"],
            run_authority=coords["run_authority"],
            policy=coords["policy"],
            target=coords["target"],
            producer=ProducerPrincipal(
                principal="observer-1", role=ProducerRole.OBSERVER
            ),
            payload=ProgressObservationPayload(progress_refs=()),
            observed_at=UtcTime(_ts()),
        )
    )
    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=ledger,
        )
    )
    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.PREDECESSOR_NOT_CLOSED in result.reasons
    assert spy.calls == []


def test_recurrence_admission_rejects_reused_receipt(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)  # predecessor receipt is req-1
    # The fresh occurrence resolves to the SAME canonical request receipt
    # (req-1): a prior receipt is never reused for a different occurrence.
    spy = _EnqueueSpy(status="accepted", request_id="req-1")

    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=ledger,
        )
    )

    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.REUSED_RECEIPT in result.reasons
    # The recurrence event was never appended (only the fresh occurrence's
    # repair_request row may exist from the seam; the recurrence is rejected).
    assert result.event_id is None
    assert len(_event_rows(ledger, "recurrence:occ-2:terminal_verification:occ-1:t1")) == 0


def test_recurrence_admission_rejects_consumed_budget(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")
    consumed = OccurrenceBudget(max_attempts=3, attempts_used=1)

    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=ledger,
            budget=consumed,
        )
    )

    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.INVALID_BUDGET in result.reasons
    assert spy.calls == []


def test_recurrence_admission_maps_pending_handoff(tmp_path: Path) -> None:
    registry = _registry()  # every handoff pending
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")

    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
        )
    )

    assert result.outcome is RecurrenceAdmissionOutcome.REJECTED
    assert RecurrenceRejectReason.PENDING_HANDOFF in result.reasons
    assert spy.calls == []


def test_concurrent_recurrence_admission_produces_one_request_and_one_event(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _CoalescingEnqueueSpy(request_id="req-2")
    kwargs = _recurrence_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
    )

    results: list[RecurrenceAdmissionResult] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def run() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(admit_verified_recurrence(**kwargs))
        except BaseException as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors
    assert len(results) == 2
    # One admission created the fresh request, the other joined the identical
    # request; both produced the SAME recurrence event.
    assert {result.outcome for result in results} == {
        RecurrenceAdmissionOutcome.ADMITTED,
        RecurrenceAdmissionOutcome.JOINED,
    }
    assert results[0].request_id == results[1].request_id == "req-2"
    assert results[0].event_id == results[1].event_id
    assert len(_event_rows(ledger, results[0].request_event_id)) == 1
    assert len(_event_rows(ledger, results[0].event_id)) == 1
    # The canonical seam was consulted by both admissions but coalesced.
    assert len(spy.calls) == 2
    assert {call["occurrence_identity"]["lease_id"] for call in spy.calls} == {"lease-2"}


def test_recurrence_result_round_trips_through_strict_codec(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    _seed_predecessor(ledger)
    spy = _EnqueueSpy(status="accepted", request_id="req-2")
    result = admit_verified_recurrence(
        **_recurrence_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=spy,
            ledger=ledger,
            budget=OccurrenceBudget(max_attempts=2, attempts_used=0),
        )
    )
    decoded = strict_loads(RecurrenceAdmissionResult, result.model_dump(mode="json"))
    assert decoded.outcome is RecurrenceAdmissionOutcome.ADMITTED
    assert decoded.request_ref == result.request_ref
    assert decoded.event_id == result.event_id
    assert canonical_digest(decoded) == canonical_digest(result)


def test_human_escalation_records_immutable_owner_ref_and_keeps_custody_open(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    coords = _coordinates()
    esc_ref = _escalation_owner_ref("esc-1")
    result = record_human_escalation(
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(principal="observer-1", role=ProducerRole.OBSERVER),
        observed_at=UtcTime(_ts()),
        escalation_owner="owner-1",
        reason="ambiguous blocker requires human decision",
        escalation_ref=esc_ref,
        ledger=ledger,
        wbc_attempt=coords["wbc_attempt"],
    )

    assert result.outcome is EscalationOutcome.RECORDED
    assert result.reasons == ()
    assert result.escalation_owner == "owner-1"
    assert result.escalation_ref == esc_ref
    assert result.event_id is not None and result.event_digest is not None

    rows = _event_rows(ledger, result.event_id)
    assert len(rows) == 1
    event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert event.action_kind.value == "human_escalation"
    assert event.payload.escalation.human_gate is True  # never a waiver
    assert event.payload.escalation.escalation_owner == "owner-1"
    assert event.payload.escalation.escalation_ref == esc_ref

    # Custody stays OPEN: the escalation appends the reference without ever
    # closing custody (no terminal, no waiver, no force-proceed).
    custody = reduce_custody(
        event, CustodyProjection(), cursor=1, event_digest=canonical_digest(event)
    )
    assert custody.open is True
    assert custody.terminal is False
    assert custody.escalated is True
    assert custody.escalations == (event.payload.escalation,)


def test_human_escalation_rejects_missing_owner_and_missing_ref(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    coords = _coordinates()
    esc_ref = _escalation_owner_ref("esc-1")

    # Missing escalation owner: typed, nothing appended.
    missing_owner = record_human_escalation(
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(principal="observer-1", role=ProducerRole.OBSERVER),
        observed_at=UtcTime(_ts()),
        escalation_owner="",
        reason="ambiguous blocker",
        escalation_ref=esc_ref,
        ledger=ledger,
    )
    assert missing_owner.outcome is EscalationOutcome.REJECTED
    assert EscalationRejectReason.MISSING_ESCALATION_OWNER in missing_owner.reasons
    assert missing_owner.event_id is None

    # Missing immutable escalation reference: typed, nothing appended.
    missing_ref = record_human_escalation(
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(principal="observer-1", role=ProducerRole.OBSERVER),
        observed_at=UtcTime(_ts()),
        escalation_owner="owner-1",
        reason="ambiguous blocker",
        escalation_ref=None,  # type: ignore[arg-type]
        ledger=ledger,
    )
    assert missing_ref.outcome is EscalationOutcome.REJECTED
    assert EscalationRejectReason.INVALID_ESCALATION_REF in missing_ref.reasons
    assert missing_ref.event_id is None

    assert not MaintenanceLedger(tmp_path).events_path.exists()


def test_human_escalation_exact_retry_dedupes_and_divergent_reuse_rejects(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    coords = _coordinates()
    esc_ref = _escalation_owner_ref("esc-1")
    kwargs = {
        "occurrence": coords["occurrence"],
        "lease": coords["lease"],
        "run_authority": coords["run_authority"],
        "policy": coords["policy"],
        "target": coords["target"],
        "producer": ProducerPrincipal(
            principal="observer-1", role=ProducerRole.OBSERVER
        ),
        "observed_at": UtcTime(_ts()),
        "escalation_owner": "owner-1",
        "reason": "ambiguous blocker requires human decision",
        "escalation_ref": esc_ref,
        "ledger": ledger,
    }

    first = record_human_escalation(**kwargs)
    replay = record_human_escalation(**kwargs)
    assert first.outcome is EscalationOutcome.RECORDED
    assert replay.outcome is EscalationOutcome.RECORDED
    assert replay.event_id == first.event_id
    assert replay.event_replayed is True
    assert len(_event_rows(ledger, first.event_id)) == 1

    # A DIFFERENT escalation for the same occurrence reuses the same lifecycle
    # action key with different content: the journal rejects it.
    divergent = record_human_escalation(
        **{**kwargs, "escalation_ref": _escalation_owner_ref("esc-2")}
    )
    assert divergent.outcome is EscalationOutcome.REJECTED
    assert EscalationRejectReason.DIVERGENT_REUSE in divergent.reasons
    assert divergent.event_id is None


def test_escalation_result_round_trips_through_strict_codec(tmp_path: Path) -> None:
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    coords = _coordinates()
    result = record_human_escalation(
        occurrence=coords["occurrence"],
        lease=coords["lease"],
        run_authority=coords["run_authority"],
        policy=coords["policy"],
        target=coords["target"],
        producer=ProducerPrincipal(principal="observer-1", role=ProducerRole.OBSERVER),
        observed_at=UtcTime(_ts()),
        escalation_owner="owner-1",
        reason="true human gate",
        escalation_ref=_escalation_owner_ref("esc-1"),
        ledger=ledger,
    )
    decoded = strict_loads(HumanEscalationResult, result.model_dump(mode="json"))
    assert decoded.outcome is EscalationOutcome.RECORDED
    assert decoded.escalation_ref == result.escalation_ref
    assert canonical_digest(decoded) == canonical_digest(result)


# ---------------------------------------------------------------------------
# submit_terminal_verification — canonical M7 terminal custody seam
# ---------------------------------------------------------------------------


class _TerminalBoundarySpy:
    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> ActionBoundaryResult:
        self.calls.append(kwargs)
        return ActionBoundaryResult(
            gate_result=(
                GateResult.AUTHORIZED
                if self.authorized
                else GateResult.BLOCKED_STALE_GRANT
            ),
            action_type="completion",
            target_digest="a" * 64,
            checks=(),
            enforcement_enabled=self.authorized,
        )


def _terminal_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    spy: _EnqueueSpy,
    ledger: MaintenanceLedger | None = None,
    boundary: _TerminalBoundarySpy | None = None,
    request_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coords = _coordinates()
    ledger = ledger if ledger is not None else MaintenanceLedger(tmp_path)
    rk = request_kwargs if request_kwargs is not None else _submit_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger,
        lease=_Lease(),
    )
    return {
        **coords,
        "observed_at": UtcTime(_ts()),
        "verifier": VerifierProvenance(
            principal="verifier-1",
            runtime_digest="b" * 64,
            source_digest="c" * 64,
            observed_at=UtcTime(_ts()),
        ),
        "terminal_reason": "independent verification of the controlled canary",
        "negative_control_refs": (),
        "verification_ref": OwnerRef(
            owner="repair_custody",
            record_type="verification",
            identity=OCCURRENCE_ID,
            locator=f"verification://{OCCURRENCE_ID}",
            digest="f" * 64,
        ),
        "sources": _sources(
            registry=registry, view=_View(), store=_SpyStore(), lease=_Lease()
        ),
        "environment": "production",
        "run": RUN_ID,
        "attempt": ATTEMPT_ID,
        "expected": ExpectedRequestAuthority(
            occurrence_id=OCCURRENCE_ID,
            lease_id=LEASE_ID,
            lease_digest=_lease_digest(_Lease()),
            fencing_token="tok-1",
            run_id=RUN_ID,
            attempt_id=ATTEMPT_ID,
        ),
        "boundary_fn": (
            boundary if boundary is not None else _TerminalBoundarySpy(authorized=True)
        ),
        "ledger": ledger,
        "wbc_attempt": coords["wbc_attempt"],
        "request_kwargs": rk,
    }


def test_terminal_submission_accepts_real_queued_status_and_uses_completion_boundary(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="queued", request_id="req-1")
    boundary = _TerminalBoundarySpy(authorized=True)
    ledger = MaintenanceLedger(tmp_path)
    result = submit_terminal_verification(
        **_terminal_kwargs(
            tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger,
            boundary=boundary,
        )
    )

    assert result.outcome is TerminalOutcome.SUBMITTED
    assert result.reasons == ()
    assert result.custody_closed is True
    assert result.enqueue_status == "queued"
    assert result.request_id == "req-1"
    assert result.event_replayed is False
    assert result.event_id == f"terminal_verification:{OCCURRENCE_ID}"
    # 1. The final action-validator reread was invoked exactly once with the
    #    canonical completion boundary contract.
    assert len(boundary.calls) == 1
    call = boundary.calls[0]
    assert call["action_type"] == "completion"
    assert call["run_authority_grant_id"] == "g-1"
    assert call["coordinator_fence_token"] == 7
    assert call["wbc_attempt_reference"] == ATTEMPT_ID
    assert call["target"]["task"] == TARGET_ID
    # 2. The terminal event is authored by the VERIFIER, never the repair
    #    producer, and appended exactly once.
    rows = _event_rows(ledger, result.event_id)
    assert len(rows) == 1
    event = strict_loads(OperationalEvent, rows[0]["payload"])
    assert event.producer.principal == "verifier-1"
    assert event.producer.role.value == "verifier"
    assert result.boundary_result is not None
    assert result.boundary_result.get("authorized") is True


def test_terminal_submission_joins_coalesced_request(tmp_path: Path) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="coalesced", request_id="req-9")
    result = submit_terminal_verification(
        **_terminal_kwargs(tmp_path=tmp_path, registry=registry, spy=spy)
    )

    assert result.outcome is TerminalOutcome.SUBMITTED
    assert result.custody_closed is True
    assert result.enqueue_status == "coalesced"
    assert result.request_id == "req-9"


def test_terminal_submission_exact_retry_replays_single_verifier_event(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="queued", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    kwargs = _terminal_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
    )

    first = submit_terminal_verification(**kwargs)
    second = submit_terminal_verification(**kwargs)

    assert first.outcome is TerminalOutcome.SUBMITTED
    assert second.outcome is TerminalOutcome.SUBMITTED
    assert second.event_replayed is True
    assert len(_event_rows(ledger, f"terminal_verification:{OCCURRENCE_ID}")) == 1


def test_terminal_submission_rejects_missing_or_invalid_boundary_result(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="queued", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    # Missing boundary function.
    kwargs = _terminal_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
    )
    kwargs["boundary_fn"] = None
    missing = submit_terminal_verification(**kwargs)
    assert missing.outcome is TerminalOutcome.REJECTED
    assert TerminalRejectReason.FINAL_BOUNDARY_REQUIRED in missing.reasons
    assert missing.custody_closed is False
    # Blocked boundary result.
    blocked = submit_terminal_verification(
        **_terminal_kwargs(
            tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger,
            boundary=_TerminalBoundarySpy(authorized=False),
        )
    )
    assert blocked.outcome is TerminalOutcome.REJECTED
    assert TerminalRejectReason.FINAL_BOUNDARY_BLOCKED in blocked.reasons
    assert blocked.custody_closed is False


def test_terminal_submission_maps_request_rejections_and_keeps_custody_open(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="rejected", request_id="")
    result = submit_terminal_verification(
        **_terminal_kwargs(tmp_path=tmp_path, registry=registry, spy=spy)
    )

    assert result.outcome is TerminalOutcome.REJECTED
    assert TerminalRejectReason.ENQUEUE_REJECTED in result.reasons
    assert result.custody_closed is False
    assert result.event_id is None


def test_terminal_submission_rejects_divergent_terminal_reuse(
    tmp_path: Path,
) -> None:
    registry = _accepted_registry()
    spy = _EnqueueSpy(status="queued", request_id="req-1")
    ledger = MaintenanceLedger(tmp_path)
    kwargs = _terminal_kwargs(
        tmp_path=tmp_path, registry=registry, spy=spy, ledger=ledger
    )
    first = submit_terminal_verification(**kwargs)
    assert first.outcome is TerminalOutcome.SUBMITTED
    # A divergent second terminal event for the same occurrence (different
    # verifier) must fail closed as divergent reuse, custody stays open.
    kwargs["verifier"] = VerifierProvenance(
        principal="verifier-2",
        runtime_digest="d" * 64,
        source_digest="e" * 64,
        observed_at=UtcTime(_ts()),
    )
    second = submit_terminal_verification(**kwargs)
    assert second.outcome is TerminalOutcome.REJECTED
    assert TerminalRejectReason.DIVERGENT_REUSE in second.reasons
    assert second.custody_closed is False
    assert len(_event_rows(ledger, f"terminal_verification:{OCCURRENCE_ID}")) == 1
