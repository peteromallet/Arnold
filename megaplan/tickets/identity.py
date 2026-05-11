"""Git-based identity helpers for ticket codebase resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path


def repo_root_sha(cwd: Path | None = None) -> str:
    """Return the SHA of the root commit in the current repo.

    Uses ``git rev-list --max-parents=0 HEAD``.  Raises
    :class:`subprocess.CalledProcessError` when the repo has no commits.
    """
    result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
    )
    sha = result.stdout.strip()
    if not sha:
        raise RuntimeError("git rev-list returned no root commit SHA")
    return sha.split("\n")[0]  # first root in case of multiple orphans


def repo_owner_name(cwd: Path | None = None) -> tuple[str, str] | tuple[None, None]:
    """Return ``(owner, name)`` parsed from the ``origin`` remote URL, or
    ``(None, None)`` if no remote is configured."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError:
        return (None, None)
    url = result.stdout.strip()
    # Handle both SSH and HTTPS URLs
    # git@github.com:owner/name.git  → owner/name
    # https://github.com/owner/name   → owner/name
    url = url.removesuffix(".git")
    if ":" in url and "@" in url:
        # SSH style
        path = url.split(":")[-1]
    else:
        # HTTPS style
        path = url.rstrip("/").split("/")[-2:]
        path = "/".join(path)
    parts = path.split("/")
    if len(parts) >= 2:
        return (parts[-2].lower(), parts[-1].lower())
    return (None, None)


def repo_default_branch(cwd: Path | None = None) -> str | None:
    """Return the default branch name (e.g. ``main``, ``master``), or *None*
    if it cannot be determined."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=cwd,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None
    ref = result.stdout.strip()
    # refs/remotes/origin/main → main
    if ref.startswith("refs/remotes/origin/"):
        return ref[len("refs/remotes/origin/"):]
    return ref or None