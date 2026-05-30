"""Fluent :class:`PipelineBuilder` for composing Python pipelines.

Ergonomic sugar over the frozen primitives in
:mod:`megaplan._pipeline.types` plus the pattern library in
:mod:`megaplan._pipeline.patterns`. Designed for terse pipeline
definition::

    pipeline = (
        Pipeline.builder("writing-panel-strict", description="...")
            .input("draft", file=True)
            .panel("panel_review", reviewers=[...], inputs=["draft"])
            .agent("synth", prompt="prompts/synth.md", inputs=["panel_review.*"])
            .agent("revise", prompt="prompts/revise.md", inputs=["draft", "synth"])
            .human_gate(
                "human_decide",
                artifact="revise",
                options=["continue", "stop"],
                edges={"continue": "panel_review", "stop": "done"},
            )
            .build()
    )

Design contracts (load-bearing for downstream tasks):

* The builder injects ``_panel_reviewer_order`` onto downstream
  :class:`AgentStep` instances using the **private** dataclass field —
  the audit recorded in finalize T1.i locked in
  ``_panel_reviewer_order`` (no public-alias rename).
* The frozen :class:`Pipeline` dataclass carries only
  ``stages / entry / overlays`` — no ``metadata`` field. Pipeline-level
  metadata (``description``, ``default_profile``, ``supported_modes``)
  is accepted by :meth:`Pipeline.builder` and stashed on the builder for
  :class:`PipelineRegistry` to surface via ``PipelineRegistry.metadata``
  (Step 8 / T9). The :meth:`build` return value is a plain
  :class:`Pipeline`.
* :meth:`tiebreaker` plugs in the canonical
  :class:`TiebreakerStep` with the LOAD-BEARING edge tuple from T11:
  three ``kind="gate"`` recommendation edges (``iterate`` → critique,
  ``proceed`` → finalize, ``escalate`` → finalize).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

from megaplan._pipeline.patterns import (
    PromoteFn,
    critique_revise_gate_loop,
    escalate_if as _escalate_if,
    iterate_until as _iterate_until,
    mode_prompts as _mode_prompts,
    panel_parallel,
)
from megaplan._pipeline.steps.agent import AgentStep
from megaplan._pipeline.steps.human_gate import HumanDecisionStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.types import (
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


class PipelineBuilder:
    """Chained builder that assembles a :class:`Pipeline`.

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
        self.name: str = name
        self.description: str = description
        self.default_profile: str | None = default_profile
        self.supported_modes: tuple[str, ...] = tuple(supported_modes)

        self._pipeline_dir: Path = pipeline_dir if pipeline_dir is not None else Path()
        self._worker: WorkerFn | None = worker
        self._prompt_registry: PromptRegistryFn | None = prompt_registry
        self._pipeline_version: int = pipeline_version

        self._stages: dict[str, Stage | ParallelStage] = {}
        self._inputs: dict[str, bool] = {}
        self._panel_reviewer_order: dict[str, list[str]] = {}
        self._overlays: list[Overlay] = []
        self._modes_dict: dict[str, Mapping[str, str]] = {}

        self._entry: str | None = None
        self._last_stage: str | None = None
        self._last_emit_label: str | None = None  # None => no auto-link

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
    ) -> "PipelineBuilder":
        from megaplan._pipeline.types import Port, PortRef
        _consumes_t = tuple(
            PortRef(port_name=str(ref), content_type="text/markdown") for ref in inputs
        )
        _produces_t = (Port(name=stage_name, content_type="text/markdown"),)
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
            produces=_produces_t,
            consumes=_consumes_t,
        )
        stage = Stage(name=stage_name, step=cast(Step, step), edges=())
        self._append_stage(stage, emit_label="done")
        return self

    def panel(
        self,
        stage_name: str,
        *,
        reviewers: Sequence[ReviewerSpec],
        inputs: Sequence[str] = (),
        merge: str = "none",
        max_workers: int | None = None,
    ) -> "PipelineBuilder":
        reviewer_pairs: list[tuple[str, Step]] = []
        ids: list[str] = []
        for reviewer_id, prompt_ref in reviewers:
            ids.append(reviewer_id)
            from megaplan._pipeline.types import Port, PortRef
            _r_consumes_t = tuple(
                PortRef(port_name=str(ref), content_type="text/markdown") for ref in inputs
            )
            _r_produces_t = (
                Port(name=f"{stage_name}.{reviewer_id}", content_type="text/markdown"),
            )
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
                produces=_r_produces_t,
                consumes=_r_consumes_t,
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
        )
        self._append_stage(parallel, emit_label="next")
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
    ) -> "PipelineBuilder":
        """Add a gate stage with the four ``kind='gate'`` recommendation
        edges plus any caller-supplied ``extra_edges`` in order. Gate
        stages own their outgoing edges — no auto-link to subsequent
        stages."""
        gate_edges: tuple[Edge, ...] = (
            Edge(label="iterate", target=on_iterate, kind="gate", recommendation="iterate"),
            Edge(label="proceed", target=on_proceed, kind="gate", recommendation="proceed"),
            Edge(label="tiebreaker", target=on_tiebreaker, kind="gate", recommendation="tiebreaker"),
            Edge(label="escalate", target=on_escalate, kind="gate", recommendation="escalate"),
        ) + tuple(extra_edges)
        stage = Stage(name=stage_name, step=step, edges=gate_edges)
        self._append_stage(stage, emit_label=None)
        return self

    def human_gate(
        self,
        stage_name: str,
        *,
        artifact: str,
        options: Sequence[str],
        edges: Mapping[str, str],
    ) -> "PipelineBuilder":
        """Add a human-pause gate. ``artifact`` names the stage whose
        latest versioned output the human reviews; ``options`` are the
        choice labels; ``edges`` maps each option to a target stage.

        Constructs a :class:`HumanDecisionStep` with the existing private
        fields (``_choices`` / ``_artifact_stage`` / ``_pipeline_name``
        / ``_pipeline_version`` / ``_resume_choice``) and the enclosing
        :class:`Stage` with one outgoing :class:`Edge` per option."""
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
        )
        stage_edges: tuple[Edge, ...] = tuple(
            Edge(label=option, target=edges[option]) for option in options
        )
        stage = Stage(name=stage_name, step=cast(Step, step), edges=stage_edges)
        self._append_stage(stage, emit_label=None)
        return self

    def subpipeline(
        self,
        name: str,
        *,
        child: Pipeline,
        promote: PromoteFn,
        when: Callable[[Mapping[str, Any]], bool] | None = None,
        artifact_subdir: str | None = None,
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
        stage = Stage(name=name, step=cast(Step, step), edges=())
        # SubloopStep emits next=<recommendation>; default promote yields
        # "proceed", so use that as the natural emit label for auto-link.
        self._append_stage(stage, emit_label="proceed")
        return self

    def tiebreaker(
        self,
        name: str = "tiebreaker",
        *,
        on_iterate: str = "critique",
        on_proceed: str = "finalize",
        on_escalate: str = "finalize",
    ) -> "PipelineBuilder":
        """Plug in the canonical :class:`TiebreakerStep` with the
        LOAD-BEARING gate-kind edge tuple from T11. The legacy
        label-only edges are gone — this is a deliberate behaviour
        delta documented in the 0.22.0 changelog."""
        # Imported lazily to avoid a hard handlers-package dependency at
        # builder import time.
        from megaplan._pipeline.stages.tiebreaker import TiebreakerStep

        step = TiebreakerStep(name=name)
        tb_edges: tuple[Edge, ...] = (
            Edge(label="", target=on_iterate, kind="gate", recommendation="iterate"),
            Edge(label="", target=on_proceed, kind="gate", recommendation="proceed"),
            Edge(label="", target=on_escalate, kind="gate", recommendation="escalate"),
        )
        stage = Stage(name=name, step=cast(Step, step), edges=tb_edges)
        self._append_stage(stage, emit_label=None)
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
        ``kind='gate'`` escalate edge to the most-recently-added
        stage."""
        if self._last_stage is None:
            raise ValueError(".escalate() requires a previously added stage")
        prev = self._stages[self._last_stage]

        escalation_step, escape_edge = _escalate_if(condition, handler)
        new_edges = prev.edges + (escape_edge,)
        if isinstance(prev, ParallelStage):
            self._stages[self._last_stage] = ParallelStage(
                name=prev.name,
                steps=prev.steps,
                join=prev.join,
                edges=new_edges,
                max_workers=prev.max_workers,
            )
        else:
            self._stages[self._last_stage] = Stage(
                name=prev.name, step=prev.step, edges=new_edges
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

    # ── build ───────────────────────────────────────────────────────

    def build(self) -> Pipeline:
        if self._entry is None:
            raise ValueError(
                f"PipelineBuilder({self.name!r}).build(): no stages added"
            )
        return Pipeline(
            stages=dict(self._stages),
            entry=self._entry,
            overlays=tuple(self._overlays),
        )

    # ── internals ───────────────────────────────────────────────────

    def _append_stage(
        self,
        stage: Stage | ParallelStage,
        *,
        emit_label: str | None,
    ) -> None:
        """Add *stage* to the graph; auto-link from the previous stage
        if it advertised an ``emit_label``."""
        if (
            self._last_stage is not None
            and self._last_emit_label is not None
            and self._last_stage in self._stages
        ):
            prev = self._stages[self._last_stage]
            new_edge = Edge(label=self._last_emit_label, target=stage.name)
            if not any(
                e.label == new_edge.label and e.target == new_edge.target
                for e in prev.edges
            ):
                if isinstance(prev, ParallelStage):
                    self._stages[self._last_stage] = ParallelStage(
                        name=prev.name,
                        steps=prev.steps,
                        join=prev.join,
                        edges=prev.edges + (new_edge,),
                        max_workers=prev.max_workers,
                    )
                else:
                    self._stages[self._last_stage] = Stage(
                        name=prev.name,
                        step=prev.step,
                        edges=prev.edges + (new_edge,),
                    )

        self._stages[stage.name] = stage
        if self._entry is None:
            self._entry = stage.name
        self._last_stage = stage.name
        self._last_emit_label = emit_label


__all__ = ["PipelineBuilder"]
