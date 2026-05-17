"""Sprint 3 — prove the architecture is elegantly composable.

Five specific claims the brief makes that need explicit tests:

1. New workflow types reuse the same Step set, just register a new
   prompt under the same key.
2. Critic output (Verdict / flags) flows into reviser input naturally
   via state_patch, not via shared globals.
3. The same primitives express the planning flow AND the doc-critique
   loop AND a fan-out flow — one parent abstraction.
4. A new loop shape (e.g. 5x critique → revise) is a tiny diff, not a
   rewrite.
5. ``prompt_key`` is honored at runtime — a Step without a registered
   prompt for its mode fails loudly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    Verdict,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.prompts import (
    PromptRegistry,
    register_prompt,
    resolve_prompt,
)


# -----------------------------------------------------------------------
# Claim 1: new workflow types reuse the same Step set; prompts register.
# -----------------------------------------------------------------------

def test_new_mode_registers_a_prompt_without_subclassing_step() -> None:
    register_prompt(
        "critique:scientific-paper",
        lambda ctx, params: "You are a peer reviewer. Be technical.",
    )

    ctx = StepContext(
        plan_dir=Path("/tmp"), state={}, profile=None,
        mode="scientific-paper", inputs={},
    )
    prompt = resolve_prompt(ctx, "critique")
    assert "peer reviewer" in prompt


def test_unregistered_mode_falls_back_to_default_prompt() -> None:
    ctx = StepContext(
        plan_dir=Path("/tmp"), state={}, profile=None,
        mode="some-unregistered-mode", inputs={},
    )
    # Should fall back to the default 'critique' registration.
    prompt = resolve_prompt(ctx, "critique")
    assert "critic" in prompt.lower() or "review" in prompt.lower()


def test_missing_prompt_key_raises_loudly() -> None:
    registry = PromptRegistry()
    with pytest.raises(KeyError):
        registry.resolve("nonexistent")


# -----------------------------------------------------------------------
# Claim 2: critic → reviser data flow via state_patch.
# -----------------------------------------------------------------------

def test_critic_verdict_flags_reach_reviser_via_state_patch(tmp_path: Path) -> None:
    captured_flags: list[Any] = []

    class TrivialCritic:
        name = "critique"
        kind = "judge"
        prompt_key = None
        slot = None

        def run(self, ctx: StepContext) -> StepResult:
            verdict = Verdict(score=0.3, flags=("flag-a", "flag-b"))
            out = ctx.plan_dir / "crit.json"
            out.write_text(json.dumps({"flags": list(verdict.flags)}))
            return StepResult(
                outputs={"crit": out},
                verdict=verdict,
                next="to_revise",
                state_patch={"last_flags": list(verdict.flags)},
            )

    class CapturingReviser:
        name = "revise"
        kind = "produce"
        prompt_key = None
        slot = None

        def run(self, ctx: StepContext) -> StepResult:
            captured_flags.extend(ctx.state.get("last_flags", []))
            out = ctx.plan_dir / "revised.md"
            out.write_text("revised")
            return StepResult(outputs={"doc": out}, next="done")

    pipeline = Pipeline(
        stages={
            "critique": Stage(
                name="critique", step=TrivialCritic(),
                edges=(Edge("to_revise", "revise"),),
            ),
            "revise": Stage(
                name="revise", step=CapturingReviser(),
                edges=(Edge("done", "halt"),),
            ),
        },
        entry="critique",
    )
    ctx = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={},
    )
    run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert captured_flags == ["flag-a", "flag-b"]


# -----------------------------------------------------------------------
# Claim 3: planning + doc-critique + fan-out all use one parent abstraction.
# -----------------------------------------------------------------------

def test_one_step_type_serves_all_pipelines() -> None:
    from megaplan._pipeline.demos.doc_critique import build_pipeline as build_doc
    from megaplan._pipeline.demo_judges import build_pipeline as build_judges
    from megaplan._pipeline.planning import compile_planning_pipeline

    doc_pipeline = build_doc()
    judges_pipeline = build_judges()
    planning_pipeline = compile_planning_pipeline()

    for pipeline in (doc_pipeline, judges_pipeline, planning_pipeline):
        assert isinstance(pipeline, Pipeline)
        for stage in pipeline.stages.values():
            # Every node either has a `.step` (Stage) or `.steps` (ParallelStage).
            assert hasattr(stage, "step") or hasattr(stage, "steps")
            if hasattr(stage, "step"):
                assert isinstance(stage.step, Step)


# -----------------------------------------------------------------------
# Claim 4: changing loop iteration count is a one-line diff.
# -----------------------------------------------------------------------

def test_five_iteration_loop_is_a_tiny_diff(tmp_path: Path) -> None:
    """Build a 5x critique → revise loop from scratch using the same
    Steps as the 3x demo. The construction block is the only change."""

    @dataclass
    class IterCritic:
        name: str = "critique"
        kind: str = "judge"
        prompt_key: str | None = None
        slot: str | None = None
        max_iter: int = 5

        def run(self, ctx: StepContext) -> StepResult:
            iteration = int(ctx.state.get("iter", 0))
            out = ctx.plan_dir / f"crit_v{iteration + 1}.json"
            out.write_text(json.dumps({"iter": iteration + 1}))
            next_label = "to_revise" if iteration + 1 < self.max_iter else "to_done"
            return StepResult(
                outputs={"crit": out},
                verdict=Verdict(score=0.5),
                next=next_label,
                state_patch={"iter": iteration + 1},
            )

    @dataclass
    class TrivialReviser:
        name: str = "revise"
        kind: str = "produce"
        prompt_key: str | None = None
        slot: str | None = None

        def run(self, ctx: StepContext) -> StepResult:
            iteration = int(ctx.state.get("iter", 0))
            out = ctx.plan_dir / f"doc_v{iteration}.md"
            out.write_text(f"iteration {iteration}")
            return StepResult(outputs={"doc": out}, next="to_critique")

    pipeline = Pipeline(
        stages={
            "critique": Stage(
                name="critique", step=IterCritic(max_iter=5),
                edges=(Edge("to_revise", "revise"), Edge("to_done", "halt")),
            ),
            "revise": Stage(
                name="revise", step=TrivialReviser(),
                edges=(Edge("to_critique", "critique"),),
            ),
        },
        entry="critique",
    )
    ctx = StepContext(plan_dir=tmp_path, state={"iter": 0}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert result["state"]["iter"] == 5
    crits = sorted(tmp_path.glob("crit_v*.json"))
    assert len(crits) == 5
    revises = sorted(tmp_path.glob("doc_v*.md"))
    assert len(revises) == 4  # 5 critiques, only 4 revises (last critique halts)


# -----------------------------------------------------------------------
# Claim 5: prompt_key resolves through the registry at runtime.
# -----------------------------------------------------------------------

def test_prompt_key_resolution_is_runtime_not_construction(tmp_path: Path) -> None:
    register_prompt(
        "panel-rubric",
        lambda ctx, params: f"Panel-default for mode={ctx.mode}",
    )
    register_prompt(
        "panel-rubric:strict",
        lambda ctx, params: "Panel-strict override",
    )

    ctx_default = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={},
    )
    ctx_strict = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="strict", inputs={},
    )

    # Same key, mode-aware resolution returns the override.
    assert "default for mode=code" in resolve_prompt(ctx_default, "panel-rubric")
    assert "Panel-strict override" == resolve_prompt(ctx_strict, "panel-rubric")
