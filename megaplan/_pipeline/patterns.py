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
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

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
    PipelineVerdict,
)

PromoteFn = Callable[[dict[str, Any]], GateRecommendation]
JoinFn = Callable[[list[StepResult], StepContext], StepResult]


__all__ = [
    "PromoteFn",
    "JoinFn",
    "critique_revise_gate_loop",
    "panel_parallel",
    "alternating_turns",
    "subpipeline_call",
    "mode_prompts",
    "iterate_until",
    "escalate_if",
    "majority_vote",
    "phase_zero_gate",
    # Dynamic primitives (0.23 — pipeline-rationalization sprint, T2).
    "panel_from_artifact",
    "dynamic_fanout",
    "weighted_vote",
    "iterate_until_consensus",
    "paired_round",
]


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
    :data:`GateRecommendation` on the parent's :class:`PipelineVerdict`.

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
      :class:`PipelineVerdict` with the winning recommendation and
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
        verdict = PipelineVerdict(score=1.0, recommendation=chosen)
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


# ── Dynamic primitives (T2, pipeline-rationalization sprint) ─────────────
#
# The four committed-SubloopStep-shaped primitives below encapsulate
# run-time-dynamic dispatch inside a :class:`SubloopStep` (or a subclass
# thereof). The rationale is that :class:`ParallelStage.steps` is a frozen
# tuple materialised at compile time (see ``executor.py:171/179/295/298``),
# so dynamism — fanning out into a panel whose size or composition is only
# known at run time — must live below the stage level. Each subclass adds
# new fields with defaults so the frozen-dataclass-with-defaults
# subclassing rules are respected; each overrides ``run`` to perform the
# dynamic work and returns a single :class:`StepResult` via the supplied
# :data:`JoinFn`. Because the subclasses inherit from :class:`SubloopStep`,
# ``isinstance(x, SubloopStep)`` remains True for callers and the
# pipeline-builder surface unchanged.


def _specialize_step(base: Step, spec: Any) -> Step:
    """Return a per-spec specialised copy of *base*.

    If *base* is a dataclass instance, the dict-like *spec*'s keys are
    intersected with the dataclass's field names and passed to
    :func:`dataclasses.replace`. Unknown keys are dropped (so reviewer
    specs may carry arbitrary metadata without breaking specialisation).
    Steps that are not dataclasses are returned unchanged.
    """

    if not isinstance(spec, Mapping):
        return base
    base_any: Any = base
    if dataclasses.is_dataclass(base_any) and not isinstance(base_any, type):
        valid = {f.name for f in dataclasses.fields(base_any)}
        kwargs = {k: v for k, v in spec.items() if k in valid}
        if kwargs:
            try:
                return cast(Step, dataclasses.replace(base_any, **kwargs))
            except TypeError:
                return base
    return base


def _read_specs_from_path(path: Path) -> list[Any]:
    """Read a JSON list of reviewer specs from *path*."""

    loaded = json.loads(Path(path).read_text())
    if not isinstance(loaded, list):
        raise ValueError(
            f"reviewer-spec artifact {str(path)!r} must be a JSON list, "
            f"got {type(loaded).__name__}"
        )
    return loaded


def _extract_specs_from_result(result: StepResult) -> list[Any]:
    """Pull a list of reviewer specs from a generator's StepResult.

    Resolution order:

    1. ``result.state_patch['specs']`` — direct in-memory list of specs.
    2. ``result.outputs['specs']`` — :class:`Path` to a JSON file
       containing a list.

    Raises :class:`LookupError` if neither slot carries a list.
    """

    sp = result.state_patch
    if isinstance(sp, Mapping):
        val = sp.get("specs")
        if isinstance(val, list):
            return list(val)
    outs = result.outputs
    if isinstance(outs, Mapping):
        out_path = outs.get("specs")
        if out_path is not None:
            return _read_specs_from_path(Path(out_path))
    raise LookupError(
        "dynamic_fanout: generator emitted no 'specs' (neither in "
        "state_patch nor outputs)"
    )


@dataclass(frozen=True)
class _PanelFromArtifactStep(SubloopStep):
    """SubloopStep subclass implementing :func:`panel_from_artifact`."""

    artifact_ref: str = ""
    base_template: Step | None = None
    join_fn: JoinFn | None = None

    def run(self, ctx: StepContext) -> StepResult:
        if self.base_template is None:
            raise ValueError(
                f"panel_from_artifact {self.name!r}: base_template is None"
            )
        if self.join_fn is None:
            raise ValueError(
                f"panel_from_artifact {self.name!r}: join is None"
            )

        path: Path | None = None
        if isinstance(ctx.inputs, Mapping):
            raw = ctx.inputs.get(self.artifact_ref)
            if raw is not None:
                path = Path(raw)
        if path is None and isinstance(ctx.state, Mapping):
            raw = ctx.state.get(self.artifact_ref)
            if raw is not None:
                path = Path(raw)
        if path is None:
            raise LookupError(
                f"panel_from_artifact {self.name!r}: artifact "
                f"{self.artifact_ref!r} not found in ctx.inputs or ctx.state"
            )

        specs = _read_specs_from_path(path)
        steps = [_specialize_step(self.base_template, spec) for spec in specs]
        results = [s.run(ctx) for s in steps]
        return self.join_fn(results, ctx)


