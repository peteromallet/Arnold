from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from vibecomfy.metadata import (
    MODEL_KEYS,
    PROMPT_KEYS,
    PROMPT_NODE_CLASSES,
    SEED_KEYS,
    STEP_KEYS,
    STEPS_NODE_CLASSES,
)


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
    public_inputs.extend(_infer_common_input_contracts(tree, public_inputs))

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


def compare_public_contracts(
    *,
    static_inputs: list[dict[str, Any]],
    static_outputs: list[dict[str, Any]],
    built_inputs: list[dict[str, Any]],
    built_outputs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compare static and built public contract descriptors by stable keys."""
    static_input_keys = {_input_key(item) for item in static_inputs}
    built_input_keys = {_input_key(item) for item in built_inputs}
    static_output_keys = {_output_key(item) for item in static_outputs}
    built_output_keys = {_output_key(item) for item in built_outputs}
    return {
        "inputs_only_static": [_input_key_to_dict(key) for key in sorted(static_input_keys - built_input_keys)],
        "inputs_only_built": [_input_key_to_dict(key) for key in sorted(built_input_keys - static_input_keys)],
        "outputs_only_static": [_output_key_to_dict(key) for key in sorted(static_output_keys - built_output_keys)],
        "outputs_only_built": [_output_key_to_dict(key) for key in sorted(built_output_keys - static_output_keys)],
    }


def public_contracts_match(
    *,
    static_inputs: list[dict[str, Any]],
    static_outputs: list[dict[str, Any]],
    built_inputs: list[dict[str, Any]],
    built_outputs: list[dict[str, Any]],
) -> bool:
    comparison = compare_public_contracts(
        static_inputs=static_inputs,
        static_outputs=static_outputs,
        built_inputs=built_inputs,
        built_outputs=built_outputs,
    )
    return all(not values for values in comparison.values())


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


def _infer_common_input_contracts(
    tree: ast.AST,
    explicit_inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    explicit_names = {item.get("name") for item in explicit_inputs if isinstance(item.get("name"), str)}
    inferred: dict[str, dict[str, Any]] = {}
    next_auto_id = 1
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node.func) in {"_node", "node", "ready_node"}
    ]
    for call in sorted(calls, key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        node_info = _runtime_node_call(call, next_auto_id)
        if node_info is None:
            continue
        next_auto_id += 1
        class_type = node_info["class_type"]
        node_id = node_info["node_id"]
        for field, value in node_info["inputs"].items():
            input_name = _common_input_name(class_type, field, value)
            if input_name is None or input_name in explicit_names or input_name in inferred:
                continue
            inferred[input_name] = {
                "name": input_name,
                "target": {"node_id": node_id, "field": field},
                "node_id": node_id,
                "field": field,
                "value": value,
                "type": None,
                "default": None,
                "required": False,
                "range": None,
                "aliases": [],
                "media_semantics": None,
                "status": "static",
                "source": "finalize_metadata",
            }
    return [inferred[name] for name in sorted(inferred)]


def _runtime_node_call(node: ast.Call, next_auto_id: int) -> dict[str, Any] | None:
    call_name = _call_name(node.func)
    if call_name == "_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        node_id = _literal_arg(node, 2, "node_id", [], call_name, required=False)
        keyword_inputs = _literal_keyword_inputs(node)
    elif call_name == "ready_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        node_id = _keyword_literal(node, "source_id", [], call_name) or str(next_auto_id)
        keyword_inputs = _literal_keyword_inputs(node, excluded={"source_id", "outputs", "extras"})
        extras = _keyword_literal(node, "extras", [], call_name)
        if isinstance(extras, dict):
            keyword_inputs.update({str(key): value for key, value in extras.items()})
    elif call_name == "node":
        class_type = _literal_arg(node, 0, "class_type", [], call_name, required=False)
        node_id = str(next_auto_id)
        keyword_inputs = _literal_keyword_inputs(node)
    else:
        return None
    if not isinstance(class_type, str) or not isinstance(node_id, str):
        return None
    return {"class_type": class_type, "node_id": node_id, "inputs": keyword_inputs}


def _literal_keyword_inputs(node: ast.Call, *, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    result: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg in excluded:
            continue
        value = _literal_value(keyword.value, {})
        if value is _UNSUPPORTED:
            continue
        result[keyword.arg] = value
    return result


def _common_input_name(class_type: str, field: str, value: Any) -> str | None:
    normalized = field.lower()
    if normalized in PROMPT_KEYS and isinstance(value, str) and class_type in PROMPT_NODE_CLASSES:
        return "prompt"
    if normalized in SEED_KEYS and isinstance(value, int) and not isinstance(value, bool):
        return "seed"
    if normalized in STEP_KEYS and isinstance(value, int) and not isinstance(value, bool) and class_type in STEPS_NODE_CLASSES:
        return "steps"
    if normalized in MODEL_KEYS and isinstance(value, str):
        return "model"
    return None


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


def _input_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("name") or ""), str(item.get("node_id") or ""), str(item.get("field") or ""))


def _output_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("name") or ""), str(item.get("node_id") or ""), str(item.get("output_type") or ""))


def _input_key_to_dict(key: tuple[str, str, str]) -> dict[str, str]:
    name, node_id, field = key
    return {"name": name, "node_id": node_id, "field": field}


def _output_key_to_dict(key: tuple[str, str, str]) -> dict[str, str]:
    name, node_id, output_type = key
    return {"name": name, "node_id": node_id, "output_type": output_type}


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
