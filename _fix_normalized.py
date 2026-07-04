"""Regenerate normalized_pipeline_shape.json using the test file's own contract function."""
import json, sys

sys.path.insert(0, '/workspace/native-composition-followup/Arnold')
sys.path.insert(0, '/workspace/native-composition-followup/Arnold/tests/arnold_pipelines/megaplan')

# Replicate the exact functions from test_topology_golden.py
from types import MappingProxyType
from typing import Any

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
    if policy is None: return None
    result: dict[str, Any] = {}
    if policy.loop is not None:
        result["loop"] = {"max_iterations": policy.loop.max_iterations, "until_ref": policy.loop.until_ref}
    if policy.timing is not None:
        result["timing"] = {"timeout_seconds": policy.timing.timeout_seconds}
    if policy.control_transitions:
        result["control_transitions"] = [
            {"transition_id": slot.transition_id, "transition_type": slot.transition_type, "trigger_ref": slot.trigger_ref, "target_ref": slot.target_ref, "policy_ref": slot.policy_ref}
            for slot in policy.control_transitions
        ]
    if policy.suspension_routes:
        routes: list[dict[str, Any]] = []
        for route in policy.suspension_routes:
            entry = {"route_id": route.route_id, "capability_id": route.capability_id}
            if route.reentry_id is not None: entry["reentry_id"] = route.reentry_id
            routes.append(entry)
        result["suspension_routes"] = routes
    return result

def _subpipeline_contract(subpipeline: Any | None) -> dict[str, Any] | None:
    if subpipeline is None: return None
    return {"manifest_hash": subpipeline.manifest_hash, "alias": subpipeline.alias}

def _normalized_pipeline_contract(pipeline: Any) -> dict[str, Any]:
    return {
        "fixture_schema": "arnold.megaplan.normalized_pipeline_shape.v1",
        "source": "arnold_pipelines.megaplan.pipeline:build_pipeline",
        "hash_neutral": True,
        "pipeline": {"id": pipeline.id, "version": pipeline.version, "metadata": dict(pipeline.metadata), "policy": _policy_contract(pipeline.policy)},
        "counts": {"steps": len(pipeline.steps), "routes": len(pipeline.routes), "capabilities": len(pipeline.capabilities)},
        "ordered_step_ids": [step.id for step in pipeline.steps],
        "steps": [
            {"id": step.id, "kind": step.kind, "inputs": _io_contract(step.inputs), "outputs": _io_contract(step.outputs), "capabilities": [_capability_contract(c) for c in step.capabilities], "policy": _policy_contract(step.policy), "handler_ref": step.metadata.get("handler_ref"), "terminal": bool(step.metadata.get("terminal", False)), "subpipeline": _subpipeline_contract(step.subpipeline), "metadata": dict(step.metadata)}
            for step in pipeline.steps
        ],
        "capabilities": [_capability_contract(c) for c in pipeline.capabilities],
        "routes": [
            {"id": route.id, "source": route.source, "target": route.target, "label": route.label, "condition_ref": route.condition_ref, "metadata": dict(route.metadata)}
            for route in pipeline.routes
        ],
    }

from arnold_pipelines.megaplan.pipeline import build_pipeline
from arnold_pipelines.megaplan.workflows import planning as workflow_planning

# Use pipeline facade builder (same as test)
result = _normalized_pipeline_contract(build_pipeline())

path = '/workspace/native-composition-followup/Arnold/tests/arnold_pipelines/megaplan/fixtures/normalized_pipeline_shape.json'
with open(path, 'w') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(f'Wrote {path}')

# Verify
with open(path) as f:
    verify = json.load(f)
print(f'Match: {json.dumps(verify, sort_keys=True) == json.dumps(result, sort_keys=True)}')
