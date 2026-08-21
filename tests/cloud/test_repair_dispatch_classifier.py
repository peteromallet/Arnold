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
    DISPATCH_DECISION_PENDING_DECISION,
    DISPATCH_DECISION_REPAIRING,
    DISPATCH_DECISION_TERMINAL,
    DISPATCH_INTENT_BROKEN_SUPERFIXER,
    DISPATCH_INTENT_HUMAN_REQUIRED,
    DISPATCH_INTENT_L1,
    DISPATCH_INTENT_QUEUE_ONLY,
    REQUEST_STATUS_PENDING_DECISION,
    RepairDispatchDecision,
    blocker_fingerprint_from_evidence,
    blocker_id_for_fingerprint,
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.repair_lock import RepairLockResult
from arnold_pipelines.megaplan.cloud.repair_requests import (
    enqueue_repair_request as _enqueue_repair_request,
    iter_repair_decisions,
)
from arnold_pipelines.megaplan.handlers.review import _review_quality_block_failure
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState
from tests.cloud.repair_identity_fixtures import identity_for_signature


def enqueue_repair_request(**kwargs: object) -> dict[str, object]:
    signature = dict(kwargs["problem_signature"])  # type: ignore[arg-type]
    kwargs.setdefault(
        "repair_identity",
        identity_for_signature(
            session=str(kwargs["session"]),
            signature=signature,
        ),
    )
    return _enqueue_repair_request(**kwargs)


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
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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


def test_classifier_keeps_failed_rerun_phase_execute_authority_divergence_terminal(
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
    enqueue_repair_request(
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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

    assert decision.decision == DISPATCH_DECISION_TERMINAL
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
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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


def test_accepted_phase_contract_request_stays_claimable_after_phase_replay(
    tmp_path: Path,
) -> None:
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    queued = enqueue_repair_request(
        queue_root=queue_root,
        session="demo-session",
        source="lifecycle_failure",
        target={"plan_name": "m6-exact-contract"},
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "critique",
            "milestone_or_plan": "m6-exact-contract",
            "blocked_task_id": "",
        },
        root_cause_hint="critique contract failed repeatedly",
    )
    state = {"name": "m6-exact-contract", "current_state": "critiqued"}
    target = _current_target(
        target_session="demo-session",
        current_refs={
            "current_plan_name": "m6-exact-contract",
            "plan_current_state": "critiqued",
        },
        event_cursors={},
        plan_state={"present": True, "fingerprint": "sha256:replayed-critique"},
    )

    projection = project_repair_custody(
        plan_state=state,
        current_target=target,
        queue_root=queue_root,
    )

    assert projection["active_request_ids"] == [queued["request"]["request_id"]]
    assert projection["blocker_id"]
    assert projection["blocker_fingerprint"]["retry_strategy"] == "repair_phase_contract"
    assert projection["blocker_fingerprint"]["blocked_task_id"] == "phase:critique"


def test_classifier_gates_typed_human_blockers_and_escalates_ambiguity(
    tmp_path: Path,
) -> None:
    projection = _projection(tmp_path)

    expected = {
        BlockerVerdict.TRUE_BLOCKER: (
            DISPATCH_DECISION_HUMAN_REQUIRED,
            DISPATCH_INTENT_HUMAN_REQUIRED,
        ),
        BlockerVerdict.AMBIGUOUS_BLOCKER: (
            DISPATCH_DECISION_BROKEN_SUPERFIXER,
            DISPATCH_INTENT_BROKEN_SUPERFIXER,
        ),
    }
    for verdict, (expected_decision, expected_intent) in expected.items():
        decision = classify_repair_dispatch(
            plan_state=_plan_state(),
            current_target=_current_target(),
            custody_projection=projection,
            human_blocker_classification=_human_blocker(verdict),
        )
        assert decision.decision == expected_decision
        assert decision.dispatch_intent == expected_intent


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


def test_classifier_requires_blocker_scoped_custody_not_process_liveness(
    tmp_path: Path,
) -> None:
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
    assert decision.decision == DISPATCH_DECISION_L1


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
        queue_root=tmp_path / ".megaplan" / "repair-queue",
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


def test_request_without_decision_projects_typed_pending_and_never_active(
    tmp_path: Path,
) -> None:
    """A request marker with no decision record is typed pending/blocked."""
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    queued = enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=tmp_path / "markers",
        session="demo-session",
        source="lifecycle_failure",
        target={"plan_name": "m6-exact-contract"},
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "critique",
            "milestone_or_plan": "m6-exact-contract",
            "blocked_task_id": "",
        },
        root_cause_hint="critique contract failed repeatedly",
    )
    request_id = str(queued["request"]["request_id"])
    # Simulate a crash between the request-marker write and the decision
    # write: remove every decision record for this request.
    decision_records = [
        record
        for record in iter_repair_decisions(queue_root)
        if str(record.get("request_id")) == request_id
    ]
    assert decision_records, "enqueue must persist an accepted decision first"
    for record in decision_records:
        Path(str(record["_path"])).unlink()

    projection = project_repair_custody(
        plan_state=_plan_state(
            name="m6-exact-contract",
            resume_cursor={"phase": "critique", "retry_strategy": "repair_phase_contract"},
            latest_failure={
                "kind": "deterministic_phase_failure",
                "phase": "critique",
                "metadata": {"count": 3, "max_attempts": 3},
            },
        ),
        current_target=_current_target(
            target_session="demo-session",
            current_refs={
                "current_plan_name": "m6-exact-contract",
                "plan_current_state": "blocked",
            },
            event_cursors={"resume_retry_strategy": "repair_phase_contract"},
            plan_state={"present": True, "fingerprint": "sha256:replayed-critique"},
        ),
        queue_root=queue_root,
    )

    assert projection["active_request_ids"] == []
    assert projection["request_status_counts"] == {REQUEST_STATUS_PENDING_DECISION: 1}
    record = next(
        item for item in projection["requests"] if item["request_id"] == request_id
    )
    assert record["status"] == REQUEST_STATUS_PENDING_DECISION
    assert record["active"] is False
    assert record["claimable"] is False
    assert record["decision"] is None

    # Absent decision must NEVER dispatch: no active request means the
    # classifier cannot authorize L1 for this blocker.
    decision = classify_repair_dispatch(
        plan_state=_plan_state(
            name="m6-exact-contract",
            resume_cursor={"phase": "critique", "retry_strategy": "repair_phase_contract"},
            latest_failure={
                "kind": "deterministic_phase_failure",
                "phase": "critique",
                "metadata": {"count": 3, "max_attempts": 3},
            },
        ),
        current_target=_current_target(
            target_session="demo-session",
            current_refs={
                "current_plan_name": "m6-exact-contract",
                "plan_current_state": "blocked",
            },
            event_cursors={"resume_retry_strategy": "repair_phase_contract"},
            plan_state={"present": True, "fingerprint": "sha256:replayed-critique"},
        ),
        custody_projection=projection,
    )
    assert decision.decision != DISPATCH_DECISION_L1
    assert decision.request_id == ""


