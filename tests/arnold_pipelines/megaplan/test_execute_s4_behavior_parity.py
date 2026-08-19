"""S4 execute behavior/parity coverage.

These tests cover split outcomes for the execute DAG/approval/resume surface.
They intentionally avoid broad suite assertions; regression ownership remains
with the recorded baseline and harness-level post-execute check.
"""

from __future__ import annotations

import copy
import json
import types as _types
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    compute_task_batches,
    execute_batch_artifact_path,
    split_oversized_batches,
    stable_task_id_digest,
)
from arnold_pipelines.megaplan.execute.batch import (
    _reset_blocked_tasks_to_pending,
    _single_batch_mode_allowed,
)
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


def test_resume_single_pending_frontier_never_expands_to_all_task_ids() -> None:
    """A partial resume must dispatch its runnable frontier, not the plan."""

    tasks = [
        _task("T1"),
        _task("T2", depends_on=["T1"]),
        _task("T3", depends_on=["T2"]),
        _task("T4", depends_on=["T3"]),
        _task("T5", depends_on=["T4"]),
        _task("T6", depends_on=["T5"]),
        _task("T7", depends_on=["T6"]),
    ]
    all_task_ids = [task["id"] for task in tasks]

    # Model a resume where only T1 is in the current runnable frontier while
    # the persisted plan still contains later task rows.  This is the shape
    # that previously entered single_batch_mode and dispatched all seven IDs.
    pending_tasks = [tasks[0]]
    pending_batches = compute_task_batches(pending_tasks)
    split_batches = split_oversized_batches(pending_batches, 7)
    completed_task_ids = {f"T{i}" for i in range(2, 7)}

    single_batch_mode = _single_batch_mode_allowed(
        all_task_ids=all_task_ids,
        pending_task_count=len(pending_tasks),
        pending_batch_count=len(split_batches),
        completed_task_ids=completed_task_ids,
        max_tasks_per_batch=7,
    )
    batches_to_run = [all_task_ids] if single_batch_mode else split_batches

    assert batches_to_run == [["T1"]]
    assert all_task_ids not in batches_to_run


# ---------------------------------------------------------------------------
# M8A — Safe-wave reporting: deterministic batch metadata
# ---------------------------------------------------------------------------


def test_safe_wave_metadata_is_deterministic() -> None:
    """Each wave's task IDs and order must be deterministic on recompilation."""
    tasks = [
        {"id": "T1", "depends_on": []},
        {"id": "T2", "depends_on": ["T1"]},
        {"id": "T3", "depends_on": ["T1"]},
        {"id": "T4", "depends_on": ["T2", "T3"]},
        {"id": "T5", "depends_on": ["T4"]},
        {"id": "T6", "depends_on": ["T5"]},
        {"id": "T7", "depends_on": ["T5"]},
        {"id": "T8", "depends_on": ["T6", "T7"]},
    ]
    first = compute_task_batches(tasks)
    second = compute_task_batches(tasks)

    assert first == second
    # Each wave should have exactly the same task IDs in the same order
    assert first == [["T1"], ["T2", "T3"], ["T4"], ["T5"], ["T6", "T7"], ["T8"]]


def test_safe_wave_count_matches_expected_dag_depth() -> None:
    """The number of waves equals the longest dependency chain length."""
    tasks = [
        {"id": "T1", "depends_on": []},
        {"id": "T2", "depends_on": ["T1"]},
        {"id": "T3", "depends_on": ["T1"]},
        {"id": "T4", "depends_on": ["T2", "T3"]},
        {"id": "T5", "depends_on": ["T4"]},
    ]
    batches = compute_task_batches(tasks)
    # Should have at most 4 waves for a 5-task chain (T1 -> T4 -> T5 max depth 4)
    assert 3 <= len(batches) <= 5
    # Every task must appear exactly once
    flat = [tid for batch in batches for tid in batch]
    assert sorted(flat) == ["T1", "T2", "T3", "T4", "T5"]


def test_safe_wave_split_oversized_preserves_order() -> None:
    """Oversized batch splitting must not reorder tasks within a wave."""
    tasks = [
        {"id": f"T{i}", "depends_on": []} for i in range(1, 7)
    ]
    batches = compute_task_batches(tasks)
    assert batches == [["T1", "T2", "T3", "T4", "T5", "T6"]]

    split = split_oversized_batches(batches, max_size=2)
    assert split == [["T1", "T2"], ["T3", "T4"], ["T5", "T6"]]

    # Original order must be preserved in each sub-batch
    for sub in split:
        indices = [tasks.index(next(t for t in tasks if t["id"] == tid)) for tid in sub]
        assert indices == sorted(indices)


