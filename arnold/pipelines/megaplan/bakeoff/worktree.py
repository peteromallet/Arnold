"""Git worktree lifecycle helpers for bake-offs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from arnold.pipelines.megaplan._core.io import atomic_write_json, now_utc
from arnold.pipelines.megaplan.types import CliError


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


# ---- Shared primitives (used by --in-worktree on `megaplan init` too) ----

_WORKTREE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_worktree_name(name: str) -> str:
    if not isinstance(name, str) or not _WORKTREE_NAME_RE.match(name):
        raise CliError(
            "invalid_worktree_name",
            "worktree name must match ^[a-z0-9][a-z0-9._-]{0,63}$ "
            "(lowercase alnum, dot, underscore, hyphen; 1-64 chars; "
            f"must start alnum). Got: {name!r}",
        )
    return name


def ensure_no_inprogress_op(repo: Path) -> None:
    """Refuse if the repo is mid-rebase/merge/cherry-pick/bisect.

    Untracked / modified files are fine; an interrupted operation is not,
    because forking a worktree off such a state is asking for confusion.
    """
    git_dir_result = _git(repo, ["rev-parse", "--git-dir"])
    if git_dir_result.returncode != 0:
        raise CliError("not_a_git_repo", _git_error_detail(git_dir_result))
    git_dir = Path(git_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (repo / git_dir).resolve()
    markers = {
        "rebase-merge": "in-progress rebase (rebase-merge)",
        "rebase-apply": "in-progress rebase (rebase-apply)",
        "MERGE_HEAD": "in-progress merge",
        "CHERRY_PICK_HEAD": "in-progress cherry-pick",
        "REVERT_HEAD": "in-progress revert",
        "BISECT_LOG": "in-progress bisect",
    }
    for marker, label in markers.items():
        if (git_dir / marker).exists():
            raise CliError(
                "repo_busy",
                f"refusing to create worktree: {label} detected in {git_dir}",
            )


def resolve_ref(repo: Path, ref: str) -> str:
    """Resolve *ref* to a full SHA in *repo*; raises if unknown."""
    result = _git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        raise CliError(
            "invalid_worktree_ref",
            f"--worktree-from ref does not resolve in this repo: {ref}",
        )
    return result.stdout.strip()


def branch_exists(repo: Path, branch: str) -> bool:
    """Return True if *branch* exists locally or on any remote."""
    # Local branches
    local = _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    if local.returncode == 0:
        return True
    # Remote-tracking branches across all remotes
    listing = _git(repo, ["for-each-ref", "--format=%(refname)", "refs/remotes/"])
    if listing.returncode == 0:
        suffix = f"/{branch}"
        for line in listing.stdout.splitlines():
            # refs/remotes/<remote>/<branch> — strip first three components
            tail = line.removeprefix("refs/remotes/")
            if "/" in tail and tail.split("/", 1)[1] == branch:
                return True
            # Defensive: in case branch contains slashes
            if tail.endswith(suffix):
                return True
    return False


def worktree_registered(repo: Path, target: Path) -> bool:
    """Return True if *target* is registered in `git worktree list` even if its
    on-disk directory was deleted by hand (a 'prunable' worktree)."""
    result = _git(repo, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return False
    target_resolved = str(target.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt = line.removeprefix("worktree ").strip()
            try:
                if str(Path(wt).resolve()) == target_resolved:
                    return True
            except OSError:
                if wt == str(target):
                    return True
    return False


def create_named_worktree(
    repo: Path,
    target: Path,
    base_ref: str,
    branch: str,
) -> None:
    """Create a new worktree at *target* on a brand-new *branch* off *base_ref*.

    Unlike :func:`create_worktree` (which checks out detached for bakeoff),
    this allocates a real branch — useful when the user intends to commit
    inside the worktree.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "-b", branch, str(target), base_ref],
    )
    if result.returncode != 0:
        raise CliError("worktree_create_failed", _git_error_detail(result))


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


# ---- Carry-dirty support for `megaplan init --in-worktree` ----

# Directory names that must never be copied as "untracked" content because
# they belong to git/megaplan infrastructure and would either confuse the new
# worktree or cause infinite recursion.
_CARRY_DIRTY_EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".git\\",
    ".claude/",
    ".claude\\",
    ".megaplan-worktrees/",
    ".megaplan-worktrees\\",
)


