"""Compensation orchestrator for manifest execution.

Compensation walks completed nodes in a scope in reverse completion order and
executes their declared compensation targets through the effect ledger.  All
external effects are idempotent; duplicate compensation runs are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.execution.state import RouteCoordinate
from arnold.kernel import EventEnvelope
from arnold.kernel.effect_ledger import derive_effect_idempotency_key
from arnold.manifest import CompensationPolicy, CompensationTarget, EffectRef, WorkflowNode


@dataclass(frozen=True)
class CompensationStep:
    """A single compensation step derived from a completed node."""

    coordinate: RouteCoordinate
    target: CompensationTarget
    idempotency_key: str


def compensation_policy_for_node(
    node: WorkflowNode,
    manifest_policy: CompensationPolicy | None,
) -> CompensationPolicy | None:
    """Return the effective compensation policy for a node."""

    if node.policy is not None and node.policy.compensation is not None:
        return node.policy.compensation
    return manifest_policy


def compensation_scope_stack(
    coordinate: RouteCoordinate,
    policy: CompensationPolicy | None,
) -> tuple[str, ...]:
    """Return the scope stack in which compensation should run."""

    del policy  # reserved for future scope_ref resolution
    return coordinate.scope_stack


def completed_nodes_in_scope(
    events: tuple[EventEnvelope, ...],
    scope_stack: tuple[str, ...],
) -> tuple[RouteCoordinate, ...]:
    """Return completed coordinates in ``scope_stack`` in completion order."""

    completed: list[RouteCoordinate] = []
    for event in events:
        if event.kind != "node_completed":
            continue
        payload = event.payload
        event_scope = tuple(payload.get("scope_stack", ()))
        if event_scope != scope_stack:
            continue
        completed.append(
            RouteCoordinate(
                node_ref=payload.get("node_ref", ""),
                scope_stack=event_scope,
                attempt=payload.get("attempt", 1),
                iteration=payload.get("iteration", 1),
                child_key=payload.get("child_key"),
            )
        )
    return tuple(completed)


def reverse_completion_order(
    events: tuple[EventEnvelope, ...],
    scope_stack: tuple[str, ...],
) -> tuple[RouteCoordinate, ...]:
    """Return completed coordinates in reverse completion order."""

    return tuple(reversed(completed_nodes_in_scope(events, scope_stack)))


def target_for_node(
    targets: tuple[CompensationTarget, ...],
    node_ref: str,
) -> CompensationTarget | None:
    """Return the compensation target declared for ``node_ref``."""

    for target in targets:
        if target.target_id == node_ref:
            return target
    return None


def derive_compensation_effect_idempotency_key(
    *,
    run_id: str,
    node_ref: str,
    target_id: str,
    effect: EffectRef,
) -> str:
    """Derive an idempotency key for a compensation effect."""

    base = derive_effect_idempotency_key(
        run_id=run_id,
        node_ref=node_ref,
        effect_id=effect.effect_id,
        key_template=effect.idempotency.key_template if effect.idempotency else None,
        key_ref=effect.idempotency.key_ref if effect.idempotency else None,
    )
    return f"{base}:compensation:{target_id}"


def compensation_run_idempotency_key(
    *,
    run_id: str,
    trigger_node_ref: str,
    scope_stack: tuple[str, ...],
) -> str:
    return f"{run_id}:compensation-run:{trigger_node_ref}:{'/'.join(scope_stack)}"


def compensation_already_started(
    events: tuple[EventEnvelope, ...],
    *,
    trigger_node_ref: str,
    scope_stack: tuple[str, ...],
) -> bool:
    """Return True if compensation has already been started for this trigger."""

    for event in events:
        if event.kind != "compensation_started":
            continue
        payload = event.payload
        if (
            payload.get("trigger_node_ref") == trigger_node_ref
            and tuple(payload.get("scope_stack", ())) == scope_stack
        ):
            return True
    return False


def build_compensation_steps(
    events: tuple[EventEnvelope, ...],
    policy: CompensationPolicy,
    trigger_coordinate: RouteCoordinate,
    *,
    run_id: str,
) -> tuple[CompensationStep, ...]:
    """Map reverse completion order onto declared compensation targets."""

    scope_stack = compensation_scope_stack(trigger_coordinate, policy)
    targets = policy.targets
    steps: list[CompensationStep] = []
    for coordinate in reverse_completion_order(events, scope_stack):
        target = target_for_node(targets, coordinate.node_ref)
        if target is None:
            continue
        idempotency_key = derive_compensation_effect_idempotency_key(
            run_id=run_id,
            node_ref=coordinate.node_ref,
            target_id=target.target_id,
            effect=target.effect,
        )
        steps.append(
            CompensationStep(
                coordinate=coordinate,
                target=target,
                idempotency_key=idempotency_key,
            )
        )
    return tuple(steps)


def compensation_started_payload(
    *,
    trigger_node_ref: str,
    scope_stack: tuple[str, ...],
    step_count: int,
) -> dict[str, Any]:
    return {
        "trigger_node_ref": trigger_node_ref,
        "scope_stack": list(scope_stack),
        "step_count": step_count,
    }


def compensation_step_payload(
    *,
    step: CompensationStep,
    success: bool,
    result: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target_id": step.target.target_id,
        "node_ref": step.coordinate.node_ref,
        "effect_id": step.target.effect.effect_id,
        "idempotency_key": step.idempotency_key,
        "success": success,
    }
    if result is not None:
        payload["result"] = dict(result)
    if error is not None:
        payload["error"] = error
    return payload


def compensation_completed_payload(
    *,
    trigger_node_ref: str,
    scope_stack: tuple[str, ...],
    completed_steps: int,
    failed_steps: int,
) -> dict[str, Any]:
    return {
        "trigger_node_ref": trigger_node_ref,
        "scope_stack": list(scope_stack),
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
    }


__all__ = [
    "CompensationStep",
    "build_compensation_steps",
    "compensation_already_started",
    "compensation_completed_payload",
    "compensation_policy_for_node",
    "compensation_run_idempotency_key",
    "compensation_scope_stack",
    "compensation_started_payload",
    "compensation_step_payload",
    "completed_nodes_in_scope",
    "derive_compensation_effect_idempotency_key",
    "reverse_completion_order",
    "target_for_node",
]