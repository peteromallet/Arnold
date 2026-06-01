"""W2 — policy path inherits the bare-path override-edge dispatch ladder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from megaplan._pipeline.executor import run_pipeline, run_pipeline_with_policy
from megaplan._pipeline.override import override_edge
from megaplan._pipeline.runtime import RuntimePolicy


@dataclass
class _Halt:
    name: str = "halt_step"
    kind: str = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


@dataclass
class _Escapes:
    name: str = "escapes"
    kind: str = "decide"
    prompt_key = None
    slot = None
    action: str = "force_proceed"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=PipelineVerdict(score=0.0, override=self.action),
            next="fallback",
        )


def _build_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "escapes": Stage(
                name="escapes",
                step=_Escapes(action="force_proceed"),
                edges=(
                    Edge(label="fallback", target="bad"),
                    override_edge("force_proceed", target="forced"),
                ),
            ),
            "forced": Stage(
                name="forced", step=_Halt(),
                edges=(Edge(label="halt", target="halt"),),
            ),
            "bad": Stage(
                name="bad", step=_Halt(),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="escapes",
    )


def test_policy_path_dispatches_override_edge_like_bare_path(tmp_path: Path) -> None:
    pipeline_a = _build_pipeline()
    pipeline_b = _build_pipeline()
    ctx_a = StepContext(plan_dir=tmp_path / "a", state={}, profile=None, mode="code", inputs={})
    ctx_b = StepContext(plan_dir=tmp_path / "b", state={}, profile=None, mode="code", inputs={})
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    bare = run_pipeline(pipeline_a, ctx_a, artifact_root=tmp_path / "a")
    policy = RuntimePolicy()
    via_policy = run_pipeline_with_policy(
        pipeline_b, ctx_b, artifact_root=tmp_path / "b", policy=policy
    )
    assert bare["final_stage"] == "forced"
    assert via_policy["final_stage"] == "forced"
