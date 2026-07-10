from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.workflow import VibeEdge, VibeInput, VibeNode, VibeOutput, VibeWorkflow


@dataclass(slots=True)
class EdgeSource:
    """Resolved source of an edge feeding a target node input.

    ``from_node`` (aliased from ``node_id``) is ``None`` when the input
    is widget-fed (no edge source).
    """

    node_id: str | None
    output_slot: int | None = None
    edge: VibeEdge | None = None

    @property
    def from_node(self) -> str | None:
        """Alias for ``node_id`` — the source node id."""
        return self.node_id


@dataclass(slots=True)
class EdgeTarget:
    """Resolved target of an edge departing from a source node."""

    to_node: str
    to_input: str
    edge: VibeEdge


@dataclass
class WorkflowLens:
    """Semantic graph lens over a ``VibeWorkflow``.

    All queries operate directly on workflow nodes/edges/inputs/outputs
    without calling ``compile()``.  Use the module-level convenience
    functions for stateless access.
    """

    workflow: VibeWorkflow

    # ── node lookup ──────────────────────────────────────────────────

    def node(self, node_id: str) -> VibeNode | None:
        return self.workflow.nodes.get(str(node_id))

    # ── edge queries ─────────────────────────────────────────────────

    def edge_source(self, to_node: str, to_input: str) -> EdgeSource | None:
        """Return the source feeding a target node input, or None when widget-fed."""
        for edge in self.workflow.edges:
            if str(edge.to_node) == str(to_node) and edge.to_input == to_input:
                return EdgeSource(node_id=str(edge.from_node), output_slot=int(edge.from_output), edge=edge)
        return None

    def edge_targets(self, from_node: str) -> list[EdgeTarget]:
        """All edge targets departing from *from_node*."""
        return [
            EdgeTarget(to_node=str(edge.to_node), to_input=edge.to_input, edge=edge)
            for edge in self.workflow.edges
            if str(edge.from_node) == str(from_node)
        ]

    def edges_to_node(self, node_id: str) -> list[VibeEdge]:
        """All edges whose target is *node_id*."""
        nid = str(node_id)
        return [edge for edge in self.workflow.edges if str(edge.to_node) == nid]

    def edges_from_node(self, node_id: str) -> list[VibeEdge]:
        """All edges whose source is *node_id*."""
        nid = str(node_id)
        return [edge for edge in self.workflow.edges if str(edge.from_node) == nid]

    # ── registered input target ──────────────────────────────────────

    def registered_input_target(self, name: str) -> VibeInput | None:
        """Return the ``VibeInput`` registered under *name*."""
        return self.workflow.inputs.get(name)

    # ── traversal ────────────────────────────────────────────────────

    def upstream_nodes(self, node_id: str) -> set[str]:
        """Set of node IDs with an edge directly into *node_id*."""
        return {str(edge.from_node) for edge in self.edges_to_node(node_id)}

    def upstream(self, node_id: str) -> set[str]:
        """Alias for :meth:`upstream_nodes`."""
        return self.upstream_nodes(node_id)

    def downstream_nodes(self, node_id: str) -> set[str]:
        """Set of node IDs that *node_id* has an edge directly into."""
        return {str(edge.to_node) for edge in self.edges_from_node(node_id)}

    def downstream(self, node_id: str) -> set[str]:
        """Alias for :meth:`downstream_nodes`."""
        return self.downstream_nodes(node_id)

    # ── output discovery ─────────────────────────────────────────────

    def outputs(self) -> list[VibeOutput]:
        return list(self.workflow.outputs)

    # ── node value ───────────────────────────────────────────────────

    def node_value(self, node_id: str, field: str) -> Any:
        """Read a widget or input value from a node, or ``None`` if missing."""
        node = self.node(node_id)
        if node is None:
            return None
        if field in node.inputs:
            return node.inputs[field]
        if field in node.widgets:
            return node.widgets[field]
        return None

    # ── filter by class_type ─────────────────────────────────────────

    def nodes_by_class_type(self, class_type: str) -> list[VibeNode]:
        return [node for node in self.workflow.nodes.values() if node.class_type == class_type]

    # ── diagnostics ──────────────────────────────────────────────────

    def diagnostics(self) -> str:
        """Human-readable text summary of the workflow graph."""
        wf = self.workflow
        lines: list[str] = []
        lines.append(f"Workflow: {wf.id}")
        lines.append(f"  nodes: {len(wf.nodes)}")
        lines.append(f"  edges: {len(wf.edges)}")
        inp_names = sorted(wf.inputs.keys())
        lines.append(f"  inputs ({len(inp_names)}): {', '.join(inp_names)}")
        out_strs = [f"{o.node_id}:{o.output_type}" for o in wf.outputs]
        lines.append(f"  outputs ({len(out_strs)}): {', '.join(out_strs)}")
        lines.append("")
        for nid in sorted(wf.nodes.keys(), key=lambda x: (int(x) if x.isdigit() else 0, x)):
            node = wf.nodes[nid]
            up = self.upstream_nodes(nid)
            down = self.downstream_nodes(nid)
            pack = f"[{node.pack}]" if node.pack else ""
            lines.append(f"  [{nid}] {node.class_type} {pack}  up={sorted(up)}  down={sorted(down)}")
        return "\n".join(lines)


# ── factory ────────────────────────────────────────────────────────────────


def lens(workflow: VibeWorkflow) -> WorkflowLens:
    """Create a ``WorkflowLens`` for *workflow* (convenience factory)."""
    return WorkflowLens(workflow)


# ── stateless convenience functions ──────────────────────────────────────────


def edge_source(workflow: VibeWorkflow, to_node: str, to_input: str) -> EdgeSource | None:
    return WorkflowLens(workflow).edge_source(to_node, to_input)


def edge_targets(workflow: VibeWorkflow, from_node: str) -> list[EdgeTarget]:
    return WorkflowLens(workflow).edge_targets(from_node)


def edges_from_node(workflow: VibeWorkflow, node_id: str) -> list[VibeEdge]:
    return WorkflowLens(workflow).edges_from_node(node_id)


def edges_to_node(workflow: VibeWorkflow, node_id: str) -> list[VibeEdge]:
    return WorkflowLens(workflow).edges_to_node(node_id)


def registered_input_target(workflow: VibeWorkflow, name: str) -> VibeInput | None:
    return WorkflowLens(workflow).registered_input_target(name)


def upstream_nodes(workflow: VibeWorkflow, node_id: str) -> set[str]:
    return WorkflowLens(workflow).upstream_nodes(node_id)


def upstream(workflow: VibeWorkflow, node_id: str) -> set[str]:
    """Alias for :func:`upstream_nodes`."""
    return upstream_nodes(workflow, node_id)


def downstream_nodes(workflow: VibeWorkflow, node_id: str) -> set[str]:
    return WorkflowLens(workflow).downstream_nodes(node_id)


def downstream(workflow: VibeWorkflow, node_id: str) -> set[str]:
    """Alias for :func:`downstream_nodes`."""
    return downstream_nodes(workflow, node_id)


def outputs(workflow: VibeWorkflow) -> list[VibeOutput]:
    return WorkflowLens(workflow).outputs()


def node_value(workflow: VibeWorkflow, node_id: str, field: str) -> Any:
    return WorkflowLens(workflow).node_value(node_id, field)


def nodes_by_class_type(workflow: VibeWorkflow, class_type: str) -> list[VibeNode]:
    return WorkflowLens(workflow).nodes_by_class_type(class_type)


def diagnostics(workflow: VibeWorkflow) -> str:
    return WorkflowLens(workflow).diagnostics()
