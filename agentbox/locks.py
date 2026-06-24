"""File-backed per-repo advisory locks for AgentBox."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import re
import time
from pathlib import Path
from typing import Iterator

from agentbox.config import AgentBoxConfig


_REPO_LOCK_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class AgentBoxLockError(RuntimeError):
    """Raised for invalid lock requests."""


class AgentBoxLockTimeout(TimeoutError):
    """Raised when a repo lock cannot be acquired before its deadline."""


@dataclass(frozen=True)
class RepoLock:
    """Acquired repo lock handle."""

    repo_name: str
    path: Path
    token: str


def repo_lock_path(config: AgentBoxConfig, repo_name: str) -> Path:
    """Return the lock file path for ``repo_name``."""

    _validate_repo_name(repo_name)
    return config.locks_root / f"{repo_name}.lock"


@contextmanager
def acquire_repo_lock(
    config: AgentBoxConfig,
    repo_name: str,
    *,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.05,
) -> Iterator[RepoLock]:
    """Acquire one repo lock using atomic lock-file creation."""

    path = repo_lock_path(config, repo_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    token = f"pid={os.getpid()} time={time.time_ns()}"
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise AgentBoxLockTimeout(
                    f"timed out acquiring repo lock {repo_name!r} at {path}"
                ) from exc
            time.sleep(poll_interval_seconds)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
        fd = None
        yield RepoLock(repo_name=repo_name, path=path, token=token)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            if path.read_text(encoding="utf-8").strip() == token:
                path.unlink()
        except FileNotFoundError:
            pass


def _validate_repo_name(repo_name: str) -> None:
    if not repo_name or not _REPO_LOCK_NAME_PATTERN.fullmatch(repo_name):
        raise AgentBoxLockError(f"invalid repo lock name: {repo_name!r}")


__all__ = [
    "AgentBoxLockError",
    "AgentBoxLockTimeout",
    "RepoLock",
    "acquire_repo_lock",
    "repo_lock_path",
]
