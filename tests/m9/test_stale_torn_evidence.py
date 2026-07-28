"""M9 stale/torn evidence traps.

These tests pin the negative contract across Run Authority, Custody, WBC,
watchdog liveness, stale marker reads, and rebuild lag: degraded evidence must
stay explicit as stale/unknown/conflict dimensions and must not produce an
authority-increasing action verdict.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from arnold_pipelines.megaplan.authority.views import derive_runner_view
from arnold_pipelines.megaplan.cloud.current_target import _collect_target_evidence_gaps
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryContext,
    GateResult,
    ValidationOutcome,
    validate_action_boundary,
)
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.outbox import (
    OutboxRecord,
    OutboxRecordStatus,
    OutboxRecordType,
)
from arnold_pipelines.megaplan.observability.projection_rebuild import (
    ProjectionRegistry,
    compare_all_projections,
)
from arnold_pipelines.megaplan.watchdog.correlate import (
    LIVENESS_DEAD,
    LIVENESS_HUNG,
    LIVENESS_RECYCLED,
    RUNNER_LOST,
    RUNNER_UNKNOWN,
    classify_worker_liveness,
)
from arnold_pipelines.megaplan.watchdog.processes import ProcessRecord
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence


_AUTHORITY_INCREASING_RESULTS = {
    GateResult.AUTHORIZED,
    "success",
    "complete",
    "completed",
    "dispatch",
    "delivery",
    "publication",
    "repair",
    "verified",
}


class _LeaseStore:
    def __init__(self, leases: Sequence[CustodyLease]) -> None:
        self._leases = tuple(leases)

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        for lease in self._leases:
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
        expected = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "action": action,
            "target_kind": target_kind,
            "target_id": target_id,
            "contract_id": contract_id,
        }
        return tuple(
            lease
            for lease in self._leases
            if lease.target_key is not None and lease.target_key.to_dict() == expected
        )


class _Outbox:
    def __init__(self, records: Sequence[OutboxRecord]) -> None:
        self._records = tuple(records)

    def list_records(self) -> tuple[OutboxRecord, ...]:
        return self._records


@pytest.fixture
def target() -> CustodyTargetKey:
    return CustodyTargetKey(
        subject_type="task",
        subject_id="T32",
        action="completion",
        target_kind="plan",
        target_id="m9",
        contract_id="m9.action-boundary",
    )


def _grant(*, grant_id: str = "grant-current", fence_token: int = 7) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id=grant_id,
        run_id="run-1",
        run_revision="rev-1",
        coordinator_attempt_id="coord-1",
        fence_token=fence_token,
        subject_ids=("T32",),
        capabilities=("completion",),
        evidence_ids=("ra-evidence-1",),
    )


def _fence(*, token: int = 7) -> CoordinatorFence:
    return CoordinatorFence(
        run_id="run-1",
        run_revision="rev-1",
        coordinator_attempt_id="coord-1",
        token=token,
    )


def _lease(
    target: CustodyTargetKey,
    *,
    lease_id: str = "lease-current",
    expires_at: str = "2999-01-01T00:00:00Z",
    epoch: int = 3,
    status: str = "acquire",
    grant_id: str = "grant-current",
    fence_token: str = "7",
    wbc_attempt: str = "attempt-current",
) -> CustodyLease:
    return CustodyLease(
        lease_id=lease_id,
        target_key=target,
        owner=("host-1", "123", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-21T00:00:00Z",
        expires_at=expires_at,
        fence_token=fence_token,
        status=status,
        run_authority_grant_id=grant_id,
        wbc_attempt_reference=wbc_attempt,
    )


def _outbox_record(
    *,
    outbox_id: str,
    lease_id: str = "lease-current",
    wbc_attempt: str = "attempt-current",
    grant_id: str = "grant-current",
    fence_token: int = 7,
    status: OutboxRecordStatus = OutboxRecordStatus.PENDING,
    version: str = "m9.current",
    target_digest: str = "digest",
) -> OutboxRecord:
    return OutboxRecord(
        outbox_id=outbox_id,
        lease_id=lease_id,
        record_type=OutboxRecordType.CROSS_OWNER_ATTEMPT,
        status=status,
        occurred_at="2026-07-21T00:00:00Z",
        idempotency_key=outbox_id,
        wbc_attempt_reference=wbc_attempt,
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        custody_epoch=3,
        payload={"evidence_version": version, "target_digest": target_digest},
    )


def _base_context(target: CustodyTargetKey) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type="completion",
        target=target,
        run_authority_grant_id="grant-current",
        coordinator_fence_token=7,
        wbc_attempt_reference="attempt-current",
        owner_host="host-1",
        owner_pid="123",
        owner_boot_id="boot-1",
        expected_custody_epoch=3,
        expected_lease_id="lease-current",
        run_authority_grant=_grant(),
        coordinator_fence=_fence(),
        required_capability="completion",
        required_wbc_evidence_version="m9.current",
    )


def _check(result: Any, source: str) -> Any:
    return next(check for check in result.checks if check.source == source)


def assert_no_authority_increase(value: Any) -> None:
    if isinstance(value, GateResult):
        assert value not in _AUTHORITY_INCREASING_RESULTS
    elif isinstance(value, str):
        assert value not in _AUTHORITY_INCREASING_RESULTS
    else:
        raise AssertionError(f"unsupported authority trap value: {value!r}")


def test_stale_run_authority_grant_blocks_with_explicit_stale_dimension(
    target: CustodyTargetKey,
) -> None:
    context = replace(
        _base_context(target),
        run_authority_grant=_grant(grant_id="grant-stale"),
    )

    result = validate_action_boundary(
        context,
        lease_store=_LeaseStore((_lease(target),)),
        outbox=_Outbox(
            (
                _outbox_record(
                    outbox_id="wbc-current",
                    target_digest=target.target_digest,
                ),
            )
        ),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_STALE_GRANT
    assert_no_authority_increase(result.gate_result)
    grant_check = _check(result, "run_authority_grant")
    assert grant_check.outcome == ValidationOutcome.STALE
    assert grant_check.identity == "grant_id"
    assert result.diagnostics["checks_summary"]["run_authority_grant"] == "stale"


def test_expired_custody_lease_blocks_with_explicit_expired_dimension(
    target: CustodyTargetKey,
) -> None:
    result = validate_action_boundary(
        _base_context(target),
        lease_store=_LeaseStore((_lease(target, expires_at="2020-01-01T00:00:00Z"),)),
        outbox=_Outbox(
            (
                _outbox_record(
                    outbox_id="wbc-current",
                    target_digest=target.target_digest,
                ),
            )
        ),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_EXPIRED_LEASE
    assert_no_authority_increase(result.gate_result)
    lease_check = _check(result, "custody_lease")
    assert lease_check.outcome == ValidationOutcome.EXPIRED
    assert lease_check.observed_value["status"] == "acquire"
    assert result.diagnostics["checks_summary"]["custody_lease"] == "expired"


def test_torn_wbc_records_block_with_explicit_conflict_dimension(
    target: CustodyTargetKey,
) -> None:
    records = (
        _outbox_record(
            outbox_id="wbc-current-a",
            status=OutboxRecordStatus.PENDING,
            target_digest=target.target_digest,
        ),
        _outbox_record(
            outbox_id="wbc-current-b",
            status=OutboxRecordStatus.DELIVERED,
            target_digest=target.target_digest,
        ),
    )

    result = validate_action_boundary(
        _base_context(target),
        lease_store=_LeaseStore((_lease(target),)),
        outbox=_Outbox(records),
        enforcement_enabled=True,
    )

    assert result.gate_result == GateResult.BLOCKED_WBC_CONFLICT
    assert_no_authority_increase(result.gate_result)
    wbc_check = _check(result, "wbc_attempt")
    assert wbc_check.outcome == ValidationOutcome.CONFLICT
    assert wbc_check.identity == "status"
    assert sorted(wbc_check.observed_value["statuses"]) == ["delivered", "pending"]


def test_recycled_hung_and_dead_workers_stay_unknown_or_lost() -> None:
    recycled = classify_worker_liveness(
        ProcessRecord(
            pid=100,
            cmdline="arnold --session S1 m9",
            category="arnold",
            is_live=True,
            session_token="S1",
            birth_time_seconds=300.0,
        ),
        attempt_session_token="S1",
        attempt_start_epoch=100.0,
        heartbeat_fresh=True,
        wbc_attempt_identity_supplied=True,
    )
    hung = classify_worker_liveness(
        ProcessRecord(
            pid=101,
            cmdline="arnold --session S1 m9",
            category="arnold",
            is_live=True,
            session_token="S1",
            birth_time_seconds=50.0,
        ),
        attempt_session_token="S1",
        attempt_start_epoch=100.0,
        heartbeat_fresh=False,
        wbc_attempt_identity_supplied=True,
    )
    dead = classify_worker_liveness(
        ProcessRecord(
            pid=102,
            cmdline="arnold --session S1 m9",
            category="arnold",
            is_live=False,
            session_token="S1",
            birth_time_seconds=50.0,
        ),
        attempt_session_token="S1",
        attempt_start_epoch=100.0,
        heartbeat_fresh=True,
        wbc_attempt_identity_supplied=True,
    )

    assert recycled.classification == LIVENESS_RECYCLED
    assert recycled.evidence_gaps["recycled_pid"]["evidence_status"] == "conflict"
    assert recycled.runner_verdict == RUNNER_UNKNOWN
    assert hung.classification == LIVENESS_HUNG
    assert hung.evidence_gaps["heartbeat_freshness"]["evidence_status"] == "stale"
    assert hung.runner_verdict == RUNNER_LOST
    assert dead.classification == LIVENESS_DEAD
    assert dead.evidence_gaps["process_liveness"]["evidence_status"] == "dead"
    assert dead.runner_verdict == RUNNER_LOST
    for verdict in (recycled.runner_verdict, hung.runner_verdict, dead.runner_verdict):
        assert_no_authority_increase(verdict)


def test_stale_markers_and_runner_heartbeats_are_diagnostic_only() -> None:
    marker_gaps = _collect_target_evidence_gaps(
        {"workspace": "/workspace/demo", "plan_name": "old-plan"},
        stale_evidence=[
            {"kind": "stale_marker_plan_ref", "path": "/markers/session.json"},
            {"kind": "stale_needs_human_plan_ref", "path": "/markers/session.needs-human.json"},
            {"kind": "stale_active_step_dead_pid", "path": "/plans/demo/state.json"},
        ],
        marker_present=True,
        tmux_live=False,
    )
    runner = derive_runner_view(
        (
            {
                "id": "heartbeat-1",
                "type": "heartbeat",
                "source": "cloud/heartbeat.json",
                "state": "live",
                "identity": "worker-1",
                "expected_identity": "worker-1",
                "heartbeat_age_seconds": 900,
            },
        ),
        expected_identity="worker-1",
        stale_after_seconds=300,
    )

    assert marker_gaps["marker_plan_ref"]["evidence_status"] == "stale"
    assert marker_gaps["needs_human_plan_ref"]["evidence_status"] == "stale"
    assert marker_gaps["active_step"]["evidence_status"] == "stale"
    assert runner.status == "stale"
    assert {diagnostic.code for diagnostic in runner.diagnostics} == {"stale_heartbeat"}
    assert runner.to_dict()["read_only"] is True
    assert "authority" not in runner.to_dict()


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_projection_lag_reports_digest_mismatch_without_mutating_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "projection-source.jsonl"
    records = (
        {"seq": 1, "payload": {"status": "running"}},
        {"seq": 2, "payload": {"status": "done"}},
    )
    _write_jsonl(source, records)
    source_before = source.read_bytes()

    def builder(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        latest = items[-1]["payload"] if items else {"status": "unknown"}
        return {
            "projection_id": "lag-fixture",
            "authority": "non_authoritative_rebuild_projection",
            "view": dict(latest),
        }

    registry = ProjectionRegistry()
    registry.register("lag-fixture", builder, source_path=source)
    stale_cached_view = {
        "projection_id": "lag-fixture",
        "authority": "non_authoritative_rebuild_projection",
        "view": {"status": "running"},
    }

    report = compare_all_projections(
        registry,
        existing_views={"lag-fixture": stale_cached_view},
    )["lag-fixture"]

    assert report.parity is False
    assert report.rebuild_digest != report.existing_digest
    assert report.source_cursor is not None
    assert report.source_cursor.source_record_count == 2
    assert any("Digest mismatch" in diagnostic for diagnostic in report.diagnostics)
    assert source.read_bytes() == source_before
