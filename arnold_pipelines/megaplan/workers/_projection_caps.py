"""Worker-side prompt projection capability resolvers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)
from arnold_pipelines.megaplan.prompts._projection import PromptProjectionCapabilities

_READABLE_HERMES_TOOLSETS = {"file", "file-readonly", "terminal"}
_WRITABLE_HERMES_TOOLSETS = {"file", "terminal"}

REBUILD_METADATA_SCHEMA_VERSION = 1


def codex_projection_capabilities(
    *,
    resumed_session: bool,
    session_has_plan_dir_access: bool | None = None,
    checkpoint_write_access: bool = True,
) -> PromptProjectionCapabilities:
    """Resolve Codex prompt capabilities for fresh vs resumed sessions."""
    can_read_plan_dir = not resumed_session or bool(session_has_plan_dir_access)
    return PromptProjectionCapabilities(
        can_read_plan_dir=can_read_plan_dir,
        can_read_project_dir=True,
        has_file_tools=True,
        checkpoint_write_access=checkpoint_write_access,
    )


def hermes_projection_capabilities(toolsets: Sequence[str] | None) -> PromptProjectionCapabilities:
    """Resolve prompt capabilities from Hermes toolset selection."""
    selected = set(toolsets or [])
    can_read = bool(selected & _READABLE_HERMES_TOOLSETS)
    can_write = bool(selected & _WRITABLE_HERMES_TOOLSETS)
    return PromptProjectionCapabilities(
        can_read_plan_dir=can_read,
        can_read_project_dir=can_read,
        has_file_tools=can_read,
        checkpoint_write_access=can_write,
    )


def shannon_projection_capabilities(*, read_only: bool) -> PromptProjectionCapabilities:
    """Resolve prompt capabilities for Shannon read-only vs write modes."""
    return PromptProjectionCapabilities(
        can_read_plan_dir=True,
        can_read_project_dir=True,
        has_file_tools=True,
        checkpoint_write_access=not read_only,
    )


# ---------------------------------------------------------------------------
# Rebuild metadata & digest helpers (pure, no side effects)
# ---------------------------------------------------------------------------


def compute_caps_projection_digest(capabilities: PromptProjectionCapabilities) -> str:
    """Compute a deterministic SHA-256 digest of a worker capabilities projection.

    The digest covers the canonical representation of the resolved
    :class:`PromptProjectionCapabilities`, making it byte-for-byte
    comparable across rebuilds.

    Parameters
    ----------
    capabilities:
        A resolved :class:`PromptProjectionCapabilities` instance.

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    projection: dict[str, Any] = {
        "can_read_plan_dir": capabilities.can_read_plan_dir,
        "can_read_project_dir": capabilities.can_read_project_dir,
        "has_file_tools": capabilities.has_file_tools,
        "checkpoint_write_access": capabilities.checkpoint_write_access,
    }
    canonical = _projection_canonical_dumps(projection)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_caps_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for a worker configuration source.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the source file driving the capability resolution
        (e.g. a worker manifest or toolset config).

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def caps_rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata for a worker capabilities projection.

    Pure function — never mutates source evidence.  The caller is
    responsible for attaching the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the worker configuration source file.
    projection_digest:
        Pre-computed digest of the capabilities projection view.
    computed_at:
        ISO-8601 rebuild timestamp (default: ``now_utc()``).

    Returns
    -------
    dict
        Metadata dict with ``source_cursor``, ``rebuilt_at``,
        ``freshness_seconds``, ``lag_seconds``, optional
        ``projection_digest``, and ``rebuild_schema_version``.
    """
    from datetime import datetime

    cursor = capture_caps_source_cursor(source_path)
    rebuilt_at = computed_at or now_utc()

    freshness_seconds = 0.0

    try:
        source_path_obj = Path(source_path)
        if source_path_obj.exists():
            source_mtime = source_path_obj.stat().st_mtime
            rebuild_epoch = datetime.fromisoformat(rebuilt_at).timestamp()
            lag_seconds = max(0.0, rebuild_epoch - source_mtime)
        else:
            lag_seconds = 0.0
    except (OSError, ValueError):
        lag_seconds = 0.0

    metadata: dict[str, Any] = {
        "rebuild_schema_version": REBUILD_METADATA_SCHEMA_VERSION,
        "source_cursor": cursor.to_dict(),
        "rebuilt_at": rebuilt_at,
        "freshness_seconds": freshness_seconds,
        "lag_seconds": lag_seconds,
    }
    if projection_digest:
        metadata["projection_digest"] = projection_digest

    return metadata


__all__ = [
    "REBUILD_METADATA_SCHEMA_VERSION",
    "codex_projection_capabilities",
    "hermes_projection_capabilities",
    "shannon_projection_capabilities",
    "compute_caps_projection_digest",
    "capture_caps_source_cursor",
    "caps_rebuild_metadata",
]
