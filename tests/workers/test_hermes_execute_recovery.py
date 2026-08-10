from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.workers.hermes import _reconstruct_execute_payload


def test_reconstruct_execute_payload_never_adopts_unbound_batch_scratch(tmp_path: Path) -> None:
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
    assert payload["task_updates"] == []
    assert payload["sense_check_acknowledgments"] == []
    assert "npm test -- current" in payload["commands_run"]


def test_reconstruct_execute_payload_ignores_stale_checkpoint_after_restart(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    (plan_dir / "execution_batch_12.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T12",
                        "status": "done",
                        "executor_notes": "Recovered from audited checkpoint.",
                        "files_changed": ["src/checkpoint.ts"],
                        "commands_run": ["npm test -- checkpoint"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "sense_check_id": "SC12",
                        "executor_note": "Recovered checkpoint ack.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_13_output.json").write_text(
        json.dumps(
            {
                "output": "[Reconstructed from tool calls] Made 0 tool calls, changed 3 files.",
                "files_changed": ["src/reconstructed.ts"],
                "commands_run": [],
                "task_updates": [],
                "sense_check_acknowledgments": [],
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
                            "arguments": json.dumps(
                                {"command": "python -m pytest tests/cloud/test_meta_repair.py -q"}
                            ),
                        }
                    }
                ],
            }
        ],
        project_dir=project_dir,
        plan_dir=plan_dir,
    )

    assert payload is not None
    assert payload["task_updates"] == []
    assert payload["sense_check_acknowledgments"] == []
    assert "python -m pytest tests/cloud/test_meta_repair.py -q" in payload["commands_run"]


def test_reconstruct_execute_payload_ignores_malformed_scratch_and_checkpoint(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    (plan_dir / "execution_batch_12.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T12",
                        "status": "done",
                        "executor_notes": "Recovered from audited checkpoint.",
                        "files_changed": ["src/checkpoint.ts"],
                        "commands_run": ["npm test -- checkpoint"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "sense_check_id": "SC12",
                        "executor_note": "Recovered checkpoint ack.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_13.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T5",
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC5", "executor_note": ""}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_13_output.json").write_text(
        json.dumps(
            {
                "output": "",
                "files_changed": [],
                "commands_run": [],
                "task_updates": [
                    {
                        "task_id": "T13",
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "auto_attributed_files": False,
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC13", "executor_note": ""}
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
                            "arguments": json.dumps({"command": "pytest -q tests/cloud/test_meta_repair.py"}),
                        }
                    }
                ],
            }
        ],
        project_dir=project_dir,
        plan_dir=plan_dir,
    )

    assert payload is not None
    assert payload["task_updates"] == []
    assert payload["sense_check_acknowledgments"] == []
