from __future__ import annotations

from arnold_pipelines.megaplan.execute.aggregation import _build_aggregate_execution_payload
from arnold_pipelines.megaplan.execute.wbc import (
    EXECUTE_DISPATCH_WBC_KEY,
    EXECUTE_PARENT_CUSTODY_KEY,
    EXECUTE_TRANSITION_WBC_KEY,
)


def _batch_payload(boundary_id: str, attempt_id: str) -> dict[str, object]:
    return {
        "output": boundary_id,
        "commands_run": [f"pytest {boundary_id}"],
        "files_changed": [f"{boundary_id}.py"],
        "task_updates": [],
        "sense_check_acknowledgments": [],
        EXECUTE_DISPATCH_WBC_KEY: {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "writer_id": "megaplan.execute.dispatch_wbc",
            "surface_name": "megaplan.execute.dispatch_wbc",
            "dispatch_id": f"dispatch:{attempt_id}",
            "plan_revision": "revision-1",
            "fence_token": 3,
            "prerequisite_digest": f"prereq:{attempt_id}",
            "worker_id": f"worker:{attempt_id}",
            "expected_source_version": f"source:{attempt_id}",
            "start_source_lookup_key": f"execute-batch:{attempt_id}:start",
            "terminal_source_lookup_key": f"execute-batch:{attempt_id}:complete",
            "verified_start_sequence": 1,
            "verified_terminal_sequence": 2,
            "verified_reread": True,
        },
        EXECUTE_TRANSITION_WBC_KEY: {
            "schema_version": 1,
            "dispatch_attempt_id": attempt_id,
            "dispatch_id": f"dispatch:{attempt_id}",
            "plan_revision": "revision-1",
            "fence_token": 3,
            "boundary_id": boundary_id,
            "receipt_path": f"boundary_receipts/{boundary_id}.json",
            "transition": "review" if boundary_id == "execute_aggregate_promotion" else "execute",
            "result": "success",
            "batch_number": 1,
            "batches_total": 2,
            "receipt_reread_verified": True,
        },
    }


def test_aggregate_payload_summarizes_execute_wbc_across_batches() -> None:
    aggregate = _build_aggregate_execution_payload(
        [
            _batch_payload("execute_batch_checkpoint", "attempt-1"),
            _batch_payload("execute_aggregate_promotion", "attempt-2"),
        ],
        completed_batches=2,
        total_batches=2,
        mode="code",
    )

    summary = aggregate["execute_wbc"]
    assert summary["all_dispatch_verified"] is True
    assert summary["all_transition_verified"] is True
    assert summary["dispatch_attempt_ids"] == ["attempt-1", "attempt-2"]
    assert summary["boundary_ids"] == [
        "execute_aggregate_promotion",
        "execute_batch_checkpoint",
    ]


def test_aggregate_payload_records_parent_custody_conflicts() -> None:
    payload = _batch_payload("execute_aggregate_promotion", "attempt-1")
    payload[EXECUTE_PARENT_CUSTODY_KEY] = {
        "accepted_subject_ids": ["attempt-1"],
        "active_repair_subject_ids": ["attempt-1"],
    }

    aggregate = _build_aggregate_execution_payload(
        [payload],
        completed_batches=1,
        total_batches=1,
        mode="code",
    )

    parent_custody = aggregate[EXECUTE_PARENT_CUSTODY_KEY]
    assert parent_custody["conflict_free"] is False
    assert parent_custody["conflicting_subject_ids"] == ["attempt-1"]
    assert any(
        "execute parent custody conflict" in issue
        for issue in aggregate["deviations"]
    )
