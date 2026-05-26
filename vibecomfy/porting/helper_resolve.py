"""Fixed-point resolver that eliminates helper nodes from the VibeWorkflow IR.

Called by port_convert_workflow before emission.  Mutates workflow.nodes,
workflow.edges, and workflow.inputs in place.  Raises ConversionParityError on
any unresolvable helper so the caller never silently produces a corrupt graph.

Resolution phases (run in a fixed-point loop until stable):

  A — Broadcast pairs: GetNode edges are rewritten to the SetNode's upstream
      source.  Unmatched broadcast name → ConversionParityError.

  B — Passthroughs: Reroute/PrimitiveNode chains are followed transitively to
      the first non-passthrough terminal and consumer edges are rewritten.
      Dangling passthrough → ConversionParityError.

  C — Value primitives: literals are folded into consumer inputs.  Named
      single-consumer primitives (reached via a SetNode broadcast) are also
      registered as public inputs.  Named multi-consumer and unnamed primitives
      fold per consumer without registering.

After the loop, all resolved helper nodes are deleted and edges whose endpoints
no longer exist are filtered out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vibecomfy.errors import ConversionParityError
from vibecomfy.porting.helpers import (
    PASSTHROUGH_HELPER_CLASS_TYPES,
    RESOLVABLE_HELPER_CLASS_TYPES,
    VALUE_HELPER_CLASS_TYPES,
    HelperDiagnostic,
    broadcast_name,
    collect_broadcast_sources,
    _node_sort_key,
    _sorted_nodes,
)
from vibecomfy.porting.object_info import get_class
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow

# Valid Python identifier pattern; broadcast names that match are safe as
# register_input names.  Names equal to the primitive's own class_type are
# excluded to prevent accidental shadowing.
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class ResolveDiagnostics:
    diagnostics: list[HelperDiagnostic] = field(default_factory=list)


def resolve_helpers(
    workflow: VibeWorkflow,
    registered_inputs: dict[str, tuple[str, str]],
) -> ResolveDiagnostics:
    """Eliminate all helper nodes from *workflow*, mutating it in place.

    *registered_inputs* is populated with ``name -> (consumer_node_id,
    consumer_field)`` for every named single-consumer primitive that is
    promoted to a public input.

    Raises :exc:`~vibecomfy.errors.ConversionParityError` on any unresolvable
    helper node (unmatched broadcast, dangling passthrough, or unreachable
    consumer).
    """
    diagnostics: list[HelperDiagnostic] = []

    # Safety limit prevents infinite loops from pathological graphs.
    for _ in range(10_000):
        changed = False
        changed |= _phase_a_broadcasts(workflow, diagnostics)
        changed |= _phase_b_passthroughs(workflow, diagnostics)
        changed |= _phase_c_value_primitives(workflow, registered_inputs, diagnostics)
        if not changed:
            break

    # Hard check: no resolvable helper may still be an edge source after the loop.
    for edge in workflow.edges:
        node = workflow.nodes.get(edge.from_node)
        if node is not None and node.class_type in RESOLVABLE_HELPER_CLASS_TYPES:
            raise ConversionParityError(
                f"Helper node {edge.from_node!r} ({node.class_type}) "
                "could not be fully resolved",
                next_action=f"check node {edge.from_node} ({node.class_type})",
            )

    # Delete all resolved helper nodes and filter dangling edges.
    resolved_ids = frozenset(
        nid
        for nid, n in workflow.nodes.items()
        if n.class_type in RESOLVABLE_HELPER_CLASS_TYPES
    )
    for nid in resolved_ids:
        workflow.nodes.pop(nid)
    workflow.edges = [
        e
        for e in workflow.edges
        if e.from_node not in resolved_ids and e.to_node not in resolved_ids
    ]

    return ResolveDiagnostics(diagnostics=diagnostics)


# ─── Phase A — Broadcast pair resolution ────────────────────────────────────


def _phase_a_broadcasts(
    workflow: VibeWorkflow,
    diagnostics: list[HelperDiagnostic],
) -> bool:
    """Rewrite GetNode and SetNode outbound edges to the broadcast source.

    GetNode edges are rewired to their SetNode's upstream source.
    SetNode edges that target non-GetNode consumers (direct connections)
    are also rewired to the broadcast source so they survive cleanup.
    """
    get_node_ids = frozenset(
        nid
        for nid, n in workflow.nodes.items()
        if n.class_type == "GetNode"
    )
    set_node_ids = frozenset(
        nid
        for nid, n in workflow.nodes.items()
        if n.class_type == "SetNode"
    )
    if not get_node_ids and not set_node_ids:
        return False

    broadcast_sources = collect_broadcast_sources(workflow.nodes, workflow.edges)
    changed = False

    for edge in _sorted_edges(workflow.edges):
        if edge.from_node in get_node_ids:
            node = workflow.nodes[edge.from_node]
            name = broadcast_name(node)
            if not name:
                raise ConversionParityError(
                    f"GetNode {edge.from_node!r} has no broadcast name",
                    next_action=f"check node {edge.from_node} (GetNode)",
                )
            if name not in broadcast_sources:
                raise ConversionParityError(
                    f"GetNode {edge.from_node!r} references unresolved broadcast {name!r}; "
                    "no matching SetNode found",
                    next_action=f"check node {edge.from_node} (GetNode)",
                )
            source = broadcast_sources[name]
            edge.from_node = str(source[0])
            edge.from_output = str(source[1])
            changed = True
        elif edge.from_node in set_node_ids:
            # Rewire SetNode outbound edges that go directly to non-GetNode
            # consumers.  GetNode consumers are handled above; this catches
            # direct SetNode→RegularNode connections that exist in some
            # workflows (e.g. wan_animate where SetNode feeds Sam2Segmentation
            # and PointsEditor directly).
            node = workflow.nodes[edge.from_node]
            name = broadcast_name(node)
            if not name or name not in broadcast_sources:
                continue
            source = broadcast_sources[name]
            edge.from_node = str(source[0])
            edge.from_output = str(source[1])
            changed = True

    return changed


# ─── Phase B — Passthrough resolution ───────────────────────────────────────


def _phase_b_passthroughs(
    workflow: VibeWorkflow,
    diagnostics: list[HelperDiagnostic],
) -> bool:
    """Rewrite Reroute/PrimitiveNode outbound edges to their terminal sources."""
    passthrough_ids = frozenset(
        nid
        for nid, n in workflow.nodes.items()
        if n.class_type in PASSTHROUGH_HELPER_CLASS_TYPES
    )
    if not passthrough_ids:
        return False

    # Build inbound-edge index once per phase call.
    inbound: dict[str, list[VibeEdge]] = {}
    for edge in workflow.edges:
        inbound.setdefault(edge.to_node, []).append(edge)

    changed = False
    folded_edges: list[Any] = []  # edges folded into consumer inputs
    for edge in _sorted_edges(workflow.edges):
        if edge.from_node not in passthrough_ids:
            continue
        terminal = _resolve_passthrough_terminal(
            workflow, edge.from_node, inbound, visited=set()
        )
        if terminal is None:
            node = workflow.nodes[edge.from_node]
            # PrimitiveNode without an inbound edge acts as a value source
            # (like PrimitiveInt/Float), not a passthrough.  Fold its
            # widget value into the consumer's inputs and drop the edge.
            if node.class_type == "PrimitiveNode":
                _fold_primitive_node_literal(workflow, edge, node)
                folded_edges.append(edge)
                changed = True
                continue
            raise ConversionParityError(
                f"Passthrough node {edge.from_node!r} ({node.class_type}) "
                "has no resolvable inbound source (dangling passthrough)",
                next_action=f"check node {edge.from_node} ({node.class_type})",
            )
        edge.from_node = terminal[0]
        edge.from_output = terminal[1]
        changed = True

    # Remove edges that were folded into consumer inputs
    if folded_edges:
        workflow.edges = [e for e in workflow.edges if e not in folded_edges]

    return changed


def _resolve_passthrough_terminal(
    workflow: VibeWorkflow,
    node_id: str,
    inbound: dict[str, list[VibeEdge]],
    visited: set[str],
) -> tuple[str, str] | None:
    """Return the (source_node_id, from_output) terminal for a passthrough chain.

    Returns None for cycles or dangling nodes.
    """
    if node_id in visited:
        return None  # cycle protection
    visited.add(node_id)

    inbound_edges = inbound.get(node_id, [])
    if not inbound_edges:
        return None  # dangling

    # Passthroughs have exactly one meaningful inbound edge; pick the lowest-sort one.
    inbound_edge = min(
        inbound_edges,
        key=lambda e: (_node_sort_key(e.from_node), e.from_output),
    )
    source_id = inbound_edge.from_node
    source_node = workflow.nodes.get(source_id)
    if source_node is None:
        return None  # dangling — source node was removed or is unknown

    if source_node.class_type in PASSTHROUGH_HELPER_CLASS_TYPES:
        return _resolve_passthrough_terminal(workflow, source_id, inbound, visited)

    return (source_id, inbound_edge.from_output)


def _fold_primitive_node_literal(
    workflow: VibeWorkflow,
    edge: Any,  # VibeEdge
    node: Any,  # VibeNode
) -> None:
    """Fold a PrimitiveNode's widget value into its consumer's inputs.

    PrimitiveNode without an inbound edge acts as a value source (like
    PrimitiveInt).  Extract its widget_0 value and write it directly into
    the consumer node's inputs field, then drop the edge.
    """
    raw_value = node.inputs.get("value") or node.widgets.get("widget_0")
    target_node = workflow.nodes.get(edge.to_node)
    if target_node is not None:
        target_node.inputs[edge.to_input] = raw_value


# ─── Phase C — Value primitive resolution ───────────────────────────────────


def _phase_c_value_primitives(
    workflow: VibeWorkflow,
    registered_inputs: dict[str, tuple[str, str]],
    diagnostics: list[HelperDiagnostic],
) -> bool:
    """Fold literal values from Primitive* nodes into consumer inputs."""
    value_prim_ids = frozenset(
        nid
        for nid, n in workflow.nodes.items()
        if n.class_type in VALUE_HELPER_CLASS_TYPES
    )
    if not value_prim_ids:
        return False

    # Build broadcast source map and invert it to find named primitives.
    # For a primitive that feeds multiple SetNode broadcasts, the lexicographically
    # first valid name wins (stable, deterministic).
    broadcast_sources = collect_broadcast_sources(workflow.nodes, workflow.edges)
    source_to_broadcast_name: dict[str, str] = {}
    for name in sorted(broadcast_sources.keys()):
        source = broadcast_sources[name]
        source_id = str(source[0])
        if source_id not in value_prim_ids:
            continue
        prim_node = workflow.nodes.get(source_id)
        if prim_node is None:
            continue
        if not _is_valid_broadcast_name(name, prim_node.class_type):
            continue
        if source_id not in source_to_broadcast_name:
            source_to_broadcast_name[source_id] = name

    changed = False
    for node_id, node in _sorted_nodes(
        {nid: n for nid, n in workflow.nodes.items() if nid in value_prim_ids}
    ):
        outbound = _sorted_edges([e for e in workflow.edges if e.from_node == node_id])
        if not outbound:
            continue  # nothing to fold; node cleaned up after loop

        # Edges to non-helper nodes are the actual runtime consumers.
        real_consumer_edges = [
            e for e in outbound
            if not _is_resolvable_helper_node(workflow, e.to_node)
        ]

        literal = _extract_primitive_value(node, diagnostics)
        bname = source_to_broadcast_name.get(node_id)

        if bname and len(real_consumer_edges) == 1:
            # Named single-consumer primitive → register as public input.
            edge = real_consumer_edges[0]
            consumer_id = edge.to_node
            consumer_field = edge.to_input
            consumer_node = workflow.nodes.get(consumer_id)
            if consumer_node is None:
                raise ConversionParityError(
                    f"Value primitive {node_id!r} ({node.class_type}) "
                    f"consumer node {consumer_id!r} not found in workflow",
                    next_action=f"check node {node_id} ({node.class_type})",
                )
            consumer_node.inputs[consumer_field] = literal
            workflow.register_input(
                bname, consumer_id, consumer_field, value=literal, default=literal
            )
            registered_inputs[bname] = (consumer_id, consumer_field)
        else:
            # Unnamed primitive, OR named with >1 real consumer → fold per consumer.
            for edge in real_consumer_edges:
                consumer_id = edge.to_node
                consumer_field = edge.to_input
                consumer_node = workflow.nodes.get(consumer_id)
                if consumer_node is None:
                    raise ConversionParityError(
                        f"Value primitive {node_id!r} ({node.class_type}) "
                        f"consumer node {consumer_id!r} not found in workflow",
                        next_action=f"check node {node_id} ({node.class_type})",
                    )
                consumer_node.inputs[consumer_field] = literal

        # Remove ALL outbound edges from this primitive (both helper-feed edges and
        # consumer edges) so the fixed-point termination condition is satisfied.
        outbound_obj_ids = frozenset(id(e) for e in outbound)
        workflow.edges = [e for e in workflow.edges if id(e) not in outbound_obj_ids]
        changed = True

    return changed


# ─── Helpers ────────────────────────────────────────────────────────────────


def _is_resolvable_helper_node(workflow: VibeWorkflow, node_id: str) -> bool:
    node = workflow.nodes.get(node_id)
    return node is not None and node.class_type in RESOLVABLE_HELPER_CLASS_TYPES


def _is_valid_broadcast_name(name: str, primitive_class_type: str) -> bool:
    """Return True when *name* is a valid Python identifier usable as a public input name."""
    if not name:
        return False
    if not _NAME_RE.match(name):
        return False
    if name == primitive_class_type:
        return False
    return True


# Mapping from object_info type token → Python callable for coercion.
_TYPE_TOKEN_MAP: dict[str, type] = {
    "BOOLEAN": bool,
    "INT": int,
    "FLOAT": float,
    "STRING": str,
}


def _extract_primitive_value(node: VibeNode, diagnostics: list[HelperDiagnostic]) -> Any:
    """Extract the typed literal from a Primitive* node via the object_info schema.

    Reads ``inputs['value']`` first (named field after widget alias resolution),
    then falls back to ``widgets['widget_0']`` (positional raw form).

    Consults the committed object_info cache: parses ``inputs.required.value``
    as a 2-element array, maps ``array[0]`` (BOOLEAN/INT/FLOAT/STRING) to a
    Python type, and coerces the widget value accordingly.

    When no schema entry is available the raw widget value (already typed from
    JSON parsing) is kept unchanged and an info-level diagnostic is emitted.
    No network or HEAD requests are performed.
    """
    raw = node.inputs.get("value", node.widgets.get("widget_0"))

    entry = get_class(node.class_type)
    if entry is None:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_no_schema",
                message=(
                    f"No object_info schema entry for {node.class_type} "
                    f"({node.id}); keeping raw widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    # Parse inputs.required.value as a 2-element [type_token, metadata] array.
    inputs = entry.get("inputs", {})
    required = inputs.get("required", {})
    value_spec = required.get("value")

    if not isinstance(value_spec, list) or len(value_spec) < 1:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_no_value_spec",
                message=(
                    f"Object_info for {node.class_type} ({node.id}) has "
                    "unexpected inputs.required.value structure; keeping raw "
                    "widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    type_token = value_spec[0]

    coerce_fn = _TYPE_TOKEN_MAP.get(type_token)
    if coerce_fn is None:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_unknown_type_token",
                message=(
                    f"Unknown type token {type_token!r} for {node.class_type} "
                    f"({node.id}); keeping raw widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    if raw is None:
        # Use zero-value for the type when no value is present.
        if coerce_fn is bool:
            return False
        if coerce_fn is int:
            return 0
        if coerce_fn is float:
            return 0.0
        if coerce_fn is str:
            return ""
        return raw

    return coerce_fn(raw)


def _sorted_edges(edges: list[VibeEdge]) -> list[VibeEdge]:
    """Return *edges* in a stable, deterministic order."""
    return sorted(
        edges,
        key=lambda e: (_node_sort_key(e.from_node), _node_sort_key(e.to_node), e.to_input),
    )


__all__ = [
    "ResolveDiagnostics",
    "resolve_helpers",
]
