"""Tests for envelope plumbing through pattern_dynamic fan-out + KeyPool."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

import pytest

from megaplan._pipeline.envelope import (
    EMPTY_ENVELOPE,
    RunEnvelope,
    _envelope_ctx,
    _fanout_active_ctx,
    current_envelope,
    make_envelope,
)
from megaplan._pipeline.pattern_dynamic import (
    _DynamicFanoutStep,
    _PanelFromArtifactStep,
)
from megaplan._pipeline.types import StepContext, StepResult
from megaplan.runtime.key_pool import KeyPool


@dataclass(frozen=True)
class _StubGenerator:
    name: str = "gen"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(state_patch={"specs": [{"i": 0}, {"i": 1}, {"i": 2}]})


@dataclass(frozen=True)
class _Observer:
    name: str = "obs"
    seen: list = field(default_factory=list)

    def run(self, ctx: StepContext) -> StepResult:
        self.seen.append(
            (
                _fanout_active_ctx.get(),
                _envelope_ctx.get(),
            )
        )
        return StepResult(state_patch={})


def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
    return StepResult(state_patch={"n": len(results)})


def _ctx(envelope: RunEnvelope = EMPTY_ENVELOPE, inputs=None, plan_dir=None) -> StepContext:
    from pathlib import Path

    return StepContext(
        plan_dir=Path(plan_dir) if plan_dir else Path("/tmp"),
        state={},
        profile=None,
        mode="run",
        inputs=inputs or {},
        envelope=envelope,
    )


def test_dynamic_fanout_sets_fanout_active_and_envelope_ctx():
    observer = _Observer(seen=[])
    step = _DynamicFanoutStep(
        name="fanout",
        generator=_StubGenerator(),
        base_prompt=observer,
        join_fn=_join,
    )
    env = make_envelope(taint="tainted", cost=2.5, lineage=("x",))
    ctx = _ctx(env)

    # Outside fan-out: both ContextVars at defaults.
    assert _fanout_active_ctx.get() is False
    assert _envelope_ctx.get() is None

    step.run(ctx)

    # 3 specs -> 3 observations, all under fan-out + envelope visible.
    assert len(observer.seen) == 3
    for active, visible in observer.seen:
        assert active is True
        assert visible == env

    # ContextVars restored on exit.
    assert _fanout_active_ctx.get() is False
    assert _envelope_ctx.get() is None


def test_fanout_active_ctx_resets_after_exception(tmp_path):
    @dataclass(frozen=True)
    class Boom:
        name: str = "boom"

        def run(self, ctx: StepContext) -> StepResult:
            raise RuntimeError("boom")

    step = _DynamicFanoutStep(
        name="fanout",
        generator=_StubGenerator(),
        base_prompt=Boom(),
        join_fn=_join,
    )
    with pytest.raises(RuntimeError):
        step.run(_ctx(make_envelope(taint="tainted")))
    assert _fanout_active_ctx.get() is False
    assert _envelope_ctx.get() is None


def test_panel_from_artifact_sets_envelope_ctx(tmp_path):
    artifact = tmp_path / "specs.json"
    artifact.write_text('[{"i":0},{"i":1}]')
    observer = _Observer(seen=[])
    step = _PanelFromArtifactStep(
        name="panel",
        artifact_ref="specs_path",
        base_template=observer,
        join_fn=_join,
    )
    env = make_envelope(taint="tainted", cost=1.0)
    ctx = _ctx(env, inputs={"specs_path": str(artifact)}, plan_dir=tmp_path)
    step.run(ctx)
    assert len(observer.seen) == 2
    for active, visible in observer.seen:
        assert active is True
        assert visible == env


def test_keypool_reads_current_envelope():
    pool = KeyPool()
    # Default: no envelope set.
    assert pool.current_envelope() is None
    env = make_envelope(taint="tainted", cost=4.2)
    token = _envelope_ctx.set(env)
    try:
        assert pool.current_envelope() == env
        assert current_envelope() == env
    finally:
        _envelope_ctx.reset(token)
    assert pool.current_envelope() is None
