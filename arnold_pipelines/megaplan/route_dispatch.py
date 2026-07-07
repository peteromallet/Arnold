"""Megaplan helpers for resolving declared route dispatch."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

_ROUTE_AUTHORITY_STEP_ALIASES = MappingProxyType(
    {
        "tiebreaker_run": "tiebreaker_researcher",
        "tiebreaker_decide": "tiebreaker_decision",
    }
)


def _route_authority_step(step: str) -> str:
    return _ROUTE_AUTHORITY_STEP_ALIASES.get(step, step)


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
    authority_step = _route_authority_step(step)
    if authority_step in _front_half_routing_step_ids():
        from arnold_pipelines.megaplan.workflows.planning import lowered_route_bindings_by_step

        return tuple(lowered_route_bindings_by_step(step_ids={authority_step}).get(authority_step, ()))
    return _component_route_bindings_for_step(step)


def resolve_route_binding_for_signal(step: str, route_signal: object) -> Mapping[str, object] | None:
    if not isinstance(route_signal, str) or not route_signal:
        return None
    for binding in _declared_route_bindings_for_step(step):
        if binding.get("label") == route_signal:
            return binding
    return None


def resolve_route_target_for_signal(step: str, route_signal: object) -> str | None:
    binding = resolve_route_binding_for_signal(step, route_signal)
    if binding is not None:
        target_ref = binding.get("target_ref")
        if isinstance(target_ref, str) and target_ref:
            return target_ref
    return None


__all__ = ["resolve_route_binding_for_signal", "resolve_route_target_for_signal"]
