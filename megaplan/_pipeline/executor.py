"""Standalone Sprint-1 pipeline executor for the ``megaplan/_pipeline`` package.

``run_pipeline`` walks a :class:`Pipeline`'s stages, dispatches each
:class:`Step`, verifies declared outputs, applies state patches, and
follows labelled edges until a terminal sentinel is hit. The executor is
deliberately self-contained — no imports from ``megaplan._core``,
``megaplan.types``, ``megaplan.phase_result``, or ``megaplan._core.io`` —
so the new package can be exercised under bare ``pytest`` without
triggering the live-megaplan import graph.

Contract notes:

(a) ``'halt'`` is reserved both as a :class:`NextEdge` label returned by
    a Step (``result.next == 'halt'``) and as an :class:`Edge` target
    (``edge.target == 'halt'``). Either form terminates the loop. Step
    authors MUST NOT use ``'halt'`` for non-terminal transitions.

(b) ``'subloop'`` and ``'override'`` are reserved ``Step.kind`` literals
    declared in :mod:`megaplan._pipeline.types`. The Sprint-1 executor
    deliberately has **no branch** for either kind — they exist purely
    for forward compatibility and any Step declared with one of these
    kinds is dispatched identically to a ``produce``/``judge``/``decide``
    step.

(c) Verify-only artifact contract: after each Step (or
    :class:`ParallelStage` ``join``) returns, the executor iterates
    ``result.outputs`` and raises ``FileNotFoundError`` if any declared
    path is absent. The error message includes the stage name, output
    label, and path. The executor never copies, moves, or rewrites
    artifacts — Step authors own placement.

(d) Immutability convention: :class:`StepResult`, :class:`Verdict`, and
    :class:`StepContext` are conceptually immutable. State is applied
    via ``state.update(dict(result.state_patch))`` — a defensive copy so
    a Step returning a shared default dict cannot alias the executor's
    working state.

(e) Step authors may nest declared outputs at any depth under the
    stage's artifact directory (or anywhere else under ``ctx.plan_dir``).
    The executor verifies existence only, not directory layout.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping

from megaplan._pipeline.types import (
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


def _atomic_write_json(dest: Path, payload: Any) -> None:
    """Write ``payload`` to ``dest`` atomically via a sibling ``.tmp`` file.

    Uses stdlib ``json`` + ``os.replace`` only — no dependency on
    ``megaplan._core.io``.
    """

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    os.replace(tmp, dest)


def _verify_outputs(stage_name: str, outputs: Mapping[str, Path]) -> None:
    for label, path in outputs.items():
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Stage {stage_name!r} declared output {label!r}={path} "
                f"but the file does not exist"
            )


def _record_error(artifact_root: Path, stage_name: str, exc: BaseException) -> None:
    stage_dir = artifact_root / stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        stage_dir / "error.json",
        {"stage": stage_name, "error": repr(exc)},
    )


def run_pipeline(
    pipeline: Pipeline,
    ctx: StepContext,
    *,
    artifact_root: Path,
) -> dict[str, Any]:
    """Walk ``pipeline`` from its entry stage until a terminal sentinel.

    Returns ``{'state': <final state dict>, 'final_stage': <stage name>}``
    on normal termination. Raises on Step failure, missing declared
    output, or unmatched edge label.
    """

    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    if isinstance(ctx.state, Mapping):
        state: dict[str, Any] = dict(ctx.state)
    else:
        state = {}

    cursor = pipeline.entry
    while True:
        node = pipeline.stages[cursor]

        # Refresh ctx.state with the executor's working state so each
        # iteration of a loop sees the latest state_patches. ctx is
        # frozen; build a new instance via dataclasses.replace.
        ctx = dataclasses.replace(ctx, state=state)

        try:
            if isinstance(node, ParallelStage):
                workers = max(1, node.max_workers or len(node.steps))
                results: list[StepResult] = [None] * len(node.steps)  # type: ignore[list-item]
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    future_to_idx = {
                        pool.submit(step.run, ctx): idx
                        for idx, step in enumerate(node.steps)
                    }
                    for fut in concurrent.futures.as_completed(future_to_idx):
                        idx = future_to_idx[fut]
                        results[idx] = fut.result()
                result = node.join(results, ctx)
            else:
                assert isinstance(node, Stage)
                result = node.step.run(ctx)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _record_error(artifact_root, node.name, exc)
            raise

        _verify_outputs(node.name, result.outputs)

        state.update(dict(result.state_patch))
        _atomic_write_json(artifact_root / "state.json", state)

        if result.next == "halt":
            return {"state": state, "final_stage": node.name}

        edge = next((e for e in node.edges if e.label == result.next), None)
        if edge is None:
            raise LookupError(
                f"Stage {node.name!r} returned NextEdge {result.next!r} "
                f"but no matching edge found in stage.edges"
            )
        if edge.target == "halt":
            return {"state": state, "final_stage": node.name}
        cursor = edge.target
