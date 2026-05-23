from __future__ import annotations

from megaplan.execute.core import (
    _build_aggregate_execution_payload,
    _receipt_task_records,
    _task_tier_record,
)
from megaplan.worktrees.identity import make_task_identity


def test_aggregate_execution_output_is_task_shaped() -> None:
    payload = _build_aggregate_execution_payload(
        [
            {
                "output": "T1 done",
                "task_updates": [{"task_id": "T1", "status": "done"}],
            }
        ],
        completed_batches=1,
        total_batches=1,
    )

    assert payload["output"].startswith("Aggregated execute tasks: completed 1/1.")


def test_receipt_task_records_use_safe_task_keys() -> None:
    records = _receipt_task_records(
        [
            {
                "task_updates": [
                    {
                        "task_id": "path/$(bad)\nTrailer: nope",
                        "status": "done",
                        "files_changed": ["megaplan/example.py"],
                        "commands_run": ["pytest tests/test_example.py"],
                    }
                ]
            }
        ]
    )

    identity = make_task_identity("path/$(bad)\nTrailer: nope")
    assert records == [
        {
            "task_id": "path/$(bad)\nTrailer: nope",
            "task_key": identity.task_key,
            "status": "done",
            "files_changed": ["megaplan/example.py"],
            "commands_run": ["pytest tests/test_example.py"],
        }
    ]
    assert "path/" not in records[0]["task_key"]
    assert "\n" not in records[0]["task_key"]


def test_task_to_tier_record_is_task_shaped() -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "complexity": 1},
            {"id": "T2", "complexity": 5},
        ]
    }

    record = _task_tier_record(
        finalize_data,
        "T2",
        tier_map={1: "hermes:flash", 5: "codex:high"},
        resolved_agent="codex",
        resolved_mode="persistent",
        resolved_model="codex-high-v1",
    )

    assert record == {
        "task_id": "T2",
        "task_key": make_task_identity("T2").task_key,
        "task_complexity": 5,
        "tier_model_spec": "codex:high",
        "resolved_agent": "codex",
        "resolved_mode": "persistent",
        "resolved_model": "codex-high-v1",
    }
    assert "batch_complexity" not in record
