"""T14 MUST integration test: receipt-format parity across the typed-ports
strangler flag for a planning-shape pipeline.

For a planning pipeline (a Step whose `verdict.recommendation` is one of the
four planning-binding literals), the receipt written at receipt.py:109 must
have identical shape AND identical `recommendation` value under flag-ON and
flag-OFF — proving that the M2 substrate swap does not break the receipt
contract that downstream tools depend on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from megaplan._pipeline.receipt import ReceiptDecorator
from megaplan._pipeline.types import (
    PipelineVerdict,
    StepContext,
    StepResult,
)


@dataclass
class _PlanningStep:
    """A planning-binding Step double: emits a fixed `iterate` verdict."""

    name: str = "planning_step"
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=PipelineVerdict(score=1.0, recommendation="iterate"),
            next="iterate",
        )


def _run_and_load_receipt(tmp_path: Path) -> dict:
    decorator = ReceiptDecorator(inner=_PlanningStep())
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    decorator.run(ctx)
    receipt_path = tmp_path / "planning_step" / "receipt.json"
    return json.loads(receipt_path.read_text())


def test_planning_receipt_identical_shape_and_recommendation_across_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    off_dir = tmp_path / "off"
    on_dir = tmp_path / "on"
    off_dir.mkdir()
    on_dir.mkdir()

    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "")
    receipt_off = _run_and_load_receipt(off_dir)

    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    receipt_on = _run_and_load_receipt(on_dir)

    # Same shape (keys).
    assert set(receipt_off.keys()) == set(receipt_on.keys())
    # Same verdict shape and recommendation value at receipt.py:109.
    assert "verdict" in receipt_off and "verdict" in receipt_on
    assert set(receipt_off["verdict"].keys()) == set(receipt_on["verdict"].keys())
    assert (
        receipt_off["verdict"]["recommendation"]
        == receipt_on["verdict"]["recommendation"]
        == "iterate"
    )
    # Same `next` and `outputs` shape.
    assert receipt_off["next"] == receipt_on["next"] == "iterate"
    assert receipt_off["outputs"] == receipt_on["outputs"]
