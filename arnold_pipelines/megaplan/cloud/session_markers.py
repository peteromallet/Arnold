"""Canonical session marker and sidecar classification helpers."""

from __future__ import annotations

from pathlib import Path

CANONICAL_SIDECAR_SUFFIXES = (
    ".liveness-fence.json",
    ".liveness-lease.json",
    ".repair-progress.json",
    ".reap-progress.json",
    ".chain-health.progress.json",
    ".progress.json",
)

RESERVED_SERVICE_SESSION_NAMES = frozenset({"megaplan-resident-discord"})


def marker_name(path_or_name: str | Path) -> str:
    return path_or_name.name if isinstance(path_or_name, Path) else Path(path_or_name).name


def session_name(path_or_name: str | Path) -> str:
    return marker_name(path_or_name).removesuffix(".json")


def is_reserved_service_session(path_or_name: str | Path) -> bool:
    return session_name(path_or_name) in RESERVED_SERVICE_SESSION_NAMES


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
    return (
        name.endswith(".json")
        and not is_canonical_sidecar_path(name)
        and not is_reserved_service_session(name)
    )
