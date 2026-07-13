"""Schema-owned, fail-closed payload projection helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


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


__all__ = [
    "closed_object_schema",
    "project_schema_owned_fields",
    "require_schema_fields",
    "schema_object_properties",
    "schema_property_names",
    "schema_template_payload",
]
