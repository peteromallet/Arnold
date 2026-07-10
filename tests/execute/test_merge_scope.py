from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority.batch_scope import BATCH_SCOPE_KEY, BatchScope
from arnold_pipelines.megaplan.execute.merge import (
    _merge_batch_results,
    reconcile_latest_execution_batch,
)


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
        "sense_checks": [
            {"id": "SC2", "task_id": "T2", "executor_note": ""},
            {"id": "SC7", "task_id": "T7", "executor_note": ""},
        ],
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
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC7", "executor_note": "off-batch check"}
            ],
        },
        batch_task_ids=["T2"],
        batch_sense_check_ids=["SC2"],
        issues=issues,
        mode="code",
    )

    tasks_by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged_count == 0
    assert total_tasks == 1
    assert tasks_by_id["T2"]["status"] == "pending"
    assert tasks_by_id["T7"]["status"] == "pending"
    checks_by_id = {check["id"]: check for check in finalize_data["sense_checks"]}
    assert checks_by_id["SC2"]["executor_note"] == ""
    assert checks_by_id["SC7"]["executor_note"] == ""
    assert any("unknown task_id 'T7'" in issue for issue in issues)
    assert any("unknown sense_check_id 'SC7'" in issue for issue in issues)
    assert any("1/1 batch tasks have no executor update" in issue for issue in issues)


def test_creative_execute_rejects_off_batch_tasks_and_sense_checks() -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending", "executor_notes": "", "sections_written": []},
            {"id": "T9", "status": "pending", "executor_notes": "", "sections_written": []},
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "executor_note": ""},
            {"id": "SC9", "task_id": "T9", "executor_note": ""},
        ],
    }
    stance = {
        "challenge_engaged": "I engaged the challenge directly.",
        "angle_taken": "I chose a narrow image.",
        "what_changed": "I removed the summary.",
    }
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [
                {
                    "task_id": "T9",
                    "status": "done",
                    "executor_notes": "wrote an undispatched section",
                    "sections_written": ["off_scope"],
                    "stance": stance,
                    "stop_signal": {"requested": False, "defense": ""},
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC9", "executor_note": "off-scope acknowledgment"}
            ],
        },
        batch_task_ids=["T1"],
        batch_sense_check_ids=["SC1"],
        issues=issues,
        mode="creative",
    )

    assert merged == (0, 1, 0, 1)
    assert finalize_data["tasks"][1]["status"] == "pending"
    assert finalize_data["sense_checks"][1]["executor_note"] == ""
    assert any("unknown task_id 'T9'" in issue for issue in issues)
    assert any("unknown sense_check_id 'SC9'" in issue for issue in issues)


def _finalize_payload() -> dict[str, object]:
    return {
        "tasks": [
            {"id": "T1", "status": "pending", "executor_notes": "", "files_changed": [], "commands_run": []},
            {"id": "T2", "status": "pending", "executor_notes": "", "files_changed": [], "commands_run": []},
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "executor_note": ""},
            {"id": "SC2", "task_id": "T2", "executor_note": ""},
        ],
    }


def test_reconcile_uses_selected_artifacts_proven_scope(tmp_path: Path) -> None:
    finalize_data = _finalize_payload()
    (tmp_path / "finalize.json").write_text(json.dumps(finalize_data), encoding="utf-8")
    scope = BatchScope.create(batch_number=2, task_ids=["T2"], sense_check_ids=["SC2"])
    artifact = execute_batch_artifact_path(tmp_path, 2, scope.task_ids)
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                BATCH_SCOPE_KEY: scope.to_dict(),
                "task_updates": [
                    {"task_id": "T1", "status": "done", "executor_notes": "off scope", "files_changed": [], "commands_run": []},
                    {"task_id": "T2", "status": "done", "executor_notes": "proven", "files_changed": [], "commands_run": []},
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "off scope"},
                    {"sense_check_id": "SC2", "executor_note": "proven"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_latest_execution_batch(tmp_path, {"config": {"mode": "code"}})

    saved = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in saved["tasks"]}
    checks = {check["id"]: check for check in saved["sense_checks"]}
    assert result["reconciled"] is True
    assert result["total_task_count"] == 1
    assert result["total_sense_check_count"] == 1
    assert tasks["T1"]["status"] == "pending"
    assert tasks["T2"]["status"] == "done"
    assert checks["SC1"]["executor_note"] == ""
    assert checks["SC2"]["executor_note"] == "proven"


def test_reconcile_quarantines_legacy_artifact_with_source_path(tmp_path: Path) -> None:
    finalize_data = _finalize_payload()
    finalize_path = tmp_path / "finalize.json"
    original = json.dumps(finalize_data)
    finalize_path.write_text(original, encoding="utf-8")
    artifact = tmp_path / "execution_batch_1.json"
    artifact.write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "T1", "status": "done", "executor_notes": "legacy", "files_changed": [], "commands_run": []}
                ]
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_latest_execution_batch(tmp_path, {"config": {"mode": "code"}})

    assert result["reconciled"] is False
    assert result["authority_status"] == "quarantined"
    assert result["artifact_path"] == str(artifact)
    assert result["quarantine"]["reason"] == "missing_batch_scope"
    assert result["quarantine"]["source_path"] == str(artifact)
    assert json.loads(finalize_path.read_text(encoding="utf-8")) == finalize_data
    events = (tmp_path / "events.ndjson").read_text(encoding="utf-8")
    assert "authority_divergence" in events
    assert str(artifact) in events
