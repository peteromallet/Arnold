"""Deterministic manifest projection and routing state.

The router derives runnable state from a manifest plus a journal of events. It
never relies on mutable overwrite-only state. It supports linear sequences,
branches, bounded loops, retry coordinates, fanout child identities, reducer
ordering, and subpipeline scope hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.kernel.events import EventEnvelope
from arnold.manifest import WorkflowEdge, WorkflowManifest, WorkflowNode

from arnold.execution.state import (
    FanoutProjection,
    LoopProjection,
    RetryProjection,
    RouteCoordinate,
    RoutingState,
)


@dataclass(frozen=True)
class _EventSummary:
    """Aggregated event-derived facts used during projection."""

    completed: set[RouteCoordinate]
    failed: set[RouteCoordinate]
    suspended: set[RouteCoordinate]
    loop_iterations: dict[RouteCoordinate, int]
    retry_attempts: dict[RouteCoordinate, int]
    branch_selected: dict[tuple[str, tuple[str, ...]], str]  # (node, scope) -> edge_id
    fanout_completed_children: dict[RouteCoordinate, set[str]]
    reducer_completed: set[RouteCoordinate]
    subpipeline_exited: set[tuple[str, tuple[str, ...]]]  # (node_ref, scope) -> True


def _node_policy(node: WorkflowNode) -> Any:
    return node.policy


def _loop_max_iterations(node: WorkflowNode) -> int | None:
    policy = _node_policy(node)
    if policy is None or policy.loop is None:
        return None
    return policy.loop.max_iterations


def _retry_max_attempts(node: WorkflowNode) -> int:
    policy = _node_policy(node)
    if policy is None or policy.retry is None:
        return 1
    return policy.retry.max_attempts


def _fanout_width(node: WorkflowNode) -> int | None:
    policy = _node_policy(node)
    if policy is None or policy.fanout is None:
        return None
    return policy.fanout.width


def _subpipeline_hash(node: WorkflowNode) -> str | None:
    if node.subpipeline is None:
        return None
    return node.subpipeline.manifest_hash


def _summary_from_events(events: tuple[EventEnvelope, ...]) -> _EventSummary:
    completed: set[RouteCoordinate] = set()
    failed: set[RouteCoordinate] = set()
    suspended: set[RouteCoordinate] = set()
    loop_iterations: dict[RouteCoordinate, int] = {}
    retry_attempts: dict[RouteCoordinate, int] = {}
    branch_selected: dict[tuple[str, tuple[str, ...]], str] = {}
    fanout_completed_children: dict[RouteCoordinate, set[str]] = {}
    reducer_completed: set[RouteCoordinate] = set()
    subpipeline_exited: set[tuple[str, tuple[str, ...]]] = set()

    for event in events:
        payload = event.payload
        node_ref = payload.get("node_ref", "")
        scope_stack = tuple(payload.get("scope_stack", ()))
        attempt = payload.get("attempt", 1)
        iteration = payload.get("iteration", 1)
        child_key = payload.get("child_key")
        coordinate = RouteCoordinate(
            node_ref=node_ref,
            scope_stack=scope_stack,
            attempt=attempt,
            iteration=iteration,
            child_key=child_key,
        )

        if event.kind == "node_completed":
            completed.add(coordinate)
            if child_key and node_ref:
                parent = coordinate.replace(child_key=None)
                fanout_completed_children.setdefault(parent, set()).add(child_key)
        elif event.kind == "node_failed":
            failed.add(coordinate)
            key = coordinate.replace(child_key=None)
            retry_attempts[key] = retry_attempts.get(key, 1) + 1
        elif event.kind == "node_suspended":
            suspended.add(coordinate)
        elif event.kind == "node_resumed":
            suspended.discard(coordinate.replace(attempt=1, iteration=1, child_key=None))
        elif event.kind == "loop_iteration":
            base = coordinate.replace(iteration=1)
            loop_iterations[base] = max(
                loop_iterations.get(base, 1),
                iteration,
            )
        elif event.kind == "branch_selected":
            edge_id = payload.get("edge_id", "")
            if edge_id:
                branch_selected[(node_ref, scope_stack)] = edge_id
        elif event.kind == "reducer_completed":
            reducer_completed.add(coordinate)
        elif event.kind == "subpipeline_exited":
            subpipeline_exited.add((node_ref, scope_stack))

    return _EventSummary(
        completed=completed,
        failed=failed,
        suspended=suspended,
        loop_iterations=loop_iterations,
        retry_attempts=retry_attempts,
        branch_selected=branch_selected,
        fanout_completed_children=fanout_completed_children,
        reducer_completed=reducer_completed,
        subpipeline_exited=subpipeline_exited,
    )


def _deterministic_node_order(nodes: tuple[WorkflowNode, ...]) -> tuple[WorkflowNode, ...]:
    return tuple(sorted(nodes, key=lambda node: node.id))


def _incoming_edges(
    node_id: str,
    edges: tuple[WorkflowEdge, ...],
) -> tuple[WorkflowEdge, ...]:
    return tuple(sorted(
        (edge for edge in edges if edge.target == node_id),
        key=lambda edge: edge.id,
    ))


def _outgoing_edges(
    node_id: str,
    edges: tuple[WorkflowEdge, ...],
) -> tuple[WorkflowEdge, ...]:
    return tuple(sorted(
        (edge for edge in edges if edge.source == node_id),
        key=lambda edge: edge.id,
    ))


def _reachable_nodes(
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
    nodes: tuple[WorkflowNode, ...],
    edges: tuple[WorkflowEdge, ...],
) -> set[str]:
    """Return the set of node refs reachable via active edges.

    A node is reachable when it has at least one active incoming edge. An
    unconditional edge is active when its source is reachable and completed. A
    conditional edge is active when its source is reachable, completed, and the
    branch selected that edge.
    """

    incoming_by_target: dict[str, tuple[WorkflowEdge, ...]] = {
        node.id: _incoming_edges(node.id, edges) for node in nodes
    }
    reachable: set[str] = {
        node.id for node in nodes if not incoming_by_target[node.id]
    }

    changed = True
    while changed:
        changed = False
        for node in nodes:
            node_id = node.id
            if node_id in reachable:
                continue
            for edge in incoming_by_target[node_id]:
                source = edge.source
                if source not in reachable:
                    continue
                source_coordinate = RouteCoordinate(
                    node_ref=source, scope_stack=scope_stack
                )
                if source_coordinate not in summary.completed:
                    continue
                if edge.condition_ref is not None:
                    selected = _branch_selected_edge(source, scope_stack, summary)
                    if selected != edge.id:
                        continue
                reachable.add(node_id)
                changed = True
                break
    return reachable


def _is_ready_linear(
    node: WorkflowNode,
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
    edges: tuple[WorkflowEdge, ...],
    reachable: set[str],
) -> bool:
    """Return True when all active predecessors are completed.

    A node is only ready when it is reachable and every active incoming edge
    (unconditional or matching conditional branch) has its source completed.
    """

    if node.id not in reachable:
        return False

    for edge in _incoming_edges(node.id, edges):
        source = edge.source
        if source not in reachable:
            continue
        source_coordinate = RouteCoordinate(node_ref=source, scope_stack=scope_stack)
        if source_coordinate not in summary.completed:
            return False
        if edge.condition_ref is not None:
            selected = _branch_selected_edge(source, scope_stack, summary)
            if selected != edge.id:
                return False
    return True


def _branch_selected_edge(
    node_id: str,
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
) -> str | None:
    return summary.branch_selected.get((node_id, scope_stack))


def _ready_branch_targets(
    node: WorkflowNode,
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
    edges: tuple[WorkflowEdge, ...],
) -> tuple[str, ...]:
    """Return the target node refs reachable after a branch node.

    If a branch has already been selected, only that target is returned. Before
    selection, all outgoing conditional edges are returned as candidates so the
    projection surfaces the choice without backend execution.
    """

    selected = _branch_selected_edge(node.id, scope_stack, summary)
    outgoing = _outgoing_edges(node.id, edges)
    if selected:
        for edge in outgoing:
            if edge.id == selected:
                return (edge.target,)
        return ()
    conditional = tuple(edge for edge in outgoing if edge.condition_ref is not None)
    if conditional:
        return tuple(edge.target for edge in conditional)
    return tuple(edge.target for edge in outgoing)


def _loop_state(
    node: WorkflowNode,
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
) -> LoopProjection:
    base = RouteCoordinate(node_ref=node.id, scope_stack=scope_stack)
    current = summary.loop_iterations.get(base, 1)
    return LoopProjection(
        coordinate=base,
        current_iteration=current,
        max_iterations=_loop_max_iterations(node),
    )


def _retry_state(
    node: WorkflowNode,
    scope_stack: tuple[str, ...],
    summary: _EventSummary,
) -> RetryProjection:
    base = RouteCoordinate(node_ref=node.id, scope_stack=scope_stack)
    current = summary.retry_attempts.get(base, 1)
    return RetryProjection(
        coordinate=base,
        current_attempt=current,
        max_attempts=_retry_max_attempts(node),
    )


def _fanout_children(node: WorkflowNode, parent: RouteCoordinate) -> tuple[RouteCoordinate, ...]:
    width = _fanout_width(node)
    if width is None:
        return ()
    return tuple(
        parent.replace(child_key=f"{node.id}:child:{idx}")
        for idx in range(width)
    )


def _subpipeline_scope(parent_scope: tuple[str, ...], node: WorkflowNode) -> tuple[str, ...]:
    sp_hash = _subpipeline_hash(node)
    if sp_hash is None:
        return parent_scope
    return parent_scope + (sp_hash,)


def project_routing_state(
    manifest: WorkflowManifest,
    events: tuple[EventEnvelope, ...] = (),
    *,
    overlays: Mapping[tuple[tuple[str, ...], str], tuple[str, ...]] | None = None,
) -> RoutingState:
    """Project deterministic routing state from a manifest and journal events.

    ``overlays`` maps ``(scope_stack, source_node_ref)`` to additional target
    node refs introduced by dynamic topology overlays.  Overlays never mutate
    the manifest; they are applied purely as a routing projection.
    """

    summary = _summary_from_events(events)
    nodes = _deterministic_node_order(manifest.nodes)
    edges = manifest.edges

    completed: set[RouteCoordinate] = set(summary.completed)
    failed: set[RouteCoordinate] = set(summary.failed)
    suspended: set[RouteCoordinate] = set(summary.suspended)
    ready_set: set[RouteCoordinate] = set()
    blocked_set: set[RouteCoordinate] = set()
    loops: dict[RouteCoordinate, LoopProjection] = {}
    retries: dict[RouteCoordinate, RetryProjection] = {}
    fanouts: dict[RouteCoordinate, FanoutProjection] = {}
    reducer_inputs: dict[RouteCoordinate, tuple[RouteCoordinate, ...]] = {}
    scope_hashes: dict[tuple[str, ...], str] = {}

    # Scope 0 is the root manifest hash.
    root_scope: tuple[str, ...] = ()
    scope_hashes[root_scope] = manifest.manifest_hash or ""

    # Collect all scopes referenced by events.
    for event in events:
        scope_stack = tuple(event.payload.get("scope_stack", ()))
        if scope_stack and scope_stack not in scope_hashes:
            scope_hashes[scope_stack] = scope_stack[-1]

    def _project_scope(scope_stack: tuple[str, ...]) -> None:
        reachable = _reachable_nodes(scope_stack, summary, nodes, edges)
        for node in nodes:
            base = RouteCoordinate(node_ref=node.id, scope_stack=scope_stack)

            # Suspended coordinates are terminal until a resume event clears them.
            if base in suspended:
                continue

            # Subpipeline nodes become ready when their linear predecessors are
            # complete; after the subpipeline exits the node is marked completed.
            sp_hash = _subpipeline_hash(node)
            if sp_hash is not None:
                sp_scope = _subpipeline_scope(scope_stack, node)
                scope_hashes[sp_scope] = sp_hash
                if (node.id, scope_stack) in summary.subpipeline_exited:
                    completed.add(base)
                    continue
                if base in completed:
                    continue
                if _is_ready_linear(node, scope_stack, summary, edges, reachable):
                    ready_set.add(base)
                else:
                    blocked_set.add(base)
                continue

            # Fanout parent: ready when linear predecessors complete; after
            # completion it spawns deterministic children.
            fanout_width = _fanout_width(node)
            if fanout_width is not None:
                if base in completed:
                    children = _fanout_children(node, base)
                    fanouts[base] = FanoutProjection(
                        parent=base,
                        width=fanout_width,
                        children=children,
                    )
                    completed_children = summary.fanout_completed_children.get(base, set())
                    if len(completed_children) == fanout_width:
                        reducer_ref = _node_policy(node).fanout.reducer_ref if _node_policy(node) else None
                        if reducer_ref:
                            reducer_coord = RouteCoordinate(
                                node_ref=f"{node.id}:reducer",
                                scope_stack=scope_stack,
                            )
                            reducer_inputs[reducer_coord] = tuple(
                                sorted(
                                    (child for child in children if child.child_key in completed_children),
                                    key=lambda c: c.child_key or "",
                                )
                            )
                            if reducer_coord not in completed and reducer_coord not in summary.reducer_completed:
                                ready_set.add(reducer_coord)
                            completed.add(reducer_coord)
                    else:
                        for child in children:
                            if child not in completed and child not in failed:
                                ready_set.add(child)
                    continue
                if _is_ready_linear(node, scope_stack, summary, edges, reachable):
                    ready_set.add(base)
                else:
                    blocked_set.add(base)
                continue

            # Loop node: after completion, re-enter if under max_iterations.
            # Nodes that have both a loop policy and conditional outgoing edges
            # are treated as branch nodes so product cycles can route to their
            # targets while still satisfying the bounded-reentry validator.
            loop_max = _loop_max_iterations(node)
            outgoing = _outgoing_edges(node.id, edges)
            if loop_max is not None and not any(edge.condition_ref is not None for edge in outgoing):
                loop_proj = _loop_state(node, scope_stack, summary)
                loops[base] = loop_proj
                iteration_coord = base.replace(iteration=loop_proj.current_iteration)
                if iteration_coord in completed:
                    if loop_proj.max_iterations is None or loop_proj.current_iteration < loop_proj.max_iterations:
                        next_iter = base.replace(iteration=loop_proj.current_iteration + 1)
                        if next_iter not in completed:
                            ready_set.add(next_iter)
                    continue
                if _is_ready_linear(node, scope_stack, summary, edges, reachable):
                    ready_set.add(iteration_coord)
                else:
                    blocked_set.add(iteration_coord)
                continue

            # Branch node: expose candidate targets until a branch is selected.
            outgoing = _outgoing_edges(node.id, edges)
            if outgoing and any(edge.condition_ref is not None for edge in outgoing):
                if base in completed:
                    targets = _ready_branch_targets(node, scope_stack, summary, edges)
                    for target_ref in targets:
                        target_coord = RouteCoordinate(node_ref=target_ref, scope_stack=scope_stack)
                        if target_coord not in completed and target_coord not in failed:
                            ready_set.add(target_coord)
                    continue
                if _is_ready_linear(node, scope_stack, summary, edges, reachable):
                    ready_set.add(base)
                else:
                    blocked_set.add(base)
                continue

            # Retry node: after failure, re-enter if under max_attempts.
            retry_proj = _retry_state(node, scope_stack, summary)
            retries[base] = retry_proj
            attempt_coord = base.replace(attempt=retry_proj.current_attempt)
            if attempt_coord in failed:
                if retry_proj.current_attempt < retry_proj.max_attempts:
                    next_attempt = base.replace(attempt=retry_proj.current_attempt + 1)
                    if next_attempt not in completed and next_attempt not in failed:
                        ready_set.add(next_attempt)
                continue
            if attempt_coord in completed:
                continue
            if retry_proj.current_attempt > retry_proj.max_attempts:
                continue
            if _is_ready_linear(node, scope_stack, summary, edges, reachable):
                ready_set.add(attempt_coord)
            else:
                blocked_set.add(attempt_coord)

        # Dynamic topology overlays: add target nodes as ready once the source
        # node is completed.  Overlays are derived from control_transition events
        # and never mutate the canonical manifest hash.
        if overlays:
            for (overlay_scope, source_ref), target_refs in overlays.items():
                if overlay_scope != scope_stack:
                    continue
                source_coord = RouteCoordinate(node_ref=source_ref, scope_stack=scope_stack)
                if source_coord not in completed:
                    continue
                for target_ref in target_refs:
                    target_coord = RouteCoordinate(node_ref=target_ref, scope_stack=scope_stack)
                    if target_coord not in completed and target_coord not in failed:
                        ready_set.add(target_coord)

    # Project the root scope and any scopes referenced by events.
    scopes_to_project: set[tuple[str, ...]] = {root_scope}
    scopes_to_project.update(scope_hashes.keys())
    for scope in sorted(scopes_to_project):
        _project_scope(scope)

    # Deterministic ordering: sort ready and blocked coordinates.
    ready = tuple(sorted(ready_set, key=lambda c: (c.scope_stack, c.node_ref, c.attempt, c.iteration, c.child_key or "")))
    blocked = tuple(sorted(blocked_set, key=lambda c: (c.scope_stack, c.node_ref, c.attempt, c.iteration, c.child_key or "")))

    return RoutingState(
        manifest=manifest,
        completed=completed,
        failed=failed,
        suspended=suspended,
        ready=ready,
        blocked=blocked,
        loops=loops,
        retries=retries,
        fanouts=fanouts,
        reducer_inputs=reducer_inputs,
        scope_hashes=scope_hashes,
    )


__all__ = ["project_routing_state"]
