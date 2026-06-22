"""Fluent :class:`PipelineBuilder` for composing Megaplan pipelines.

Extends the neutral :class:`arnold.pipeline.builder.PipelineBuilder` with
Megaplan-specific step classes (AgentStep, PanelReviewerStep,
HumanDecisionStep, SubloopStep, TiebreakerStep), gate/tiebreaker/human_gate
conveniences, and pattern helpers (iterate, escalate, mode).

M3a: Graph-building mechanics (add_stage, add_parallel_stage,
add_caller_supplied_edges, attach_resource_bundles, build) are inherited
from the neutral Arnold base. This subclass adds Megaplan policy defaults
and step constructors.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.builder import PipelineBuilder as _BasePipelineBuilder
from arnold.pipeline.step_invocation import StepInvocation

from arnold_pipelines.megaplan._pipeline.patterns import (
    PromoteFn,
    critique_revise_gate_loop,
    escalate_if as _escalate_if,
    iterate_until as _iterate_until,
    mode_prompts as _mode_prompts,
    panel_parallel,
)
from arnold_pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold_pipelines.megaplan._pipeline.steps.human_gate import HumanDecisionStep
from arnold_pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold_pipelines.megaplan._pipeline.subloop import SubloopStep
from arnold_pipelines.megaplan._pipeline.types import (
    Edge,
    Overlay,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
)

WorkerFn = Callable[..., str]
PromptRegistryFn = Callable[[str], str]
ReviewerSpec = tuple[str, str]  # (reviewer_id, prompt_ref)
ReadDecl = Any
WriteDecl = Any


def _legacy_model_invocation(
    *,
    prompt_ref: str,
    input_refs: Sequence[str],
    prompt_key: str | None = None,
) -> StepInvocation:
    """Derive the legacy authored model invocation shape when unambiguous."""
    metadata: dict[str, Any] = {"prompt": prompt_ref}
    if input_refs:
        metadata["input_refs"] = list(input_refs)
    if prompt_key is not None:
        metadata["prompt_key"] = prompt_key
    return StepInvocation(kind="model", metadata=metadata)


class PipelineBuilder(_BasePipelineBuilder):
    """Chained builder that assembles a Megaplan :class:`Pipeline`.

    Inherits neutral graph-building from
    :class:`arnold.pipeline.builder.PipelineBuilder` and layers on
    Megaplan-specific step constructors and conveniences.

    Linking semantics: each ``.agent`` / ``.panel`` / ``.subpipeline``
    call appends a transition edge from the previously added stage to
    the new one using that previous stage's natural ``StepResult.next``
    label (``"done"`` for :class:`AgentStep`, ``"next"`` for
    :func:`panel_parallel`'s ParallelStage join, ``"proceed"`` for the
    default SubloopStep recommendation). ``.gate`` / ``.human_gate`` /
    ``.tiebreaker`` stages own their outgoing edges explicitly and do
    NOT auto-link to a subsequent stage — the caller wires those edges
    via the method's own ``edges`` / ``extra_edges`` argument or
    bypasses the auto-link by leaving them terminal.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        *,
        default_profile: str | None = None,
        supported_modes: tuple[str, ...] = (),
        pipeline_dir: Path | None = None,
        worker: WorkerFn | None = None,
        prompt_registry: PromptRegistryFn | None = None,
        pipeline_version: int = 1,
    ) -> None:
        super().__init__(name, description)
        self.default_profile: str | None = default_profile
        self.supported_modes: tuple[str, ...] = tuple(supported_modes)

        self._pipeline_dir: Path = pipeline_dir if pipeline_dir is not None else Path()
        self._worker: WorkerFn | None = worker
        self._prompt_registry: PromptRegistryFn | None = prompt_registry
        self._pipeline_version: int = pipeline_version

        self._inputs: dict[str, bool] = {}
        self._panel_reviewer_order: dict[str, list[str]] = {}
        self._overlays: list[Overlay] = []
        self._modes_dict: dict[str, Mapping[str, str]] = {}

    # ── declarative kwargs ──────────────────────────────────────────

    def input(self, name: str, *, file: bool = False) -> "PipelineBuilder":
        """Declare a named input. ``file=True`` marks it as a path-input
        the caller will pass via :attr:`StepContext.inputs`."""
        self._inputs[name] = file
        return self

    # ── Step-producing methods ──────────────────────────────────────

    def agent(
        self,
        stage_name: str,
        *,
        prompt: str,
        inputs: Sequence[str] = (),
        prompt_key: str | None = None,
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
    ) -> "PipelineBuilder":
        stage_invocation = invocation or _legacy_model_invocation(
            prompt_ref=prompt,
            input_refs=inputs,
            prompt_key=prompt_key,
        )
        step = AgentStep(
            name=stage_name,
            kind="produce",
            prompt_key=prompt_key,
            slot=None,
            _prompt_ref=prompt,
            _pipeline_dir=self._pipeline_dir,
            _pipeline_name=self.name,
            _input_refs=list(inputs),
            _produces="markdown",
            _worker=self._worker,
            _prompt_registry=self._prompt_registry,
            _panel_reviewer_order={k: list(v) for k, v in self._panel_reviewer_order.items()},
            _mode="",
            _invocation=stage_invocation,
            _invocation_explicit=invocation is not None,
        )
        stage = Stage(
            name=stage_name,
            step=cast(Step, step),
            edges=(),
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=stage_invocation,
            required_capabilities=tuple(required_capabilities),
        )
        self.add_stage(stage, emit_label="done")
        return self

    def panel(
        self,
        stage_name: str,
        *,
        reviewers: Sequence[ReviewerSpec],
        inputs: Sequence[str] = (),
        merge: str = "none",
        max_workers: int | None = None,
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
    ) -> "PipelineBuilder":
        reviewer_pairs: list[tuple[str, Step]] = []
        ids: list[str] = []
        for reviewer_id, prompt_ref in reviewers:
            ids.append(reviewer_id)
            rstep = PanelReviewerStep(
                name=f"{stage_name}.{reviewer_id}",
                kind="produce",
                prompt_key=None,
                slot=None,
                _prompt_ref=prompt_ref,
                _pipeline_dir=self._pipeline_dir,
                _pipeline_name=self.name,
                _input_refs=list(inputs),
                _reviewer_id=reviewer_id,
                _worker=self._worker,
                _prompt_registry=self._prompt_registry,
                _panel_reviewer_order={
                    k: list(v) for k, v in self._panel_reviewer_order.items()
                },
                _mode="",
            )
            reviewer_pairs.append((reviewer_id, cast(Step, rstep)))

        # Plumb panel reviewer order so downstream .agent calls
        # referencing this panel can expand `<panel>.*` in reviewer-list
        # order via step_helpers.resolve_inputs.
        self._panel_reviewer_order[stage_name] = ids

        parallel = panel_parallel(
            stage_name,
            tuple(reviewer_pairs),
            edges=(),
            merge_strategy=merge,
            max_workers=max_workers,
            next_label="next",
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=invocation,
            required_capabilities=tuple(required_capabilities),
        )
        self.add_parallel_stage(parallel, emit_label="next")
        return self

    def gate(
        self,
        stage_name: str,
        *,
        step: Step,
        on_proceed: str,
        on_iterate: str,
        on_tiebreaker: str,
        on_escalate: str,
        extra_edges: tuple[Edge, ...] = (),
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
    ) -> "PipelineBuilder":
        """Add a gate stage with the four ``kind='decision'``
        edges plus any caller-supplied ``extra_edges`` in order. Gate
        stages own their outgoing edges — no auto-link to subsequent
        stages.

        Delegates to :func:`~megaplan.pipelines.planning.routing.planning_gate_edges`
        so edge construction stays in one place."""
        from arnold_pipelines.megaplan.routing import planning_gate_edges

        gate_edges = planning_gate_edges(
            on_proceed=on_proceed,
            on_iterate=on_iterate,
            on_tiebreaker=on_tiebreaker,
            on_escalate=on_escalate,
            gate_extra_edges=extra_edges,
        )
        stage = Stage(
            name=stage_name,
            step=step,
            edges=gate_edges,
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=invocation,
            required_capabilities=tuple(required_capabilities),
        )
        self.add_stage(stage, emit_label=None)
        return self

    def human_gate(
        self,
        stage_name: str,
        *,
        artifact: str,
        options: Sequence[str],
        edges: Mapping[str, str],
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
        port: str | None = None,
        content_type: str | None = None,
        artifact_ref: dict | None = None,
        invalid_policy: str = "resuspend",
    ) -> "PipelineBuilder":
        """Add a human-pause gate. ``artifact`` names the stage whose
        latest versioned output the human reviews; ``options`` are the
        choice labels; ``edges`` maps each option to a target stage.

        Constructs a :class:`HumanDecisionStep` with the existing private
        fields (``_choices`` / ``_artifact_stage`` / ``_pipeline_name``
        / ``_pipeline_version`` / ``_resume_choice``) and the enclosing
        :class:`Stage` with one outgoing :class:`Edge` per option.

        When *port* / *content_type* / *artifact_ref* are supplied the
        builder configures the step to embed an ``x-arnold-resume``
        declaration in the checkpoint's ``resume_input_schema`` so the
        consumer can re-verify the artifact on resume.  *invalid_policy*
        controls what happens when re-verification fails (default
        ``"resuspend"``).
        """
        step = HumanDecisionStep(
            name=stage_name,
            kind="decide",
            prompt_key=None,
            slot=None,
            _artifact_stage=artifact,
            _choices=list(options),
            _pipeline_name=self.name,
            _pipeline_version=self._pipeline_version,
            _resume_choice=None,
            _port=port,
            _content_type=content_type,
            _artifact_ref=artifact_ref,
            _invalid_policy=invalid_policy,
        )
        stage_edges: tuple[Edge, ...] = tuple(
            Edge(label=option, target=edges[option]) for option in options
        )
        stage = Stage(
            name=stage_name,
            step=cast(Step, step),
            edges=stage_edges,
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=invocation,
            required_capabilities=tuple(required_capabilities),
        )
        self.add_stage(stage, emit_label=None)
        return self

    def subpipeline(
        self,
        name: str,
        *,
        child: Pipeline,
        promote: PromoteFn,
        when: Callable[[Mapping[str, Any]], bool] | None = None,
        artifact_subdir: str | None = None,
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
    ) -> "PipelineBuilder":
        """Add a :class:`SubloopStep` running *child* as a nested
        pipeline. *when* is documentation-only (consumed by an upstream
        gate stage that decides whether to dispatch here)."""
        del when  # documentation parameter
        step = SubloopStep(
            name=name,
            child_pipeline=child,
            promote=promote,
            artifact_subdir=artifact_subdir,
        )
        stage = Stage(
            name=name,
            step=cast(Step, step),
            edges=(),
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=invocation,
            required_capabilities=tuple(required_capabilities),
        )
        # SubloopStep emits next=<recommendation>; default promote yields
        # "proceed", so use that as the natural emit label for auto-link.
        self.add_stage(stage, emit_label="proceed")
        return self

    def tiebreaker(
        self,
        name: str = "tiebreaker",
        *,
        on_iterate: str = "critique",
        on_proceed: str = "finalize",
        on_escalate: str = "finalize",
        reads: Sequence[ReadDecl] = (),
        writes: Sequence[WriteDecl] = (),
        invocation: StepInvocation | None = None,
        required_capabilities: Sequence[str] = (),
    ) -> "PipelineBuilder":
        """Plug in the canonical :class:`TiebreakerStep` with the
        LOAD-BEARING decision-kind edge tuple from T11. The legacy
        label-only edges are gone — this is a deliberate behaviour
        delta documented in the 0.22.0 changelog.

        Delegates to :func:`~megaplan.pipelines.planning.routing.tiebreaker_edges`
        so edge construction stays in one place."""
        # Imported lazily to avoid a hard handlers-package dependency at
        # builder import time.
        from arnold_pipelines.megaplan.stages.tiebreaker import TiebreakerStep
        from arnold_pipelines.megaplan.routing import tiebreaker_edges

        step = TiebreakerStep(name=name)
        tb_edges = tiebreaker_edges(
            on_iterate=on_iterate,
            on_proceed=on_proceed,
            on_escalate=on_escalate,
        )
        stage = Stage(
            name=name,
            step=cast(Step, step),
            edges=tb_edges,
            reads=tuple(reads),
            writes=tuple(writes),
            invocation=invocation,
            required_capabilities=tuple(required_capabilities),
        )
        self.add_stage(stage, emit_label=None)
        return self

    # ── pattern conveniences ────────────────────────────────────────

    def iterate(
        self,
        *,
        condition: Callable[[Mapping[str, Any]], bool],
        max_iterations: int = 10,
        iterate_label: str = "iterate",
        halt_label: str = "halt",
    ) -> "PipelineBuilder":
        """Wrap the most-recently-added :class:`Stage` with a self-loop
        + halt edge via :func:`patterns.iterate_until`."""
        if self._last_stage is None:
            raise ValueError(".iterate() requires a previously added stage")
        prev = self._stages[self._last_stage]
        if not isinstance(prev, Stage):
            raise TypeError(
                f".iterate() targets Stage, not {type(prev).__name__} "
                f"({self._last_stage!r})"
            )
        self._stages[self._last_stage] = _iterate_until(
            prev,
            condition=condition,
            max_iterations=max_iterations,
            iterate_label=iterate_label,
            halt_label=halt_label,
        )
        return self

    def escalate(
        self,
        *,
        condition: Callable[[Mapping[str, Any]], bool],
        handler: Step,
    ) -> "PipelineBuilder":
        """Append the *handler* as a standalone stage and add the
        ``kind='decision'`` escalate edge to the most-recently-added
        stage."""
        if self._last_stage is None:
            raise ValueError(".escalate() requires a previously added stage")
        prev = self._stages[self._last_stage]

        escalation_step, escape_edge = _escalate_if(condition, handler)
        self._stages[self._last_stage] = replace(
            prev,
            edges=prev.edges + (escape_edge,),
        )

        # Register the escalation handler as a terminal Stage on the
        # graph; the caller is responsible for further routing.
        self._stages[escalation_step.name] = Stage(
            name=escalation_step.name, step=escalation_step, edges=()
        )
        return self

    def mode(
        self, modes_dict: Mapping[str, Mapping[str, str]]
    ) -> "PipelineBuilder":
        """Stash *modes_dict* for runtime mode-overlay application.

        Per-mode prompt swapping is applied at run time once the active
        mode is known (the executor receives it via
        :attr:`StepContext.mode`); callers can materialise the overlay
        via ``patterns.mode_prompts(builder._modes_dict)(active_mode)``.
        The stashed dict is also exposed for introspection by the
        registry / describe surface."""
        self._modes_dict = {k: dict(v) for k, v in modes_dict.items()}
        return self

    def overlay(self, overlay: Overlay) -> "PipelineBuilder":
        """Append an :class:`Overlay` to the pipeline's overlay tuple."""
        self._overlays.append(overlay)
        return self

    # ── build (override — returns Megaplan Pipeline with overlays) ───

    def build(self) -> Pipeline:
        """Assemble and return the frozen Megaplan :class:`Pipeline`."""
        if self._entry is None:
            raise ValueError(
                f"PipelineBuilder({self.name!r}).build(): no stages added"
            )
        edges = [
            (src_name, edge.target)
            for src_name, stage in self._stages.items()
            for edge in getattr(stage, "edges", ())
            if edge.target != "halt"
        ]
        return Pipeline(
            stages=dict(self._stages),
            entry=self._entry,
            overlays=tuple(self._overlays),
            binding_map=derive_binding_map(dict(self._stages), edges),
        )

    # ── internals (override — uses Megaplan Edge/Stage types) ─────────

    def _auto_link(self, new_stage_name: str) -> None:
        """Create an auto-link edge using Megaplan :class:`Edge`."""
        if (
            self._last_stage is not None
            and self._last_emit_label is not None
            and self._last_stage in self._stages
        ):
            prev = self._stages[self._last_stage]
            new_edge = Edge(label=self._last_emit_label, target=new_stage_name)
            if not any(
                e.label == new_edge.label and e.target == new_edge.target
                for e in prev.edges
            ):
                self._stages[self._last_stage] = replace(
                    prev,
                    edges=prev.edges + (new_edge,),
                )


__all__ = ["PipelineBuilder"]
