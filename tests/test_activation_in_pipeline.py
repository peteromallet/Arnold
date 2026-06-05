"""Tests for per-step Activation lifecycle wiring in executor.run_pipeline.

Covers:
- Activation created + PENDING→READY→RUNNING→SUCCEEDED per step (flag OFF: no events)
- flag ON: ACTIVATION_TRANSITIONED events emitted in order per step
- flag OFF: zero events emitted
- FAILED lifecycle emitted when step raises (flag ON)
- identity: activation_id is stable across two calls with same (node, ports, profile)
- 3-step pipeline: each step gets its own activation_id; correct event count
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.pipelines.megaplan._core.activation import compute_activation_id, LifecycleState


# ---------------------------------------------------------------------------
# Minimal step helpers
# ---------------------------------------------------------------------------

def _make_step(name: str, *, next_label: str = "halt", state_patch: dict | None = None):
    """Return a minimal Step-like object."""

    class _Step:
        kind = "produce"
        prompt_key = ""
        slot = ""
        produces: tuple = ()
        consumes: tuple = ()

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(
                next=next_label,
                state_patch=state_patch or {},
                outputs={},
            )

    s = _Step()
    s.__class__.__name__ = name
    return s


def _make_failing_step(name: str, exc: BaseException | None = None):
    _exc = exc or RuntimeError(f"step {name} failed")

    class _FailStep:
        kind = "produce"
        prompt_key = ""
        slot = ""
        produces: tuple = ()
        consumes: tuple = ()

        def run(self, ctx: StepContext) -> StepResult:
            raise _exc

    s = _FailStep()
    s.__class__.__name__ = name
    return s


def _pipeline_one_step(step, stage_name: str = "s1") -> Pipeline:
    stage = Stage(name=stage_name, step=step, edges=[Edge(label="halt", target="halt", kind="normal")])
    return Pipeline(stages={stage_name: stage}, entry=stage_name)


def _pipeline_three_steps() -> Pipeline:
    s1 = Stage(
        name="s1",
        step=_make_step("s1_step", next_label="next"),
        edges=[Edge(label="next", target="s2", kind="normal")],
    )
    s2 = Stage(
        name="s2",
        step=_make_step("s2_step", next_label="next"),
        edges=[Edge(label="next", target="s3", kind="normal")],
    )
    s3 = Stage(
        name="s3",
        step=_make_step("s3_step", next_label="halt"),
        edges=[Edge(label="halt", target="halt", kind="normal")],
    )
    return Pipeline(stages={"s1": s1, "s2": s2, "s3": s3}, entry="s1")


def _ctx(plan_dir: Path) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={},
        profile=None,
        mode="run",
        inputs={},
        envelope=EMPTY_ENVELOPE,
    )


def _read_events(plan_dir: Path) -> list[dict]:
    ndjson = plan_dir / "events.ndjson"
    if not ndjson.exists():
        return []
    import json
    return [json.loads(line) for line in ndjson.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Tests: flag OFF (default)
# ---------------------------------------------------------------------------

def test_flag_off_no_activation_events(tmp_path):
    """With ACTIVATION_EMIT unset and MEGAPLAN_UNIFIED_DISPATCH unset, no events emitted."""
    env_keys = ["ACTIVATION_EMIT", "MEGAPLAN_UNIFIED_DISPATCH"]
    saved = {k: os.environ.pop(k, None) for k in env_keys}
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step"))
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert events == [], f"Expected no activation events, got {events}"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_flag_off_pipeline_still_succeeds(tmp_path):
    """Pipeline runs normally even when activation emit is off."""
    env_keys = ["ACTIVATION_EMIT", "MEGAPLAN_UNIFIED_DISPATCH"]
    saved = {k: os.environ.pop(k, None) for k in env_keys}
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step", state_patch={"x": 1}))
        result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        assert result["state"]["x"] == 1
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# Tests: flag ON via MEGAPLAN_UNIFIED_DISPATCH=1
# ---------------------------------------------------------------------------

def test_flag_on_emits_three_transitions_per_step(tmp_path):
    """PENDING→READY→RUNNING→SUCCEEDED = 3 ACTIVATION_TRANSITIONED events per step."""
    saved = os.environ.get("MEGAPLAN_UNIFIED_DISPATCH")
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step"))
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert len(events) == 3, f"Expected 3 events, got {len(events)}: {events}"
        transitions = [(e["payload"]["from"], e["payload"]["to"]) for e in events]
        assert transitions == [
            ("pending", "ready"),
            ("ready", "running"),
            ("running", "succeeded"),
        ]
    finally:
        if saved is None:
            os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
        else:
            os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = saved


def test_flag_on_events_carry_node_and_activation_id(tmp_path):
    """Events carry node name and a stable activation_id."""
    saved = os.environ.get("MEGAPLAN_UNIFIED_DISPATCH")
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step"), stage_name="my_stage")
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert all(e["payload"]["node"] == "my_stage" for e in events)
        act_ids = {e["payload"]["activation_id"] for e in events}
        assert len(act_ids) == 1, "All transitions for one step share the same activation_id"
        act_id = act_ids.pop()
        expected_id = compute_activation_id("my_stage", [], "")
        assert act_id == expected_id
    finally:
        if saved is None:
            os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
        else:
            os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = saved


def test_flag_on_three_steps_correct_event_count(tmp_path):
    """3 steps × 3 transitions each = 9 ACTIVATION_TRANSITIONED events."""
    saved = os.environ.get("MEGAPLAN_UNIFIED_DISPATCH")
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_three_steps()
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert len(events) == 9, f"Expected 9, got {len(events)}"
        # Each step has its own distinct activation_id
        ids_by_step: dict[str, set] = {}
        for e in events:
            n = e["payload"]["node"]
            ids_by_step.setdefault(n, set()).add(e["payload"]["activation_id"])
        assert set(ids_by_step.keys()) == {"s1", "s2", "s3"}
        for node_name, id_set in ids_by_step.items():
            assert len(id_set) == 1, f"Step {node_name} should have one activation_id"
        all_ids = {id_set.pop() for id_set in ids_by_step.values()}
        # All three steps should have distinct activation_ids (different node names)
        assert len(all_ids) == 3
    finally:
        if saved is None:
            os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
        else:
            os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = saved


def test_flag_on_failed_step_emits_failed_transition(tmp_path):
    """A step that raises emits RUNNING→FAILED transition."""
    saved = os.environ.get("MEGAPLAN_UNIFIED_DISPATCH")
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_failing_step("bad_step"))
        with pytest.raises(RuntimeError):
            run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        transitions = [(e["payload"]["from"], e["payload"]["to"]) for e in events]
        assert ("running", "failed") in transitions
        assert ("running", "succeeded") not in transitions
    finally:
        if saved is None:
            os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
        else:
            os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = saved


def test_activation_id_stable_across_calls(tmp_path):
    """compute_activation_id is deterministic; same args → same id across calls."""
    id1 = compute_activation_id("my_node", ["portA", "portB"], "production")
    id2 = compute_activation_id("my_node", ["portA", "portB"], "production")
    assert id1 == id2
    assert len(id1) == 16
    assert all(c in "0123456789abcdef" for c in id1)


def test_activation_id_differs_per_stage_name(tmp_path):
    """Different node names produce different activation_ids."""
    id1 = compute_activation_id("stage_a", [], "")
    id2 = compute_activation_id("stage_b", [], "")
    assert id1 != id2


def test_activation_emit_env_var_override(tmp_path):
    """ACTIVATION_EMIT=1 (own var) enables emission even with master unset."""
    for k in ["MEGAPLAN_UNIFIED_DISPATCH", "ACTIVATION_EMIT"]:
        os.environ.pop(k, None)
    os.environ["ACTIVATION_EMIT"] = "1"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step"))
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert len(events) == 3
    finally:
        os.environ.pop("ACTIVATION_EMIT", None)


def test_activation_emit_env_var_off_overrides_master(tmp_path):
    """ACTIVATION_EMIT=0 disables emission even when master MEGAPLAN_UNIFIED_DISPATCH=1."""
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    os.environ["ACTIVATION_EMIT"] = "0"
    try:
        from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
        pipeline = _pipeline_one_step(_make_step("s1_step"))
        run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path / "artifacts")
        events = [e for e in _read_events(tmp_path) if e["kind"] == "activation_transitioned"]
        assert events == []
    finally:
        os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
        os.environ.pop("ACTIVATION_EMIT", None)
