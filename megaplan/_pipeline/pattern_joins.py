"""Join-callable primitives for pipeline pattern composition."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from megaplan._pipeline.flags import typed_ports_on
from megaplan._pipeline.pattern_types import JoinFn
from megaplan._pipeline.types import (
    PipelineVerdict,
    ReduceResult,
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
        recs: list[str] = []
        for result in results:
            if result.verdict is not None and result.verdict.recommendation is not None:
                recs.append(result.verdict.recommendation)
        counts: Counter[str] = Counter(recs)
        chosen_label: str | None
        if not recs:
            chosen_label = None
        else:
            top = counts.most_common()
            if len(top) > 1 and top[0][1] == top[1][1]:
                chosen_label = None
            else:
                chosen_label = top[0][0]

        if typed_ports_on():
            reduce_result = ReduceResult(
                value=chosen_label,
                tally=dict(counts),
                label=chosen_label,
            )
            return StepResult(
                outputs={},
                verdict=PipelineVerdict(
                    score=1.0,
                    recommendation=None,
                    payload={"reduce_result": reduce_result},
                ),
                next=chosen_label if chosen_label is not None else "tiebreaker",
            )

        chosen: str = (
            chosen_label if chosen_label is not None else "tiebreaker"
        )
        verdict = PipelineVerdict(score=1.0, recommendation=chosen)
        return StepResult(verdict=verdict, next=chosen)

    return _join


def weighted_vote(weights: Mapping[str, float]) -> JoinFn:
    """Return a join callable that picks the highest-weighted recommendation."""

    weights_map: dict[str, float] = dict(weights)

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        tally: dict[str, float] = {}
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

        chosen_label: str | None
        if not any_vote or not tally:
            chosen_label = None
        else:
            ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
            if ranked[0][1] <= 0.0:
                chosen_label = None
            elif len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                chosen_label = None
            else:
                chosen_label = ranked[0][0]

        if typed_ports_on():
            tally_str = {str(k): v for k, v in tally.items()}
            reduce_result = ReduceResult(
                value=chosen_label,
                tally=tally_str,
                label=chosen_label,
            )
            return StepResult(
                outputs={},
                verdict=PipelineVerdict(
                    score=1.0,
                    recommendation=None,
                    payload={"reduce_result": reduce_result},
                ),
                next=chosen_label if chosen_label is not None else "tiebreaker",
            )

        chosen: str = (
            chosen_label if chosen_label is not None else "tiebreaker"
        )
        verdict = PipelineVerdict(score=1.0, recommendation=chosen)
        return StepResult(verdict=verdict, next=chosen)

    return _join
