from __future__ import annotations

from typing import Any

from vibecomfy.schema.provider import SchemaProvider, schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


#: Known-lying custom-node schemas that may suppress only ``unknown_input`` and
#: ``value_*`` validation issues. Every entry must be cross-referenced from
#: ``docs/hiddenswitch_incompatibilities.md`` with its contract/root-cause note.
SCHEMA_VALIDATION_SKIP_CLASSES: dict[str, str] = {}


def validate_against_schema(workflow: VibeWorkflow, provider: SchemaProvider) -> list[ValidationIssue]:
    if schema_registry_empty(provider):
        return []

    issues: list[ValidationIssue] = []
    schema_by_node: dict[str, Any] = {}
    incoming = _incoming_inputs(workflow)

    for node_id, node in workflow.nodes.items():
        schema = schema_for(provider, node.class_type)
        if schema is None:
            issues.append(
                ValidationIssue(
                    "unknown_class_type",
                    f"Unknown class_type {node.class_type} on node {node_id}.",
                    detail={"node_id": node_id, "class_type": node.class_type},
                )
            )
            continue

        schema_by_node[node_id] = schema
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        declared_inputs = set(raw_schema_inputs)
        provided_inputs = set(node.inputs) | set(node.widgets)
        connected_inputs = incoming.get(node_id, set())

        if not raw_schema_inputs:
            continue

        for name, spec in raw_schema_inputs.items():
            if getattr(spec, "required", False) and name not in provided_inputs and name not in connected_inputs:
                issues.append(
                    ValidationIssue(
                        "missing_required_input",
                        f"Node {node_id} ({node.class_type}) is missing required input {name}.",
                        detail={"node_id": node_id, "class_type": node.class_type, "input": name},
                    )
                )

        for name in sorted(provided_inputs - declared_inputs):
            if not _issue_suppressed(node.class_type, "unknown_input"):
                issues.append(
                    ValidationIssue(
                        "unknown_input",
                        f"Node {node_id} ({node.class_type}) has unknown input {name}.",
                        detail={"node_id": node_id, "class_type": node.class_type, "input": name},
                    )
                )

        for name in sorted(provided_inputs & declared_inputs):
            value = node.inputs[name] if name in node.inputs else node.widgets[name]
            if _is_api_link(value):
                continue
            spec = raw_schema_inputs[name]
            choices = getattr(spec, "choices", None) or []
            if choices and value not in choices and not _issue_suppressed(node.class_type, "value_not_in_enum"):
                issues.append(
                    ValidationIssue(
                        "value_not_in_enum",
                        f"Node {node_id} ({node.class_type}) input {name} value {_truncate(value)} is not one of the declared choices.",
                        severity="error",
                        detail={
                            "node_id": node_id,
                            "class_type": node.class_type,
                            "input": name,
                            "value": _truncate(value),
                            "choices": choices,
                        },
                    )
                )

            min_value = getattr(spec, "min", None)
            max_value = getattr(spec, "max", None)
            if (min_value is not None or max_value is not None) and not _issue_suppressed(
                node.class_type, "value_out_of_range"
            ):
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if (min_value is not None and numeric_value < float(min_value)) or (
                    max_value is not None and numeric_value > float(max_value)
                ):
                    issues.append(
                        ValidationIssue(
                            "value_out_of_range",
                            f"Node {node_id} ({node.class_type}) input {name} value {_truncate(value)} is outside the declared range.",
                            severity="error",
                            detail={
                                "node_id": node_id,
                                "class_type": node.class_type,
                                "input": name,
                                "value": _truncate(value),
                                "min": min_value,
                                "max": max_value,
                            },
                        )
                    )

    for edge in workflow.edges:
        from_schema = schema_by_node.get(edge.from_node)
        to_schema = schema_by_node.get(edge.to_node)
        if from_schema is None or to_schema is None:
            continue
        output_type = _edge_output_type(from_schema, edge.from_output)
        input_type = _edge_input_type(to_schema, edge.to_input)
        if output_type and input_type and not _types_compatible(output_type, input_type):
            issues.append(
                ValidationIssue(
                    "type_mismatch",
                    (
                        f"Edge {edge.from_node}.{edge.from_output} -> {edge.to_node}.{edge.to_input} "
                        f"connects {output_type} to {input_type}."
                    ),
                    severity="warning",
                    detail={
                        "from_node": edge.from_node,
                        "from_output": edge.from_output,
                        "to_node": edge.to_node,
                        "to_input": edge.to_input,
                        "output_type": output_type,
                        "input_type": input_type,
                    },
                )
            )

    return issues


def validate_api_link_shapes(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        schema = schema_for(provider, class_type)
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        for name, value in inputs.items():
            if not isinstance(value, dict):
                continue
            spec = raw_schema_inputs.get(name)
            if _schema_accepts_dict(spec):
                continue
            issues.append(
                ValidationIssue(
                    "invalid_link_shape",
                    f"Node {node_id} ({class_type}) input {name} has dict-shaped link; expected [node_id, output_index].",
                    severity="error",
                    detail={
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "input": name,
                        "value_repr": _truncate(value),
                    },
                )
            )
    return issues


def _incoming_inputs(workflow: VibeWorkflow) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {}
    for edge in workflow.edges:
        incoming.setdefault(edge.to_node, set()).add(edge.to_input)
    return incoming


def _edge_output_type(schema, from_output: str) -> str | None:
    outputs = getattr(schema, "outputs", None) or []
    try:
        index = int(from_output)
    except (TypeError, ValueError):
        index = None
    if index is not None and 0 <= index < len(outputs):
        return _normalize_type(getattr(outputs[index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == from_output:
            return _normalize_type(getattr(output, "type", None))
    return None


def _edge_input_type(schema, to_input: str) -> str | None:
    spec = (getattr(schema, "inputs", {}) or {}).get(to_input)
    if spec is None:
        return None
    return _normalize_type(getattr(spec, "type", None))


def _normalize_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text == "*":
        return None
    return text


def _types_compatible(output_type: str, input_type: str) -> bool:
    if output_type == input_type:
        return True
    if output_type in {"*", "ANY"} or input_type in {"*", "ANY"}:
        return True
    return False


def _is_api_link(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _truncate(value: Any, n: int = 120) -> str:
    text = repr(value)
    if len(text) <= n:
        return text
    return text[: max(0, n - 3)] + "..."


def _issue_suppressed(class_type: str, code: str) -> bool:
    if class_type not in SCHEMA_VALIDATION_SKIP_CLASSES:
        return False
    return code == "unknown_input" or code.startswith("value_")


def _schema_accepts_dict(spec: Any) -> bool:
    typ = getattr(spec, "type", None)
    if typ is None:
        return False
    return str(typ).strip().upper() in {"DICT", "*"}
