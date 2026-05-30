"""Join-callable primitives for pipeline pattern composition."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping

from megaplan._pipeline.pattern_types import JoinFn
from megaplan._pipeline.types import (
    GateRecommendation,
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
)


def majority_vote(
    panel_output_key: str = "verdict",
    *,
    label_extractor: Callable[[StepResult], str | None] | None = None,
    default_on_tie: str | None = None,
) -> JoinFn:
    """Return a join callable that picks the majority recommendation.

    Args:
        panel_output_key: reserved for future per-key tallying.
        label_extractor: callable extracting a vote label from a
            StepResult. Default skips None verdicts/recommendations.
        default_on_tie: label when no majority exists or the panel is
            empty. ``None`` means ``verdict.recommendation`` will be
            ``None`` (no tiebreaker label injected).
    """

    del panel_output_key  # reserved for future per-key tallying

    _extract = label_extractor or (
        lambda r: (
            r.verdict.recommendation
            if r.verdict is not None and r.verdict.recommendation is not None
            else None
        )
    )

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        recs: list[str] = []
        for result in results:
            label = _extract(result)
            if label is not None:
                recs.append(label)

        chosen: str | None
        tally: tuple[float, ...] = ()
        if not recs:
            chosen = default_on_tie
        else:
            counts: Counter[str] = Counter(recs)
            top = counts.most_common()
            tally = tuple(float(c) for _, c in top)
            if len(top) > 1 and top[0][1] == top[1][1]:
                chosen = default_on_tie
            else:
                chosen = top[0][0]

        reduce_result = ReduceResult(
            value=chosen,
            label=chosen or "",
            scores=tally,
            provenance=(),
        )
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=chosen,  # type: ignore[arg-type]  # Note: M2 will re-type
            payload={"reduce_result": reduce_result},
        )
        return StepResult(
            verdict=verdict,
            next=chosen or "halt",  # Note: M2 will re-type
        )

    return _join


def weighted_vote(
    weights: Mapping[str, float],
    *,
    label_extractor: Callable[[StepResult], str | None] | None = None,
    default_on_tie: str | None = None,
) -> JoinFn:
    """Return a join callable that picks the highest-weighted recommendation.

    Args:
        weights: mapping of reviewer_id → weight (missing ids → 0.0).
        label_extractor: callable extracting a vote label from a
            StepResult. Default skips None verdicts/recommendations.
        default_on_tie: label when no weighted winner exists or the
            panel is empty. ``None`` means ``verdict.recommendation``
            will be ``None`` (no tiebreaker label injected).
    """

    weights_map: dict[str, float] = dict(weights)

    _extract = label_extractor or (
        lambda r: (
            r.verdict.recommendation
            if r.verdict is not None and r.verdict.recommendation is not None
            else None
        )
    )

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        tally_map: dict[str, float] = {}
        any_vote = False
        for result in results:
            label = _extract(result)
            if label is None:
                continue
            reviewer_id: Any = None
            payload = result.verdict.payload if result.verdict else {}
            if isinstance(payload, Mapping):
                reviewer_id = payload.get("reviewer_id")
            weight = (
                weights_map.get(str(reviewer_id), 0.0)
                if reviewer_id is not None
                else 0.0
            )
            tally_map[label] = tally_map.get(label, 0.0) + weight
            any_vote = True

        chosen: str | None
        tally: tuple[float, ...] = ()
        if not any_vote or not tally_map:
            chosen = default_on_tie
        else:
            ranked = sorted(tally_map.items(), key=lambda kv: kv[1], reverse=True)
            tally = tuple(v for _, v in ranked)
            if ranked[0][1] <= 0.0:
                chosen = default_on_tie
            elif len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                chosen = default_on_tie
            else:
                chosen = ranked[0][0]

        reduce_result = ReduceResult(
            value=chosen,
            label=chosen or "",
            scores=tally,
            provenance=(),
        )
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=chosen,  # type: ignore[arg-type]  # Note: M2 will re-type
            payload={"reduce_result": reduce_result},
        )
        return StepResult(
            verdict=verdict,
            next=chosen or "halt",  # Note: M2 will re-type
        )

    return _join