def test_classifier_never_dispatches_request_without_decision(tmp_path: Path) -> None:
    """Even a hand-built active projection cannot dispatch without a decision."""
    projection = _projection(tmp_path)
    request_id = str(projection["active_request_ids"][0])
    projection["active_request_ids"] = [request_id]
    for item in projection["requests"]:
        if str(item["request_id"]) == request_id:
            item["status"] = REQUEST_STATUS_PENDING_DECISION
            item["active"] = True
            item["claimable"] = False
            item["decision"] = None

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_PENDING_DECISION
    assert decision.dispatch_intent == DISPATCH_INTENT_QUEUE_ONLY
    assert decision.request_id == request_id


def test_classifier_never_dispatches_rejected_request_decision(tmp_path: Path) -> None:
    """A rejected (non-dispatchable) decision never authorizes L1."""
    projection = _projection(tmp_path)
    request_id = str(projection["active_request_ids"][0])
    projection["active_request_ids"] = [request_id]
    for item in projection["requests"]:
        if str(item["request_id"]) == request_id:
            item["status"] = "stale"
            item["active"] = True
            item["claimable"] = False
            item["decision"] = {
                "decision_id": "rejected-decision",
                "request_id": request_id,
                "decision": "stale",
                "reason": "rejected by operator",
                "related_request_id": "",
                "created_at": "2026-07-16T13:35:03Z",
                "path": "/queue/decisions/rejected.json",
            }

    decision = classify_repair_dispatch(
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_PENDING_DECISION
    assert decision.dispatch_intent == DISPATCH_INTENT_QUEUE_ONLY
    assert decision.request_id == request_id


def test_classifier_dispatches_deterministic_phase_failure_with_canonical_request(
    tmp_path: Path,
) -> None:
    """Deterministic mechanical phase failures with a canonical request go L1."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    state = _plan_state(
        name="m6-exact-contract",
        current_state="blocked",
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
    queued = enqueue_repair_request(
        queue_root=tmp_path / ".megaplan" / "repair-queue",
        marker_dir=marker_dir,
        session="demo-session",
        source="lifecycle_failure",
        target={"plan_name": "m6-exact-contract"},
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "critique",
            "milestone_or_plan": "m6-exact-contract",
            "blocked_task_id": "",
        },
        root_cause_hint="critique contract failed repeatedly",
    )
    projection = project_repair_custody(
        plan_state=state,
        current_target=target,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

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
        plan_state=state,
        current_target=target,
        custody_projection=projection,
    )

    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.dispatch_intent == DISPATCH_INTENT_L1
    assert decision.request_id == str(queued["request"]["request_id"])
    assert decision.failure_kind == "deterministic_phase_failure"
 
 
def _quality_dispatch_fixture(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    disposable_root = (tmp_path / "t23-disposable").resolve()
    disposable_root.mkdir(exist_ok=True)
    project_root = Path(__file__).parents[2].resolve()
    assert disposable_root != project_root and project_root not in disposable_root.parents
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": "blocked",
        "history": [{"step": "review", "result": "needs_rework"}] * 4,
        "meta": {"total_cost_usd": 0.0},
    }
    failure = _review_quality_block_failure(
        state=state,  # type: ignore[arg-type]
        blockers=["unresolved blocking rework: deterministic import check"],
        rework_items=[
            {
                "task_id": "T2",
                "issue": "import check failed",
                "deterministic_check": {
                    "command": "python -c 'import package'",
                    "baseline_status": "failed",
                    "post_status": "failed",
                },
            }
        ],
        review_artifact_hash="a" * 64,
    )
    state["latest_failure"] = failure
    state["resume_cursor"] = {
        "phase": "review",
        "retry_strategy": "manual_review",
        "evidence_cursor": dict(failure["evidence_cursor"]),  # type: ignore[index]
    }
    target: dict[str, object] = {
        "authoritative_source": "plan_state",
        "current_refs": {
            "current_plan_name": "review-quality-plan",
            "plan_current_state": "blocked",
        },
        "plan_state": {
            "present": True,
            "name": "review-quality-plan",
            "current_state": "blocked",
            "current_phase": "review",
            "resume_cursor": dict(state["resume_cursor"]),  # type: ignore[arg-type]
        },
    }
    return state, target


def _quality_dispatch_decision(
    state: dict[str, object], target: dict[str, object]
) -> RepairDispatchDecision:
    return classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection={
            "blocker_id": "blocker:quality-review",
            "active_request_ids": ["request-quality-review"],
            "custody_bucket": CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
        },
    )


def test_t23_valid_complete_quality_failure_dispatches(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    decision = _quality_dispatch_decision(state, target)
    assert decision.decision == DISPATCH_DECISION_L1
    assert decision.dispatch_intent == DISPATCH_INTENT_L1
    assert decision.request_id == "request-quality-review"


def test_t23_generic_quality_gate_blocked_is_not_dispatchable(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    state["latest_failure"] = {
        "kind": "quality_gate_blocked",
        "phase": "review",
        "metadata": {},
    }
    decision = _quality_dispatch_decision(state, target)
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_non_review_failure_classes_are_not_dispatchable(tmp_path: Path) -> None:
    for failure_kind in (
        "liveness",
        "quota_exceeded",
        "open_pr",
        "human_only",
        "awaiting_human",
    ):
        state, target = _quality_dispatch_fixture(tmp_path)
        state["latest_failure"] = {
            "kind": failure_kind,
            "phase": "review",
            "metadata": {"deterministic": True, "repairability": "deterministic_machine"},
        }
        decision = _quality_dispatch_decision(state, target)
        assert decision.dispatch_intent != DISPATCH_INTENT_L1, failure_kind


def test_t23_missing_scope_is_not_dispatchable(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    failure = state["latest_failure"]
    assert isinstance(failure, dict)
    metadata = failure["metadata"]
    assert isinstance(metadata, dict)
    metadata.pop("scope")
    decision = _quality_dispatch_decision(state, target)
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_stale_target_is_not_dispatchable(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    refs = target["current_refs"]
    assert isinstance(refs, dict)
    refs["current_plan_name"] = "different-plan"
    decision = _quality_dispatch_decision(state, target)
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_mismatched_cursor_is_not_dispatchable(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    plan_state = target["plan_state"]
    assert isinstance(plan_state, dict)
    resume_cursor = plan_state["resume_cursor"]
    assert isinstance(resume_cursor, dict)
    cursor = resume_cursor["evidence_cursor"]
    assert isinstance(cursor, dict)
    cursor["history_index"] = 99
    decision = _quality_dispatch_decision(state, target)
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_mismatched_evidence_hash_is_not_dispatchable(tmp_path: Path) -> None:
    state, target = _quality_dispatch_fixture(tmp_path)
    failure = state["latest_failure"]
    assert isinstance(failure, dict)
    cursor = failure["evidence_cursor"]
    assert isinstance(cursor, dict)
    cursor["review_artifact_hash"] = "b" * 64
    decision = _quality_dispatch_decision(state, target)
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_untrusted_producer_or_mismatched_digest_is_not_dispatchable(
    tmp_path: Path,
) -> None:
    for field, value in (
        ("trusted", False),
        ("evidence_digest", "0" * 64),
    ):
        state, target = _quality_dispatch_fixture(tmp_path)
        failure = state["latest_failure"]
        assert isinstance(failure, dict)
        if field == "trusted":
            provenance = failure["producer_provenance"]
            assert isinstance(provenance, dict)
            provenance["trusted"] = value
            metadata = failure["metadata"]
            assert isinstance(metadata, dict)
            metadata_provenance = metadata["producer_provenance"]
            assert isinstance(metadata_provenance, dict)
            metadata_provenance["trusted"] = value
        else:
            failure["evidence_digest"] = value
            metadata = failure["metadata"]
            assert isinstance(metadata, dict)
            metadata["evidence_digest"] = value
        decision = _quality_dispatch_decision(state, target)
        assert decision.dispatch_intent != DISPATCH_INTENT_L1, field
