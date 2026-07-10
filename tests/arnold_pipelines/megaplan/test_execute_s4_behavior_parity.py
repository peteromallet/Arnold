"""S4 execute behavior/parity coverage.

These tests cover split outcomes for the execute DAG/approval/resume surface.
They intentionally avoid broad suite assertions; regression ownership remains
with the recorded baseline and harness-level post-execute check.
"""

from __future__ import annotations

import copy
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    compute_task_batches,
    execute_batch_artifact_path,
    split_oversized_batches,
    stable_task_id_digest,
)
from arnold_pipelines.megaplan.execute.batch import _reset_blocked_tasks_to_pending
from arnold_pipelines.megaplan.execute.policy import (
    ApprovalOutcome,
    NoReviewTerminalOutcome,
    ResumeOutcome,
    evaluate_destructive_approval,
    evaluate_no_review_terminal,
    resolve_partial_failure_resume,
)


def _task(
    task_id: str,
    *,
    status: str = "pending",
    depends_on: list[str] | None = None,
    files_changed: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": task_id,
        "status": status,
        "depends_on": list(depends_on or []),
        "executor_notes": f"notes:{task_id}",
        "files_changed": list(files_changed or [f"{task_id}.py"]),
        "commands_run": [f"pytest {task_id}"],
        "evidence_files": [f"evidence/{task_id}.json"],
        "reviewer_verdict": "recorded",
        "recorded_invocation_id": f"inv-{task_id}",
    }


def test_destructive_approval_split_outcomes_are_policy_visible() -> None:
    approved = evaluate_destructive_approval(
        confirm_destructive=True,
        auto_approve=True,
        user_approved_gate=False,
        is_prose_mode=False,
    )
    missing_confirm = evaluate_destructive_approval(
        confirm_destructive=False,
        auto_approve=True,
        user_approved_gate=False,
        is_prose_mode=False,
    )
    missing_approval = evaluate_destructive_approval(
        confirm_destructive=True,
        auto_approve=False,
        user_approved_gate=False,
        is_prose_mode=False,
    )

    assert approved.outcome is ApprovalOutcome.APPROVED
    assert approved.is_approved is True
    assert missing_confirm.outcome is ApprovalOutcome.DENIED_MISSING_CONFIRM
    assert missing_confirm.is_approved is False
    assert missing_approval.outcome is ApprovalOutcome.DENIED_MISSING_APPROVAL
    assert missing_approval.is_approved is False
    assert {approved.reason, missing_confirm.reason, missing_approval.reason}


def test_batch_two_of_four_block_resume_reruns_only_blocked_batch() -> None:
    finalized_tasks = [
        _task("T1", status="done"),
        _task("T2", status="blocked", depends_on=["T1"]),
        _task("T3", depends_on=["T2"]),
        _task("T4", depends_on=["T3"]),
    ]
    assert compute_task_batches(finalized_tasks) == [["T1"], ["T2"], ["T3"], ["T4"]]

    decision = resolve_partial_failure_resume(
        finalized_tasks,
        completed_task_ids={"T1"},
        preserved_artifact_refs=(
            "execute_batches/batch_2/tasks_existing.json",
            "finalize.json",
        ),
        preserved_receipt_ids=("execute_resume_anchor", "execute_partial_failure"),
    )
    assert decision.outcome is ResumeOutcome.RESUME
    assert decision.rerun_task_ids == ("T2",)
    assert decision.preserved_task_ids == ("T1",)
    assert decision.preserved_receipt_ids == (
        "execute_partial_failure",
        "execute_resume_anchor",
    )

    finalize_data = {"tasks": copy.deepcopy(finalized_tasks)}
    reset_ids = _reset_blocked_tasks_to_pending(finalize_data)
    by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert reset_ids == ["T2"]
    assert by_id["T1"]["status"] == "done"
    assert by_id["T1"]["files_changed"] == ["T1.py"]
    assert by_id["T2"]["status"] == "pending"
    assert by_id["T2"]["files_changed"] == []
    assert by_id["T3"]["status"] == "pending"
    assert by_id["T4"]["status"] == "pending"

    resumed_pending = [
        task
        for task in finalize_data["tasks"]
        if task["id"] != "T1"
    ]
    assert compute_task_batches(resumed_pending, completed_ids={"T1"}) == [
        ["T2"],
        ["T3"],
        ["T4"],
    ]


