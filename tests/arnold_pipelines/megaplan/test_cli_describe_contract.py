from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import pytest

from arnold.pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult


class _StaticCheckStep:
    name = "noop"
    kind = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


def test_m1_dispatch_substrate_proof_describe_surfaces_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arnold_pipelines.megaplan.cli import handle_describe
    from arnold_pipelines.megaplan.cli.run import _describe_pipeline
    from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

    facade_path = Path(importlib.import_module("arnold_pipelines.megaplan.pipeline").__file__).resolve()
    response = handle_describe(argparse.Namespace(pipeline_name="megaplan"))
    handle_output = capsys.readouterr().out

    rc = _describe_pipeline("megaplan")
    run_output = capsys.readouterr().out
    compiled = build_and_compile_pipeline()

    assert response["success"] is True
    assert rc == 0
    for expected in (
        "Pipeline: megaplan",
        f"Manifest: {compiled.manifest_hash}",
        f"Source:   {facade_path}",
        "Driver:   native / megaplan",
        "Registration: native",
        "Contract: M1 dispatch substrate proof only; not final Megaplan report conformance.",
        "Modes:           code, doc, creative, joke, plan, native",
    ):
        assert expected in handle_output, (
            "M1 dispatch substrate proof requires megaplan describe output to "
            f"publish {expected!r} without claiming final report conformance."
        )
        assert expected in run_output, (
            "M1 dispatch substrate proof requires run --describe to resolve "
            f"through the same metadata line {expected!r}."
        )


def test_canonical_metadata_comes_from_native_backed_compile_path() -> None:
    from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
    from arnold_pipelines.megaplan.planning.operations import SUPPORTED_OPERATIONS, canonical_metadata

    compiled = build_and_compile_pipeline()
    metadata = canonical_metadata()

    assert metadata["manifest_hash"] == compiled.manifest_hash
    assert metadata["topology_hash"] == compiled.topology_hash
    assert metadata["registration_kind"] == "native"
    assert metadata["compatibility_classification"] == "native"
    assert metadata["source_path"].endswith("/arnold_pipelines/megaplan/pipeline.py")
    assert metadata["authored_source_path"].endswith(
        "/arnold_pipelines/megaplan/workflows/planning.py"
    )
    assert metadata["supported_operations"] == tuple(
        kind.value for kind in sorted(SUPPORTED_OPERATIONS, key=lambda item: item.value)
    )


def test_describe_alias_resolves_to_canonical_megaplan_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arnold_pipelines.megaplan.cli import handle_describe
    from arnold_pipelines.megaplan.cli.run import _describe_pipeline

    response = handle_describe(argparse.Namespace(pipeline_name="planning"))
    handle_output = capsys.readouterr().out

    rc = _describe_pipeline("planning")
    run_output = capsys.readouterr().out

    assert response == {"success": True, "step": "describe", "pipeline": "megaplan"}
    assert rc == 0
    assert "Pipeline: megaplan" in handle_output
    assert "Pipeline: megaplan" in run_output


def test_m1_dispatch_substrate_proof_pipelines_check_uses_manifest_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan import registry as registry_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    module_path = tmp_path / "demo_pipeline.py"
    module_path.write_text(
        "\n".join(
            (
                'name = "demo-pipeline"',
                'description = "manifest-backed pipeline"',
                "default_profile = 'default'",
                "supported_modes = ('native',)",
                "driver = ('native', 'project+validate')",
                "entrypoint = 'build_pipeline'",
                "arnold_api_version = '1.0'",
                "capabilities = ('plan',)",
                "",
                "def build_pipeline():",
                "    return None",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("# demo\n", encoding="utf-8")

    pipeline = Pipeline(
        stages={
            "start": Stage(
                name="start",
                step=_StaticCheckStep(),
                edges=(Edge(label="halt", target="halt"),),
            )
        },
        entry="start",
    )

    monkeypatch.setattr(discovery_mod, "scan_python_pipelines", lambda: [])
    monkeypatch.setattr(registry_mod, "get_pipeline", lambda name: pipeline)
    monkeypatch.setattr(
        registry_mod,
        "pipeline_metadata",
        lambda name: {
            "source_path": str(module_path),
            "manifest_hash": "sha256:test-manifest",
            "driver": ("native", "project+validate"),
            "supported_modes": ("native",),
            "default_profile": "default",
            "compatibility_classification": "native",
        },
    )

    rc = cli_mod._handle_pipelines(
        Path.cwd(),
        argparse.Namespace(pipelines_action="check", pipeline_name="demo-pipeline"),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[manifest.native_execution_missing]" in captured.err, (
        "M1 dispatch substrate proof requires pipelines check to use manifest "
        "metadata context rather than claiming final report conformance."
    )
