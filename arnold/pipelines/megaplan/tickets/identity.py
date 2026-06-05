"""Git-based identity helpers for ticket codebase resolution."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .files import slugify


@dataclass(frozen=True)
class RepoCodebaseIdentity:
    owner: str
    name: str
    default_branch: str
    root_commit_sha: str


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


def repo_codebase_identity(cwd: Path | None = None) -> RepoCodebaseIdentity:
    """Return deterministic store codebase metadata for the current repo.

    This helper requires a committed repository first. If the repo has no
    resolvable ``origin`` owner/name, it falls back to a deterministic local
    identity that incorporates the repo directory slug, the resolved path hash,
    and the root commit SHA prefix.
    """
    root_sha = repo_root_sha(cwd)
    owner, name = repo_owner_name(cwd)
    if not owner or not name:
        repo_root = Path(cwd or ".").resolve()
        path_hash = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]
        root_sha_prefix = root_sha[:12]
        owner = "local"
        name = f"{slugify(repo_root.name)}-{path_hash}-{root_sha_prefix}"
    default_branch = repo_default_branch(cwd) or "main"
    return RepoCodebaseIdentity(
        owner=owner,
        name=name,
        default_branch=default_branch,
        root_commit_sha=root_sha,
    )
