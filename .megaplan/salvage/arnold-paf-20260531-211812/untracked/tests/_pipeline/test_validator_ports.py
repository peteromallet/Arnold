"""Tests for _validate_ports in megaplan._pipeline.validator (M5a T11).

Four contract units:
1. flag-OFF parity: validate() behaves identically to pre-T11 (no port defects).
2. flag-ON well-wired clean: produced port has a consumer — no port defects.
3. flag-ON unwired defect: produced port has no consumer — defect surfaces.
4. flag-ON unregistered skipped: step not in registry — silently skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import megaplan._pipeline.patterns as patterns_mod
from megaplan._pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from megaplan._pipeline.validator import validate


# ── Minimal Step doubles ──────────────────────────────────────────────────


@dataclass
class _StubStep:
    name: str
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult(next="done")


# ── Helpers ───────────────────────────────────────────────────────────────


def _single_stage_pipeline(step: _StubStep) -> Pipeline:
    return Pipeline(
        stages={"s": Stage(name="s", step=step, edges=())},
        entry="s",
    )


def _two_stage_pipeline(producer_step: _StubStep, consumer_step: _StubStep) -> Pipeline:
    return Pipeline(
        stages={
            "producer": Stage(
                name="producer",
                step=producer_step,
                edges=(Edge(label="next", target="consumer"),),
            ),
            "consumer": Stage(
                name="consumer",
                step=consumer_step,
                edges=(),
            ),
        },
        entry="producer",
    )


# ── 1. flag-OFF parity ────────────────────────────────────────────────────


def test_flag_off_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH unset, validate() produces no port defects
    even for a step that has a registered produced port with no consumer."""
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    monkeypatch.setitem(
        patterns_mod._NODE_REGISTRY,
        "test_producer_parity",
        {
            "tier": "topology",
            "consumes": (),
            "produces": ("test_port_parity",),
            "arnold_api_version": "0.1.0-m5a",
        },
    )
    step = _StubStep(name="test_producer_parity")
    pipeline = _single_stage_pipeline(step)

    diag = validate(pipeline)
    port_defects = [d for d in diag.defects if "test_port_parity" in d]
    assert port_defects == [], f"Expected no port defects with flag off; got: {port_defects}"


# ── 2. flag-ON well-wired clean ───────────────────────────────────────────


def test_flag_on_well_wired_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, a produced port that is consumed by
    another stage in the pipeline generates no port defect."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.setitem(
        patterns_mod._NODE_REGISTRY,
        "test_producer_clean",
        {
            "tier": "topology",
            "consumes": (),
            "produces": ("test_port_clean",),
            "arnold_api_version": "0.1.0-m5a",
        },
    )
    monkeypatch.setitem(
        patterns_mod._NODE_REGISTRY,
        "test_consumer_clean",
        {
            "tier": "topology",
            "consumes": ("test_port_clean",),
            "produces": (),
            "arnold_api_version": "0.1.0-m5a",
        },
    )
    producer = _StubStep(name="test_producer_clean")
    consumer = _StubStep(name="test_consumer_clean")
    pipeline = _two_stage_pipeline(producer, consumer)

    diag = validate(pipeline)
    port_defects = [d for d in diag.defects if "test_port_clean" in d]
    assert port_defects == [], f"Expected no port defects; got: {port_defects}"


# ── 3. flag-ON unwired defect ─────────────────────────────────────────────


def test_flag_on_unwired_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, a produced port with no consumer in
    the pipeline surfaces as a defect in the expected format."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.setitem(
        patterns_mod._NODE_REGISTRY,
        "test_producer_unwired",
        {
            "tier": "topology",
            "consumes": (),
            "produces": ("test_port_unwired",),
            "arnold_api_version": "0.1.0-m5a",
        },
    )
    step = _StubStep(name="test_producer_unwired")
    pipeline = _single_stage_pipeline(step)

    diag = validate(pipeline)
    port_defects = [d for d in diag.defects if "test_port_unwired" in d]
    assert len(port_defects) == 1
    assert "stage 's'" in port_defects[0]
    assert "test_port_unwired" in port_defects[0]
    assert "no downstream consumer" in port_defects[0]


# ── 4. flag-ON unregistered skipped ──────────────────────────────────────


def test_flag_on_unregistered_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, a step whose name is not in _NODE_REGISTRY
    is silently skipped — no port defects emitted."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    # Ensure this name is NOT in the registry.
    patterns_mod._NODE_REGISTRY.pop("test_unregistered_step", None)

    step = _StubStep(name="test_unregistered_step")
    pipeline = _single_stage_pipeline(step)

    diag = validate(pipeline)
    port_defects = [d for d in diag.defects if "produces port" in d]
    assert port_defects == [], f"Expected no port defects for unregistered step; got: {port_defects}"
