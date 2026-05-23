from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

from megaplan.worktrees import (
    TaskWorktreeLifecycleError,
    make_task_identity,
    prepare_task_worktree,
    read_registry_entries,
)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    plan_dir = repo / ".megaplan" / "plans" / "plan-1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.idea").write_text("idea\n", encoding="utf-8")
    (plan_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (plan_dir / "state.json").write_text('{"phase":"finalized"}\n', encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "Task/Unsafe\nID: trailer"}]}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "final.md").write_text("# Final\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial plan")
    return repo, plan_dir, _git(repo, "rev-parse", "HEAD")


def test_prepare_task_worktree_creates_task_keyed_worktree_context_and_registry(tmp_path: Path) -> None:
    repo, plan_dir, head = _init_repo(tmp_path)
    identity = make_task_identity("Task/Unsafe\nID: trailer")

    record = prepare_task_worktree(repo, plan_dir, "run-9", identity)

    expected_worktree = repo / ".megaplan-worktrees" / "run-9" / f"task-{identity.task_key}"
    assert record.worktree_path == expected_worktree
    assert record.base_ref == "HEAD"
    assert record.base_sha == head
    assert _git(record.worktree_path, "rev-parse", "HEAD") == head
    assert "Task/Unsafe" not in str(record.worktree_path)
    assert "\n" not in str(record.worktree_path)

    assert record.context_dir == record.worktree_path / ".megaplan" / "task-context"
    assert record.worker_dir == record.worktree_path / ".megaplan" / "worker"
    assert record.worker_dir.is_dir()
    assert (record.worker_dir / "scratch.txt").write_text("ok\n", encoding="utf-8") == 3

    copied_names = set(record.copied_context_files)
    assert {"state.idea", "plan.md", "state.json", "finalize.json", "final.md", "task.json"}.issubset(copied_names)
    for relative in copied_names:
        path = record.context_dir / relative
        assert path.exists()
        assert path.stat().st_mode & stat.S_IWUSR == 0

    task_context = json.loads((record.context_dir / "task.json").read_text(encoding="utf-8"))
    assert task_context["task_key"] == identity.task_key
    assert task_context["identity"] == identity.registry_identity()
    assert task_context["base_sha"] == head
    assert "original_task_id" not in task_context["identity"]

    entries = read_registry_entries(repo, "run-9")
    assert [entry["entry_type"] for entry in entries] == [
        "task_worktree_created",
        "task_context_snapshot_created",
    ]
    assert [entry["sequence"] for entry in entries] == [1, 2]
    for entry in entries:
        assert entry["schema_version"] == 2
        assert entry["task_key"] == identity.task_key
        assert "task_id" not in entry
        assert entry["identity"] == identity.registry_identity()
    assert entries[0]["payload"]["worktree_path"] == str(expected_worktree)
    assert entries[0]["payload"]["base_ref"] == "HEAD"
    assert entries[0]["payload"]["base_sha"] == head
    assert entries[1]["payload"]["context_dir"] == str(record.context_dir)
    assert entries[1]["payload"]["worker_dir"] == str(record.worker_dir)
    assert "task.json" in entries[1]["payload"]["copied_context_files"]


def test_prepare_task_worktree_requires_task_identity(tmp_path: Path) -> None:
    repo, plan_dir, _head = _init_repo(tmp_path)

    with pytest.raises(TypeError, match="TaskIdentity"):
        prepare_task_worktree(repo, plan_dir, "run-9", "T9")  # type: ignore[arg-type]


def test_prepare_task_worktree_rejects_existing_task_key_path(tmp_path: Path) -> None:
    repo, plan_dir, _head = _init_repo(tmp_path)
    identity = make_task_identity("T9")

    prepare_task_worktree(repo, plan_dir, "run-9", identity)

    with pytest.raises(TaskWorktreeLifecycleError, match="already exists"):
        prepare_task_worktree(repo, plan_dir, "run-9", identity)