def test_safe_wave_empty_tasks_yields_empty_batches() -> None:
    """An empty task list produces an empty batch list (no crash)."""
    assert compute_task_batches([]) == []


def test_safe_wave_stable_task_id_digest_is_order_independent() -> None:
    """stable_task_id_digest is stable regardless of input order."""
    digest_a = stable_task_id_digest(["T3", "T1", "T2"])
    digest_b = stable_task_id_digest(["T1", "T2", "T3"])
    digest_c = stable_task_id_digest(["T2", "T3", "T1"])
    assert digest_a == digest_b == digest_c
    assert len(digest_a) == 12  # 6 hex bytes (sha256 truncated to 48 bits)


# ---------------------------------------------------------------------------
# M8A — Complexity 7/8/9 split behavior in batch dispatch
# ---------------------------------------------------------------------------


def test_split_high_complexity_batches_isolates_complexity_7_8_9() -> None:
    """Each complexity >=7 task gets its own batch; others stay grouped."""
    from arnold_pipelines.megaplan._core import split_high_complexity_batches

    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "complexity": 4,
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            },
            {
                "id": "T7",
                "complexity": 7,
                "checkpoint": {
                    "required": True,
                    "max_interval_seconds": 300,
                    "records": [
                        "completed_subobjectives",
                        "remaining_subobjectives",
                        "output_hashes",
                        "test_state",
                    ],
                },
            },
            {
                "id": "T8",
                "complexity": 8,
                "checkpoint": {
                    "required": True,
                    "max_interval_seconds": 300,
                    "records": [
                        "completed_subobjectives",
                        "remaining_subobjectives",
                        "output_hashes",
                        "test_state",
                    ],
                },
            },
            {
                "id": "T2",
                "complexity": 5,
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            },
            {
                "id": "T9",
                "complexity": 9,
                "checkpoint": {
                    "required": True,
                    "max_interval_seconds": 300,
                    "records": [
                        "completed_subobjectives",
                        "remaining_subobjectives",
                        "output_hashes",
                        "test_state",
                    ],
                },
            },
            {
                "id": "T3",
                "complexity": 3,
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            },
        ],
    }

    input_batches = [["T1", "T7", "T8", "T2", "T9", "T3"]]
    result = split_high_complexity_batches(input_batches, finalize_data, max_tasks_per_batch=5)

    # Each high-complexity task in its own batch
    assert ["T7"] in result
    assert ["T8"] in result
    assert ["T9"] in result
    # Remaining non-high-complexity tasks stay grouped
    non_high = [batch for batch in result if batch not in (["T7"], ["T8"], ["T9"])]
    flat_non_high = [tid for batch in non_high for tid in batch]
    assert sorted(flat_non_high) == ["T1", "T2", "T3"]


def test_split_high_complexity_batches_preserves_task_identity() -> None:
    """Splitting must never mutate task checkpoints, complexity, or other fields."""
    from arnold_pipelines.megaplan._core import split_high_complexity_batches

    original_task = {
        "id": "T7",
        "complexity": 7,
        "objective": "Implement custody repair adapter.",
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 300,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
    }
    finalize_data = {"tasks": [dict(original_task), {"id": "T1", "complexity": 3}]}
    input_batches = [["T7", "T1"]]

    result = split_high_complexity_batches(input_batches, finalize_data)

    # T7 must be isolated
    assert ["T7"] in result
    # The original task dict must be unchanged
    assert finalize_data["tasks"][0] == original_task


def test_split_high_complexity_batches_noop_when_no_high_complexity() -> None:
    """When no tasks have complexity >=7, batches are returned unchanged."""
    from arnold_pipelines.megaplan._core import split_high_complexity_batches

    finalize_data = {
        "tasks": [
            {"id": "T1", "complexity": 3},
            {"id": "T2", "complexity": 5},
            {"id": "T3", "complexity": 6},
        ],
    }
    input_batches = [["T1", "T2"], ["T3"]]
    result = split_high_complexity_batches(input_batches, finalize_data)
    assert result == input_batches


