from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.orchestration import critique_runtime as _runtime
from arnold_pipelines.megaplan.types import PlanState, StepResponse
from arnold_pipelines.megaplan.workers import WorkerResult

_CRITIQUE_SCRATCH_KNOWN_KEYS = _runtime._CRITIQUE_SCRATCH_KNOWN_KEYS


def _apply_adaptive_critique_routing(
    state: PlanState,
    args: argparse.Namespace,
    active_checks: list[dict[str, Any]],
) -> str | None:
    return _runtime._apply_adaptive_critique_routing(state, args, active_checks)


def handle_critique(root: Path, args: argparse.Namespace) -> StepResponse:
    return _runtime.handle_critique(root, args)


def handle_revise(root: Path, args: argparse.Namespace) -> StepResponse:
    return _runtime.handle_revise(root, args)


def _validate_tiebreaker(
    state: PlanState,
    gate_summary: dict[str, Any],
    plan_dir: Path,
    worker: WorkerResult,
    args: argparse.Namespace,
    agent: str,
    resolved: tuple,
    signals_artifact: dict[str, Any],
    gate_signals: dict[str, Any],
    root: Path,
) -> tuple[str, str, str]:
    return _runtime._validate_tiebreaker(
        state,
        gate_summary,
        plan_dir,
        worker,
        args,
        agent,
        resolved,
        signals_artifact,
        gate_signals,
        root,
    )
