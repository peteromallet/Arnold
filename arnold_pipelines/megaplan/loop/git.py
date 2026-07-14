"""Small git helpers for MegaLoop iterations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _run_git(project_dir: str | Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(project_dir),
        text=True,
        capture_output=True,
        check=check,
    )


def _normalize_pathspec(pattern: str) -> str:
    if pattern.startswith(":("):
        return pattern
    return f":(glob){pattern}"


def _changed_allowed_paths(project_dir: str | Path, allowed_changes: list[str]) -> list[str]:
    if not allowed_changes:
        return []
    status = _run_git(
        project_dir,
        ["status", "--porcelain", "--untracked-files=all", "--", *(_normalize_pathspec(item) for item in allowed_changes)],
    )
    paths: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in paths:
            paths.append(path)
    return paths


def git_commit(project_dir: str | Path, message: str, allowed_changes: list[str]) -> str | None:
    changed_paths = _changed_allowed_paths(project_dir, allowed_changes)
    if not changed_paths:
        return None
    _run_git(project_dir, ["add", "--", *changed_paths])
    staged = _run_git(project_dir, ["diff", "--cached", "--name-only", "--", *changed_paths], check=False)
    if not staged.stdout.strip():
        return None
    _run_git(project_dir, ["commit", "-m", message, "--only", "--", *changed_paths])
    return git_current_sha(project_dir)


def git_revert(project_dir: str | Path, commit_sha: str) -> None:
    try:
        _run_git(project_dir, ["revert", "--no-edit", commit_sha])
    except subprocess.CalledProcessError:
        try:
            _run_git(project_dir, ["revert", "--abort"], check=False)
        except subprocess.CalledProcessError:
            pass


def git_current_sha(project_dir: str | Path) -> str:
    result = _run_git(project_dir, ["rev-parse", "HEAD"])
    return result.stdout.strip()


def parse_metric(output: str, pattern: str) -> float | None:
    match = re.search(pattern, output, re.MULTILINE)
    if match is None:
        return None
    captured = next((group for group in match.groups() if group is not None), match.group(0))
    try:
        return float(captured)
    except (TypeError, ValueError):
        numeric = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(captured))
        if numeric is None:
            return None
        try:
            return float(numeric.group(0))
        except ValueError:
            return None


# ── git-status helpers (canonical home; moved from arnold_pipelines.megaplan.orchestration.evaluation) ──


def _normalize_repo_path(path: str, project_dir: Path | None = None) -> str:
    p = Path(path.strip())
    if project_dir is not None and p.is_absolute():
        try:
            project_abs = project_dir.resolve()
            resolved = p.resolve()
            rel = resolved.relative_to(project_abs)
            return rel.as_posix()
        except (ValueError, OSError):
            pass
    return p.as_posix()


def _parse_git_status_paths(stdout: str) -> set[str]:
    paths: set[str] = set()
    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        path_text = raw_line[3:].strip() if len(raw_line) >= 4 else raw_line.strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        cleaned = path_text.strip().strip('"')
        if not cleaned:
            continue
        is_dir = cleaned.endswith("/")
        normalized = _normalize_repo_path(cleaned)
        if is_dir and not normalized.endswith("/"):
            normalized += "/"
        paths.add(normalized)
    return paths


def _run_git_status_paths(
    repo_dir: Path,
    *,
    untracked_mode: str = "normal",
) -> tuple[set[str], str | None]:
    if not (repo_dir / ".git").exists():
        return set(), "Project directory is not a git repository."
    command = ["git", "status", "--short"]
    if untracked_mode == "all":
        command.append("--untracked-files=all")
    try:
        process = subprocess.run(
            command,
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return set(), "git not found on PATH."
    except subprocess.TimeoutExpired:
        return set(), "git status timed out."

    if process.returncode != 0:
        return set(), f"git status failed: {process.stderr.strip() or process.stdout.strip()}"
    return _parse_git_status_paths(process.stdout), None


def _discover_nested_git_repos(project_dir: Path, claimed_paths: set[str]) -> list[Path]:
    repos: set[Path] = set()
    project_abs = project_dir.resolve()
    for claimed in claimed_paths:
        candidate = project_dir / claimed
        try:
            relative_parts = candidate.resolve().relative_to(project_abs).parts
        except (OSError, ValueError):
            continue
        cursor = project_dir
        for part in relative_parts[:-1]:
            cursor = cursor / part
            if (cursor / ".git").exists():
                repos.add(cursor)
                break
    return sorted(repos, key=lambda path: path.as_posix())


def _collect_committed_range_paths(
    repo_dir: Path,
    *,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> set[str]:
    """Paths changed in the committed milestone range ``base..head``."""
    if base_ref is None:
        from arnold_pipelines.megaplan._core.io import _branch_diff_base

        base_ref = _branch_diff_base(repo_dir)
    if not base_ref:
        return set()
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}..{head_ref or 'HEAD'}"],
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0:
        return set()
    paths: set[str] = set()
    for line in proc.stdout.splitlines():
        cleaned = line.strip().strip('"')
        if not cleaned:
            continue
        if len(line) >= 4 and line[:2].strip() and line[2] == " ":
            paths.update(_parse_git_status_paths(line))
        else:
            paths.add(_normalize_repo_path(cleaned))
    return paths


def _collect_git_status_paths_with_nested_repos(
    project_dir: Path,
    *,
    claimed_paths: set[str],
    untracked_mode: str = "normal",
    include_committed: bool = False,
    committed_base_ref: str | None = None,
    committed_head_ref: str | None = None,
) -> tuple[set[str], str | None]:
    paths, error = _run_git_status_paths(project_dir, untracked_mode=untracked_mode)
    if error is not None:
        return paths, error

    project_abs = project_dir.resolve()
    for repo_dir in _discover_nested_git_repos(project_dir, claimed_paths):
        nested_paths, nested_error = _run_git_status_paths(
            repo_dir,
            untracked_mode=untracked_mode,
        )
        if nested_error is not None:
            continue
        try:
            prefix = repo_dir.resolve().relative_to(project_abs).as_posix()
        except (OSError, ValueError):
            continue
        paths.update(f"{prefix}/{path}" for path in nested_paths)
    if include_committed:
        paths.update(
            _collect_committed_range_paths(
                project_dir,
                base_ref=committed_base_ref,
                head_ref=committed_head_ref,
            )
        )
    return paths, None
