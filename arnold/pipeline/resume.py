"""Pipeline resume-cursor persistence helpers.

Writes a ``resume_cursor.json`` file atomically via the runtime persistence
primitives so external tooling (and the executor itself) can discover where
a pipeline should re-enter on resume.

Boundary discipline: no ``megaplan`` imports.  No ``plan_dir`` vocabulary.
Uses ``atomic_write_json`` from ``arnold.runtime.state_persistence``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.runtime.state_persistence import atomic_write_json


def persist_resume_cursor(
    artifact_root: str | Path,
    *,
    stage: str,
    resume_cursor: str | None = None,
    **extra: Any,
) -> Path:
    """Atomically write ``resume_cursor.json`` to *artifact_root*.

    Parameters
    ----------
    artifact_root:
        Root directory where ``resume_cursor.json`` will be written.
    stage:
        Name of the pipeline stage to re-enter on resume.
    resume_cursor:
        Opaque cursor payload for the step to consume on resume.
        When ``None`` the field is emitted as ``null`` in JSON.
    **extra:
        Additional key-value pairs injected into the payload.

    Returns
    -------
    Path
        The path to the written ``resume_cursor.json`` file.
    """
    root = Path(artifact_root)
    payload: dict[str, Any] = {
        "stage": stage,
        "resume_cursor": resume_cursor,
    }
    payload.update(extra)
    path = root / "resume_cursor.json"
    atomic_write_json(path, payload)
    return path


def read_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read the persisted ``resume_cursor.json`` from *artifact_root*.

    Returns ``None`` when the file is missing, unreadable, malformed
    JSON, or not a ``dict``.  A ``resume_cursor`` value of ``null`` in
    the JSON translates to Python ``None`` in the returned dict.
    """
    root = Path(artifact_root)
    path = root / "resume_cursor.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def persist_composite_resume_cursor(
    artifact_root: str | Path,
    *,
    children: dict[str, Any],
    version: int = 1,
    **extra: Any,
) -> Path:
    """Atomically write ``composite_resume_cursor.json`` to *artifact_root*.

    Parameters
    ----------
    artifact_root:
        Root directory where ``composite_resume_cursor.json`` will be written.
    children:
        Mapping of ``child_id`` → resume cursor payload for each suspended
        child in a fan-out composition.
    version:
        Schema version for the composite cursor envelope.  Defaults to 1.
    **extra:
        Additional key-value pairs injected into the payload (e.g.
        ``shared_awaitable``, ``pending_suspensions``, ``shared_thread_ref``).

    Returns
    -------
    Path
        The path to the written ``composite_resume_cursor.json`` file.
    """
    root = Path(artifact_root)
    payload: dict[str, Any] = {
        "kind": "composite_suspension",
        "version": version,
        "children": children,
    }
    payload.update(extra)
    path = root / "composite_resume_cursor.json"
    atomic_write_json(path, payload)
    return path


def read_composite_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read the persisted ``composite_resume_cursor.json`` from *artifact_root*.

    Returns ``None`` when the file is missing, unreadable, malformed
    JSON, or not a ``dict``.
    """
    root = Path(artifact_root)
    path = root / "composite_resume_cursor.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data
