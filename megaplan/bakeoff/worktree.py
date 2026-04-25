"""Git worktree lifecycle helpers for bake-offs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from megaplan._core.io import atomic_write_json, now_utc
from megaplan.types import CliError


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("bakeoff_git_failed", str(exc)) from exc


def _git_error_detail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip() or "git command failed"


def capture_base_sha(repo: Path) -> str:
    result = _git(repo, ["rev-parse", "HEAD"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    return result.stdout.strip()


def create_worktree(repo: Path, target: Path, base_sha: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "--detach", str(target), base_sha],
    )
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))


def remove_worktree(target: Path, force: bool = True) -> None:
    if not target.exists():
        return
    repo = _main_worktree_for(target)
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target))
    result = _git(repo, args)
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    _remove_empty_parent(target.parent)


def mark_crashed(target: Path, reason: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        target / "BAKEOFF_CRASHED",
        {
            "reason": reason,
            "ts": now_utc(),
            "pid": os.getpid(),
        },
    )


def ensure_main_worktree_clean(repo: Path, *, allow_dirty: bool = False) -> None:
    if allow_dirty:
        return
    result = _git(repo, ["status", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    if result.stdout.strip():
        raise CliError(
            "bakeoff_dirty_worktree",
            "main worktree is dirty; run `git status` or pass --allow-dirty.",
        )


def _main_worktree_for(target: Path) -> Path:
    result = _git(target, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")).resolve()
    raise CliError("bakeoff_worktree_failed", "could not locate main worktree")


def _remove_empty_parent(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