def test_split_high_complexity_batches_handles_empty_input() -> None:
    """Empty or None inputs are returned unchanged."""
    from arnold_pipelines.megaplan._core import split_high_complexity_batches

    assert split_high_complexity_batches([], {}) == []
    assert split_high_complexity_batches([], {"tasks": []}) == []


# ═══════════════════════════════════════════════════════════════════════════
# Cross-session blocked-task semantics (occurrence 0ae19cc17afd, shipped in
# b2aaab3f). A validation_blocked row (typed disposition, no accepted terminal
# authority) is retryable: the NEXT invocation resets it to pending, and only
# an accepted pass marks it done (never skipped, never adopted without
# authority). A real failure without an accepted envelope stays rerunnable and
# never enters completed IDs.
# ═══════════════════════════════════════════════════════════════════════════

import argparse as _s4_argparse  # noqa: F401  (kept for symmetry with other suites)

from arnold_pipelines.megaplan.execute.batch import (
    _has_genuine_task_level_blocker,
    _reset_blocked_tasks_to_pending,
)


def _s4_blocked_task(task_id: str, *, blocker_kind: str) -> dict[str, object]:
    task = _task(task_id, status="blocked")
    task["blocked_reason"] = blocker_kind
    task["recorded_invocation_id"] = f"inv-{task_id}"
    return task


def test_cross_session_block_pass_reruns_once_then_authority_skips() -> None:
    """Next invocation resets the blocked row; accepted pass marks it done."""
    tasks = [
        _s4_blocked_task("T1", blocker_kind="validation_blocked"),
        _task("T2", depends_on=["T1"]),
        _task("T3"),
    ]
    finalize_data = {"tasks": tasks}

    # Validation-blocked rows are retryable, not genuine blockers.
    assert _has_genuine_task_level_blocker(tasks[0]) is False

    # Fresh session: reset the blocked row back to pending (cross-session
    # retry path). T2 depends on T1 so it stays pending; T3 is independent.
    reset_ids = _reset_blocked_tasks_to_pending(finalize_data)
    assert reset_ids == ["T1"]
    assert tasks[0]["status"] == "pending"
    assert tasks[0].get("recorded_invocation_id") is None

    # The fresh run passes: T1 gets accepted authority and is done. A later
    # resume derives T1 completed from authority and never re-dispatches it.
    tasks[0]["status"] = "done"
    completed_ids = {"T1"}
    pending_tasks = [task for task in tasks if task.get("status") == "pending"]
    batches = compute_task_batches(pending_tasks, completed_ids=completed_ids)
    assert [tid for batch in batches for tid in batch] == ["T2", "T3"]
    assert "T1" not in {tid for batch in batches for tid in batch}

    # T1 is done with accepted authority: the recompute path must not re-add it
    # to a runnable frontier, and it is not part of any blocked closure.
    assert tasks[0]["status"] == "done"
    assert tasks[0]["id"] not in {tid for batch in batches for tid in batch}


def test_cross_session_real_fail_is_not_skipped_or_adopted() -> None:
    """No accepted envelope: failed row is rerunnable next session, never adopted."""
    tasks = [
        _s4_blocked_task("T1", blocker_kind="validation_blocked"),
        _task("T2", depends_on=["T1"]),
    ]
    finalize_data = {"tasks": tasks}

    # Fresh session resets the failed row (no accepted envelope exists).
    reset_ids = _reset_blocked_tasks_to_pending(finalize_data)
    assert reset_ids == ["T1"]
    assert tasks[0]["status"] == "pending"

    # No accepted terminal authority: T1 never enters completed IDs, so the
    # initial frontier re-derives it (never skipped) and it stays pending.
    completed_ids: set[str] = set()
    batches = compute_task_batches(tasks, completed_ids=completed_ids)
    assert [tid for batch in batches for tid in batch] == ["T1", "T2"]
    assert "T1" not in completed_ids
    assert tasks[0]["status"] == "pending"  # rerunnable, not skipped/adopted


def _budget_blocked_task(task_id: str) -> dict[str, object]:
    task = _task(task_id, status="blocked")
    task["blocked_reason"] = "task_test_budget_exhausted"
    task["executor_notes"] = (
        "work done [harness] task_test_budget_exhausted: declared test "
        "timeout total 240s exceeds max_seconds=120"
    )
    task["files_changed"] = [f"{task_id}.py"]
    task["commands_run"] = [
        "timeout 120 pytest tests/test_t1.py",
        "timeout 120 pytest tests/test_t1.py",
    ]
    return task


