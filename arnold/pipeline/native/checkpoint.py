"""Native pipeline checkpoint persistence.

Thin wrappers around :mod:`arnold.pipeline.resume` that serialise and
deserialise the native runtime cursor shape.  The native fields are
passed as ``**extra`` kwargs to :func:`persist_resume_cursor` so the
existing atomic-write path is reused without modification.

Cursor shape (additive — existing readers see the usual top-level keys
plus extra native data)::

    {
        "stage": "<current-stage>",
        "resume_cursor": null,
        "stages": ["phase_a__pc0", "phase_b__pc1"],
        "loops": {"my_loop": 2},
        "frames": {"my_loop": {"iteration_data": ...}},
        "native": {
            "pc": 3,
            "version": 1
        },
        "cursor_id": "<uuid4-hex>",
        "stage_reentry_points": {"phase_name": "<stable_stage_id>"}
    }

The ``native`` key carries the program counter and a schema version so
the runtime can detect schema drift on resume.

``cursor_id`` is a stable UUID4 hex string generated once per pipeline
execution and reused across all checkpoint/suspension events within that
run.  ``stage_reentry_points`` maps each completed phase name to its
full stage identifier, enabling external tooling to locate reentry
targets without parsing the ``stages`` list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from arnold.pipeline.resume import (
    persist_resume_cursor,
    read_resume_cursor,
)

NATIVE_CURSOR_VERSION = 1
"""Schema version for the native cursor payload."""


def persist_native_cursor(
    artifact_root: str | Path,
    *,
    stage: str,
    pc: int,
    stages: list[str] | None = None,
    loops: dict[str, int] | None = None,
    frames: dict[str, Any] | None = None,
    resume_cursor: str | None = None,
    cursor_id: str | None = None,
    stage_reentry_points: dict[str, Any] | None = None,
    version: int = NATIVE_CURSOR_VERSION,
) -> Path:
    """Persist the native runtime cursor to *artifact_root*/resume_cursor.json.

    All native-specific fields are passed through as ``**extra`` kwargs
    to :func:`persist_resume_cursor`, which handles atomic writes.

    Args:
        artifact_root: Directory to write ``resume_cursor.json`` into.
        stage: Current stage identifier (e.g. ``"my_pipe__do_work__pc0"``).
        pc: Current zero-based program counter.
        stages: Ordered list of completed stage identifiers.
        loops: Loop iteration counters keyed by loop guard name.
        frames: JSON-serializable per-loop frame data keyed by loop guard name.
        resume_cursor: Opaque cursor string (forwarded as-is).
        cursor_id: Stable identifier for this cursor instance (uuid4 hex).
        stage_reentry_points: Mapping of phase name → stable stage identifier.
        version: Native cursor schema version (default ``1``).

    Returns:
        Path to the written cursor file.
    """
    native_payload: dict[str, Any] = {
        "pc": pc,
        "version": version,
    }

    extra: dict[str, Any] = {
        "native": native_payload,
        "stages": stages if stages is not None else [],
        "loops": loops if loops is not None else {},
        "frames": frames if frames is not None else {},
    }

    if cursor_id is not None:
        extra["cursor_id"] = cursor_id
    if stage_reentry_points is not None:
        extra["stage_reentry_points"] = stage_reentry_points

    return persist_resume_cursor(
        artifact_root,
        stage=stage,
        resume_cursor=resume_cursor,
        **extra,
    )


def read_native_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read and validate a native cursor from *artifact_root*/resume_cursor.json.

    Returns ``None`` when the file is missing, malformed, or lacks the
    required ``native`` sub-dict with ``pc`` and ``version`` fields.

    Old cursors without ``cursor_id`` or ``stage_reentry_points`` are
    accepted; these fields are normalised to ``None`` and ``{}``
    respectively.

    Args:
        artifact_root: Directory containing ``resume_cursor.json``.

    Returns:
        The full cursor dict on success, or ``None`` if invalid/absent.
    """
    data = read_resume_cursor(artifact_root)
    if data is None:
        return None

    # Require the additive native key with pc and version
    native = data.get("native")
    if not isinstance(native, dict):
        return None
    if "pc" not in native or "version" not in native:
        return None
    if not isinstance(native["pc"], int) or not isinstance(native["version"], int):
        return None

    # Normalise optional fields to their expected types
    if not isinstance(data.get("stages"), list):
        data["stages"] = []
    if not isinstance(data.get("loops"), dict):
        data["loops"] = {}
    if not isinstance(data.get("frames"), dict):
        data["frames"] = {}

    # Normalise new additive fields (backward-compatible with old cursors)
    if "cursor_id" not in data or not isinstance(data.get("cursor_id"), str):
        data["cursor_id"] = None
    if "stage_reentry_points" not in data or not isinstance(data.get("stage_reentry_points"), dict):
        data["stage_reentry_points"] = {}

    return data


__all__ = [
    "NATIVE_CURSOR_VERSION",
    "persist_native_cursor",
    "read_native_cursor",
]
