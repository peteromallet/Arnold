from __future__ import annotations

import pytest

from arnold.execution.routing import project_routing_state
from arnold.execution.state import RouteCoordinate
from arnold.kernel import EventEnvelope, EventFamily, ManifestReference
from arnold.manifest import (
    BudgetPolicy,
    FanoutPolicy,
    LoopPolicy,
    RetryPolicy,
    SubpipelineRef,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _manifest(*nodes: WorkflowNode, edges: tuple[WorkflowEdge, ...] = ()) -> WorkflowManifest:
    return WorkflowManifest(id="demo", nodes=nodes, edges=edges)


def _event(kind: str, payload: dict, sequence: int = 0) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"e{sequence}",
        family=EventFamily.NODE_LIFECYCLE,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash=_hash("a")),
        run_id="run-1",
        payload_schema_hash=_hash("b"),
        payload=payload,
        sequence=sequence,
    )


def test_linear_projection_ready_node_is_first_node() -> None:
    manifest = _manifest(
        WorkflowNode(id="start", kind="noop"),
        WorkflowNode(id="end", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="start", target="end"),),
    )

    state = project_routing_state(manifest)
    assert state.ready == (RouteCoordinate(node_ref="start"),)
    assert RouteCoordinate(node_ref="end") in state.blocked


def test_linear_second_node_ready_after_first_completion() -> None:
    manifest = _manifest(
        WorkflowNode(id="start", kind="noop"),
        WorkflowNode(id="end", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="start", target="end"),),
    )
    events = (_event("node_completed", {"node_ref": "start"}, sequence=0),)

    state = project_routing_state(manifest, events)
    assert state.ready == (RouteCoordinate(node_ref="end"),)
    assert RouteCoordinate(node_ref="start") in state.completed


def test_linear_complete_when_all_nodes_done() -> None:
    manifest = _manifest(
        WorkflowNode(id="start", kind="noop"),
        WorkflowNode(id="end", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="start", target="end"),),
    )
    events = (
        _event("node_completed", {"node_ref": "start"}, sequence=0),
        _event("node_completed", {"node_ref": "end"}, sequence=1),
    )

    state = project_routing_state(manifest, events)
    assert not state.ready
    assert state.is_complete


def test_branch_projection_exposes_candidates_before_selection() -> None:
    manifest = _manifest(
        WorkflowNode(id="gate", kind="branch"),
        WorkflowNode(id="left", kind="noop"),
        WorkflowNode(id="right", kind="noop"),
        edges=(
            WorkflowEdge(id="e-left", source="gate", target="left", condition_ref="cond-left"),
            WorkflowEdge(id="e-right", source="gate", target="right", condition_ref="cond-right"),
        ),
    )
    events = (_event("node_completed", {"node_ref": "gate"}, sequence=0),)

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="left") in state.ready
    assert RouteCoordinate(node_ref="right") in state.ready


def test_branch_projection_selects_single_target_after_selection_event() -> None:
    manifest = _manifest(
        WorkflowNode(id="gate", kind="branch"),
        WorkflowNode(id="left", kind="noop"),
        WorkflowNode(id="right", kind="noop"),
        edges=(
            WorkflowEdge(id="e-left", source="gate", target="left", condition_ref="cond-left"),
            WorkflowEdge(id="e-right", source="gate", target="right", condition_ref="cond-right"),
        ),
    )
    events = (
        _event("node_completed", {"node_ref": "gate"}, sequence=0),
        _event("branch_selected", {"node_ref": "gate", "edge_id": "e-left"}, sequence=1),
    )

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="left") in state.ready
    assert RouteCoordinate(node_ref="right") not in state.ready


def test_loop_projection_respects_bounded_limit() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="loop",
            kind="loop",
            policy=WorkflowPolicy(loop=LoopPolicy(max_iterations=3)),
        ),
    )

    state = project_routing_state(manifest)
    assert RouteCoordinate(node_ref="loop", iteration=1) in state.ready
    assert state.loops[RouteCoordinate(node_ref="loop")].max_iterations == 3


def test_loop_projection_stops_after_max_iterations() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="loop",
            kind="loop",
            policy=WorkflowPolicy(loop=LoopPolicy(max_iterations=2)),
        ),
    )
    events = (
        _event("loop_iteration", {"node_ref": "loop", "iteration": 1}, sequence=0),
        _event("node_completed", {"node_ref": "loop", "iteration": 1}, sequence=1),
        _event("loop_iteration", {"node_ref": "loop", "iteration": 2}, sequence=2),
        _event("node_completed", {"node_ref": "loop", "iteration": 2}, sequence=3),
    )

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="loop", iteration=2) in state.completed
    assert RouteCoordinate(node_ref="loop", iteration=3) not in state.ready


def test_retry_projection_allows_multiple_attempts() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(retry=RetryPolicy(max_attempts=3)),
        ),
    )
    events = (
        _event("node_failed", {"node_ref": "fragile", "attempt": 1}, sequence=0),
    )

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="fragile", attempt=2) in state.ready
    assert state.retries[RouteCoordinate(node_ref="fragile")].max_attempts == 3