def test_bare_and_light_no_review_terminal_split_outcomes() -> None:
    bare = evaluate_no_review_terminal(robustness="bare", has_deferred_must=True)
    light_clean = evaluate_no_review_terminal(
        robustness="light",
        has_deferred_must=False,
    )
    light_deferred = evaluate_no_review_terminal(
        robustness="light",
        has_deferred_must=True,
    )
    standard_deferred = evaluate_no_review_terminal(
        robustness="standard",
        has_deferred_must=True,
    )
    standard_clean = evaluate_no_review_terminal(robustness="standard")

    assert bare.outcome is NoReviewTerminalOutcome.TERMINATE_DONE
    assert bare.target_state == "done"
    assert light_clean.outcome is NoReviewTerminalOutcome.TERMINATE_DONE
    assert light_clean.target_state == "done"
    assert light_deferred.outcome is NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN
    assert light_deferred.target_state == "awaiting_human_verify"
    assert standard_deferred.outcome is NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN
    assert standard_deferred.target_state == "awaiting_human_verify"
    assert standard_clean.outcome is NoReviewTerminalOutcome.NOT_APPLICABLE
    assert standard_clean.target_state is None


def test_partial_failure_resume_preserves_success_outputs_and_evidence_refs() -> None:
    tasks = [
        _task("T3", status="blocked"),
        _task("T1", status="done", files_changed=["src/one.py"]),
        _task("T2", status="skipped", files_changed=["docs/two.md"]),
        _task("T4", status="pending"),
    ]
    original_tasks = copy.deepcopy(tasks)

    decision = resolve_partial_failure_resume(
        tasks,
        preserved_artifact_refs=(
            "execute_batches/batch_2/tasks_b.json",
            "execute_batches/batch_1/tasks_a.json",
            "execute_batches/batch_2/tasks_b.json",
        ),
        preserved_receipt_ids=("execute_resume_anchor", "execute_partial_failure"),
    )

    assert decision.outcome is ResumeOutcome.RESUME
    assert decision.should_resume is True
    assert decision.rerun_task_ids == ("T3",)
    assert decision.preserved_task_ids == ("T1", "T2")
    assert decision.preserved_artifact_refs == (
        "execute_batches/batch_1/tasks_a.json",
        "execute_batches/batch_2/tasks_b.json",
    )
    assert decision.debt_registry_preserved is True
    assert decision.preserved_receipt_ids == (
        "execute_partial_failure",
        "execute_resume_anchor",
    )
    assert tasks == original_tasks


def test_batch_ordering_and_s4_paths_are_deterministic(tmp_path: Path) -> None:
    tasks = [
        {"id": "T1", "depends_on": []},
        {"id": "T2", "depends_on": ["T1"]},
        {"id": "T3", "depends_on": ["T1"]},
        {"id": "T4", "depends_on": ["T2", "T3"]},
        {"id": "T5", "depends_on": ["T4"]},
        {"id": "T6", "depends_on": ["T4"]},
    ]
    first = compute_task_batches(copy.deepcopy(tasks))
    second = compute_task_batches(copy.deepcopy(tasks))
    assert first == second == [["T1"], ["T2", "T3"], ["T4"], ["T5", "T6"]]
    assert split_oversized_batches(first, 1) == [
        ["T1"],
        ["T2"],
        ["T3"],
        ["T4"],
        ["T5"],
        ["T6"],
    ]

    sibling_swapped = copy.deepcopy(tasks)
    sibling_swapped[1], sibling_swapped[2] = sibling_swapped[2], sibling_swapped[1]
    assert compute_task_batches(sibling_swapped) == [
        ["T1"],
        ["T3", "T2"],
        ["T4"],
        ["T5", "T6"],
    ]

    digest = stable_task_id_digest(["T3", "T2", "T2"])
    assert digest == stable_task_id_digest(["T2", "T3"])
    artifact = execute_batch_artifact_path(tmp_path, 2, ["T3", "T2"])
    assert artifact == tmp_path / "execute_batches" / "batch_2" / f"tasks_{digest}.json"
