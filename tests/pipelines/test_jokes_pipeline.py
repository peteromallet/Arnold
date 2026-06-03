"""Focused tests for the standalone ``jokes`` pipeline — M3a Arnold migration.

Uses Arnold executor and Arnold types.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from arnold.pipeline import Pipeline, Stage, StepContext, run_pipeline
from arnold.runtime.envelope import RuntimeEnvelope
from megaplan._pipeline import registry
from megaplan._pipeline.discovery.manifest import Manifest, read_manifest


PIPELINE_INIT = (
    Path(__file__).resolve().parents[2]
    / "megaplan"
    / "pipelines"
    / "jokes"
    / "__init__.py"
)


def test_jokes_manifest_is_static_and_discoverable() -> None:
    result = read_manifest(PIPELINE_INIT)
    assert isinstance(result, Manifest)
    assert result.name == "jokes"
    assert result.driver == ("graph", "dispatch+emit")
    assert result.entrypoint == "build_pipeline"
    assert result.capabilities == ("creative", "joke")


def test_jokes_manifest_first_scan_defers_import() -> None:
    scan_root = PIPELINE_INIT.parents[1]
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry, "_get_scan_roots", lambda: [(scan_root, "megaplan.pipelines")]
    ), patch.object(registry, "_load_module_from_path") as load_spy:
        dispositions = registry.scan_python_pipelines()

    by_name = {d.cli_name: d for d in dispositions}
    assert "jokes" in by_name
    assert by_name["jokes"].status == "discovered"
    assert isinstance(by_name["jokes"].manifest, Manifest)
    assert load_spy.call_count == 0


def test_jokes_build_pipeline_supplies_content_and_wiring() -> None:
    import importlib

    module = importlib.import_module("megaplan.pipelines.jokes")
    pipeline = module.build_pipeline(topic="dependency graphs")

    assert pipeline.entry == "draft"
    assert set(pipeline.stages) == {"draft", "tighten", "emit"}
    assert [edge.target for edge in pipeline.stages["draft"].edges] == ["tighten"]
    assert [edge.target for edge in pipeline.stages["tighten"].edges] == ["emit"]
    assert pipeline.stages["emit"].edges == ()
    for stage in pipeline.stages.values():
        assert isinstance(stage, Stage)
        assert stage.step.prompt_key


def test_jokes_runs_and_emits_final_artifact(tmp_path) -> None:
    import importlib

    module = importlib.import_module("megaplan.pipelines.jokes")
    pipeline = module.build_pipeline(topic="dependency graphs")
    plan_dir = tmp_path / "jokes"

    envelope = RuntimeEnvelope(artifact_root=str(plan_dir))
    run_pipeline(pipeline, initial_state={}, envelope=envelope)

    # Verify the final emit stage artifact exists on disk.
    # The emit stage writes to <artifact_root>/emit/v1.md and
    # records the path in state_patch["joke_artifact"].
    emit_dir = plan_dir / "emit"
    assert emit_dir.is_dir()
    artifacts = sorted(emit_dir.glob("v*.md"))
    assert len(artifacts) >= 1
    final_artifact = artifacts[-1]
    assert "dependency graphs" in final_artifact.read_text(encoding="utf-8")
