from __future__ import annotations

from pathlib import Path
from typing import Any

from vibecomfy.metadata import (
    OUTPUT_NODE_NAMES,
    _infer_requirements,
    _register_common_inputs,
)
from vibecomfy.schema import SchemaProvider, schema_for
from vibecomfy.workflow import VibeEdge, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


def detect_workflow_shape(raw: dict[str, Any]) -> str:
    if "prompt" in raw and isinstance(raw["prompt"], dict):
        return detect_workflow_shape(raw["prompt"])
    if isinstance(raw.get("nodes"), list):
        return "ui"
    if raw and all(isinstance(value, dict) and "class_type" in value for value in raw.values()):
        return "api"
    return "unknown"


def normalize_to_api(raw: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> dict[str, Any]:
    shape = detect_workflow_shape(raw)
    if shape == "api":
        return raw.get("prompt", raw)
    if shape != "ui":
        raise ValueError(f"Unsupported workflow shape: {shape}")

    try:
        from comfy.component_model.workflow_convert import convert_ui_to_api
    except ImportError:
        pass
    else:
        return convert_ui_to_api(raw)

    nodes = {str(node["id"]): node for node in raw.get("nodes", []) if isinstance(node, dict) and "id" in node}
    links = raw.get("links", [])
    link_map: dict[int, tuple[str, int]] = {}
    for link in links:
        if isinstance(link, list) and len(link) >= 4:
            link_map[int(link[0])] = (str(link[1]), int(link[2]))
        elif isinstance(link, dict) and {"id", "origin_id", "origin_slot"} <= set(link):
            link_map[int(link["id"])] = (str(link["origin_id"]), int(link["origin_slot"]))

    api: dict[str, Any] = {}
    for node_id, node in nodes.items():
        inputs: dict[str, Any] = {}
        class_type = str(node.get("type", "Unknown"))
        for input_item in node.get("inputs", []) or []:
            if not isinstance(input_item, dict):
                continue
            name = input_item.get("name")
            link_id = input_item.get("link")
            if name and link_id in link_map:
                inputs[name] = [link_map[link_id][0], link_map[link_id][1]]
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, list):
            widget_names = _schema_input_names(schema_provider, class_type)
            for idx, value in enumerate(widgets):
                name = widget_names[idx] if idx < len(widget_names) else f"widget_{idx}"
                if name in inputs:
                    continue
                inputs[name] = value
        api[node_id] = {"class_type": class_type, "inputs": inputs, "_ui": node}
    return api


def convert_to_vibe_format(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    if detect_workflow_shape(api_workflow) != "api":
        api_workflow = normalize_to_api(api_workflow, schema_provider=schema_provider)
    source = WorkflowSource(
        id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
        path=source_path,
        source_type="api",
    )
    workflow = VibeWorkflow(id=source.id, source=source)
    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        raw_inputs = dict(node.get("inputs", {}))
        inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        for key, value in raw_inputs.items():
            if _is_link(value):
                continue
            if key.startswith("widget_"):
                widgets[key] = value
            else:
                inputs[key] = value
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=str(node.get("class_type", "Unknown")),
            inputs=inputs,
            widgets=widgets,
            metadata={key: value for key, value in node.items() if key not in {"class_type", "inputs"}},
        )
        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))

    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        for name, value in dict(node.get("inputs", {})).items():
            if _is_link(value):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)
    return workflow


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]).isdigit()


def _schema_input_names(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    schema = schema_for(schema_provider, class_type)
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    return list(inputs)
