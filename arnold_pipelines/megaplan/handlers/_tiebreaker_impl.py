from __future__ import annotations

import argparse
from pathlib import Path

from arnold_pipelines.megaplan.orchestration import tiebreaker_runtime as _runtime
from arnold_pipelines.megaplan.types import PlanState, StepResponse
from arnold_pipelines.megaplan.workflows.planning import resolve_lowered_route_target_for_signal

_LEGACY_TIEBREAKER_RUN_STEP = "tiebreaker_run"
_LEGACY_TIEBREAKER_DECIDE_STEP = "tiebreaker_decide"


def _build_tiebreaker_reprompt(
    agent_type: str, state: PlanState, plan_dir: Path, *, root: Path,
) -> str:
    return _runtime._build_tiebreaker_reprompt(agent_type, state, plan_dir, root=root)


def _normalize_tiebreaker_action(args: argparse.Namespace) -> str:
    return _runtime._normalize_tiebreaker_action(args)


def _route_signal_for_tiebreaker_action(action: str) -> str:
    return _runtime._route_signal_for_tiebreaker_action(action)


def _bridge_tiebreaker_next_step(node_id: str, route_signal: str | None) -> str | None:
    if not route_signal:
        return None
    if node_id == _LEGACY_TIEBREAKER_RUN_STEP:
        return "tiebreaker decide" if route_signal == "default" else None
    if node_id != _LEGACY_TIEBREAKER_DECIDE_STEP:
        return None
    target = resolve_lowered_route_target_for_signal("tiebreaker_decision", route_signal)
    if target == "override":
        return "override add-note"
    return target


def _apply_legacy_tiebreaker_bridge(
    args: argparse.Namespace,
    response: StepResponse,
    *,
    default_node_id: str,
) -> StepResponse:
    node_id = getattr(args, "node_id", None)
    if isinstance(node_id, str) and node_id:
        phase_id = node_id
    else:
        phase_id = default_node_id
    next_step = _bridge_tiebreaker_next_step(phase_id, response.get("route_signal"))
    if next_step is not None:
        response["next_step"] = next_step
    return response


def handle_tiebreaker_run(root: Path, args: argparse.Namespace) -> StepResponse:
    response = _runtime.handle_tiebreaker_run(root, args)
    return _apply_legacy_tiebreaker_bridge(args, response, default_node_id=_LEGACY_TIEBREAKER_RUN_STEP)


def handle_tiebreaker_decide(root: Path, args: argparse.Namespace) -> StepResponse:
    response = _runtime.handle_tiebreaker_decide(root, args)
    return _apply_legacy_tiebreaker_bridge(args, response, default_node_id=_LEGACY_TIEBREAKER_DECIDE_STEP)
