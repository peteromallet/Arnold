from __future__ import annotations

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
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.repair_lock import RepairLockResult
from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request


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


def test_classifier_recognizes_terminal_repair_state() -> None:
    decision = classify_repair_dispatch(
        plan_state=_plan_state(current_state="done"),
        current_target=_current_target(),
        custody_projection={"terminal_outcomes": []},
    )

    assert decision.decision == DISPATCH_DECISION_TERMINAL
