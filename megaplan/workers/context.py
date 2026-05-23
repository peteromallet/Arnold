"""Explicit worker execution context for task-native execute runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from megaplan.worktrees import validate_task_key


@dataclass(frozen=True)
class WorkerExecutionContext:
    """Task-local worker paths for execute dispatch.

    Non-execute phases keep using the global work-dir resolution. Execute can
    pass this context to force the subprocess/tool sandbox into the task
    worktree and keep prompts, outputs, and worker state under
    ``.megaplan/worker`` in that worktree.
    """

    task_id: str
    task_key: str
    worktree_dir: Path
    task_context_dir: Path
    worker_dir: Path

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id:
            raise ValueError("task_id must be a non-empty string")
        object.__setattr__(self, "task_key", validate_task_key(self.task_key))
        object.__setattr__(self, "worktree_dir", Path(self.worktree_dir))
        object.__setattr__(self, "task_context_dir", Path(self.task_context_dir))
        object.__setattr__(self, "worker_dir", Path(self.worker_dir))

    def ensure_worker_dir(self) -> Path:
        self.worker_dir.mkdir(parents=True, exist_ok=True)
        return self.worker_dir

    def output_path(self, agent: str, step: str, suffix: str = "json") -> Path:
        return self.ensure_worker_dir() / f"{step}_{agent}_output.{suffix}"

    def prompt_path(self, step: str, agent: str) -> Path:
        return self.ensure_worker_dir() / f"{step}_{agent}_prompt.txt"
