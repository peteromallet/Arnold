"""Tournament demo — fans out matchup scores, selects top half each round via
iterate_until, declares a champion once one candidate remains.

Pipeline shape:
  prep_field   → produce initial candidates (Port: field_result)
  run_round    → score candidates (ReduceResult) then select top_k(N//2)
                 (SelectionResult); wrapped by iterate_until with
                 plateau(window=2, eps=0.1) + max_iters cap; loops via
                 "iterate" edge, halts via "halt" edge
  (champion is the sole survivor in state['champion'])

All data flow between steps is mediated by Port / PortRef declarations.
Flag-ON: contracts.bind clean. Flag-OFF: PortBindError raised.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._pipeline.contracts import BindResult, PortBindError, RepairGradient, bind
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on
from arnold.pipelines.megaplan._pipeline.pattern_select import top_k
from arnold.pipelines.megaplan._pipeline.pattern_stops import LoopState, max_iters, plateau
from arnold.pipelines.megaplan._pipeline.pattern_topology import iterate_until
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    ReduceResult,
    SelectionResult,
    Stage,
    StepContext,
    StepResult,
)

# ── Content-type constants ──────────────────────────────────────────────

_CT_FIELD = "application/x-fanout-results+json"
_CT_VERDICT = "application/x-verdict+json"


# ── Steps ───────────────────────────────────────────────────────────────


class PrepFieldStep:
    """Emit the initial candidate field as a Port."""

    name = "prep_field"
    kind = "produce"
    prompt_key = None
    slot = None
    produces: tuple[Port, ...] = (Port(name="field_result", content_type=_CT_FIELD),)
    consumes: tuple[PortRef, ...] = ()

    def __init__(self, candidates: list[Any] | None = None) -> None:
        self._candidates = candidates if candidates is not None else list(range(8))

    def run(self, ctx: StepContext) -> StepResult:
        # Write to plan_dir/<stage_name>/v1.md so the executor's port-binding
        # artifact resolver can find the file via the v<n>.* scan.
        out_dir = Path(ctx.plan_dir) / "prep_field"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "v1.md"
        out_path.write_text(json.dumps({"candidates": self._candidates}, indent=2))
        return StepResult(
            outputs={"field_result": out_path},
            next="to_round",
            state_patch={"candidates": self._candidates, "tournament_iter": 0},
        )


class TournamentRoundStep:
    """Score the current field (ReduceResult) then select top_k(N//2) (SelectionResult).

    Produces 'round_result' (SelectionResult serialised) and consumes
    'field_result' from the upstream PrepFieldStep.
    """

    name = "run_round"
    kind = "produce"
    prompt_key = None
    slot = None
    produces: tuple[Port, ...] = (Port(name="round_result", content_type=_CT_VERDICT),)
    consumes: tuple[PortRef, ...] = (PortRef(port_name="field_result", content_type=_CT_FIELD),)

    def run(self, ctx: StepContext) -> StepResult:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        candidates: list[Any] = state.get("candidates", list(range(8)))
        iteration: int = int(state.get("tournament_iter", 0))

        # ── data-reduce: score each candidate ──────────────────────────
        scores = tuple(float(c + iteration * 0.01) for c in candidates)
        _reduce_result = ReduceResult(
            value=candidates,
            scores=scores,
            tally={},
            provenance=(f"iter:{iteration}",),
            label=None,
        )

        # ── select top half via top_k ───────────────────────────────────
        n = len(candidates)
        k = max(1, n // 2)
        rule = top_k(k)
        items = list(zip(candidates, scores))
        selection: SelectionResult = rule(items)

        survivors = [candidates[i] for i in selection.subset] if selection.subset else candidates[:k]
        champion = survivors[0] if len(survivors) == 1 else None

        out_dir = Path(ctx.plan_dir) / "rounds"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"round_v{iteration}.json"
        out_path.write_text(
            json.dumps(
                {
                    "iteration": iteration,
                    "candidates_in": candidates,
                    "survivors": survivors,
                    "scores": list(scores),
                    "champion": champion,
                },
                indent=2,
            )
        )

        next_label = "halt" if champion is not None else "iterate"

        return StepResult(
            outputs={"round_result": out_path},
            next=next_label,
            state_patch={
                "candidates": survivors,
                "champion": champion,
                "tournament_iter": iteration + 1,
                # iterate_until reads last_fanout_results for plateau checks
                "last_fanout_results": list(scores),
            },
        )


# ── Pipeline construction ───────────────────────────────────────────────


def build_pipeline(*, max_rounds: int = 6) -> Pipeline:
    """Build the tournament pipeline.

    Flag-ON: ``contracts.bind`` is called; raises ``PortBindError`` on
    mismatch (e.g. mismatched content types, missing upstream port).
    Flag-OFF: the same pipeline is returned without a bind check.
    """
    prep_step = PrepFieldStep()
    round_step = TournamentRoundStep()

    prep_stage = Stage(
        name="prep_field",
        step=prep_step,
        edges=(Edge("to_round", "run_round"),),
        produces=(Port(name="field_result", content_type=_CT_FIELD),),
    )

    round_stage_base = Stage(
        name="run_round",
        step=round_step,
        edges=(),
        produces=(Port(name="round_result", content_type=_CT_VERDICT),),
        consumes=(PortRef(port_name="field_result", content_type=_CT_FIELD),),
    )

    # OR-combined stop predicate: plateau OR max_iters safety cap.
    _plateau_pred = plateau(window=2, eps=0.1)
    _max_pred = max_iters(max_rounds)

    def _combined(ls: LoopState) -> bool:
        return _plateau_pred(ls) or _max_pred(ls)

    # iterate_until attaches loop_condition and adds "iterate" (self-loop)
    # and "halt" edges; the step returns next="iterate" or next="halt".
    round_stage = iterate_until(
        round_stage_base,
        condition=_combined,
        max_iterations=max_rounds,
    )

    stages: dict[str, Any] = {
        "prep_field": prep_stage,
        "run_round": round_stage,
    }

    pipeline = Pipeline(stages=stages, entry="prep_field")

    if typed_ports_on():
        result = bind(
            pipeline.stages,
            {"prep_field": ["run_round"], "run_round": []},
        )
        if isinstance(result, RepairGradient):
            raise PortBindError(
                "build",
                str(getattr(result.wanted, "port_name", result.wanted)),
                f"bind failed: {result.error_kind}",
            )
        assert isinstance(result, BindResult)
        pipeline = dataclasses.replace(pipeline, binding_map=result.binding_map)

    return pipeline


def run_tournament(*, max_rounds: int = 6) -> dict[str, Any]:
    """Run the tournament pipeline and return the final state dict."""
    pipeline = build_pipeline(max_rounds=max_rounds)
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        ctx = StepContext(
            plan_dir=plan_dir,
            state={},
            profile=None,
            mode="tournament",
        )
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir / "artifacts")
    return result
