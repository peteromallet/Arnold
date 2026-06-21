"""Stable inspect views over a compiled workflow manifest.

Stability:
    public: ``inspect_manifest`` stable data fields
    diagnostic-only: ``to_dot`` and ``to_yaml`` formatting helpers

These helpers never execute steps, hooks, prompt builders, reducers, or any
workflow topology code.  They report the durable coordinates carried by the
manifest and any unresolved inputs that would need to be supplied at runtime.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from arnold.workflow.manifests import WorkflowManifest
from arnold.workflow.refs import EdgeRef, NodeRef, ValueRef


def inspect_manifest(manifest: WorkflowManifest) -> dict[str, Any]:
    """Return a stable, serializable inspect view of ``manifest``.

    Fields:
      - ``node_ids``: tuple of manifest node IDs.
      - ``refs``: durable refs for nodes and edges.
      - ``dependencies``: per-node value dependencies derived from input bindings.
      - ``capabilities``: per-node and manifest-level capability requirements.
      - ``control_routes``: edge-derived control routes.
      - ``suspension_points``: suspension routes with reentry IDs.
      - ``unresolved_inputs``: inputs that have no declared ``value_ref``.
      - ``source_spans``: per-node and manifest-level source spans.
      - ``hash_inputs``: topology and manifest hash inputs used for identity.
    """

    nodes_by_id = {node.id: node for node in manifest.nodes}
    refs: dict[str, Any] = {
        "nodes": tuple(NodeRef(node.id).key for node in manifest.nodes),
        "edges": tuple(
            EdgeRef(NodeRef(edge.source), NodeRef(edge.target), edge.label).key
            for edge in manifest.edges
        ),
    }
    dependencies: dict[str, tuple[str, ...]] = {}
    unresolved_inputs: dict[str, tuple[str, ...]] = {}
    source_spans: dict[str, Any] = {}
    if manifest.source_span is not None:
        source_spans["__manifest__"] = asdict(manifest.source_span)
    for node in manifest.nodes:
        bindings = node.metadata.get("input_bindings", {})
        deps: list[str] = []
        unresolved: list[str] = []
        for name, meta in bindings.items():
            value_ref = meta.get("value_ref") if isinstance(meta, Mapping) else None
            if value_ref:
                deps.append(ValueRef(NodeRef(node.id), name).key)
            else:
                unresolved.append(name)
        dependencies[node.id] = tuple(deps)
        if unresolved:
            unresolved_inputs[node.id] = tuple(unresolved)
        if node.source_span is not None:
            source_spans[node.id] = asdict(node.source_span)

    capabilities: dict[str, Any] = {
        "manifest": tuple(
            {"capability_id": cap.capability_id, "route": cap.route, "required": cap.required}
            for cap in manifest.capabilities
        ),
        "nodes": {
            node.id: tuple(
                {"capability_id": cap.capability_id, "route": cap.route, "required": cap.required}
                for cap in node.capabilities
            )
            for node in manifest.nodes
        },
    }
    control_routes = tuple(
        {
            "id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "label": edge.label,
            "condition_ref": edge.condition_ref,
        }
        for edge in manifest.edges
    )
    suspension_points: list[dict[str, Any]] = []
    for node in manifest.nodes:
        if node.policy is None:
            continue
        for route in node.policy.suspension_routes:
            suspension_points.append(
                {
                    "node_id": node.id,
                    "route_id": route.route_id,
                    "capability_id": route.capability_id,
                    "reentry_id": route.reentry_id,
                    "payload_schema_hash": route.payload_schema_hash,
                }
            )
    if manifest.policy is not None:
        for route in manifest.policy.suspension_routes:
            suspension_points.append(
                {
                    "node_id": None,
                    "route_id": route.route_id,
                    "capability_id": route.capability_id,
                    "reentry_id": route.reentry_id,
                    "payload_schema_hash": route.payload_schema_hash,
                }
            )

    hash_inputs = {
        "id": manifest.id,
        "schema_version": manifest.schema_version,
        "version": manifest.version,
        "topology_hash": manifest.topology_hash,
        "manifest_hash": manifest.manifest_hash,
    }

    return {
        "node_ids": tuple(nodes_by_id.keys()),
        "refs": refs,
        "dependencies": dependencies,
        "capabilities": capabilities,
        "control_routes": control_routes,
        "suspension_points": tuple(suspension_points),
        "unresolved_inputs": unresolved_inputs,
        "source_spans": source_spans,
        "hash_inputs": hash_inputs,
    }


def to_dot(manifest: WorkflowManifest) -> str:
    """Return a diagnostic DOT graph rendering of the manifest topology."""

    lines = ["digraph workflow {"]
    for node in manifest.nodes:
        label = node.label or node.id
        lines.append(f'  "{node.id}" [label="{label}"];')
    for edge in manifest.edges:
        label = edge.label
        if edge.condition_ref:
            label = f"{label}:{edge.condition_ref}"
        lines.append(f'  "{edge.source}" -> "{edge.target}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


def to_yaml(data: Any) -> str:
    """Return a diagnostic YAML rendering of inspect/dry-run data.

    Falls back to JSON with a leading comment when PyYAML is unavailable.
    """

    try:
        import yaml

        return yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
    except Exception:  # noqa: BLE001 - formatting helper is diagnostic-only.
        import json

        return "# YAML unavailable; using JSON fallback\n" + json.dumps(data, sort_keys=True, indent=2)
