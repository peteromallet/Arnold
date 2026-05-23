"""Centralized project-level custody paths for worktree execute substrate."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from megaplan._core import atomic_write_text
from .identity import validate_task_key

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
MEGAPLAN_WORKTREES_IGNORE_ENTRY = ".megaplan-worktrees/"


def validate_run_id(run_id: str) -> str:
    """Return a custody-safe run id or raise ValueError."""
    return _validate_id(run_id, label="run_id", pattern=_RUN_ID_RE)


def validate_task_id(task_id: str) -> str:
    """Return a custody-safe legacy task id or task key."""
    return _validate_id(task_id, label="task_id", pattern=_TASK_ID_RE)


def _validate_id(value: str, *, label: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not pattern.fullmatch(value):
        raise ValueError(
            f"{label} must match [A-Za-z0-9][A-Za-z0-9_-]{{0,79}}"
        )
    return value


@dataclass(frozen=True)
class CustodyPaths:
    """Path layout for project-level worktree custody state."""

    project_dir: Path

    @property
    def project_root(self) -> Path:
        return self.project_dir.resolve()

    @property
    def custody_root(self) -> Path:
        return self.project_root / ".megaplan" / "worktrees"

    @property
    def registry_dir(self) -> Path:
        return self.custody_root / "registry"

    @property
    def patches_dir(self) -> Path:
        return self.custody_root / "patches"

    @property
    def reports_dir(self) -> Path:
        return self.custody_root / "custody-reports"

    @property
    def secrets_dir(self) -> Path:
        return self.custody_root / "secrets"

    @property
    def scratch_worktrees_dir(self) -> Path:
        return self.project_root / ".megaplan-worktrees"

    def registry_jsonl(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.registry_dir / f"{run_id}.jsonl"

    def registry_head(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.registry_dir / f"{run_id}.head.json"

    def registry_lock(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.registry_dir / f"{run_id}.lock"

    def patch_run_dir(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.patches_dir / run_id

    def patch_task_dir(self, run_id: str, task_id: str) -> Path:
        task_id = validate_task_id(task_id)
        return self.patch_run_dir(run_id) / f"task-{task_id}"

    def patch_manifest(self, run_id: str, task_id: str) -> Path:
        return self.patch_task_dir(run_id, task_id) / "manifest.json"

    def patch_payload(self, run_id: str, task_id: str) -> Path:
        return self.patch_task_dir(run_id, task_id) / "bundle.patch"

    def custody_report(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.custody_report_dir(run_id) / "report.json"

    def custody_report_dir(self, run_id: str) -> Path:
        run_id = validate_run_id(run_id)
        return self.reports_dir / run_id

    def secret_scan_report(self, run_id: str, task_id: str) -> Path:
        task_id = validate_task_id(task_id)
        return self.secrets_dir / validate_run_id(run_id) / f"task-{task_id}.json"

    def scratch_worktree(self, run_id: str, task_id: str) -> Path:
        task_id = validate_task_id(task_id)
        return self.scratch_worktrees_dir / validate_run_id(run_id) / f"task-{task_id}"

    def scratch_task_worktree(self, run_id: str, task_key: str) -> Path:
        task_key = validate_task_key(task_key)
        return self.scratch_worktrees_dir / validate_run_id(run_id) / f"task-{task_key}"


def custody_paths(project_dir: str | Path) -> CustodyPaths:
    return CustodyPaths(project_dir=Path(project_dir))


def scratch_worktree_root_path(project_dir: str | Path) -> Path:
    return custody_paths(project_dir).scratch_worktrees_dir


def scratch_worktree_path(project_dir: str | Path, run_id: str, task_id: str) -> Path:
    return custody_paths(project_dir).scratch_worktree(run_id, task_id)


def scratch_task_worktree_path(project_dir: str | Path, run_id: str, task_key: str) -> Path:
    return custody_paths(project_dir).scratch_task_worktree(run_id, task_key)


def ensure_megaplan_worktrees_ignored(project_root: str | Path) -> Path:
    """Idempotently add the project-owned worktree scratch dir to .gitignore."""
    root = Path(project_root).expanduser().resolve()
    gitignore = root / ".gitignore"
    try:
        existing = gitignore.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    lines = existing.splitlines()
    if MEGAPLAN_WORKTREES_IGNORE_ENTRY in {line.strip() for line in lines}:
        return gitignore
    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"{MEGAPLAN_WORKTREES_IGNORE_ENTRY}\n"
    atomic_write_text(gitignore, content)
    return gitignore
