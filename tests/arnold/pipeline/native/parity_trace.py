"""Narrow, stable normalization for event-journal folds used in parity traces.

The helpers here convert filesystem paths to a stable ``<artifact-root>``
prefix, coerce tuples/lists, and sort dict keys so that graph-side and
native-side folds can be compared as plain JSON-shaped values. They do not
strip semantics; any semantic divergence between engines still fails the
assertion.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _looks_like_path(value: str) -> bool:
    # Match POSIX absolute paths and Windows absolute paths.
    return (
        len(value) > 1
        and (value.startswith("/") or (len(value) > 2 and value[1] == ":"))
        and "/" in value
    )


def _collect_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, Path):
        paths.append(str(value))
    elif isinstance(value, str) and _looks_like_path(value):
        paths.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_paths(item, paths)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_paths(item, paths)


def _common_prefix(paths: list[str]) -> str:
    if not paths:
        return ""
    normalized = [os.path.normpath(p) for p in paths]
    prefix = os.path.commonprefix(normalized)
    # Back up to the nearest directory boundary so we replace the whole root.
    if prefix and not prefix.endswith(os.sep):
        prefix = prefix.rsplit(os.sep, 1)[0] + os.sep
    return prefix


def _json_default(value: object) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _normalize_roots(value: Any, prefix: str) -> Any:
    if prefix and isinstance(value, str):
        if value.startswith(prefix):
            return "<artifact-root>/" + value[len(prefix):].lstrip("/")
        # Also try normalized match.
        norm_value = os.path.normpath(value)
        if norm_value.startswith(prefix):
            return "<artifact-root>/" + norm_value[len(prefix):].lstrip("/")
    return value


def normalize_event_fold(folded: Any) -> Any:
    """Return a JSON-round-tripped, key-sorted, root-normalized fold."""

    if folded is None:
        return None

    path_strings: list[str] = []
    _collect_paths(folded, path_strings)
    prefix = _common_prefix(path_strings)

    def _walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): _walk(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_walk(v) for v in value]
        if isinstance(value, Path):
            return _normalize_roots(str(value), prefix)
        if isinstance(value, str):
            return _normalize_roots(value, prefix)
        return value

    normalized = _walk(folded)
    return json.loads(json.dumps(normalized, default=_json_default, sort_keys=True))
