"""Reusable pattern functions for composing Pipelines from primitives.

These patterns are stateless: each function returns the appropriate
primitive (:class:`Stage`, :class:`ParallelStage`, ``dict[str, Stage]``,
:class:`Pipeline`, :class:`Step`, or a join callable) that callers wire
into their pipeline via :func:`Pipeline.builder` or manual Stage/Edge
construction.

The library uses only the frozen primitive surface from
:mod:`megaplan._pipeline.types` plus :class:`SubloopStep` from
:mod:`megaplan._pipeline.subloop` and helpers from
:mod:`megaplan._pipeline.step_helpers`. No new primitive types are
introduced — patterns assemble topology and join callables; the Step
implementations themselves live elsewhere (e.g. ``_pipeline/stages/``,
``_pipeline/steps/``).

Sprint conventions encoded here:

* Gate stages produced by :func:`critique_revise_gate_loop` carry the
  four required ``kind="gate"`` recommendation edges (one per
  :data:`GateRecommendation` literal) ahead of any caller-supplied
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
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, cast

from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.types import (
    Edge,
    GateRecommendation,
    Overlay,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    Verdict,
)

PromoteFn = Callable[[dict[str, Any]], GateRecommendation]
JoinFn = Callable[[list[StepResult], StepContext], StepResult]


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

    The gate stage carries exactly the four ``kind="gate"`` recommendation
    edges (iterate / proceed / tiebreaker / escalate) targeting
    *on_iterate* / *on_proceed* / *on_tiebreaker* / *on_escalate*, plus
    any *gate_extra_edges* appended in order. The critique stage carries
    only *critique_fallback_edges* (caller-provided, typically the two
    label-fallback edges to ``"gate"``); when empty the critique stage
    defaults to a single ``Edge(label="gate", target="gate")``. The
    revise stage routes back to *revise_target* (default ``"critique"``,
    forming the loop).

    Caller is responsible for wiring inbound edges to ``"critique"`` and
    for naming the downstream stages that the four gate edges point at.
    """

    gate_edges: tuple[Edge, ...] = (
        Edge(label="iterate", target=on_iterate, kind="gate", recommendation="iterate"),
        Edge(label="proceed", target=on_proceed, kind="gate", recommendation="proceed"),
        Edge(label="tiebreaker", target=on_tiebreaker, kind="gate", recommendation="tiebreaker"),
        Edge(label="escalate", target=on_escalate, kind="gate", recommendation="escalate"),
    ) + tuple(gate_extra_edges)

    critique_edges: tuple[Edge, ...] = tuple(critique_fallback_edges) or (
        Edge(label="gate", target="gate"),
    )

    return {
        "critique": Stage(name="critique", step=critique_step, edges=critique_edges),
        "gate": Stage(name="gate", step=gate_step, edges=gate_edges),
        "revise": Stage(
            name="revise",
            step=revise_step,
            edges=(Edge(label="critique", target=revise_target),),
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

    del history_strategy, max_rounds, until_condition  # consumed by Step.run, not topology

    if not roles:
        raise ValueError("alternating_turns: roles must be non-empty")

    names: tuple[str, ...] = tuple(role_name for role_name, _ in roles)
    target_for_loop: str = loop_target if loop_target is not None else names[0]

    stages: dict[str, Stage] = {}
    for idx, (role_name, role_step) in enumerate(roles):
        next_name: str = names[idx + 1] if idx + 1 < len(names) else target_for_loop
        stages[role_name] = Stage(
            name=role_name,
            step=role_step,
            edges=(Edge(label=next_name, target=next_name),),
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
    :data:`GateRecommendation` on the parent's :class:`Verdict`.

    Note: :class:`SubloopStep` copies the parent ``StepContext.state``
    into the child via ``dict(ctx.state)`` — the child's state patches
    do NOT propagate back to the parent state. Only the *promote*
    callable's recommendation flows up via :class:`Verdict`.
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
    condition: Callable[[Mapping[str, Any]], bool],
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

    del condition, max_iterations  # consumed by Step.run, not topology

    return Stage(
        name=stage.name,
        step=stage.step,
        edges=stage.edges
        + (
            Edge(label=iterate_label, target=stage.name),
            Edge(label=halt_label, target="halt"),
        ),
    )


def escalate_if(
    condition: Callable[[Mapping[str, Any]], bool],
    escalation_handler: Step,
) -> tuple[Step, Edge]:
    """Return the ``(escalation_handler, escape_edge)`` pair.

    Documentation-first: callers plug *escalation_handler* into the host
    stage's neighbour graph and append the produced *escape_edge*
    (``kind="gate"``, ``recommendation="escalate"``) as an outgoing edge.
    *condition* documents when the host Step should emit a
    :class:`Verdict` whose ``recommendation == "escalate"``; the host
    Step's ``run()`` consults it against :attr:`StepContext.state`.
    """

    del condition  # consumed by host Step

    escape_edge = Edge(
        label="escalate",
        target=escalation_handler.name,
        kind="gate",
        recommendation="escalate",
    )
    return escalation_handler, escape_edge


def majority_vote(
    panel_output_key: str = "verdict",
) -> JoinFn:
    """Return a :class:`ParallelStage` ``join`` callable that picks the
    majority :data:`GateRecommendation` across panel reviewer verdicts.

    Behaviour:

    * Each input :class:`StepResult` contributes its
      ``verdict.recommendation`` if the verdict is non-None and carries
      a recommendation literal.
    * The most-common recommendation wins; ties resolve to
      ``"tiebreaker"``. Panels whose reviewers produced no verdicts at
      all also yield ``"tiebreaker"`` so the host stage routes to its
      tiebreaker edge.
    * The returned :class:`StepResult` carries a synthetic
      :class:`Verdict` with the winning recommendation and
      ``next=<recommendation>`` for label-fallback dispatch.

    *panel_output_key* is reserved for future per-key tallying (e.g.
    multiple verdicts per reviewer) and is currently a documentation
    parameter.
    """

    del panel_output_key  # reserved for future per-key tallying

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        recs: list[GateRecommendation] = []
        for r in results:
            if r.verdict is not None and r.verdict.recommendation is not None:
                recs.append(r.verdict.recommendation)
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
        verdict = Verdict(score=1.0, recommendation=chosen)
        return StepResult(verdict=verdict, next=chosen)

    return _join


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
