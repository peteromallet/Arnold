"""Canonical session marker and sidecar classification helpers."""

from __future__ import annotations

from pathlib import Path

CANONICAL_SIDECAR_SUFFIXES = (
    ".repair-progress.json",
    ".reap-progress.json",
    ".chain-health.progress.json",
    ".progress.json",
)


def marker_name(path_or_name: str | Path) -> str:
    return path_or_name.name if isinstance(path_or_name, Path) else Path(path_or_name).name


def canonical_sidecar_suffix(path_or_name: str | Path) -> str | None:
    name = marker_name(path_or_name)
    for suffix in CANONICAL_SIDECAR_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return None


def is_canonical_sidecar_path(path_or_name: str | Path) -> bool:
    return canonical_sidecar_suffix(path_or_name) is not None


def is_canonical_session_marker_path(path_or_name: str | Path) -> bool:
    name = marker_name(path_or_name)
    return name.endswith(".json") and not is_canonical_sidecar_path(name)