@dataclass(frozen=True)
class _DynamicFanoutStep(SubloopStep):
    """SubloopStep subclass implementing :func:`dynamic_fanout`."""

    generator: Step | None = None
    base_prompt: Step | None = None
    join_fn: JoinFn | None = None

    def run(self, ctx: StepContext) -> StepResult:
        if self.generator is None:
            raise ValueError(
                f"dynamic_fanout {self.name!r}: generator is None"
            )
        if self.base_prompt is None:
            raise ValueError(
                f"dynamic_fanout {self.name!r}: base_prompt is None"
            )
        if self.join_fn is None:
            raise ValueError(
                f"dynamic_fanout {self.name!r}: join is None"
            )

        gen_result = self.generator.run(ctx)
        specs = _extract_specs_from_result(gen_result)
        steps = [_specialize_step(self.base_prompt, spec) for spec in specs]
        results = [s.run(ctx) for s in steps]
        return self.join_fn(results, ctx)


def panel_from_artifact(
    artifact_ref: str,
    base_template: Step,
    join: JoinFn,
    *,
    name: str,
) -> SubloopStep:
    """Read N reviewer specs from an upstream JSON artifact and run a
    specialised copy of *base_template* per spec, then collapse via *join*.

    Committed :class:`SubloopStep` shape — :class:`ParallelStage.steps` is
    materialised at compile time (see ``executor.py:171/179/295/298``), so
    dynamic per-reviewer fan-out must be encapsulated inside a
    :class:`SubloopStep` whose ``run`` performs the dispatch at run time.
    """

    return _PanelFromArtifactStep(
        name=name,
        artifact_ref=artifact_ref,
        base_template=base_template,
        join_fn=join,
    )


def dynamic_fanout(
    generator: Step,
    base_prompt: Step,
    join: JoinFn,
    *,
    name: str,
) -> SubloopStep:
    """Run *generator* once, consume its emitted specs, and fan out
    *base_prompt* per spec — then collapse via *join*.

    Committed :class:`SubloopStep` shape — :class:`ParallelStage.steps` is
    materialised at compile time (see ``executor.py:171/179/295/298``), so
    a generator-driven fan-out whose width is only known at run time must
    be encapsulated inside a :class:`SubloopStep` whose ``run`` performs
    the dispatch at run time.
    """

    return _DynamicFanoutStep(
        name=name,
        generator=generator,
        base_prompt=base_prompt,
        join_fn=join,
    )


def weighted_vote(weights: Mapping[str, float]) -> JoinFn:
    """Return a :class:`ParallelStage` ``join`` callable that picks the
    highest-weighted :data:`GateRecommendation` across panel verdicts.

    Each input :class:`StepResult`'s
    ``verdict.payload['reviewer_id']`` is used to look up the reviewer's
    weight in *weights*; missing ids contribute zero. Per-recommendation
    weighted sums are tallied across all panellists; the highest sum
    wins. Ties (or panels whose reviewers produced no verdicts at all)
    resolve to ``'tiebreaker'`` for parity with :func:`majority_vote`.
    The returned :class:`StepResult` carries a synthetic
    :class:`PipelineVerdict` whose ``recommendation`` matches the winning label
    and ``next=<recommendation>`` for label-fallback dispatch.
    """

    weights_map: dict[str, float] = dict(weights)

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        del ctx  # vote is state-agnostic
        tally: dict[GateRecommendation, float] = {}
        any_vote = False
        for r in results:
            if r.verdict is None or r.verdict.recommendation is None:
                continue
            rec = r.verdict.recommendation
            rid: Any = None
            payload = r.verdict.payload
            if isinstance(payload, Mapping):
                rid = payload.get("reviewer_id")
            w = weights_map.get(str(rid), 0.0) if rid is not None else 0.0
            tally[rec] = tally.get(rec, 0.0) + w
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


def _agreement_ratio(result: StepResult) -> float:
    """Compute the agreement ratio for a panel result.

    The host panel is expected to surface per-reviewer recommendations
    in ``result.verdict.payload['per_reviewer_recommendations']`` as a
    list of :data:`GateRecommendation` strings. The ratio is the share
    of the most-common recommendation across that list. If the slot is
    missing or empty, the ratio defaults to ``1.0`` (a single aggregate
    verdict is unanimous by definition).
    """

    if result.verdict is None:
        return 0.0
    payload = result.verdict.payload
    recs: list[Any] = []
    if isinstance(payload, Mapping):
        v = payload.get("per_reviewer_recommendations")
        if isinstance(v, list):
            recs = list(v)
    if not recs:
        return 1.0
    counts = Counter(recs)
    top = counts.most_common(1)[0][1]
    return float(top) / float(len(recs))


