"""Join-callable primitives for pipeline pattern composition."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping

from arnold.pipeline.pattern_types import JoinFn
from arnold.pipeline.flags import typed_ports_on
from arnold.pipeline.types import (
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
)


def majority_vote(
    panel_output_key: str = "verdict",
    *,
    label_extractor: Callable[[StepResult], str | None] | None = None,
    default_on_tie: str | None = "tiebreaker",
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
        typed = typed_ports_on()
        recs: list[str] = []
        counts: Counter[str] = Counter()
        for result in results:
            label = _extract(result)
            if label is not None:
                recs.append(label)
                counts[label] += 1

        chosen: str | None
        next_label: str
        tally: tuple[float, ...] = ()
        if not recs:
            chosen = None
            next_label = default_on_tie or "halt"
        else:
            top = counts.most_common()
            tally = tuple(float(c) for _, c in top)
            if len(top) > 1 and top[0][1] == top[1][1]:
                chosen = None
                next_label = default_on_tie or "halt"
            else:
                chosen = top[0][0]
                next_label = chosen

        reduce_result = ReduceResult(
            value=chosen,
            label=chosen,
            scores=tally,
            tally=dict(counts),
            provenance=(),
        )
        recommendation = None if typed else (chosen or next_label)
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=recommendation,  # type: ignore[arg-type]
            payload={"reduce_result": reduce_result} if typed else {},
        )
        return StepResult(
            verdict=verdict,
            next=next_label,  # Note: M2 will re-type
        )

    return _join


def weighted_vote(
    weights: Mapping[str, float],
    *,
    label_extractor: Callable[[StepResult], str | None] | None = None,
    default_on_tie: str | None = "tiebreaker",
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
        typed = typed_ports_on()
        tally_map: dict[str, float] = {}
        vote_counts: Counter[str] = Counter()
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
            vote_counts[label] += 1
            any_vote = True

        chosen: str | None
        next_label: str
        tally: tuple[float, ...] = ()
        if not any_vote or not tally_map:
            chosen = None
            next_label = default_on_tie or "halt"
        else:
            ranked = sorted(tally_map.items(), key=lambda kv: kv[1], reverse=True)
            tally = tuple(v for _, v in ranked)
            if ranked[0][1] <= 0.0:
                chosen = None
                next_label = default_on_tie or "halt"
            elif len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                chosen = None
                next_label = default_on_tie or "halt"
            else:
                chosen = ranked[0][0]
                next_label = chosen

        reduce_result = ReduceResult(
            value=chosen,
            label=chosen,
            scores=tally,
            tally=dict(vote_counts),
            provenance=(),
        )
        recommendation = None if typed else (chosen or next_label)
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=recommendation,  # type: ignore[arg-type]
            payload={"reduce_result": reduce_result} if typed else {},
        )
        return StepResult(
            verdict=verdict,
            next=next_label,  # Note: M2 will re-type
        )

    return _join

__all__ = [
    "majority_vote",
    "weighted_vote",
]

