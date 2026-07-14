from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.human_blockers import (
    BlockerVerdict,
    classify_needs_human_blocker,
    dispatch_gate_for_human_blocker,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.status_snapshot import (
    _compose_repair_decision_projection,
    _needs_human_superseded_by_authoritative_recovery,
)
from arnold_pipelines.megaplan.cloud.status_format import format_cloud_status_detailed
from arnold_pipelines.megaplan.handlers.review import _review_quality_block_failure


def _target(plan_state: dict[str, object], *, cursor: str = "sha256:cursor-1") -> dict[str, object]:
    return {
        "schema_version": 1,
        "target_session": "wbc",
        "authoritative_source": "plan_state",
        "current_refs": {
            "current_plan_name": "c1",
            "plan_current_state": plan_state["current_state"],
        },
        "plan_state": {
            "present": True,
            "path": "/evidence/c1/state.json",
            "fingerprint": cursor,
        },
        "chain_state": {"present": False, "fingerprint": ""},
        "chain_log": {"present": False},
        "active_step_heartbeat": {"active": False},
        "needs_human": {"present": False, "plan_refs": []},
        "stale_evidence": [],
        "event_cursors": {
            "resume_retry_strategy": "manual_review",
            "latest_failure_kind": "quality_gate_blocked",
        },
    }


def _quality_state(review_hash: str = "sha256:review-1") -> dict[str, object]:
    state: dict[str, object] = {
        "name": "c1",
        "current_state": "blocked",
        "history": [{"step": "review", "result": "needs_rework"}] * 2,
    }
    failure = _review_quality_block_failure(
        state=state,  # type: ignore[arg-type]
        blockers=["unresolved blocking rework: import contract_reality"],
        rework_items=[
            {
                "task_id": "T1",
                "issue": "runtime import is shadowed",
                "priority": "must",
                "deterministic_check": {
                    "command": "python -c 'import contract_reality'",
                    "baseline_status": "failed",
                    "post_status": "failed",
                },
            }
        ],
        review_artifact_hash=review_hash,
    )
    state["latest_failure"] = failure
    state["resume_cursor"] = {
        "phase": "review",
        "retry_strategy": "manual_review",
        "evidence_cursor": failure["evidence_cursor"],
    }
    return state


def _enqueue_quality(queue_root: Path, target: dict[str, object]) -> dict[str, object]:
    return repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        session="wbc",
        source="watchdog",
        target={"plan_name": "c1"},
        problem_signature={
            "failure_kind": "quality_gate_blocked",
            "current_state": "blocked",
            "phase_or_step": "review",
            "milestone_or_plan": "c1",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
            "event_signature": "",
        },
        root_cause_hint={"target": target, "class": "deterministic_quality"},
    )


def test_detailed_failed_review_statuses_emit_deterministic_quality_evidence() -> None:
    state: dict[str, object] = {
        "name": "c1",
        "current_state": "blocked",
        "history": [{"step": "review", "result": "needs_rework"}],
    }

    failure = _review_quality_block_failure(
        state=state,  # type: ignore[arg-type]
        blockers=["unresolved blocking rework: green_suite"],
        rework_items=[
            {
                "task_id": "T1",
                "issue": "green suite still fails",
                "priority": "must",
                "deterministic_check": {
                    "command": "pytest tests/test_green.py",
                    "baseline_status": "passed",
                    "post_status": "failed: green_suite remains unsatisfied",
                },
            }
        ],
        review_artifact_hash="sha256:review-detail",
    )

    evidence = failure["metadata"]["deterministic_evidence"]  # type: ignore[index]
    assert failure["kind"] == "quality_gate_blocked"
    assert evidence == [
        {
            "command": "pytest tests/test_green.py",
            "baseline_status": "passed",
            "post_status": "failed: green_suite remains unsatisfied",
            "task_id": "T1",
            "issue": "green suite still fails",
        }
    ]


