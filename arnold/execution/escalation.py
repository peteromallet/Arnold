"""Escalation orchestrator for manifest execution.

Escalation routes a failed or explicitly escalated coordinate to the targets
declared in ``policy.escalation`` and journals an ``escalation_routed`` event.
Targets are string-keyed node refs resolved against the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arnold.execution.state import RouteCoordinate
from arnold.kernel import EventEnvelope
from arnold.manifest import EscalationPolicy, WorkflowNode


@dataclass(frozen=True)
class EscalationRoute:
    """Resolved escalation route for a coordinate."""

    source_coordinate: RouteCoordinate
    target_refs: tuple[str, ...]
    policy_ref: str | None = None


def escalation_policy_for_node(
    node: WorkflowNode,
    manifest_policy: EscalationPolicy | None,
) -> EscalationPolicy | None:
    """Return the effective escalation policy for a node."""

    if node.policy is not None and node.policy.escalation is not None:
        return node.policy.escalation
    return manifest_policy


def retry_exhausted(
    coordinate: RouteCoordinate,
    node: WorkflowNode,
) -> bool:
    """Return True when the coordinate has exhausted its retry budget."""

    max_attempts = 1
    if node.policy is not None and node.policy.retry is not None:
        max_attempts = node.policy.retry.max_attempts
    return coordinate.attempt >= max_attempts


def should_escalate(
    coordinate: RouteCoordinate,
    node: WorkflowNode,
    manifest_policy: EscalationPolicy | None,
    explicit_signal: bool = False,
) -> EscalationRoute | None:
    """Return an escalation route if one should be triggered."""

    policy = escalation_policy_for_node(node, manifest_policy)
    if policy is None:
        return None
    if not explicit_signal and not retry_exhausted(coordinate, node):
        return None
    if not policy.targets:
        return None
    return EscalationRoute(
        source_coordinate=coordinate,
        target_refs=policy.targets,
        policy_ref=policy.policy_ref,
    )


def escalation_routed_payload(
    route: EscalationRoute,
    *,
    manifest_hash: str,
) -> dict[str, Any]:
    return {
        "source_node": route.source_coordinate.node_ref,
        "source_scope_stack": list(route.source_coordinate.scope_stack),
        "source_attempt": route.source_coordinate.attempt,
        "targets": list(route.target_refs),
        "policy_ref": route.policy_ref,
        "manifest_hash": manifest_hash,
    }


def escalation_already_routed(
    events: tuple[EventEnvelope, ...],
    *,
    source_node: str,
    scope_stack: tuple[str, ...],
    attempt: int,
) -> bool:
    """Return True if an escalation has already been journaled for this source."""

    for event in events:
        if event.kind != "escalation_routed":
            continue
        payload = event.payload
        if (
            payload.get("source_node") == source_node
            and tuple(payload.get("source_scope_stack", ())) == scope_stack
            and payload.get("source_attempt") == attempt
        ):
            return True
    return False


__all__ = [
    "EscalationRoute",
    "escalation_already_routed",
    "escalation_policy_for_node",
    "escalation_routed_payload",
    "retry_exhausted",
    "should_escalate",
]