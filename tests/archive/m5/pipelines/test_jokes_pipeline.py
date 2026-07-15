"""Focused tests for the native-backed ``jokes`` pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.skip("archived legacy jokes pipeline; native contract coverage is active elsewhere", allow_module_level=True)

from arnold.pipeline import Pipeline, Stage, run_pipeline
from arnold.pipeline.discovery.manifest import Manifest, read_manifest
from arnold.pipeline.native import NativeProgram
from arnold.pipelines.megaplan._pipeline import registry
from arnold.runtime.envelope import RuntimeEnvelope


PIPELINE_INIT = (
    Path(__file__).resolve().parents[4]
    / "arnold"
    / "pipelines"
    / "megaplan"
    / "pipelines"
    / "jokes"
    / "__init__.py"
)


def test_jokes_manifest_is_static_and_discoverable() -> None:
    result = read_manifest(PIPELINE_INIT)
    assert isinstance(result, Manifest)
    assert result.name == "jokes"
    assert result.driver == ("native", "linear")
    assert result.entrypoint == "build_pipeline"
    assert result.capabilities == ("creative", "joke")
    assert "native" in result.supported_modes


def test_jokes_manifest_first_scan_defers_import() -> None:
    scan_root = PIPELINE_INIT.parents[1]
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry,
        "_get_scan_roots",
        lambda: [(scan_root, "arnold.pipelines.megaplan.pipelines")],
    ), patch.object(registry, "_load_module_from_path") as load_spy:
        dispositions = registry.scan_python_pipelines()

    by_name = {d.cli_name: d for d in dispositions}
    assert "jokes" in by_name
    assert by_name["jokes"].status == "discovered"
    assert isinstance(by_name["jokes"].manifest, Manifest)
    assert load_spy.call_count == 0


def test_jokes_package_init_is_thin_metadata_surface() -> None:
    import arnold.pipelines.megaplan.pipelines.jokes as package
    from arnold.pipelines.megaplan.pipelines.jokes import pipeline as pipeline_module

    assert package.build_pipeline is pipeline_module.build_pipeline
    assert package.name == "jokes"
    assert package.driver[0] == "native"
    assert "native" in package.supported_modes
    assert "jokes_native" not in package.__all__
    assert not hasattr(package, "jokes_native")
    assert not hasattr(package, "_build_graph_pipeline")


def test_jokes_mirror_is_compatibility_shim() -> None:
    import arnold.pipelines.megaplan.pipelines.jokes as canonical
    import arnold.pipelines.megaplan.pipelines.jokes.pipeline as canonical_pipeline
    import arnold_pipelines.megaplan.pipelines.jokes as mirror
    import arnold_pipelines.megaplan.pipelines.jokes.pipeline as mirror_pipeline

    assert mirror.build_pipeline is canonical.build_pipeline
    assert mirror_pipeline.build_pipeline is canonical_pipeline.build_pipeline
    assert mirror.__all__ == canonical.__all__


def test_jokes_build_pipeline_returns_native_backed_projected_shell() -> None:
    from arnold.pipelines.megaplan.pipelines.jokes import build_pipeline

    pipeline = build_pipeline(topic="dependency graphs")

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "jokes"
    assert tuple(pipeline.resource_bundles) == ()
    assert pipeline.entry == "draft"
    assert tuple(pipeline.stages) == ("draft", "tighten", "emit")
    assert [edge.target for edge in pipeline.stages["draft"].edges] == ["tighten"]
    assert [edge.target for edge in pipeline.stages["tighten"].edges] == ["emit"]
    assert pipeline.stages["emit"].edges == ()
    for stage in pipeline.stages.values():
        assert isinstance(stage, Stage)
        assert stage.step.prompt_key
        assert stage.step.topic == "dependency graphs"


def test_jokes_runs_natively_and_emits_final_artifact(tmp_path) -> None:
    from arnold.pipelines.megaplan.pipelines.jokes import build_pipeline

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
