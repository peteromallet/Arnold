"""Generic git worktree primitives for AgentBox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


class GitWorktreeError(RuntimeError):
    """Raised when a git command or worktree precondition fails."""


@dataclass(frozen=True)
class GitResult:
    """Completed git invocation details."""

    argv: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class WorktreeInfo:
    """One entry from ``git worktree list --porcelain``."""

    path: Path
    head: str | None = None
    branch_ref: str | None = None
    detached: bool = False
    bare: bool = False
    prunable_reason: str | None = None

    @property
    def branch_name(self) -> str | None:
        if self.branch_ref and self.branch_ref.startswith("refs/heads/"):
            return self.branch_ref.removeprefix("refs/heads/")
        return None


@dataclass(frozen=True)
class GitOperationStatus:
    """Current in-progress git operation markers for one checkout."""

    in_progress: bool
    markers: tuple[str, ...]


@dataclass(frozen=True)
class GitDirtyStatus:
    """Current dirty-path summary for one checkout."""

    is_dirty: bool
    entries: tuple[str, ...]


def git(
    cwd: Path | str,
    *args: str,
    check: bool = True,
) -> GitResult:
    """Run git with argv-list construction and captured text output."""

    path = Path(cwd)
    argv = ("git", *args)
    completed = subprocess.run(
        argv,
        cwd=path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = GitResult(
        argv=argv,
        cwd=path,
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
    if check and completed.returncode != 0:
        reason = result.stderr or result.stdout or f"git exited {completed.returncode}"
        raise GitWorktreeError(reason)
    return result


def resolve_ref(repo_path: Path | str, ref: str) -> str:
    """Resolve ``ref`` to a commit SHA."""

    return git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout


def ref_exists(repo_path: Path | str, ref: str) -> bool:
    """Return true when ``ref`` resolves to any git reference."""

    return _show_ref_exists(repo_path, ref)


def has_local_branch(repo_path: Path | str, branch: str) -> bool:
    """Return true when ``branch`` exists under ``refs/heads``."""

    return _show_ref_exists(repo_path, f"refs/heads/{branch}")


def has_remote_tracking_ref(repo_path: Path | str, ref: str) -> bool:
    """Return true when ``ref`` exists under ``refs/remotes``."""

    remote_ref = ref if ref.startswith("refs/remotes/") else f"refs/remotes/{ref}"
    return _show_ref_exists(repo_path, remote_ref)


def commit_exists(repo_path: Path | str, ref: str) -> bool:
    """Return true when ``ref`` resolves to a commit object."""

    return (
        git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False).returncode
        == 0
    )


def parse_worktree_porcelain(output: str) -> tuple[WorktreeInfo, ...]:
    """Parse ``git worktree list --porcelain`` output."""

    records: list[WorktreeInfo] = []
    current: dict[str, object] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            _append_worktree_record(records, current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                _append_worktree_record(records, current)
            current = {"path": Path(value)}
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch_ref"] = value
        elif key == "detached":
            current["detached"] = True
        elif key == "bare":
            current["bare"] = True
        elif key == "prunable":
            current["prunable_reason"] = value or None
    _append_worktree_record(records, current)
    return tuple(records)


def list_worktrees(repo_path: Path | str) -> tuple[WorktreeInfo, ...]:
    """Return registered worktrees for ``repo_path`` from git porcelain output."""

    return parse_worktree_porcelain(
        git(repo_path, "worktree", "list", "--porcelain").stdout
    )


def is_registered_worktree(repo_path: Path | str, path: Path | str) -> bool:
    """Return true when ``path`` is present in git's registered worktree list."""

    target = Path(path).resolve()
    return any(worktree.path.resolve() == target for worktree in list_worktrees(repo_path))


def checked_out_branch_worktree(
    repo_path: Path | str,
    branch: str,
) -> WorktreeInfo | None:
    """Return the worktree that currently has local ``branch`` checked out."""

    for worktree in list_worktrees(repo_path):
        if worktree.branch_name == branch:
            return worktree
    return None


def git_operation_status(repo_path: Path | str) -> GitOperationStatus:
    """Detect common in-progress git operations without modifying state."""

    git_dir = Path(git(repo_path, "rev-parse", "--git-dir").stdout)
    if not git_dir.is_absolute():
        git_dir = Path(repo_path) / git_dir
    markers = tuple(
        name
        for name in (
            "rebase-merge",
            "rebase-apply",
            "MERGE_HEAD",
            "CHERRY_PICK_HEAD",
            "REVERT_HEAD",
            "BISECT_LOG",
        )
        if (git_dir / name).exists()
    )
    return GitOperationStatus(in_progress=bool(markers), markers=markers)


def git_dirty_status(repo_path: Path | str) -> GitDirtyStatus:
    """Return tracked/untracked dirty entries from ``git status --porcelain``."""

    completed = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    entries = tuple(line for line in completed.stdout.splitlines() if line.strip())
    return GitDirtyStatus(is_dirty=bool(entries), entries=entries)


def create_branch_worktree(
    repo_path: Path | str,
    worktree_path: Path | str,
    branch: str,
    start_point: str,
) -> WorktreeInfo:
    """Create a worktree with a new local branch at ``start_point``."""

    git(repo_path, "worktree", "add", "-b", branch, str(worktree_path), start_point)
    return _lookup_registered_worktree(repo_path, worktree_path)


def attach_existing_local_branch(
    repo_path: Path | str,
    worktree_path: Path | str,
    branch: str,
) -> WorktreeInfo:
    """Attach ``worktree_path`` to an existing local branch."""

    if not has_local_branch(repo_path, branch):
        raise GitWorktreeError(f"local branch does not exist: {branch}")
    git(repo_path, "worktree", "add", str(worktree_path), branch)
    return _lookup_registered_worktree(repo_path, worktree_path)


def _show_ref_exists(repo_path: Path | str, ref: str) -> bool:
    return git(repo_path, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 0


def _append_worktree_record(
    records: list[WorktreeInfo],
    current: dict[str, object],
) -> None:
    path = current.get("path")
    if not isinstance(path, Path):
        return
    records.append(
        WorktreeInfo(
            path=path,
            head=current.get("head") if isinstance(current.get("head"), str) else None,
            branch_ref=(
                current.get("branch_ref")
                if isinstance(current.get("branch_ref"), str)
                else None
            ),
            detached=bool(current.get("detached", False)),
            bare=bool(current.get("bare", False)),
            prunable_reason=(
                current.get("prunable_reason")
                if isinstance(current.get("prunable_reason"), str)
                else None
            ),
        )
    )


def _lookup_registered_worktree(
    repo_path: Path | str,
    worktree_path: Path | str,
) -> WorktreeInfo:
    target = Path(worktree_path).resolve()
    for worktree in list_worktrees(repo_path):
        if worktree.path.resolve() == target:
            return worktree
    raise GitWorktreeError(f"worktree was not registered: {target}")


__all__ = [
    "GitDirtyStatus",
    "GitOperationStatus",
    "GitResult",
    "GitWorktreeError",
    "WorktreeInfo",
    "attach_existing_local_branch",
    "checked_out_branch_worktree",
    "commit_exists",
    "create_branch_worktree",
    "git",
    "git_dirty_status",
    "git_operation_status",
    "has_local_branch",
    "has_remote_tracking_ref",
    "is_registered_worktree",
    "list_worktrees",
    "parse_worktree_porcelain",
    "ref_exists",
    "resolve_ref",
]
