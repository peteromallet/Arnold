from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    atomic_write_json,
    now_utc,
    sha256_file,
)

ADVISORY_PATH_PROJECTION_LIMIT = 40
BULK_OPERATION_SAMPLE_LIMIT = 5

REBUILD_METADATA_SCHEMA_VERSION = 1


def _artifact_ref_for_json_file(plan_dir: Path, name: str) -> dict[str, Any]:
    path = plan_dir / name
    return {
        "plan_id": plan_dir.name,
        "name": name,
        "kind": "json",
        "role": "full_advisory_path_set",
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _semantic_bulk_operation_summary(values: list[str]) -> dict[str, Any] | None:
    """Summarize only path sets that are mechanically uniform by inspection."""
    if len(values) <= ADVISORY_PATH_PROJECTION_LIMIT:
        return None
    normalized = [Path(value) for value in values if value.strip()]
    if len(normalized) != len(values):
        return None
    suffixes = {path.suffix for path in normalized}
    if len(suffixes) != 1:
        return None
    parents = {path.parent.as_posix() for path in normalized}
    if len(parents) != 1:
        return None
    parent = next(iter(parents))
    if parent in {"", "."}:
        return None
    suffix = next(iter(suffixes))
    sample_paths = list(values[:BULK_OPERATION_SAMPLE_LIMIT])
    return {
        "kind": "semantic_bulk_operation_summary",
        "operation": "uniform_path_set",
        "confidence": "conservative_path_shape_only",
        "path_count": len(values),
        "common_directory": parent,
        "file_extension": suffix,
        "sample_paths": sample_paths,
        "sampled_deviations": [],
        "fallback": "mixed diffs are left as capped path projections plus full_set_artifact_ref",
        "live_tree_verification": [
            f"git status --short -- {parent}",
            f"find {parent} -type f -name '*{suffix}' | sort | head -n 20",
            "Inspect the full_set_artifact_ref JSON before relying on the summary.",
        ],
    }


def _project_advisory_path_list(
    values: list[str],
    *,
    plan_dir: Path,
    artifact_name: str,
    label: str,
    item_limit: int = ADVISORY_PATH_PROJECTION_LIMIT,
) -> dict[str, Any] | list[str]:
    """Return a bounded inline path projection, preserving full data in a sidecar."""
    if len(values) <= item_limit:
        return list(values)
    bulk_summary = _semantic_bulk_operation_summary(values)
    payload = {
        "label": label,
        "count": len(values),
        "items": list(values),
    }
    if bulk_summary is not None:
        payload["semantic_bulk_operation_summary"] = bulk_summary
    atomic_write_json(plan_dir / artifact_name, payload, _plan_dir=plan_dir)
    projection: dict[str, Any] = {
        "items": list(values[:item_limit]),
        "omitted_count": len(values) - item_limit,
        "full_set_artifact_ref": _artifact_ref_for_json_file(plan_dir, artifact_name),
    }
    if bulk_summary is not None:
        projection["semantic_bulk_operation_summary"] = bulk_summary
    return projection


def summarize_path_list_for_prose(
    paths: list[str],
    *,
    plan_dir: Path | None,
    artifact_prefix: str,
    label: str,
) -> str:
    """Return a bounded prose summary of an advisory path list."""
    n = len(paths)
    k = ADVISORY_PATH_PROJECTION_LIMIT
    artifact_name = f"{artifact_prefix}_{label}.json"
    if n <= k:
        return ", ".join(paths)
    _project_advisory_path_list(
        paths,
        plan_dir=plan_dir if plan_dir is not None else Path("."),
        artifact_name=artifact_name,
        label=label,
        item_limit=k,
    )
    shown = ", ".join(paths[:k])
    suffix = f" — full set via ArtifactRef {artifact_name}" if plan_dir is not None else ""
    return f"{n} paths (showing {k}): {shown}{suffix}"


# ---------------------------------------------------------------------------
# Rebuild metadata & digest helpers (pure, no side effects)
# ---------------------------------------------------------------------------


def compute_advisory_projection_digest(projection: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of an advisory projection view.

    The digest is computed over the canonical (stable, sorted-key,
    no-whitespace) JSON representation of *projection*, making it
    byte-for-byte comparable across rebuilds.

    Parameters
    ----------
    projection:
        A projection dict produced by advisory path projection
        (e.g. the return value of :func:`_project_advisory_path_list`).

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    canonical = _projection_canonical_dumps(dict(projection))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_advisory_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for an advisory source file.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the source file driving the advisory projection
        (e.g. a plan directory artifact or path-list sidecar).

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def advisory_rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata for an advisory projection.

    Pure function — never mutates source evidence.  The caller is
    responsible for attaching the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the advisory source file.
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

    cursor = capture_advisory_source_cursor(source_path)
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
