"""Task-native scratch worktree lifecycle helpers."""

from __future__ import annotations

import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from megaplan._core import atomic_write_json

from .identity import TaskIdentity
from .paths import custody_paths, ensure_megaplan_worktrees_ignored, validate_run_id
from .registry import append_registry_entry

DEFAULT_CONTEXT_FILES = (
    "state.idea",
    "plan.md",
    "plan_v1.meta.json",
    "state.json",
    "finalize.json",
    "final.md",
    "execution.json",
)


class TaskWorktreeLifecycleError(RuntimeError):
    """Raised when a task scratch worktree cannot be prepared safely."""


@dataclass(frozen=True)
class TaskWorktreeRecord:
    """Prepared task-local worktree and context snapshot locations."""

    run_id: str
    identity: TaskIdentity
    base_ref: str
    base_sha: str
    worktree_path: Path
    context_dir: Path
    worker_dir: Path
    copied_context_files: tuple[str, ...]
    registry_entries: tuple[dict[str, Any], ...]


def prepare_task_worktree(
    project_dir: str | Path,
    plan_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    *,
    base_ref: str = "HEAD",
    context_files: Iterable[str] = DEFAULT_CONTEXT_FILES,
) -> TaskWorktreeRecord:
    """Create a task-keyed scratch worktree and task-local context snapshot."""
    if not isinstance(identity, TaskIdentity):
        raise TypeError("identity must be a TaskIdentity")
    run_id = validate_run_id(run_id)
    project_root = Path(project_dir).expanduser().resolve()
    source_plan_dir = Path(plan_dir).expanduser().resolve()
    if not source_plan_dir.is_dir():
        raise TaskWorktreeLifecycleError(f"plan_dir does not exist: {source_plan_dir}")

    paths = custody_paths(project_root)
    worktree_path = paths.scratch_task_worktree(run_id, identity.task_key)
    if worktree_path.exists():
        raise TaskWorktreeLifecycleError(f"task worktree already exists: {worktree_path}")

    base_sha = _git(project_root, "rev-parse", base_ref)
    ensure_megaplan_worktrees_ignored(project_root)
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(project_root, "worktree", "add", "--detach", str(worktree_path), base_sha)

    context_dir = worktree_path / ".megaplan" / "task-context"
    worker_dir = worktree_path / ".megaplan" / "worker"
    copied_files = _copy_read_only_context(
        source_plan_dir,
        context_dir,
        context_files=context_files,
        run_id=run_id,
        identity=identity,
        base_ref=base_ref,
        base_sha=base_sha,
    )
    worker_dir.mkdir(parents=True, exist_ok=True)

    entries = (
        append_registry_entry(
            project_root,
            run_id,
            "task_worktree_created",
            {
                "worktree_path": str(worktree_path),
                "worktree": str(worktree_path),
                "base_ref": base_ref,
                "base_sha": base_sha,
            },
            identity=identity,
        ),
        append_registry_entry(
            project_root,
            run_id,
            "task_context_snapshot_created",
            {
                "context_dir": str(context_dir),
                "worker_dir": str(worker_dir),
                "copied_context_files": list(copied_files),
                "base_ref": base_ref,
                "base_sha": base_sha,
            },
            identity=identity,
        ),
    )
    return TaskWorktreeRecord(
        run_id=run_id,
        identity=identity,
        base_ref=base_ref,
        base_sha=base_sha,
        worktree_path=worktree_path,
        context_dir=context_dir,
        worker_dir=worker_dir,
        copied_context_files=copied_files,
        registry_entries=entries,
    )


def _copy_read_only_context(
    source_plan_dir: Path,
    context_dir: Path,
    *,
    context_files: Iterable[str],
    run_id: str,
    identity: TaskIdentity,
    base_ref: str,
    base_sha: str,
) -> tuple[str, ...]:
    context_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for relative in context_files:
        source = _safe_context_source(source_plan_dir, relative)
        if not source.exists() or not source.is_file():
            continue
        target = context_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        _make_read_only(target)
        copied.append(relative)

    metadata_path = context_dir / "task.json"
    metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "task_key": identity.task_key,
        "identity": identity.registry_identity(),
        "base_ref": base_ref,
        "base_sha": base_sha,
        "copied_context_files": copied,
    }
    atomic_write_json(metadata_path, metadata)
    _make_read_only(metadata_path)
    return tuple(copied + ["task.json"])


def _safe_context_source(source_plan_dir: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("context file paths must be non-empty relative strings")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"context file path must stay inside plan_dir: {relative}")
    return source_plan_dir / path


def _make_read_only(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise TaskWorktreeLifecycleError(message)
    return result.stdout.strip()
