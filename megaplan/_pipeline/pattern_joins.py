"""Join-callable primitives for pipeline pattern composition."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from megaplan._pipeline.pattern_types import JoinFn
from megaplan._pipeline.types import (
    GateRecommendation,
    PipelineVerdict,
    StepContext,
    StepResult,
)


def majority_vote(
    panel_output_key: str = "verdict",
) -> JoinFn:
    """Return a join callable that picks the majority recommendation."""

    del panel_output_key  # reserved for future per-key tallying

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        recs: list[GateRecommendation] = []
        for result in results:
            if result.verdict is not None and result.verdict.recommendation is not None:
                recs.append(result.verdict.recommendation)
        chosen: GateRecommendation
        if not recs:
            chosen = "tiebreaker"
        else:
            counts: Counter[GateRecommendation] = Counter(recs)
            top = counts.most_common()
            if len(top) > 1 and top[0][1] == top[1][1]:
                chosen = "tiebreaker"
            else:
                chosen = top[0][0]
        verdict = PipelineVerdict(score=1.0, recommendation=chosen)
        return StepResult(verdict=verdict, next=chosen)

    return _join


def weighted_vote(weights: Mapping[str, float]) -> JoinFn:
    """Return a join callable that picks the highest-weighted recommendation."""

    weights_map: dict[str, float] = dict(weights)

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        tally: dict[GateRecommendation, float] = {}
        any_vote = False
        for result in results:
            if result.verdict is None or result.verdict.recommendation is None:
                continue
            rec = result.verdict.recommendation
            reviewer_id: Any = None
            payload = result.verdict.payload
            if isinstance(payload, Mapping):
                reviewer_id = payload.get("reviewer_id")
            weight = (
                weights_map.get(str(reviewer_id), 0.0)
                if reviewer_id is not None
                else 0.0
            )
            tally[rec] = tally.get(rec, 0.0) + weight
            any_vote = True

        chosen: GateRecommendation
        if not any_vote or not tally:
            chosen = "tiebreaker"
        else:
            ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
            if ranked[0][1] <= 0.0:
                chosen = "tiebreaker"
            elif len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                chosen = "tiebreaker"
            else:
                chosen = ranked[0][0]

        verdict = PipelineVerdict(score=1.0, recommendation=chosen)
        return StepResult(verdict=verdict, next=chosen)

    return _join
