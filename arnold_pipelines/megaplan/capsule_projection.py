"""Capsule Definition identity projection helpers.

Rehomed from ``arnold_pipelines.megaplan._pipeline.behavioral_manifest``
during M3 burn-down (T15).  Only the projection functions consumed by
``store/capsule.py`` are carried forward; the full static-behavioral-manifest
builder remains in the legacy module for internal ``_pipeline`` consumers
until M4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)

SCHEMA_VERSION = 1
REBUILD_METADATA_SCHEMA_VERSION = 1


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Return stable JSON bytes for identity projections."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def capsule_definition_identity_projection(
    *,
    static_behavioral_hash: str,
    runtime_topology_hash: str | None = None,
) -> dict[str, object]:
    """Return the canonical Capsule Definition identity inputs.

    Runtime topology is intentionally additive.  Static-only definitions keep
    the static source identity but are marked non-replay-ready until a trusted
    runtime topology hash is available.
    """
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "projection": "megaplan.capsule-definition-identity",
        "static_behavioral_hash": static_behavioral_hash,
        "runtime_topology_hash": runtime_topology_hash,
        "identity_mode": "static+runtime-topology"
        if runtime_topology_hash
        else "static-only",
        "replay_ready": bool(runtime_topology_hash),
    }
    canonical = canonical_json_bytes(payload)
    return {
        **payload,
        "canonical_bytes": canonical,
        "definition_identity_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }


# ── Rebuild metadata & digest helpers (pure, no side effects) ──────────────


def _capsule_projection_json_safe(projection: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a capsule projection dict to a JSON-safe representation.

    The ``canonical_bytes`` field is a ``bytes`` object that cannot be
    serialized by ``json.dumps``.  This helper replaces it with its hex
    representation so the digest computation is deterministic.
    """
    result: dict[str, Any] = {}
    for key, value in projection.items():
        if isinstance(value, bytes):
            result[key] = "hex:" + value.hex()
        elif isinstance(value, dict):
            result[key] = _capsule_projection_json_safe(value)
        else:
            result[key] = value
    return result


def compute_capsule_projection_digest(projection: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of a capsule projection view.

    This digest is separate from the ``definition_identity_hash`` — it
    covers the full projection output including any appended metadata
    and is used for rebuild parity comparisons.

    Parameters
    ----------
    projection:
        A projection dict produced by
        :func:`capsule_definition_identity_projection` or
        :func:`capsule_projection_with_metadata`.

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    safe = _capsule_projection_json_safe(dict(projection))
    canonical = _projection_canonical_dumps(safe)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_capsule_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for a capsule source file.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the source file driving the capsule projection.

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def capsule_rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata for a capsule projection.

    Pure function — never mutates source evidence.  The caller attaches
    the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the capsule source file.
    projection_digest:
        Pre-computed digest of the projection view.
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

    cursor = capture_capsule_source_cursor(source_path)
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


def capsule_projection_with_metadata(
    *,
    static_behavioral_hash: str,
    runtime_topology_hash: str | None = None,
    source_path: str | Path | None = None,
) -> dict[str, object]:
    """Return a capsule identity projection with rebuild metadata attached.

    This is the recommended entry point for rebuild-aware consumers: it
    produces the same identity projection as
    :func:`capsule_definition_identity_projection` plus a top-level
    ``rebuild_metadata`` block containing the source cursor, freshness,
    lag, and rebuild digest.

    The ``definition_identity_hash`` remains stable and is **not**
    affected by metadata — it covers only the core identity payload.
    The ``projection_digest`` inside ``rebuild_metadata`` covers the
    entire output including metadata, enabling rebuild parity checks.

    Parameters
    ----------
    static_behavioral_hash:
        The static behavioral hash of the Capsule Definition.
    runtime_topology_hash:
        Optional runtime topology hash.
    source_path:
        Optional path to the source file for cursor capture. When
        ``None``, ``rebuild_metadata`` is omitted.

    Returns
    -------
    dict
        The identity projection with an optional ``rebuild_metadata`` key.
    """
    projection = capsule_definition_identity_projection(
        static_behavioral_hash=static_behavioral_hash,
        runtime_topology_hash=runtime_topology_hash,
    )
    if source_path is not None:
        digest = compute_capsule_projection_digest(projection)
        metadata = capsule_rebuild_metadata(
            source_path, projection_digest=digest
        )
        result: dict[str, object] = dict(projection)
        result["rebuild_metadata"] = metadata
        return result
    return projection
