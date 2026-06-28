from __future__ import annotations

from typing import Any

from vibecomfy.porting.edit.apply_types import _issue
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.schema import InputSpec


def _validate_literal_value(
    *,
    value: Any,
    spec: InputSpec | None,
    class_type: str,
    input_name: str,
    context: str,
) -> list[PortIssue]:
    if spec is None:
        return []
    issues: list[PortIssue] = []
    choices = getattr(spec, "choices", None) or []
    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
        issues.append(
            _issue(
                "value_not_in_enum",
                f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "choices": list(choices),
                },
            )
        )
    min_value = getattr(spec, "min", None)
    max_value = getattr(spec, "max", None)
    if min_value is not None or max_value is not None:
        numeric = _as_number(value)
        if numeric is not None and (
            (min_value is not None and numeric < float(min_value))
            or (max_value is not None and numeric > float(max_value))
        ):
            issues.append(
                _issue(
                    "value_out_of_range",
                    f"{context} rejected {class_type}.{input_name}: value {value!r} is outside the declared range.",
                    detail={
                        "class_type": class_type,
                        "input": input_name,
                        "value": value,
                        "min": min_value,
                        "max": max_value,
                    },
                )
            )
    expected_type = _primitive_expected_type(getattr(spec, "type", None))
    if expected_type is not None and not _matches_primitive_type(value, expected_type):
        issues.append(
            _issue(
                "value_type_mismatch",
                f"{context} rejected {class_type}.{input_name}: expected {expected_type}, got {type(value).__name__}.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
            )
        )
    return issues


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING", "TEXT"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "FLOAT":
        return ((isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float))
    if expected_type == "BOOLEAN":
        return isinstance(value, bool)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_NO_MATCH = object()


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for choice in choices:
            if isinstance(choice, str) and choice.replace("\\", "/") == normalized:
                return choice
    return _NO_MATCH
