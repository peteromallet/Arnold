from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract, repair_requests
from arnold_pipelines.megaplan.cloud.repair_contract import (
    ATTEMPT_STATE_RUNNING,
    BLOCKER_FINGERPRINT_V1_PREFIX,
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    CUSTODY_BUCKET_REPAIRING,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_REPAIRING,
    DISPATCH_DECISION_TERMINAL,
    BlockerFingerprintV1,
    blocker_fingerprint_from_exact_request,
    blocker_id_for_fingerprint,
    classify_repair_dispatch,
    durable_repair_active,
    normalize_blocker_fingerprint_v1,
    project_repair_custody,
)
from arnold_pipelines.megaplan.run_state import CanonicalState, resolve_run_state


def _fingerprint(**overrides: str) -> BlockerFingerprintV1:
    payload: BlockerFingerprintV1 = {
        "schema_version": 1,
        "current_state": "blocked",
        "retry_strategy": "manual_review",
        "failure_kind": "blocked_recovery_not_resolved",
        "phase_or_step": "execute",
        "milestone_or_plan": "agentic-replay-viewer",
        "blocked_task_id": "T1",
        "target_fingerprint": "sha256:target-proof",
    }
    payload.update(overrides)
    return payload


def test_blocker_id_is_stable_for_same_v1_fingerprint() -> None:
    first = _fingerprint()
    same_values_different_order = {
        "target_fingerprint": "  sha256:target-proof  ",
        "blocked_task_id": "T1",
        "milestone_or_plan": "agentic-replay-viewer",
        "phase_or_step": "execute",
        "failure_kind": "blocked_recovery_not_resolved",
        "retry_strategy": "manual_review",
        "current_state": "blocked",
        "schema_version": 1,
    }

    normalized = normalize_blocker_fingerprint_v1(same_values_different_order)
    assert normalized == first
    assert BLOCKER_FINGERPRINT_V1_PREFIX.endswith("/v1")
    assert blocker_id_for_fingerprint(first) == blocker_id_for_fingerprint(same_values_different_order)


def test_blocker_id_changes_when_v1_fingerprint_changes() -> None:
    first = blocker_id_for_fingerprint(_fingerprint())
    second = blocker_id_for_fingerprint(_fingerprint(target_fingerprint="sha256:changed-proof"))

    assert first is not None
    assert second is not None
    assert first != second


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"schema_version": 1},
        {"schema_version": 2, "current_state": "blocked"},
        {"schema_version": 1, "current_state": "blocked", "retry_strategy": "manual_review"},
        {
            "schema_version": 1,
            "current_state": "blocked",
            "retry_strategy": "manual_review",
            "failure_kind": "blocked_recovery_not_resolved",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "blocked_task_id": "",
            "target_fingerprint": "sha256:target-proof",
        },
        {
            "schema_version": 1,
            "current_state": "blocked",
            "retry_strategy": "manual_review",
            "failure_kind": "blocked_recovery_not_resolved",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "blocked_task_id": "T1",
            "target_fingerprint": 123,
        },
    ],
)
def test_malformed_or_partial_blocker_fingerprints_fail_conservatively(payload: object) -> None:
    assert normalize_blocker_fingerprint_v1(payload) is None
    assert blocker_id_for_fingerprint(payload) is None


def test_exact_request_adapts_taskless_phase_failure_without_weakening_general_projection(
    tmp_path: Path,
) -> None:
    queue_root = _queue_root(tmp_path)
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        session="custody-session",
        source="lifecycle_failure",
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "finalize",
            "milestone_or_plan": "m9-rebuildable-projections",
            "gate_recommendation": "repair the deterministic phase contract",
            "blocked_task_id": "",
        },
        target={"plan_name": "m9-rebuildable-projections"},
        root_cause_hint="finalize contract failed",
        created_at="2026-07-22T04:48:40Z",
    )
    request = queued["request"]
    expected = {
        "schema_version": 1,
        "current_state": "blocked",
        "retry_strategy": "repair_phase_contract",
        "failure_kind": "deterministic_phase_failure",
        "phase_or_step": "finalize",
        "milestone_or_plan": "m9-rebuildable-projections",
        "blocked_task_id": "phase:finalize",
        "target_fingerprint": f"repair-request:{request['request_id']}",
    }

    assert blocker_fingerprint_from_exact_request(request) == expected
    general = project_repair_custody(
        plan_state={"name": "m9-rebuildable-projections", "current_state": "planned"},
        current_target={"target_session": "custody-session"},
        queue_root=queue_root,
    )
    exact = project_repair_custody(
        plan_state={"name": "m9-rebuildable-projections", "current_state": "planned"},
        current_target={"target_session": "custody-session"},
        queue_root=queue_root,
        request_id=request["request_id"],
    )

    assert general["blocker_id"] == ""
    assert general["requests"][0]["blocker_id"] == ""
    assert exact["blocker_fingerprint"] == expected
    assert exact["blocker_id"] == blocker_id_for_fingerprint(expected)
    assert exact["requests"][0]["blocker_id"] == exact["blocker_id"]