def test_exhausted_deterministic_quality_dispatches_one_bounded_repair_without_human(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    state = _quality_state()
    target = _target(state)
    _enqueue_quality(queue_root, target)

    custody = project_repair_custody(
        plan_state=state,
        current_target=target,
        queue_root=queue_root,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=custody,
    )

    assert state["latest_failure"]["kind"] == "quality_gate_blocked"  # type: ignore[index]
    assert decision.decision == DISPATCH_DECISION_L1
    assert custody["active_request_ids"] == custody["accepted_unclaimed_request_ids"]
    assert len(custody["active_request_ids"]) == 1
    assert custody["retry_budget"]["max_attempts"] == 1
    assert custody["retry_budget"]["used_attempts"] == 0
    assert custody["retry_budget"]["remaining_attempts"] == 1
    assert custody["retry_budget"]["retryable"] is True
    assert custody["retry_budget"]["alert_required"] is False
    assert dispatch_gate_for_human_blocker(None) == "clear"


def test_typed_human_gate_remains_human_only_and_unknown_does_not_invent_one(
    tmp_path: Path,
) -> None:
    resolver = _target({"current_state": "blocked"})
    resolver["needs_human"] = {"present": True, "plan_refs": ["c1"]}
    typed = classify_needs_human_blocker(
        "wbc",
        current_plan="c1",
        marker_dir=tmp_path,
        needs_human_payload={
            "plan_name": "c1",
            "human_gate": "product_decision",
            "decision_required": "choose compatibility semantics",
        },
        resolver_record=resolver,
    )
    unknown = classify_needs_human_blocker(
        "wbc",
        current_plan="c1",
        marker_dir=tmp_path,
        needs_human_payload={"plan_name": "c1", "summary": "repair evidence missing"},
        resolver_record=resolver,
    )

    assert typed.verdict is BlockerVerdict.TRUE_BLOCKER
    assert dispatch_gate_for_human_blocker(typed) == "human_required"
    assert unknown.verdict is BlockerVerdict.AMBIGUOUS_BLOCKER
    assert dispatch_gate_for_human_blocker(unknown) == "broken_superfixer"

    human = classify_repair_dispatch(
        plan_state={"current_state": "blocked"},
        human_blocker_classification=typed,
    )
    broken = classify_repair_dispatch(
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        human_blocker_classification=unknown,
    )
    assert human.decision == DISPATCH_DECISION_HUMAN_REQUIRED
    assert broken.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER


def test_status_watchdog_and_custody_share_cursor_counts_and_unclaimed_retry(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    repair_data = tmp_path / "repair-data"
    repair_data.mkdir()

    for suffix in ("1", "2"):
        state = _quality_state(f"sha256:review-{suffix}")
        target = _target(state, cursor=f"sha256:cursor-{suffix}")
        _enqueue_quality(queue_root, target)
        custody = project_repair_custody(
            plan_state=state,
            current_target=target,
            queue_root=queue_root,
            repair_data_dir=repair_data,
        )
        watchdog = classify_repair_dispatch(
            plan_state=state,
            current_target=target,
            custody_projection=custody,
        )
        status = _compose_repair_decision_projection(
            workspace=workspace,
            repair_data_dir=repair_data,
            plan_state=state,
            current_target=target,
        )
        status_dispatch = status["repair_dispatch"]
        status_custody = status["repair_custody"]
        assert status_dispatch["decision"] == watchdog.decision == DISPATCH_DECISION_L1
        assert status_dispatch["evidence_cursor"] == custody["evidence_cursor"]
        assert status_dispatch["request_count"] == custody["request_count"]
        assert status_dispatch["claim_count"] == custody["claim_count"] == 0
        assert status_dispatch["attempt_count"] == custody["attempt_count"] == 0
        assert status_custody["accepted_unclaimed_request_ids"]
        assert status_dispatch["retry_budget"]["retryable"] is True
        rendered = format_cloud_status_detailed(
            {
                "generated_at": "2026-07-11T22:00:00Z",
                "source": "test",
                "summary": {
                    "running": 0,
                    "repairing": 0,
                    "blocked": 0,
                    "complete": 0,
                    "attention": 1,
                },
                "sessions": [
                    {
                        "session": "wbc",
                        "status": "attention",
                        "repair_dispatch": status_dispatch,
                    }
                ],
            }
        )
        assert "request/claim/attempt=1/0/0" in rendered
        assert "decision=dispatch_l1_repair" in rendered


def test_stale_marker_cannot_override_newer_authoritative_recovery_evidence() -> None:
    marker = {"recorded_at": "2026-07-11T21:44:00+00:00", "summary": "old"}
    state = _quality_state()
    state["latest_failure"]["recorded_at"] = "2026-07-11T21:45:00+00:00"  # type: ignore[index]

    assert _needs_human_superseded_by_authoritative_recovery(
        needs_human=marker,
        plan_state=state,
    )


def test_unclaimed_claim_handoff_retries_are_durable_bounded_and_alert_once(
    tmp_path: Path,
) -> None:
    queue_root = tmp_path / "workspace" / ".megaplan" / "repair-queue"
    state = _quality_state()
    queued = _enqueue_quality(queue_root, _target(state))
    request_id = queued["request"]["request_id"]

    results = [
        repair_requests.record_unclaimed_request_failure(
            queue_root,
            request_id=request_id,
            reason="claim handoff failed",
        )
        for _ in range(4)
    ]
    history = [
        item
        for item in repair_requests.iter_repair_decisions(queue_root)
        if item["request_id"] == request_id
    ]

    assert [item["status"] for item in results] == [
        "retryable",
        "retryable",
        "alerted",
        "alerted",
    ]
    assert sum(item["decision"] == "claim_retry" for item in history) == 3
    assert sum(item["decision"] == "claim_alert" for item in history) == 1
    custody = project_repair_custody(
        plan_state=state,
        current_target=_target(state),
        queue_root=queue_root,
    )
    assert custody["accepted_unclaimed_request_ids"] == [request_id]
    assert custody["retry_budget"]["claim_retries_used"] == 3
    assert custody["retry_budget"]["claim_alerted"] is True


def test_repair_exhaustion_does_not_emit_human_marker_or_notification() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    terminal = wrapper[wrapper.index('if [[ "${BREAKER_TRIPPED:-0}" == "1" ]]'):]

    assert 'repair_data_set_outcome "repair_exhausted"' in terminal
    assert "classification=broken_superfixer" in terminal
    assert "send_discord_escalation" not in terminal
    assert "write_needs_human_marker" not in terminal


def test_repair_loop_shell_quotes_canonical_relaunch_command() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert "printf -v quoted_command_shell '%q' \"$quoted_command\"" in wrapper
    assert 'bash -lc $quoted_command_shell' in wrapper
    assert 'bash -lc "$quoted_command"' not in wrapper
