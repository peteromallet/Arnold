"""Static topology-building functions for pipeline patterns.

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
  four required ``kind="decision"`` edges (one per literal
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

import dataclasses
from pathlib import Path
from typing import Any, Callable, Mapping, cast

from megaplan._pipeline._forward_m2_m3 import restore_and_diverge  # TODO(M3): sentinel → RoutingKey
from megaplan._pipeline.pattern_types import PromoteFn
from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.types import (
    Edge,
    Overlay,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)




def critique_revise_gate_loop(
    critique_step: Step,
    gate_step: Step,
    revise_step: Step,
    *,
    on_proceed: str,
    on_iterate: str,
    on_tiebreaker: str,
    on_escalate: str,
    critique_fallback_edges: tuple[Edge, ...] = (),
    gate_extra_edges: tuple[Edge, ...] = (),
    revise_target: str = "critique",
) -> dict[str, Stage]:
    """Compose the critique → gate → revise cycle as three Stages.

    Returns ``{"critique": Stage, "gate": Stage, "revise": Stage}``.

    The gate stage carries ``kind='decision'`` edges for the four
    planning labels (iterate / proceed / tiebreaker / escalate) targeting
    *on_iterate* / *on_proceed* / *on_tiebreaker* / *on_escalate*, plus
    any *gate_extra_edges* appended in order.  Edge construction is
    delegated to
    :func:`megaplan.pipelines.planning.routing.critique_revise_gate_routing`.

    The critique stage carries only *critique_fallback_edges*
    (caller-provided, typically the two label-fallback edges to
    ``"gate"``); when empty the critique stage defaults to a single
    ``Edge(label="gate", target="gate")``. The revise stage routes back
    to *revise_target* (default ``"critique"``, forming the loop).

    Caller is responsible for wiring inbound edges to ``"critique"`` and
    for naming the downstream stages that the four gate edges point at.
    """

    # Delegate edge construction to the planning plugin (Megaplan-owned
    # decision literals live ONLY in megaplan.pipelines.planning.routing).
    # Lazy import to avoid circular dependency (planning/__init__.py imports
    # from megaplan._pipeline.patterns).
    from arnold.pipelines.megaplan.routing import critique_revise_gate_routing as _routing

    routing = _routing(
        on_proceed=on_proceed,
        on_iterate=on_iterate,
        on_tiebreaker=on_tiebreaker,
        on_escalate=on_escalate,
        on_revise=revise_target,
        gate_extra_edges=gate_extra_edges,
    )

    critique_edges: tuple[Edge, ...] = tuple(critique_fallback_edges) or (
        Edge(label="gate", target="gate"),
    )

    return {
        "critique": Stage(name="critique", step=critique_step, edges=critique_edges),
        "gate": Stage(name="gate", step=gate_step, edges=routing["gate"]),
        "revise": Stage(
            name="revise",
            step=revise_step,
            edges=routing["revise"],
        ),
    }


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


def mode_prompts(
    modes_dict: Mapping[str, Mapping[str, str]],
) -> Callable[[str], Overlay]:
    """Build a stage-rewriter overlay that swaps ``prompt_key`` per mode
    without changing topology.

    *modes_dict* is ``{mode_name: {stage_name: prompt_key}}``. The
    returned ``Callable[[mode], Overlay]`` produces an :class:`Overlay`
    parameterised on the active mode; applying the overlay rewrites each
    matching :class:`Stage`'s Step via :func:`dataclasses.replace`
    setting the new ``prompt_key``. :class:`ParallelStage` entries and
    Steps that are not dataclasses (or whose dataclass has no
    ``prompt_key`` field) are passed through unchanged.
    """

    def _build(mode: str) -> Overlay:
        per_stage: Mapping[str, str] = modes_dict.get(mode, {})

        def _apply(pipeline: Pipeline) -> Pipeline:
            new_stages: dict[str, Stage | ParallelStage] = {}
            for stage_name, stage in pipeline.stages.items():
                if isinstance(stage, Stage) and stage_name in per_stage:
                    step_any: Any = stage.step
                    if dataclasses.is_dataclass(step_any) and not isinstance(step_any, type):
                        try:
                            new_step = cast(
                                Step,
                                dataclasses.replace(step_any, prompt_key=per_stage[stage_name]),
                            )
                            new_stages[stage_name] = Stage(
                                name=stage.name, step=new_step, edges=stage.edges
                            )
                            continue
                        except TypeError:
                            pass
                new_stages[stage_name] = stage
            return Pipeline(
                stages=new_stages,
                entry=pipeline.entry,
                overlays=pipeline.overlays,
            )

        return Overlay(name=f"mode_prompts:{mode}", apply=_apply)

    return _build


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


def escalate_if(
    condition: Callable[[Mapping[str, Any]], bool],
    escalation_handler: Step,
) -> tuple[Step, Edge]:
    """Return the ``(escalation_handler, escape_edge)`` pair.

    Documentation-first: callers plug *escalation_handler* into the host
    stage's neighbour graph and append the produced *escape_edge*
    (``kind="decision"``, ``label="escalate"``) as an outgoing edge.
    *condition* documents when the host Step should emit a
    :class:`PipelineVerdict` whose ``label == "escalate"``; the host
    Step's ``run()`` consults it against :attr:`StepContext.state`.
    """

    del condition  # consumed by host Step

    from arnold.pipelines.megaplan.routing import PLAN_ESCALATE as _ESC

    escape_edge = Edge(
        label=_ESC,
        target=escalation_handler.name,
        kind="decision",
    )
    return escalation_handler, escape_edge



def escalate_via_subpipeline(
    condition: Callable[[Mapping[str, Any]], bool],
    deadlock_pipeline: Pipeline,
    promote: PromoteFn,
    *,
    name: str = "escalate",
    artifact_subdir: str | None = None,
) -> tuple[SubloopStep, Edge]:
    """Return the ``(subloop, escape_edge)`` pair for divergent escalation.

    Composes :func:`subpipeline_call` with an escape :class:`Edge` whose
    label is :attr:`restore_and_diverge.name`
    (``\"escalate\"`` — with :func:`# TODO(M3) <megaplan._pipeline._forward_m2_m3.restore_and_diverge>`
    marker).  Callers wire the returned *subloop* into the host pipeline
    as a :class:`SubloopStep` and append the *escape_edge* as an outgoing
    :class:`Edge` on the preceding stage, exactly as :func:`escalate_if`
    does for an inline escalation handler.

    *condition* documents when the host Step should trigger this path;
    the host Step's ``run()`` consults it against
    :attr:`StepContext.state`.  *deadlock_pipeline* is the child
    :class:`Pipeline` that attempts resolution; if it deadlocks the
    *promote* callable returns the :data:`RoutingKey` that feeds into the
    escape edge.  *artifact_subdir* isolates the child pipeline's
    artifacts under ``<plan_dir>/<artifact_subdir>/``.

    Ports
    -----
    * **consumes** — ``gated@artifact``: the artifact (and surrounding
      state) produced by the preceding gate stage that triggered the
      escalation.
    * **produces** — ``resolved@artifact``: the artifact (and state)
      after the subpipeline resolves (or fails to resolve) the deadlock.

    Keep-alive invariants
    ---------------------
    * :func:`escalate_if` and :func:`subpipeline_call`
      are left intact and remain exported through
      :mod:`megaplan._pipeline.patterns`.
    * The escape edge's ``label`` is
      :attr:`restore_and_diverge.name` (``"escalate"``) so the
      decision-dispatch path can route it alongside the existing
      ``kind="decision"`` edges produced by :func:`escalate_if` and
      :func:`critique_revise_gate_loop`.
    """
    del condition  # consumed by the host Step that invokes this path

    subloop = subpipeline_call(
        deadlock_pipeline,
        promote=promote,
        artifact_subdir=artifact_subdir,
        name=name,
    )

    # TODO(M3): when M3 maps restore_and_diverge as a RoutingKey, the
    # label below will be RoutingKey(name='restore_and_diverge',
    # kind='restore').  For M5a it is the literal 'escalate' so the
    # existing decision-dispatch executor handles it.
    escape_edge = Edge(
        label=restore_and_diverge.name,
        target=subloop.name,
        kind="decision",
    )
    return subloop, escape_edge

def phase_zero_gate(
    step: Step,
    *,
    name: str = "prep",
    on_pass: str = "plan",
    on_fail: str = "halt",
    criteria: Callable[[Mapping[str, Any]], bool] | None = None,
) -> Stage:
    """Phase-0 objective gate stage.

    Runs *step* and routes its emitted next-label to *on_pass*
    (default ``"plan"``) or *on_fail* (default ``"halt"``). *criteria*
    documents the objective check the Step performs against
    :attr:`StepContext.state`; the wrapped Step's ``run()`` consults it.

    The returned :class:`Stage` carries three edges so the gate handles
    explicit ``"pass"`` / ``"fail"`` labels plus the bare next-label
    fallback used by megaplan's existing :class:`PrepStep`
    (``next=on_pass``):

    * ``Edge("pass",  target=on_pass)``
    * ``Edge("fail",  target=on_fail)``
    * ``Edge(on_pass, target=on_pass)``
    """

    del criteria  # consumed by the Step impl

    edges: tuple[Edge, ...] = (
        Edge(label="pass", target=on_pass),
        Edge(label="fail", target=on_fail),
    )
    if on_pass not in {"pass", "fail"}:
        edges = edges + (Edge(label=on_pass, target=on_pass),)
    return Stage(name=name, step=step, edges=edges)
