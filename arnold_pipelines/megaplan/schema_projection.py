"""Schema-owned, fail-closed payload projection helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)


def closed_object_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a schema and reject unknown fields at every object boundary.

    Unlike the provider transport transformation, this keeps the schema's
    explicit ``required`` lists unchanged.
    """

    def _close(node: Any) -> Any:
        if isinstance(node, dict):
            closed = {key: _close(value) for key, value in node.items()}
            node_type = closed.get("type")
            if node_type == "object" or (
                isinstance(node_type, list) and "object" in node_type
            ):
                closed.setdefault("additionalProperties", False)
            return closed
        if isinstance(node, list):
            return [_close(item) for item in node]
        return deepcopy(node)

    return _close(dict(schema))


def schema_object_properties(
    schema: Mapping[str, Any],
    *,
    contract: str,
) -> Mapping[str, Any]:
    """Return an object schema's properties or fail closed."""

    properties = schema.get("properties")
    if schema.get("type") != "object" or not isinstance(properties, Mapping):
        raise RuntimeError(
            f"{contract}: expected an object schema with a properties mapping; "
            "cannot project contract fields safely"
        )
    return properties


def schema_property_names(
    schema: Mapping[str, Any],
    *,
    contract: str,
) -> frozenset[str]:
    """Return the authoritative top-level field names for *schema*."""

    return frozenset(schema_object_properties(schema, contract=contract))


def schema_mapping_at_path(
    schema: Mapping[str, Any],
    path: Sequence[str],
    *,
    contract: str,
) -> Mapping[str, Any]:
    """Resolve a nested schema mapping or fail with its contract path.

    Projection code uses this instead of repeating unchecked
    ``schema["properties"][...]["items"]`` chains. A schema refactor then
    fails at import/use time instead of silently reverting to a stale
    hand-maintained field list.
    """

    node: Any = schema
    traversed: list[str] = []
    for key in path:
        traversed.append(key)
        if not isinstance(node, Mapping) or key not in node:
            location = "/".join(traversed)
            raise RuntimeError(
                f"{contract}: expected schema mapping at {location!r}"
            )
        node = node[key]
    if not isinstance(node, Mapping):
        location = "/".join(path)
        raise RuntimeError(
            f"{contract}: expected schema mapping at {location!r}"
        )
    return node


def require_schema_fields(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    contract: str,
) -> None:
    """Fail closed when a projection source lacks schema-required fields."""

    required = schema.get("required")
    if not isinstance(required, list) or not all(isinstance(key, str) for key in required):
        raise RuntimeError(
            f"{contract}: schema required must be a list of field names"
        )
    missing = [key for key in required if key not in payload]
    if missing:
        raise RuntimeError(
            f"{contract}: refusing to project payload missing required schema "
            f"fields: {', '.join(missing)}"
        )


def project_schema_owned_fields(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    contract: str,
) -> dict[str, Any]:
    """Project schema fields without renaming or defaulting them.

    Required fields are deliberately not synthesized. Structural validation
    remains responsible for reporting missing required fields.
    """

    owned = schema_property_names(schema, contract=contract)
    return {key: value for key, value in payload.items() if key in owned}


def schema_owned_field_drops(
    before: Any,
    after: Any,
    schema: Mapping[str, Any],
    *,
    pointer: str = "",
) -> tuple[str, ...]:
    """Return schema-owned JSON pointers removed by a normalizer.

    Value coercion and alias handling remain the normalizer's job. This guard
    answers the narrower contract question that caused the incident: did a
    field already owned by the active schema exist before normalization and
    disappear afterward?
    """

    drops: list[str] = []
    properties = schema.get("properties")
    if isinstance(before, Mapping) and isinstance(properties, Mapping):
        after_mapping = after if isinstance(after, Mapping) else {}
        for key, child_schema in properties.items():
            if key not in before:
                continue
            child_pointer = f"{pointer}/{key}"
            if key not in after_mapping:
                drops.append(child_pointer)
                continue
            if isinstance(child_schema, Mapping):
                drops.extend(
                    schema_owned_field_drops(
                        before[key],
                        after_mapping[key],
                        child_schema,
                        pointer=child_pointer,
                    )
                )
        return tuple(drops)

    items = schema.get("items")
    if (
        isinstance(before, list)
        and isinstance(after, list)
        and isinstance(items, Mapping)
    ):
        for index, before_item in enumerate(before):
            if index >= len(after):
                # The parent array field still exists; element filtering is a
                # semantic transform and cannot be attributed to one property.
                break
            drops.extend(
                schema_owned_field_drops(
                    before_item,
                    after[index],
                    items,
                    pointer=f"{pointer}/{index}",
                )
            )
    return tuple(drops)


def schema_template_payload(
    schema: Mapping[str, Any],
    *,
    contract: str,
) -> dict[str, Any]:
    """Build an editable object template from schema-owned properties."""

    def _placeholder(node: Any) -> Any:
        if not isinstance(node, Mapping):
            return None
        node_type = node.get("type")
        if isinstance(node_type, list):
            node_type = next((item for item in node_type if item != "null"), "null")
        if node_type == "object":
            properties = node.get("properties")
            if not isinstance(properties, Mapping):
                return {}
            return {key: _placeholder(value) for key, value in properties.items()}
        if node_type == "array":
            return []
        if node_type == "boolean":
            return False
        if node_type in {"integer", "number"}:
            return 0
        if node_type == "null":
            return None
        return ""

    properties = schema_object_properties(schema, contract=contract)
    return {key: _placeholder(value) for key, value in properties.items()}


# ── Rebuild metadata & digest helpers (pure, no side effects) ──────────────


REBUILD_METADATA_SCHEMA_VERSION = 1


def compute_projection_digest(projection: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of a schema projection view.

    The digest is computed over the canonical (stable, sorted-key,
    no-whitespace) JSON representation of *projection*, making it
    byte-for-byte comparable across rebuilds.

    Parameters
    ----------
    projection:
        A projection dict produced by any schema projection function.

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    canonical = _projection_canonical_dumps(dict(projection))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for a source schema file.

    Computes a cursor from the file at *source_path* that captures its
    absolute path, record count (line count for JSONL, 1 for a single
    schema file), and content digest.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the source schema file (e.g. a JSON schema or JSONL ledger).

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata (cursor, freshness, lag, digest) for a projection.

    This is a **pure function** — it never mutates source evidence or
    writes to the filesystem.  The caller is responsible for attaching
    the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the source schema file.
    projection_digest:
        Pre-computed digest of the projection view. When empty, the
        returned metadata will not include a digest.
    computed_at:
        ISO-8601 timestamp for the rebuild. When ``None``, ``now_utc()``
        is used.

    Returns
    -------
    dict
        A metadata dict with keys ``source_cursor`` (``ProjectionCursor``
        as dict), ``rebuilt_at``, ``freshness_seconds``, ``lag_seconds``,
        ``projection_digest`` (when non-empty), and
        ``rebuild_schema_version``.
    """
    from datetime import datetime, timezone

    cursor = capture_source_cursor(source_path)
    rebuilt_at = computed_at or now_utc()

    # Compute freshness: 0 for a just-rebuilt projection.
    freshness_seconds = 0.0

    # Compute lag: difference between rebuild time and source modification.
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
    "capture_source_cursor",
    "closed_object_schema",
    "compute_projection_digest",
    "project_schema_owned_fields",
    "rebuild_metadata",
    "require_schema_fields",
    "schema_mapping_at_path",
    "schema_owned_field_drops",
    "schema_object_properties",
    "schema_property_names",
    "schema_template_payload",
]
