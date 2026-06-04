"""Per-pipeline prompt scoping — two pipelines share a Step, use different prompts."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.resources import PipelineResourceBundle, resolve_bundle_prompt
from megaplan._pipeline.types import StepContext


def _ctx(pipeline_name: str | None = None, mode: str = "code") -> StepContext:
    inputs: dict = {}
    if pipeline_name is not None:
        inputs["_pipeline"] = pipeline_name
    return StepContext(
        plan_dir=Path("/tmp"), state={}, profile=None,
        mode=mode, inputs=inputs, budget=None,
    )


def _bundle(prompts: dict[str, object]) -> PipelineResourceBundle:
    return PipelineResourceBundle(
        base_dir=Path("/tmp"),
        prompt_dir=Path("/tmp/prompts"),
        prompts=prompts,
    )


def test_pipeline_scoped_prompt_wins_over_global() -> None:
    bundle = _bundle(
        {
            "scoped-test-key": lambda ctx, p: "GLOBAL",
            "alpha/scoped-test-key": lambda ctx, p: "ALPHA-SCOPED",
        }
    )

    assert (
        resolve_bundle_prompt(bundle, "scoped-test-key", _ctx(pipeline_name="alpha"))
        == "ALPHA-SCOPED"
    )
    assert (
        resolve_bundle_prompt(bundle, "scoped-test-key", _ctx(pipeline_name="beta"))
        == "GLOBAL"
    )


def test_pipeline_mode_scoped_prompt_wins_over_pipeline_default() -> None:
    bundle = _bundle(
        {
            "mode-test-key": lambda ctx, p: "FALLBACK",
            "gamma/mode-test-key": lambda ctx, p: "GAMMA-DEFAULT",
            "gamma/mode-test-key:doc": lambda ctx, p: "GAMMA-DOC",
        }
    )

    assert (
        resolve_bundle_prompt(bundle, "mode-test-key", _ctx(pipeline_name="gamma"))
        == "GAMMA-DEFAULT"
    )
    assert (
        resolve_bundle_prompt(
            bundle,
            "mode-test-key",
            _ctx(pipeline_name="gamma", mode="doc"),
        )
        == "GAMMA-DOC"
    )


def test_resolve_falls_back_to_global_when_pipeline_unspecified() -> None:
    bundle = _bundle({"global-only": lambda ctx, p: "G"})
    # No pipeline in ctx → global lookup.
    assert resolve_bundle_prompt(bundle, "global-only", _ctx()) == "G"


def test_resolve_falls_back_to_global_when_pipeline_unknown() -> None:
    bundle = _bundle({"only-global": lambda ctx, p: "G"})
    # Unknown pipeline → global fallback.
    assert resolve_bundle_prompt(bundle, "only-global", _ctx(pipeline_name="unknown")) == "G"


def test_run_by_name_injects_pipeline_into_ctx(tmp_path: Path) -> None:
    """The registry's run_pipeline_by_name auto-injects ctx.inputs['_pipeline']."""
    from megaplan._pipeline.registry import register_pipeline, run_pipeline_by_name
    from megaplan._pipeline.types import Edge, Pipeline, Stage, StepResult

    captured_pipeline_name: list[str] = []

    class _Witness:
        name = "witness"
        kind = "produce"
        prompt_key = None
        slot = None

        def run(self, ctx: StepContext) -> StepResult:
            pipeline_name = ctx.inputs.get("_pipeline") if isinstance(ctx.inputs, dict) else None
            captured_pipeline_name.append(str(pipeline_name))
            return StepResult(next="halt")

    def _build_witness() -> Pipeline:
        return Pipeline(
            stages={"witness": Stage(
                name="witness", step=_Witness(),
                edges=(Edge(label="halt", target="halt"),),
            )},
            entry="witness",
        )

    register_pipeline("witness-test", _build_witness)
    run_pipeline_by_name("witness-test", plan_dir=tmp_path)
    assert captured_pipeline_name == ["witness-test"]
