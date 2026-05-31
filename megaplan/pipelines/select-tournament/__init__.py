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

from megaplan._pipeline.contracts import BindResult, PortBindError, RepairGradient, bind
from megaplan._pipeline.flags import typed_ports_on
from megaplan._pipeline.types import Edge, ParallelStage, Pipeline, Port, PortRef, Stage
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


def _bind_or_raise(pipeline: Pipeline) -> Pipeline:
    edges = {
        stage_name: tuple(
            edge.target
            for edge in stage.edges
            if edge.target != "halt" and edge.target in pipeline.stages
        )
        for stage_name, stage in pipeline.stages.items()
    }
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


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical ``select-tournament`` pipeline.

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

    pipeline = Pipeline(stages=stages, entry="score_candidates")
    if typed_ports_on():
        return _bind_or_raise(pipeline)
    return pipeline


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
