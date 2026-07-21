"""Focused tests for native runtime hook defaults and subpipeline boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.kernel.effect_ledger import EffectRecordState
from arnold.pipeline.native import compile_pipeline, phase, pipeline, run_native_pipeline, workflow
from arnold.pipeline.native.audit import AuditHooks
from arnold.pipeline.native.hooks import (
    EffectLedgerHooks,
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.checkpoint import read_native_cursor
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold.runtime.envelope import RunEnvelope
from arnold.workflow.native_wbc import native_wbc_dir


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


def test_effect_ledger_hooks_marks_side_effect_fulfilled() -> None:
    hooks = EffectLedgerHooks()

    @phase(operation="file_write", target="out/report.json", effect_class="filesystem_mutation")
    def write_report(ctx: dict) -> dict:
        return {"ok": True}

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield write_report(ctx)
        return state

    prog = compile_pipeline(my_pipe)
    run_native_pipeline(prog, hooks=hooks)

    instr = next(i for i in prog.instructions if i.name == "write_report")
    record = hooks._ledger.get_record(instr.idempotency_key or "")
    assert record is not None
    assert record.state is EffectRecordState.FULFILLED
    assert hooks.checkpoint_effect_metadata() == {
        "idempotency_key": instr.idempotency_key,
        "step_path": "root/write_report",
        "operation": "file_write",
        "target": "out/report.json",
        "attempt": 1,
        "lifecycle_state": "fulfilled",
        "effect_class": "filesystem_mutation",
        "duplicate_action": None,
    }


def test_effect_ledger_hooks_emit_wbc_effect_and_reconciliation_evidence(tmp_path: Path) -> None:
    hooks = EffectLedgerHooks(artifact_root=tmp_path, program_name="hook-demo")

    @phase(operation="file_write", target="out/report.json", effect_class="filesystem_mutation")
    def write_report(ctx: dict) -> dict:
        return {"attempt": ctx["attempt"]}

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield write_report(ctx)
        return state

    prog = compile_pipeline(my_pipe)
    run_native_pipeline(prog, hooks=hooks, artifact_root=tmp_path)
    run_native_pipeline(prog, hooks=hooks, artifact_root=tmp_path)

    path = native_wbc_dir(
        tmp_path,
        producer_family="arnold_native",
        surface="effect_ledger_hooks",
    ) / "events.ndjson"
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert "effect_intent" in [event["event"] for event in events]
    assert "effect_outcome" in [event["event"] for event in events]
    assert "reconciliation" in [event["event"] for event in events]
    assert all(event["authority"]["grants_authority"] is False for event in events)
    assert all(event["authority"]["leases_authority"] is False for event in events)


def test_effect_ledger_hooks_marks_side_effect_failed() -> None:
    hooks = EffectLedgerHooks()

    @phase(operation="git_commit", target="main", effect_class="git_repo_mutation")
    def commit_step(ctx: dict) -> dict:
        raise RuntimeError("boom")

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield commit_step(ctx)
        return state

    prog = compile_pipeline(my_pipe)

    with pytest.raises(RuntimeError, match="boom"):
        run_native_pipeline(prog, hooks=hooks)

    instr = next(i for i in prog.instructions if i.name == "commit_step")
    record = hooks._ledger.get_record(instr.idempotency_key or "")
    assert record is not None
    assert record.state is EffectRecordState.FAILED
    assert hooks.checkpoint_effect_metadata()["lifecycle_state"] == "failed"


def test_effect_ledger_hooks_duplicate_fulfilled_defaults_to_skip() -> None:
    hooks = EffectLedgerHooks()

    @phase(operation="file_write", target="out/report.json", effect_class="filesystem_mutation")
    def write_report(ctx: dict) -> dict:
        return {"attempt": ctx["attempt"]}

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield write_report(ctx)
        return state

    prog = compile_pipeline(my_pipe)
    run_native_pipeline(prog, hooks=hooks)
    run_native_pipeline(prog, hooks=hooks)

    effect = hooks.checkpoint_effect_metadata()
    assert effect is not None
    assert effect["duplicate_action"] == "skip"
    assert effect["lifecycle_state"] == "fulfilled"


def test_effect_ledger_hooks_duplicate_fulfilled_policy_is_configurable() -> None:
    hooks = EffectLedgerHooks(duplicate_fulfilled_action="fail")

    @phase(operation="git_commit", target="main", effect_class="git_repo_mutation")
    def commit_step(ctx: dict) -> dict:
        return {"ok": True}

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield commit_step(ctx)
        return state

    prog = compile_pipeline(my_pipe)
    run_native_pipeline(prog, hooks=hooks)
    run_native_pipeline(prog, hooks=hooks)

    effect = hooks.checkpoint_effect_metadata()
    assert effect is not None
    assert effect["duplicate_action"] == "fail"


def test_cancellation_propagates_through_wrapped_hook_chain_without_failure(
    tmp_path: Path,
) -> None:
    effect_hooks = EffectLedgerHooks()
    audit_dir = tmp_path / "audit"
    trace_dir = tmp_path / "trace"
    hooks = NativeTraceHooks(
        inner=AuditHooks(inner=effect_hooks, audit_dir=audit_dir),
        trace_dir=trace_dir,
        artifact_root=tmp_path / "artifacts",
    )

    @phase(operation="file_write", target="out/report.json", effect_class="filesystem_mutation")
    def write_report(ctx: dict) -> dict:
        raise AssertionError("phase body should not run after cancellation")

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield write_report(ctx)
        return state

    result = run_native_pipeline(
        compile_pipeline(my_pipe),
        artifact_root=tmp_path / "artifacts",
        hooks=hooks,
        initial_envelope=RunEnvelope(cancellation=True),
    )

    assert result.suspended is True
    assert effect_hooks.checkpoint_effect_metadata() is None

    records = [
        json.loads(line)
        for line in (audit_dir / "audit.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    step_records = [record for record in records if "attempt_id" in record]
    assert len(step_records) == 1
    assert step_records[0]["status"] == "cancelled"
    assert step_records[0]["step_path"] == "root/write_report"
    assert step_records[0]["error_type"] is None

    events = [
        json.loads(line)
        for line in (trace_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cancelled_events = [event for event in events if event["kind"] == "pipeline_cancelled"]
    assert len(cancelled_events) == 1
    assert cancelled_events[0]["payload"]["status"] == "cancelled"
    assert cancelled_events[0]["payload"]["trace"]["path"] == "root/write_report"


def test_effect_metadata_is_persisted_into_checkpoint(tmp_path) -> None:
    hooks = EffectLedgerHooks()

    @phase(operation="file_write", target="out/report.json", effect_class="filesystem_mutation")
    def write_report(ctx: dict) -> dict:
        return {"report": "ok"}

    @phase
    def pure_step(ctx: dict) -> dict:
        return {"done": True}

    @pipeline
    def my_pipe(ctx: dict) -> dict:
        state = yield write_report(ctx)
        state = yield pure_step(ctx)
        return state

    prog = compile_pipeline(my_pipe)
    result = run_native_pipeline(prog, hooks=hooks, artifact_root=tmp_path, max_phases=1)

    assert result.suspended is True
    cursor = read_native_cursor(tmp_path)
    assert cursor is not None
    assert cursor["effect"] == {
        "idempotency_key": next(i for i in prog.instructions if i.name == "write_report").idempotency_key,
        "step_path": "root/write_report",
        "operation": "file_write",
        "target": "out/report.json",
        "attempt": 1,
        "lifecycle_state": "fulfilled",
        "effect_class": "filesystem_mutation",
        "duplicate_action": None,
    }
