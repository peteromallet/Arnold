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
    (tmp_path / "some_file.py").write_text("max_tokens = ***\n", encoding="utf-8")

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
    (tmp_path / "some_file.py").write_text("max_tokens = 1\n", encoding="utf-8")

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
    (tmp_path / "some_file.py").write_text("max_tokens = 1\n", encoding="utf-8")

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
    (tmp_path / "README.md").write_text("max_tokens = ***\n", encoding="utf-8")

    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
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
            "files_changed": ["deleted.py"],
            "commands_run": [],
        },
    )

    assert task["status"] == "done"
    assert issues == []


def test_fixed_syntax_error_prose_does_not_block_when_file_parses(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / "some_file.py").write_text("import os as _os\n", encoding="utf-8")

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
        deviations=["T1 had a double-`as` syntax error in the import; fixed it"],
    )

    assert task["status"] == "done"


def test_real_syntax_error_in_file_still_blocks_via_ast(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")

    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["broken.py"],
            "commands_run": [],
        },
    )

    assert task["status"] == "blocked"
    assert any("patch_corruption" in issue for issue in issues)
