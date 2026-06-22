"""T29/T30: control transitions and dynamic topology overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.execution.state import RouteCoordinate
from arnold.kernel import (
    ControlBinding,
    ControlTarget,
    ControlTransition,
    ControlTransitionType,
    EventFamily,
)
from arnold.kernel.journal import read_event_journal
from arnold.manifest import (
    ControlTransitionSlot,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


class KindControlHandler:
    """Product-neutral control handler that returns the requested transition kind."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def apply(
        self,
        transition_id: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: dict[str, Any],
    ) -> ControlTransition:
        del transition_type
        enum_value = self.kind.replace("supervisor_promotion", "supervisor-promotion")
        return ControlTransition(
            transition_type=ControlTransitionType(enum_value),
            source=ControlTarget(node_ref=context["source_node"]),
            target=ControlTarget(node_ref=binding.target.node_ref),
            trigger=transition_id,
            payload_schema_hash="sha256:" + "0" * 64,
            policy_ref=binding.policy_ref,
            idempotency_key=f"idem-{transition_id}",
        )


def _manifest(*nodes: WorkflowNode, edges: tuple[WorkflowEdge, ...] = ()) -> WorkflowManifest:
    return WorkflowManifest(id="control-demo", nodes=nodes, edges=edges)


def _control_events(tmp_path: Path) -> list[Any]:
    return [
        e for e in read_event_journal(tmp_path) if e.family == EventFamily.CONTROL_TRANSITION
    ]


@pytest.mark.parametrize(
    "kind",
    ["override", "fallback", "escalation", "supervisor_promotion", "overlay"],
)
def test_control_transition_kind_is_journaled(
    tmp_path: Path,
    fake_backend_factory,
    kind: str,
) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="src",
            kind="task",
            policy=WorkflowPolicy(
                control_transitions=(
                    ControlTransitionSlot(
                        transition_id=f"ctrl.{kind}",
                        transition_type=kind,
                        target_ref="target",
                    ),
                )
            ),
        ),
        WorkflowNode(id="target", kind="noop"),
    )
    original_hash = manifest.manifest_hash
    registry = ExecutionRegistries(
        controls={f"ctrl.{kind}": KindControlHandler(kind)}
    )
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registry,
    )

    assert result.state is ExecutionState.COMPLETED
    events = _control_events(tmp_path)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["kind"] == kind
    assert payload["source_node"] == "src"
    assert payload["target_node"] == "target"
    assert tuple(payload["scope_stack"]) == ()
    assert payload["manifest_hash"] == original_hash
    assert "payload" in payload


def test_unregistered_control_transition_is_silently_ignored(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="src",
            kind="task",
            policy=WorkflowPolicy(
                control_transitions=(
                    ControlTransitionSlot(
                        transition_id="ctrl.unregistered",
                        transition_type="override",
                    ),
                )
            ),
        ),
    )
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    assert _control_events(tmp_path) == []


def test_topology_overlay_routes_isolated_target_without_mutating_manifest_hash(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="src",
            kind="task",
            policy=WorkflowPolicy(
                topology_overlays=(
                    TopologyOverlaySlot(
                        overlay_id="overlay.1",
                        overlay_type="route",
                        source_ref="src",
                        target_refs=("target",),
                    ),
                )
            ),
        ),
        WorkflowNode(id="target", kind="noop"),
    )
    original_hash = manifest.manifest_hash
    registry = ExecutionRegistries(
        controls={"overlay.1": KindControlHandler("overlay")}
    )
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registry,
    )

    assert result.state is ExecutionState.COMPLETED
    assert manifest.manifest_hash == original_hash
    events = _control_events(tmp_path)
    assert len(events) == 1
    assert events[0].payload["kind"] == "overlay"
    completed = {
        e.payload["node_ref"]
        for e in read_event_journal(tmp_path)
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert "src" in completed
    assert "target" in completed


def test_control_signal_from_node_outcome_is_journaled(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = _manifest(WorkflowNode(id="src", kind="task"))
    signal = {
        "kind": "escalation",
        "source_node": "src",
        "target_node": "escalation-node",
        "payload": {"reason": "manual"},
    }
    backend = fake_backend_factory(
        control_signals={"src": (signal,)},
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = _control_events(tmp_path)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["kind"] == "escalation"
    assert payload["source_node"] == "src"
    assert payload["target_node"] == "escalation-node"
    assert payload["payload"] == {"reason": "manual"}


def test_control_transition_dispatch_is_product_neutral(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    """The runtime treats transition IDs as opaque strings; no product import."""

    manifest = _manifest(
        WorkflowNode(
            id="src",
            kind="task",
            policy=WorkflowPolicy(
                control_transitions=(
                    ControlTransitionSlot(
                        transition_id="arnold.pipelines.megaplan:control:override",
                        transition_type="override",
                        target_ref="target",
                    ),
                )
            ),
        ),
        WorkflowNode(id="target", kind="noop"),
    )
    registry = ExecutionRegistries(
        controls={
            "arnold.pipelines.megaplan:control:override": KindControlHandler("override")
        }
    )
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registry,
    )

    assert result.state is ExecutionState.COMPLETED
    events = _control_events(tmp_path)
    assert len(events) == 1
    assert events[0].payload["kind"] == "override"
