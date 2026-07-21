"""Tests for megaplan.execute._binding.reducer (T7).

Parametrises across the four BatchOutcome values with fixture batch results
that produce each outcome, asserting:
  (a) returned BatchReduceResult.value matches expectation
  (b) task['status']/notes mutations match pre-refactor behaviour
  (c) apply_outcome_to_state writes the same current_state and _phase_outcome
      the legacy path writes for the same inputs
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from arnold_pipelines.megaplan._core.scheduler.types import Reduce
from arnold_pipelines.megaplan.authority.batch_scope import DISPATCH_IDENTITY_KEY
from arnold_pipelines.megaplan.authority.binding import DispatchIdentity
from arnold_pipelines.megaplan.execute._binding.reducer import (
    BatchOutcome,
    BatchReduceResult,
    ReducerEvidence,
    ReducerOutcome,
    apply_outcome_to_state,
    compute_reducer_evidence,
    reduce_batch,
    reduce_batch_full,
)
from arnold_pipelines.megaplan.execute.batch import BatchResult
from arnold_pipelines.megaplan.execute.wbc import (
    EXECUTE_DISPATCH_WBC_KEY,
    EXECUTE_PARENT_CUSTODY_KEY,
    EXECUTE_TRANSITION_WBC_KEY,
)
from arnold_pipelines.megaplan.planning.state import STATE_EXECUTED
from arnold_pipelines.megaplan.workers import WorkerResult


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


def _execute_wbc_payload(
    *,
    transition: str = "review",
    boundary_id: str = "execute_aggregate_promotion",
    result_value: str = "success",
) -> dict[str, Any]:
    dispatch = DispatchIdentity.create(
        dispatch_id="dispatch-1",
        run_id="run-1",
        run_revision="revision-1",
        coordinator_attempt_id="coordinator-1",
        fence_token=3,
        subject_ids=("T1",),
        capabilities=("megaplan.task.result",),
        prerequisite_digest="prereq-1",
        worker_id="worker-1",
    )
    return {
        DISPATCH_IDENTITY_KEY: dispatch.to_dict(),
        EXECUTE_DISPATCH_WBC_KEY: {
            "schema_version": 1,
            "attempt_id": "execute-attempt",
            "writer_id": "megaplan.execute.dispatch_wbc",
            "surface_name": "megaplan.execute.dispatch_wbc",
            "dispatch_id": dispatch.dispatch_id,
            "plan_revision": dispatch.plan_revision,
            "fence_token": dispatch.fence_token,
            "prerequisite_digest": dispatch.prerequisite_digest,
            "worker_id": dispatch.worker_id,
            "expected_source_version": "source.v1",
            "start_source_lookup_key": "execute-batch:1:start",
            "terminal_source_lookup_key": "execute-batch:1:complete",
            "verified_start_sequence": 1,
            "verified_terminal_sequence": 2,
            "verified_reread": True,
        },
        EXECUTE_TRANSITION_WBC_KEY: {
            "schema_version": 1,
            "dispatch_attempt_id": "execute-attempt",
            "dispatch_id": dispatch.dispatch_id,
            "plan_revision": dispatch.plan_revision,
            "fence_token": dispatch.fence_token,
            "boundary_id": boundary_id,
            "receipt_path": f"boundary_receipts/{boundary_id}.json",
            "transition": transition,
            "result": result_value,
            "batch_number": 1,
            "batches_total": 1,
            "receipt_reread_verified": True,
        },
    }


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
    base_payload = _execute_wbc_payload()
    if payload:
        base_payload.update(payload)
    return BatchResult(
        worker=_make_worker(),
        agent="test-agent",
        mode="test",
        refreshed=False,
        payload=base_payload,
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
    "result,finalize_data,batch_task_ids,task_deviation_dict,completed_task_ids,expected_outcome",
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
            {"T1"},
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
            set(),
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
            set(),
            BatchOutcome.BLOCKED_BY_PREREQ,
        ),
        # TIMEOUT: _phase_outcome carries "timeout" (highest priority)
        (
            _make_batch_result(
                merged_task_count=1,
                total_task_count=1,
                payload={
                    "_phase_outcome": "timeout",
                    **_execute_wbc_payload(
                        transition="blocked",
                        boundary_id="execute_resume_anchor",
                        result_value="blocked",
                    ),
                },
                batch_task_ids=["T1"],
            ),
            {"tasks": [{"id": "T1", "status": "done"}]},
            ["T1"],
            None,
            {"T1"},
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
    completed_task_ids: set[str],
    expected_outcome: BatchOutcome,
) -> None:
    """(a) reduce_batch returns a BatchReduceResult with the expected outcome."""
    reduced = reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        task_deviation_dict=task_deviation_dict,
        completed_task_ids=completed_task_ids,
    )
    assert isinstance(reduced, Reduce)
    assert reduced.value == expected_outcome
    # BatchReduceResult is a subscripted generic alias; verify type via annotation
    assert type(reduced) is Reduce


def test_reduce_batch_success_can_use_authority_adapter_evidence(tmp_path) -> None:
    """SUCCESS is allowed when all tracked tasks have corroborated evidence."""
    task = {"id": "T1", "status": "done", "files_changed": ["src/a.py"]}
    (tmp_path / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/a.py"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    reduced = reduce_batch(
        _make_batch_result(
            merged_task_count=1,
            total_task_count=1,
            batch_task_ids=["T1"],
        ),
        finalize_data={"tasks": [task]},
        batch_task_ids=["T1"],
        plan_dir=tmp_path,
    )

    assert reduced.value == BatchOutcome.SUCCESS


def test_reduce_batch_raw_done_without_corroboration_is_not_success(tmp_path) -> None:
    """Raw done divergence cannot produce SUCCESS for a tracked batch task."""
    task = {"id": "T1", "status": "done"}
    (tmp_path / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )

    reduced = reduce_batch(
        _make_batch_result(
            merged_task_count=1,
            total_task_count=1,
            batch_task_ids=["T1"],
        ),
        finalize_data={"tasks": [task]},
        batch_task_ids=["T1"],
        plan_dir=tmp_path,
    )

    assert reduced.value == BatchOutcome.BLOCKED_BY_PREREQ


def test_reduce_batch_blocks_when_execute_transition_evidence_is_missing() -> None:
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        payload={EXECUTE_TRANSITION_WBC_KEY: None},
        batch_task_ids=["T1"],
    )
    finalize_data = {"tasks": [{"id": "T1", "status": "done"}]}

    reduced = reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        completed_task_ids={"T1"},
    )

    assert reduced.value == BatchOutcome.BLOCKED_BY_QUALITY


def test_reduce_batch_blocks_when_parent_custody_conflicts() -> None:
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        payload={
            EXECUTE_PARENT_CUSTODY_KEY: {
                "accepted_subject_ids": ["execute-attempt"],
                "active_repair_subject_ids": ["execute-attempt"],
            }
        },
        batch_task_ids=["T1"],
    )
    finalize_data = {"tasks": [{"id": "T1", "status": "done"}]}

    reduced = reduce_batch(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        completed_task_ids={"T1"},
    )

    assert reduced.value == BatchOutcome.BLOCKED_BY_QUALITY


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


# ---------------------------------------------------------------------------
# T7: Reducer evidence surface tests
# ---------------------------------------------------------------------------


def test_compute_reducer_evidence_child_outputs_structure() -> None:
    """(T7) compute_reducer_evidence produces per-task child_outputs with
    status, files_changed, commands_run, and executor_notes."""
    result = _make_batch_result(
        merged_task_count=2,
        total_task_count=2,
        batch_task_ids=["T1", "T2"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["src/a.py"],
                "commands_run": ["pytest -v"],
                "executor_notes": "all good",
            },
            {
                "id": "T2",
                "status": "done",
                "files_changed": ["src/b.py", "src/c.py"],
                "commands_run": ["pytest -v", "flake8"],
                "executor_notes": "",
            },
        ]
    }

    evidence = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1", "T2"],
    )

    assert isinstance(evidence, ReducerEvidence)
    assert len(evidence.child_outputs) == 2
    assert evidence.child_outputs["T1"] == {
        "status": "done",
        "files_changed": ["src/a.py"],
        "commands_run": ["pytest -v"],
        "executor_notes": "all good",
    }
    assert evidence.child_outputs["T2"]["status"] == "done"
    assert evidence.child_outputs["T2"]["files_changed"] == ["src/b.py", "src/c.py"]
    # Files from child tasks appear in side_effect_refs
    assert "src/a.py" in evidence.side_effect_refs
    assert "src/b.py" in evidence.side_effect_refs
    assert "src/c.py" in evidence.side_effect_refs


def test_compute_reducer_evidence_child_output_without_parent_promotion() -> None:
    """(T7) child_outputs record per-task completion evidence regardless of
    whether parent promotion points exist."""
    result = _make_batch_result(
        merged_task_count=0,
        total_task_count=1,
        batch_task_ids=["T1"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["src/x.py"],
                "commands_run": [],
                "executor_notes": "task done but uncorroborated",
            },
        ]
    }

    evidence = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
    )

    # Child output is recorded faithfully
    assert len(evidence.child_outputs) == 1
    assert evidence.child_outputs["T1"]["status"] == "done"
    assert evidence.child_outputs["T1"]["files_changed"] == ["src/x.py"]

    # parent_promotion_points still exist (completed_task_ids may be empty
    # when uncorroborated), but the child evidence is present regardless
    assert isinstance(evidence.parent_promotion_points, list)
    completed_point = next(
        (p for p in evidence.parent_promotion_points if p["kind"] == "completed_task_ids"),
        None,
    )
    assert completed_point is not None

    # blocked_retry_records should flag the uncorroborated task
    assert len(evidence.blocked_retry_records) >= 1
    t1_record = next(
        (r for r in evidence.blocked_retry_records if r["task_id"] == "T1"), None
    )
    assert t1_record is not None
    assert t1_record["blocked"] is True


def test_compute_reducer_evidence_parent_promotion_without_child_tasks() -> None:
    """(T7) parent_promotion_points carry blocking reasons when no child
    tasks completed — promotion exists but child evidence is absent."""
    result = _make_batch_result(
        merged_task_count=0,
        total_task_count=1,
        batch_task_ids=["T1"],
        missing_task_evidence=["T1"],
    )
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "blocked", "files_changed": [], "executor_notes": ""},
        ]
    }

    evidence = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
    )

    # child_outputs still has the task entry
    assert "T1" in evidence.child_outputs
    assert evidence.child_outputs["T1"]["status"] == "blocked"

    # parent_promotion_points includes blocking_reasons
    blocking_point = next(
        (p for p in evidence.parent_promotion_points if p["kind"] == "blocking_reasons"),
        None,
    )
    assert blocking_point is not None
    assert blocking_point["blocked"] is True
    assert len(blocking_point["reasons"]) > 0

    # phase_outcome promotion point reflects blocked state
    outcome_point = next(
        (p for p in evidence.parent_promotion_points if p["kind"] == "phase_outcome"),
        None,
    )
    assert outcome_point is not None
    assert outcome_point["outcome"] == "blocked"

    # state_transition should be None (no SUCCESS)
    transition_point = next(
        (p for p in evidence.parent_promotion_points if p["kind"] == "state_transition"),
        None,
    )
    assert transition_point is not None
    assert transition_point["target_current_state"] is None


def test_compute_reducer_evidence_non_atomic_side_effect_preservation() -> None:
    """(T7) side_effect_refs preserve files_changed from child tasks
    with deduplication."""
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        batch_task_ids=["T1"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["src/a.py", "src/b.py", "src/a.py"],
                "commands_run": [],
                "executor_notes": "",
            },
        ]
    }

    evidence = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
    )

    # files_changed deduplication: "src/a.py" appears once even though listed twice
    assert evidence.side_effect_refs.count("src/a.py") == 1
    assert "src/a.py" in evidence.side_effect_refs
    assert "src/b.py" in evidence.side_effect_refs
    assert isinstance(evidence.side_effect_refs, list)


def test_compute_reducer_evidence_blocked_retry_records() -> None:
    """(T7) blocked_retry_records carry harness_generated flag and
    retry_eligible for each blocked or uncorroborated task."""
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=2,
        batch_task_ids=["T1", "T2"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "blocked",
                "files_changed": [],
                "commands_run": [],
                "executor_notes": "[harness] patch_corruption: foo.py line 5: invalid syntax",
            },
            {
                "id": "T2",
                "status": "done",
                "files_changed": ["src/x.py"],
                "commands_run": [],
                "executor_notes": "",
            },
        ]
    }

    evidence = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1", "T2"],
    )

    assert len(evidence.blocked_retry_records) >= 1
    t1_record = next(
        (r for r in evidence.blocked_retry_records if r["task_id"] == "T1"), None
    )
    assert t1_record is not None
    assert t1_record["status"] == "blocked"
    assert t1_record["blocked"] is True
    assert t1_record["harness_generated"] is True
    assert t1_record["retry_eligible"] is False


def test_compute_reducer_evidence_repair_domain_separation() -> None:
    """(T7) repair_domain_separation distinguishes repair execution from
    ordinary execution, recording deviation task IDs and repair domain."""
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        batch_task_ids=["T1"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": [],
                "commands_run": [],
                "executor_notes": "",
            },
        ]
    }

    # No deviations → ordinary domain
    evidence_ordinary = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict=None,
    )
    assert evidence_ordinary.repair_domain_separation["is_repair_execution"] is False
    assert evidence_ordinary.repair_domain_separation["repair_domain"] == "ordinary"
    assert evidence_ordinary.repair_domain_separation["deviation_task_ids"] == []
    assert evidence_ordinary.repair_domain_separation["deviation_count"] == 0

    # With deviations → repair domain
    evidence_repair = compute_reducer_evidence(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        task_deviation_dict={"T1": ["correctness failed: logic error"]},
    )
    assert evidence_repair.repair_domain_separation["is_repair_execution"] is True
    assert evidence_repair.repair_domain_separation["repair_domain"] == "repair"
    assert evidence_repair.repair_domain_separation["deviation_task_ids"] == ["T1"]
    assert evidence_repair.repair_domain_separation["deviation_count"] == 1


def test_compute_reducer_evidence_carries_parent_custody_conflicts() -> None:
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        payload={
            EXECUTE_PARENT_CUSTODY_KEY: {
                "accepted_subject_ids": ["execute-attempt"],
                "active_repair_subject_ids": ["execute-attempt"],
            }
        },
        batch_task_ids=["T1"],
    )

    evidence = compute_reducer_evidence(
        result,
        finalize_data={"tasks": [{"id": "T1", "status": "done"}]},
        batch_task_ids=["T1"],
        completed_task_ids={"T1"},
    )

    parent_custody = evidence.aggregate_canonical_outputs["parent_custody"]
    assert parent_custody["conflicting_subject_ids"] == ["execute-attempt"]
    assert "parent_custody_conflicts" in evidence.repair_domain_separation


def test_reduce_batch_full_returns_reducer_outcome() -> None:
    """(T7) reduce_batch_full returns a ReducerOutcome with outcome and evidence."""
    result = _make_batch_result(
        merged_task_count=1,
        total_task_count=1,
        batch_task_ids=["T1"],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["src/a.py"],
                "commands_run": [],
                "executor_notes": "",
            },
        ]
    }

    reducer_outcome = reduce_batch_full(
        result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
    )

    assert isinstance(reducer_outcome, ReducerOutcome)
    assert isinstance(reducer_outcome.outcome, BatchOutcome)
    assert isinstance(reducer_outcome.evidence, ReducerEvidence)
    assert reducer_outcome.value == reducer_outcome.outcome
    assert len(reducer_outcome.evidence.child_outputs) == 1
    assert "T1" in reducer_outcome.evidence.child_outputs


def test_apply_outcome_to_state_writes_reducer_evidence_keys() -> None:
    """(T7) apply_outcome_to_state writes all 7 T5 reducer evidence keys
    into state when evidence is supplied."""
    state: dict[str, Any] = {"current_state": "executing"}

    evidence = ReducerEvidence(
        child_outputs={"T1": {"status": "done", "files_changed": [], "commands_run": [], "executor_notes": ""}},
        aggregate_canonical_outputs={"merged_task_count": 1},
        parent_promotion_points=[{"kind": "completed_task_ids", "task_ids": ["T1"]}],
        side_effect_refs=["src/a.py"],
        blocked_retry_records=[],
        repair_domain_separation={"is_repair_execution": False, "repair_domain": "ordinary"},
        resume_anchors=[{"anchor_kind": "complete", "completed_task_ids": ["T1"]}],
    )

    apply_outcome_to_state(state, BatchOutcome.SUCCESS, evidence=evidence)

    assert state["current_state"] == STATE_EXECUTED
    assert state["_phase_outcome"] == "success"
    assert state["_reducer_child_outputs"] == evidence.child_outputs
    assert state["_reducer_aggregate_canonical_outputs"] == evidence.aggregate_canonical_outputs
    assert state["_reducer_parent_promotion_points"] == evidence.parent_promotion_points
    assert state["_reducer_side_effect_refs"] == evidence.side_effect_refs
    assert state["_reducer_blocked_retry_records"] == evidence.blocked_retry_records
    assert state["_reducer_repair_domain_separation"] == evidence.repair_domain_separation
    assert state["_reducer_resume_anchors"] == evidence.resume_anchors


def test_apply_outcome_to_state_without_evidence_no_reducer_keys() -> None:
    """(T7) apply_outcome_to_state without evidence does not write reducer keys."""
    state: dict[str, Any] = {"current_state": "executing"}
    apply_outcome_to_state(state, BatchOutcome.SUCCESS, evidence=None)

    assert state["current_state"] == STATE_EXECUTED
    assert state["_phase_outcome"] == "success"
    assert "_reducer_child_outputs" not in state
    assert "_reducer_parent_promotion_points" not in state
    assert "_reducer_resume_anchors" not in state
