from __future__ import annotations

from dataclasses import dataclass

from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryContext,
    GateResult,
    ValidationOutcome,
    validate_action_boundary,
)
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.outbox import OutboxRecord, OutboxRecordStatus, OutboxRecordType
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence


TARGET = CustodyTargetKey("task", "T6", "complete", "task", "T6", "contract-T6")
CAPABILITY = "megaplan.task.result"
GRANT = CapabilityGrant(
    grant_id="grant-T6",
    run_id="run-T6",
    run_revision="rev-T6",
    coordinator_attempt_id="coord-T6",
    fence_token=7,
    subject_ids=(TARGET.subject_id,),
    capabilities=(CAPABILITY,),
    evidence_ids=("evidence-1",),
)
FENCE = CoordinatorFence("run-T6", "rev-T6", "coord-T6", 7)


@dataclass
class FakeLeaseStore:
    leases: tuple[CustodyLease, ...]

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        for lease in self.leases:
            if lease.lease_id == lease_id:
                return lease
        return None

    def find_by_target_key(
        self,
        subject_type: str,
        subject_id: str,
        action: str,
        target_kind: str,
        target_id: str,
        contract_id: str,
    ) -> tuple[CustodyLease, ...]:
        return tuple(
            lease
            for lease in self.leases
            if lease.target_key is not None
            and lease.target_key.to_dict()
            == TARGET.to_dict()
        )


@dataclass
class FakeOutbox:
    records: tuple[OutboxRecord, ...]

    def list_records(self) -> tuple[OutboxRecord, ...]:
        return self.records


def _lease(*, epoch: int = 5, subject_id: str = TARGET.subject_id, grant_id: str = GRANT.grant_id) -> CustodyLease:
    target = (
        TARGET
        if subject_id == TARGET.subject_id
        else CustodyTargetKey(TARGET.subject_type, subject_id, TARGET.action, TARGET.target_kind, TARGET.target_id, TARGET.contract_id)
    )
    return CustodyLease(
        lease_id="lease-T6",
        target_key=target,
        owner=("validator-host", "12345", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(FENCE.token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference="wbc-T6",
    )


def _record(*, version: str = "wbc-evidence.v1", grant_id: str = GRANT.grant_id) -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T6",
        lease_id="lease-T6",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T6",
        wbc_attempt_reference="wbc-T6",
        run_authority_grant_id=grant_id,
        coordinator_fence_token=FENCE.token,
        custody_epoch=5,
        payload={
            "schema_version": version,
            "target_digest": TARGET.target_digest,
        },
    )


def _context(**overrides: object) -> ActionBoundaryContext:
    base = {
        "action_type": "completion",
        "target": TARGET,
        "run_authority_grant_id": GRANT.grant_id,
        "coordinator_fence_token": FENCE.token,
        "wbc_attempt_reference": "wbc-T6",
        "owner_host": "validator-host",
        "owner_pid": "12345",
        "owner_boot_id": "boot-1",
        "expected_custody_epoch": 5,
        "expected_lease_id": "lease-T6",
        "run_authority_grant": GRANT,
        "coordinator_fence": FENCE,
        "required_capability": CAPABILITY,
        "required_wbc_evidence_version": "wbc-evidence.v1",
    }
    base.update(overrides)
    return ActionBoundaryContext(**base)


def test_validator_authorizes_current_exact_identities() -> None:
    result = validate_action_boundary(
        _context(),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(),)),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.AUTHORIZED
    assert all(check.outcome == ValidationOutcome.SATISFIED for check in result.checks)
    assert result.diagnostics["checks_summary"] == {
        "run_authority_grant": "satisfied",
        "run_authority_fence": "satisfied",
        "custody_lease": "satisfied",
        "wbc_attempt": "satisfied",
    }


def test_validator_blocks_missing_current_grant_with_typed_denial() -> None:
    result = validate_action_boundary(
        _context(run_authority_grant=None),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(),)),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_MISSING_GRANT
    assert result.diagnostics["denials"][0]["identity"] == "grant"
    assert result.diagnostics["denials"][0]["outcome"] == "missing"


def test_validator_blocks_subject_outside_current_grant_scope() -> None:
    off_scope_grant = CapabilityGrant(
        grant_id=GRANT.grant_id,
        run_id=GRANT.run_id,
        run_revision=GRANT.run_revision,
        coordinator_attempt_id=GRANT.coordinator_attempt_id,
        fence_token=GRANT.fence_token,
        subject_ids=("other-task",),
        capabilities=GRANT.capabilities,
        evidence_ids=GRANT.evidence_ids,
    )

    result = validate_action_boundary(
        _context(run_authority_grant=off_scope_grant),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(),)),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_SUBJECT_SCOPE_MISMATCH
    assert result.diagnostics["denials"][0]["identity"] == "subject_id"
    assert "outside current grant scope" in result.diagnostics["denials"][0]["detail"]


def test_validator_blocks_stale_custody_epoch_with_typed_denial() -> None:
    result = validate_action_boundary(
        _context(expected_custody_epoch=4),
        lease_store=FakeLeaseStore((_lease(epoch=5),)),
        outbox=FakeOutbox((_record(),)),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_STALE_EPOCH
    denial = next(item for item in result.diagnostics["denials"] if item["source"] == "custody_lease")
    assert denial["identity"] == "custody_epoch"
    assert denial["outcome"] == "stale"


def test_validator_blocks_wbc_evidence_version_mismatch() -> None:
    result = validate_action_boundary(
        _context(required_wbc_evidence_version="wbc-evidence.v2"),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(version="wbc-evidence.v1"),)),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_WBC_VERSION_MISMATCH
    denial = next(item for item in result.diagnostics["denials"] if item["source"] == "wbc_attempt")
    assert denial["identity"] == "wbc_evidence_version"
    assert denial["outcome"] == "stale"
