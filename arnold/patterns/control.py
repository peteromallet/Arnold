"""Control topology pattern constructors.

Stability:
    public: ``branch``, ``loop``, ``fanout``, ``panel``, ``retry``,
        ``human_gate``
    provisional: ``panel`` and ``retry`` composite helpers
    internal: route-id generation helpers

These constructors lower branch, loop, fanout, retry, and suspension shapes
into explicit nodes and routes.  Loops and retries use bounded reentry routes
rather than arbitrary graph cycles.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.workflow import (
    Capability,
    FanoutPolicy,
    LoopPolicy,
    Output,
    RetryPolicy,
    Route,
    SourceSpan,
    Step,
    SuspensionRoute,
    WorkflowPolicy,
)
from arnold.patterns._core import PatternBlock, _as_hook_ref, _as_optional_hook_ref


def branch(
    step_id: str,
    *,
    condition_ref: str | object,
    then_id: str,
    else_id: str,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a branch step plus explicit ``then`` and ``else`` routes."""

    condition = _as_hook_ref(condition_ref, node_id=step_id, field="condition_ref")
    step = Step(
        id=step_id,
        kind="branch",
        source_span=source_span,
        metadata={**(metadata or {}), "condition_ref": condition.spec},
    )
    routes = (
        Route(
            id=f"{step_id}-{then_id}",
            source=step_id,
            target=then_id,
            label="then",
            condition_ref=condition.spec,
        ),
        Route(
            id=f"{step_id}-{else_id}",
            source=step_id,
            target=else_id,
            label="else",
            condition_ref=f"{condition.spec}:negated",
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def loop(
    step_id: str,
    body_id: str,
    *,
    until_ref: str | object,
    max_iterations: int,
    reentry_id: str,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a bounded loop step plus a reentry route from ``body_id``."""

    until = _as_hook_ref(until_ref, node_id=step_id, field="until_ref")
    step = Step(
        id=step_id,
        kind="loop",
        policy=WorkflowPolicy(
            loop=LoopPolicy(max_iterations=max_iterations, until_ref=until.spec),
            suspension_routes=(SuspensionRoute(route_id=f"{step_id}-reentry", reentry_id=reentry_id),),
        ),
        source_span=source_span,
        metadata=metadata or {},
    )
    routes = (
        Route(
            id=f"{body_id}-{step_id}",
            source=body_id,
            target=step_id,
            label="reentry",
            condition_ref=reentry_id,
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def fanout(
    step_id: str,
    branch_ids: tuple[str, ...],
    *,
    reducer_ref: str | object | None = None,
    width: int | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a fanout step plus deterministic routes to each branch."""

    reducer = _as_optional_hook_ref(reducer_ref, node_id=step_id, field="reducer_ref")
    merged_metadata = dict(metadata or {})
    if reducer is not None:
        merged_metadata["reducer_ref"] = reducer.spec
    step = Step(
        id=step_id,
        kind="fanout",
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(mode="static", width=width, reducer_ref=reducer.spec if reducer is not None else None),
        ),
        source_span=source_span,
        metadata=merged_metadata,
    )
    routes = tuple(
        Route(
            id=f"{step_id}-{branch_id}",
            source=step_id,
            target=branch_id,
            label="branch",
        )
        for branch_id in branch_ids
    )
    return PatternBlock(steps=(step,), routes=routes)


def panel(
    step_id: str,
    branch_ids: tuple[str, ...],
    merge_id: str,
    *,
    reducer_ref: str | object | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a fanout + merge panel pattern with join routes.

    Provisional: the join-route semantics are product-neutral but may be
    replaced by an explicit reducer node in later milestones.
    """

    fanout_block = fanout(
        step_id,
        branch_ids,
        reducer_ref=reducer_ref,
        source_span=source_span,
        metadata=metadata,
    )
    merge_step = Step(
        id=merge_id,
        kind="merge",
        inputs=tuple(),
        outputs=(Output("result"),),
        source_span=source_span,
    )
    join_routes = tuple(
        Route(
            id=f"{branch_id}-{merge_id}",
            source=branch_id,
            target=merge_id,
            label="join",
        )
        for branch_id in branch_ids
    )
    return PatternBlock(
        steps=(*fanout_block.steps, merge_step),
        routes=(*fanout_block.routes, *join_routes),
    )


def retry(
    step_id: str,
    target_id: str,
    *,
    max_attempts: int,
    retry_on: tuple[str, ...] = (),
    backoff: str = "none",
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PatternBlock:
    """Return a bounded retry step plus attempt and retry-back routes.

    Provisional: retry back-edges are modeled as bounded reentry routes.
    """

    reentry_id = f"{step_id}:retry"
    step = Step(
        id=step_id,
        kind="retry",
        policy=WorkflowPolicy(
            retry=RetryPolicy(max_attempts=max_attempts, backoff=backoff, retry_on=tuple(retry_on)),
            loop=LoopPolicy(max_iterations=max_attempts),
            suspension_routes=(SuspensionRoute(route_id=f"{step_id}-reentry", reentry_id=reentry_id),),
        ),
        source_span=source_span,
        metadata=metadata or {},
    )
    routes = (
        Route(
            id=f"{step_id}-{target_id}",
            source=step_id,
            target=target_id,
            label="attempt",
        ),
        Route(
            id=f"{target_id}-{step_id}",
            source=target_id,
            target=step_id,
            label="retry",
            condition_ref=reentry_id,
        ),
    )
    return PatternBlock(steps=(step,), routes=routes)


def human_gate(
    step_id: str,
    *,
    capability_id: str,
    reentry_id: str,
    payload_schema_hash: str | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Step:
    """Return a generic suspension step gated by a capability."""

    return Step(
        id=step_id,
        kind="suspension",
        capabilities=(Capability(capability_id),),
        policy=WorkflowPolicy(
            suspension_routes=(
                SuspensionRoute(
                    route_id=f"{step_id}-gate",
                    capability_id=capability_id,
                    reentry_id=reentry_id,
                    payload_schema_hash=payload_schema_hash,
                ),
            ),
        ),
        source_span=source_span,
        metadata=metadata or {},
    )
