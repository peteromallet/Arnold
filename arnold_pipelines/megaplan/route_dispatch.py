"""Megaplan helpers for resolving declared route dispatch."""

from __future__ import annotations

from typing import Mapping


def resolve_route_target_for_signal(step: str, route_signal: object) -> str | None:
    if not isinstance(route_signal, str) or not route_signal:
        return None
    try:
        from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

        component = STEP_COMPONENTS_BY_ID[step]
    except Exception:
        return None
    for binding in component.metadata.get("route_bindings", ()):
        if not isinstance(binding, Mapping):
            continue
        if binding.get("label") != route_signal:
            continue
        target_ref = binding.get("target_ref")
        if isinstance(target_ref, str) and target_ref:
            return target_ref
    return None


__all__ = ["resolve_route_target_for_signal"]
