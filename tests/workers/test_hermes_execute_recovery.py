from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.workers.hermes import _reconstruct_execute_payload


def test_reconstruct_execute_payload_prefers_current_batch_output(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Prior batch checkpoint.",
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Prior batch ack."}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_3_output.json").write_text(
        json.dumps(
            {
                "output": "T3: current batch recovered from scratch output.",
                "files_changed": ["src/current.ts"],
                "commands_run": ["npm test -- current"],
                "task_updates": [
                    {
                        "task_id": "T3",
                        "status": "done",
                        "executor_notes": "Current batch task update.",
                        "files_changed": ["src/current.ts"],
                        "commands_run": ["npm test -- current"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC3", "executor_note": "Current batch ack."}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = _reconstruct_execute_payload(
        messages=[
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell",
                            "arguments": json.dumps({"command": "npm test -- current"}),
                        }
                    }
                ],
            }
        ],
        project_dir=project_dir,
        plan_dir=plan_dir,
    )

    assert payload is not None
    assert payload["output"] == "T3: current batch recovered from scratch output."
    assert payload["task_updates"] == [
        {
            "task_id": "T3",
            "status": "done",
            "executor_notes": "Current batch task update.",
            "files_changed": ["src/current.ts"],
            "commands_run": ["npm test -- current"],
        }
    ]
    assert payload["sense_check_acknowledgments"] == [
        {"sense_check_id": "SC3", "executor_note": "Current batch ack."}
    ]
    assert "src/current.ts" in payload["files_changed"]
    assert "npm test -- current" in payload["commands_run"]
