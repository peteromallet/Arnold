from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan.execute.merge import TERMINAL_TASK_STATUSES, _validate_and_merge_batch


def _merge_task_update(
    tmp_path: Path,
    monkeypatch: Any,
    *,
    task_update: dict[str, Any],
    deviations: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    monkeypatch.chdir(tmp_path)
    task = {
        "id": task_update["task_id"],
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
    }
    issues = list(deviations or [])
    _validate_and_merge_batch(
        [task_update],
        required_fields=("task_id", "status", "executor_notes", "files_changed", "commands_run"),
        targets_by_id={task["id"]: task},
        id_field="task_id",
        merge_fields=("status", "executor_notes", "files_changed", "commands_run"),
        issues=issues,
        validation_label="task_updates",
        merge_label="task_update",
        enum_fields={"status": set(TERMINAL_TASK_STATUSES)},
        nonempty_fields={"executor_notes"},
        array_fields=("files_changed", "commands_run"),
    )
    return task, issues


def test_patch_corruption_downgrades_to_blocked(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "some_file.py").write_text("max_tokens=*** encoding=\"utf-8\")")

    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["some_file.py"],
            "commands_run": [],
        },
    )

    assert task["status"] == "blocked"
    assert "patch_corruption" in task["executor_notes"]
    assert any("patch_corruption: some_file.py line 1" in issue for issue in issues)


def test_deviation_phrase_downgrades_to_blocked(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "some_file.py").write_text("max_tokens=*** encoding=\"utf-8\")")

    task, _issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["some_file.py"],
            "commands_run": [],
        },
        deviations=["T1 reported patch artifact: stray ***"],
    )

    assert task["status"] == "blocked"
    assert "status auto-downgraded" in task["executor_notes"]
    assert "patch artifact" in task["executor_notes"]


def test_clean_task_stays_done(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "some_file.py").write_text("print('hello')\n", encoding="utf-8")

    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["some_file.py"],
            "commands_run": [],
        },
    )

    assert task["status"] == "done"
    assert issues == []


def test_non_python_files_skip_ast_check(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "README.md").write_text("# Title\n\nBody.\n", encoding="utf-8")

    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "added docs",
            "files_changed": ["README.md"],
            "commands_run": [],
        },
    )

    assert task["status"] == "done"
    assert issues == []


def test_missing_file_skips_silently(tmp_path: Path, monkeypatch: Any) -> None:
    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["nonexistent.py"],
            "commands_run": [],
        },
    )
    assert task["status"] == "done"
    assert issues == []