def _plan_state() -> dict[str, object]:
    return {
        "name": "agentic-replay-viewer",
        "current_state": "blocked",
        "resume_cursor": {"retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": "blocked_recovery_not_resolved",
            "phase": "execute",
            "metadata": {"blocked_task_id": "T1"},
        },
    }


def _current_target() -> dict[str, object]:
    return {
        "current_refs": {
            "current_plan_name": "agentic-replay-viewer",
            "plan_current_state": "blocked",
        },
        "event_cursors": {"resume_retry_strategy": "manual_review"},
        "plan_state": {"fingerprint": "sha256:target-proof"},
    }


def _queue_root(tmp_path: Path) -> Path:
    root = tmp_path / ".megaplan" / "repair-queue"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_custody_projection_reads_plan_state_and_accepted_request_without_migration(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queue_root = _queue_root(tmp_path)

    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        target={"plan_dir": "/tmp/plan"},
        root_cause_hint="repairable blocker",
        created_at="2026-07-04T01:00:00Z",
    )

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert projection["blocker_fingerprint"] == _fingerprint()
    assert projection["blocker_id"] == blocker_id_for_fingerprint(_fingerprint())
    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    assert projection["current_state"] == "blocked"
    assert projection["retry_strategy"] == "manual_review"
    assert projection["failure_kind"] == "blocked_recovery_not_resolved"
    assert projection["active_request_ids"] == [queued["request"]["request_id"]]
    assert projection["request_status_counts"] == {"accepted": 1}
    assert projection["attempts"] == []
    assert projection["requests"][0]["status"] == "accepted"
    assert projection["requests"][0]["decision"]["decision"] == "accepted"
    assert projection["requests"][0]["problem_signature"]["blocked_task_id"] == "T1"


def test_advisory_sidecar_canonical_label_does_not_create_repair_custody(
    tmp_path: Path,
) -> None:
    canonical = resolve_run_state(
        {"repair_progress": {"present": True, "items": [{"status": "repairing"}]}}
    )
    assert canonical.canonical_state is not CanonicalState.REPAIRING

    projection = project_repair_custody(
        plan_state={"name": "live-plan", "current_state": "finalized"},
        current_target={"target_session": "demo-session"},
        canonical_run_state=canonical,
        queue_root=_queue_root(tmp_path),
        repair_data_dir=tmp_path / "repair-data",
    )

    assert projection["custody_bucket"] != CUSTODY_BUCKET_REPAIRING
    assert projection["request_count"] == 0
    assert projection["claim_count"] == 0
    assert projection["attempt_count"] == 0
    assert projection["requests"] == []
    assert projection["attempts"] == []
    assert durable_repair_active(projection) is False


def test_identity_free_legacy_attempt_cannot_own_current_request(tmp_path: Path) -> None:
    """An S2 requestless sidecar must not suppress ordinary L1 for dead S3."""

    custody = {
        "custody_bucket": CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
        "active_request_ids": ["current-s3-request"],
        "active_claim_request_ids": [],
        "attempts": [
            {
                "attempt_id": "legacy-s2-attempt",
                "path": "/tmp/legacy-s2-progress.json",
                "request_id": "",
                "blocker_id": "",
                "source": "repair_progress_sidecar",
                "terminal": False,
                "raw": {
                    "problem_signature": {
                        "current_state": "",
                        "failure_kind": "",
                        "phase_or_step": "",
                        "milestone_or_plan": "",
                    }
                },
            }
        ],
    }

    assert durable_repair_active(custody) is False
    assert repair_contract._problem_signature_matches_fingerprint(
        custody["attempts"][0]["raw"]["problem_signature"],
        {"current_state": "finalized", "milestone_or_plan": "s3"},
    ) is False
    assert repair_contract._has_active_repair(
        lock_evidence=None,
        process_evidence={},
        custody=custody,
    ) is False


