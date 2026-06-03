"""Neutral topology-building functions for Arnold pipeline patterns.

Every function in this module is *stateless*: it returns primitive
pipeline objects (:class:`Stage`, :class:`ParallelStage`,
:class:`Pipeline`, :class:`Step`, or a join callable) that callers wire
into their pipeline via :func:`Pipeline.builder` or manual Stage/Edge
construction.  No new primitive types are introduced — these functions
assemble topology and join callables; the Step implementations
themselves live elsewhere (e.g. ``_pipeline/stages/``,
``_pipeline/steps/``).

Sprint conventions encoded here:

* Gate stages produced by :func:`critique_revise_gate_loop` carry the
  four required ``kind="gate"`` recommendation edges (one per literal
  of the planning binding) ahead of any caller-supplied
  ``gate_extra_edges``. The executor's typed-verdict dispatch resolves
  them in preference to label-string matching.
* Panel fan-out stages produced by :func:`panel_parallel` collate per-
  reviewer outputs into ``{reviewer_id}.{label}`` keys; per-reviewer
  artifact pathing under ``<stage>/<reviewer>/v<N>.md`` is owned by the
  reviewer Steps themselves and surfaces through their ``result.outputs``.
* :func:`subpipeline_call` is a thin wrapper around :class:`SubloopStep`
  for documentation-first use in future user pipelines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

# restore_and_diverge import removed — used only by escalate_via_subpipeline (moved to megaplan/pipelines/megaplan/planning_topology.py)
from arnold.pipeline.pattern_types import PromoteFn
from arnold.pipeline.subloop import SubloopStep
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)
def panel_parallel(
    name: str,
    reviewers: tuple[tuple[str, Step], ...],
    *,
    edges: tuple[Edge, ...] = (),
    merge_strategy: str = "none",
    max_workers: int | None = None,
    next_label: str = "next",
) -> ParallelStage:
    """Pure :class:`ParallelStage` fan-out across *reviewers*.

    Each ``(reviewer_id, Step)`` pair runs concurrently. The built-in join
    collates per-reviewer outputs into ``{reviewer_id}.{label}`` keys
    (e.g. ``"pessimist.draft"``) so a downstream agent can resolve
    ``<panel>.*`` references in reviewer-list order via
    :func:`step_helpers.resolve_inputs`.

    Per-reviewer artifact pathing under ``<stage>/<reviewer>/v<N>.md`` is
    owned by the reviewer Steps themselves; the join just relays each
    reviewer's :attr:`StepResult.outputs` mapping under a prefixed key.
    The join emits ``next=next_label`` (default ``"next"``) so callers
    can wire a single outgoing :class:`Edge` to the synthesis stage.

    *merge_strategy* is accepted for future structural / textual / none
    merge implementations; today only ``"none"`` is meaningful and the
    parameter is reserved for forward compatibility. There is no
    sequential retry inside the pattern — that is an executor-level
    concern and is intentionally out of scope here.
    """

    del merge_strategy  # reserved for future expansion; runtime behaviour is "none"

    reviewer_ids: tuple[str, ...] = tuple(rid for rid, _ in reviewers)
    steps: tuple[Step, ...] = tuple(step for _, step in reviewers)

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # join is path-agnostic; reviewer Steps own their artifact paths
        outputs: dict[str, Path] = {}
        for rid, result in zip(reviewer_ids, results):
            for label, path in result.outputs.items():
                outputs[f"{rid}.{label}"] = path
        return StepResult(outputs=outputs, next=next_label)

    return ParallelStage(
        name=name,
        steps=steps,
        join=_join,
        edges=edges,
        max_workers=max_workers,
    )


def alternating_turns(
    roles: tuple[tuple[str, Step], ...],
    *,
    history_strategy: str = "append",
    max_rounds: int = 10,
    until_condition: Callable[[Mapping[str, Any]], bool] | None = None,
    loop_target: str | None = None,
) -> dict[str, Stage]:
    """N-agent alternating workshop topology.

    Returns ``{role_name: Stage}`` chaining roles linearly
    ``role_0 → role_1 → ... → role_(N-1)``. The terminal role loops back
    to *loop_target* (default: the first role's name) so the sequence
    can iterate.

    *history_strategy*, *max_rounds*, and *until_condition* are accepted
    for documentation parity with future user pipelines; today the
    wrapped Steps must consult them via :attr:`StepContext.state`. Wrap
    the loop with :func:`iterate_until` to add a counting / escape Stage
    on top.
    """

    del history_strategy, max_rounds  # consumed by Step.run, not topology

    if not roles:
        raise ValueError("alternating_turns: roles must be non-empty")

    names: tuple[str, ...] = tuple(role_name for role_name, _ in roles)
    target_for_loop: str = loop_target if loop_target is not None else names[0]

    stages: dict[str, Stage] = {}
    terminal_name = names[-1]
    for idx, (role_name, role_step) in enumerate(roles):
        next_name: str = names[idx + 1] if idx + 1 < len(names) else target_for_loop
        stages[role_name] = Stage(
            name=role_name,
            step=role_step,
            edges=(Edge(label=next_name, target=next_name),),
            loop_condition=until_condition if role_name == terminal_name else None,
        )
    return stages


def subpipeline_call(
    child_pipeline: Pipeline,
    *,
    promote: PromoteFn,
    artifact_subdir: str | None = None,
    name: str = "subpipeline",
) -> SubloopStep:
    """Thin wrapper that constructs a :class:`SubloopStep` around
    *child_pipeline*.

    Documentation-first primitive for future user pipelines. The
    executor's ``kind="subloop"`` dispatch runs the child as a nested
    pipeline; *promote* maps the child's terminal state ``dict`` to a
    literal of the planning binding on the parent's
    :class:`PipelineVerdict`.

    Note: :class:`SubloopStep` copies the parent ``StepContext.state``
    into the child via ``dict(ctx.state)`` — the child's state patches
    do NOT propagate back to the parent state. Only the *promote*
    callable's recommendation flows up via :class:`PipelineVerdict`.
    """

    return SubloopStep(
        name=name,
        child_pipeline=child_pipeline,
        promote=promote,
        artifact_subdir=artifact_subdir,
    )
def iterate_until(
    stage: Stage,
    *,
    condition: Callable[[Any], bool] | None = None,
    max_iterations: int = 10,
    iterate_label: str = "iterate",
    halt_label: str = "halt",
) -> Stage:
    """Wrap *stage* with a self-loop edge plus a halt edge.

    *condition* and *max_iterations* document the contract; the wrapped
    Step's ``run()`` consults :attr:`StepContext.state` and emits
    ``next=iterate_label`` while the loop should continue, or
    ``next=halt_label`` to terminate. The returned :class:`Stage`
    carries the original outgoing edges plus
    ``Edge(label=iterate_label, target=stage.name)`` and
    ``Edge(label=halt_label, target="halt")``.
    """

    from megaplan._pipeline.pattern_stops import LoopState
    from megaplan._pipeline.loop_node import LoopNode

    _max = int(max_iterations)

    if condition is None:
        # Default predicate: caller relies entirely on the cap.
        def _default_pred(_ls: Any) -> bool:
            return False

        pred: Callable[[Any], bool] = _default_pred
    else:
        pred = condition

    node = LoopNode(predicate=pred, max_iterations=_max)
    # Stage.loop_condition is consulted per-iteration; route it through the
    # LoopNode so the cap + budget + predicate composition is enforced in
    # one place.  Existing legacy callers continue to see a plain callable.
    stored: Callable[[LoopState], bool] = node.should_halt

    return Stage(
        name=stage.name,
        step=stage.step,
        edges=stage.edges
        + (
            Edge(label=iterate_label, target=stage.name),
            Edge(label=halt_label, target="halt"),
        ),
        loop_condition=stored,
    )

__all__ = [
    "alternating_turns",
    "iterate_until",
    "panel_parallel",
    "subpipeline_call",
]

