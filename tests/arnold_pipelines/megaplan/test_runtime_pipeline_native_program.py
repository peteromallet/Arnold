from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import Edge as NeutralEdge
from arnold.pipeline.types import Pipeline as NeutralPipeline
from arnold.pipeline.types import Stage as NeutralStage
from arnold_pipelines.megaplan.runtime.bridge import run_pipeline_bridged
from arnold_pipelines.megaplan.runtime.resume import with_entry
from arnold_pipelines.megaplan.step_types import Edge, Stage, StepResult


class _MpNoopStep:
    name = "prep"
    kind = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx) -> StepResult:
        return StepResult(next="halt")


def _megaplan_ctx(*, state: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=state or {},
        inputs={},
        profile=None,
        mode="test",
        budget=None,
        envelope=None,
    )


def test_with_entry_preserves_native_program_for_resume_reentry() -> None:
    program = NativeProgram(name="resume-contract")
    original = NeutralPipeline(
        stages={
            "prep": NeutralStage(
                name="prep",
                step=_MpNoopStep(),
                edges=(NeutralEdge("halt", "halt"),),
            ),
            "review": NeutralStage(
                name="review",
                step=_MpNoopStep(),
                edges=(NeutralEdge("halt", "halt"),),
            ),
        },
        entry="prep",
        resource_bundles=("compat-runner",),
        native_program=program,
    )

    rerouted = with_entry(original, "review")

    assert rerouted.entry == "review"
    assert rerouted.native_program is program
    assert rerouted.resource_bundles == ("compat-runner",)


def test_run_pipeline_bridged_preserves_native_program_on_projected_shells(
    monkeypatch,
    tmp_path: Path,
) -> None:
    program = NativeProgram(name="bridge-contract")
    mp_pipeline = SimpleNamespace(
        stages={
            "prep": Stage(
                name="prep",
                step=_MpNoopStep(),
                edges=(Edge("halt", "halt"),),
            )
        },
        entry="prep",
        binding_map={"x": "y"},
        resource_bundles=("compat-runner",),
        native_program=program,
    )

    captured: dict[str, object] = {}

    def fake_run(pipeline, state, envelope, *, hooks, initial_context):
        captured["pipeline"] = pipeline
        hooks._final_state = dict(state)
        hooks._final_stage = pipeline.entry

    monkeypatch.setattr("arnold.pipeline.runner.run_pipeline", fake_run)

    result = run_pipeline_bridged(
        mp_pipeline,
        _megaplan_ctx(state={"runtime_envelope": {"artifact_root": str(tmp_path)}}),
        artifact_root=tmp_path,
    )

    translated = captured["pipeline"]
    assert isinstance(translated, NeutralPipeline)
    assert translated.native_program is program
    assert translated.resource_bundles == ("compat-runner",)
    assert result["final_stage"] == "prep"


def test_run_pipeline_bridged_keeps_native_pipeline_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    program = NativeProgram(name="already-neutral")
    neutral_pipeline = NeutralPipeline(
        stages={
            "prep": NeutralStage(
                name="prep",
                step=_MpNoopStep(),
                edges=(NeutralEdge("halt", "halt"),),
            )
        },
        entry="prep",
        native_program=program,
    )

    captured: dict[str, object] = {}

    def fake_run(pipeline, state, envelope, *, hooks, initial_context):
        captured["pipeline"] = pipeline
        hooks._final_state = dict(state)
        hooks._final_stage = pipeline.entry

    monkeypatch.setattr("arnold.pipeline.runner.run_pipeline", fake_run)

    run_pipeline_bridged(
        neutral_pipeline,
        _megaplan_ctx(state={"runtime_envelope": {"artifact_root": str(tmp_path)}}),
        artifact_root=tmp_path,
    )

    assert captured["pipeline"] is neutral_pipeline
