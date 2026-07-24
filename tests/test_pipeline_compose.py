"""Acceptance test #2 — compose a 4-stage pipeline from public primitives.

The pipeline-construction block (delimited by the marker comments below) MUST
stay ≤50 lines of Python. Step subclass definitions and assertions sit
outside the budget.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.step_types import (
    Edge,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)
from arnold_pipelines.megaplan.runtime.bridge import run_pipeline


class _BaseStep:
    prompt_key: str | None = None
    slot: str | None = None

    @property
    def produces(self) -> tuple:
        return ()

    @property
    def consumes(self) -> tuple:
        return ()

    def _write(self, ctx: StepContext, name: str, body: str) -> Path:
        out = Path(ctx.plan_dir) / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body)
        return out


class PrepStep(_BaseStep):
    name = "prep"
    kind = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        out = self._write(ctx, "prep/prep.json", json.dumps({"prepared": True}))
        return StepResult(outputs={"prep": out}, next="to_critique_a", state_patch={"prepped": True})


class CritiqueAStep(_BaseStep):
    name = "critique_a"
    kind = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        out = self._write(ctx, "critique_a/critique.json", json.dumps({"flags": []}))
        return StepResult(outputs={"critique": out}, next="to_critique_b", state_patch={"critique_a_done": True})


class CritiqueBStep(_BaseStep):
    name = "critique_b"
    kind = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        out = self._write(ctx, "critique_b/critique.json", json.dumps({"flags": []}))
        return StepResult(outputs={"critique": out}, next="to_finalize", state_patch={"critique_b_done": True})


class FinalizeStep(_BaseStep):
    name = "finalize"
    kind = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        out = self._write(ctx, "finalize/final.md", "# done\n")
        return StepResult(outputs={"final": out}, next="done", state_patch={"finalized": True})


def test_compose_four_stage_pipeline(tmp_path: Path) -> None:
    prep = PrepStep()
    critique_a = CritiqueAStep()
    critique_b = CritiqueBStep()
    finalize = FinalizeStep()

    assert isinstance(prep, Step)
    assert isinstance(finalize, Step)

    # --- pipeline construction begin
    entry = "prep"
    stages: dict[str, Stage] = {
        "prep": Stage(
            name="prep",
            step=prep,
            edges=(Edge("to_critique_a", "critique_a"),),
        ),
        "critique_a": Stage(
            name="critique_a",
            step=critique_a,
            edges=(Edge("to_critique_b", "critique_b"),),
        ),
        "critique_b": Stage(
            name="critique_b",
            step=critique_b,
            edges=(Edge("to_finalize", "finalize"),),
        ),
        "finalize": Stage(
            name="finalize",
            step=finalize,
            edges=(Edge("done", "halt"),),
        ),
    }
    pipeline = Pipeline(stages=stages, entry=entry)
    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
        inputs={},
        budget=None,
    )
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    # --- pipeline construction end

    for expected in [
        tmp_path / "prep" / "prep.json",
        tmp_path / "critique_a" / "critique.json",
        tmp_path / "critique_b" / "critique.json",
        tmp_path / "finalize" / "final.md",
    ]:
        assert expected.exists(), f"missing artifact: {expected}"

    assert result.get("final_stage") == "finalize"
    state = result["state"]
    assert state.get("finalized") is True
    assert state.get("prepped") is True
    assert state.get("critique_a_done") is True
    assert state.get("critique_b_done") is True
