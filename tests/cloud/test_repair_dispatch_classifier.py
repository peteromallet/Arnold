from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud.human_blockers import (
    BlockerVerdict,
    HumanBlockerClassification,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_REPAIRING,
    DISPATCH_DECISION_TERMINAL,
    DISPATCH_INTENT_BROKEN_SUPERFIXER,
    DISPATCH_INTENT_HUMAN_REQUIRED,
    DISPATCH_INTENT_L1,
    RepairDispatchDecision,
    blocker_fingerprint_from_evidence,
    blocker_id_for_fingerprint,
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.repair_lock import RepairLockResult
from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState


def _plan_state(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "agentic-replay-viewer",
        "current_state": "blocked",
        "resume_cursor": {"retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": "blocked_recovery_not_resolved",
            "phase": "execute",
            "metadata": {"blocked_task_id": "T1"},
        },
    }
    payload.update(overrides)
    return payload


def _current_target(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "authoritative_source": "plan_state",
        "current_refs": {
            "current_plan_name": "agentic-replay-viewer",
            "plan_current_state": "blocked",
        },
        "event_cursors": {"resume_retry_strategy": "manual_review"},
        "plan_state": {"present": True, "fingerprint": "sha256:target-proof"},
    }
    payload.update(overrides)
    return payload


def _human_blocker(verdict: BlockerVerdict) -> HumanBlockerClassification:
    return HumanBlockerClassification(
        verdict=verdict,
        session="demo-session",
        current_plan="agentic-replay-viewer",
        rationale=("fixture",),
    )


def _projection(tmp_path: Path) -> dict[str, object]:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    queued = enqueue_repair_request(
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
        root_cause_hint="repairable blocker",
    )
    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=_current_target(),
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    assert projection["active_request_ids"] == [queued["request"]["request_id"]]
    return projection


def test_classifier_dispatches_exact_manual_review_repairable_shape(tmp_path: Path) -> None:
    projection = _projection(tmp_path)

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
    )

    assert decision == RepairDispatchDecision(
        decision=DISPATCH_DECISION_L1,
        dispatch_intent=DISPATCH_INTENT_L1,
        rationale=("known repairable blocker has active custody and no competing owner",),
        blocker_id=projection["blocker_id"],
        request_id=projection["active_request_ids"][0],
        custody_bucket=projection["custody_bucket"],
        current_state="blocked",
        retry_strategy="manual_review",
        failure_kind="blocked_recovery_not_resolved",
    )


