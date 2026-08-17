"""Cloud canary tests: report-only installed-runtime M3 lifecycle (T14).

These tests prove the Maintenance canary adapter ``maintenance_canary``
(M3 Plan Step 13):

* binds one canary to the EXACT M11 installed-runtime identity (strict
  runtime tuple, runtime digest, source digest) and fails closed on
  source/runtime digest mismatch;
* drives ONE occurrence-bound repair request, ONE allowlisted effect, and
  ALL canonical checkpoints through the same cloud adapter seams as
  production (``maintenance_recovery``), appending every durable result
  BEFORE any closure decision;
* keeps the run report-only (truthful non-authorizing terminal receipt,
  custody open) unless an operator sign-off is injected (``authorizing``),
  which submits the terminal event exactly once;
* covers forced install/retrigger failure, kill-switch rollback (with
  observation/ledger/replay preserved), stale verifier fencing, and
  source/runtime digest mismatch;
* reuses M11 installed-runtime identity, isolated-relaunch, and verifier
  evidence infrastructure without recreating it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.cloud import m11_live_canary, m11_workflow_canary
from arnold_pipelines.megaplan.cloud.maintenance_canary import (
    CanaryOutcome,
    CanaryRejectReason,
    CanaryRunResult,
    MaintenanceCanaryError,
    admit_maintenance_canary,
    canary_verifier_binding_matches,
    load_maintenance_canary_admission,
    rollback_maintenance_canary,
    run_maintenance_canary,
)
from arnold_pipelines.megaplan.cloud import maintenance_canary as canary_module
from arnold_pipelines.megaplan.cloud import maintenance_recovery
from arnold_pipelines.megaplan.cloud.maintenance_recovery import (
    EffectKind,
    EffectOutcome,
    EffectRejectReason,
    ExpectedRequestAuthority,
    RequestOutcome,
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
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointWindowKind,
    VerifierProvenance,
)
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HANDOFF_IDS,
    ApprovalEvidence,
    ApprovalState,
    HandoffRegistry,
    HandoffRow,
    WbcCoordinates,
)
from arnold_pipelines.megaplan.maintenance.identity import OwnerRef, UtcTime
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
from arnold_pipelines.megaplan.maintenance.verification import (
    ExpectedAuthority,
    NegativeControlResult,
    VerificationOutcome,
)

UTC = timezone.utc
REVISION = "a" * 40

OCCURRENCE_ID = "occ-1"
LEASE_ID = "lease-1"
RUN_ID = "run-1"
ATTEMPT_ID = "att-1"
FENCE = "tok-1"
TARGET_ID = "target-1"


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

    def __init__(self, view_hash: str = "a" * 64, run_id: str = RUN_ID) -> None:
        self.view_hash = view_hash
        self.run_id = run_id
        self.run_revision = "rev-1"
        self.journal_cursor = 7
        self.evidence_set_digest = "b" * 64
        self.grants = [_Grant("g-1", payload="PAYLOAD-SECRET")]
        self.decisions = [_Decision("d-1")]
        self.fences = [_Fence("att-9", FENCE)]
        self.attempts = [_Attempt("a-1")]
        self.quarantines = [_Quarantine("q-1")]
        self.diagnostics = [_Diagnostic("diag", "r-1")]


class _EventType:
    def __init__(self, value: str) -> None:
        self.value = value


class _Event:
    def __init__(self, sequence: int, event_type: str = "started") -> None:
        self.sequence = sequence
        self.event_type = _EventType(event_type)
        self.idempotency_key = f"key-{sequence}"

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
        self, cursor_key: str = "default", last_sequence: int = 0, last_position: str | None = None
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


class _PersistenceDiag:
    def __init__(self, target_event_sequence: int = 0) -> None:
        self.target_event_sequence = target_event_sequence

    def to_dict(self) -> dict:
        return {"target_event_sequence": self.target_event_sequence}


class _SpyStore:
    """Read/query/version-only WBC AttemptLedgerStore-shaped fake."""

    def __init__(self, *, contract: str = "c1", store: str = "s1") -> None:
        self._events: list[_Event] = []
        self._ledger = _Ledger(_Event(1))
        self._contract = contract
        self._store = store

    def get_contract_version(self) -> str:
        return self._contract

    def get_store_version(self) -> str:
        return self._store

    def read_events(self, attempt_id: str) -> list[_Event]:
        return self._events

    def read_ledger(self, attempt_id: str) -> _Ledger | None:
        return self._ledger

    def get_terminal_event(self, attempt_id: str) -> _Event | None:
        return None

    def query_gaps(self, attempt_id: str) -> list[_Gap]:
        return []

    def query_persistence_diagnostics(self, attempt_id: str) -> list[_PersistenceDiag]:
        return []

    def query_reconciliation_state(self, attempt_id: str) -> list[_PersistenceDiag]:
        return []

    def query_source_cursor(self, attempt_id: str, cursor_key: str) -> _Cursor | None:
        return _Cursor()


class _Lease:
    """M7 current-lease-shaped fake (epoch + occurrence + fence)."""

    def __init__(
        self,
        custody_epoch: int = 3,
        occurrence_id: str = OCCURRENCE_ID,
        fencing_token: str = FENCE,
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


def _accepted_row(handoff_id: str, *, source_path: str, schema_identity: str, digest: str) -> HandoffRow:
    return HandoffRow(
        id=handoff_id,
        source_path=source_path,
        schema_identity=schema_identity,
        owner_api_identity=f"owner.api.{handoff_id}",
        schema_version=schema_identity.rsplit(".", 1)[-1],
        digest=digest,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=(handoff_id == "M6A"),
        wbc_coordinates=(
            WbcCoordinates(incarnation="inc-1", restore_generation="rg-1", high_water="hw-1")
            if handoff_id == "M6A"
            else None
        ),
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
            ),
        }
    )


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
        "producer": ProducerPrincipal(
            principal="producer-1", role=ProducerRole.REPAIR_PRODUCER
        ),
        "wbc_attempt": WbcAttemptCoordinates(attempt_id=ATTEMPT_ID),
    }


def _identity(
    *, lease_id: str = LEASE_ID, epoch: int = 3, occurrence_digest: str = "1" * 64
) -> dict[str, Any]:
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
            "run_id": RUN_ID,
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


def _lease_digest(lease: _Lease | None = None) -> str:
    lease = lease if lease is not None else _Lease()
    import json as _json

    return hashlib.sha256(
        _json.dumps(lease.to_dict(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


# ---------------------------------------------------------------------------
# Seam spies
# ---------------------------------------------------------------------------


class _EnqueueSpy:
    def __init__(self, status: str = "accepted", request_id: str = "req-1") -> None:
        self.status = status
        self.request_id = request_id
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
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
            "status": self.status,
            "request": record,
            "path": f"{self.request_id}.json",
            "decision": {
                "decision": "accepted" if self.status == "accepted" else "coalesced"
            },
        }


class _GateSpy:
    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized
        self.calls: list[str] = []

    def __call__(self, path: str) -> bool:
        self.calls.append(path)
        return self.authorized


class _AllowlistSpy:
    def __init__(self, verdict: AllowlistVerdict = AllowlistVerdict.APPROVED) -> None:
        self.verdict = verdict

    def __call__(self, effect_class: str | RepairEffectClass) -> AllowlistCheckResult:
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
            # A valid closed delegation outcome; never an invented label.
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
    def __init__(self, prior: MutationReservation | None = None) -> None:
        self.prior = prior

    def __call__(self, identity: Mapping[str, Any]) -> MutationReservation | None:
        return self.prior


def _reservation(
    *, state: str = "RESERVED", reservation_id: str = "res-1", repair_identity_key: str = "key-1"
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


# ---------------------------------------------------------------------------
# Sources + adapter kwargs
# ---------------------------------------------------------------------------


def _sources(
    *,
    registry: HandoffRegistry,
    view: _View | None = None,
    store: _SpyStore | None = None,
    lease: _Lease | None = None,
    stale: bool = False,
) -> list[Any]:
    view = view if view is not None else _View()
    store = store if store is not None else _SpyStore()
    lease = lease if lease is not None else _Lease()
    stale_probe = (lambda _read: True) if stale else (lambda _read: False)
    return [
        run_authority_source(
            lambda: view,
            environment="production",
            stale_probe=stale_probe,
        ),
        wbc_source(
            store,
            ATTEMPT_ID,
            registry=registry,
            environment="production",
            stale_probe=stale_probe,
        ),
        custody_source(
            LEASE_ID,
            current_lease_provider=lambda _lease_id: lease,
            history_provider=lambda _lease_id: [],
            registry=registry,
            environment="production",
            stale_probe=stale_probe,
        ),
    ]


def _expected(lease: _Lease | None = None) -> ExpectedRequestAuthority:
    return ExpectedRequestAuthority(
        occurrence_id=OCCURRENCE_ID,
        lease_id=LEASE_ID,
        lease_digest=_lease_digest(lease),
        fencing_token=FENCE,
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
    )


def _request_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    spy: _EnqueueSpy,
    ledger: MaintenanceLedger | None = None,
    sources: list[Any] | None = None,
    lease_digest: str | None = None,
) -> dict[str, Any]:
    coords = _coordinates(lease_digest=lease_digest)
    return {
        **coords,
        "observed_at": UtcTime(_ts()),
        "occurrence_identity": _identity(),
        "sources": sources if sources is not None else _sources(registry=registry),
        "environment": "production",
        "run": RUN_ID,
        "attempt": ATTEMPT_ID,
        "expected": _expected(),
        "handoff_resolver": registry.resolve,
        "enqueue_fn": spy,
        "ledger": ledger if ledger is not None else MaintenanceLedger(tmp_path),
        "queue_root": tmp_path / "requests",
        "session": "sess-1",
        "problem_signature": {"kind": "blocker", "digest": "3" * 64},
        "source": "maintenance_canary",
        "root_cause_hint": {"summary": "blocker"},
        "marker_dir": tmp_path / "markers",
        "target_mapping": {"plan": "plan-1", "phase": "repair"},
        "workspace": tmp_path / "ws",
        "run_kind": "maintenance",
        "evidence_cursor_digest": "4" * 64,
    }


def _effect_kwargs(
    *,
    tmp_path: Path,
    registry: HandoffRegistry,
    effect_kind: EffectKind | str = EffectKind.INSTALLATION,
    delegation: _DelegationSpy | None = None,
    gate: _GateSpy | None = None,
    sources: list[Any] | None = None,
    ledger: MaintenanceLedger | None = None,
    install_digest: str | None = "a" * 64,
    source_digest: str | None = None,
    reason: str = "retrigger the canary worker",
) -> dict[str, Any]:
    coords = _coordinates()
    return {
        **coords,
        "effect_kind": effect_kind,
        "observed_at": UtcTime(_ts()),
        "repair_identity": _identity(),
        "sources": sources if sources is not None else _sources(registry=registry),
        "environment": "production",
        "run": RUN_ID,
        "attempt": ATTEMPT_ID,
        "expected": _expected(),
        "handoff_resolver": registry.resolve,
        "ledger": ledger if ledger is not None else MaintenanceLedger(tmp_path),
        "queue_root": tmp_path / "requests",
        "request_id": "req-1",
        "session": "sess-1",
        "effect_class": RepairEffectClass.MUTATE,
        "mutate": lambda occ: "changed",
        "source_digest": source_digest,
        "install_digest": install_digest,
        "reason": reason,
        "wbc_attempt": coords["wbc_attempt"],
        "mutation_gate_fn": gate if gate is not None else _GateSpy(True),
        "allowlist_fn": _AllowlistSpy(),
        "boundary_fn": _BoundarySpy(),
        "delegation_fn": delegation if delegation is not None else _DelegationSpy(),
        "receipts_fn": _ReceiptsSpy(),
    }


# ---------------------------------------------------------------------------
# M11 installed-runtime receipt + admission
# ---------------------------------------------------------------------------


def _runtime_receipt(
    path: Path,
    *,
    revision: str = REVISION,
    deployment_target: str = "production",
    deployment_id: str = "deploy-1",
    source_digest: str | None = None,
) -> dict:
    components = {
        name: {"ok": True}
        for name in (
            "interpreter",
            "editable_checkout",
            "pth_files",
            "imports",
            "source_lineage",
            "wrappers",
            "supervisor_command",
            "target_marker",
        )
    }
    components["interpreter"]["executable"] = sys.executable
    lineage = {"revision": revision, "expected_revision": revision}
    if source_digest is not None:
        lineage["source_digest"] = source_digest
    components["source_lineage"].update(lineage)
    components["target_marker"]["fields"] = {
        "deployment_target": deployment_target,
        "deployment_id": deployment_id,
    }
    payload = {
        "schema": "arnold.megaplan.m11_bound_runtime_identity.v1",
        "valid": True,
        "strict": True,
        "expected_revision": revision,
        "components": components,
    }
    payload["content_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return payload


def _canary_root(tmp_path: Path, name: str = "test-1") -> tuple[Path, Path]:
    base = tmp_path / "m11-canaries"
    root = base / f"maintenance-canary-{name}"
    root.mkdir(parents=True)
    return root, base


def _admit(tmp_path: Path, name: str = "test-1", **overrides: Any) -> tuple[Path, Any, dict]:
    root, base = _canary_root(tmp_path, name)
    runtime_path = root / "runtime.json"
    runtime = _runtime_receipt(runtime_path)
    admission = admit_maintenance_canary(
        root=root,
        job_id="job-1",
        deployment_target="production",
        deployment_id="deploy-1",
        expected_revision=REVISION,
        runtime_receipt_path=runtime_path,
        base_root=base,
        **overrides,
    )
    return root, admission, runtime


def _verifier(
    runtime_digest: str,
    source_digest: str,
    *,
    principal: str = "verifier-1",
    observed_at: datetime | None = None,
) -> VerifierProvenance:
    return VerifierProvenance(
        principal=principal,
        runtime_digest=runtime_digest,
        source_digest=source_digest,
        credential_envelope_ref=OwnerRef(
            owner="snapshot",
            record_type="credential_envelope",
            locator="envelope://verifier-1/1",
            digest="3" * 64,
        ),
        observed_at=UtcTime(observed_at if observed_at is not None else _ts()),
        direct_read_refs=(
            OwnerRef(
                owner="run_authority",
                record_type="grant",
                locator="grant://g-1",
                digest="4" * 64,
            ),
            OwnerRef(
                owner="wbc",
                record_type="attempt",
                locator="attempt://att-1",
                digest="5" * 64,
            ),
        ),
    )


def _controls() -> tuple[NegativeControlResult, ...]:
    return (
        NegativeControlResult(
            control_id="c2-f01",
            control_ref=OwnerRef(
                owner="conformance",
                record_type="negative_control",
                locator="control://c2/f01",
                digest="6" * 64,
            ),
            blocker_absent=True,
        ),
    )


def _pre_repair_ref() -> OwnerRef:
    return OwnerRef(
        owner="repair_custody",
        record_type="checkpoint",
        locator="checkpoint://occ-1/pre",
        digest="d" * 64,
        cursor="journal:5",
    )


def _progress_refs() -> tuple[OwnerRef, ...]:
    return (
        OwnerRef(
            owner="repair_custody",
            record_type="effect",
            locator="effect://occ-1/9",
            digest="e" * 64,
            cursor="journal:9",
        ),
    )


def _run_kwargs(
    *,
    root: Path,
    admission: Any,
    verifier: VerifierProvenance,
    tmp_path: Path,
    registry: HandoffRegistry,
    enqueue: _EnqueueSpy | None = None,
    delegation: _DelegationSpy | None = None,
    sources: list[Any] | None = None,
    ledger: MaintenanceLedger | None = None,
    authorizing: bool = False,
    rollback_on_failure: bool = False,
    stale: bool = False,
    expected_authority: Any | None = None,
    run_id: str = "run-canary-1",
    now: datetime | None = None,
    final_boundary_fn: Any | None = None,
    effect_kind: EffectKind | str = EffectKind.INSTALLATION,
    install_digest: str | None = "a" * 64,
    reason: str = "retrigger the canary worker",
) -> dict[str, Any]:
    sources = (
        sources
        if sources is not None
        else _sources(registry=registry, stale=stale)
    )
    return {
        "root": root,
        "run_id": run_id,
        "admission": admission,
        "verifier": verifier,
        "negative_controls": _controls(),
        "pre_repair_ref": _pre_repair_ref(),
        "progress_refs": _progress_refs(),
        "request_kwargs": _request_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            spy=enqueue if enqueue is not None else _EnqueueSpy(),
            ledger=ledger,
            sources=sources,
        ),
        "effect_kwargs": _effect_kwargs(
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            ledger=ledger,
            sources=sources,
            effect_kind=effect_kind,
            install_digest=install_digest,
            reason=reason,
        ),
        "anchor_at": UtcTime(_ts()),
        "now": UtcTime(now if now is not None else _ts() + timedelta(hours=4)),
        "authorizing": authorizing,
        "rollback_on_failure": rollback_on_failure,
        "expected_authority": expected_authority,
        "final_boundary_fn": final_boundary_fn,
        "base_root": root.parent,
        "persist": False,
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
# Success: one request, one effect, all checkpoints, report-only
# ---------------------------------------------------------------------------


def test_success_lifecycle_drives_one_request_one_effect_all_checkpoints_report_only(
    tmp_path: Path,
) -> None:
    root, admission, _ = _admit(tmp_path)
    registry = _accepted_registry()
    enqueue = _EnqueueSpy(status="accepted", request_id="req-1")
    delegation = _DelegationSpy(outcome="delegated", reservation_id="res-1")
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            enqueue=enqueue,
            delegation=delegation,
            ledger=ledger,
        )
    )

    assert result.outcome is CanaryOutcome.COMPLETED
    assert result.reasons == ()
    # 1. ONE canonical request through the enqueue-or-join seam.
    assert result.request is not None and result.request.outcome is RequestOutcome.ACCEPTED
    assert len(enqueue.calls) == 1
    # 2. ONE allowlisted effect through the unified fixer.
    assert result.effect is not None and result.effect.outcome is EffectOutcome.DELEGATED
    assert len(delegation.calls) == 1
    # 3. ALL canonical checkpoints evaluated (event-time order); each verified
    #    result was appended BEFORE any closure decision.
    assert [outcome.window for outcome in result.checkpoints] == [
        CheckpointWindowKind.IMMEDIATE,
        CheckpointWindowKind.FIVE_MINUTE,
        CheckpointWindowKind.ONE_HOUR,
        CheckpointWindowKind.NEXT_THREE_HOUR,
    ]
    assert all(
        outcome.verification.outcome is VerificationOutcome.VERIFIED
        for outcome in result.checkpoints
    )
    # The settled journal contract admits exactly ONE checkpoint_verification
    # event per occurrence: the first verified window appends durably, later
    # windows' identical action keys are rejected as DIVERGENT reuse with
    # nothing appended (no divergent ledger acceptance), and the evaluations
    # stay durable in the report-only receipts.
    assert all(outcome.appended is True for outcome in result.checkpoints)
    assert all(outcome.event_id is not None for outcome in result.checkpoints)
    assert len({outcome.event_id for outcome in result.checkpoints}) == 4
    # All four policy-required checkpoint windows are durably appended with
    # distinct stable lifecycle identities (no divergent reuse, no rewrite).
    rows = ledger.events_path.read_text(encoding="utf-8").strip().splitlines()
    checkpoint_rows = [
        row
        for row in rows
        if (json.loads(row).get("payload") or {}).get("action_kind")
        == "checkpoint_verification"
    ]
    assert len(checkpoint_rows) == 4

    def _row_checkpoint_window(row: str) -> str:
        """Extract the checkpoint window from one journal row.

        The journal may wrap the canonical event at different depths; both
        the direct ``payload.checkpoint`` and the nested event
        ``payload.payload.checkpoint`` shapes are accepted.
        """
        data = json.loads(row)
        payload = data.get("payload") or {}
        for candidate in (payload, payload.get("payload") or {}):
            checkpoint = candidate.get("checkpoint")
            if checkpoint is not None:
                return (
                    checkpoint.value
                    if hasattr(checkpoint, "value")
                    else str(checkpoint)
                )
        return ""

    assert {_row_checkpoint_window(row) for row in checkpoint_rows} == {
        window.value for window in CheckpointWindowKind
    }
    # 4. Terminal verified but report-only: truthful non-authorizing receipt,
    #    custody stays OPEN, no terminal event appended.
    assert result.terminal is not None
    assert result.terminal.verification.outcome is VerificationOutcome.VERIFIED
    assert result.terminal.submitted is False
    assert result.terminal.pending_signoff is True
    assert result.custody_open is True
    assert result.terminal_submitted is False
    assert _event_rows(ledger, "terminal_verification:occ-1") == []


def test_authorizing_run_submits_terminal_exactly_once(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="authorizing")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    kwargs = _run_kwargs(
        root=root,
        admission=admission,
        verifier=verifier,
        tmp_path=tmp_path,
        registry=registry,
        ledger=ledger,
        authorizing=True,
        final_boundary_fn=_BoundarySpy(),
        run_id="run-authorizing-1",
    )
    first = run_maintenance_canary(**kwargs)
    assert first.outcome is CanaryOutcome.COMPLETED
    assert first.terminal is not None and first.terminal.submitted is True
    assert first.terminal_submitted is True
    assert first.custody_open is False
    assert len(_event_rows(ledger, "terminal_verification:occ-1")) == 1

    # A replayed authorizing run (same lifecycle coordinates) deduplicates at
    # the journal boundary: still exactly one terminal row.
    kwargs["run_id"] = "run-authorizing-2"
    second = run_maintenance_canary(**kwargs)
    assert second.terminal is not None and second.terminal.submitted is True
    assert len(_event_rows(ledger, "terminal_verification:occ-1")) == 1


def test_report_only_run_never_submits_terminal_without_signoff(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="report-only")
    registry = _accepted_registry()
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            authorizing=False,
        )
    )
    assert result.outcome is CanaryOutcome.COMPLETED
    assert result.custody_open is True
    assert result.terminal_submitted is False
    assert result.terminal is not None and result.terminal.pending_signoff is True


# ---------------------------------------------------------------------------
# Forced install / retrigger failure
# ---------------------------------------------------------------------------


def test_forced_install_failure_rejects_without_appending(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="install-fail")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    delegation = _DelegationSpy(outcome="delegation_failed", reservation_id="res-x")
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            ledger=ledger,
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.EFFECT_REJECTED in result.reasons
    assert result.effect is not None
    assert result.effect.outcome is EffectOutcome.REJECTED
    assert EffectRejectReason.DELEGATION_REJECTED in result.effect.reasons
    # The canonical request WAS appended (one request event), but the effect
    # was never delegated and no effect/checkpoint event was ever appended.
    assert result.effect.event_id is None
    assert result.checkpoints == ()
    assert result.terminal is None
    assert result.custody_open is True
    rows = ledger.events_path.read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(row).get("payload") or {} for row in rows]
    assert [
        p.get("action_kind") for p in payloads if p.get("action_kind")
    ] == ["repair_request"]


def test_invalid_retrigger_reason_rejects_before_delegation(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="retrigger-fail")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    delegation = _DelegationSpy()
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            ledger=ledger,
            effect_kind=EffectKind.RETRIGGER,
            install_digest=None,
            reason="",
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.EFFECT_REJECTED in result.reasons
    assert result.effect is not None
    assert EffectRejectReason.INVALID_RETRIGGER_REASON in result.effect.reasons
    # The unified fixer was never consulted; only the canonical request event
    # exists (no effect, no checkpoint rows).
    assert delegation.calls == []
    assert result.effect.event_id is None
    rows = ledger.events_path.read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(row).get("payload") or {} for row in rows]
    assert [
        p.get("action_kind") for p in payloads if p.get("action_kind")
    ] == ["repair_request"]


# ---------------------------------------------------------------------------
# Kill-switch rollback
# ---------------------------------------------------------------------------


def test_kill_switch_rollback_records_truthful_non_authorizing_receipt(
    tmp_path: Path,
) -> None:
    root, admission, _ = _admit(tmp_path, name="rollback")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    # First drive the full report-only lifecycle so the ledger has durable
    # observation rows to preserve.
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            ledger=ledger,
        )
    )
    assert result.outcome is CanaryOutcome.COMPLETED
    rows_before = sum(1 for _ in open(ledger.events_path, encoding="utf-8") if _.strip())

    receipt = rollback_maintenance_canary(
        root=root,
        run_id="run-rollback-1",
        ledger=ledger,
        reason="kill-switch: operator halted the canary",
        mutation_gate_fn=_GateSpy(False),
        base_root=root.parent,
    )

    assert receipt.effects_disabled is True
    assert receipt.authorizing is False
    assert receipt.custody_open is True
    assert receipt.ledger_event_count == rows_before
    assert receipt.receipt_ref is not None
    assert receipt.receipt_ref.locator == "rollback://run-rollback-1"
    assert receipt.receipt_digest is not None
    # The ledger was preserved byte-for-byte (observation/replay intact).
    rows_after = sum(1 for _ in open(ledger.events_path, encoding="utf-8") if _.strip())
    assert rows_after == rows_before


def test_kill_switch_refuses_rollback_while_effects_authorized(tmp_path: Path) -> None:
    root, _, _ = _admit(tmp_path, name="rollback-refused")
    with pytest.raises(MaintenanceCanaryError) as excinfo:
        rollback_maintenance_canary(
            root=root,
            run_id="run-rollback-refused",
            reason="kill-switch",
            mutation_gate_fn=_GateSpy(True),
            base_root=root.parent,
        )
    assert excinfo.value.reason == "rollback_refused"


def test_effect_failure_with_kill_switch_records_rolled_back_outcome(
    tmp_path: Path,
) -> None:
    root, admission, _ = _admit(tmp_path, name="rollback-on-failure")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    delegation = _DelegationSpy(outcome="delegation_failed")
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            delegation=delegation,
            ledger=ledger,
            rollback_on_failure=True,
        )
    )

    assert result.outcome is CanaryOutcome.ROLLED_BACK
    assert CanaryRejectReason.EFFECT_REJECTED in result.reasons
    assert result.rollback is not None
    assert result.rollback.authorizing is False
    assert result.rollback.custody_open is True
    assert result.rollback.receipt_ref is not None
    assert result.custody_open is True


# ---------------------------------------------------------------------------
# Stale verifier fencing
# ---------------------------------------------------------------------------


def test_stale_verifier_fencing_rejects_checkpoint_without_append(
    tmp_path: Path,
) -> None:
    root, admission, _ = _admit(tmp_path, name="stale-verifier")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    # The verifier's FRESH capture is fenced because the expected authority
    # coordinates (run identity) do not match the capture: stale fencing.
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            ledger=ledger,
            expected_authority=ExpectedAuthority(run_id="run-stale"),
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.STALE_VERIFIER in result.reasons
    # The FIRST due window (immediate) was fenced: no checkpoint event was
    # appended and the window was never completed.
    assert len(result.checkpoints) == 1
    assert result.checkpoints[0].window is CheckpointWindowKind.IMMEDIATE
    assert result.checkpoints[0].appended is False
    assert (
        result.checkpoints[0].verification.outcome is VerificationOutcome.UNKNOWN
    )
    assert result.terminal is None
    assert result.custody_open is True
    assert _event_rows(ledger, "checkpoint_verification:occ-1:immediate") == []


def test_terminal_boundary_blocked_keeps_custody_open(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="boundary-blocked")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)

    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            ledger=ledger,
            authorizing=True,
            final_boundary_fn=_BoundarySpy(authorized=False),
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.TERMINAL_BOUNDARY_BLOCKED in result.reasons
    # The four checkpoint windows ARE durable, but the final action-validator
    # reread blocked terminal submission: custody stays open and the
    # rejection is recorded as a submitted=False terminal receipt.
    assert len(result.checkpoints) == 4
    assert result.terminal is not None
    assert result.terminal.submitted is False
    assert result.terminal.pending_signoff is False
    assert result.custody_open is True
    assert result.terminal_submitted is False
    assert _event_rows(ledger, "terminal_verification:occ-1") == []


# ---------------------------------------------------------------------------
# Source/runtime digest mismatch
# ---------------------------------------------------------------------------


def test_source_runtime_digest_mismatch_fences_verifier(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="verifier-mismatch")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    # The verifier claims a DIFFERENT source digest than the admitted
    # installed runtime.
    verifier = _verifier(
        admission.runtime_digest,
        "9" * 64,
        principal="verifier-other-source",
    )
    assert canary_verifier_binding_matches(admission, verifier) is False
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            ledger=ledger,
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.VERIFIER_DIGEST_MISMATCH in result.reasons
    # Nothing ran: no request, no effect, no checkpoint, no ledger rows.
    assert result.request is None
    assert result.effect is None
    assert result.checkpoints == ()
    assert not ledger.events_path.exists()


def test_admission_rejects_source_runtime_digest_mismatch(tmp_path: Path) -> None:
    root, base = _canary_root(tmp_path, "admission-mismatch")
    runtime_path = root / "runtime.json"
    _runtime_receipt(runtime_path)

    with pytest.raises(MaintenanceCanaryError) as excinfo:
        admit_maintenance_canary(
            root=root,
            job_id="job-1",
            deployment_target="production",
            deployment_id="deploy-1",
            expected_revision=REVISION,
            runtime_receipt_path=runtime_path,
            expected_source_digest="9" * 64,
            base_root=base,
        )
    assert excinfo.value.reason == "source_runtime_digest_mismatch"

    with pytest.raises(MaintenanceCanaryError) as excinfo:
        admit_maintenance_canary(
            root=root,
            job_id="job-1",
            deployment_target="production",
            deployment_id="deploy-1",
            expected_revision=REVISION,
            runtime_receipt_path=runtime_path,
            expected_runtime_digest="8" * 64,
            base_root=base,
        )
    assert excinfo.value.reason == "runtime_digest_mismatch"

    # Nothing was written by the rejected admissions.
    assert not (root / "maintenance-canary" / "admission.json").exists()


# ---------------------------------------------------------------------------
# Admission: M11 installed-runtime identity binding
# ---------------------------------------------------------------------------


def test_admission_binds_m11_installed_runtime_identity(tmp_path: Path) -> None:
    root, admission, runtime = _admit(tmp_path)
    assert admission.job_id == "job-1"
    assert admission.deployment == {
        "target": "production",
        "id": "deploy-1",
        "expected_revision": REVISION,
    }
    assert admission.runtime_digest == runtime["content_sha256"]
    assert admission.runtime_receipt["runtime_identity"] == (
        f"sha256:{runtime['content_sha256']}"
    )
    # The source identity digest is derived from the M11 source lineage.
    assert admission.source_digest == hashlib.sha256(
        json.dumps(
            {"revision": REVISION, "expected_revision": REVISION},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert admission.required_checkpoints == (
        "immediate",
        "five_minute",
        "one_hour",
        "next_three_hour",
    )
    assert (root / "maintenance-canary" / "admission.json").is_file()
    # The artifact is append-only and content-addressed: it round-trips.
    loaded = load_maintenance_canary_admission(root, base_root=root.parent)
    assert loaded.runtime_digest == admission.runtime_digest
    assert loaded.source_digest == admission.source_digest


def test_admission_rejects_invalid_runtime_binding_and_duplicate(tmp_path: Path) -> None:
    root, base = _canary_root(tmp_path, "admission-invalid")
    runtime_path = root / "runtime.json"
    _runtime_receipt(runtime_path, revision="b" * 40)

    with pytest.raises(MaintenanceCanaryError) as excinfo:
        admit_maintenance_canary(
            root=root,
            job_id="job-1",
            deployment_target="production",
            deployment_id="deploy-1",
            expected_revision=REVISION,
            runtime_receipt_path=runtime_path,
            base_root=base,
        )
    assert excinfo.value.reason == "invalid_runtime_binding"

    # A second admission for the same private root is refused (append-only).
    runtime_path = root / "runtime.json"
    _runtime_receipt(runtime_path)
    admit_maintenance_canary(
        root=root,
        job_id="job-1",
        deployment_target="production",
        deployment_id="deploy-1",
        expected_revision=REVISION,
        runtime_receipt_path=runtime_path,
        base_root=base,
    )
    with pytest.raises(MaintenanceCanaryError) as excinfo:
        admit_maintenance_canary(
            root=root,
            job_id="job-1",
            deployment_target="production",
            deployment_id="deploy-1",
            expected_revision=REVISION,
            runtime_receipt_path=runtime_path,
            base_root=base,
        )
    assert excinfo.value.reason == "admission_conflict"


# ---------------------------------------------------------------------------
# M11 reuse (no recreated infrastructure)
# ---------------------------------------------------------------------------


def test_module_reuses_m11_infrastructure_without_recreating_it() -> None:
    # Installed-runtime identity validation is the M11 implementation.
    assert (
        canary_module._strict_runtime_binding
        is m11_workflow_canary._strict_runtime_binding
    )
    # The canary base and evidence helpers come from the M11 live canary.
    assert canary_module.CANARY_BASE is m11_live_canary.CANARY_BASE
    assert canary_module._digest is m11_live_canary._digest
    # The request/effect bridges are the SAME cloud-adapter seams as
    # production; the canary never reimplements enqueue/delegation.
    assert (
        canary_module.submit_occurrence_bound_repair_request
        is maintenance_recovery.submit_occurrence_bound_repair_request
    )
    assert (
        canary_module.route_allowlisted_effect
        is maintenance_recovery.route_allowlisted_effect
    )
    assert not hasattr(canary_module, "enqueue_occurrence_bound_repair_request")
    assert not hasattr(canary_module, "RepairEffectLedger")


def test_canary_result_round_trips_through_strict_codec(tmp_path: Path) -> None:
    root, admission, _ = _admit(tmp_path, name="round-trip")
    registry = _accepted_registry()
    verifier = _verifier(admission.runtime_digest, admission.source_digest)
    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
        )
    )
    dumped = result.model_dump(mode="json")
    reloaded = CanaryRunResult.model_validate(dumped)
    assert reloaded.outcome is result.outcome
    assert reloaded.run_id == result.run_id
    assert reloaded.custody_open == result.custody_open
    assert [c.window for c in reloaded.checkpoints] == [
        c.window for c in result.checkpoints
    ]


# ---------------------------------------------------------------------------
# Static runbook contract assertions (T15 / Plan Step 14)
# ---------------------------------------------------------------------------
# The runbook is the Maintenance-owned canary/rollback operating document.
# These assertions pin its required sections, every stop-condition family,
# its truthful no-approval posture, and its alignment with the implemented
# canary API and canonical checkpoint schedule.  They are static: they read
# the runbook text and never imply that promotion is currently authorized.


RUNBOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "arnold_pipelines/megaplan/maintenance/RUNBOOK.md"
)

REQUIRED_RUNBOOK_SECTIONS = (
    "## Purpose",
    "## Prerequisites",
    "## Exact handoff digest reporting",
    "## Verifier and inherited lease policy",
    "## Allowlist",
    "## Target and owners",
    "## Gates",
    "## Rehearsal (report-only, default)",
    "## Promotion",
    "## Checkpoint",
    "## Rollback",
    "## Kill-switch",
    "## Evidence procedures",
    "## Stop conditions",
    "## Static contract assertions",
)


def _runbook_text() -> str:
    assert RUNBOOK_PATH.is_file(), f"runbook missing: {RUNBOOK_PATH}"
    return RUNBOOK_PATH.read_text(encoding="utf-8")


def test_runbook_documents_required_sections() -> None:
    text = _runbook_text()
    missing = [section for section in REQUIRED_RUNBOOK_SECTIONS if section not in text]
    assert not missing, f"runbook missing required sections: {missing}"


def test_runbook_states_every_stop_condition_family() -> None:
    text = _runbook_text()
    # Stale authority, torn evidence, and digest mismatches.
    for token in (
        "STALE_AUTHORITY",
        "TORN_ENVELOPE",
        "INCOHERENT_EVIDENCE",
        "UNKNOWN_EVIDENCE",
        "DIGEST_MISMATCH",
        "runtime_digest_mismatch",
        "source_runtime_digest_mismatch",
        "VERIFIER_DIGEST_MISMATCH",
        "wrong installation hash",
    ):
        assert token in text, f"runbook missing stale/torn/digest stop token {token!r}"
    # Lost independence and unresolved ownership.
    for token in (
        "SELF_VERIFICATION",
        "REPAIR_PRODUCER_AUTHORED",
        "MISSING_PROVENANCE",
        "LIVENESS_ONLY",
        "MISSING_NEGATIVE_CONTROL",
        "FAILED_CONTROL",
        "PENDING_HANDOFF",
        "unresolved escalation",
        "rollback owner",
    ):
        assert token in text, f"runbook missing independence/ownership stop token {token!r}"
    # Recurrence without fresh authority and direct plan/chain writes.
    for token in (
        "Recurrence without fresh authority",
        "new canonical occurrence",
        "write_plan_state",
        "save_chain_state",
        "TransitionWriter",
        "M7BypassFinding",
        "delegate_to_simple_fixer",
        "divergent reuse",
    ):
        assert token in text, f"runbook missing recurrence/direct-write stop token {token!r}"


def test_runbook_does_not_imply_current_approval() -> None:
    text = _runbook_text()
    # Truthful current posture: pending handoffs, default-off action, and no
    # promotion authority today.
    for token in (
        "does **not** imply current approval",
        "pending_human_approval",
        "default-off",
        "automatic effects remain **disabled**",
        "not authorized today",
        "custody_open=True",
        "report-only",
    ):
        assert token in text, f"runbook missing truthful posture token {token!r}"
    # The runbook must never claim that promotion or effects are current.
    for forbidden in (
        "promotion is authorized",
        "effects are enabled today",
        "all handoff rows are approved",
    ):
        assert forbidden not in text, (
            f"runbook must not imply current approval; found {forbidden!r}"
        )


def test_runbook_matches_implemented_canary_api_and_checkpoint_schedule() -> None:
    text = _runbook_text()
    for token in (
        "admit_maintenance_canary",
        "run_maintenance_canary",
        "rollback_maintenance_canary",
        "canary_verifier_binding_matches",
        "CanaryOutcome",
        "CanaryRejectReason",
        "arnold.megaplan.maintenance_canary.v1",
        "authorizing=False",
        "rollback_refused",
        "immediate",
        "five_minute",
        "one_hour",
        "next_three_hour",
        "six_hour",
        "MUTATION_PATH_L1",
        "ARNOLD_AUTONOMY",
        "validate_action_boundary",
    ):
        assert token in text, f"runbook missing implemented-API token {token!r}"



def test_authorizing_run_requires_final_boundary_callback(tmp_path: Path) -> None:
    """An authorizing canary WITHOUT the final action-validator reread must
    fail closed TERMINAL_BOUNDARY_BLOCKED with custody open and no terminal
    row."""
    root, admission, _ = _admit(tmp_path, name="boundary-required")
    registry = _accepted_registry()
    ledger = MaintenanceLedger(tmp_path)
    verifier = _verifier(admission.runtime_digest, admission.source_digest)

    result = run_maintenance_canary(
        **_run_kwargs(
            root=root,
            admission=admission,
            verifier=verifier,
            tmp_path=tmp_path,
            registry=registry,
            ledger=ledger,
            authorizing=True,
            final_boundary_fn=None,
        )
    )

    assert result.outcome is CanaryOutcome.REJECTED
    assert CanaryRejectReason.TERMINAL_BOUNDARY_BLOCKED in result.reasons
    assert len(result.checkpoints) == 4
    assert result.terminal is None
    assert result.custody_open is True
    assert result.terminal_submitted is False
    assert _event_rows(ledger, "terminal_verification:occ-1") == []