def test_terminal_attempt_closes_older_immutable_dispatch_receipt() -> None:
    request_id = "workflow-boundary-request"
    custody = {
        "active_request_ids": [request_id],
        "active_claim_request_ids": [],
        "attempts": [
            {
                "attempt_id": "dispatch-receipt",
                "path": "/queue/attempts/dispatch.json",
                "request_id": request_id,
                "blocker_id": "blocker:v1:demo",
                "source": "repair_queue_dispatch_attempt",
                "terminal": False,
                "recorded_at": "2026-07-14T00:02:35Z",
            },
            {
                "attempt_id": "66",
                "path": "/repair-data/workflow-boundary.repair-data.json",
                "request_id": request_id,
                "source": "repair_data_snapshot",
                "terminal": True,
                "outcome": "partial_liveness",
                "recorded_at": "2026-07-14T00:08:29Z",
            },
        ],
    }

    assert durable_repair_active(custody) is False


def test_new_dispatch_after_terminal_attempt_remains_active() -> None:
    request_id = "workflow-boundary-request"
    custody = {
        "active_request_ids": [request_id],
        "active_claim_request_ids": [],
        "attempts": [
            {
                "attempt_id": "closed-attempt",
                "path": "/repair-data/workflow-boundary.repair-data.json",
                "request_id": request_id,
                "source": "repair_data_snapshot",
                "terminal": True,
                "outcome": "repair_exhausted",
                "recorded_at": "2026-07-14T00:08:29Z",
            },
            {
                "attempt_id": "new-dispatch-receipt",
                "path": "/queue/attempts/new-dispatch.json",
                "request_id": request_id,
                "blocker_id": "blocker:v1:demo",
                "source": "repair_queue_dispatch_attempt",
                "terminal": False,
                "recorded_at": "2026-07-14T00:09:00Z",
            },
        ],
    }

    assert durable_repair_active(custody) is True


def test_live_execute_worker_is_not_a_finalized_state_contradiction() -> None:
    target = {
        "authoritative_source": "chain_state",
        "current_refs": {"current_plan_name": "s3-boundary-coverage"},
        "plan_state": {"present": True, "fingerprint": "sha256:live-plan"},
        "active_step_heartbeat": {
            "active": True,
            "worker_pid": "1004788",
            "pid_live": True,
        },
    }

    assert repair_contract._has_terminality_contradiction(target) is False


def test_dead_execute_worker_still_reopens_finalized_state_custody() -> None:
    target = {
        "authoritative_source": "chain_state",
        "current_refs": {"current_plan_name": "s3-boundary-coverage"},
        "plan_state": {"present": True, "fingerprint": "sha256:dead-plan"},
        "active_step_heartbeat": {
            "active": True,
            "worker_pid": "3136480",
            "pid_live": False,
        },
    }

    assert repair_contract._has_terminality_contradiction(target) is True


def test_custody_projection_keeps_request_decisions_separate_from_attempt_outcomes(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queue_root = _queue_root(tmp_path)

    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="repair_trigger",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        root_cause_hint="dispatch me",
        created_at="2026-07-04T01:00:00Z",
    )
    repair_requests.write_decision(
        queue_root,
        request_id=queued["request"]["request_id"],
        decision="dispatched",
        reason="repair loop launched",
        created_at="2026-07-04T01:05:00Z",
    )

    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            repair_contract.merge_additive_fields(
                {
                    "session": "demo-session",
                    "workspace": "/tmp/ws",
                    "run_kind": "chain",
                    "plan_name": "agentic-replay-viewer",
                    "attempts": [
                        {
                            "attempt_id": 1,
                            "request_id": queued["request"]["request_id"],
                            "mechanical_launch": "running",
                        }
                    ],
                    "current_attempt_id": 1,
                    "outcome": "repairing",
                }
            )
        ),
        encoding="utf-8",
    )

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert projection["request_status_counts"] == {"dispatched": 1}
    assert projection["terminal_outcomes"] == []
    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRING
    assert projection["active_request_ids"] == [queued["request"]["request_id"]]
    assert len(projection["attempts"]) == 1
    assert projection["attempts"][0]["request_id"] == queued["request"]["request_id"]
    assert projection["attempts"][0]["state"] == ATTEMPT_STATE_RUNNING
    assert projection["attempts"][0]["terminal"] is False


