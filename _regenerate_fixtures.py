"""Regenerate M6 fixture files after extraction work (T7-T11)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
from arnold_pipelines.megaplan.workflows import planning as workflow_planning
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.workflows import components as workflow_components
from types import MappingProxyType
from typing import Any
from importlib import import_module
import yaml


FIXTURES_DIR = Path(__file__).parent / "tests" / "arnold_pipelines" / "megaplan" / "fixtures"

MANIFEST_GOLDEN_PATH = FIXTURES_DIR / "megaplan_m4_manifest_golden.json"
TOPOLOGY_PATH = FIXTURES_DIR / "megaplan_m4_topology.yaml"
NORMALIZED_SHAPE_PATH = FIXTURES_DIR / "normalized_pipeline_shape.json"


def _resolve_component(ref: str) -> Any:
    module_name, export_name = ref.split(":", 1)
    module = import_module(module_name)
    return getattr(module, export_name)


def _collapse_branch_target(target: str) -> str:
    if target in {"halt", "gate_abort", "gate_suspend", "review_halt", "override_halt", "override_unknown"}:
        return "halt"
    if target in {"blocked_override", "tiebreaker_override"}:
        return "override"
    if target in {"review_revise", "override_revise"}:
        return "revise"
    if target.endswith("finalize") or target == "finalize":
        return "finalize"
    return target


def _normalize_plain(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, dict):
        return {key: _normalize_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_plain(item) for item in value]
    return value


def _io_contract(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        entry: dict[str, Any] = {"name": item.name}
        schema_hash = getattr(item, "schema_hash", None)
        value_ref = getattr(item, "value_ref", None)
        if schema_hash is not None:
            entry["schema_hash"] = schema_hash
        if value_ref is not None:
            entry["value_ref"] = value_ref
        if dict(getattr(item, "metadata", {}) or {}):
            entry["metadata"] = dict(item.metadata)
        result.append(entry)
    return result


def _capability_contract(capability: Any) -> dict[str, Any]:
    capability_id = getattr(capability, "id", None) or getattr(capability, "capability_id")
    return {
        "id": capability_id,
        "route": capability.route,
        "required": capability.required,
    }


def _policy_contract(policy: Any | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    result: dict[str, Any] = {}
    if policy.loop is not None:
        result["loop"] = {
            "max_iterations": policy.loop.max_iterations,
            "until_ref": policy.loop.until_ref,
        }
    if policy.timing is not None:
        result["timing"] = {"timeout_seconds": policy.timing.timeout_seconds}
    if policy.control_transitions:
        result["control_transitions"] = [
            {
                "transition_id": slot.transition_id,
                "transition_type": slot.transition_type,
                "trigger_ref": slot.trigger_ref,
                "target_ref": slot.target_ref,
                "policy_ref": slot.policy_ref,
            }
            for slot in policy.control_transitions
        ]
    if policy.suspension_routes:
        routes: list[dict[str, Any]] = []
        for route in policy.suspension_routes:
            entry = {
                "route_id": route.route_id,
                "capability_id": route.capability_id,
            }
            if route.reentry_id is not None:
                entry["reentry_id"] = route.reentry_id
            routes.append(entry)
        result["suspension_routes"] = routes
    return result


def _subpipeline_contract(subpipeline: Any | None) -> dict[str, Any] | None:
    if subpipeline is None:
        return None
    return {
        "manifest_hash": subpipeline.manifest_hash,
        "alias": subpipeline.alias,
    }


def _normalized_pipeline_contract(pipeline: Any) -> dict[str, Any]:
    return {
        "fixture_schema": "arnold.megaplan.normalized_pipeline_shape.v1",
        "source": "arnold_pipelines.megaplan.pipeline:build_pipeline",
        "hash_neutral": True,
        "pipeline": {
            "id": pipeline.id,
            "version": pipeline.version,
            "metadata": dict(pipeline.metadata),
            "policy": _policy_contract(pipeline.policy),
        },
        "counts": {
            "steps": len(pipeline.steps),
            "routes": len(pipeline.routes),
            "capabilities": len(pipeline.capabilities),
        },
        "ordered_step_ids": [step.id for step in pipeline.steps],
        "steps": [
            {
                "id": step.id,
                "kind": step.kind,
                "inputs": _io_contract(step.inputs),
                "outputs": _io_contract(step.outputs),
                "capabilities": [_capability_contract(capability) for capability in step.capabilities],
                "policy": _policy_contract(step.policy),
                "handler_ref": step.metadata.get("handler_ref"),
                "terminal": bool(step.metadata.get("terminal", False)),
                "subpipeline": _subpipeline_contract(step.subpipeline),
                "metadata": dict(step.metadata),
            }
            for step in pipeline.steps
        ],
        "capabilities": [_capability_contract(capability) for capability in pipeline.capabilities],
        "routes": [
            {
                "id": route.id,
                "source": route.source,
                "target": route.target,
                "label": route.label,
                "condition_ref": route.condition_ref,
                "metadata": dict(route.metadata),
            }
            for route in pipeline.routes
        ],
    }


def _canonical_authored_topology() -> dict[str, Any]:
    lowered = lower_workflow_file(workflow_planning.AUTHORING_SOURCE_PATH)
    semantic_nodes = [
        "prep",
        "plan",
        "critique-fanout",
        "gate",
        "revise",
        "tiebreaker",
        "finalize",
        "execute-batches",
        "review-fan-in",
        "override",
        "tiebreaker-execute-batches",
        "execute",
        "halt",
    ]

    def _routes_for(source_id: str) -> list[dict[str, Any]]:
        return [
            {
                "route_id": route.id,
                "label": route.label,
                "target": _collapse_branch_target(route.target),
                "lowered_target": route.target,
                "condition_ref": route.condition_ref,
            }
            for route in lowered.routes
            if route.source == source_id
        ]

    dynamic_maps = []
    for step in lowered.steps:
        if step.kind != "parallel_map":
            continue
        component = _resolve_component(step.metadata["mapper_ref"])
        dynamic_maps.append(
            {
                "id": step.id,
                "items_ref": step.metadata["items_ref"],
                "mapper_ref": step.metadata["mapper_ref"],
                "reducer_ref": step.metadata["reducer_ref"],
                "path_template": step.metadata["path_template"],
                "iteration_coordinate": step.metadata["iteration_coordinate"],
                "call_site_path": step.metadata["call_site_path"],
                "topology_contract": _normalize_plain(component.metadata.get("topology_contract", {})),
            }
        )

    child_workflows = []
    for step in lowered.steps:
        if step.kind != "subpipeline":
            continue
        component = _resolve_component(step.metadata["component_ref"])
        child_workflows.append(
            {
                "id": step.id,
                "child_workflow_id": step.metadata["child_workflow_id"],
                "call_site_path": step.metadata["call_site_path"],
                "parent_path": step.metadata["parent_path"],
                "inputs_schema": list(step.metadata["inputs_schema"]),
                "outputs_schema": list(step.metadata["outputs_schema"]),
                "topology_contract": _normalize_plain(component.metadata.get("topology_contract", {})),
            }
        )

    return {
        "source_path": "arnold_pipelines/megaplan/workflows/workflow.py",
        "workflow_id": lowered.id,
        "workflow_version": lowered.version,
        "semantic_nodes": semantic_nodes,
        "excluded_wrapper_nodes": sorted(
            step.id for step in lowered.steps if step.id not in set(semantic_nodes)
        ),
        "gate_routes": _routes_for("gate"),
        "review_routes": _routes_for("review-fan-in"),
        "override_routes": _routes_for("override"),
        "tiebreaker_routes": _routes_for("tiebreaker"),
        "dynamic_maps": dynamic_maps,
        "child_workflows": child_workflows,
        "suspension_routes": {
            "gate": _normalize_plain(
                list(workflow_components.STEP_COMPONENTS_BY_ID["gate"].policy.config["suspension_routes"])
            ),
            "review": _normalize_plain(
                list(workflow_components.STEP_COMPONENTS_BY_ID["review"].policy.config["suspension_routes"])
            ),
            "tiebreaker": _normalize_plain(
                list(
                workflow_components.STEP_COMPONENTS_BY_ID["tiebreaker_decide"].policy.config["suspension_routes"]
                )
            ),
        },
    }


def _canonical_manifest_json(manifest: Any) -> str:
    payload = json.loads(manifest.to_json())
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main():
    manifest = build_and_compile_pipeline()
    pipeline = build_pipeline()

    new_manifest_hash = manifest.manifest_hash
    new_topology_hash = manifest.topology_hash

    print(f"new manifest_hash:  {new_manifest_hash}")
    print(f"new topology_hash:  {new_topology_hash}")

    # 1. Regenerate manifest golden JSON
    manifest_json = _canonical_manifest_json(manifest)
    MANIFEST_GOLDEN_PATH.write_text(manifest_json, encoding="utf-8")
    print(f"Wrote {MANIFEST_GOLDEN_PATH} ({len(manifest_json)} bytes)")

    # 2. Regenerate topology YAML
    authored_topology = _canonical_authored_topology()
    topology = {
        "manifest_id": manifest.id,
        "manifest_hash": new_manifest_hash,
        "topology_hash": new_topology_hash,
        "nodes": [step.id for step in pipeline.steps],
        "capabilities": [c.id for c in pipeline.capabilities],
        "gate_targets": [
            {"label": e.label, "target": e.target}
            for e in manifest.edges
            if e.source == "gate"
        ],
        "tiebreaker_targets": [
            {"label": e.label, "target": e.target}
            for e in manifest.edges
            if e.source == "tiebreaker_decide"
        ],
        "review_targets": [
            {"label": e.label, "target": e.target}
            for e in manifest.edges
            if e.source == "review"
        ],
        "canonical_authoring": authored_topology,
    }
    with TOPOLOGY_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(topology, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Wrote {TOPOLOGY_PATH}")

    # 3. Regenerate normalized pipeline shape
    normalized = _normalized_pipeline_contract(pipeline)
    NORMALIZED_SHAPE_PATH.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {NORMALIZED_SHAPE_PATH}")

    print("\n=== NEW LOCKED CONSTANTS ===")
    print(f'LOCKED_MANIFEST_HASH = "{new_manifest_hash}"')
    print(f'LOCKED_TOPOLOGY_HASH = "{new_topology_hash}"')


if __name__ == "__main__":
    main()
