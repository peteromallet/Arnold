from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.skip("archived legacy runtime; active merge coverage lives under tests/execute", allow_module_level=True)

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


# ---------------------------------------------------------------------------
# T3: three-way drift test + alias acceptance via shared status_constants
# ---------------------------------------------------------------------------


def test_three_way_drift_value_aliases_match_status_constants() -> None:
    """merge._VALUE_ALIASES["status"] must equal EXECUTE_TASK_STATUS_ALIASES —
    the three consumers (merge, status_constants, model_seam capture) must
    share the same alias map."""
    from arnold.pipelines.megaplan.execute.merge import _VALUE_ALIASES
    from arnold.pipelines.megaplan.execute.status_constants import EXECUTE_TASK_STATUS_ALIASES

    assert _VALUE_ALIASES["status"] == EXECUTE_TASK_STATUS_ALIASES
    # Confirming the identity of the full map
    assert _VALUE_ALIASES["status"] == {
        "completed": "done",
        "complete": "done",
        "skip": "skipped",
        "verified": "done",
    }


def test_three_way_drift_model_seam_normalizer_matches_status_constants() -> None:
    """model_seam's capture normalization delegates to the same
    normalize_execute_task_status that status_constants exports."""
    from arnold.pipelines.megaplan.execute.status_constants import (
        EXECUTE_TASK_STATUS_ALIASES,
        normalize_execute_task_status,
    )

    for alias, canonical in EXECUTE_TASK_STATUS_ALIASES.items():
        assert normalize_execute_task_status(alias) == canonical


def test_merge_accepts_verified_as_done(tmp_path: Path, monkeypatch: Any) -> None:
    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T1",
            "status": "verified",
            "executor_notes": "checked",
            "files_changed": [],
            "commands_run": [],
        },
    )
    assert task["status"] == "done"
    assert issues == []


def test_merge_accepts_completed_as_done(tmp_path: Path, monkeypatch: Any) -> None:
    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T2",
            "status": "completed",
            "executor_notes": "done earlier",
            "files_changed": [],
            "commands_run": [],
        },
    )
    assert task["status"] == "done"
    assert issues == []


def test_merge_accepts_complete_as_done(tmp_path: Path, monkeypatch: Any) -> None:
    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T3",
            "status": "complete",
            "executor_notes": "all done",
            "files_changed": [],
            "commands_run": [],
        },
    )
    assert task["status"] == "done"
    assert issues == []


def test_merge_accepts_skip_as_skipped(tmp_path: Path, monkeypatch: Any) -> None:
    task, issues = _merge_task_update(
        tmp_path,
        monkeypatch,
        task_update={
            "task_id": "T4",
            "status": "skip",
            "executor_notes": "not needed",
            "files_changed": [],
            "commands_run": [],
        },
    )
    assert task["status"] == "skipped"
    assert issues == []


def test_merge_field_aliases_untouched() -> None:
    """_FIELD_ALIASES at merge.py:38-45 must be preserved completely unchanged."""
    from arnold.pipelines.megaplan.execute.merge import _FIELD_ALIASES

    assert _FIELD_ALIASES == {
        "task_id": ("id", "taskId", "task"),
        "sense_check_id": ("id", "senseCheckId", "check_id"),
        "executor_notes": ("notes", "executor_note", "note"),
        "executor_note": ("notes", "executor_notes", "note"),
        "concern": ("summary", "description", "issue", "finding"),
        "evidence": ("detail", "details", "explanation", "reasoning"),
    }


def test_merge_terminal_task_statuses_matches_status_constants() -> None:
    """TERMINAL_TASK_STATUSES in merge must be the same object as in status_constants."""
    from arnold.pipelines.megaplan.execute.merge import TERMINAL_TASK_STATUSES as merge_tts
    from arnold.pipelines.megaplan.execute.status_constants import TERMINAL_TASK_STATUSES as sc_tts

    assert merge_tts is sc_tts
    assert merge_tts == frozenset({"done", "skipped", "completed", "blocked"})