def _is_excluded_carry_path(rel_posix: str) -> bool:
    """Reject paths under .git/, .claude/, or .megaplan-worktrees/."""
    if rel_posix in (".git", ".claude", ".megaplan-worktrees"):
        return True
    for prefix in _CARRY_DIRTY_EXCLUDED_PREFIXES:
        if rel_posix.startswith(prefix):
            return True
    return False


def has_dirty_state(repo: Path) -> bool:
    """Return True if *repo* has any tracked modification or untracked file."""
    diff = _git(repo, ["diff", "HEAD", "--quiet"])
    if diff.returncode != 0:
        return True
    others = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    if others.returncode != 0:
        raise CliError("carry_dirty_failed", _git_error_detail(others))
    return bool(others.stdout)


def _list_untracked(repo: Path) -> list[str]:
    """Return repo-relative POSIX paths of untracked files (excluding ignored)."""
    result = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    if result.returncode != 0:
        raise CliError("carry_dirty_failed", _git_error_detail(result))
    raw = result.stdout
    if not raw:
        return []
    return [p for p in raw.split("\0") if p]


def _capture_tracked_patch(repo: Path) -> bytes:
    """Capture `git diff HEAD --binary` as bytes (preserves binary diffs)."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--binary", "--no-color"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("carry_dirty_failed", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise CliError("carry_dirty_failed", detail or "git diff HEAD failed")
    return result.stdout


def _apply_patch(repo: Path, patch: bytes) -> None:
    """Apply *patch* in *repo* without touching the index. Errors are hard."""
    try:
        result = subprocess.run(
            ["git", "apply", "--binary"],
            cwd=repo,
            input=patch,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("carry_dirty_failed", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise CliError(
            "carry_dirty_failed",
            f"git apply failed in new worktree: {detail or 'unknown error'}",
        )


def _copy_untracked(source: Path, target: Path, rel_paths: list[str]) -> int:
    """Copy untracked files from *source* into *target*. Returns count copied.

    Skips paths under .git/, .claude/, or .megaplan-worktrees/. Refuses
    anything that's not a regular file or symlink. Preserves mode bits and
    symlink semantics.
    """
    copied = 0
    for rel in rel_paths:
        if _is_excluded_carry_path(rel):
            continue
        src = source / rel
        if not src.exists() and not src.is_symlink():
            # File vanished between ls-files and copy — skip silently.
            continue
        # Only regular files or symlinks are allowed.
        if src.is_symlink():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            link_target = os.readlink(src)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(link_target, dst)
        elif src.is_file():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        else:
            raise CliError(
                "carry_dirty_failed",
                f"untracked entry is neither regular file nor symlink: {rel}",
            )
        copied += 1
    return copied


def carry_dirty_state(source: Path, target: Path) -> tuple[int, int]:
    """Replicate *source*'s working-copy dirt into *target*. Atomic on failure.

    Returns ``(tracked_changes, untracked_files)`` actually carried.

    On any failure the caller is responsible for removing *target* via
    :func:`remove_worktree`; this function raises CliError without cleanup so
    the calling layer can decide between rollback strategies. (In practice
    :func:`carry_dirty_state_atomic` does that wrap.)
    """
    # Tracked modifications via patch.
    patch = _capture_tracked_patch(source)
    tracked_count = 0
    if patch.strip():
        # Count files in the diff by looking for "diff --git" lines.
        tracked_count = sum(
            1 for line in patch.splitlines() if line.startswith(b"diff --git ")
        )
        _apply_patch(target, patch)

    # Untracked files via copy.
    untracked = _list_untracked(source)
    untracked_count = _copy_untracked(source, target, untracked)

    return tracked_count, untracked_count


def carry_dirty_state_atomic(
    source: Path, target: Path
) -> tuple[int, int]:
    """Same as :func:`carry_dirty_state` but on failure removes *target*.

    Source repo is read-only throughout. If carrying fails for any reason,
    the new worktree is forcibly removed before re-raising.
    """
    try:
        return carry_dirty_state(source, target)
    except CliError:
        try:
            remove_worktree(target, force=True)
        except CliError:
            # Best-effort cleanup; the original error is more informative.
            pass
        raise
