"""T31/T32: compensation and escalation orchestrators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.execution.state import RouteCoordinate
from arnold.kernel import EventFamily
from arnold.kernel.journal import read_event_journal
from arnold.manifest import (
    CompensationPolicy,
    CompensationTarget,
    EffectRef,
    EscalationPolicy,
    IdempotencyPolicy,
    RetryPolicy,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


class RecordingEffectHandler:
    """Product-neutral effect handler that records each execution."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: dict[str, Any],
        idempotency_key: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del route, context
        self.calls.append((effect_id, {"payload": payload, "idempotency_key": idempotency_key}))
        return {"effect_id": effect_id, "idempotency_key": idempotency_key}


def _manifest(
    *nodes: WorkflowNode,
    edges: tuple[WorkflowEdge, ...] = (),
    policy: WorkflowPolicy | None = None,
) -> WorkflowManifest:
    return WorkflowManifest(id="comp-esc-demo", nodes=nodes, edges=edges, policy=policy)


def test_compensation_walks_completed_nodes_in_reverse_order(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    handler = RecordingEffectHandler()
    manifest = _manifest(
        WorkflowNode(id="a", kind="task"),
        WorkflowNode(id="b", kind="task"),
        WorkflowNode(
            id="c",
            kind="task",
            policy=WorkflowPolicy(
                compensation=CompensationPolicy(
                    targets=(
                        CompensationTarget(
                            target_id="a",
                            effect=EffectRef(
                                effect_id="refund.a",
                                idempotency=IdempotencyPolicy(key_ref="a"),
                            ),
                        ),
                        CompensationTarget(
                            target_id="b",
                            effect=EffectRef(
                                effect_id="refund.b",
                                idempotency=IdempotencyPolicy(key_ref="b"),
                            ),
                        ),
                    )
                )
            ),
        ),
        edges=(
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ),
    )
    registries = ExecutionRegistries(
        effects={
            "refund.a": handler,
            "refund.b": handler,
        }
    )
    backend = fake_backend_factory(
        node_behaviors={"c": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)

    started = [e for e in events if e.kind == "compensation_started"]
    assert len(started) == 1
    assert started[0].payload["trigger_node_ref"] == "c"
    assert started[0].payload["step_count"] == 2

    steps = [
        e
        for e in events
        if e.kind in ("compensation_step_completed", "compensation_step_failed")
    ]
    assert len(steps) == 2
    assert steps[0].payload["node_ref"] == "b"
    assert steps[1].payload["node_ref"] == "a"
    assert all(s.payload["success"] for s in steps)

    completed = [e for e in events if e.kind == "compensation_completed"]
    assert len(completed) == 1
    assert completed[0].payload["completed_steps"] == 2
    assert completed[0].payload["failed_steps"] == 0

    assert len(handler.calls) == 2
    assert {call[0] for call in handler.calls} == {"refund.a", "refund.b"}


def test_compensation_is_idempotent(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    handler = RecordingEffectHandler()
    manifest = _manifest(
        WorkflowNode(id="a", kind="task"),
        WorkflowNode(
            id="c",
            kind="task",
            policy=WorkflowPolicy(
                compensation=CompensationPolicy(
                    targets=(
                        CompensationTarget(
                            target_id="a",
                            effect=EffectRef(
                                effect_id="refund.a",
                                idempotency=IdempotencyPolicy(key_ref="a"),
                            ),
                        ),
                    )
                )
            ),
        ),
        edges=(WorkflowEdge(id="e1", source="a", target="c"),),
    )
    registries = ExecutionRegistries(effects={"refund.a": handler})
    backend = fake_backend_factory(
        node_behaviors={"c": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )
    assert len(handler.calls) == 1

    c_node = next(n for n in manifest.nodes if n.id == "c")
    backend._maybe_compensate(
        RouteCoordinate(node_ref="c", scope_stack=()),
        c_node,
    )

    events = read_event_journal(tmp_path)
    started = [e for e in events if e.kind == "compensation_started"]
    assert len(started) == 1
    assert len(handler.calls) == 1


def test_compensation_step_failed_is_journaled(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    class FailingEffectHandler:
        def execute(self, effect_id, *, route, payload, idempotency_key, context):
            del route, payload, idempotency_key, context
            raise RuntimeError("refund gateway down")

    manifest = _manifest(
        WorkflowNode(id="a", kind="task"),
        WorkflowNode(
            id="c",
            kind="task",
            policy=WorkflowPolicy(
                compensation=CompensationPolicy(
                    targets=(
                        CompensationTarget(
                            target_id="a",
                            effect=EffectRef(
                                effect_id="refund.a",
                                idempotency=IdempotencyPolicy(key_ref="a"),
                            ),
                        ),
                    )
                )
            ),
        ),
        edges=(WorkflowEdge(id="e1", source="a", target="c"),),
    )
    registries = ExecutionRegistries(effects={"refund.a": FailingEffectHandler()})
    backend = fake_backend_factory(
        node_behaviors={"c": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    events = read_event_journal(tmp_path)
    failed_steps = [e for e in events if e.kind == "compensation_step_failed"]
    assert len(failed_steps) == 1
    assert failed_steps[0].payload["node_ref"] == "a"
    assert "refund gateway down" in failed_steps[0].payload["error"]
    completed = [e for e in events if e.kind == "compensation_completed"]
    assert completed[0].payload["failed_steps"] == 1


def test_escalation_routes_targets_after_retry_exhaustion(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(
                retry=RetryPolicy(max_attempts=2),
                escalation=EscalationPolicy(targets=("escalation_target",)),
            ),
        ),
        WorkflowNode(id="escalation_target", kind="task"),
    )
    backend = fake_backend_factory(
        node_behaviors={"fragile": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    # The original failure remains terminal because the escalation target is a
    # different node, but the escalation target is still executed and journaled.
    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)
    routed = [e for e in events if e.kind == "escalation_routed"]
    assert len(routed) == 1
    assert routed[0].payload["source_node"] == "fragile"
    assert routed[0].payload["targets"] == ["escalation_target"]
    completed = {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert "escalation_target" in completed


def test_escalation_target_same_as_failed_node_suppresses_terminal_failure(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(
                retry=RetryPolicy(max_attempts=2),
                escalation=EscalationPolicy(targets=("fragile",)),
            ),
        ),
    )
    attempts: list[int] = []

    def behavior(coordinate: RouteCoordinate, node: WorkflowNode, context: Any) -> NodeOutcome:
        del node, context
        attempts.append(coordinate.attempt)
        # Fail the initial two retry attempts, then succeed once escalation
        # re-runs the same node.
        if len(attempts) <= 2:
            return NodeOutcome(state=NodeState.FAILED, error="boom")
        return NodeOutcome(state=NodeState.COMPLETED)

    backend = fake_backend_factory(node_behaviors={"fragile": behavior})

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    # Escalation re-runs the same node, which eventually succeeds and suppresses
    # the terminal failure in the routing projection.
    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "escalation_routed" for e in events)
    completed = [e for e in events if e.kind == "node_completed"]
    assert len(completed) == 1
