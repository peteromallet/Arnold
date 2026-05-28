"""Sprint 4 Chunk D — SubloopStep runs a child Pipeline and promotes it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.subloop import SubloopStep


@dataclass
class _ChildLeaf:
    name: str = "leaf"
    kind: str = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        out = ctx.plan_dir / "leaf.json"
        out.write_text(json.dumps({"verdict": "ok"}))
        return StepResult(
            outputs={"leaf": out},
            next="halt",
            state_patch={"child_done": True, "score": 0.9},
        )


def _child_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "leaf": Stage(name="leaf", step=_ChildLeaf(),
                          edges=(Edge(label="halt", target="halt"),)),
        },
        entry="leaf",
    )


def test_subloop_runs_child_and_emits_verdict(tmp_path: Path) -> None:
    subloop = SubloopStep(
        name="tiebreaker",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed" if state.get("child_done") else "iterate",
    )
    assert isinstance(subloop, Step)
    assert subloop.kind == "subloop"

    pipeline = Pipeline(
        stages={
            "tiebreaker": Stage(name="tiebreaker", step=subloop,
                                edges=(
                                    Edge(label="proceed", target="done", kind="gate", recommendation="proceed"),
                                )),
            "done": Stage(name="done", step=_ChildLeaf(),
                          edges=(Edge(label="halt", target="halt"),)),
        },
        entry="tiebreaker",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    # Child artifacts land under the subdir.
    assert (tmp_path / "tiebreaker" / "leaf.json").exists()
    assert (tmp_path / "tiebreaker" / "state.json").exists()
    child_state = json.loads((tmp_path / "tiebreaker" / "state.json").read_text())
    assert child_state["child_done"] is True

    # Parent reached the gate-edge target.
    assert result["final_stage"] == "done"
    parent_state = result["state"]
    assert "subloop:tiebreaker:recommendation" in parent_state
    assert parent_state["subloop:tiebreaker:recommendation"] == "proceed"


def test_subloop_promotion_callable_decides_recommendation(tmp_path: Path) -> None:
    """A different promote callable changes which gate edge fires."""

    subloop = SubloopStep(
        name="tb",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "iterate",
    )
    pipeline = Pipeline(
        stages={
            "tb": Stage(name="tb", step=subloop,
                        edges=(
                            Edge(label="iterate", target="iter_done", kind="gate", recommendation="iterate"),
                            Edge(label="proceed", target="proceed_done", kind="gate", recommendation="proceed"),
                        )),
            "iter_done": Stage(name="iter_done", step=_ChildLeaf(),
                               edges=(Edge(label="halt", target="halt"),)),
            "proceed_done": Stage(name="proceed_done", step=_ChildLeaf(),
                                  edges=(Edge(label="halt", target="halt"),)),
        },
        entry="tb",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "iter_done"


def test_subloop_without_child_pipeline_raises(tmp_path: Path) -> None:
    subloop = SubloopStep(name="bad", child_pipeline=None)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    with pytest.raises(ValueError, match="no child_pipeline"):
        subloop.run(ctx)
