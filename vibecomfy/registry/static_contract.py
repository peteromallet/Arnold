from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


_UNSUPPORTED = object()


def extract_ready_template_contract(path: str | Path) -> dict[str, Any]:
    """Extract cheap public contract metadata from a ready-template source file.

    The extractor is intentionally static: unsupported dynamic values become
    diagnostics instead of guessed descriptor fields.
    """
    source_path = Path(path)
    diagnostics: list[dict[str, Any]] = []
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        return {
            "public_inputs": [],
            "public_outputs": [],
            "diagnostics": [
                {
                    "code": "static_contract_parse_failed",
                    "severity": "warning",
                    "message": str(exc),
                }
            ],
            "marker": "unknown",
        }

    assignments = _module_assignments(tree, diagnostics)
    metadata = _dict_or_empty(assignments.get("READY_METADATA"))
    requirements = _dict_or_empty(assignments.get("READY_REQUIREMENTS"))
    public_inputs: list[dict[str, Any]] = []
    public_outputs: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name in {"bind_input", "register_input"}:
            descriptor = _extract_input_call(node, call_name, diagnostics)
            if descriptor is not None:
                public_inputs.append(descriptor)
        elif call_name in {"bind_output", "VibeOutput"}:
            descriptor = _extract_output_call(node, call_name, diagnostics)
            if descriptor is not None:
                public_outputs.append(descriptor)

    marker = _template_marker(source)
    return {
        "public_inputs": public_inputs,
        "public_outputs": public_outputs,
        "diagnostics": diagnostics,
        "marker": marker,
        "readiness_class": _readiness_class(metadata, marker),
        "artifact_expectations": public_outputs,
        "model_count": len(_list_items(requirements.get("models"))),
        "custom_nodes": sorted(item for item in _list_items(requirements.get("custom_nodes")) if isinstance(item, str)),
        "app_active": _is_app_active(metadata),
        "blocked": _has_marker(metadata, "blocked"),
        "reference": _has_marker(metadata, "reference"),
        "supplemental": _has_marker(metadata, "supplemental"),
    }


