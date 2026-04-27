from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def build_api_ready_workflow(
    api_workflow: dict[str, Any],
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    workflow_id: str | None = None,
    requirements: Mapping[str, list[Any]] | None = None,
) -> VibeWorkflow:
    metadata = dict(ready_metadata)
    workflow = convert_to_vibe_format(
        api_workflow,
        source_path=source_path,
        workflow_id=workflow_id or metadata.get("ready_template") or Path(source_path).stem,
    )
    return apply_ready_template_policy(
        workflow,
        metadata,
        source_path=source_path,
        requirements=requirements,
    )


def apply_ready_template_policy(
    workflow: VibeWorkflow,
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, list[Any]] | None = None,
) -> VibeWorkflow:
    workflow.metadata.update(dict(ready_metadata))
    workflow.metadata["ready_template_path"] = source_path
    workflow.metadata["python_policy_applied"] = True
    if not workflow.nodes:
        raise ValueError("ready template produced no nodes")
    if requirements:
        _merge_requirements(workflow, requirements)
    return workflow


def apply_authored_metadata(
    workflow: VibeWorkflow,
    ready_metadata: Mapping[str, Any],
    *,
    requirements: Mapping[str, list[Any]] | None = None,
    source_path: str,
) -> VibeWorkflow:
    workflow.finalize_metadata()
    return apply_ready_template_policy(
        workflow,
        ready_metadata,
        source_path=source_path,
        requirements=requirements,
    )


def build_authored_ready_workflow(
    nodes: tuple[tuple[str, str, dict[str, Any]], ...],
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    workflow_id: str | None = None,
    requirements: Mapping[str, list[Any]] | None = None,
    registered_inputs: Mapping[str, tuple[str, str]] | None = None,
) -> VibeWorkflow:
    metadata = dict(ready_metadata)
    workflow = VibeWorkflow(
        workflow_id or str(metadata.get("ready_template") or Path(source_path).stem),
        WorkflowSource(
            id=workflow_id or str(metadata.get("ready_template") or Path(source_path).stem),
            path=source_path,
            source_type="ready_template",
        ),
    )
    node_ids = {old_id for old_id, _, _ in nodes}
    handles: dict[tuple[str, int], Handle] = {}
    old_to_new: dict[str, str] = {}

    for old_id, class_type, inputs in nodes:
        kwargs = {
            name: _authored_value(value, handles, node_ids)
            for name, value in dict(inputs).items()
        }
        builder = workflow.node(class_type, **kwargs)
        temp_id = builder.id
        if temp_id != old_id:
            node = workflow.nodes.pop(temp_id)
            node.id = old_id
            workflow.nodes[old_id] = node
            for edge in workflow.edges:
                if edge.to_node == temp_id:
                    edge.to_node = old_id
        old_to_new[old_id] = old_id
        for slot in _referenced_output_slots(nodes, old_id):
            handles[(old_id, slot)] = builder.out(slot)
        handles.setdefault((old_id, 0), builder.out(0))

    apply_authored_metadata(workflow, metadata, source_path=source_path, requirements=requirements)
    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        new_id = old_to_new[old_id]
        node = workflow.nodes[new_id]
        value = node.inputs.get(field, node.widgets.get(field))
        workflow.register_input(input_name, new_id, field, value)
    return workflow


def _authored_value(value: Any, handles: Mapping[tuple[str, int], Handle], node_ids: set[str]) -> Any:
    if _is_authored_link(value, node_ids):
        key = (str(value[0]), int(value[1]))
        return handles.get(key) or Handle(node_id=key[0], output_slot=key[1])
    return value


def _referenced_output_slots(nodes: tuple[tuple[str, str, dict[str, Any]], ...], old_id: str) -> set[int]:
    node_ids = {node_id for node_id, _, _ in nodes}
    slots = {0}
    for _, _, inputs in nodes:
        for value in inputs.values():
            if _is_authored_link(value, node_ids) and str(value[0]) == old_id:
                slots.add(int(value[1]))
    return slots


def _is_authored_link(value: Any, node_ids: set[str]) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]) in node_ids and isinstance(value[1], int)


def _merge_requirements(workflow: VibeWorkflow, requirements: Mapping[str, list[Any]]) -> None:
    for model in requirements.get("models", []):
        if isinstance(model, Mapping):
            name = model.get("name")
            if not isinstance(name, str) or not name:
                continue
            if name not in workflow.requirements.models:
                workflow.requirements.models.append(name)
            _append_model_asset(workflow, model)
        elif isinstance(model, str) and model not in workflow.requirements.models:
            workflow.requirements.models.append(model)
    for custom_node in requirements.get("custom_nodes", []):
        if custom_node not in workflow.requirements.custom_nodes:
            workflow.requirements.custom_nodes.append(custom_node)
    workflow.requirements.models.sort()
    workflow.requirements.custom_nodes.sort()


def _append_model_asset(workflow: VibeWorkflow, asset: Mapping[str, Any]) -> None:
    model_assets = workflow.metadata.setdefault("model_assets", [])
    if not isinstance(model_assets, list):
        model_assets = []
        workflow.metadata["model_assets"] = model_assets
    key = (asset.get("name"), asset.get("subdir"))
    if any(isinstance(existing, Mapping) and (existing.get("name"), existing.get("subdir")) == key for existing in model_assets):
        return
    model_assets.append(dict(asset))


_MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".gguf", ".pt", ".bin", ".pth")


def _referenced_model_filenames(workflow: VibeWorkflow) -> set[str]:
    filenames: set[str] = set()
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and value.endswith(_MODEL_EXTENSIONS):
                filenames.add(value)
                filenames.add(Path(value.replace("\\", "/")).name)
    return filenames


def finalise_model_assets(workflow: VibeWorkflow) -> None:
    referenced = _referenced_model_filenames(workflow)
    raw_assets = workflow.metadata.get("model_assets", [])
    extra_assets = workflow.metadata.pop("model_assets_extra", [])
    replaced_by_policy = set(workflow.metadata.pop("model_assets_replaced_by_policy", []))
    filtered = [
        asset
        for asset in raw_assets
        if isinstance(asset, dict)
        and isinstance(asset.get("name"), str)
        and asset["name"] not in replaced_by_policy
        and (asset["name"] in referenced or _asset_name_appears_in_workflow_text(workflow, asset["name"]))
    ]
    combined = filtered + [asset for asset in extra_assets if isinstance(asset, dict)]
    final_assets: list[dict[str, Any]] = []
    seen: set[tuple[object, object]] = set()
    for asset in combined:
        key = (asset.get("name"), asset.get("subdir"))
        if key in seen:
            continue
        seen.add(key)
        final_assets.append(asset)
    workflow.metadata["model_assets"] = final_assets


def _asset_name_appears_in_workflow_text(workflow: VibeWorkflow, name: str) -> bool:
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and name in value:
                return True
    return False


_finalise_model_assets = finalise_model_assets


__all__ = [
    "apply_authored_metadata",
    "apply_ready_template_policy",
    "build_authored_ready_workflow",
    "build_api_ready_workflow",
    "finalise_model_assets",
    "_finalise_model_assets",
]
