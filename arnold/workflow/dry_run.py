"""Dry-run view over a compiled workflow manifest.

Stability:
    public: ``dry_run`` stable data fields
    diagnostic-only: ``to_data`` formatting helper

A dry run reports possible control routes and unresolved inputs without
executing steps, hooks, prompt builders, reducers, or any runtime workflow code.
"""

from __future__ import annotations

from typing import Any

from arnold.manifest.manifests import WorkflowManifest


def dry_run(manifest: WorkflowManifest) -> dict[str, Any]:
    """Return a stable, serializable dry-run report for ``manifest``.

    Fields:
      - ``id``: manifest alias.
      - ``manifest_hash``: runtime identity hash.
      - ``node_count``: number of nodes.
      - ``edge_count``: number of edges.
      - ``possible_routes``: forward control routes the runner may traverse.
      - ``unresolved_inputs``: inputs with no bound ``value_ref``.
      - ``suspension_point_count``: number of suspension routes.
      - ``topology_summary``: node/edge counts and entry/exit sets.
    """

    possible_routes = tuple(
        {
            "source": edge.source,
            "target": edge.target,
            "label": edge.label,
            "condition_ref": edge.condition_ref,
        }
        for edge in manifest.edges
    )
    unresolved_inputs: dict[str, tuple[str, ...]] = {}
    suspension_count = 0
    for node in manifest.nodes:
        bindings = node.metadata.get("input_bindings", {})
        unresolved = tuple(
            name
            for name, meta in bindings.items()
            if not (isinstance(meta, dict) and meta.get("value_ref"))
        )
        if unresolved:
            unresolved_inputs[node.id] = unresolved
        if node.policy is not None:
            suspension_count += len(node.policy.suspension_routes)
    if manifest.policy is not None:
        suspension_count += len(manifest.policy.suspension_routes)

    sources = {edge.source for edge in manifest.edges}
    targets = {edge.target for edge in manifest.edges}
    topology_summary = {
        "node_count": len(manifest.nodes),
        "edge_count": len(manifest.edges),
        "entry_nodes": tuple(sorted(node.id for node in manifest.nodes if node.id not in targets)),
        "exit_nodes": tuple(sorted(node.id for node in manifest.nodes if node.id not in sources)),
    }

    return {
        "id": manifest.id,
        "manifest_hash": manifest.manifest_hash,
        "node_count": len(manifest.nodes),
        "edge_count": len(manifest.edges),
        "possible_routes": possible_routes,
        "unresolved_inputs": unresolved_inputs,
        "suspension_point_count": suspension_count,
        "topology_summary": topology_summary,
    }


def to_data(report: dict[str, Any]) -> dict[str, Any]:
    """Return the dry-run report unchanged for JSON/YAML serialization."""

    return dict(report)
