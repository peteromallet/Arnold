"""Sprint 4 Chunk C acceptance — runtime policy modules + executor.

Pins each of the five policy classes in isolation, then exercises
``run_pipeline_with_policy`` against a hermetic pipeline. The full
``auto.py`` migration is gated by ``MEGAPLAN_PIPELINE_AUTO=1``;
when unset the legacy phase loop is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    Verdict,
)
from megaplan._pipeline.executor import run_pipeline_with_policy
from megaplan._pipeline.runtime import (
    BlockedRetry,
    ContextRetry,
    CostTracker,
    EscalatePolicy,
    RuntimePolicy,
    StallDetector,
    pipeline_runtime_enabled,
    policy_from_cli_args,
)


def test_stall_detector_increments_on_repeat_state() -> None:
    d = StallDetector(threshold=3)
    for _ in range(2):
        d.observe({"current_state": "planned", "history": []})
    assert not d.is_stalled()
    for _ in range(3):
        d.observe({"current_state": "planned", "history": []})
    assert d.is_stalled()


def test_stall_detector_resets_on_state_change() -> None:
    d = StallDetector(threshold=2)
    d.observe({"current_state": "planned", "history": []})
    d.observe({"current_state": "planned", "history": []})
    d.observe({"current_state": "critiqued", "history": []})
    assert not d.is_stalled()


def test_cost_tracker_no_cap_never_aborts() -> None:
    c = CostTracker(cap_usd=None)
    assert not c.should_abort({"meta": {"total_cost_usd": 999.0}})


def test_cost_tracker_caps_at_threshold() -> None:
    c = CostTracker(cap_usd=10.0)
    assert not c.should_abort({"meta": {"total_cost_usd": 9.0}})
    assert c.should_abort({"meta": {"total_cost_usd": 10.5}})


@pytest.mark.parametrize("mode,expected", [
    ("force-proceed", "force_proceed"),
    ("abort", "abort"),
])
def test_escalate_policy_modes(mode: str, expected: str) -> None:
    p = EscalatePolicy(mode=mode)
    assert p.resolve("critiqued") == expected


def test_escalate_policy_fail_raises() -> None:
    p = EscalatePolicy(mode="fail")
    with pytest.raises(RuntimeError, match="escalated"):
        p.resolve("critiqued")


def test_context_retry_respects_cap() -> None:
    r = ContextRetry(cap=2)
    assert r.should_retry({"result": "context_exhausted"})
    assert r.should_retry({"result": "context_exhausted"})
    assert not r.should_retry({"result": "context_exhausted"})


def test_blocked_retry_respects_cap() -> None:
    r = BlockedRetry(cap=1)
    assert r.should_retry({"result": "blocked"})
    assert not r.should_retry({"result": "blocked"})


def test_blocked_retry_ignores_non_blocked() -> None:
    r = BlockedRetry(cap=1)
    assert not r.should_retry({"result": "success"})
    assert r.should_retry({"result": "blocked"})  # still 1 left


def test_policy_from_cli_args_wires_every_flag() -> None:
    p = policy_from_cli_args(
        stall_threshold=7, max_iterations=42, max_cost_usd=12.0,
        max_context_retries=3, max_blocked_retries=2, on_escalate="abort",
    )
    assert p.stall.threshold == 7
    assert p.cost.cap_usd == 12.0
    assert p.escalate.mode == "abort"
    assert p.context_retry.cap == 3
    assert p.blocked_retry.cap == 2
    assert p.max_iterations == 42


def test_pipeline_runtime_enabled_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEGAPLAN_PIPELINE_AUTO", raising=False)
    assert pipeline_runtime_enabled() is False


def test_pipeline_runtime_enabled_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_PIPELINE_AUTO", "1")
    assert pipeline_runtime_enabled() is True


# ----------------------------------------------------------------------------
# Executor wrapper: run_pipeline_with_policy
# ----------------------------------------------------------------------------


@dataclass
class _Trivial:
    name: str = "trivial"
    kind: str = "produce"
    prompt_key = None
    slot = None
    next_label: str = "halt"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self.next_label)


def test_run_pipeline_with_policy_runs_to_halt(tmp_path: Path) -> None:
    pipeline = Pipeline(
        stages={"trivial": Stage(name="trivial", step=_Trivial(),
                                  edges=(Edge(label="halt", target="halt"),))},
        entry="trivial",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    policy = policy_from_cli_args(max_iterations=5)
    result = run_pipeline_with_policy(pipeline, ctx, artifact_root=tmp_path, policy=policy)
    assert result["final_stage"] == "trivial"


def test_run_pipeline_with_policy_respects_max_iterations(tmp_path: Path) -> None:
    """Infinite loop bounded by max_iterations."""

    @dataclass
    class _Loop:
        name: str = "loop"
        kind: str = "produce"
        prompt_key = None
        slot = None

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(next="again")

    pipeline = Pipeline(
        stages={"loop": Stage(name="loop", step=_Loop(),
                              edges=(Edge(label="again", target="loop"),))},
        entry="loop",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    policy = policy_from_cli_args(max_iterations=3, stall_threshold=999)
    result = run_pipeline_with_policy(pipeline, ctx, artifact_root=tmp_path, policy=policy)
    assert result.get("halt_reason") == "max_iterations"


def test_run_pipeline_with_policy_requires_runtimepolicy(tmp_path: Path) -> None:
    pipeline = Pipeline(
        stages={"trivial": Stage(name="trivial", step=_Trivial(),
                                  edges=(Edge(label="halt", target="halt"),))},
        entry="trivial",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    with pytest.raises(TypeError, match="RuntimePolicy"):
        run_pipeline_with_policy(pipeline, ctx, artifact_root=tmp_path, policy={"not": "a policy"})