@dataclass(frozen=True)
class _ConsensusStep(SubloopStep):
    """SubloopStep subclass implementing :func:`iterate_until_consensus`."""

    panel: Any = None  # Step | Stage
    min_agreement: float = 0.8
    max_iters: int = 3

    def run(self, ctx: StepContext) -> StepResult:
        if self.panel is None:
            raise ValueError(
                f"iterate_until_consensus {self.name!r}: panel is None"
            )

        panel_step: Step
        if isinstance(self.panel, Stage):
            panel_step = self.panel.step
        else:
            panel_step = cast(Step, self.panel)

        last_result: StepResult | None = None
        last_ratio = 0.0
        for i in range(max(1, self.max_iters)):
            result = panel_step.run(ctx)
            last_result = result
            last_ratio = _agreement_ratio(result)
            if last_ratio >= self.min_agreement:
                merged = dict(result.state_patch) if isinstance(result.state_patch, Mapping) else {}
                merged[f"consensus:{self.name}:agreement"] = last_ratio
                merged[f"consensus:{self.name}:iterations"] = i + 1
                return StepResult(
                    outputs=result.outputs,
                    verdict=result.verdict,
                    next="halt",
                    state_patch=merged,
                )

        assert last_result is not None  # max_iters >= 1 guarantees one pass
        merged = dict(last_result.state_patch) if isinstance(last_result.state_patch, Mapping) else {}
        merged[f"consensus:{self.name}:agreement"] = last_ratio
        merged[f"consensus:{self.name}:iterations"] = max(1, self.max_iters)
        return StepResult(
            outputs=last_result.outputs,
            verdict=last_result.verdict,
            next="halt",
            state_patch=merged,
        )


def iterate_until_consensus(
    panel: Step | Stage,
    min_agreement: float = 0.8,
    max_iters: int = 3,
    *,
    name: str,
) -> SubloopStep:
    """Wrap :func:`iterate_until` with an agreement-ratio predicate.

    Returns a :class:`SubloopStep` that repeatedly invokes *panel* (a
    :class:`Step` or :class:`Stage`) up to *max_iters* times, computing
    :func:`_agreement_ratio` on each pass. The loop exits as soon as the
    ratio reaches *min_agreement*; otherwise it falls through after the
    final iteration. The two ``consensus:<name>:{agreement,iterations}``
    keys are emitted as ``state_patch`` so downstream stages can
    inspect the loop's exit conditions.
    """

    return _ConsensusStep(
        name=name,
        panel=panel,
        min_agreement=float(min_agreement),
        max_iters=int(max_iters),
    )


@dataclass(frozen=True)
class _PairedRoundStep:
    """Custom Step backing :func:`paired_round`.

    Runs each advocate in sequence. When *sees_other* is True, each
    advocate's :class:`StepContext.inputs` is augmented with the prior
    turn's :attr:`StepResult.outputs` under ``prior.<label>`` keys so
    role B's run sees role A's argument (and vice versa on the next
    round).
    """

    name: str = "paired_round"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    advocates: tuple[Step, ...] = ()
    sees_other: bool = True

    def run(self, ctx: StepContext) -> StepResult:
        if not self.advocates:
            return StepResult(next="halt")

        prior_outputs: Mapping[str, Path] = {}
        outputs_accum: dict[str, Path] = {}
        last_result: StepResult | None = None

        for adv in self.advocates:
            base_inputs: dict[str, Path] = (
                dict(ctx.inputs) if isinstance(ctx.inputs, Mapping) else {}
            )
            if self.sees_other and prior_outputs:
                for label, path in prior_outputs.items():
                    base_inputs[f"prior.{label}"] = path
            adv_ctx = dataclasses.replace(ctx, inputs=base_inputs)
            result = adv.run(adv_ctx)
            last_result = result
            prior_outputs = dict(result.outputs) if isinstance(result.outputs, Mapping) else {}
            for label, path in prior_outputs.items():
                outputs_accum[f"{adv.name}.{label}"] = path

        assert last_result is not None
        return StepResult(
            outputs=outputs_accum,
            verdict=last_result.verdict,
            next=last_result.next,
            state_patch=last_result.state_patch,
        )


def paired_round(
    advocates: Sequence[Step],
    *,
    sees_other: bool = True,
    name: str,
) -> Stage:
    """Debate-style round where each advocate sees the other's argument.

    Extends :func:`alternating_turns` (linear chain of role Stages) by
    collapsing the chain into a single :class:`Stage` whose Step
    internally runs the advocates in sequence, splicing the prior turn's
    :attr:`StepResult.outputs` into the next advocate's
    :attr:`StepContext.inputs` under ``prior.<label>`` keys when
    *sees_other* is ``True``. Set *sees_other* to ``False`` to recover
    the topology-only semantics of :func:`alternating_turns` without the
    cross-turn artifact injection.
    """

    if not advocates:
        raise ValueError("paired_round: advocates must be non-empty")

    return Stage(
        name=name,
        step=_PairedRoundStep(
            name=name,
            advocates=tuple(advocates),
            sees_other=sees_other,
        ),
        edges=(),
    )