def test_retry_projection_stops_after_max_attempts() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(retry=RetryPolicy(max_attempts=2)),
        ),
    )
    events = (
        _event("node_failed", {"node_ref": "fragile", "attempt": 1}, sequence=0),
        _event("node_failed", {"node_ref": "fragile", "attempt": 2}, sequence=1),
    )

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="fragile", attempt=1) in state.failed
    assert RouteCoordinate(node_ref="fragile", attempt=2) in state.failed
    assert RouteCoordinate(node_ref="fragile", attempt=3) not in state.ready


def test_fanout_projection_spawn_children() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fan",
            kind="fanout",
            policy=WorkflowPolicy(fanout=FanoutPolicy(width=3)),
        ),
    )
    events = (_event("node_completed", {"node_ref": "fan"}, sequence=0),)

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="fan") in state.completed
    projection = state.fanouts[RouteCoordinate(node_ref="fan")]
    assert projection.width == 3
    assert len(projection.children) == 3
    for idx in range(3):
        assert RouteCoordinate(node_ref="fan", child_key=f"fan:child:{idx}") in state.ready


def test_fanout_reducer_ready_after_children_complete() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fan",
            kind="fanout",
            policy=WorkflowPolicy(fanout=FanoutPolicy(width=2, reducer_ref="reducer.sum")),
        ),
    )
    events = (
        _event("node_completed", {"node_ref": "fan"}, sequence=0),
        _event("node_completed", {"node_ref": "fan", "child_key": "fan:child:0"}, sequence=1),
        _event("node_completed", {"node_ref": "fan", "child_key": "fan:child:1"}, sequence=2),
    )

    state = project_routing_state(manifest, events)
    reducer = RouteCoordinate(node_ref="fan:reducer")
    assert reducer in state.completed
    assert len(state.reducer_inputs[reducer]) == 2


def test_reducer_inputs_are_ordered_by_child_key() -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fan",
            kind="fanout",
            policy=WorkflowPolicy(fanout=FanoutPolicy(width=2, reducer_ref="reducer.sum")),
        ),
    )
    events = (
        _event("node_completed", {"node_ref": "fan"}, sequence=0),
        _event("node_completed", {"node_ref": "fan", "child_key": "fan:child:1"}, sequence=1),
        _event("node_completed", {"node_ref": "fan", "child_key": "fan:child:0"}, sequence=2),
    )

    state = project_routing_state(manifest, events)
    reducer = RouteCoordinate(node_ref="fan:reducer")
    inputs = state.reducer_inputs[reducer]
    assert inputs[0].child_key == "fan:child:0"
    assert inputs[1].child_key == "fan:child:1"


def test_subpipeline_scope_hash_is_tracked() -> None:
    child_hash = _hash("c")
    manifest = _manifest(
        WorkflowNode(
            id="parent",
            kind="subpipeline",
            subpipeline=SubpipelineRef(manifest_hash=child_hash, alias="child"),
        ),
    )

    state = project_routing_state(manifest)
    assert () in state.scope_hashes
    assert state.scope_hashes[()] == manifest.manifest_hash
    assert (child_hash,) in state.scope_hashes
    assert state.scope_hashes[(child_hash,)] == child_hash


def test_subpipeline_projection_completes_after_exit_event() -> None:
    child_hash = _hash("c")
    manifest = _manifest(
        WorkflowNode(
            id="parent",
            kind="subpipeline",
            subpipeline=SubpipelineRef(manifest_hash=child_hash, alias="child"),
        ),
    )
    events = (
        _event("subpipeline_exited", {"node_ref": "parent", "scope_stack": []}, sequence=0),
    )

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="parent") in state.completed


def test_routing_state_orders_nodes_deterministically() -> None:
    manifest = _manifest(
        WorkflowNode(id="z", kind="noop"),
        WorkflowNode(id="a", kind="noop"),
        WorkflowNode(id="m", kind="noop"),
    )

    state = project_routing_state(manifest)
    refs = [coord.node_ref for coord in state.ready]
    assert refs == ["a", "m", "z"]


def test_blocked_nodes_are_tracked_when_predecessors_incomplete() -> None:
    manifest = _manifest(
        WorkflowNode(id="first", kind="noop"),
        WorkflowNode(id="second", kind="noop"),
        WorkflowNode(id="third", kind="noop"),
        edges=(
            WorkflowEdge(id="e1", source="first", target="second"),
            WorkflowEdge(id="e2", source="second", target="third"),
        ),
    )

    state = project_routing_state(manifest)
    assert RouteCoordinate(node_ref="first") in state.ready
    assert RouteCoordinate(node_ref="second") in state.blocked
    assert RouteCoordinate(node_ref="third") in state.blocked


def test_suspended_nodes_are_tracked() -> None:
    manifest = _manifest(WorkflowNode(id="ask", kind="human"))
    events = (_event("node_suspended", {"node_ref": "ask"}, sequence=0),)

    state = project_routing_state(manifest, events)
    assert RouteCoordinate(node_ref="ask") in state.suspended
    assert not state.ready
