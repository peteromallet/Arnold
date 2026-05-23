from __future__ import annotations

import megaplan.execute.core
from megaplan.execute.core import BatchResult
from megaplan.types import EXECUTE_MODEL_LEGACY_BATCH, EXECUTE_MODEL_WORKTREE_NATIVE
from megaplan.workers import WorkerResult
from megaplan.worktrees.identity import make_task_identity


def _make_result(
    *,
    task_ids: list[str],
    sense_check_ids: list[str],
) -> BatchResult:
    payload = {
        "task_updates": [
            {
                "task_id": task_id,
                "status": "done",
                "executor_notes": f"Completed {task_id}.",
                "files_changed": [],
                "commands_run": [],
            }
            for task_id in task_ids
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": sense_check_id, "executor_note": "ok"}
            for sense_check_id in sense_check_ids
        ],
    }
    return BatchResult(
        worker=WorkerResult(
            payload=payload,
            raw_output="",
            duration_ms=1,
            cost_usd=0.0,
            session_id="session-1",
        ),
        agent="codex",
        mode="persistent",
        refreshed=False,
        payload=payload,
        batch_number=1,
        batch_task_ids=list(task_ids),
        batch_sense_check_ids=list(sense_check_ids),
        merged_task_count=len(task_ids),
        total_task_count=len(task_ids),
        acknowledged_sense_check_count=len(sense_check_ids),
        total_sense_check_count=len(sense_check_ids),
        missing_task_evidence=[],
        execution_audit={"skipped": False, "reason": "", "findings": []},
        finalize_hash="sha256:fake",
        attribution_records=[],
    )


class _ProgressRecorder:
    def __init__(self) -> None:
        self.task_events: list[tuple[str, dict[str, object]]] = []
        self.batch_events: list[tuple[str, dict[str, object]]] = []

    def task_complete(self, task_key: str, **details: object) -> None:
        self.task_events.append((task_key, details))

    def batch_complete(self, batch_id: str, **details: object) -> None:
        self.batch_events.append((batch_id, details))


def test_worktree_native_execute_progress_emits_task_complete_not_batch_complete() -> None:
    task_ids = ["T1", "path/Task: two"]
    result = _make_result(task_ids=task_ids, sense_check_ids=["SC1", "SC2"])
    recorder = _ProgressRecorder()

    megaplan.execute.core._emit_execute_progress(
        recorder,
        state={"config": {"execute_model": EXECUTE_MODEL_WORKTREE_NATIVE}},
        finalize_data={
            "sense_checks": [
                {"id": "SC1", "task_id": "T1"},
                {"id": "SC2", "task_id": "path/Task: two"},
            ]
        },
        batch_number=1,
        batches_total=2,
        batch_task_ids=task_ids,
        batch_sense_check_ids=["SC1", "SC2"],
        result=result,
        blocked=False,
        batch_blocked_ids=[],
        response_state="executed",
        tier_routing_active=False,
        tier_complexity=None,
        tier_spec_raw=None,
        tier_resolved_model=None,
    )

    assert recorder.batch_events == []
    assert [event[0] for event in recorder.task_events] == [
        make_task_identity("T1").task_key,
        make_task_identity("path/Task: two").task_key,
    ]
    first_details = recorder.task_events[0][1]
    assert first_details["summary"] == "Task T1 complete"
    assert first_details["task_id"] == "T1"
    assert first_details["task_id_encoded"] == make_task_identity("T1").original_task_id_encoded
    assert first_details["sense_check_ids"] == ["SC1"]
    assert "batch_number" not in first_details
    assert "batches_total" not in first_details
    assert "task_ids" not in first_details


def test_legacy_execute_progress_keeps_batch_complete() -> None:
    result = _make_result(task_ids=["T1"], sense_check_ids=["SC1"])
    recorder = _ProgressRecorder()

    megaplan.execute.core._emit_execute_progress(
        recorder,
        state={"config": {"execute_model": EXECUTE_MODEL_LEGACY_BATCH}},
        finalize_data={"sense_checks": [{"id": "SC1", "task_id": "T1"}]},
        batch_number=1,
        batches_total=1,
        batch_task_ids=["T1"],
        batch_sense_check_ids=["SC1"],
        result=result,
        blocked=False,
        batch_blocked_ids=[],
        response_state="executed",
        tier_routing_active=False,
        tier_complexity=None,
        tier_spec_raw=None,
        tier_resolved_model=None,
    )

    assert recorder.task_events == []
    assert recorder.batch_events[0][0] == "1"
    assert recorder.batch_events[0][1]["batch_number"] == 1
    assert recorder.batch_events[0][1]["task_ids"] == ["T1"]