def _module_assignments(tree: ast.Module, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in {"READY_METADATA", "READY_REQUIREMENTS"}:
                continue
            value = _literal_value(node.value, assignments)
            if value is _UNSUPPORTED:
                diagnostics.append(_diagnostic("static_dynamic_assignment", f"{target.id} contains dynamic values"))
                continue
            assignments[target.id] = value
    return assignments


def _extract_input_call(
    node: ast.Call,
    call_name: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    offset = 1 if call_name == "bind_input" else 0
    name = _literal_arg_or_keyword(node, offset, "name", diagnostics, call_name)
    node_id = _literal_arg_or_keyword(node, offset + 1, "node_id", diagnostics, call_name)
    field = _literal_arg_or_keyword(node, offset + 2, "field", diagnostics, call_name)
    if not all(isinstance(value, str) for value in (name, node_id, field)):
        return None
    value = _literal_arg_or_keyword(node, offset + 3, "value", diagnostics, call_name, required=False)
    descriptor = {
        "name": name,
        "target": {"node_id": node_id, "field": field},
        "node_id": node_id,
        "field": field,
        "value": None if value is _UNSUPPORTED else value,
        "type": _keyword_literal(node, "type", diagnostics, call_name),
        "default": _keyword_literal(node, "default", diagnostics, call_name),
        "required": _keyword_literal(node, "required", diagnostics, call_name),
        "range": _keyword_literal(node, "range", diagnostics, call_name),
        "aliases": _keyword_literal(node, "aliases", diagnostics, call_name) or [],
        "media_semantics": _keyword_literal(node, "media_semantics", diagnostics, call_name),
        "status": "static",
        "source": call_name,
    }
    if descriptor["media_semantics"] is None:
        descriptor["media_semantics"] = _keyword_literal(node, "media", diagnostics, call_name)
    if descriptor["default"] is None and value is not _UNSUPPORTED:
        descriptor["default"] = value
    return descriptor


def _extract_output_call(
    node: ast.Call,
    call_name: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    offset = 1 if call_name == "bind_output" else 0
    node_id = _literal_arg_or_keyword(node, offset, "node_id", diagnostics, call_name)
    if not isinstance(node_id, str):
        return None
    output_type = _literal_arg_or_keyword(node, offset + 1, "output_type", diagnostics, call_name, required=False)
    descriptor = {
        "name": _keyword_literal(node, "name", diagnostics, call_name),
        "node_id": node_id,
        "output_type": _keyword_literal(node, "output_type", diagnostics, call_name)
        or (output_type if output_type is not _UNSUPPORTED else None),
        "artifact_kind": _keyword_literal(node, "artifact_kind", diagnostics, call_name),
        "mime_type": _keyword_literal(node, "mime_type", diagnostics, call_name),
        "filename_prefix": _keyword_literal(node, "filename_prefix", diagnostics, call_name),
        "expected_cardinality": _keyword_literal(node, "expected_cardinality", diagnostics, call_name),
        "status": "static",
        "source": call_name,
    }
    if call_name == "VibeOutput":
        positional_name = _literal_arg_or_keyword(node, offset + 2, "name", diagnostics, call_name, required=False)
        if descriptor["name"] is None and positional_name is not _UNSUPPORTED:
            descriptor["name"] = positional_name
    return descriptor


def _literal_arg(
    node: ast.Call,
    index: int,
    field_name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
    *,
    required: bool = True,
) -> Any:
    if index >= len(node.args):
        if required:
            diagnostics.append(_diagnostic("static_missing_argument", f"{call_name} missing {field_name!r}"))
        return _UNSUPPORTED
    value = _literal_value(node.args[index], {})
    if value is _UNSUPPORTED and required:
        diagnostics.append(_diagnostic("static_dynamic_value", f"{call_name} has dynamic {field_name!r}"))
    return value


def _literal_arg_or_keyword(
    node: ast.Call,
    index: int,
    field_name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
    *,
    required: bool = True,
) -> Any:
    if index < len(node.args):
        return _literal_arg(node, index, field_name, diagnostics, call_name, required=required)
    value = _keyword_literal(node, field_name, diagnostics, call_name)
    if value is None and required:
        diagnostics.append(_diagnostic("static_missing_argument", f"{call_name} missing {field_name!r}"))
        return _UNSUPPORTED
    return value if value is not None else _UNSUPPORTED


def _keyword_literal(
    node: ast.Call,
    name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
) -> Any:
    for keyword in node.keywords:
        if keyword.arg != name:
            continue
        value = _literal_value(keyword.value, {})
        if value is _UNSUPPORTED:
            diagnostics.append(_diagnostic("static_dynamic_value", f"{call_name} has dynamic {name!r}"))
            return None
        return value
    return None


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        values = [_literal_value(item, assignments) for item in node.elts]
        return _UNSUPPORTED if any(value is _UNSUPPORTED for value in values) else values
    if isinstance(node, ast.Tuple):
        values = [_literal_value(item, assignments) for item in node.elts]
        return _UNSUPPORTED if any(value is _UNSUPPORTED for value in values) else tuple(values)
    if isinstance(node, ast.Dict):
        result: dict[Any, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                return _UNSUPPORTED
            key = _literal_value(key_node, assignments)
            value = _literal_value(value_node, assignments)
            if key is _UNSUPPORTED or value is _UNSUPPORTED:
                return _UNSUPPORTED
            result[key] = value
        return result
    if isinstance(node, ast.Name):
        return assignments.get(node.id, _UNSUPPORTED)
    if isinstance(node, ast.Subscript):
        value = _literal_value(node.value, assignments)
        key = _literal_value(node.slice, assignments)
        if isinstance(value, dict) and key is not _UNSUPPORTED:
            return value.get(key, _UNSUPPORTED)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _UNSUPPORTED


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _diagnostic(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "message": message}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _template_marker(source: str) -> str:
    header = "\n".join(source.splitlines()[:5])
    if "# vibecomfy: manual" in header:
        return "manual"
    if "# vibecomfy: generated" in header:
        return "generated"
    return "unmarked"


def _readiness_class(metadata: dict[str, Any], marker: str) -> str:
    if _has_marker(metadata, "blocked"):
        return "blocked"
    if metadata.get("ready_template"):
        return "ready"
    return marker


def _has_marker(metadata: dict[str, Any], marker: str) -> bool:
    markers = metadata.get("markers")
    if isinstance(markers, list) and marker in markers:
        return True
    return metadata.get(marker) is True


def _is_app_active(metadata: dict[str, Any]) -> bool:
    if metadata.get("app_active") is True:
        return True
    return metadata.get("coverage_tier") == "required"
