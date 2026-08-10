"""Native contract tests for the ``jokes`` pipeline (restored from archive/m5).

Verifies the native-first package contract: build_pipeline returns a
native-backed projected shell, metadata is correct, and no graph-era
builders are exposed publicly.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipeline import Pipeline
from arnold.pipeline.types import Stage
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.native import NativeProgram
from arnold.runtime.envelope import RuntimeEnvelope


# ── Package metadata / import surface ────────────────────────────────────


def test_jokes_package_init_is_thin_metadata_surface() -> None:
    import arnold_pipelines.megaplan.pipelines.jokes as package

    assert package.name == "jokes"
    assert package.driver[0] == "native"
    assert "native" in package.supported_modes
    assert package.entrypoint == "build_pipeline"
    assert callable(package.build_pipeline)
    # No legacy graph builders leaked.
    assert not hasattr(package, "_build_graph_pipeline")
    assert "build_graph_pipeline" not in (getattr(package, "__all__", ()) or ())


def test_jokes_mirror_is_compatibility_shim() -> None:
    import arnold_pipelines.megaplan.pipelines.jokes as canonical
    import arnold_pipelines.megaplan.pipelines.jokes.pipeline as canonical_pipeline

    # The mirror import should resolve to the same objects.
    assert canonical.build_pipeline is canonical_pipeline.build_pipeline
    assert canonical.__all__ == canonical_pipeline.__all__


# ── Native contract assertions ───────────────────────────────────────────


def test_jokes_build_pipeline_returns_native_backed_projected_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.jokes import build_pipeline

    pipeline = build_pipeline(topic="dependency graphs")

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "jokes"
    assert tuple(pipeline.resource_bundles) == ()
    assert pipeline.entry == "draft"
    assert tuple(pipeline.stages) == ("draft", "tighten", "emit")
    # Verify linear edges: draft → tighten → emit
    assert [edge.target for edge in pipeline.stages["draft"].edges] == ["tighten"]
    assert [edge.target for edge in pipeline.stages["tighten"].edges] == ["emit"]
    assert pipeline.stages["emit"].edges == ()
    for stage in pipeline.stages.values():
        assert isinstance(stage, Stage)
        assert stage.step.prompt_key
        assert stage.step.topic == "dependency graphs"


def test_jokes_runs_natively_and_emits_final_artifact(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.pipelines.jokes import build_pipeline

    pipeline = build_pipeline(topic="dependency graphs")
    plan_dir = tmp_path / "jokes"

    envelope = RuntimeEnvelope(artifact_root=str(plan_dir))
    run_pipeline(pipeline, initial_state={}, envelope=envelope)

    emit_dir = plan_dir / "emit"
    assert emit_dir.is_dir()
    artifacts = sorted(emit_dir.glob("v*.md"))
    assert len(artifacts) >= 1
    final_artifact = artifacts[-1]
    assert "dependency graphs" in final_artifact.read_text(encoding="utf-8")


def test_jokes_native_program_has_instructions() -> None:
    """The native program compiled from jokes has phase instructions."""
    from arnold_pipelines.megaplan.pipelines.jokes import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    # Must have either instructions or phases.
    assert native.instructions or native.phases
