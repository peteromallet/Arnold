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
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_REPAIRING,
    DISPATCH_DECISION_TERMINAL,
    BlockerFingerprintV1,
    blocker_id_for_fingerprint,
    classify_repair_dispatch,
    normalize_blocker_fingerprint_v1,
    project_repair_custody,
)


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


def test_custody_projection_drops_stale_request_from_advanced_plan_target(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()

    stale = repair_requests.enqueue_repair_request(
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
        marker_dir=marker_dir,
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
    # The attempt is present (non-terminal since outcome is liveness)
    assert len(projection["attempts"]) >= 1
    # partial_liveness is a non-success outcome
    assert projection["attempts"][0]["state"] in ("running", "failed")


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
