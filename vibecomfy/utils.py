"""Utility functions for VibeComfy.

Includes ``atomic_write_json`` for crash-safe JSON writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write_json(path: str | Path, data: Any) -> Path:
    """Atomically write *data* as JSON to *path*.

    Writes to a temporary sibling file (same directory, ``.tmp`` suffix),
    ``json.dump``\\s with ``indent=2, default=str``, flushes, ``os.fsync``\\s
    the file descriptor, then atomically replaces the target via
    ``Path.replace()``.

    If a stale temp file exists from a prior crash it is removed before
    writing.

    Returns the final ``Path``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")

    # Remove stale temp file from a prior crash.
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        # Clean up the temp file on any failure so it doesn't linger.
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    tmp_path.replace(target)
    return target
