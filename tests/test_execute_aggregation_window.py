"""Tests for milestone-window and carry-forward filtering in _compute_execute_scope_drift."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from megaplan.execute.aggregation import _compute_execute_scope_drift


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


def _setup_git_repo(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)


def _commit_file(tmp_path: Path, name: str, content: str = "x") -> None:
    (tmp_path / name).write_text(content)
    _git(["add", name], tmp_path)
    _git(["commit", "-m", f"add {name}"], tmp_path)


def _head_sha(tmp_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Window filtering: pre-base committed files excluded, in-window files included
# ---------------------------------------------------------------------------


def test_scope_drift_excludes_pre_base_committed_file(tmp_path: Path) -> None:
    _setup_git_repo(tmp_path)

    # C0: initial commit
    _commit_file(tmp_path, "README.md", "readme")

    # C1: pre-milestone commit
    _commit_file(tmp_path, "pre_milestone.py", "pre")

    # milestone_base_sha = C1 (the start of the current milestone)
    milestone_base_sha = _head_sha(tmp_path)

    # C2: in-window commit (work done during this milestone)
    _commit_file(tmp_path, "in_window.py", "new")

    state: dict[str, Any] = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "meta": {"chain_policy": {"milestone_base_sha": milestone_base_sha}},
    }
    aggregate_payload: dict[str, Any] = {"files_changed": [], "task_updates": []}

    drift = _compute_execute_scope_drift(tmp_path, aggregate_payload, state=state)

    # pre_milestone.py was committed before the milestone base — must NOT appear
    assert "pre_milestone.py" not in drift.files_added
    # in_window.py is in-window and unclaimed — must appear
    assert "in_window.py" in drift.files_added


def test_scope_drift_no_base_sha_uses_git_status_only(tmp_path: Path) -> None:
    _setup_git_repo(tmp_path)
    _commit_file(tmp_path, "README.md", "readme")

    # Dirty (uncommitted) file
    (tmp_path / "dirty.py").write_text("dirty")
    _git(["add", "dirty.py"], tmp_path)

    state: dict[str, Any] = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "meta": {},
    }
    aggregate_payload: dict[str, Any] = {"files_changed": [], "task_updates": []}

    drift = _compute_execute_scope_drift(tmp_path, aggregate_payload, state=state)
    # Staged dirty.py appears in scope drift (no milestone window filter applied)
    assert "dirty.py" in drift.files_added


# ---------------------------------------------------------------------------
# Carry-forward filtering: carried files excluded from scope drift
# ---------------------------------------------------------------------------


def test_scope_drift_excludes_carry_forward_files(tmp_path: Path) -> None:
    _setup_git_repo(tmp_path)
    _commit_file(tmp_path, "README.md", "readme")

    milestone_base_sha = _head_sha(tmp_path)

    # In-window commits
    _commit_file(tmp_path, "carried.py", "cf")
    _commit_file(tmp_path, "in_window.py", "new")

    state: dict[str, Any] = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "meta": {
            "chain_policy": {
                "milestone_base_sha": milestone_base_sha,
                "carry_forward_manifest": {"carried.py": {"source": "milestone_0"}},
            }
        },
    }
    aggregate_payload: dict[str, Any] = {"files_changed": [], "task_updates": []}

    drift = _compute_execute_scope_drift(tmp_path, aggregate_payload, state=state)

    # carried.py is in carry-forward manifest — must NOT block
    assert "carried.py" not in drift.files_added
    # in_window.py is in-window and unclaimed — must appear
    assert "in_window.py" in drift.files_added


def test_scope_drift_carry_forward_list_form(tmp_path: Path) -> None:
    _setup_git_repo(tmp_path)
    _commit_file(tmp_path, "README.md", "readme")

    milestone_base_sha = _head_sha(tmp_path)
    _commit_file(tmp_path, "carried.py", "cf")

    state: dict[str, Any] = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "meta": {
            "chain_policy": {
                "milestone_base_sha": milestone_base_sha,
                "carry_forward_manifest": ["carried.py"],
            }
        },
    }
    aggregate_payload: dict[str, Any] = {"files_changed": [], "task_updates": []}

    drift = _compute_execute_scope_drift(tmp_path, aggregate_payload, state=state)
    assert "carried.py" not in drift.files_added
