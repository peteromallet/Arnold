"""Pipeline assembly for the live-supervisor pipeline."""

from __future__ import annotations

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import Edge, Pipeline, Stage
from arnold_pipelines.megaplan.pipelines.live_supervisor.steps import (
    ClassifyStep,
    DiagnoseStep,
    RecheckEmitStep,
    RepairDecisionStep,
)


def build_pipeline() -> Pipeline:
    """Build the classify→diagnose→repair_decision→recheck_emit pipeline."""
    builder = PipelineBuilder(
        name="live-supervisor",
        description=(
            "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
            "safe repair actions for likely-live Megaplan/Arnold runs."
        ),
    )

    builder.add_stage(
        Stage(
            name="classify",
            step=ClassifyStep(),
            edges=(Edge(label="diagnose", target="diagnose"),),
        ),
        emit_label="diagnose",
    )
    builder.add_stage(
        Stage(
            name="diagnose",
            step=DiagnoseStep(),
            edges=(Edge(label="repair_decision", target="repair_decision"),),
        ),
        emit_label="repair_decision",
    )
    builder.add_stage(
        Stage(
            name="repair_decision",
            step=RepairDecisionStep(),
            edges=(Edge(label="recheck_emit", target="recheck_emit"),),
        ),
        emit_label="recheck_emit",
    )
    builder.add_stage(
        Stage(
            name="recheck_emit",
            step=RecheckEmitStep(),
            edges=(Edge(label="halt", target="halt"),),
        ),
    )

    return builder.build()