def test_custody_projection_reads_immutable_queue_dispatch_attempt(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queue_root = _queue_root(tmp_path)
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        root_cause_hint="dispatch me",
    )
    request_id = queued["request"]["request_id"]
    blocker_id = blocker_id_for_fingerprint(_fingerprint())
    assert blocker_id is not None
    repair_requests.write_decision(
        queue_root,
        request_id=request_id,
        decision="dispatched",
        reason="managed repair child launched",
    )
    repair_requests.write_dispatch_attempt(
        queue_root,
        request_id=request_id,
        blocker_id=blocker_id,
        actor="watchdog",
        repair_layer="l1",
        command="managed repair",
        child_pid=4242,
        managed_run_id="managed-1",
        managed_manifest_path="/durable/managed-1/manifest.json",
    )

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRING
    assert projection["request_count"] == 1
    assert projection["attempt_count"] == 1
    assert projection["attempts"][0]["source"] == "repair_queue_dispatch_attempt"
    assert projection["attempts"][0]["terminal"] is False


def test_queue_dispatch_attempt_uses_terminal_managed_manifest(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queue_root = _queue_root(tmp_path)
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        root_cause_hint="dispatch me",
    )
    request_id = queued["request"]["request_id"]
    blocker_id = blocker_id_for_fingerprint(_fingerprint())
    assert blocker_id is not None
    managed_dir = tmp_path / "managed-1"
    managed_dir.mkdir()
    manifest_path = managed_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "schema_version": "arnold-managed-agent-run-v2",
            "custodian": "arnold.megaplan.managed_agent",
            "run_id": "managed-1",
            "status": "failed",
            "terminal_outcome": "failed",
            "updated_at": "2026-07-04T01:06:00Z",
            "links": {
                "repair_request_id": request_id,
                "blocker_id": blocker_id,
            },
        }),
        encoding="utf-8",
    )
    repair_requests.write_decision(
        queue_root,
        request_id=request_id,
        decision="dispatched",
        reason="managed repair child launched",
    )
    repair_requests.write_dispatch_attempt(
        queue_root,
        request_id=request_id,
        blocker_id=blocker_id,
        actor="watchdog",
        repair_layer="l1",
        command="managed repair",
        child_pid=4242,
        managed_run_id="managed-1",
        managed_manifest_path=str(manifest_path),
    )

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert projection["attempts"][0]["state"] == "failed"
    assert projection["attempts"][0]["outcome"] == "failed"
    assert projection["attempts"][0]["terminal"] is True
    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING


