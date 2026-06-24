"""Pipeline resume-cursor persistence helpers.

The executor and package hooks can publish a small, opaque cursor document for
external tooling to discover where a suspended pipeline should re-enter. The
helper owns only durable JSON persistence; it does not interpret cursor bodies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.runtime.state_persistence import atomic_write_json

RESUME_CURSOR_FILENAME = "resume_cursor.json"
COMPOSITE_RESUME_CURSOR_FILENAME = "composite_resume_cursor.json"

ResumeCursorRuntime = str


def classify_resume_cursor_payload(payload: Any) -> ResumeCursorRuntime:
    """Classify a decoded resume cursor payload by runtime ownership.

    Returns ``"native"`` when the payload carries a valid additive native
    cursor, ``"graph"`` when it is a graph-era cursor with no native payload,
    ``"corrupt_native"`` when the payload claims native ownership but the
    native discriminator is malformed, and ``"none"`` when no cursor payload
    is available.
    """

    if not isinstance(payload, dict):
        return "none"

    native = payload.get("native")
    if native is None:
        return "graph"
    if not isinstance(native, dict):
        return "corrupt_native"
    if not isinstance(native.get("pc"), int):
        return "corrupt_native"
    if not isinstance(native.get("version"), int):
        return "corrupt_native"
    return "native"


def persist_resume_cursor(
    artifact_root: str | Path,
    *,
    stage: str,
    resume_cursor: str | None = None,
    **extra: Any,
) -> Path:
    """Atomically write ``resume_cursor.json`` under *artifact_root*."""

    path = Path(artifact_root) / RESUME_CURSOR_FILENAME
    payload: dict[str, Any] = {
        "stage": stage,
        "resume_cursor": resume_cursor,
    }
    payload.update(extra)
    atomic_write_json(path, payload)
    return path


def read_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``resume_cursor.json``; return ``None`` for absent or malformed data."""

    path = Path(artifact_root) / RESUME_CURSOR_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def persist_composite_resume_cursor(
    artifact_root: str | Path,
    *,
    children: dict[str, Any],
    version: int = 1,
    **extra: Any,
) -> Path:
    """Atomically write a fan-out/composite resume cursor document."""

    path = Path(artifact_root) / COMPOSITE_RESUME_CURSOR_FILENAME
    payload: dict[str, Any] = {
        "kind": "composite_suspension",
        "version": version,
        "children": children,
    }
    payload.update(extra)
    atomic_write_json(path, payload)
    return path


def read_composite_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``composite_resume_cursor.json``; return ``None`` if invalid."""

    path = Path(artifact_root) / COMPOSITE_RESUME_CURSOR_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


__all__ = [
    "COMPOSITE_RESUME_CURSOR_FILENAME",
    "RESUME_CURSOR_FILENAME",
    "classify_resume_cursor_payload",
    "persist_composite_resume_cursor",
    "persist_resume_cursor",
    "read_composite_resume_cursor",
    "read_resume_cursor",
]
