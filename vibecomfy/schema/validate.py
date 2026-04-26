from __future__ import annotations

from typing import Any

from vibecomfy.schema.provider import SchemaProvider, schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


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
            issues.append(
                ValidationIssue(
                    "unknown_input",
                    f"Node {node_id} ({node.class_type}) has unknown input {name}.",
                    detail={"node_id": node_id, "class_type": node.class_type, "input": name},
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
