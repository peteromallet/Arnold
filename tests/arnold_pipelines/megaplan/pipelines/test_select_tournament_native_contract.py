"""Native contract tests for the ``select-tournament`` pipeline (restored from archive/m5).

Verifies the native-first package contract, port/binding declarations,
and native execution — without depending on deleted _pipeline modules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.types import ParallelStage, Stage
from arnold.pipeline import Port, PortRef
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.native import NativeProgram
from arnold.pipeline.contracts import PortBindError
from arnold.runtime.envelope import RuntimeEnvelope


# ── Package metadata / native contract ───────────────────────────────────


def test_select_tournament_package_metadata() -> None:
    import arnold_pipelines.megaplan.pipelines.select_tournament as pkg

    assert pkg.name == "select-tournament"
    assert pkg.driver[0] == "native"
    assert "native" in pkg.supported_modes
    assert pkg.entrypoint == "build_pipeline"
    assert callable(pkg.build_pipeline)
    assert not hasattr(pkg, "_build_graph_pipeline")


def test_select_tournament_build_pipeline_returns_native_backed_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline(candidates=("a", "b", "c", "d"))
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "select-tournament"
    assert tuple(pipeline.resource_bundles) == ()
    assert tuple(pipeline.stages) == ("score_candidates", "pairwise_bracket", "winner")


def test_select_tournament_native_program_has_instructions() -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    assert native.instructions or native.phases


def test_select_tournament_mirror_is_compatibility_shim() -> None:
    import arnold_pipelines.megaplan.pipelines.select_tournament as canonical
    import arnold_pipelines.megaplan.pipelines.select_tournament.pipeline as canonical_pipeline

    assert canonical.build_pipeline is canonical_pipeline.build_pipeline
    assert set(canonical.__all__) == set(canonical_pipeline.__all__)


# ── Port / binding assertions ────────────────────────────────────────────


def test_select_tournament_declares_binding_map() -> None:
    """The native program binds score_candidates → pairwise_bracket → winner."""
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline(candidates=("a", "b", "c", "d"))
    # Binding is in the native program (not Pipeline.binding_map in native-first mode).
    assert pipeline.native_program is not None
    # Verify the port wiring exists in the native program phases.
    phase_names = [p.name for p in pipeline.native_program.phases]
    assert "pairwise_bracket" in phase_names
    assert "winner" in phase_names


def test_select_tournament_score_candidates_is_parallel_stage() -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline(candidates=("a", "b", "c", "d"))
    score_stage = pipeline.stages["score_candidates"]
    assert isinstance(score_stage, ParallelStage)
    assert score_stage.max_workers == 4


# ── Runtime smoke ────────────────────────────────────────────────────────


def test_select_tournament_runs_natively(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline(candidates=("a", "b", "c", "d"))
    plan_dir = tmp_path / "select-tournament"

    result = run_pipeline(
        pipeline,
        initial_state={},
        envelope=RuntimeEnvelope(artifact_root=str(plan_dir)),
    )
    assert result.state["select_tournament_winner"] == "d"
    winner = json.loads((plan_dir / "winner" / "v1.json").read_text())
    assert winner["winner"] == "d"


def test_select_tournament_non_default_candidates_drive_native_program(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament import build_pipeline

    pipeline = build_pipeline(candidates=("red", "green", "blue"))
    plan_dir = tmp_path / "select-tournament-custom"

    assert pipeline.native_program is not None
    parallel_block = pipeline.native_program.parallel_blocks[0]
    assert parallel_block.branches == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
    )
    assert pipeline.stages["score_candidates"].max_workers == 3

    result = run_pipeline(
        pipeline,
        initial_state={},
        envelope=RuntimeEnvelope(artifact_root=str(plan_dir)),
    )
    assert result.state["select_tournament_winner"] == "blue"


# ── Private _bind_or_raise tests ─────────────────────────────────────────


def test_select_tournament_private_bind_uses_lowered_authored_declarations() -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament.pipeline import _bind_or_raise

    class _Step:
        produces = ()
        consumes = ()

        def run(self, ctx):
            raise NotImplementedError

    pipeline = Pipeline(
        stages={
            "src": Stage(
                name="src",
                step=_Step(),
                edges=(),
                writes=(Port(name="alpha", content_type="text/markdown"),),
            ),
            "sink": Stage(
                name="sink",
                step=_Step(),
                edges=(),
                reads=(PortRef(port_name="alpha", content_type="text/markdown"),),
            ),
        },
        entry="src",
    )
    bound = _bind_or_raise(pipeline)
    assert bound.binding_map == {("sink", "alpha"): ("src", "alpha")}


def test_select_tournament_private_bind_rejects_drifted_declarations() -> None:
    from arnold_pipelines.megaplan.pipelines.select_tournament.pipeline import _bind_or_raise

    class _Step:
        produces = ()
        consumes = ()

        def run(self, ctx):
            raise NotImplementedError

    pipeline = Pipeline(
        stages={
            "src": Stage(
                name="src",
                step=_Step(),
                edges=(),
                writes=(Port(name="alpha", content_type="text/markdown"),),
                produces=(Port(name="other", content_type="text/markdown"),),
            ),
            "sink": Stage(
                name="sink",
                step=_Step(),
                edges=(),
                reads=(PortRef(port_name="alpha", content_type="text/markdown"),),
            ),
        },
        entry="src",
    )
    with pytest.raises(PortBindError, match="no_match"):
        _bind_or_raise(pipeline)
