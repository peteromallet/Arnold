"""Legacy-fenced Megaplan helpers for compatibility-only route projection."""

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


class LegacyRouteDispatchDisabled(RuntimeError):
    """Raised when compatibility-only route dispatch is used on a live path."""


def _require_legacy_opt_in(*, allow_legacy: bool) -> None:
    if allow_legacy:
        return
    raise LegacyRouteDispatchDisabled(
        "route_dispatch is legacy-fenced; live routing must resolve from "
        "source-derived workflow planning helpers instead"
    )


def resolve_route_binding_for_signal(
    step: str,
    route_signal: object,
    *,
    allow_legacy: bool = False,
) -> Mapping[str, object] | None:
    if not isinstance(route_signal, str) or not route_signal:
        return None
    _require_legacy_opt_in(allow_legacy=allow_legacy)

    from arnold_pipelines.megaplan.workflows.planning import lowered_route_bindings_by_step

    authority_step = _route_authority_step(step)
    for binding in lowered_route_bindings_by_step(step_ids={authority_step}).get(authority_step, ()):
        if binding.get("label") == route_signal:
            return binding
    return None


def resolve_route_target_for_signal(
    step: str,
    route_signal: object,
    *,
    allow_legacy: bool = False,
) -> str | None:
    if not isinstance(route_signal, str) or not route_signal:
        return None
    _require_legacy_opt_in(allow_legacy=allow_legacy)

    from arnold_pipelines.megaplan.workflows.planning import resolve_lowered_route_target_for_signal

    return resolve_lowered_route_target_for_signal(_route_authority_step(step), route_signal)


__all__ = [
    "LegacyRouteDispatchDisabled",
    "resolve_route_binding_for_signal",
    "resolve_route_target_for_signal",
]
