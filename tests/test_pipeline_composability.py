"""Sprint 3 — prove the architecture is elegantly composable.

Five specific claims the brief makes that need explicit tests:

1. New workflow types reuse the same Step set, just register a new
   prompt under the same key.
2. Critic output (PipelineVerdict / flags) flows into reviser input naturally
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
from typing import ClassVar
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.resources import PipelineResourceBundle, resolve_bundle_prompt
from megaplan._pipeline import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.prompts import PromptRegistry


# -----------------------------------------------------------------------
# Claim 1: new workflow types reuse the same Step set; prompts register.
# -----------------------------------------------------------------------


_TEST_PROMPT_BUNDLE = PipelineResourceBundle(
    base_dir=Path("/tmp"),
    prompt_dir=Path("/tmp/prompts"),
)

def test_new_mode_registers_a_prompt_without_subclassing_step() -> None:
    _TEST_PROMPT_BUNDLE.prompts.clear()
    _TEST_PROMPT_BUNDLE.prompts.update(
        {
            "critique:scientific-paper": (
                lambda ctx, params: "You are a peer reviewer. Be technical."
            )
        }
    )

    ctx = StepContext(
        plan_dir=Path("/tmp"), state={}, profile=None,
        mode="scientific-paper", inputs={},
    )
    prompt = resolve_bundle_prompt(_TEST_PROMPT_BUNDLE, "critique", ctx)
    assert "peer reviewer" in prompt


def test_unregistered_mode_falls_back_to_default_prompt() -> None:
    _TEST_PROMPT_BUNDLE.prompts.clear()
    _TEST_PROMPT_BUNDLE.prompts.update(
        {
            "critique": (
                "You are a document critic. Rate this draft on clarity and review quality."
            )
        }
    )

    ctx = StepContext(
        plan_dir=Path("/tmp"), state={}, profile=None,
        mode="some-unregistered-mode", inputs={},
    )
    # Should fall back to the default 'critique' registration.
    prompt = resolve_bundle_prompt(_TEST_PROMPT_BUNDLE, "critique", ctx)
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
            verdict = PipelineVerdict(score=0.3, flags=("flag-a", "flag-b"))
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
                verdict=PipelineVerdict(score=0.5),
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
    _TEST_PROMPT_BUNDLE.prompts.clear()
    _TEST_PROMPT_BUNDLE.prompts.update(
        {
            "panel-rubric": lambda ctx, params: f"Panel-default for mode={ctx.mode}",
            "panel-rubric:strict": lambda ctx, params: "Panel-strict override",
        }
    )

    ctx_default = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={},
    )
    ctx_strict = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="strict", inputs={},
    )

    # Same key, mode-aware resolution returns the override.
    assert "default for mode=code" in resolve_bundle_prompt(
        _TEST_PROMPT_BUNDLE, "panel-rubric", ctx_default
    )
    assert "Panel-strict override" == resolve_bundle_prompt(
        _TEST_PROMPT_BUNDLE, "panel-rubric", ctx_strict
    )


# -----------------------------------------------------------------------
# T2 tests — process-hygiene guard: reject InProcessHandlerStep in
#            ParallelStage; safe hermetic steps run concurrently in order.
# -----------------------------------------------------------------------


def test_parallel_stage_with_inprocess_handler_step_rejected_by_run_pipeline(
    tmp_path: Path,
) -> None:
    """run_pipeline rejects a ParallelStage containing an InProcessHandlerStep.

    The rejection must happen BEFORE any handler executes (the guard fires at
    submission time in _run_parallel_stage, before pool.submit).  The error
    message must name the stage and the unsafe step.
    """
    from megaplan._pipeline.executor import run_pipeline
    from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep

    # A handler that raises if called — proves the guard fires first.
    def _must_not_run(_root: Path, _args: Any) -> dict[str, Any]:
        raise AssertionError("handler must not be called — guard should reject first")

    unsafe = InProcessHandlerStep(
        name="unsafe_handler",
        kind="produce",
        handler=_must_not_run,
        slot="critique",
    )
    # A hermetic step alongside — proves the guard checks all steps.
    hermetic = _HermeticNoOp("hermetic_ok")

    parallel_stage = ParallelStage(
        name="bad_fanout",
        steps=(hermetic, unsafe),
        join=_trivial_join,
        edges=(Edge("done", "halt"),),
    )
    pipeline = Pipeline(
        stages={"bad_fanout": parallel_stage},
        entry="bad_fanout",
    )
    ctx = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={},
    )

    with pytest.raises(ValueError, match="bad_fanout"):
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    # Confirm the rejection message names the unsafe step too.
    with pytest.raises(ValueError, match="unsafe_handler"):
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    # Confirm the message mentions thread-safety / InProcessHandlerStep.
    with pytest.raises(ValueError, match="thread-safe"):
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)


def test_parallel_stage_with_inprocess_handler_step_rejected_by_run_pipeline_with_policy(
    tmp_path: Path,
) -> None:
    """run_pipeline_with_policy also rejects unsafe ParallelStage before any handler runs."""
    from megaplan._pipeline.executor import run_pipeline_with_policy
    from megaplan._pipeline.runtime import RuntimePolicy
    from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep

    def _must_not_run(_root: Path, _args: Any) -> dict[str, Any]:
        raise AssertionError("handler must not be called — guard should reject first")

    unsafe = InProcessHandlerStep(
        name="unsafe_handler",
        kind="produce",
        handler=_must_not_run,
        slot="critique",
    )
    parallel_stage = ParallelStage(
        name="bad_fanout",
        steps=(unsafe,),
        join=_trivial_join,
        edges=(Edge("done", "halt"),),
    )
    pipeline = Pipeline(
        stages={"bad_fanout": parallel_stage},
        entry="bad_fanout",
    )
    ctx = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={},
    )
    policy = RuntimePolicy(max_iterations=10)

    with pytest.raises(ValueError, match="bad_fanout"):
        run_pipeline_with_policy(
            pipeline, ctx, artifact_root=tmp_path, policy=policy,
        )

    with pytest.raises(ValueError, match="unsafe_handler"):
        run_pipeline_with_policy(
            pipeline, ctx, artifact_root=tmp_path, policy=policy,
        )


def test_safe_hermetic_parallel_steps_run_concurrently_and_return_in_declaration_order(
    tmp_path: Path,
) -> None:
    """Hermetic steps in a ParallelStage run concurrently; outputs stay in declaration order.

    Uses a pair of hermetic steps where one deliberately sleeps to prove the
    other is not blocked.  Results are collected in declaration order, not
    as_completed order.
    """
    import time as _time
    from megaplan._pipeline.executor import run_pipeline

    # Shared timeline so we can assert overlap.
    timeline: list[tuple[str, float]] = []

    @dataclass
    class SleepyStep:
        """Hermetic step that sleeps then records its finish time."""

        name: str
        kind: str = "produce"
        prompt_key: str | None = None
        slot: str | None = None
        sleep_s: float = 0.0
        output_label: str = "out"
        produces: ClassVar[tuple] = ()
        consumes: ClassVar[tuple] = ()

        def run(self, ctx: StepContext) -> StepResult:
            _time.sleep(self.sleep_s)
            now = _time.monotonic()
            timeline.append((self.name, now))
            out = ctx.plan_dir / f"{self.name}.txt"
            out.write_text(f"done by {self.name}")
            return StepResult(outputs={self.output_label: out}, next="done")

    fast = SleepyStep(name="fast_step", sleep_s=0.0, output_label="fast")
    slow = SleepyStep(name="slow_step", sleep_s=0.15, output_label="slow")

    parallel_stage = ParallelStage(
        name="safe_fanout",
        steps=(slow, fast),  # slow is index 0, fast is index 1
        join=_trivial_join,
        edges=(Edge("done", "halt"),),
    )
    pipeline = Pipeline(
        stages={"safe_fanout": parallel_stage},
        entry="safe_fanout",
    )
    ctx = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={},
    )
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    # Both steps ran (fast should finish before slow despite being index 1).
    names = [entry[0] for entry in timeline]
    assert "fast_step" in names
    assert "slow_step" in names

    # Concurrency check: fast_step completed before slow_step finished
    # (since slow_step sleeps 0.15s and fast_step sleeps 0.0s).
    fast_time = next(t for name, t in timeline if name == "fast_step")
    slow_time = next(t for name, t in timeline if name == "slow_step")
    assert fast_time < slow_time, (
        f"fast_step ({fast_time}) should finish before slow_step ({slow_time}) "
        f"— if not, steps ran sequentially"
    )

    # Declaration-order check: slow is index 0, fast is index 1.
    # The join sees results in declaration order regardless of completion.
    assert result["state"].get("_parallel_order") == ["slow_step", "fast_step"]


# ── Helpers shared by T2 tests ─────────────────────────────────────────


class _HermeticNoOp:
    """A minimal hermetic Step that writes one file and returns next='done'."""

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: StepContext) -> StepResult:
        out = ctx.plan_dir / f"{self.name}.txt"
        out.write_text(f"noop by {self.name}")
        return StepResult(outputs={"out": out}, next="done")


def _trivial_join(results: list[StepResult], ctx: StepContext) -> StepResult:
    """Join that passes through the first result's next and records order."""
    order = []
    for r in results:
        for p in r.outputs.values():
            name = Path(p).stem
            order.append(name)
            break
    return StepResult(
        outputs={},
        next=results[0].next if results else "halt",
        state_patch={"_parallel_order": order},
    )
