"""T11b — runtime port-binding tests.

Covers:
* Typed port bound correctly flag-ON via Pipeline.binding_map → ctx.inputs
  is populated with the upstream artifact path.
* Unbindable consume (missing binding_map entry OR no upstream artifact)
  raises :class:`PortBindError`.
* Flag-OFF: legacy ``v1.md`` fallback in :func:`resolve_inputs` still
  fires unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from megaplan._pipeline.contracts import PortBindError
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.step_helpers import resolve_inputs
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


@dataclass
class _ProducerStep:
    """Writes a fixed artifact at <plan_dir>/<name>/v1.md."""

    name: str
    kind: str = "produce"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        out_dir = ctx.plan_dir / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "v1.md"
        path.write_text(f"hello from {self.name}", encoding="utf-8")
        return StepResult(outputs={self.name: path}, next="next")


@dataclass
class _ConsumerStep:
    """Records the resolved ctx.inputs[port_name] into state_patch."""

    name: str
    consume_name: str
    consume_ct: str = "text/markdown"
    kind: str = "produce"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.consumes:
            self.consumes = (
                PortRef(port_name=self.consume_name, content_type=self.consume_ct),
            )

    def run(self, ctx: StepContext) -> StepResult:
        seen = ctx.inputs.get(self.consume_name)
        return StepResult(
            outputs={},
            state_patch={"seen_path": str(seen) if seen is not None else None},
            next="halt",
        )


def _mk_pipeline(producer: _ProducerStep, consumer: _ConsumerStep, *, binding_map):
    stages = {
        producer.name: Stage(
            name=producer.name,
            step=producer,
            edges=(Edge(label="next", target=consumer.name),),
        ),
        consumer.name: Stage(
            name=consumer.name,
            step=consumer,
            edges=(),
        ),
    }
    return Pipeline(
        stages=stages,
        entry=producer.name,
        binding_map=binding_map,
    )


@pytest.fixture(autouse=True)
def _isolate_flag(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    yield


def test_typed_port_bound_correctly_flag_on(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert out["state"]["seen_path"] == str(tmp_path / "prod" / "v1.md")


def test_unbindable_consume_raises_port_bind_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="ghost")
    # binding_map intentionally omits ("cons", "ghost").
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    with pytest.raises(PortBindError) as ei:
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert ei.value.step_id == "cons"
    assert ei.value.consume_name == "ghost"


def test_flag_off_v1md_fallback_unchanged(tmp_path, monkeypatch):
    # Flag explicitly off: resolve_inputs should fall back to the legacy
    # v1.md path for any ref that is not in ctx.inputs and has no
    # produced artifact yet — and NOT raise PortBindError.
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "0")

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    resolved = resolve_inputs(["unproduced"], ctx)
    assert resolved == {"unproduced": tmp_path / "unproduced" / "v1.md"}


def test_flag_on_resolve_inputs_raises_on_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    with pytest.raises(PortBindError):
        resolve_inputs(["unproduced"], ctx)
