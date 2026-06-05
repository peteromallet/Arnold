"""Tests for megaplan.execute._binding.reducer (T7).

Parametrises across the four BatchOutcome values with fixture batch results
that produce each outcome, asserting:
  (a) returned BatchReduceResult.value matches expectation
  (b) task['status']/notes mutations match pre-refactor behaviour
  (c) apply_outcome_to_state writes the same current_state and _phase_outcome
      the legacy path writes for the same inputs
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipelines.megaplan._core.scheduler.types import Reduce
from arnold.pipelines.megaplan.execute._binding.reducer import (
    BatchOutcome,
    BatchReduceResult,
    apply_outcome_to_state,
    reduce_batch,
)
from arnold.pipelines.megaplan.execute.batch import BatchResult
from arnold.pipelines.megaplan.planning.state import STATE_EXECUTED
from arnold.pipelines.megaplan.workers import WorkerResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_worker() -> WorkerResult:
    return WorkerResult(
        payload={},
        raw_output="",
        duration_ms=0,
        cost_usd=0.0,
    )


def _make_batch_result(
    *,
    merged_task_count: int = 1,
    total_task_count: int = 1,
    acknowledged_sense_check_count: int = 0,
    total_sense_check_count: int = 0,
    missing_task_evidence: list[str] | None = None,
    payload: dict[str, Any] | None = None,
    batch_task_ids: list[str] | None = None,
) -> BatchResult:
    return BatchResult(
        worker=_make_worker(),
        agent="test-agent",
        mode="test",
        refreshed=False,
        payload=payload or {},
        batch_number=1,
        batch_task_ids=batch_task_ids or ["T1"],
        batch_sense_check_ids=[],
        merged_task_count=merged_task_count,
        total_task_count=total_task_count,
        acknowledged_sense_check_count=acknowledged_sense_check_count,
        total_sense_check_count=total_sense_check_count,
        missing_task_evidence=missing_task_evidence or [],
        execution_audit={},
        finalize_hash="abc123",
    )


# ---------------------------------------------------------------------------
# (a) Four-outcome classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result,finalize_data,batch_task_ids,task_deviation_dict,expected_outcome",
    [
        # SUCCESS: all tasks done, no blocking reasons
        (
            _make_batch_result(
                merged_task_count=1,
                total_task_count=1,
                batch_task_ids=["T1"],
            ),
            {"tasks": [{"id": "T1", "status": "done"}]},
            ["T1"],
            None,
            BatchOutcome.SUCCESS,
        ),
        # BLOCKED_BY_QUALITY: untracked task — missing executor update
        (
            _make_batch_result(
                merged_task_count=0,
                total_task_count=1,
                batch_task_ids=["T1"],
            ),
            {"tasks": [{"id": "T1", "status": "pending"}]},
            ["T1"],
            None,
            BatchOutcome.BLOCKED_BY_QUALITY,
        ),
        # BLOCKED_BY_PREREQ: task explicitly marked blocked by executor
        (
            _make_batch_result(
                merged_task_count=1,
                total_task_count=1,
                batch_task_ids=["T1"],
            ),
            {"tasks": [{"id": "T1", "status": "blocked"}]},
            ["T1"],
            None,
            BatchOutcome.BLOCKED_BY_PREREQ,
        ),
        # TIMEOUT: _phase_outcome carries "timeout" (highest priority)
        (
            _make_batch_result(
                merged_task_count=1,
                total_task_count=1,
                payload={"_phase_outcome": "timeout"},
                batch_task_ids=["T1"],
            ),
            {"tasks": [{"id": "T1", "status": "done"}]},
            ["T1"],
            None,
            BatchOutcome.TIMEOUT,
        ),
    ],
    ids=["success", "blocked_by_quality", "blocked_by_prereq", "timeout"],
)
def test_reduce_batch_outcome(
    result: BatchResult,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
    task_deviation_dict: dict[str, list[str]] | None,
    expected_outcome: BatchOutcome,
) -> None:
    """(a) reduce_batch returns a BatchReduceResult with the expected outcome."""
    reduced = reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        task_deviation_dict=task_deviation_dict,
    )
    assert isinstance(reduced, Reduce)
    assert reduced.value == expected_outcome
    # BatchReduceResult is a subscripted generic alias; verify type via annotation
    assert type(reduced) is Reduce


# ---------------------------------------------------------------------------
# (b) Task mutation: SD2 deviation dict
# ---------------------------------------------------------------------------


def test_reduce_batch_patch_corruption_blocks_task_and_appends_note() -> None:
    """Patch-corruption deviation sets status=blocked and appends harness note."""
    task: dict[str, Any] = {"id": "T1", "status": "done", "executor_notes": ""}
    finalize_data = {"tasks": [task]}
    result = _make_batch_result(
        merged_task_count=1, total_task_count=1, batch_task_ids=["T1"]
    )
    reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict={"T1": ["patch_corruption: foo.py line 5: invalid syntax"]},
    )
    assert task["status"] == "blocked"
    assert "[harness] patch_corruption:" in task["executor_notes"]


def test_reduce_batch_blocking_deviation_downgrades_done_to_blocked() -> None:
    """Blocking deviation auto-downgrades done→blocked with harness note."""
    task: dict[str, Any] = {"id": "T1", "status": "done", "executor_notes": ""}
    finalize_data = {"tasks": [task]}
    result = _make_batch_result(
        merged_task_count=1, total_task_count=1, batch_task_ids=["T1"]
    )
    reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict={"T1": ["correctness failed: logic error in T1"]},
    )
    assert task["status"] == "blocked"
    assert "status auto-downgraded" in task["executor_notes"]
    assert "[harness]" in task["executor_notes"]


def test_reduce_batch_blocking_deviation_appends_to_existing_notes() -> None:
    """Harness note is appended (newline-separated) to non-empty executor_notes."""
    task: dict[str, Any] = {
        "id": "T1",
        "status": "done",
        "executor_notes": "prior note",
    }
    finalize_data = {"tasks": [task]}
    result = _make_batch_result(
        merged_task_count=1, total_task_count=1, batch_task_ids=["T1"]
    )
    reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict={"T1": ["correctness failed: x"]},
    )
    assert task["executor_notes"].startswith("prior note\n")


def test_reduce_batch_legacy_empty_dict_applies_no_mutations() -> None:
    """Empty task_deviation_dict (legacy mode) produces no task mutations."""
    task: dict[str, Any] = {"id": "T1", "status": "done", "executor_notes": ""}
    finalize_data = {"tasks": [task]}
    result = _make_batch_result(
        merged_task_count=1, total_task_count=1, batch_task_ids=["T1"]
    )
    reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict={},
    )
    assert task["status"] == "done"
    assert task["executor_notes"] == ""


def test_reduce_batch_none_deviation_dict_applies_no_mutations() -> None:
    """None task_deviation_dict (legacy mode default) produces no task mutations."""
    task: dict[str, Any] = {"id": "T1", "status": "done", "executor_notes": ""}
    finalize_data = {"tasks": [task]}
    result = _make_batch_result(
        merged_task_count=1, total_task_count=1, batch_task_ids=["T1"]
    )
    reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict=None,
    )
    assert task["status"] == "done"
    assert task["executor_notes"] == ""


# ---------------------------------------------------------------------------
# (c) apply_outcome_to_state: same transitions as legacy path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome,expected_current_state,expected_phase_outcome",
    [
        (BatchOutcome.SUCCESS, STATE_EXECUTED, "success"),
        (BatchOutcome.BLOCKED_BY_QUALITY, "executing", "blocked_by_quality"),
        (BatchOutcome.BLOCKED_BY_PREREQ, "executing", "blocked_by_prereq"),
        (BatchOutcome.TIMEOUT, "executing", "timeout"),
    ],
    ids=["success", "blocked_by_quality", "blocked_by_prereq", "timeout"],
)
def test_apply_outcome_to_state(
    outcome: BatchOutcome,
    expected_current_state: str,
    expected_phase_outcome: str,
) -> None:
    """(c) apply_outcome_to_state writes _phase_outcome and current_state transition."""
    state: dict[str, Any] = {"current_state": "executing"}
    apply_outcome_to_state(state, outcome)
    assert state["_phase_outcome"] == expected_phase_outcome
    assert state["current_state"] == expected_current_state


def test_apply_outcome_success_sets_state_executed() -> None:
    """SUCCESS outcome transitions current_state to STATE_EXECUTED."""
    state: dict[str, Any] = {"current_state": "executing"}
    apply_outcome_to_state(state, BatchOutcome.SUCCESS)
    assert state["current_state"] == STATE_EXECUTED


def test_apply_outcome_non_success_leaves_current_state_unchanged() -> None:
    """Non-SUCCESS outcomes do not change current_state."""
    for outcome in (
        BatchOutcome.BLOCKED_BY_QUALITY,
        BatchOutcome.BLOCKED_BY_PREREQ,
        BatchOutcome.TIMEOUT,
    ):
        state: dict[str, Any] = {"current_state": "executing"}
        apply_outcome_to_state(state, outcome)
        assert state["current_state"] == "executing", (
            f"Expected current_state unchanged for {outcome}"
        )


# ---------------------------------------------------------------------------
# BatchOutcome and BatchReduceResult type smoke tests
# ---------------------------------------------------------------------------


def test_batch_outcome_values() -> None:
    assert BatchOutcome.SUCCESS.value == "success"
    assert BatchOutcome.BLOCKED_BY_QUALITY.value == "blocked_by_quality"
    assert BatchOutcome.BLOCKED_BY_PREREQ.value == "blocked_by_prereq"
    assert BatchOutcome.TIMEOUT.value == "timeout"


def test_batch_reduce_result_is_frozen() -> None:
    r = BatchReduceResult(value=BatchOutcome.SUCCESS)
    assert r.value == BatchOutcome.SUCCESS
    with pytest.raises((AttributeError, TypeError)):
        r.value = BatchOutcome.TIMEOUT  # type: ignore[misc]
