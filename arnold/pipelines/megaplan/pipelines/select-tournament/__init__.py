"""First-class ``select-tournament`` pipeline.

Topology:

    score_candidates (fanout) -> pairwise_bracket -> winner

The boundary between every stage is a declared typed Port:
``candidate_scores`` feeds the bracket reducer, and ``bracket_result`` feeds
the winner stage. The terminal winner artifact is also declared as a Port so
consumers can bind to it later without scraping state.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arnold.pipeline.declaration_lowering import bind_with_lowered_declarations
from arnold.pipeline.native import (
    compile_pipeline,
    parallel,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipelines.megaplan._pipeline.contracts import (
    BindResult,
    PortBindError,
    RepairGradient,
    bind,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE
from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on
from arnold.pipelines.megaplan._pipeline.types import StepContext

# M3a: Edge / Port / PortRef migrated to Arnold neutral shapes.
from arnold.pipeline import Edge, Port, PortRef
# M3a: Stage / ParallelStage / Pipeline kept as bridge — uses produces/consumes/binding_map fields.
from arnold.pipelines.megaplan._pipeline.types import ParallelStage, Pipeline, Stage
from .steps import (
    BRACKET_RESULT_PORT,
    CANDIDATE_SCORES_PORT,
    WINNER_PORT,
    CandidateScoreStep,
    PairwiseBracketStep,
    WinnerStep,
    join_candidate_scores,
)


name: str = "select-tournament"
description: str = (
    "Selection tournament pipeline: fan out per-candidate scoring, reduce "
    "scores through a pairwise bracket, then emit a winner artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("subprocess_isolated", "fanout+pairwise-reduce")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("review",)


DEFAULT_CANDIDATES: tuple[str, ...] = (
    "alpha",
    "beta",
    "gamma",
    "delta",
)


def _candidate_score_steps(candidates: Sequence[str]) -> tuple[CandidateScoreStep, ...]:
    """Return deterministic per-candidate scoring steps in seed order."""

    total = max(1, len(candidates))
    return tuple(
        CandidateScoreStep(
            candidate=str(candidate),
            seed=index,
            score=float(index + 1) / float(total),
        )
        for index, candidate in enumerate(candidates)
    )


def _dict_to_step_context(ctx: object) -> StepContext:
    """Adapt native-runtime contexts to the Megaplan StepContext expected here."""

    if isinstance(ctx, StepContext):
        return ctx
    if hasattr(ctx, "plan_dir") and hasattr(ctx, "state") and hasattr(ctx, "profile"):
        return ctx  # type: ignore[return-value]

    if isinstance(ctx, dict):
        raw_state = ctx.get("state") or {}
        raw_inputs = ctx.get("inputs") or {}
        root = ctx.get("artifact_root") or ctx.get("plan_dir") or "."
        envelope = ctx.get("envelope") or EMPTY_ENVELOPE
        mode = str(ctx.get("mode") or "select")
        profile = ctx.get("profile") or {}
    else:
        raw_state = getattr(ctx, "state", {}) or {}
        raw_inputs = getattr(ctx, "inputs", {}) or {}
        root = getattr(ctx, "artifact_root", None) or getattr(ctx, "plan_dir", ".")
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        mode = str(getattr(ctx, "mode", "select") or "select")
        profile = getattr(ctx, "profile", {}) or {}

    inputs = {
        str(key): Path(value) if isinstance(value, str) else value
        for key, value in dict(raw_inputs).items()
    }
    return StepContext(
        plan_dir=Path(root),
        state=dict(raw_state) if isinstance(raw_state, dict) else raw_state,
        profile=profile,
        mode=mode,
        inputs=inputs,
        envelope=envelope,
    )


def _native_candidate_score(ctx: object, *, seed: int) -> Any:
    return _candidate_score_steps(DEFAULT_CANDIDATES)[seed].run(
        _dict_to_step_context(ctx)
    )


@phase(name="candidate_score_0", produces=(CANDIDATE_SCORES_PORT,))
def _native_candidate_score_0(ctx: object) -> Any:
    return _native_candidate_score(ctx, seed=0)


@phase(name="candidate_score_1", produces=(CANDIDATE_SCORES_PORT,))
def _native_candidate_score_1(ctx: object) -> Any:
    return _native_candidate_score(ctx, seed=1)


@phase(name="candidate_score_2", produces=(CANDIDATE_SCORES_PORT,))
def _native_candidate_score_2(ctx: object) -> Any:
    return _native_candidate_score(ctx, seed=2)


@phase(name="candidate_score_3", produces=(CANDIDATE_SCORES_PORT,))
def _native_candidate_score_3(ctx: object) -> Any:
    return _native_candidate_score(ctx, seed=3)


@phase(
    name="pairwise_bracket",
    consumes=(PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),),
    produces=(BRACKET_RESULT_PORT,),
)
def _native_pairwise_bracket(ctx: object) -> Any:
    return PairwiseBracketStep().run(_dict_to_step_context(ctx))


@phase(
    name="winner",
    consumes=(PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),),
    produces=(WINNER_PORT,),
)
def _native_winner(ctx: object) -> Any:
    return WinnerStep().run(_dict_to_step_context(ctx))


@pipeline("select-tournament")
def select_tournament(ctx: object) -> Any:
    for branch in parallel(
        [
            _native_candidate_score_0,
            _native_candidate_score_1,
            _native_candidate_score_2,
            _native_candidate_score_3,
        ],
        reducer=join_candidate_scores,
        name="score_candidates",
    ):
        state = yield branch(ctx)
    state = yield _native_pairwise_bracket(ctx)
    state = yield _native_winner(ctx)
    return state


def _bind_or_raise(pipeline: Pipeline) -> Pipeline:
    edges = {
        stage_name: tuple(
            edge.target
            for edge in stage.edges
            if edge.target != "halt" and edge.target in pipeline.stages
        )
        for stage_name, stage in pipeline.stages.items()
    }
    result = bind_with_lowered_declarations(pipeline.stages, edges)
    if result is None:
        result = bind(pipeline.stages, edges)
    if isinstance(result, RepairGradient):
        wanted = getattr(result.wanted, "port_name", result.wanted)
        raise PortBindError(
            "select-tournament",
            str(wanted),
            f"bind failed: {result.error_kind}",
        )
    assert isinstance(result, BindResult)
    return dataclasses.replace(pipeline, binding_map=result.binding_map)


def _project_native_pipeline(candidate_list: tuple[str, ...]) -> Pipeline:
    """Compile/project the native declaration and specialize candidate scoring."""

    projected = project_graph(compile_pipeline(select_tournament), key_mode="phase")
    projected_stages = projected.stages
    for stage_name in ("score_candidates", "pairwise_bracket", "winner"):
        if stage_name not in projected_stages:
            raise RuntimeError(
                f"select-tournament native projection missing stage {stage_name!r}"
            )

    score_projected = projected_stages["score_candidates"]
    pairwise_projected = projected_stages["pairwise_bracket"]

    stages = {
        "score_candidates": ParallelStage(
            name="score_candidates",
            steps=_candidate_score_steps(candidate_list),
            join=join_candidate_scores,
            edges=tuple(score_projected.edges),
            max_workers=len(candidate_list),
            produces=(CANDIDATE_SCORES_PORT,),
        ),
        "pairwise_bracket": Stage(
            name="pairwise_bracket",
            step=PairwiseBracketStep(),
            edges=tuple(pairwise_projected.edges),
            consumes=(PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),),
            produces=(BRACKET_RESULT_PORT,),
        ),
        "winner": Stage(
            name="winner",
            step=WinnerStep(),
            edges=(),
            consumes=(PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),),
            produces=(WINNER_PORT,),
        ),
    }
    return Pipeline(
        stages=stages,
        entry=projected.entry,
        resource_bundles=("score_candidate", "pairwise_bracket", "winner"),
    )


def _build_legacy_graph_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the legacy hand-built graph, kept for parity baselines only.

    ``score_candidates`` is a real :class:`ParallelStage`; its join emits the
    ``candidate_scores`` Port consumed by ``pairwise_bracket``. ``winner`` only
    reads the declared ``bracket_result`` Port and writes ``winner_result``.
    """

    candidate_list = tuple(str(candidate) for candidate in candidates)
    if not candidate_list:
        raise ValueError("select-tournament requires at least one candidate")

    stages = {
        "score_candidates": ParallelStage(
            name="score_candidates",
            steps=_candidate_score_steps(candidate_list),
            join=join_candidate_scores,
            edges=(Edge(label="pairwise_bracket", target="pairwise_bracket"),),
            max_workers=len(candidate_list),
            produces=(CANDIDATE_SCORES_PORT,),
        ),
        "pairwise_bracket": Stage(
            name="pairwise_bracket",
            step=PairwiseBracketStep(),
            edges=(Edge(label="winner", target="winner"),),
            consumes=(PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),),
            produces=(BRACKET_RESULT_PORT,),
        ),
        "winner": Stage(
            name="winner",
            step=WinnerStep(),
            edges=(),
            consumes=(PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),),
            produces=(WINNER_PORT,),
        ),
    }

    pipeline = Pipeline(
        stages=stages,
        entry="score_candidates",
        resource_bundles=("score_candidate", "pairwise_bracket", "winner"),
    )
    if typed_ports_on():
        return _bind_or_raise(pipeline)
    return pipeline


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical native-projected ``select-tournament`` pipeline."""

    candidate_list = tuple(str(candidate) for candidate in candidates)
    if not candidate_list:
        raise ValueError("select-tournament requires at least one candidate")

    pipeline = _project_native_pipeline(candidate_list)
    if typed_ports_on():
        return _bind_or_raise(pipeline)
    return dataclasses.replace(pipeline, binding_map=None)


__all__ = [
    "DEFAULT_CANDIDATES",
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
