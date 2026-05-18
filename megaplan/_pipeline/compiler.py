"""YAML-to-runtime compiler: convert PipelineSpec into Pipeline dataclasses.

This module is the bridge between the YAML schema (``schema.py``) and the
runtime primitives (``types.py``).  It produces a :class:`Pipeline` whose
:class:`Stage` / :class:`ParallelStage` nodes carry :class:`Step`
implementations that the executor can dispatch.

Design decisions (locked):
* ``_pipeline`` is injected from ``PipelineSpec.name`` (not directory slug).
* Panel output ordering follows YAML reviewer-list order.
* ``done`` in edges maps to the ``halt`` sentinel.
* Human-gate edges carry the choice label as a normal edge label.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from megaplan._pipeline.schema import (
    AgentStepSpec,
    EdgeSpec,
    GateStepSpec,
    HumanGateStepSpec,
    PanelStepSpec,
    PipelineSpec,
)
from megaplan._pipeline.steps.agent import (
    AgentStep,
    WorkerFn,
    _interpolate_inputs,
    _next_version,
    _resolve_inputs,
    _resolve_prompt_text,
)
from megaplan._pipeline.steps.gate import GateStep
from megaplan._pipeline.steps.human_gate import HumanGateStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)


# ── Compiler ──────────────────────────────────────────────────────────


def compile_pipeline(
    spec: PipelineSpec,
    *,
    pipeline_dir: Path,
    worker: WorkerFn | None = None,
    prompt_registry: Callable[[str], str] | None = None,
    resume_choice: str | None = None,
    mode: str = "",
) -> Pipeline:
    """Compile a :class:`PipelineSpec` into a :class:`Pipeline`.

    Parameters
    ----------
    spec:
        The validated YAML pipeline specification.
    pipeline_dir:
        The directory containing ``pipeline.yaml`` (for resolving .md prompts).
    worker:
        An optional callable for model invocation.  When ``None``, steps
        produce placeholder output (useful for testing).
    prompt_registry:
        An optional callable that resolves PromptRegistry keys to prompt text.
    resume_choice:
        If set, the human_gate step will return this choice instead of pausing.
    mode:
        The pipeline mode (e.g. "polish", "restructure").
    """
    stages: dict[str, Stage | ParallelStage] = {}
    entry: str | None = None

    # Build panel_reviewer_order map for input resolution
    panel_reviewer_order: dict[str, list[str]] = {}
    for stage_spec in spec.stages:
        if isinstance(stage_spec, PanelStepSpec):
            panel_reviewer_order[stage_spec.id] = [
                r.id for r in stage_spec.reviewers
            ]

    for stage_spec in spec.stages:
        if entry is None:
            entry = stage_spec.id

        edges = _compile_edges(stage_spec.id, spec.edges)

        if isinstance(stage_spec, AgentStepSpec):
            step = AgentStep(
                name=stage_spec.id,
                kind="produce",
                prompt_key=stage_spec.prompt,
                slot=stage_spec.id,
                _prompt_ref=stage_spec.prompt,
                _pipeline_dir=pipeline_dir,
                _pipeline_name=spec.name,
                _input_refs=list(stage_spec.inputs),
                _produces=stage_spec.produces or "markdown",
                _worker=worker,
                _prompt_registry=prompt_registry,
                _panel_reviewer_order=panel_reviewer_order,
                _mode=mode,
            )
            stages[stage_spec.id] = Stage(
                name=stage_spec.id,
                step=step,
                edges=edges,
            )

        elif isinstance(stage_spec, PanelStepSpec):
            reviewer_steps: list[Step] = []
            for reviewer in stage_spec.reviewers:
                rstep = PanelReviewerStep(
                    name=f"{stage_spec.id}.{reviewer.id}",
                    kind="produce",
                    prompt_key=reviewer.prompt,
                    slot=f"{stage_spec.id}.{reviewer.id}",
                    _prompt_ref=reviewer.prompt,
                    _pipeline_dir=pipeline_dir,
                    _pipeline_name=spec.name,
                    _input_refs=list(stage_spec.inputs),
                    _reviewer_id=reviewer.id,
                    _worker=worker,
                    _prompt_registry=prompt_registry,
                    _panel_reviewer_order=panel_reviewer_order,
                    _mode=mode,
                )
                reviewer_steps.append(rstep)

            # Merge=none: join returns the first result (passthrough).
            # The synth stage downstream uses panel_review.* to collect all.
            def _make_join(panel_id: str):
                def _join(
                    results: list[StepResult], ctx: StepContext
                ) -> StepResult:
                    # Collect all reviewer outputs into a merged output map
                    merged_outputs: dict[str, Path] = {}
                    for r in results:
                        merged_outputs.update(dict(r.outputs))
                    return StepResult(
                        outputs=merged_outputs,
                        next="done",
                    )

                return _join

            stages[stage_spec.id] = ParallelStage(
                name=stage_spec.id,
                steps=tuple(reviewer_steps),
                join=_make_join(stage_spec.id),
                edges=edges,
                max_workers=len(reviewer_steps),
            )

        elif isinstance(stage_spec, HumanGateStepSpec):
            step = HumanGateStep(
                name=stage_spec.id,
                kind="decide",
                prompt_key=None,
                slot=stage_spec.id,
                _artifact_stage=stage_spec.artifact,
                _choices=list(stage_spec.choices),
                _pipeline_name=spec.name,
                _pipeline_version=spec.version,
                _resume_choice=resume_choice,
            )
            stages[stage_spec.id] = Stage(
                name=stage_spec.id,
                step=step,
                edges=edges,
            )

        elif isinstance(stage_spec, GateStepSpec):
            step = GateStep(
                name=stage_spec.id,
                kind="judge",
                prompt_key=stage_spec.prompt,
                slot=stage_spec.id,
                _prompt_ref=stage_spec.prompt,
                _pipeline_dir=pipeline_dir,
                _pipeline_name=spec.name,
                _input_refs=list(stage_spec.inputs),
                _worker=worker,
                _prompt_registry=prompt_registry,
                _panel_reviewer_order=panel_reviewer_order,
                _mode=mode,
            )
            stages[stage_spec.id] = Stage(
                name=stage_spec.id,
                step=step,
                edges=edges,
            )

    if entry is None:
        raise ValueError("Pipeline has no stages")

    # Add implicit linear edges between consecutive stages that have no
    # explicit edges declared in the YAML.  Implicit edges use the ``done``
    # label — each step returns ``next="done"`` by default.
    stage_ids = [s.id for s in spec.stages]
    for i, stage_id in enumerate(stage_ids):
        node = stages[stage_id]
        if node.edges:
            continue  # Has explicit edges — don't add implicit ones
        if i + 1 < len(stage_ids):
            # Not the last stage: add implicit done → next_stage
            implicit_edge = Edge(label="done", target=stage_ids[i + 1], kind="normal")
        else:
            # Last stage: add implicit done → halt (terminal)
            implicit_edge = Edge(label="done", target="halt", kind="normal")
        # Replace the Stage/ParallelStage with updated edges
        if isinstance(node, Stage):
            stages[stage_id] = Stage(
                name=node.name, step=node.step, edges=(implicit_edge,)
            )
        else:
            stages[stage_id] = ParallelStage(
                name=node.name, steps=node.steps, join=node.join,
                edges=(implicit_edge,), max_workers=node.max_workers,
            )

    return Pipeline(stages=stages, entry=entry)


def _compile_edges(
    stage_id: str,
    edge_specs: list[EdgeSpec],
) -> tuple[Edge, ...]:
    """Compile YAML edges for a given source stage into :class:`Edge` objects.

    * ``to: done`` → ``target="halt"`` sentinel.
    * Human-gate edges: ``kind="normal"`` with the choice as label.
    * Gate edges: ``kind="gate"`` with ``when`` as the recommendation.
    """
    edges: list[Edge] = []
    for es in edge_specs:
        if es.from_ != stage_id:
            continue
        target = "halt" if es.to == "done" else es.to
        label = es.when

        # Determine edge kind from the stage type
        # Human-gate: normal edges with choice labels
        # Gate: gate edges with recommendation labels
        edges.append(
            Edge(
                label=label,
                target=target,
                kind="normal",
            )
        )
    return tuple(edges)


def inject_pipeline_context(
    ctx: StepContext,
    pipeline_name: str,
) -> StepContext:
    """Return a new StepContext with ``_pipeline`` injected into inputs.

    This is the YAML-specific path — it does NOT mutate ``run_pipeline_by_name``
    or the registered-pipeline registry path.
    """
    new_inputs = dict(ctx.inputs)
    new_inputs["_pipeline"] = Path(pipeline_name)  # sentinel value
    return replace(ctx, inputs=new_inputs)
