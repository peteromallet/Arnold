"""Higher-order review pattern constructors.

Stability:
    public: ``critique``, ``review``, ``revise``, ``tournament``
    provisional: all constructors in this module are provisional until the
        canonical fixture matrix validates every lowering detail.
    internal: helper route and node ID generation

These patterns compose lower-level DSL and control patterns into explicit
nodes and routes.  They do not hide review logic inside opaque subpipelines.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.workflow import (
    LoopPolicy,
    Output,
    Route,
    SourceSpan,
    Step,
    SuspensionRoute,
    WorkflowPolicy,
)
from arnold.patterns._core import PatternBlock, _as_hook_ref


def critique(
    step_id: str,
    target_id: str,
    *,
    critique_ref: str | object,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a critique step plus a route from ``target_id``."""

    hook = _as_hook_ref(critique_ref, node_id=step_id, field="critique_ref")
    step = Step(
        id=step_id,
        kind="critique",
        source_span=source_span,
        metadata={**(metadata or {}), "critique_ref": hook.spec},
    )
    routes = (
        Route(
            id=f"{target_id}-{step_id}",
            source=target_id,
            target=step_id,
            label="critique",
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def review(
    step_id: str,
    target_id: str,
    *,
    review_ref: str | object,
    approve_ref: str | object,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a review step plus approve/reject routes from ``target_id``."""

    review_hook = _as_hook_ref(review_ref, node_id=step_id, field="review_ref")
    approve_hook = _as_hook_ref(approve_ref, node_id=step_id, field="approve_ref")
    step = Step(
        id=step_id,
        kind="review",
        source_span=source_span,
        metadata={
            **(metadata or {}),
            "review_ref": review_hook.spec,
            "approve_ref": approve_hook.spec,
        },
    )
    routes = (
        Route(
            id=f"{target_id}-{step_id}",
            source=target_id,
            target=step_id,
            label="review",
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def revise(
    step_id: str,
    target_id: str,
    *,
    revise_ref: str | object,
    until_ref: str | object,
    max_iterations: int,
    reentry_id: str,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a bounded revise step plus a reentry route from ``target_id``."""

    revise_hook = _as_hook_ref(revise_ref, node_id=step_id, field="revise_ref")
    until_hook = _as_hook_ref(until_ref, node_id=step_id, field="until_ref")
    step = Step(
        id=step_id,
        kind="revise",
        policy=WorkflowPolicy(
            loop=LoopPolicy(max_iterations=max_iterations, until_ref=until_hook.spec),
            suspension_routes=(SuspensionRoute(route_id=f"{step_id}-reentry", reentry_id=reentry_id),),
        ),
        source_span=source_span,
        metadata={**(metadata or {}), "revise_ref": revise_hook.spec},
    )
    routes = (
        Route(
            id=f"{target_id}-{step_id}",
            source=target_id,
            target=step_id,
            label="revise",
            condition_ref=reentry_id,
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def tournament(
    step_id: str,
    candidate_ids: tuple[str, ...],
    merge_id: str,
    *,
    winner_ref: str | object,
    tie_ref: str | object,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return an explicit tournament with two full tiebreaker rounds.

    Provisional: the exact judge/tiebreaker node count is stable and
    inspectable, but the condition labels may be refined by later milestones.
    """

    winner_hook = _as_hook_ref(winner_ref, node_id=step_id, field="winner_ref")
    tie_hook = _as_hook_ref(tie_ref, node_id=step_id, field="tie_ref")
    judge_id = f"{step_id}-judge"
    tiebreak1_id = f"{step_id}-tiebreak-1"
    tiebreak2_id = f"{step_id}-tiebreak-2"
    merge_step = Step(
        id=merge_id,
        kind="merge",
        outputs=(Output("winner"),),
        source_span=source_span,
        metadata={**(metadata or {}), "winner_ref": winner_hook.spec, "tie_ref": tie_hook.spec},
    )

    def make_branch(branch_id: str) -> Step:
        return Step(
            id=branch_id,
            kind="branch",
            metadata={
                "winner_ref": winner_hook.spec,
                "tie_ref": tie_hook.spec,
            },
        )

    judge = make_branch(judge_id)
    tiebreak1 = make_branch(tiebreak1_id)
    tiebreak2 = make_branch(tiebreak2_id)

    incoming_routes = tuple(
        Route(
            id=f"{candidate_id}-{judge_id}",
            source=candidate_id,
            target=judge_id,
            label="candidate",
        )
        for candidate_id in candidate_ids
    )
    judge_routes = (
        Route(
            id=f"{judge_id}-{merge_id}",
            source=judge_id,
            target=merge_id,
            label="winner",
            condition_ref=winner_hook.spec,
        ),
        Route(
            id=f"{judge_id}-{tiebreak1_id}",
            source=judge_id,
            target=tiebreak1_id,
            label="tie",
            condition_ref=tie_hook.spec,
        ),
    )
    tiebreak1_routes = (
        Route(
            id=f"{tiebreak1_id}-{merge_id}",
            source=tiebreak1_id,
            target=merge_id,
            label="winner",
            condition_ref=winner_hook.spec,
        ),
        Route(
            id=f"{tiebreak1_id}-{tiebreak2_id}",
            source=tiebreak1_id,
            target=tiebreak2_id,
            label="tie",
            condition_ref=tie_hook.spec,
        ),
    )
    tiebreak2_routes = (
        Route(
            id=f"{tiebreak2_id}-{merge_id}",
            source=tiebreak2_id,
            target=merge_id,
            label="winner",
            condition_ref=winner_hook.spec,
        ),
    )
    return PatternBlock(
        steps=(judge, tiebreak1, tiebreak2, merge_step),
        routes=(*incoming_routes, *judge_routes, *tiebreak1_routes, *tiebreak2_routes),
    )
