"""Control transitions and dynamic topology overlays.

Runtime control transitions are recorded as journal events and projected back
into routing state without mutating the canonical manifest hash.  All product
meaning is dispatched through ``arnold.execution.registries.ControlRegistry``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.execution.registries import ControlRegistry
from arnold.execution.state import RouteCoordinate
from arnold.kernel import ControlBinding, ControlTarget, ControlTransition
from arnold.kernel.events import EventEnvelope
from arnold.manifest import (
    ControlTransitionSlot,
    TopologyOverlaySlot,
    WorkflowManifest,
    WorkflowNode,
)


CONTROL_TRANSITION_KINDS = frozenset({
    "override",
    "fallback",
    "escalation",
    "supervisor_promotion",
    "supervisor-promotion",
    "overlay",
})


@dataclass(frozen=True)
class ControlProjection:
    """Projected control-transition state derived from journal events."""

    transitions: dict[tuple[tuple[str, ...], str], tuple[Mapping[str, Any], ...]] = field(
        default_factory=dict
    )
    overlays: dict[tuple[tuple[str, ...], str], tuple[str, ...]] = field(
        default_factory=dict
    )

    def targets_for(
        self,
        scope_stack: tuple[str, ...],
        source_node: str,
    ) -> tuple[str, ...]:
        return self.overlays.get((scope_stack, source_node), ())


def control_transition_payload(
    *,
    kind: str,
    source_node: str,
    target_node: str,
    scope_stack: tuple[str, ...],
    payload: Mapping[str, Any],
    manifest_hash: str,
    trigger: str | None = None,
) -> dict[str, Any]:
    """Build a ``control_transition`` event payload."""

    result: dict[str, Any] = {
        "kind": kind,
        "source_node": source_node,
        "target_node": target_node,
        "scope_stack": list(scope_stack),
        "payload": dict(payload),
        "manifest_hash": manifest_hash,
    }
    if trigger is not None:
        result["trigger"] = trigger
    return result


def project_control_transitions(
    manifest: WorkflowManifest,
    events: tuple[EventEnvelope, ...],
) -> ControlProjection:
    """Fold control-transition events into a deterministic projection."""

    del manifest  # reserved for future source-node validation
    transitions: dict[tuple[tuple[str, ...], str], list[Mapping[str, Any]]] = {}
    overlays: dict[tuple[tuple[str, ...], str], list[str]] = {}

    for event in events:
        if event.kind != "control_transition":
            continue
        payload = event.payload
        scope_stack = tuple(payload.get("scope_stack", ()))
        source_node = payload.get("source_node", "")
        target_node = payload.get("target_node", "")
        kind = payload.get("kind", "")
        key = (scope_stack, source_node)
        transitions.setdefault(key, []).append(dict(payload))
        if kind == "overlay":
            overlays.setdefault(key, []).append(target_node)

    return ControlProjection(
        transitions={
            key: tuple(values) for key, values in transitions.items()
        },
        overlays={
            key: tuple(values) for key, values in overlays.items()
        },
    )


def dispatch_control_transition(
    registry: ControlRegistry,
    slot: ControlTransitionSlot,
    coordinate: RouteCoordinate,
    *,
    run_id: str,
) -> ControlTransition | None:
    """Dispatch a declared control transition through the control registry."""

    if not registry.has(slot.transition_id):
        return None
    binding = ControlBinding(
        binding_id=slot.transition_id,
        target=ControlTarget(
            node_ref=slot.target_ref or coordinate.node_ref,
        ),
        policy_ref=slot.policy_ref,
    )
    return registry.apply(
        slot.transition_id,
        transition_type=slot.transition_type,
        binding=binding,
        context={
            "run_id": run_id,
            "coordinate": str(coordinate),
            "source_node": coordinate.node_ref,
        },
    )


def dispatch_topology_overlay(
    registry: ControlRegistry,
    slot: TopologyOverlaySlot,
    coordinate: RouteCoordinate,
    *,
    run_id: str,
) -> tuple[ControlTransition, ...]:
    """Dispatch a topology overlay through the control registry.

    Each target in the overlay slot is dispatched independently.  The resulting
    transitions are recorded as ``control_transition`` events with kind
    ``overlay``.
    """

    if not registry.has(slot.overlay_id):
        return ()
    source = slot.source_ref or coordinate.node_ref
    transitions: list[ControlTransition] = []
    for target_ref in slot.target_refs:
        binding = ControlBinding(
            binding_id=slot.overlay_id,
            target=ControlTarget(node_ref=target_ref),
            policy_ref=None,
        )
        transition = registry.apply(
            slot.overlay_id,
            transition_type=slot.overlay_type,
            binding=binding,
            context={
                "run_id": run_id,
                "coordinate": str(coordinate),
                "source_node": source,
            },
        )
        if transition is not None:
            transitions.append(transition)
    return tuple(transitions)


def control_transition_from_projection(
    transition: ControlTransition,
    *,
    scope_stack: tuple[str, ...],
    manifest_hash: str,
) -> dict[str, Any]:
    """Convert a projected control transition into an event payload."""

    kind = transition.transition_type.value.replace("-", "_")
    return control_transition_payload(
        kind=kind,
        source_node=transition.source.node_ref,
        target_node=transition.target.node_ref,
        scope_stack=scope_stack,
        payload=dict(transition.payload or {}),
        manifest_hash=manifest_hash,
        trigger=transition.trigger,
    )


def collect_declared_transitions(
    node: WorkflowNode,
) -> tuple[ControlTransitionSlot, ...]:
    """Return declared control-transition slots for a node."""

    policy = node.policy
    if policy is None:
        return ()
    return policy.control_transitions


def collect_declared_overlays(
    node: WorkflowNode,
) -> tuple[TopologyOverlaySlot, ...]:
    """Return declared topology-overlay slots for a node."""

    policy = node.policy
    if policy is None:
        return ()
    return policy.topology_overlays


__all__ = [
    "CONTROL_TRANSITION_KINDS",
    "ControlProjection",
    "collect_declared_overlays",
    "collect_declared_transitions",
    "control_transition_from_projection",
    "control_transition_payload",
    "dispatch_control_transition",
    "dispatch_topology_overlay",
    "project_control_transitions",
]