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

Resume routing
--------------

:func:`classify_resume_cursor` inspects the raw cursor on disk and
returns one of three outcomes:

* ``"graph"`` — cursor exists but has **no** ``native`` key.
  The cursor was produced by the graph executor; resume must route
  through :func:`arnold.pipeline.executor.run_pipeline_resume`.

* ``"native"`` — cursor exists with a valid ``native`` key (contains
  ``pc`` and ``version`` as integers).  The cursor was produced by
  the native runtime; resume must route through
  :func:`arnold.pipeline.native.runtime.run_native_pipeline` with
  ``resume=True``.

* ``"none"`` — no ``resume_cursor.json`` file exists at
  *artifact_root*.  The caller must decide whether to start a fresh
  run or raise a missing-cursor error.

* Raises :class:`NativeCursorCorruptError` — cursor exists and carries
  a ``native`` key, but the key is malformed (not a dict, missing
  ``pc``/``version``, or non-integer values).  The caller MUST NOT
  silently fall back to the graph executor; it must fail closed and
  surface the diagnostic so an operator can investigate.

This classification is intentionally separate from
:func:`read_native_cursor` so that callers who only care about the
valid native shape can use the existing reader, while resume routing
can inspect the raw on-disk bytes and distinguish between "no native
data" and "native data that is corrupt."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from arnold.pipeline.resume import (
    RESUME_CURSOR_FILENAME,
    persist_resume_cursor,
    read_resume_cursor,
)

NATIVE_CURSOR_VERSION = 1
"""Schema version for the native cursor payload."""


class NativeCursorCorruptError(ValueError):
    """Raised when a resume cursor carries a native key that is corrupt.

    This is a **fail-closed** error.  The caller MUST NOT silently
    fall back to the graph executor — the cursor claims native
    ownership but cannot be validated, so resuming through the wrong
    engine risks incompatible state.
    """

    def __init__(self, detail: str, *, cursor_path: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.cursor_path = cursor_path


def classify_resume_cursor(artifact_root: str | Path) -> str:
    """Classify a resume cursor as graph-born or native-born.

    Reads the raw ``resume_cursor.json`` from *artifact_root* and
    inspects the top-level ``native`` key WITHOUT applying the
    full :func:`read_native_cursor` normalisation — callers get a
    deterministic routing decision based solely on the on-disk shape.

    Returns
    -------
    str
        One of ``"graph"``, ``"native"``, or ``"none"``.

        * ``"graph"`` — cursor exists but the ``native`` key is absent.
          The cursor was written by the graph executor (or an older
          system that never emitted a ``native`` key).  Resume must
          route through the graph executor.

        * ``"native"`` — cursor exists and the ``native`` key is a
          valid dict containing integer ``pc`` and ``version`` fields.
          Resume must route through the native runtime.

        * ``"none"`` — no ``resume_cursor.json`` file exists at
          *artifact_root*.  There is no cursor to route.

    Raises
    ------
    NativeCursorCorruptError
        The cursor file exists and carries a ``native`` key, but the
        key is malformed — not a dict, missing ``pc`` or ``version``,
        or non-integer values.  The caller must fail closed.
    """
    root = Path(artifact_root)
    cursor_path = root / RESUME_CURSOR_FILENAME

    if not cursor_path.exists():
        return "none"

    # Read raw JSON — intentionally bypass read_resume_cursor so we
    # can distinguish malformed JSON from a missing native key.
    try:
        raw = json.loads(cursor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Unreadable or malformed JSON — treat as no usable cursor.
        # This is the same as "none" because we cannot even determine
        # whether a native key was intended.
        return "none"

    if not isinstance(raw, dict):
        return "none"

    native = raw.get("native")

    # No native key at all → graph-born cursor.
    if native is None:
        return "graph"

    # native key present but not a dict → corrupt.
    if not isinstance(native, dict):
        raise NativeCursorCorruptError(
            f"Resume cursor at {cursor_path} has a 'native' key "
            f"that is not a JSON object (got {type(native).__name__}). "
            f"The cursor claims native ownership but the native payload "
            f"is unreadable — refusing to route.",
            cursor_path=str(cursor_path),
        )

    # native key is a dict — check required fields.
    if "pc" not in native:
        raise NativeCursorCorruptError(
            f"Resume cursor at {cursor_path} has a 'native' key "
            f"that is missing the required 'pc' field. "
            f"The cursor claims native ownership but the native "
            f"payload is incomplete — refusing to route.",
            cursor_path=str(cursor_path),
        )

    if "version" not in native:
        raise NativeCursorCorruptError(
            f"Resume cursor at {cursor_path} has a 'native' key "
            f"that is missing the required 'version' field. "
            f"The cursor claims native ownership but the native "
            f"payload is incomplete — refusing to route.",
            cursor_path=str(cursor_path),
        )

    if not isinstance(native["pc"], int):
        raise NativeCursorCorruptError(
            f"Resume cursor at {cursor_path} has a 'native.pc' "
            f"value of type {type(native['pc']).__name__} (expected int). "
            f"The cursor claims native ownership but the program "
            f"counter is unreadable — refusing to route.",
            cursor_path=str(cursor_path),
        )

    if not isinstance(native["version"], int):
        raise NativeCursorCorruptError(
            f"Resume cursor at {cursor_path} has a 'native.version' "
            f"value of type {type(native['version']).__name__} (expected int). "
            f"The cursor claims native ownership but the schema "
            f"version is unreadable — refusing to route.",
            cursor_path=str(cursor_path),
        )

    # Valid native cursor.
    return "native"


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
    reentry_stage: str | None = None,
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
        reentry_stage: Stable stage identifier where resume should re-enter.
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
    if reentry_stage is not None:
        extra["reentry_stage"] = reentry_stage
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
    "NativeCursorCorruptError",
    "classify_resume_cursor",
    "persist_native_cursor",
    "read_native_cursor",
]