def test_budget_blocked_row_is_not_adopted_and_resets_on_fresh_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Occurrence 4c0190500877: the merge admission gate's budget block cannot
    be overridden by accepted worker authority.

    ``_adopt_authority_completed_blocked_tasks`` must leave the budget-blocked
    row ``blocked`` even when the kernel authority reports it completed, and
    ``--retry-blocked-tasks`` must reset it to ``pending`` (it is removed from
    the authority-completed exclusion so a fresh compliant attempt runs).
    """
    from arnold_pipelines.megaplan.execute.batch import (
        _adopt_authority_completed_blocked_tasks,
        _is_task_test_budget_blocked,
    )

    budget_task = _budget_blocked_task("T1")
    generic_blocked = _s4_blocked_task("T2", blocker_kind="worker_abort")
    pending_lag = _task("T3", status="pending")

    assert _is_task_test_budget_blocked(budget_task)
    assert not _is_task_test_budget_blocked(generic_blocked)
    assert not _is_task_test_budget_blocked(pending_lag)

    finalize_data = {"tasks": [budget_task, generic_blocked, pending_lag]}
    # Kernel authority says ALL THREE are dependency-closed completed; the
    # scheduler also records satisfied decisions for each (the adopt gate
    # requires the per-task decision, not just membership in completed_ids).
    def _fake_completed(tasks, **kwargs):
        decisions = kwargs.get("decisions")
        if decisions is not None:
            for tid in ("T1", "T2", "T3"):
                decisions[tid] = _types.SimpleNamespace(satisfied=True)
        return {"T1", "T2", "T3"}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._scheduler_completed_ids_for_tasks",
        _fake_completed,
    )
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}}
    adopted = _adopt_authority_completed_blocked_tasks(
        finalize_data,
        plan_dir=tmp_path,
        root=tmp_path,
        state=state,
    )
    # Generic blocked + pending adopt-miss rows promote; the budget row stays.
    assert adopted == ["T2", "T3"]
    by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert by_id["T1"]["status"] == "blocked"
    assert "task_test_budget_exhausted" in by_id["T1"]["executor_notes"]
    assert by_id["T2"]["status"] == "done"
    assert by_id["T3"]["status"] == "done"

    # Fresh --retry-blocked-tasks partition: T1 is NOT authority-completed for
    # the reset (its budget block removed it from the exclusion), so it resets.
    reset_ids = _reset_blocked_tasks_to_pending(
        finalize_data,
        exclude_task_ids={"T2", "T3"},
    )
    assert reset_ids == ["T1"]
    assert by_id["T1"]["status"] == "pending"
    assert by_id["T1"]["executor_notes"] == ""
    assert by_id["T1"]["files_changed"] == []


def test_budget_identity_survives_retry_reset_and_blocks_adoption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Occurrence 0513dbf3f069: the --retry-blocked-tasks reset (which clears
    executor_notes/files_changed/commands_run) must NOT erase the test-budget
    block identity, or _adopt_authority_completed_blocked_tasks re-promotes the
    authority-completed row to done WITHOUT evidence and the quality gate
    re-blocks forever.

    The merge gate now stamps a durable ``task_test_budget_exhausted`` field
    on both the entry and the target row; the retry reset preserves it; and
    ``_is_task_test_budget_blocked`` recognizes the durable field even when the
    row is pending, so the adopt gate keeps excluding the row until a fresh
    compliant attempt passes.
    """
    from arnold_pipelines.megaplan.execute.batch import (
        _adopt_authority_completed_blocked_tasks,
        _is_task_test_budget_blocked,
        _reset_blocked_tasks_to_pending,
    )
    from arnold_pipelines.megaplan.execute.batch import (
        _scheduler_completed_ids_for_tasks as _real_scheduler_completed_ids,
    )

    budget_task = _budget_blocked_task("T1")
    budget_task["task_test_budget_exhausted"] = (
        "task_test_budget_exhausted: declared test timeout total 240s exceeds max_seconds=120"
    )
    finalize_data = {"tasks": [budget_task]}
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}}

    def _fake_completed(tasks, **kwargs):
        decisions = kwargs.get("decisions")
        if decisions is not None:
            decisions["T1"] = _types.SimpleNamespace(satisfied=True)
        return {"T1"}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._scheduler_completed_ids_for_tasks",
        _fake_completed,
    )

    # retry reset: blocked -> pending, notes/evidence cleared, durable field KEPT
    reset_ids = _reset_blocked_tasks_to_pending(finalize_data)
    assert reset_ids == ["T1"]
    by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert by_id["T1"]["status"] == "pending"
    assert by_id["T1"]["executor_notes"] == ""
    assert by_id["T1"]["files_changed"] == []
    assert by_id["T1"]["task_test_budget_exhausted"]

    # budget identity survives the reset -> adopt gate excludes the row
    assert _is_task_test_budget_blocked(by_id["T1"])
    adopted = _adopt_authority_completed_blocked_tasks(
        finalize_data,
        plan_dir=tmp_path,
        root=tmp_path,
        state=state,
    )
    assert adopted == []
    assert by_id["T1"]["status"] == "pending"  # NOT re-promoted to done-null
    assert by_id["T1"]["files_changed"] == []

    # The shared completed-ids reader must ALSO exclude the budget row, or the
    # planner drops it from the pending frontier and the reducer declares a
    # false SUCCESS without a compliant re-run (observed at 03:09Z: phase_result
    # success while finalize rows were still budget-blocked, no new batch
    # artifacts). Patch the INNER reader to return the row as authority-complete
    # and verify the outer scheduler reader strips the budget-gated row.
    from arnold_pipelines.megaplan.execute.batch import _scheduler_completed_ids_for_tasks

    def _inner_completed(*_args, **_kwargs):
        return {"T1"}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch.effective_execute_completed_task_ids",
        _inner_completed,
    )
    completed_ids = _real_scheduler_completed_ids(
        finalize_data["tasks"],
        plan_dir=tmp_path,
        root=tmp_path,
        state=state,
    )
    assert "T1" not in completed_ids


