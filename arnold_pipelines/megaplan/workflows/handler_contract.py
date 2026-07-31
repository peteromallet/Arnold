"""Workflow-owned projection of typed route decisions onto legacy mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from arnold_pipelines.megaplan._core import workflow_next, workflow_transition
from arnold_pipelines.megaplan.review.parallel import run_parallel_review
from arnold_pipelines.megaplan.types import PlanState


_UNSET = object()


@dataclass(frozen=True)
class RouteProjection:
    route_signal: str
    state: object = _UNSET
    next_step: object = _UNSET

    def __post_init__(self) -> None:
        if not isinstance(self.route_signal, str) or not self.route_signal:
            raise ValueError("route projection requires a non-empty route_signal")


def apply_state_projection(
    state: PlanState, value: str, *, route_signal: str
) -> None:
    projection = RouteProjection(route_signal=route_signal, state=value)
    state["current_state"] = projection.state


def apply_response_projection(
    response: MutableMapping[str, Any],
    *,
    route_signal: str,
    state: object = _UNSET,
    next_step: object = _UNSET,
) -> None:
    projection = RouteProjection(
        route_signal=route_signal, state=state, next_step=next_step
    )
    response["route_signal"] = projection.route_signal
    if projection.state is not _UNSET:
        response["state"] = projection.state
    if projection.next_step is not _UNSET:
        response["next_step"] = projection.next_step


def resolve_transition(state: PlanState, step: str) -> Any:
    return workflow_transition(state, step)


def resolve_next_steps(state: PlanState) -> list[str]:
    return workflow_next(state)


def dispatch_review_panel(
    state: PlanState,
    plan_dir: Any,
    *,
    root: Any,
    model: str | None,
    checks: Any,
    pre_check_flags: Any,
) -> Any:
    """Workflow-owned extreme-review fanout boundary."""

    return run_parallel_review(
        state,
        plan_dir,
        root=root,
        model=model,
        checks=checks,
        pre_check_flags=pre_check_flags,
    )


__all__ = [
    "RouteProjection",
    "apply_response_projection",
    "apply_state_projection",
    "dispatch_review_panel",
    "resolve_next_steps",
    "resolve_transition",
]