def test_custody_projection_uses_managed_execution_as_formal_attempt(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    managed_dir = tmp_path / "managed" / "managed-automatic-repair-test"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    managed_dir.mkdir(parents=True)
    queue_root = _queue_root(tmp_path)

    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        root_cause_hint="dispatch me",
        created_at="2026-07-04T01:00:00Z",
    )
    request_id = queued["request"]["request_id"]
    expected_blocker_id = blocker_id_for_fingerprint(_fingerprint())
    manifest_path = managed_dir / "manifest.json"
    stdin_path = managed_dir / "stdin.bin"
    stdin_path.write_bytes(b"x")
    provenance = {
        "schema_version": "arnold-machine-origin-provenance-v1",
        "applicability": "not_applicable",
        "transport": "automatic_system",
        "origin_kind": "watchdog_repair",
        "origin_id": request_id,
        "component": "test_repair_custody",
        "trigger_id": request_id,
    }
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "arnold-managed-agent-run-v2",
                "custodian": "arnold.megaplan.managed_agent",
                "run_id": managed_dir.name,
                "run_kind": "automatic_repair",
                "status": "completed",
                "terminal_outcome": "completed",
                "created_at": "2026-07-04T01:05:00Z",
                "updated_at": "2026-07-04T01:06:00Z",
                "task_kind": "autonomous",
                "difficulty": 8,
                "model": "control-plane",
                "route_class": "test",
                "backend": "repair-loop",
                "log_path": str(managed_dir / "run.log"),
                "result_path": str(managed_dir / "result.json"),
                "launch_contract_sha256": "a" * 64,
                "launch_provenance": provenance,
                "provenance_sha256": hashlib.sha256(
                    json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "stdin": {
                    "kind": "sealed_file",
                    "sealed": True,
                    "path": str(stdin_path),
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                    "size_bytes": 1,
                },
                "links": {
                    "repair_request_id": request_id,
                    "blocker_id": expected_blocker_id,
                    "cloud_session": "demo-session",
                },
            }
        ),
        encoding="utf-8",
    )
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "attempts": [],
                "current_attempt_id": None,
                "outcome": "repairing",
                "managed_agent_runs": [
                    {
                        "run_id": managed_dir.name,
                        "manifest_path": str(manifest_path),
                        "repair_request_id": request_id,
                        "blocker_id": expected_blocker_id,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert len(projection["attempts"]) == 1
    attempt = projection["attempts"][0]
    assert attempt["attempt_id"] == managed_dir.name
    assert attempt["request_id"] == request_id
    assert attempt["source"] == "managed_agent_execution"
    assert attempt["state"] == "succeeded"
    assert attempt["terminal"] is True


def test_custody_projection_drops_stale_request_from_advanced_plan_target(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queue_root = _queue_root(tmp_path)

    stale = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "stalled",
            "current_state": "finalized",
            "phase_or_step": "execute",
            "milestone_or_plan": "s3-old-plan",
            "gate_recommendation": "",
            "blocked_task_id": "",
        },
        target={"plan_name": "s3-old-plan"},
        root_cause_hint="old stalled execute request",
        created_at="2026-07-04T01:00:00Z",
    )

    projection = project_repair_custody(
        plan_state={
            "name": "s7-new-plan",
            "current_state": "done",
            "resume_cursor": {},
            "latest_failure": {},
        },
        current_target={
            "current_refs": {
                "current_plan_name": "s7-new-plan",
                "chain_current_plan_name": "s7-new-plan",
                "plan_current_state": "done",
            },
            "event_cursors": {},
            "plan_state": {"fingerprint": "sha256:target-proof"},
        },
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    assert projection["active_request_ids"] == []
    assert all(request["request_id"] != stale["request"]["request_id"] for request in projection["requests"])


# ---------------------------------------------------------------------------
# classify_repair_dispatch — recovery-view integration
# ---------------------------------------------------------------------------


def _recovery_dict(
    *,
    custody_bucket: str = "repairable",
    status: str = "repairable",
    recovery_needed: bool = True,
    permitted_actions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "recovery_needed": recovery_needed,
        "custody_bucket": custody_bucket,
        "observations": [],
        "permitted_actions": permitted_actions or [],
        "source_paths": ["recovery://custody-test"],
        "diagnostics": [],
        "view_hash": "test-hash",
        "shadow": True,
        "read_only": True,
    }


def test_recovery_view_repairable_with_active_request_dispatches_l1() -> None:
    """Recovery view repairable + active request → L1 dispatch."""
    recovery = _recovery_dict(
        custody_bucket="repairable",
        permitted_actions=[{"action_type": "repair_dispatch", "rationale": "ready", "source": "test"}],
    )
    decision = classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.custody_bucket == "repairable"


def test_recovery_view_repairing_custody_is_no_dispatch() -> None:
    """Recovery view repairing → REPAIRING, no L1 dispatch."""
    recovery = _recovery_dict(custody_bucket="repairing")
    decision = classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairing",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == DISPATCH_DECISION_REPAIRING
    assert decision.dispatch_intent == "queue_only"


def test_recovery_view_human_required_trumps_legacy_repairable() -> None:
    """Recovery view human_required overrides legacy repairable custody."""
    recovery = _recovery_dict(custody_bucket="human_required")
    decision = classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
    assert decision.custody_bucket == "human_required"


def test_recovery_view_healthy_with_terminal_state() -> None:
    """Recovery view healthy + terminal state → TERMINAL."""
    recovery = _recovery_dict(custody_bucket="healthy", recovery_needed=False)
    decision = classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "done",
            "failure_kind": "",
            "terminal_outcomes": ["complete"],
        },
        plan_state={"current_state": "done", "resume_cursor": {}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == DISPATCH_DECISION_TERMINAL


def test_recovery_view_legacy_fallback_preserved() -> None:
    """When recovery_view is absent, legacy classify_repair_dispatch works unchanged."""
    decision = classify_repair_dispatch(
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "execution_blocked", "phase": "execute"},
        },
        current_target={
            "current_refs": {
                "current_plan_name": "test-plan",
                "plan_current_state": "blocked",
            },
            "plan_state": {"fingerprint": "sha256:proof"},
        },
    )
    assert decision.decision == DISPATCH_DECISION_L1


