"""Megaplan-policy topology functions — relocated from arnold/pipeline/pattern_topology.py.

These functions encode Megaplan-specific planning vocabulary
(GateRecommendation literals, Overlay, restore_and_diverge) and are
intentionally kept separate from the neutral arnold.pipeline topology
primitives.

Each function imports shared types from ``arnold.pipeline.*`` and
Megaplan-specific types from ``megaplan._pipeline.*``.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Mapping, cast

from arnold.pipeline.pattern_types import PromoteFn
from arnold.pipeline.subloop import SubloopStep
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
)
from megaplan._pipeline._forward_m2_m3 import restore_and_diverge
from megaplan._pipeline.types import (
    GateRecommendation,
    Overlay,
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
    """Compose the critique -> gate -> revise cycle as three Stages.

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


def escalate_if(
    condition: Callable[[Mapping[str, Any]], bool],
    escalation_handler: Step,
) -> tuple[Step, Edge]:
    """Return the ``(escalation_handler, escape_edge)`` pair.

    Documentation-first: callers plug *escalation_handler* into the host
    stage's neighbour graph and append the produced *escape_edge*
    (``kind="gate"``, ``recommendation="escalate"``) as an outgoing edge.
    *condition* documents when the host Step should emit a
    :class:`PipelineVerdict` whose ``recommendation == "escalate"``; the host
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
    ``recommendation`` is :attr:`restore_and_diverge.name`
    (``"escalate"``).  Callers wire the returned *subloop* into the host
    pipeline as a :class:`SubloopStep` and append the *escape_edge* as an
    outgoing :class:`Edge` on the preceding stage.

    *condition* documents when the host Step should trigger this path;
    the host Step's ``run()`` consults it against
    :attr:`StepContext.state`.  *deadlock_pipeline* is the child
    :class:`Pipeline` that attempts resolution.
    """
    del condition

    from arnold.pipeline.pattern_topology import subpipeline_call as _subpipeline_call

    subloop = _subpipeline_call(
        deadlock_pipeline,
        promote=promote,
        artifact_subdir=artifact_subdir,
        name=name,
    )

    escape_edge = Edge(
        label=restore_and_diverge.name,
        target=subloop.name,
        kind="gate",
        recommendation=restore_and_diverge.name,
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
    """

    del criteria

    edges: tuple[Edge, ...] = (
        Edge(label="pass", target=on_pass),
        Edge(label="fail", target=on_fail),
    )
    if on_pass not in {"pass", "fail"}:
        edges = edges + (Edge(label=on_pass, target=on_pass),)
    return Stage(name=name, step=step, edges=edges)


def mode_prompts(
    modes_dict: Mapping[str, Mapping[str, str]],
) -> Callable[[str], Overlay]:
    """Build a stage-rewriter overlay that swaps ``prompt_key`` per mode
    without changing topology.

    *modes_dict* is ``{mode_name: {stage_name: prompt_key}}``. The
    returned ``Callable[[mode], Overlay]`` produces an :class:`Overlay`
    parameterised on the active mode; applying the overlay rewrites each
    matching :class:`Stage`'s Step via :func:`dataclasses.replace`
    setting the new ``prompt_key``.
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


__all__ = [
    "critique_revise_gate_loop",
    "escalate_if",
    "escalate_via_subpipeline",
    "phase_zero_gate",
    "mode_prompts",
]
