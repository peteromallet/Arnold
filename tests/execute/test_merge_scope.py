from __future__ import annotations

from arnold_pipelines.megaplan.execute.merge import _merge_batch_results


def test_code_execute_rejects_off_batch_task_updates() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T2",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
            {
                "id": "T7",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
        ],
        "sense_checks": [],
    }
    issues: list[str] = []

    merged_count, total_tasks, _ack_count, _total_checks = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [
                {
                    "task_id": "T7",
                    "status": "done",
                    "executor_notes": "completed unrelated task",
                    "files_changed": ["src/unrelated.py"],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [],
        },
        batch_task_ids=["T2"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="code",
    )

    tasks_by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged_count == 0
    assert total_tasks == 1
    assert tasks_by_id["T2"]["status"] == "pending"
    assert tasks_by_id["T7"]["status"] == "pending"
    assert any("unknown task_id 'T7'" in issue for issue in issues)
    assert any("1/1 batch tasks have no executor update" in issue for issue in issues)