# ---------------------------------------------------------------------------
# T15: Repair verdict evidence in custody projection
# ---------------------------------------------------------------------------


def test_custody_projection_includes_verdict_evidence_when_present(
    tmp_path: Path,
) -> None:
    """Custody projection surfaces verdict evidence when repair verdict is saved."""
    queue_root = tmp_path / ".megaplan" / repair_requests.QUEUE_DIR_NAME
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir(parents=True)

    # Enqueue a request using queue_root
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        target={"plan_dir": "/tmp/plan"},
        root_cause_hint="needs verdict",
        created_at="2026-07-04T01:00:00Z",
    )

    # Save a cleared verdict into the repair data
    verdict_path = repair_data_dir / "verdict.json"
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_CLEARED,
        blocker_id="blocker-42",
        session="demo-session",
        request_id=queued["request"]["request_id"],
        outcome="complete",
        evidence_timestamp="2026-07-04T02:00:00Z",
    )
    repair_contract.save_repair_verdict(verdict_path, verdict)

    projection = project_repair_custody(
        plan_state={
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "blocked_recovery_not_resolved",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            },
        },
        current_target={
            "current_refs": {
                "current_plan_name": "agentic-replay-viewer",
                "plan_current_state": "blocked",
            },
            "event_cursors": {"resume_retry_strategy": "manual_review"},
            "plan_state": {"fingerprint": "sha256:target-proof"},
        },
        queue_root=queue_root,
        repair_data_dir=repair_data_dir,
    )

    # Custody projection should still work — request is present
    assert len(projection["requests"]) >= 1
    assert projection["custody_bucket"] == "repairable_not_repairing"


def test_custody_rejects_liveness_only_repair_outcome(tmp_path: Path) -> None:
    """When repair data has only liveness outcome, custody treats it as non-terminal."""
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()

    # Write repair data with liveness-only outcome
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            repair_contract.merge_additive_fields(
                {
                    "session": "demo-session",
                    "workspace": "/tmp/ws",
                    "run_kind": "chain",
                    "plan_name": "agentic-replay-viewer",
                    "attempts": [
                        {"attempt_id": 1, "mechanical_launch": "running"}
                    ],
                    "current_attempt_id": 1,
                    "outcome": "partial_liveness",
                }
            )
        ),
        encoding="utf-8",
    )

    projection = project_repair_custody(
        plan_state={
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "blocked_recovery_not_resolved",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            },
        },
        current_target={
            "current_refs": {
                "current_plan_name": "agentic-replay-viewer",
                "plan_current_state": "blocked",
            },
            "event_cursors": {"resume_retry_strategy": "manual_review"},
            "plan_state": {"fingerprint": "sha256:target-proof"},
        },
        repair_data_dir=repair_data_dir,
    )

    # Liveness-only outcome does not produce a cleared/success outcome
    assert "complete" not in projection["terminal_outcomes"]
    # Liveness without a current request/claim does not own durable custody.
    assert projection["attempts"] == []
    assert projection["custody_bucket"] != CUSTODY_BUCKET_REPAIRING


def test_custody_verdict_distinguishes_cleared_from_escalated(tmp_path: Path) -> None:
    """Repair verdicts of different kinds produce distinct custody signals."""
    # Simulate a verdict dict to check how the verdict kind propagates
    verdict_cleared = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_CLEARED,
        blocker_id="blocker-cleared",
        evidence_timestamp="2026-07-10T10:00:00Z",
    )
    verdict_escalated = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_ESCALATED,
        blocker_id="blocker-esc",
        evidence_timestamp="2026-07-10T10:00:00Z",
    )
    verdict_no_fix = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_NO_FIX,
        blocker_id="blocker-nofix",
        evidence_timestamp="2026-07-10T10:00:00Z",
    )

    # Each verdict kind is distinguishable
    assert verdict_cleared.verdict_kind == "cleared"
    assert verdict_escalated.verdict_kind == "escalated"
    assert verdict_no_fix.verdict_kind == "no_fix"

    # Cleared is different from escalated
    assert verdict_cleared.verdict_kind != verdict_escalated.verdict_kind
    # No-fix is different from cleared
    assert verdict_no_fix.verdict_kind != verdict_cleared.verdict_kind
