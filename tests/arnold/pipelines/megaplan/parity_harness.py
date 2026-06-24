"""Shared normalization helpers for Megaplan native/graph parity traces.

These helpers narrow runtime state and resume cursors to stable, comparable
JSON-shaped values. They convert filesystem paths to a stable
``<artifact-root>`` prefix, coerce tuple/list equivalence, and sort dict keys.
They preserve all semantic keys; they only normalize representation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _looks_like_path(value: str) -> bool:
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
        norm_value = os.path.normpath(value)
        if norm_value.startswith(prefix):
            return "<artifact-root>/" + norm_value[len(prefix):].lstrip("/")
    return value


def normalize_state_narrow(state: Any) -> Any:
    """Return a JSON-round-tripped, key-sorted, root-normalized state."""

    if state is None:
        return None

    path_strings: list[str] = []
    _collect_paths(state, path_strings)
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

    normalized = _walk(state)
    return json.loads(json.dumps(normalized, default=_json_default, sort_keys=True))


def normalize_cursor_narrow(cursor: Any) -> Any:
    """Return a JSON-round-tripped, key-sorted, root-normalized cursor."""

    if cursor is None:
        return None

    path_strings: list[str] = []
    _collect_paths(cursor, path_strings)
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

    normalized = _walk(cursor)
    return json.loads(json.dumps(normalized, default=_json_default, sort_keys=True))


class MegaplanParityHarness:
    """Compare native and graph runtime traces for parity coverage."""

    def compare_native_to_graph(
        self,
        native: dict[str, Any],
        graph: dict[str, Any],
        *,
        topology_hash: str,
    ) -> dict[str, str]:
        """Return a match/mismatch report across parity dimensions."""

        report: dict[str, str] = {}

        native_hash = native.get("topology_hash")
        graph_hash = graph.get("topology_hash")
        if native_hash == graph_hash == topology_hash:
            report["topology_hash"] = "match"
        else:
            report["topology_hash"] = "mismatch"

        report["stage_sequence"] = (
            "match"
            if native.get("stage_sequence") == graph.get("stage_sequence")
            else "mismatch"
        )

        report["state"] = self._compare(
            normalize_state_narrow(native.get("state")),
            normalize_state_narrow(graph.get("state")),
        )
        report["resume_cursor"] = self._compare(
            normalize_cursor_narrow(native.get("resume_cursor")),
            normalize_cursor_narrow(graph.get("resume_cursor")),
        )
        report["artifact_inventory"] = self._compare(
            native.get("artifact_inventory"),
            graph.get("artifact_inventory"),
        )
        report["event_fold"] = self._compare(
            normalize_state_narrow(native.get("event_fold")),
            normalize_state_narrow(graph.get("event_fold")),
        )

        return report

    def _compare(self, native_value: Any, graph_value: Any) -> str:
        native_json = json.dumps(
            native_value, sort_keys=True, default=str, ensure_ascii=False
        )
        graph_json = json.dumps(
            graph_value, sort_keys=True, default=str, ensure_ascii=False
        )
        return "match" if native_json == graph_json else "mismatch"
