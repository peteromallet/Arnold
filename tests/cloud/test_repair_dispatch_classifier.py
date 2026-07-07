from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract as rc
from arnold_pipelines.megaplan.cloud.human_blockers import (
    BlockerVerdict,
    HumanBlockerClassification,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    CUSTODY_BUCKET_REPAIRING,
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_NO_ACTION,
    DISPATCH_DECISION_REPAIRING,
    DISPATCH_DECISION_TERMINAL,
    DISPATCH_INTENT_BROKEN_SUPERFIXER,
    DISPATCH_INTENT_HUMAN_REQUIRED,
    DISPATCH_INTENT_L1,
    DISPATCH_INTENT_QUEUE_ONLY,
    blocker_fingerprint_from_evidence,
    blocker_id_for_fingerprint,
    classify_repair_dispatch,
)
from arnold_pipelines.megaplan.cloud.repair_lock import RepairLockResult
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


def _projection(*, request_id: str = "", active_repair: bool = False) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    custody_bucket = CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    if active_repair:
        attempts.append({"terminal": False, "state": "running"})
        custody_bucket = CUSTODY_BUCKET_REPAIRING
    return {
        "blocker_id": "blk-test-001",
        "custody_bucket": custody_bucket,
        "active_request_ids": [request_id] if request_id else [],
        "terminal_outcomes": [],
        "attempts": attempts,
        "current_target": {},
        "plan_state": {},
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


def _event_plan_dir(tmp_path: Path) -> Path:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _human_blocker(verdict: BlockerVerdict) -> HumanBlockerClassification:
    return HumanBlockerClassification(
        verdict=verdict,
        session="demo-session",
        current_plan="agentic-replay-viewer",
        rationale=("fixture",),
    )


@pytest.mark.parametrize(
    ("state", "request_id", "active_repair", "expected_decision", "expected_intent"),
    [
        (CanonicalState.RUNNING, "req-1", False, DISPATCH_DECISION_NO_ACTION, DISPATCH_INTENT_QUEUE_ONLY),
        (CanonicalState.REPAIRING, "req-1", False, DISPATCH_DECISION_REPAIRING, DISPATCH_INTENT_QUEUE_ONLY),
        (
            CanonicalState.RETRYABLE_EXECUTION_BLOCK,
            "req-1",
            False,
            DISPATCH_DECISION_L1,
            DISPATCH_INTENT_L1,
        ),
        (
            CanonicalState.RETRYABLE_EXECUTION_BLOCK,
            "",
            False,
            DISPATCH_DECISION_NO_ACTION,
            DISPATCH_INTENT_QUEUE_ONLY,
        ),
        (
            CanonicalState.RETRYABLE_EXECUTION_BLOCK,
            "req-1",
            True,
            DISPATCH_DECISION_REPAIRING,
            DISPATCH_INTENT_QUEUE_ONLY,
        ),
        (
            CanonicalState.REAL_IMPLEMENTATION_BLOCK,
            "req-1",
            False,
            DISPATCH_DECISION_L1,
            DISPATCH_INTENT_L1,
        ),
        (
            CanonicalState.HUMAN_ACTION_REQUIRED,
            "req-1",
            False,
            DISPATCH_DECISION_HUMAN_REQUIRED,
            DISPATCH_INTENT_HUMAN_REQUIRED,
        ),
        (
            CanonicalState.COMPLETED,
            "req-1",
            False,
            DISPATCH_DECISION_TERMINAL,
            DISPATCH_INTENT_QUEUE_ONLY,
        ),
        (
            CanonicalState.STALE_DERIVED_STATE,
            "req-1",
            False,
            DISPATCH_DECISION_BROKEN_SUPERFIXER,
            DISPATCH_INTENT_BROKEN_SUPERFIXER,
        ),
        (
            CanonicalState.BROKEN_STATE_MACHINE,
            "req-1",
            False,
            DISPATCH_DECISION_BROKEN_SUPERFIXER,
            DISPATCH_INTENT_BROKEN_SUPERFIXER,
        ),
        (
            CanonicalState.UNKNOWN,
            "req-1",
            False,
            DISPATCH_DECISION_BROKEN_SUPERFIXER,
            DISPATCH_INTENT_BROKEN_SUPERFIXER,
        ),
    ],
)
def test_classifier_maps_every_canonical_state(
    tmp_path: Path,
    state: CanonicalState,
    request_id: str,
    active_repair: bool,
    expected_decision: str,
    expected_intent: str,
) -> None:
    decision = classify_repair_dispatch(
        canonical_run_state=_canonical(state),
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=_projection(request_id=request_id, active_repair=active_repair),
    )

    assert decision.decision == expected_decision
    assert decision.dispatch_intent == expected_intent


def test_classifier_fails_closed_without_canonical_provenance(tmp_path: Path) -> None:
    decision = classify_repair_dispatch(
        canonical_run_state=None,
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=_projection(request_id="req-1"),
    )

    assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert "canonical provenance missing" in decision.rationale[0]


def test_legacy_manual_review_and_human_blockers_do_not_authorize_dispatch(tmp_path: Path) -> None:
    decision = classify_repair_dispatch(
        canonical_run_state=_canonical(CanonicalState.RUNNING),
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=_projection(request_id="req-1"),
        human_blocker_classification=_human_blocker(BlockerVerdict.TRUE_BLOCKER),
    )

    assert decision.decision == DISPATCH_DECISION_NO_ACTION


def test_active_lock_or_process_only_suppresses_machine_actionable_dispatch(tmp_path: Path) -> None:
    decision = classify_repair_dispatch(
        canonical_run_state=_canonical(CanonicalState.REAL_IMPLEMENTATION_BLOCK),
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=_projection(request_id="req-1"),
        lock_evidence=RepairLockResult(status="busy", lock_dir=tmp_path / "repair.lock"),
    )
    assert decision.decision == DISPATCH_DECISION_REPAIRING

    decision = classify_repair_dispatch(
        canonical_run_state=_canonical(CanonicalState.REAL_IMPLEMENTATION_BLOCK),
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(),
        current_target=_current_target(),
        custody_projection=_projection(request_id="req-1"),
        process_evidence={"status": "running"},
    )
    assert decision.decision == DISPATCH_DECISION_REPAIRING


def test_dispatch_emits_drift_only_when_canonical_and_legacy_disagree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []

    def _fake_emit(kind: str, plan_dir: Path, *, phase=None, payload=None, store=None) -> dict[str, object]:
        record = {"kind": kind, "plan_dir": plan_dir, "payload": payload or {}}
        events.append(record)
        return record

    monkeypatch.setattr(rc, "emit", _fake_emit)

    classify_repair_dispatch(
        canonical_run_state=_canonical(CanonicalState.RUNNING, stale_sources=("chain_state",)),
        event_plan_dir=_event_plan_dir(tmp_path),
        plan_state=_plan_state(
            latest_failure={
                "kind": "route_metadata_mismatch",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            }
        ),
        current_target=_current_target(),
        custody_projection=_projection(request_id="req-1"),
    )

    assert len(events) == 1
    assert events[0]["kind"] == rc.EventKind.DRIFT_DETECTED
    payload = events[0]["payload"]
    assert payload["expected"] == DISPATCH_DECISION_NO_ACTION
    assert payload["actual"] == DISPATCH_DECISION_HUMAN_REQUIRED
    assert payload["canonical_state"] == CanonicalState.RUNNING.name


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
