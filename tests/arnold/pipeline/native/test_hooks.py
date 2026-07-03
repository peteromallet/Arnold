"""Focused tests for native runtime hook defaults and subpipeline boundaries."""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline.native import compile_pipeline, phase, pipeline, run_native_pipeline, workflow
from arnold.pipeline.native.hooks import NativeRuntimeHooks, NullNativeRuntimeHooks


class _StepResult:
    def __init__(self, outputs: dict[str, Any], envelope: Any = None) -> None:
        self.outputs = outputs
        self.envelope = envelope


def test_null_hooks_implements_protocol() -> None:
    hooks = NullNativeRuntimeHooks()
    assert isinstance(hooks, NativeRuntimeHooks)


def test_null_hooks_default_methods_are_noops() -> None:
    hooks = NullNativeRuntimeHooks()
    state = {"x": 1}
    owned_keys = frozenset({"x"})

    merged_state, merged_owned = hooks.merge_state(
        instr=None,  # type: ignore[arg-type]
        state=state,
        outputs={"y": 2},
        owned_keys=owned_keys,
    )

    assert hooks.on_step_start(None, {"state": state}) == {"state": state}  # type: ignore[arg-type]
    assert hooks.on_step_end(None, {"state": state}, {"ok": True}) == {"ok": True}  # type: ignore[arg-type]
    assert merged_state is state
    assert merged_owned is owned_keys
    assert hooks.join_envelope(None, {"current": True}, None) == {"current": True}  # type: ignore[arg-type]
    assert hooks.join_envelope(None, {"current": True}, {"step": True}) == {"step": True}  # type: ignore[arg-type]
    assert hooks.should_suspend(None, state, {"ok": True}) == (False, None)  # type: ignore[arg-type]
    assert hooks.should_halt_loop(None, state, 3) == (False, None)  # type: ignore[arg-type]


def test_subpipeline_completion_flows_through_hook_merge_and_envelope() -> None:
    merge_calls: list[tuple[str, dict[str, Any]]] = []
    envelope_calls: list[tuple[str, Any, Any]] = []

    class RecordingHooks(NullNativeRuntimeHooks):
        def merge_state(self, instr, state, outputs, owned_keys):
            merge_calls.append((instr.op, dict(outputs)))
            return state, frozenset(set(owned_keys) | set(outputs))

        def join_envelope(self, instr, current_envelope, step_envelope):
            envelope_calls.append((instr.op, current_envelope, step_envelope))
            return step_envelope if step_envelope is not None else current_envelope

    @phase
    def child_step(ctx: dict) -> _StepResult:
        return _StepResult({"child": "done"}, envelope={"source": "child"})

    @workflow(
        name="child_flow",
        outputs={"type": "object", "required": ["child"]},
    )
    def child(ctx: dict) -> dict:
        state = yield child_step(ctx)
        return state

    @pipeline
    def parent(ctx: dict) -> dict:
        state = yield child(ctx)
        return state

    prog = compile_pipeline(parent)
    result = run_native_pipeline(prog, hooks=RecordingHooks())

    assert result.state["child"] == "done"
    assert result.envelope == {"source": "child"}
    assert ("subpipeline", {"child": "done"}) in merge_calls
    assert any(
        op == "subpipeline" and step_envelope == {"source": "child"}
        for op, _, step_envelope in envelope_calls
    )


def test_subpipeline_merge_conflict_propagates() -> None:
    class ConflictHooks(NullNativeRuntimeHooks):
        def merge_state(self, instr, state, outputs, owned_keys):
            if instr.op == "subpipeline":
                raise RuntimeError("subpipeline merge conflict")
            return state, owned_keys

    @phase
    def child_step(ctx: dict) -> dict:
        return {"child": "done"}

    @workflow(
        name="child_flow",
        outputs={"type": "object", "required": ["child"]},
    )
    def child(ctx: dict) -> dict:
        state = yield child_step(ctx)
        return state

    @pipeline
    def parent(ctx: dict) -> dict:
        state = yield child(ctx)
        return state

    prog = compile_pipeline(parent)

    with pytest.raises(RuntimeError, match="subpipeline merge conflict"):
        run_native_pipeline(prog, hooks=ConflictHooks())
