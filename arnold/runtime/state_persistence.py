"""Mechanism-only state persistence primitives — locks and atomic writes.

These are pure-mechanism, opinion-free building blocks lifted from the
Megaplan substrate and stripped of all policy references.  They have
zero knowledge of plan directories, phase names, gate labels, or
Megaplan event emission.

Exports
-------
* ``plan_state_lock(lock_path)`` — fcntl.flock context manager.
* ``atomic_write_bytes``, ``atomic_write_text``, ``atomic_write_json`` —
  fsync-then-replace-then-fsync-parent atomic writes.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fsync_file_descriptor(fd: int) -> None:
    os.fsync(fd)


def _fsync_dir(path: Path) -> None:
    directory = path if path.is_dir() else path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY)
    try:
        _fsync_file_descriptor(fd)
    finally:
        os.close(fd)


def _json_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# File lock
# ---------------------------------------------------------------------------


@contextmanager
def plan_state_lock(lock_path: Path) -> Iterator[None]:
    """Serialize short read/modify/write cycles using an advisory file lock.

    Args:
        lock_path: Path to the lock file.  Parent directories are created
            if needed.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def runtime_state_lock(lock_path: str | Path) -> Iterator[None]:
    """Compatibility alias for neutral runtime state locks."""
    with plan_state_lock(Path(lock_path)):
        yield


# ---------------------------------------------------------------------------
# Atomic writes (fsync → replace → fsync-parent)
# ---------------------------------------------------------------------------


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write *content* to *path* atomically.

    Creates parent directories.  Writes to a temp file in the same
    directory, fsyncs the temp file, atomically replaces the target,
    then fsyncs the parent directory.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        _fsync_file_descriptor(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    _fsync_dir(path.parent)


def atomic_write_text(path: Path, content: str) -> None:
    """Atomic UTF-8 text write.  Delegates to :func:`atomic_write_bytes`."""
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, data: Any) -> None:
    """Atomic JSON write.  Delegates to :func:`atomic_write_text`."""
    atomic_write_text(path, _json_dump(data))