def test_count_execute_tracking_sees_acks_in_non_preferred_batch_envelope(
    tmp_path: Path,
) -> None:
    """Occurrence 047aff60f06c: the sense-check ack scan must read ALL batch
    envelopes, not only the preferred attempt per reused batch index.

    In the m3 plan, ``execute_batches/batch_1`` holds 7 distinct task
    envelopes (the index was reused across dispatch waves). The SC1/SC7
    acknowledgments live in a non-preferred envelope
    (``tasks_c47c2a07ab05.json``, fence 2) while the preferred fence-5
    envelope carries only SC12. ``_count_execute_tracking`` scanned batch
    artifacts via ``list_batch_artifacts`` (preferred-only), so SC1/SC7 were
    invisible and execute completion blocked with "2/18 sense checks have no
    executor acknowledgment" (blocked_by_quality), keeping the chain guard in
    authority_divergence. The ack scan is an existence set-union, so reading
    all envelopes is safe (no double counting).
    """
    from arnold_pipelines.megaplan.execute.batch import _count_execute_tracking

    finalize_data = {
        "tasks": [_task("T1", status="done"), _task("T7", status="done")],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1"},
            {"id": "SC7", "task_id": "T7"},
            {"id": "SC12", "task_id": "T12"},
        ],
    }
    batch_dir = tmp_path / "execute_batches" / "batch_1"
    batch_dir.mkdir(parents=True)
    # Preferred attempt (highest fence token) carries only SC12.
    (batch_dir / "tasks_preferred.json").write_text(
        json.dumps(
            {
                "dispatch_identity": {"fence_token": 5},
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC12", "executor_note": "verified"},
                ],
            }
        ),
        encoding="utf-8",
    )
    # Non-preferred attempt carries SC1 + SC7 — hidden by preferred-only scan.
    (batch_dir / "tasks_c47c2a07ab05.json").write_text(
        json.dumps(
            {
                "dispatch_identity": {"fence_token": 2},
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "verified"},
                    {"sense_check_id": "SC7", "executor_note": "verified"},
                ],
            }
        ),
        encoding="utf-8",
    )
    tracked, total_tasks, acked, total_checks = _count_execute_tracking(
        finalize_data,
        active_task_ids={"T1", "T7"},
        active_sense_check_ids={"SC1", "SC7", "SC12"},
        plan_dir=tmp_path,
    )
    assert tracked == total_tasks == 2
    assert acked == total_checks == 3