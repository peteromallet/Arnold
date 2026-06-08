"""Tests for ReceiptDecorator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.receipt import ReceiptDecorator
from arnold.pipelines.megaplan._pipeline.types import Step, StepContext, StepResult, PipelineVerdict


@dataclass
class _Trivial:
    name: str = "trivial"
    kind: str = "produce"
    prompt_key: str | None = "trivial"
    slot: str | None = "trivial"

    def run(self, ctx: StepContext) -> StepResult:
        out = ctx.plan_dir / self.name / "out.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("trivial output")
        return StepResult(
            outputs={"out": out},
            verdict=PipelineVerdict(score=0.8, flags=("a", "b"), recommendation="proceed"),
            next="done",
            state_patch={"x": 1},
        )


@dataclass
class _Failing:
    name: str = "failing"
    kind: str = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        raise RuntimeError("boom")


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={},
    )


def test_receipt_decorator_satisfies_step_protocol() -> None:
    wrapped = ReceiptDecorator(_Trivial())
    assert isinstance(wrapped, Step)


def test_receipt_decorator_writes_success_receipt(tmp_path: Path) -> None:
    wrapped = ReceiptDecorator(_Trivial())
    result = wrapped.run(_ctx(tmp_path))

    receipt_path = tmp_path / "trivial" / "receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["step_name"] == "trivial"
    assert receipt["step_kind"] == "produce"
    assert receipt["slot"] == "trivial"
    assert receipt["outcome"] == "success"
    assert receipt["error"] is None
    assert receipt["next"] == "done"
    assert receipt["verdict"]["recommendation"] == "proceed"
    assert receipt["state_patch_keys"] == ["x"]
    assert "out" in receipt["outputs"]
    assert receipt["duration_ms"] >= 0


def test_receipt_decorator_writes_error_receipt(tmp_path: Path) -> None:
    wrapped = ReceiptDecorator(_Failing())
    with pytest.raises(RuntimeError, match="boom"):
        wrapped.run(_ctx(tmp_path))

    receipt_path = tmp_path / "failing" / "receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["outcome"] == "error"
    assert "boom" in receipt["error"]


def test_receipt_decorator_preserves_inner_protocol_attrs() -> None:
    inner = _Trivial()
    wrapped = ReceiptDecorator(inner)
    assert wrapped.name == inner.name
    assert wrapped.kind == inner.kind
    assert wrapped.slot == inner.slot
    assert wrapped.prompt_key == inner.prompt_key


def test_receipt_decorator_passes_result_through(tmp_path: Path) -> None:
    wrapped = ReceiptDecorator(_Trivial())
    result = wrapped.run(_ctx(tmp_path))
    assert result.next == "done"
    assert result.verdict is not None
    assert result.verdict.recommendation == "proceed"
    assert dict(result.state_patch) == {"x": 1}
