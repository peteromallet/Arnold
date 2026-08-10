"""Pure structural validation for :class:`arnold.pipeline.types.ContractResult`.

This module validates only the ``ContractResult.payload`` mapping against a
small, deterministic JSON Schema subset. It is intentionally neutral:
no registry lookups, runtime wiring, or tier-specific behavior lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.types import ContractResult


JSON_POINTER_ROOT = ""


@dataclass(frozen=True)
class ValidationDiagnostic:
    """A single deterministic validation failure."""

    code: str
    message: str
    payload_pointer: str = JSON_POINTER_ROOT
    schema_pointer: str = JSON_POINTER_ROOT


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate validation outcome."""

    diagnostics: tuple[ValidationDiagnostic, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def escape_json_pointer_token(token: str) -> str:
    """Escape one RFC 6901 token."""

    return token.replace("~", "~0").replace("/", "~1")


def append_json_pointer(pointer: str, token: str | int) -> str:
    """Append a token to an RFC 6901 pointer."""

    return f"{pointer}/{escape_json_pointer_token(str(token))}"


def _is_json_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(
            value, float
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, Mapping)
    return False


def _normalise_type_keyword(schema: Mapping[str, Any]) -> tuple[str, ...]:
    raw = schema.get("type")
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        values = [item for item in raw if isinstance(item, str)]
        return tuple(sorted(dict.fromkeys(values)))
    return ()


def _diagnostic(
    code: str,
    message: str,
    payload_pointer: str,
    schema_pointer: str,
) -> ValidationDiagnostic:
    return ValidationDiagnostic(
        code=code,
        message=message,
        payload_pointer=payload_pointer,
        schema_pointer=schema_pointer,
    )


def _validate(
    value: Any,
    schema: Mapping[str, Any],
    payload_pointer: str,
    schema_pointer: str,
) -> tuple[ValidationDiagnostic, ...]:
    diagnostics: list[ValidationDiagnostic] = []

    const = schema.get("const", _MISSING)
    if const is not _MISSING and value != const:
        diagnostics.append(
            _diagnostic(
                "const_mismatch",
                f"value must equal const {const!r}",
                payload_pointer,
                append_json_pointer(schema_pointer, "const"),
            )
        )
        return tuple(diagnostics)

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        diagnostics.append(
            _diagnostic(
                "enum_mismatch",
                f"value must be one of {enum_values!r}",
                payload_pointer,
                append_json_pointer(schema_pointer, "enum"),
            )
        )
        return tuple(diagnostics)

    type_names = _normalise_type_keyword(schema)
    if type_names and not any(_is_json_type(value, name) for name in type_names):
        diagnostics.append(
            _diagnostic(
                "type_mismatch",
                f"value does not match declared type(s) {list(type_names)!r}",
                payload_pointer,
                append_json_pointer(schema_pointer, "type"),
            )
        )
        return tuple(diagnostics)

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        match_count = 0
        for index, branch in enumerate(one_of):
            if isinstance(branch, Mapping) and not _validate(
                value,
                branch,
                payload_pointer,
                append_json_pointer(append_json_pointer(schema_pointer, "oneOf"), index),
            ):
                match_count += 1
        if match_count != 1:
            diagnostics.append(
                _diagnostic(
                    "one_of_mismatch",
                    f"value must match exactly one oneOf branch; matched {match_count}",
                    payload_pointer,
                    append_json_pointer(schema_pointer, "oneOf"),
                )
            )
            return tuple(diagnostics)

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        matched = False
        for index, branch in enumerate(any_of):
            if isinstance(branch, Mapping) and not _validate(
                value,
                branch,
                payload_pointer,
                append_json_pointer(append_json_pointer(schema_pointer, "anyOf"), index),
            ):
                matched = True
                break
        if not matched:
            diagnostics.append(
                _diagnostic(
                    "any_of_mismatch",
                    "value must match at least one anyOf branch",
                    payload_pointer,
                    append_json_pointer(schema_pointer, "anyOf"),
                )
            )
            return tuple(diagnostics)

    has_object_keywords = any(
        key in schema for key in ("properties", "required", "additionalProperties")
    )
    has_array_keywords = "items" in schema

    if ("object" in type_names or (not type_names and has_object_keywords)) and isinstance(
        value, Mapping
    ):
        diagnostics.extend(
            _validate_object(
                value=value,
                schema=schema,
                payload_pointer=payload_pointer,
                schema_pointer=schema_pointer,
            )
        )
    elif ("array" in type_names or (not type_names and has_array_keywords)) and isinstance(
        value, list
    ):
        diagnostics.extend(
            _validate_array(
                value=value,
                schema=schema,
                payload_pointer=payload_pointer,
                schema_pointer=schema_pointer,
            )
        )

    return tuple(diagnostics)


def _validate_object(
    *,
    value: Mapping[str, Any],
    schema: Mapping[str, Any],
    payload_pointer: str,
    schema_pointer: str,
) -> tuple[ValidationDiagnostic, ...]:
    diagnostics: list[ValidationDiagnostic] = []
    properties_raw = schema.get("properties")
    properties = properties_raw if isinstance(properties_raw, Mapping) else {}
    required_raw = schema.get("required")
    required = (
        tuple(item for item in required_raw if isinstance(item, str))
        if isinstance(required_raw, list)
        else ()
    )
    for key in sorted(required):
        if key not in value:
            diagnostics.append(
                _diagnostic(
                    "missing_required",
                    f"missing required property {key!r}",
                    append_json_pointer(payload_pointer, key),
                    append_json_pointer(schema_pointer, "required"),
                )
            )

    additional_properties = schema.get("additionalProperties", True)
    if additional_properties is False:
        extra_keys = sorted(key for key in value.keys() if key not in properties)
        for key in extra_keys:
            diagnostics.append(
                _diagnostic(
                    "additional_property",
                    f"unexpected property {key!r}",
                    append_json_pointer(payload_pointer, key),
                    append_json_pointer(schema_pointer, "additionalProperties"),
                )
            )

    for key in sorted(properties):
        if key not in value:
            continue
        child_schema = properties[key]
        if isinstance(child_schema, Mapping):
            diagnostics.extend(
                _validate(
                    value[key],
                    child_schema,
                    append_json_pointer(payload_pointer, key),
                    append_json_pointer(
                        append_json_pointer(schema_pointer, "properties"), key
                    ),
                )
            )
    return tuple(diagnostics)


def _validate_array(
    *,
    value: list[Any],
    schema: Mapping[str, Any],
    payload_pointer: str,
    schema_pointer: str,
) -> tuple[ValidationDiagnostic, ...]:
    item_schema = schema.get("items")
    if not isinstance(item_schema, Mapping):
        return ()
    diagnostics: list[ValidationDiagnostic] = []
    schema_items_pointer = append_json_pointer(schema_pointer, "items")
    for index, item in enumerate(value):
        diagnostics.extend(
            _validate(
                item,
                item_schema,
                append_json_pointer(payload_pointer, index),
                schema_items_pointer,
            )
        )
    return tuple(diagnostics)


def validate_payload_against_schema(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> ValidationResult:
    """Validate a payload mapping against the supported schema subset."""

    return ValidationResult(
        diagnostics=_validate(
            payload,
            schema,
            payload_pointer=JSON_POINTER_ROOT,
            schema_pointer=JSON_POINTER_ROOT,
        )
    )


def validate_contract_result(
    contract: ContractResult,
    schema: Mapping[str, Any],
) -> ValidationResult:
    """Validate only ``contract.payload`` against *schema*."""

    return validate_payload_against_schema(contract.payload, schema)


_MISSING = object()
