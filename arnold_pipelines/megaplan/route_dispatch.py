"""Megaplan helpers for resolving declared route dispatch."""

from __future__ import annotations

from typing import Mapping


def _front_half_routing_step_ids() -> frozenset[str]:
    from arnold_pipelines.megaplan.workflows.planning import FRONT_HALF_ROUTING_STEP_IDS

    return FRONT_HALF_ROUTING_STEP_IDS


def _component_route_bindings_for_step(step: str) -> tuple[Mapping[str, object], ...]:
    try:
        from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

        component = STEP_COMPONENTS_BY_ID[step]
    except Exception:
        return ()
    bindings = component.metadata.get("route_bindings", ())
    return tuple(binding for binding in bindings if isinstance(binding, Mapping))


def _declared_route_bindings_for_step(step: str) -> tuple[Mapping[str, object], ...]:
    if step in _front_half_routing_step_ids():
        from arnold_pipelines.megaplan.workflows.planning import lowered_route_bindings_by_step

        return tuple(lowered_route_bindings_by_step(step_ids={step}).get(step, ()))
    return _component_route_bindings_for_step(step)


def resolve_route_target_for_signal(step: str, route_signal: object) -> str | None:
    if not isinstance(route_signal, str) or not route_signal:
        return None
    if step in _front_half_routing_step_ids():
        from arnold_pipelines.megaplan.workflows.planning import (
            resolve_lowered_route_target_for_signal,
        )

        return resolve_lowered_route_target_for_signal(step, route_signal)
    for binding in _declared_route_bindings_for_step(step):
        if binding.get("label") == route_signal:
            target_ref = binding.get("target_ref")
            if isinstance(target_ref, str) and target_ref:
                return target_ref
    return None


__all__ = ["resolve_route_target_for_signal"]
