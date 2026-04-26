from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.workflow import VibeWorkflow


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


__all__ = ["apply_ready_template_policy", "build_api_ready_workflow"]
