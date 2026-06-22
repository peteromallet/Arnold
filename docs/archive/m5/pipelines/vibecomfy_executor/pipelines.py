"""VibeComfy executor pipeline construction.

The graph is assembled with the neutral :class:`~arnold.pipeline.builder.PipelineBuilder`
and typed :class:`Port` / :class:`PortRef` declarations.  Because the current
``arnold run`` CLI still executes non-bridged pipelines through the legacy
Megaplan executor, the neutral graph is converted to Megaplan ``Pipeline`` /
``Stage`` instances before being returned from ``build_pipeline``.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import (
    Pipeline as NeutralPipeline,
    Port,
    PortRef,
    Stage as NeutralStage,
)
from arnold.pipelines.megaplan._pipeline.types import (
    Pipeline as MpPipeline,
    Stage as MpStage,
    Edge as MpEdge,
)

from arnold.pipelines.vibecomfy_executor.steps import (
    ClassifyStep,
    ImplementStep,
    ReplyStep,
    ResearchStep,
)


def _to_megaplan_pipeline(neutral_pipeline: NeutralPipeline) -> MpPipeline:
    """Convert a neutral PipelineBuilder result into a Megaplan executor graph."""
    mp_stages: dict[str, MpStage] = {}
    for name, stage in neutral_pipeline.stages.items():
        if isinstance(stage, NeutralStage):
            mp_stages[name] = MpStage(
                name=stage.name,
                step=stage.step,
                edges=tuple(
                    MpEdge(
                        label=edge.label,
                        target=edge.target,
                        kind=edge.kind,
                        recommendation=edge.recommendation,
                    )
                    for edge in stage.edges
                ),
                reads=stage.reads,
                writes=stage.writes,
                produces=stage.produces,
                consumes=stage.consumes,
                invocation=stage.invocation,
                required_capabilities=stage.required_capabilities,
                loop_condition=stage.loop_condition,
                decision_vocabulary=stage.decision_vocabulary,
                override_vocabulary=stage.override_vocabulary,
            )
        else:
            # ParallelStage conversion not needed for this pipeline.
            raise TypeError(
                f"Cannot convert stage {name!r} of type {type(stage).__name__}"
            )

    return MpPipeline(
        stages=mp_stages,
        entry=neutral_pipeline.entry,
        binding_map=neutral_pipeline.binding_map,
        resource_bundles=neutral_pipeline.resource_bundles,
    )


def build_pipeline(
    name: str = "vibecomfy-executor",
    description: str = "",
) -> MpPipeline:
    """Build the VibeComfy executor pipeline.

    The public shape is a neutral :class:`~arnold.pipeline.types.Pipeline`; the
    returned instance is a Megaplan-compatible subclass so it runs under the
    existing CLI executor without bridge changes.
    """
    neutral = (
        PipelineBuilder(
            name=name,
            description=description or "Classify, research, implement, and reply.",
        )
        .add_stage(
            NeutralStage(
                name="classify",
                step=ClassifyStep(),
                produces=(Port(name="plan", content_type="application/json"),),
            ),
            emit_label="done",
        )
        .add_stage(
            NeutralStage(
                name="research",
                step=ResearchStep(),
                consumes=(PortRef(port_name="plan", content_type="application/json"),),
                produces=(Port(name="research_summary", content_type="text/markdown"),),
            ),
            emit_label="done",
        )
        .add_stage(
            NeutralStage(
                name="implement",
                step=ImplementStep(),
                consumes=(
                    PortRef(port_name="plan", content_type="application/json"),
                    PortRef(port_name="research_summary", content_type="text/markdown"),
                ),
                produces=(Port(name="implementation", content_type="text/markdown"),),
            ),
            emit_label="done",
        )
        .add_stage(
            NeutralStage(
                name="reply",
                step=ReplyStep(),
                consumes=(
                    PortRef(port_name="plan", content_type="application/json"),
                    PortRef(port_name="research_summary", content_type="text/markdown"),
                    PortRef(port_name="implementation", content_type="text/markdown"),
                ),
                produces=(Port(name="reply", content_type="text/markdown"),),
            ),
            emit_label="done",
        )
        .build(derive_bindings=True)
    )

    return _to_megaplan_pipeline(neutral)
