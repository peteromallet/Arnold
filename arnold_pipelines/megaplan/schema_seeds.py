"""Generation-only helpers for seeding retained Megaplan contract schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.step_contracts import build_step_schema_filenames


def _step_schema_clones() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for step, filename in build_step_schema_filenames().items():
        schema = deepcopy(SCHEMAS[filename])
        required = schema.get("required")
        if isinstance(required, list):
            schema["required"] = list(required)
        schemas[step] = schema
    return schemas


def _is_object_schema(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "object":
        return True
    return isinstance(schema_type, list) and "object" in schema_type


def _close_object_schemas(schema: Any) -> Any:
    if isinstance(schema, dict):
        updated = {key: _close_object_schemas(value) for key, value in schema.items()}
        if _is_object_schema(updated):
            updated["additionalProperties"] = False
        return updated
    if isinstance(schema, list):
        return [_close_object_schemas(item) for item in schema]
    return schema


def legacy_v0_step_schemas() -> dict[str, dict[str, Any]]:
    """Return legacy-lenient top-level schemas keyed by Megaplan step name."""

    schemas = _step_schema_clones()
    for schema in schemas.values():
        if _is_object_schema(schema):
            schema["additionalProperties"] = True
    return schemas


def canonical_v1_step_schemas() -> dict[str, dict[str, Any]]:
    """Return canonical retained schemas keyed by Megaplan step name."""

    return {
        step: _close_object_schemas(schema)
        for step, schema in _step_schema_clones().items()
    }
