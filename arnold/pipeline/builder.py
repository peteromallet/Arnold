"""Neutral directed-graph builder for :class:`Pipeline` construction.

This module provides a policy-free :class:`PipelineBuilder` that assembles
:class:`Stage` and :class:`ParallelStage` objects into a :class:`Pipeline`.
Megaplan-specific conveniences (``.agent()``, ``.gate()``, ``.tiebreaker()``,
``.human_gate()``) are deliberately excluded — they live in the Megaplan
subclass at :mod:`megaplan._pipeline.builder`.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from arnold.pipeline.types import Edge, ParallelStage, Pipeline, Stage


class PipelineBuilder:
    """Policy-free builder that assembles a :class:`Pipeline` from stages and edges.

    Linking semantics: successive calls to :meth:`add_stage` /
    :meth:`add_parallel_stage` auto-link via the ``emit_label`` parameter.
    When ``emit_label`` is provided, an edge is created from the previously
    added stage to the new one using that label.

    Callers that want explicit edge wiring can use
    :meth:`add_caller_supplied_edges` to inject arbitrary edges after stages
    are registered.

    Resource bundles (prompt directories, model configs) are attached via
    :meth:`attach_resource_bundles` and surfaced through
    :attr:`resource_bundles` for downstream resolution.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name: str = name
        self.description: str = description

        self._stages: dict[str, Stage | ParallelStage] = {}
        self._entry: str | None = None
        self._last_stage: str | None = None
        self._last_emit_label: str | None = None
        self.resource_bundles: list[Any] = []

    # ── stage registration ────────────────────────────────────────────

    def add_stage(
        self,
        stage: Stage,
        *,
        emit_label: str | None = None,
    ) -> "PipelineBuilder":
        """Register a single-Step *stage*.

        If *emit_label* is provided and a previous stage was registered
        with a non-None emit_label, an auto-link :class:`Edge` is created
        from the previous stage to *stage*.
        """
        self._auto_link(stage.name)
        self._stages[stage.name] = stage
        self._set_entry_and_last(stage.name, emit_label)
        return self

    def add_parallel_stage(
        self,
        stage: ParallelStage,
        *,
        emit_label: str | None = None,
    ) -> "PipelineBuilder":
        """Register a fan-out *stage* with auto-link support.

        Behaves identically to :meth:`add_stage` but accepts a
        :class:`ParallelStage`.
        """
        self._auto_link(stage.name)
        self._stages[stage.name] = stage
        self._set_entry_and_last(stage.name, emit_label)
        return self

    # ── explicit edges ────────────────────────────────────────────────

    def add_caller_supplied_edges(
        self,
        edges: Mapping[str, Sequence[str]],
    ) -> "PipelineBuilder":
        """Inject caller-supplied edges into already-registered stages.

        *edges* is a mapping of ``stage_name → [target_name, ...]``.
        Each edge is created with the label equal to the target name
        (the caller can refine labels by constructing :class:`Edge`
        objects directly and using :meth:`add_stage` with pre-built edges).
        """
        for src_name, targets in edges.items():
            if src_name not in self._stages:
                continue
            stage = self._stages[src_name]
            new_edges = tuple(
                Edge(label=tgt, target=tgt)
                for tgt in targets
            )
            if isinstance(stage, ParallelStage):
                self._stages[src_name] = ParallelStage(
                    name=stage.name,
                    steps=stage.steps,
                    join=stage.join,
                    edges=stage.edges + new_edges,
                    max_workers=stage.max_workers,
                )
            else:
                self._stages[src_name] = Stage(
                    name=stage.name,
                    step=stage.step,
                    edges=stage.edges + new_edges,
                )
        return self

    # ── resource bundles ──────────────────────────────────────────────

    def attach_resource_bundles(self, bundles: Sequence[Any]) -> "PipelineBuilder":
        """Attach opaque resource bundles available to steps at runtime.

        *bundles* is a sequence of arbitrary objects (typically
        :class:`PipelineResourceBundle` instances) that the consuming
        runtime resolves when constructing :class:`StepContext`.
        """
        self.resource_bundles.extend(bundles)
        return self

    # ── build ─────────────────────────────────────────────────────────

    def build(self) -> Pipeline:
        """Assemble and return the frozen :class:`Pipeline`.

        Raises :class:`ValueError` if no stages have been added.
        """
        if self._entry is None:
            raise ValueError(
                f"PipelineBuilder({self.name!r}).build(): no stages added"
            )
        return Pipeline(
            stages=dict(self._stages),
            entry=self._entry,
        )

    # ── internals ─────────────────────────────────────────────────────

    def _auto_link(self, new_stage_name: str) -> None:
        """Create an auto-link edge from the previously added stage."""
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

    def _set_entry_and_last(
        self, stage_name: str, emit_label: str | None
    ) -> None:
        """Update entry point and last-stage tracking."""
        if self._entry is None:
            self._entry = stage_name
        self._last_stage = stage_name
        self._last_emit_label = emit_label


__all__ = ["PipelineBuilder"]
