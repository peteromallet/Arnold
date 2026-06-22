"""Canonical importable module for the ``select-tournament`` pipeline.

The hyphenated sibling directory ``select-tournament/`` holds prompts,
profiles, and ``SKILL.md``. This module is the importable surface so the
workflow CLI and registry discovery can address it as
``arnold_pipelines.megaplan.pipelines.select_tournament:build_pipeline``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from arnold.manifest import FanoutPolicy, ReducerRef, WorkflowPolicy
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


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

_PIPELINE_DIR: Path = Path(__file__).parent / "select-tournament"
_PROMPTS: Path = _PIPELINE_DIR / "prompts"


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical ``select-tournament`` explicit-node pipeline.

    ``score_candidates`` is a fanout step whose width equals the number of
    candidates. The reducer joins individual scores into the
    ``candidate_scores`` artifact consumed by ``pairwise_bracket``.
    """

    candidate_list = tuple(str(candidate) for candidate in candidates)
    if not candidate_list:
        raise ValueError("select-tournament requires at least one candidate")

    score_candidates = Step(
        id="score_candidates",
        kind="fanout",
        label="Score each candidate",
        inputs=(Input(name="candidates"),),
        outputs=(Output(name="candidate_scores"),),
        capabilities=(Capability(id="review", route="score"),),
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(
                mode="static",
                width=len(candidate_list),
                reducer_ref="select_tournament:join_candidate_scores",
            ),
            reducers=(
                ReducerRef(
                    reducer_id="select_tournament:join_candidate_scores",
                    input_ref="candidates",
                    output_ref="candidate_scores",
                ),
            ),
        ),
        metadata={
            "candidates": candidate_list,
            "prompt_key": "score_candidate",
            "prompt_bundle": str(_PROMPTS),
        },
    )
    pairwise_bracket = Step(
        id="pairwise_bracket",
        kind="agent",
        label="Run pairwise elimination bracket",
        inputs=(Input(name="candidate_scores", value_ref="score_candidates.candidate_scores"),),
        outputs=(Output(name="bracket_result"),),
        capabilities=(Capability(id="review", route="bracket"),),
        metadata={
            "prompt_key": "pairwise_bracket",
            "prompt_bundle": str(_PROMPTS),
        },
    )
    winner = Step(
        id="winner",
        kind="emit",
        label="Emit tournament winner",
        inputs=(Input(name="bracket_result", value_ref="pairwise_bracket.bracket_result"),),
        outputs=(Output(name="winner_result"),),
        capabilities=(Capability(id="review", route="winner"),),
        metadata={
            "prompt_key": "winner",
            "terminal": True,
            "prompt_bundle": str(_PROMPTS),
        },
    )

    return Pipeline(
        id="select-tournament",
        version="m5-phase3",
        steps=(score_candidates, pairwise_bracket, winner),
        routes=(
            Route(id="score_candidates:pairwise_bracket", source="score_candidates", target="pairwise_bracket", label="default"),
            Route(id="pairwise_bracket:winner", source="pairwise_bracket", target="winner", label="default"),
        ),
        capabilities=(Capability(id="review", route="default"),),
        metadata={
            "name": name,
            "description": description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
            "candidates": candidate_list,
        },
    )


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
