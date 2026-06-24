from __future__ import annotations

from dataclasses import asdict, fields

import arnold.pipeline as pipeline
import arnold.pipeline.legacy as legacy
import arnold.pipeline.native as native
from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.native import NativeInstruction, NativeProgram, project_graph
from arnold.pipeline.types import Edge, Stage, StepContext, StepResult


class _Step:
    name = "only"
    kind = "test"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


def test_native_first_import_surface_is_available_from_pipeline_and_native() -> None:
    names = (
        "NativeProgram",
        "compile_pipeline",
        "project_graph",
        "run_native_pipeline",
        "persist_native_cursor",
        "read_native_cursor",
        "upgrade_graph_cursor_to_native",
    )

    for name in names:
        assert getattr(pipeline, name) is getattr(native, name)
        assert name in pipeline.__all__
        assert name in native.__all__


def test_legacy_namespace_exports_graph_runtime_symbols() -> None:
    names = (
        "Pipeline",
        "Stage",
        "ParallelStage",
        "Edge",
        "StepContext",
        "StepResult",
        "PipelineBuilder",
        "run_pipeline",
        "run_pipeline_resume",
    )

    for name in names:
        assert getattr(legacy, name) is getattr(pipeline, name)
        assert name in legacy.__all__


def test_pipeline_native_program_is_preserved_by_dataclass_and_builder_helpers() -> None:
    program = NativeProgram(
        name="contract",
        instructions=(NativeInstruction(pc=0, op="phase", name="only", func=_Step().run),),
    )
    builder = PipelineBuilder("contract")
    builder.add_stage(
        Stage(
            name="only",
            step=_Step(),
            edges=(Edge(label="done", target="halt"),),
        )
    )

    built = builder.build(native_program=program)
    payload = asdict(built)

    assert "native_program" in {field.name for field in fields(type(built))}
    assert built.native_program is program
    assert payload["native_program"]["name"] == "contract"


def test_project_graph_attaches_native_program_to_projected_pipeline() -> None:
    program = NativeProgram(
        name="projected",
        instructions=(NativeInstruction(pc=0, op="phase", name="only", func=_Step().run),),
    )

    projected = project_graph(program)

    assert projected.native_program is program
