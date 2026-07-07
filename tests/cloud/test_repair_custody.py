from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract, repair_requests
from arnold_pipelines.megaplan.cloud.repair_contract import (
    ATTEMPT_STATE_RUNNING,
    BLOCKER_FINGERPRINT_V1_PREFIX,
    CUSTODY_BUCKET_HUMAN_REQUIRED,
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    CUSTODY_BUCKET_REPAIRING,
    BlockerFingerprintV1,
    blocker_id_for_fingerprint,
    normalize_blocker_fingerprint_v1,
    project_repair_custody,
)
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState


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


def _canonical(state: CanonicalState, **overrides: object) -> CanonicalRunState:
    payload = {
        "canonical_state": state,
        "reason": f"{state.name} test state",
        "repairable": state
        in {CanonicalState.REAL_IMPLEMENTATION_BLOCK, CanonicalState.RETRYABLE_EXECUTION_BLOCK},
        "running": state is CanonicalState.RUNNING,
        "human_required": state is CanonicalState.HUMAN_ACTION_REQUIRED,
    }
    payload.update(overrides)
    return CanonicalRunState(**payload)


def test_custody_projection_reads_plan_state_and_accepted_request_without_migration(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()

    queued = repair_requests.enqueue_repair_request(
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
        marker_dir=marker_dir,
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


def test_custody_projection_keeps_request_decisions_separate_from_attempt_outcomes(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()

    queued = repair_requests.enqueue_repair_request(
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
        repair_requests.repair_queue_dir(marker_dir),
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
        marker_dir=marker_dir,
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


def test_custody_projection_uses_canonical_machine_actionable_bucket_when_supplied(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        canonical_run_state=_canonical(CanonicalState.REAL_IMPLEMENTATION_BLOCK),
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING


def test_custody_projection_preserves_legacy_manual_review_bucket_without_canonical(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()

    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert projection["custody_bucket"] == CUSTODY_BUCKET_HUMAN_REQUIRED
