from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from vibecomfy.workflow import VibeWorkflow


def _coerce_json_safe(value: Any) -> Any:
    """Naive JSON coercion: Path→str, Enum→value, skip non-serializable objects."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {_coerce_json_safe(k): _coerce_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_json_safe(item) for item in value]
    # Skip non-serializable objects (dataclass instances, custom objects, etc.)
    return None


def _coerce_dict_values(d: dict[str, Any]) -> dict[str, Any]:
    """Coerce all values in a dict to JSON-safe types."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        coerced = _coerce_json_safe(value)
        if coerced is not None or value is None:
            result[str(key)] = coerced
    return result


@dataclass(slots=True)
class WorkflowRuntimeContract:
    """First-class workflow runtime contract payload (v1).

    Captures what a workflow declares it needs to run: provider/runtime requirements,
    model assets, custom nodes, inputs, outputs, and runtime class types.
    """

    version: int = 1
    workflow_id: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    readiness_level: str = "unknown"
    model_assets: list[dict[str, Any]] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    runtime_nodes: list[str] = field(default_factory=list)
    runtime_class_types: list[str] = field(default_factory=list)
    runtime_packages: list[dict[str, Any]] = field(default_factory=list)
    comfy_configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_contract(workflow: VibeWorkflow) -> WorkflowRuntimeContract:
    """Build a v1 JSON-serializable runtime contract from a VibeWorkflow.

    Derives payload from workflow fields: source, metadata, requirements, inputs,
    outputs, runtime_class_types(), and compile('api'). Falls back to
    requirements.models when metadata['model_assets'] is absent.
    """
    # Model assets: prefer metadata['model_assets'], fall back to requirements.models
    raw_model_assets = workflow.metadata.get("model_assets")
    if raw_model_assets and isinstance(raw_model_assets, list):
        model_assets = [
            _coerce_dict_values(asset) if isinstance(asset, dict) else {"name": str(asset)}
            for asset in raw_model_assets
        ]
    elif workflow.requirements.models:
        model_assets = [
            {"name": str(model_name)} for model_name in workflow.requirements.models
        ]
    else:
        model_assets = []

    # Runtime packages
    raw_runtime_packages = workflow.metadata.get("runtime_packages") or []
    if isinstance(raw_runtime_packages, list):
        runtime_packages = [
            _coerce_dict_values(pkg) if isinstance(pkg, dict) else {"name": str(pkg)}
            for pkg in raw_runtime_packages
        ]
    else:
        runtime_packages = []

    # Comfy configuration (descriptive, not validated)
    comfy_config = workflow.metadata.get("comfy_configuration")
    if isinstance(comfy_config, dict):
        comfy_configuration = _coerce_dict_values(comfy_config) or {}
    else:
        comfy_configuration = {}

    # Readiness level
    readiness_level = "unknown"
    if workflow.metadata.get("python_policy_applied"):
        readiness_level = "ready"
    elif workflow.metadata.get("ready_template"):
        readiness_level = "ready"

    # Input names
    inputs_list = sorted(workflow.inputs.keys())

    # Outputs
    outputs_list = []
    for output in workflow.outputs:
        out_dict: dict[str, Any] = {"node_id": str(output.node_id), "output_type": output.output_type}
        if output.name:
            out_dict["name"] = output.name
        outputs_list.append(out_dict)

    # Runtime class types
    runtime_rt = sorted(workflow.runtime_class_types())

    # Runtime node ids
    runtime_nodes_dict = workflow.runtime_nodes()
    runtime_node_ids = sorted(runtime_nodes_dict.keys())

    return WorkflowRuntimeContract(
        version=1,
        workflow_id=workflow.id,
        source=_coerce_dict_values(asdict(workflow.source)),
        readiness_level=readiness_level,
        model_assets=model_assets,
        custom_nodes=sorted(workflow.requirements.custom_nodes),
        inputs=inputs_list,
        outputs=outputs_list,
        runtime_nodes=runtime_node_ids,
        runtime_class_types=runtime_rt,
        runtime_packages=runtime_packages,
        comfy_configuration=comfy_configuration,
        metadata={
            "ready_template": workflow.metadata.get("ready_template"),
            "capability": workflow.metadata.get("capability"),
            "coverage_tier": workflow.metadata.get("coverage_tier"),
        },
    )
