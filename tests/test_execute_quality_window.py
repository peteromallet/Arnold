"""Tests for milestone-window and carry-forward filtering in quality.py producers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan.execute.quality import (
    _auto_attribute_unclaimed_paths,
    _observe_git_changes,
)


def _make_finalize(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"tasks": tasks}


def _make_done_task(task_id: str, files: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "done",
        "executor_notes": "did the work",
        "files_changed": files or [],
        "commands_run": ["pytest"],
    }


# ---------------------------------------------------------------------------
# _observe_git_changes — carry-forward filtering
# ---------------------------------------------------------------------------


def test_observe_git_changes_no_filtering_without_carry_forward(tmp_path: Path) -> None:
    before: dict[str, str] = {}
    after: dict[str, str] = {"new_file.py": "hash1"}
    payload: dict[str, Any] = {"files_changed": []}

    def capture_fn(p: Path):  # type: ignore[override]
        return after, None

    issues = _observe_git_changes(
        project_dir=tmp_path,
        payload=payload,
        before_snapshot=before,
        before_error=None,
        batch_number=1,
        batches_total=1,
        capture_git_status_snapshot_fn=capture_fn,
    )
    assert any("unclaimed" in i for i in issues)
    assert any("new_file.py" in i for i in issues)


def test_observe_git_changes_carry_forward_excluded_from_unclaimed(tmp_path: Path) -> None:
    before: dict[str, str] = {}
    after: dict[str, str] = {"carried.py": "hash_cf", "new_file.py": "hash1"}
    payload: dict[str, Any] = {"files_changed": []}

    def capture_fn(p: Path):  # type: ignore[override]
        return after, None

    issues = _observe_git_changes(
        project_dir=tmp_path,
        payload=payload,
        before_snapshot=before,
        before_error=None,
        batch_number=1,
        batches_total=1,
        capture_git_status_snapshot_fn=capture_fn,
        carry_forward_paths={"carried.py"},
    )
    # carried.py must NOT appear as unclaimed
    unclaimed_issues = [i for i in issues if "unclaimed" in i]
    assert not any("carried.py" in i for i in unclaimed_issues)
    # carried.py should be reported as carry-forward advisory
    assert any("carry-forward" in i and "carried.py" in i for i in issues)
    # new_file.py is still reported as unclaimed
    assert any("unclaimed" in i and "new_file.py" in i for i in issues)


def test_observe_git_changes_all_carry_forward_no_unclaimed_message(tmp_path: Path) -> None:
    before: dict[str, str] = {}
    after: dict[str, str] = {"carried.py": "hash_cf"}
    payload: dict[str, Any] = {"files_changed": []}

    def capture_fn(p: Path):  # type: ignore[override]
        return after, None

    issues = _observe_git_changes(
        project_dir=tmp_path,
        payload=payload,
        before_snapshot=before,
        before_error=None,
        batch_number=1,
        batches_total=1,
        capture_git_status_snapshot_fn=capture_fn,
        carry_forward_paths={"carried.py"},
    )
    # No "unclaimed" advisory — only the carry-forward note
    assert not any("unclaimed" in i for i in issues)
    assert any("carry-forward" in i for i in issues)


def test_observe_git_changes_milestone_base_sha_accepted(tmp_path: Path) -> None:
    """milestone_base_sha param is accepted without error (even if unused in snapshot path)."""
    before: dict[str, str] = {}
    after: dict[str, str] = {}
    payload: dict[str, Any] = {"files_changed": []}

    def capture_fn(p: Path):  # type: ignore[override]
        return after, None

    issues = _observe_git_changes(
        project_dir=tmp_path,
        payload=payload,
        before_snapshot=before,
        before_error=None,
        batch_number=1,
        batches_total=1,
        capture_git_status_snapshot_fn=capture_fn,
        milestone_base_sha="abc123",
    )
    assert issues == []


# ---------------------------------------------------------------------------
# _auto_attribute_unclaimed_paths — carry-forward filtering
# ---------------------------------------------------------------------------


def test_auto_attribute_skips_carry_forward_paths(tmp_path: Path) -> None:
    task = {"id": "T1", "status": "done", "executor_notes": "done", "files_changed": [], "commands_run": []}
    finalize = _make_finalize([task])
    payload: dict[str, Any] = {"files_changed": [], "task_updates": [{"task_id": "T1", "status": "done"}]}

    # Snapshot returns carried.py as the only dirty file
    def capture_fn(p: Path):  # type: ignore[override]
        return {"carried.py": "hashcf"}, None

    issues: list[str] = []
    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize,
        payload=payload,
        batch_task_ids=["T1"],
        issues=issues,
        capture_recursive_snapshot_fn=capture_fn,
        carry_forward_paths={"carried.py"},
    )
    # carried.py should NOT be auto-attributed to T1
    assert result.records == []
    attributed = task.get("files_changed") or []
    assert "carried.py" not in attributed


def test_auto_attribute_attributes_non_carry_forward_paths(tmp_path: Path) -> None:
    task = {"id": "T1", "status": "done", "executor_notes": "done", "files_changed": [], "commands_run": []}
    finalize = _make_finalize([task])
    payload: dict[str, Any] = {"files_changed": [], "task_updates": [{"task_id": "T1", "status": "done"}]}

    def capture_fn(p: Path):  # type: ignore[override]
        return {"carried.py": "hashcf", "new_work.py": "hashnew"}, None

    issues: list[str] = []
    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize,
        payload=payload,
        batch_task_ids=["T1"],
        issues=issues,
        capture_recursive_snapshot_fn=capture_fn,
        carry_forward_paths={"carried.py"},
    )
    # new_work.py is attributed; carried.py is not
    assert result.records
    assert "new_work.py" in (result.records[0].get("files") or [])
    assert "carried.py" not in (result.records[0].get("files") or [])