def test_classifier_dispatches_known_repairable_shape_when_canonical_state_unknown(
    tmp_path: Path,
) -> None:
    projection = _projection(tmp_path)

    decision = classify_repair_dispatch(
        canonical_run_state=CanonicalRunState(
            canonical_state=CanonicalState.UNKNOWN,
            confidence="low",
            repairable=False,
            running=False,
            next_action="inspect_evidence",
            reason="resolver lacked a typed classifier",
        ),
        event_plan_dir=tmp_path,
        plan_state=_plan_state(
            latest_failure={
                "kind": "execution_blocked",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            }
        ),
        current_target=_current_target(),
        custody_projection={
            **projection,
            "failure_kind": "execution_blocked",
            "blocker_fingerprint": {
                **dict(projection["blocker_fingerprint"]),
                "failure_kind": "execution_blocked",
            },
        },
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.dispatch_intent == DISPATCH_INTENT_L1
    assert decision.request_id == projection["active_request_ids"][0]
    assert decision.failure_kind == "execution_blocked"
    assert "canonical unknown but legacy evidence proves known repairable shape" in decision.rationale[0]


def test_classifier_dispatches_failed_no_next_step_repair_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    state = _plan_state(
        current_state="failed",
        resume_cursor={"retry_strategy": "repair_state"},
        latest_failure={
            "kind": "no_next_step",
            "phase": "",
            "metadata": {"iteration": 4, "valid_next": []},
        },
    )
    target = _current_target(
        current_refs={
            "current_plan_name": "agentic-replay-viewer",
            "plan_current_state": "failed",
        },
        plan_state={"present": True, "fingerprint": "sha256:no-next-proof"},
    )
    queued = enqueue_repair_request(
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "no_next_step",
            "current_state": "failed",
            "phase_or_step": "status",
            "milestone_or_plan": "agentic-replay-viewer",
        },
        root_cause_hint="state-machine transition gap after finalize",
    )

    projection = project_repair_custody(
        plan_state=state,
        current_target=target,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.request_id == queued["request"]["request_id"]
    assert decision.current_state == "failed"
    assert decision.retry_strategy == "repair_state"
    assert decision.failure_kind == "no_next_step"


def test_classifier_dispatches_failed_rerun_phase_execute_authority_divergence(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    state = _plan_state(
        current_state="failed",
        resume_cursor={"retry_strategy": "rerun_phase"},
        latest_failure={
            "kind": "phase_failed",
            "phase": "review",
            "metadata": {"stderr": "Cannot run 'review' while current state is 'failed'"},
        },
    )
    target = _current_target(
        current_refs={
            "current_plan_name": "agentic-replay-viewer",
            "plan_current_state": "failed",
        },
        plan_state={"present": True, "fingerprint": "sha256:failed-proof"},
        resume_authority_failure={
            "code": "resume_execute_authority_blocked",
            "reason": "execute_authority_diverged",
            "phase": "review",
            "missing_task_ids": ["T1"],
        },
    )
    queued = enqueue_repair_request(
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "phase_failed",
            "current_state": "failed",
            "phase_or_step": "review",
            "milestone_or_plan": "agentic-replay-viewer",
            "blocked_task_id": "T1",
        },
        root_cause_hint="failed plan is blocked on execute authority divergence",
    )

    projection = project_repair_custody(
        plan_state=state,
        current_target=target,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.request_id == queued["request"]["request_id"]
    assert decision.current_state == "failed"
    assert decision.retry_strategy == "rerun_phase"
    assert decision.failure_kind == "phase_failed"


def test_projection_ignores_stale_cross_session_custody_for_execution_blocked(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    enqueue_repair_request(
        marker_dir=marker_dir,
        session="other-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "chain_plan_done_not_advanced",
            "current_state": "plan_done_chain_blocked",
            "phase_or_step": "chain_bookkeeping_reconciliation",
            "milestone_or_plan": "other-plan",
            "blocked_task_id": "T2",
        },
        root_cause_hint="unrelated blocker",
    )
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "live_with_fresh_activity",
                "attempts": [
                    {
                        "attempt_id": 1,
                        "problem_signature": {
                            "current_state": "initialized",
                            "failure_kind": "unknown_failure_mode",
                            "phase_or_step": "init",
                            "milestone_or_plan": "agentic-replay-viewer",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    state = _plan_state(
        latest_failure={
            "kind": "execution_blocked",
            "phase": "execute",
            "metadata": {"blocked_task_id": "T1"},
        }
    )
    target = _current_target(
        target_session="demo-session",
        marker={"session": "demo-session"},
    )
    queued = enqueue_repair_request(
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "execution_blocked",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "blocked_task_id": "T1",
        },
        root_cause_hint="repairable blocker",
    )

    projection = project_repair_custody(
        plan_state=state,
        current_target=target,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=projection,
    )

    assert projection["active_request_ids"] == [queued["request"]["request_id"]]
    assert projection["terminal_outcomes"] == []
    assert projection["attempts"] == []
    assert decision.decision == DISPATCH_DECISION_L1


def test_execution_blocked_fingerprint_extracts_blocked_task_from_reason() -> None:
    fingerprint = blocker_fingerprint_from_evidence(
        plan_state=_plan_state(
            name="progress-auditor-stage-20260704-1400",
            latest_failure={
                "kind": "execution_blocked",
                "phase": "execute",
                "metadata": {
                    "blocking_reasons": [
                        "task T4 reported status=blocked by executor: fixture could not verify handoff_gaps",
                    ],
                },
            },
        ),
        current_target=_current_target(
            current_refs={
                "current_plan_name": "progress-auditor-stage-20260704-1400",
                "plan_current_state": "blocked",
            },
        ),
    )

    assert fingerprint is not None
    assert fingerprint["blocked_task_id"] == "T4"
    assert blocker_id_for_fingerprint(fingerprint)


def test_phase_contract_failure_gets_claimable_phase_scoped_identity() -> None:
    state = _plan_state(
        name="m6-exact-contract",
        resume_cursor={"phase": "critique", "retry_strategy": "repair_phase_contract"},
        latest_failure={
            "kind": "deterministic_phase_failure",
            "phase": "critique",
            "metadata": {"count": 3, "max_attempts": 3},
        },
    )
    target = _current_target(
        current_refs={
            "current_plan_name": "m6-exact-contract",
            "plan_current_state": "blocked",
        },
        event_cursors={"resume_retry_strategy": "repair_phase_contract"},
    )

    fingerprint = blocker_fingerprint_from_evidence(
        plan_state=state,
        current_target=target,
    )

    assert fingerprint is not None
    assert fingerprint["blocked_task_id"] == "phase:critique"
    assert fingerprint["retry_strategy"] == "repair_phase_contract"
    assert blocker_id_for_fingerprint(fingerprint)


def test_classifier_gates_true_or_ambiguous_human_blockers(tmp_path: Path) -> None:
    projection = _projection(tmp_path)

    for verdict in (BlockerVerdict.TRUE_BLOCKER, BlockerVerdict.AMBIGUOUS_BLOCKER):
        decision = classify_repair_dispatch(
            plan_state=_plan_state(),
            current_target=_current_target(),
            custody_projection=projection,
            human_blocker_classification=_human_blocker(verdict),
        )
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
        assert decision.dispatch_intent == DISPATCH_INTENT_HUMAN_REQUIRED


def test_classifier_marks_mechanical_blocker_as_broken_superfixer(tmp_path: Path) -> None:
    projection = _projection(tmp_path)

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
        human_blocker_classification=_human_blocker(BlockerVerdict.MECHANICAL_BLOCKER),
    )

    assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert decision.dispatch_intent == DISPATCH_INTENT_BROKEN_SUPERFIXER


def test_classifier_treats_active_lock_or_process_as_repairing(tmp_path: Path) -> None:
    projection = _projection(tmp_path)

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
        lock_evidence=RepairLockResult(status="busy", lock_dir=tmp_path / "repair.lock"),
    )
    assert decision.decision == DISPATCH_DECISION_REPAIRING

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
        process_evidence={"status": "running"},
    )
    assert decision.decision == DISPATCH_DECISION_REPAIRING


def test_classifier_defaults_unknown_manual_review_shape_to_human_required(tmp_path: Path) -> None:
    projection = _projection(tmp_path)

    decision = classify_repair_dispatch(
        plan_state=_plan_state(
            latest_failure={
                "kind": "different_failure",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            }
        ),
        current_target=_current_target(),
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
    assert decision.dispatch_intent == DISPATCH_INTENT_HUMAN_REQUIRED


def test_classifier_does_not_dispatch_marker_only_target(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    enqueue_repair_request(
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "agentic-replay-viewer",
            "blocked_task_id": "T1",
        },
        root_cause_hint="marker-only stale session",
    )
    target = _current_target(
        authoritative_source="marker",
        plan_state={"present": False, "fingerprint": ""},
        current_refs={
            "current_plan_name": "agentic-replay-viewer",
            "plan_current_state": "blocked",
        },
    )
    projection = project_repair_custody(
        plan_state=_plan_state(),
        current_target=target,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=target,
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
    assert decision.dispatch_intent == DISPATCH_INTENT_HUMAN_REQUIRED


def test_classifier_recognizes_terminal_repair_state() -> None:
    decision = classify_repair_dispatch(
        plan_state=_plan_state(current_state="done"),
        current_target=_current_target(),
        custody_projection={"terminal_outcomes": []},
    )

    assert decision.decision == DISPATCH_DECISION_TERMINAL


def test_classifier_dispatches_workflow_cursor_mismatch_as_retryable(tmp_path: Path) -> None:
    """A blocked control/cursor disagreement is mechanical, not human-only."""
    projection = _projection(tmp_path)
    projection["active_request_ids"] = ["req-cursor"]
    decision = classify_repair_dispatch(
        plan_state=_plan_state(
            latest_failure={"kind": "workflow_cursor_mismatch", "phase": "execute"}
        ),
        current_target=_current_target(),
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.dispatch_intent == DISPATCH_INTENT_L1


def test_classifier_reopens_complete_repair_when_chain_is_incomplete(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    projection["active_request_ids"] = ["req-incomplete"]
    projection["terminal_outcomes"] = ["complete"]
    target = _current_target(
        chain_state={
            "present": True,
            "fingerprint": "sha256:chain-proof",
            "milestone_total": 2,
            "completed_count": 1,
        }
    )
    decision = classify_repair_dispatch(
        plan_state=_plan_state(current_state="finalized"),
        current_target=target,
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.dispatch_intent == DISPATCH_INTENT_L1
