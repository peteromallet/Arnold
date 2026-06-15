from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft7Validator

from arnold.pipelines.megaplan._core.io import _enforce_openai_strict_mode
from arnold.pipelines.megaplan.schema_seeds import (
    canonical_v1_step_schemas,
    legacy_v0_step_schemas,
)


def _is_object_schema(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    return schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    )


def _without_null(schema_type: Any) -> Any:
    if isinstance(schema_type, list):
        without_null = [item for item in schema_type if item != "null"]
        return without_null[0] if len(without_null) == 1 else without_null
    return schema_type


def _compare_canonical_to_worker_projection(
    canonical: Any,
    projected: Any,
    *,
    path: str = "$",
    optional_nullable: bool = False,
) -> list[str]:
    errors: list[str] = []
    if isinstance(canonical, dict) and isinstance(projected, dict):
        projected = dict(projected)
        if optional_nullable and "type" in projected:
            projected["type"] = _without_null(projected["type"])

        canonical_properties = canonical.get("properties")
        projected_properties = projected.get("properties")
        if isinstance(canonical_properties, dict):
            if not isinstance(projected_properties, dict):
                return [f"{path}: projected schema lost properties"]
            if set(projected_properties) != set(canonical_properties):
                missing = sorted(set(canonical_properties) - set(projected_properties))
                extra = sorted(set(projected_properties) - set(canonical_properties))
                errors.append(f"{path}: property mismatch missing={missing} extra={extra}")
            required = set(canonical.get("required", []))
            projected_required = set(projected.get("required", []))
            expected_projected_required = set(canonical_properties)
            if projected_required != expected_projected_required:
                errors.append(
                    f"{path}: projected required mismatch "
                    f"expected={sorted(expected_projected_required)} "
                    f"actual={sorted(projected_required)}"
                )
            for name in sorted(set(canonical_properties) & set(projected_properties)):
                prop = projected_properties[name]
                if name not in required and isinstance(prop, dict):
                    projected_type = prop.get("type")
                    if isinstance(projected_type, str):
                        if projected_type != "null":
                            errors.append(f"{path}.{name}: optional property is not nullable")
                    elif isinstance(projected_type, list) and "null" not in projected_type:
                        errors.append(f"{path}.{name}: optional property is not nullable")
                errors.extend(
                    _compare_canonical_to_worker_projection(
                        canonical_properties[name],
                        projected_properties[name],
                        path=f"{path}.properties.{name}",
                        optional_nullable=name not in required,
                    )
                )

        canonical_keys = set(canonical) - {"properties", "required", "oneOf", "const", "type"}
        projected_keys = set(projected) - {"properties", "required", "anyOf", "type"}
        if "const" in canonical:
            projected_keys.discard("enum")
        if canonical_keys != projected_keys:
            errors.append(
                f"{path}: keyword mismatch missing={sorted(canonical_keys - projected_keys)} "
                f"extra={sorted(projected_keys - canonical_keys)}"
            )

        canonical_type = canonical.get("type")
        projected_type = projected.get("type")
        if optional_nullable:
            canonical_type = _without_null(canonical_type)
            projected_type = _without_null(projected_type)
        if canonical_type != projected_type:
            errors.append(
                f"{path}: type drift canonical={canonical.get('type')!r} "
                f"projected={projected.get('type')!r}"
            )
        if "oneOf" in canonical:
            if "anyOf" not in projected:
                errors.append(f"{path}: oneOf was not projected to anyOf")
            else:
                errors.extend(
                    _compare_canonical_to_worker_projection(
                        canonical["oneOf"],
                        projected["anyOf"],
                        path=f"{path}.oneOf",
                    )
                )
        if "const" in canonical:
            if projected.get("enum") != [canonical["const"]]:
                errors.append(f"{path}: const was not projected to a single-value enum")

        for key in sorted(canonical_keys & projected_keys):
            errors.extend(
                _compare_canonical_to_worker_projection(
                    canonical[key],
                    projected[key],
                    path=f"{path}.{key}",
                )
            )
        return errors

    if isinstance(canonical, list) and isinstance(projected, list):
        if len(canonical) != len(projected):
            return [f"{path}: list length drift {len(canonical)} != {len(projected)}"]
        for index, (canonical_item, projected_item) in enumerate(zip(canonical, projected)):
            errors.extend(
                _compare_canonical_to_worker_projection(
                    canonical_item,
                    projected_item,
                    path=f"{path}[{index}]",
                )
            )
        return errors

    if canonical != projected:
        return [f"{path}: value drift canonical={canonical!r} projected={projected!r}"]
    return []


def _assert_canonical_matches_worker_projection(step: str, schema: dict[str, Any]) -> None:
    projected = _enforce_openai_strict_mode(deepcopy(schema))
    errors = _compare_canonical_to_worker_projection(schema, projected)
    assert errors == [], step


def test_worker_projection_matches_canonical_v1_with_only_known_dialect_shifts() -> None:
    for step, schema in canonical_v1_step_schemas().items():
        _assert_canonical_matches_worker_projection(step, schema)


def test_projection_comparison_rejects_property_loss_rename_and_type_drift() -> None:
    schema = canonical_v1_step_schemas()["prep"]
    projected = _enforce_openai_strict_mode(deepcopy(schema))
    projected["properties"].pop("task_summary")
    assert any(
        "property mismatch" in error and "task_summary" in error
        for error in _compare_canonical_to_worker_projection(schema, projected)
    )

    projected = _enforce_openai_strict_mode(deepcopy(schema))
    projected["properties"]["renamed_summary"] = projected["properties"].pop("task_summary")
    assert any(
        "property mismatch" in error and "renamed_summary" in error
        for error in _compare_canonical_to_worker_projection(schema, projected)
    )

    projected = _enforce_openai_strict_mode(deepcopy(schema))
    projected["properties"]["task_summary"]["type"] = "integer"
    assert any(
        "type drift" in error and "task_summary" in error
        for error in _compare_canonical_to_worker_projection(schema, projected)
    )


def test_legacy_v0_accepts_extras_while_canonical_v1_rejects_them() -> None:
    v0 = legacy_v0_step_schemas()["prep"]
    v1 = canonical_v1_step_schemas()["prep"]
    payload = {
        "skip": False,
        "task_summary": "Add schema tests.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Compare projected schemas.",
        "legacy_extra": "allowed in v0 only",
    }

    assert list(Draft7Validator(v0).iter_errors(payload)) == []
    errors = list(Draft7Validator(v1).iter_errors(payload))
    assert errors
    assert any(error.validator == "additionalProperties" for error in errors)


def test_canonical_v1_keeps_optional_properties_optional() -> None:
    schema = canonical_v1_step_schemas()["prep"]
    payload = {
        "skip": False,
        "task_summary": "Add schema tests.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Compare projected schemas.",
    }

    assert "primary_criterion" not in schema["required"]
    assert "open_questions" not in schema["required"]
    assert list(Draft7Validator(schema).iter_errors(payload)) == []


def test_canonical_v1_recursively_closes_object_schemas() -> None:
    def assert_closed(schema: Any, path: str = "$") -> None:
        if isinstance(schema, dict):
            if _is_object_schema(schema):
                assert schema.get("additionalProperties") is False, path
            for key, value in schema.items():
                assert_closed(value, f"{path}.{key}")
        elif isinstance(schema, list):
            for index, value in enumerate(schema):
                assert_closed(value, f"{path}[{index}]")

    for schema in canonical_v1_step_schemas().values():
        assert_closed(schema)
