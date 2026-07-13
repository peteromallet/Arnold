from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract, repair_requests
from arnold_pipelines.megaplan.cloud.repair_contract import (
    ATTEMPT_STATE_RUNNING,
    BLOCKER_FINGERPRINT_V1_PREFIX,
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    CUSTODY_BUCKET_REPAIRING,
    BlockerFingerprintV1,
    blocker_id_for_fingerprint,
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
