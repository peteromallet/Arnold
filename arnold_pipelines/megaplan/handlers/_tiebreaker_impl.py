from __future__ import annotations

import argparse
from pathlib import Path

from arnold_pipelines.megaplan.orchestration import tiebreaker_runtime as _runtime
from arnold_pipelines.megaplan.types import PlanState, StepResponse


def _build_tiebreaker_reprompt(
    agent_type: str, state: PlanState, plan_dir: Path, *, root: Path,
) -> str:
    return _runtime._build_tiebreaker_reprompt(agent_type, state, plan_dir, root=root)


def _normalize_tiebreaker_action(args: argparse.Namespace) -> str:
    return _runtime._normalize_tiebreaker_action(args)


def _route_signal_for_tiebreaker_action(action: str) -> str:
    return _runtime._route_signal_for_tiebreaker_action(action)


def handle_tiebreaker_run(root: Path, args: argparse.Namespace) -> StepResponse:
    return _runtime.handle_tiebreaker_run(root, args)


def handle_tiebreaker_decide(root: Path, args: argparse.Namespace) -> StepResponse:
    return _runtime.handle_tiebreaker_decide(root, args)
