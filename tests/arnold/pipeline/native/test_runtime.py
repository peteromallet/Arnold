"""Tests for the native sequential runtime state machine.

Covers:
- Single-phase and multi-phase sequential execution
- State merging (dict return and object-with-outputs return)
- pc advancement and stage tracking
- max_phases suspension and resume parity
- Checkpoint persistence on max_phases stop
- Decision branching in the runtime
- While loop execution (guard + body + loop-back)
- Halt termination
- Control-override short-circuit (body skipped) vs additive-override (body called)
- Override application recording via body-call counters
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline.native import (
    NativeExecutionResult,
    NativeInstruction,
    NativeProgram,
    NativeRuntimeError,
    compile_pipeline,
    decision,
    parallel_map,
    parallel,
    phase,
    pipeline,
    project_graph,
    run_native_pipeline,
    workflow,
)
from arnold.pipeline.native.checkpoint import read_native_cursor
from arnold.pipeline.native.hooks import EffectLedgerHooks, NullNativeRuntimeHooks
from arnold.pipeline.native.ir import ParallelMapInstruction
from arnold.pipeline.types import ContractResult, ContractStatus, HumanSuspension, StepResult
from arnold.runtime.envelope import RunEnvelope


# ── module-level fixture ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the historical env var present for compatibility coverage."""
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


# ── helpers ───────────────────────────────────────────────────────────


def _make_program(
    name: str = "test_pipe",
    instructions: tuple[NativeInstruction, ...] = (),
) -> NativeProgram:
    return NativeProgram(name=name, instructions=instructions)


class _MemoryNativePersistenceBackend:
    def __init__(self) -> None:
        self.resume: dict[object, dict] = {}
        self.human_gate: dict[object, dict] = {}
        self.trace_artifacts: dict[tuple[object, str], object] = {}
        self.events: dict[object, list[dict]] = {}
        self.resume_writes: list[tuple[object, dict]] = []
        self.human_gate_writes: list[tuple[object, dict]] = []
        self.resume_deletes: list[object] = []
        self.human_gate_deletes: list[object] = []

    def write_resume_cursor(self, scope, *, payload):
        self.resume[scope] = dict(payload)
        self.resume_writes.append((scope, dict(payload)))
        return None

    def read_resume_cursor(self, scope):
        payload = self.resume.get(scope)
        return dict(payload) if payload is not None else None

    def delete_resume_cursor(self, scope) -> None:
        self.resume_deletes.append(scope)
        self.resume.pop(scope, None)

    def read_state_resume_cursor(self, scope):
        return None

    def write_composite_resume_cursor(self, scope, *, payload):
        return None

    def read_composite_resume_cursor(self, scope):
        return None

    def delete_composite_resume_cursor(self, scope) -> None:
        return None

    def write_human_gate(self, scope, *, payload):
        self.human_gate[scope] = dict(payload)
        self.human_gate_writes.append((scope, dict(payload)))
        return None

    def read_human_gate(self, scope):
        payload = self.human_gate.get(scope)
        return dict(payload) if payload is not None else None

    def delete_human_gate(self, scope) -> None:
        self.human_gate_deletes.append(scope)
        self.human_gate.pop(scope, None)

    def resolve_resume_surface(self, scope):
        raise NotImplementedError

    def append_audit_record(self, scope, *, payload):
        raise NotImplementedError

    def read_audit_records(self, scope):
        return []

    def emit_event(self, scope, *, kind, payload=None, phase=None, idempotency_key=None, event_scope=None):
        entries = self.events.setdefault(scope, [])
        event = {
            "seq": len(entries),
            "schema_version": 1,
            "kind": kind,
            "payload": dict(payload or {}),
        }
        if phase is not None:
            event["phase"] = phase
        if idempotency_key is not None:
            event["idempotency_key"] = idempotency_key
        if event_scope is not None:
            event["scope"] = event_scope
        entries.append(event)
        return type("Row", (), {"sequence": event["seq"], "payload": event, "kind": kind})()

    def read_events(self, scope, *, since_sequence=None, to_sequence=None, limit=None):
        rows = []
        for event in self.events.get(scope, []):
            seq = event["seq"]
            if since_sequence is not None and seq <= since_sequence:
                continue
            if to_sequence is not None and seq >= to_sequence:
                continue
            rows.append(type("Row", (), {"sequence": seq, "payload": dict(event), "kind": event["kind"]})())
            if limit is not None and len(rows) >= limit:
                break
        return rows

    def write_trace_artifact(self, scope, *, name, payload):
        if isinstance(payload, dict):
            stored = dict(payload)
        elif isinstance(payload, list):
            stored = list(payload)
        else:
            stored = payload
        self.trace_artifacts[(scope, name)] = stored
        return None

    def read_trace_artifact(self, scope, *, name):
        payload = self.trace_artifacts.get((scope, name))
        if isinstance(payload, dict):
            return dict(payload)
        if isinstance(payload, list):
            return list(payload)
        return payload


# ── sequential execution ──────────────────────────────────────────────


class TestSequentialExecution:
    """Sequential phase execution with state merging."""

    def test_single_phase(self) -> None:
        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"result": 42}
        assert len(result.stages) == 1
        assert result.stages[0].endswith("__do_work__pc0")
        assert not result.suspended

    def test_two_phases_state_merge(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step_a(ctx)
            state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"a": 1, "b": 2}
        assert len(result.stages) == 2
        assert "step_a" in result.stages[0]
        assert "step_b" in result.stages[1]
        assert not result.suspended

    def test_three_phases(self) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"x": 1, "y": 2, "z": 3}
        assert len(result.stages) == 3

    def test_phase_context_exposes_root_run_and_step_paths(self) -> None:
        seen: dict[str, object] = {}

        @phase
        def inspect(ctx: dict) -> dict:
            seen["run_path"] = ctx["run_path"]
            seen["step_path"] = ctx["step_path"]
            seen["call_site_path"] = ctx["call_site_path"]
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield inspect(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)

        assert result.state["ok"] is True
        assert seen == {
            "run_path": "root",
            "step_path": "root/inspect",
            "call_site_path": (),
        }

    def test_state_accumulates_across_phases(self) -> None:
        @phase
        def first(ctx: dict) -> dict:
            return {"count": 1}

        @phase
        def second(ctx: dict) -> dict:
            current = ctx["state"].get("count", 0)
            return {"count": current + 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield first(ctx)
            s = yield second(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state["count"] == 2

    def test_phase_receives_accumulated_state(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"key": "hello"}

        @phase
        def step_b(ctx: dict) -> dict:
            # step_b should see step_a's output in state
            prev = ctx["state"].get("key", "missing")
            return {"key": prev + "_world"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state["key"] == "hello_world"

    def test_initial_state_provided(self) -> None:
        @phase
        def step(ctx: dict) -> dict:
            base = ctx["state"].get("base", 0)
            return {"result": base + 10}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, initial_state={"base": 5})
        assert result.state == {"base": 5, "result": 15}

    def test_empty_program(self) -> None:
        prog = NativeProgram(name="empty")
        result = run_native_pipeline(prog)
        assert result.state == {}
        assert result.stages == []
        assert result.pc == 0

    def test_context_has_artifact_root(self) -> None:
        captured_root = None

        @phase
        def step(ctx: dict) -> dict:
            nonlocal captured_root
            captured_root = ctx.get("artifact_root")
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root="/tmp/test_root")
        assert captured_root == "/tmp/test_root"


# ── pc and stage tracking ─────────────────────────────────────────────


class TestPcAndStageTracking:
    """pc advances correctly and stages are recorded after completion."""

    def test_pc_is_tracked(self) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {}

        @phase
        def b(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        # After completion, pc should be at the halt instruction
        halt_instrs = [i for i in prog.instructions if i.op == "halt"]
        if halt_instrs:
            assert result.pc == halt_instrs[0].pc
        assert not result.suspended

    def test_subpipeline_instruction_executes_child_program(self) -> None:
        @phase
        def child_step(ctx: dict) -> dict:
            seed = ctx["state"]["seed"]
            current = ctx["state"].get("visits", 0)
            return {
                "seed": "child-only",
                "visits": current + 1,
                "child": f"{seed}-done",
                "hidden": "ignored",
            }

        @workflow(
            name="child_flow",
            id="workflow.child",
            inputs={"type": "object", "required": ["seed", "visits"]},
            outputs={"type": "object", "required": ["child", "visits"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @phase
        def parent_step(ctx: dict) -> dict:
            return {"parent": ctx["state"]["child"], "visits": ctx["state"]["visits"] + 1}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx)
            state = yield parent_step(ctx)
            return state

        prog = compile_pipeline(parent)
        subpipeline_instr = prog.instructions[0]
        assert subpipeline_instr.op == "subpipeline"
        assert subpipeline_instr.subprogram is not None
        assert subpipeline_instr.subprogram.stable_id == "workflow.child"
        result = run_native_pipeline(prog, initial_state={"seed": "s1", "visits": 1, "ambient": "keep"})
        assert result.state == {
            "seed": "s1",
            "visits": 3,
            "ambient": "keep",
            "child": "s1-done",
            "parent": "s1-done",
        }
        assert result.stages == ["parent__parent_step__pc1"]
        assert not result.suspended

    def test_subpipeline_uses_isolated_child_artifact_root(
        self, tmp_path: Path
    ) -> None:
        captured_child_root: Path | None = None

        @phase
        def child_step(ctx: dict) -> dict:
            nonlocal captured_child_root
            captured_child_root = Path(ctx["artifact_root"])
            marker = captured_child_root / "child.txt"
            marker.write_text("child", encoding="utf-8")
            return {"child_root_name": captured_child_root.name}

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child_root_name"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog, artifact_root=tmp_path)

        assert captured_child_root == tmp_path / "_child_child_flow"
        assert result.state["child_root_name"] == "_child_child_flow"
        assert (tmp_path / "_child_child_flow" / "child.txt").read_text(
            encoding="utf-8"
        ) == "child"
        assert not (tmp_path / "child.txt").exists()

    def test_subpipeline_only_merges_declared_outputs(self) -> None:
        @phase
        def child_step(ctx: dict) -> dict:
            return {"child": "done", "secret": "nope"}

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
        result = run_native_pipeline(prog, initial_state={"ambient": "keep"})

        assert result.state == {"ambient": "keep", "child": "done"}

    def test_subpipeline_explicit_output_bindings_rename_child_outputs(self) -> None:
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
            state = yield child(ctx, outputs={"child": "child_status"})
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog)

        assert result.state == {"child_status": "done"}

    def test_subpipeline_context_composes_child_run_path(self) -> None:
        seen: dict[str, object] = {}

        @phase
        def child_step(ctx: dict) -> dict:
            seen["run_path"] = ctx["run_path"]
            seen["step_path"] = ctx["step_path"]
            seen["call_site_path"] = ctx["call_site_path"]
            return {"child": "done"}

        @workflow(
            name="child_flow",
            inputs={"type": "object"},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog)

        assert result.state == {"child": "done"}
        assert seen == {
            "run_path": "root/child_call",
            "step_path": "root/child_call/child_step",
            "call_site_path": ("child_call",),
        }

    def test_subpipeline_writes_composite_parent_cursor_before_child_entry(
        self,
        tmp_path: Path,
    ) -> None:
        observed: dict[str, object] = {}

        @phase
        def child_step(ctx: dict) -> dict:
            observed["child_root"] = ctx["artifact_root"]
            observed["cursor"] = read_native_cursor(tmp_path)
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
            state = yield child(ctx, id="child_call")
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog, artifact_root=tmp_path)

        assert result.state["child"] == "done"
        cursor = observed["cursor"]
        assert isinstance(cursor, dict)
        assert cursor["native_cursor_kind"] == "composite_parent_child"
        assert cursor["native"]["pc"] == 0
        assert cursor["composite"]["parent"]["pc"] == 0
        assert cursor["composite"]["parent"]["run_path"] == "root"
        assert cursor["composite"]["parent"]["state"] == {}
        assert cursor["composite"]["child"] == {
            "cursor_path": "_child_child_call/resume_cursor.json",
            "run_path": "root/child_call",
            "call_site_path": ("child_call",),
        }
        assert observed["child_root"] == str(tmp_path / "_child_child_call")

    def test_subpipeline_composite_cursor_uses_injected_persistence_backend(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import Suspension

        backend = _MemoryNativePersistenceBackend()
        calls = {"child": 0}

        @phase
        def child_step(ctx: dict) -> StepResult | dict:
            calls["child"] += 1
            if calls["child"] == 1:
                return StepResult(
                    outputs={"waiting": True},
                    contract_result=ContractResult(
                        status=ContractStatus.SUSPENDED,
                        suspension=Suspension(
                            kind="human",
                            resume_cursor="child-review",
                        ),
                    ),
                )
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
            state = yield child(ctx, id="child_call")
            return state

        prog = compile_pipeline(parent)
        first = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            persistence_backend=backend,
        )
        assert first.suspended is True
        assert not (tmp_path / "resume_cursor.json").exists()

        parent_scope, parent_cursor = backend.resume_writes[-1]
        assert parent_cursor["composite"]["kind"] == "parent_child"
        assert parent_cursor["native"]["suspension_kind"] == "child_suspended"

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            persistence_backend=backend,
        )
        assert resumed.suspended is False
        assert resumed.state["child"] == "done"
        assert parent_scope in backend.resume_deletes
        assert parent_scope not in backend.resume

    def test_repeated_subpipeline_call_sites_have_distinct_child_cursor_paths(
        self,
        tmp_path: Path,
    ) -> None:
        observed_paths: list[str] = []
        observed_roots: list[str] = []

        @phase
        def child_step(ctx: dict) -> dict:
            cursor = read_native_cursor(tmp_path)
            assert cursor is not None
            observed_paths.append(cursor["composite"]["child"]["cursor_path"])
            observed_roots.append(ctx["artifact_root"])
            return {"child": ctx["call_site_path"][0]}

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_a", outputs={"child": "a"})
            state = yield child(ctx, id="child_b", outputs={"child": "b"})
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog, artifact_root=tmp_path)

        assert result.state["a"] == "child_a"
        assert result.state["b"] == "child_b"
        assert observed_paths == [
            "_child_child_a/resume_cursor.json",
            "_child_child_b/resume_cursor.json",
        ]
        assert observed_roots == [
            str(tmp_path / "_child_child_a"),
            str(tmp_path / "_child_child_b"),
        ]

    def test_subpipeline_child_suspension_returns_suspended_parent_without_merging_outputs(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        captured: list[tuple[dict, dict]] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append((dict(cursor), dict(state)))

        @phase
        def child_step(ctx: dict) -> StepResult:
            return StepResult(
                outputs={"child": ctx["state"].get("seed", "missing")},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        resume_cursor="child-review",
                    ),
                ),
            )

        @workflow(
            name="child_flow",
            inputs={"type": "object", "required": ["seed"]},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline(inputs={"type": "object", "required": ["seed"]})
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call", outputs={"child": "merged_child"})
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_state={"seed": "ready"},
            hooks=RecordingHooks(),
        )

        assert result.suspended is True
        assert result.state == {"seed": "ready"}
        assert "merged_child" not in result.state

        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["native"]["suspension_kind"] == "child_suspended"
        assert cursor["suspension_kind"] == "child_suspended"
        assert cursor["composite"]["child"]["cursor_path"] == "_child_child_call/resume_cursor.json"

        parent_suspensions = [
            (checkpoint_cursor, checkpoint_state)
            for checkpoint_cursor, checkpoint_state in captured
            if checkpoint_cursor.get("native", {}).get("suspension_kind") == "child_suspended"
        ]
        assert len(parent_suspensions) == 1
        assert parent_suspensions[0][1] == {"seed": "ready"}

    def test_composite_cursor_resume_restores_parent_and_child_once(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        calls = {
            "parent_start": 0,
            "child_prepare": 0,
            "child_wait": 0,
            "parent_finish": 0,
        }
        allow_child_complete = {"value": False}

        @phase
        def parent_start(ctx: dict) -> dict:
            calls["parent_start"] += 1
            return {"parent_ready": True}

        @phase
        def child_prepare(ctx: dict) -> dict:
            calls["child_prepare"] += 1
            return {"prepared": ctx["state"]["seed"]}

        @phase
        def child_wait(ctx: dict) -> StepResult | dict:
            calls["child_wait"] += 1
            if allow_child_complete["value"]:
                return {"child": f"done:{ctx['state']['prepared']}"}
            return StepResult(
                outputs={"wait_seen": calls["child_wait"]},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        resume_cursor=f"child-review-{calls['child_wait']}",
                    ),
                ),
            )

        @phase
        def parent_finish(ctx: dict) -> dict:
            calls["parent_finish"] += 1
            return {"finished": ctx["state"]["merged_child"]}

        @workflow(
            name="child_flow",
            inputs={
                "type": "object",
                "properties": {
                    "seed": {"type": "string"},
                    "approved": {"type": "boolean"},
                },
                "required": ["seed"],
            },
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_prepare(ctx)
            state = yield child_wait(ctx)
            return state

        @pipeline(
            inputs={
                "type": "object",
                "properties": {
                    "seed": {"type": "string"},
                    "approved": {"type": "boolean"},
                },
                "required": ["seed"],
            }
        )
        def parent(ctx: dict) -> dict:
            state = yield parent_start(ctx)
            state = yield child(ctx, id="child_call", outputs={"child": "merged_child"})
            state = yield parent_finish(ctx)
            return state

        prog = compile_pipeline(parent)

        first = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_state={"seed": "alpha"},
        )
        assert first.suspended is True
        assert calls == {
            "parent_start": 1,
            "child_prepare": 1,
            "child_wait": 1,
            "parent_finish": 0,
        }

        second = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_state={"seed": "alpha"},
            resume=True,
        )
        assert second.suspended is True
        assert calls == {
            "parent_start": 1,
            "child_prepare": 1,
            "child_wait": 2,
            "parent_finish": 0,
        }
        parent_cursor = json.loads(
            (tmp_path / "resume_cursor.json").read_text(encoding="utf-8")
        )
        child_cursor = json.loads(
            (tmp_path / "_child_child_call" / "resume_cursor.json").read_text(
                encoding="utf-8"
            )
        )
        assert parent_cursor["native"]["suspension_kind"] == "child_suspended"
        assert child_cursor["resume_cursor"] == "child-review-2"

        allow_child_complete["value"] = True
        final = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_state={"seed": "alpha"},
            resume=True,
        )

        assert final.suspended is False
        assert final.state["finished"] == "done:alpha"
        assert calls == {
            "parent_start": 1,
            "child_prepare": 1,
            "child_wait": 3,
            "parent_finish": 1,
        }
        assert not (tmp_path / "resume_cursor.json").exists()

    def test_parallel_map_uses_parameter_precedence_and_preserves_item_order(self) -> None:
        seen_ids: list[str] = []

        @phase
        def mutate_checks(ctx: dict) -> dict:
            return {"checks": [{"item_id": "later"}, {"item_id": "first"}]}

        @phase
        def mapper(ctx: dict) -> dict:
            seen_ids.append(ctx["state"]["item_id"])
            return {"item_id": ctx["state"]["item_id"]}

        @pipeline(inputs={"type": "object", "required": ["checks"]})
        def parent(ctx: dict) -> dict:
            state = yield mutate_checks(ctx)
            state = yield parallel_map(items="checks", step=mapper, name="batch")
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(
            prog,
            initial_state={"checks": [{"item_id": "first"}, {"item_id": "later"}]},
        )

        assert seen_ids == ["first", "later"]
        assert result.state["batch"] == [
            {"item_id": "first"},
            {"item_id": "later"},
        ]

    def test_parallel_map_reducer_receives_ordered_results_and_item_paths(self) -> None:
        reducer_inputs: list[list[dict[str, str]]] = []

        @phase
        def mapper(ctx: dict) -> dict:
            return {
                "item_id": ctx["state"]["item_id"],
                "path": "/".join(ctx["call_site_path"]),
                "run_path": ctx["run_path"],
                "step_path": ctx["step_path"],
            }

        def reduce_paths(results: list[dict[str, str]]) -> dict:
            reducer_inputs.append(results)
            return {"paths": [result["path"] for result in results]}

        @pipeline(inputs={"type": "object", "required": ["checks"]})
        def parent(ctx: dict) -> dict:
            state = yield parallel_map(
                items="checks",
                step=mapper,
                reducer=reduce_paths,
                path_template="critique/{item_id}",
                name="critique_batch",
            )
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(
            prog,
            initial_state={"checks": [{"item_id": "a"}, {"item_id": "b"}]},
        )

        assert reducer_inputs == [[
            {
                "item_id": "a",
                "path": "critique_batch/critique/a",
                "run_path": "root/critique_batch/critique/a",
                "step_path": "root/critique_batch/critique/a/mapper",
            },
            {
                "item_id": "b",
                "path": "critique_batch/critique/b",
                "run_path": "root/critique_batch/critique/b",
                "step_path": "root/critique_batch/critique/b/mapper",
            },
        ]]
        assert result.state["paths"] == [
            "critique_batch/critique/a",
            "critique_batch/critique/b",
        ]

    def test_parallel_map_workflow_mapper_collects_declared_outputs_only(self) -> None:
        def reduce_children(results: list[dict[str, str]]) -> dict:
            return {"children": results}

        @phase
        def child_step(ctx: dict) -> dict:
            return {
                "child": ctx["state"]["item_id"],
                "hidden": "ignore-me",
            }

        @workflow(
            name="child_flow",
            inputs={"type": "object", "required": ["item_id"]},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline(inputs={"type": "object", "required": ["checks"]})
        def parent(ctx: dict) -> dict:
            state = yield parallel_map(
                items="checks",
                step=child,
                reducer=reduce_children,
                name="batch",
            )
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(
            prog,
            initial_state={"checks": [{"item_id": "x"}, {"item_id": "y"}]},
        )

        assert result.state["children"] == [
            {"child": "x"},
            {"child": "y"},
        ]

    def test_parallel_map_compiled_child_suspension_returns_suspended_parent_without_merging_outputs(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        captured: list[tuple[dict, dict]] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append((dict(cursor), dict(state)))

        @phase
        def child_step(ctx: dict) -> StepResult:
            item_id = ctx["state"]["item_id"]
            return StepResult(
                outputs={"child": item_id},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        resume_cursor=f"child-review-{item_id}",
                    ),
                ),
            )

        @workflow(
            name="child_flow",
            inputs={"type": "object", "required": ["item_id"]},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        def reduce_children(results: list[dict[str, str]]) -> dict:
            return {"children": results}

        @pipeline(inputs={"type": "object", "required": ["checks"]})
        def parent(ctx: dict) -> dict:
            state = yield parallel_map(
                items="checks",
                path_template="{item_id}",
                step=child,
                reducer=reduce_children,
                name="batch",
            )
            return state

        prog = compile_pipeline(parent)
        initial_state = {"checks": [{"item_id": "x"}, {"item_id": "y"}], "seed": "ready"}
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_state=initial_state,
            hooks=RecordingHooks(),
        )

        assert result.suspended is True
        assert result.state == initial_state
        assert "children" not in result.state
        assert "child" not in result.state

        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["native"]["suspension_kind"] == "child_suspended"
        assert cursor["suspension_kind"] == "child_suspended"
        assert cursor["composite"]["child"]["cursor_path"] == "_child_child_flow/x/resume_cursor.json"
        assert cursor["composite"]["child"]["run_path"] == "root/batch/x"

        parent_suspensions = [
            (checkpoint_cursor, checkpoint_state)
            for checkpoint_cursor, checkpoint_state in captured
            if checkpoint_cursor.get("native", {}).get("suspension_kind") == "child_suspended"
        ]
        assert len(parent_suspensions) == 1
        assert parent_suspensions[0][1] == initial_state

    def test_parallel_map_empty_collection_invokes_reducer_with_empty_results(self) -> None:
        reducer_calls: list[list[dict[str, str]]] = []
        mapper_calls: list[str] = []

        @phase
        def mapper(ctx: dict) -> dict:
            mapper_calls.append("called")
            return {"item_id": "unexpected"}

        def reduce_empty(results: list[dict[str, str]]) -> dict:
            reducer_calls.append(results)
            return {"count": len(results)}

        @pipeline(inputs={"type": "object", "required": ["checks"]})
        def parent(ctx: dict) -> dict:
            state = yield parallel_map(
                items="checks",
                step=mapper,
                reducer=reduce_empty,
                name="batch",
            )
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog, initial_state={"checks": []})

        assert mapper_calls == []
        assert reducer_calls == [[]]
        assert result.state["count"] == 0

    def test_stages_have_correct_format(self) -> None:
        @phase
        def my_phase(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield my_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert len(result.stages) == 1
        assert result.stages[0].startswith("my_pipe__my_phase__pc")

    def test_stages_not_recorded_before_completion(self) -> None:
        """If a phase raises, stages should not include it."""
        @phase
        def good(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def bad(ctx: dict) -> dict:
            raise RuntimeError("fail")

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield good(ctx)
            s = yield bad(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        with pytest.raises(RuntimeError, match="fail"):
            run_native_pipeline(prog)
        # The exception prevents the function from returning, so we can't
        # check result.stages directly. This test documents the expectation
        # that exceptions propagate to the caller.


# ── max_phases and resume ─────────────────────────────────────────────


class TestMaxPhasesAndResume:
    """max_phases stops after N phases and persists a resume cursor."""

    def test_max_phases_stops_after_n(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result.suspended
        assert result.cursor_path is not None
        assert len(result.stages) == 1
        assert result.state == {"x": 1}

    def test_max_phases_persists_cursor(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result.suspended

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["pc"] == result.pc
        assert len(cursor["stages"]) == 1

    def test_max_phases_uses_injected_persistence_backend(self, tmp_path: Path) -> None:
        backend = _MemoryNativePersistenceBackend()

        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": ctx["state"]["x"] + 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        first = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            max_phases=1,
            persistence_backend=backend,
        )
        assert first.suspended is True
        assert not (tmp_path / "resume_cursor.json").exists()
        assert backend.resume_writes[-1][1]["native"]["pc"] == 1

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            persistence_backend=backend,
        )
        assert resumed.suspended is False
        assert resumed.state == {"x": 1, "y": 2}

    def test_resume_from_max_phases(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Run with max_phases=1 → should suspend after phase a
        result1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result1.suspended
        assert result1.state == {"x": 1}

        # Resume → should continue from phase b
        result2 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert not result2.suspended
        assert result2.state == {"x": 1, "y": 2, "z": 3}
        assert len(result2.stages) == 3  # a (from cursor) + b + c

    def test_full_vs_resumed_parity(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Full run
        full = run_native_pipeline(prog)

        # Resumed run: stop after 1, then resume
        run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        resumed = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)

        # State parity
        assert resumed.state == full.state

        # Stage parity (the full run has stages from one continuous run;
        # the resumed run carries stages accumulated across both runs)
        assert len(resumed.stages) == len(full.stages)

    def test_resume_with_no_cursor_runs_from_start(self) -> None:
        @phase
        def step(ctx: dict) -> dict:
            return {"result": "done"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        # resume=True with no cursor file → starts from pc=0
        result = run_native_pipeline(prog, resume=True)
        assert result.state == {"result": "done"}

    def test_resume_with_corrupt_cursor_fails_closed(self, tmp_path: Path) -> None:
        @phase
        def step(ctx: dict) -> dict:
            return {"result": "done"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        (tmp_path / "resume_cursor.json").write_text("{", encoding="utf-8")

        prog = compile_pipeline(my_pipe)
        with pytest.raises(NativeRuntimeError, match="Cannot resume native pipeline"):
            run_native_pipeline(prog, artifact_root=tmp_path, resume=True)

    def test_max_phases_multiple_suspensions(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"c": 3}

        @phase
        def d(ctx: dict) -> dict:
            return {"d": 4}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            s = yield d(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Stop after phase a
        r1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert r1.suspended
        assert r1.state == {"a": 1}

        # Resume, stop after phase b (1 more phase)
        r2 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, resume=True)
        assert r2.suspended
        assert r2.state == {"a": 1, "b": 2}

        # Resume, run to completion
        r3 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert not r3.suspended
        assert r3.state == {"a": 1, "b": 2, "c": 3, "d": 4}
        assert len(r3.stages) == 4

    def test_resumed_traced_run_seeds_stage_sequence_from_cursor(
        self, tmp_path: Path
    ) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            state = yield c(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        trace_dir = tmp_path / "trace"

        first = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            max_phases=1,
            trace_dir=trace_dir,
        )
        assert first.suspended is True
        assert json.loads((trace_dir / "stages.json").read_text(encoding="utf-8")) == [
            "a__pc0"
        ]

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            trace_dir=trace_dir,
        )

        assert resumed.suspended is False
        assert resumed.stages == [
            "my_pipe__a__pc0",
            "my_pipe__b__pc1",
            "my_pipe__c__pc2",
        ]
        assert json.loads((trace_dir / "stages.json").read_text(encoding="utf-8")) == [
            "a__pc0",
            "b__pc1",
            "c__pc2",
        ]
        checkpoint = json.loads(
            (trace_dir / "checkpoint.json").read_text(encoding="utf-8")
        )
        assert checkpoint["stage_sequence"] == ["a__pc0", "b__pc1", "c__pc2"]
        assert checkpoint["cursor_stage"] == "my_pipe__c__pc2"

    def test_fresh_traced_run_keeps_existing_short_stage_sequence(
        self, tmp_path: Path
    ) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        trace_dir = tmp_path / "trace"

        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            trace_dir=trace_dir,
        )

        assert result.suspended is False
        assert result.stages == ["my_pipe__a__pc0", "my_pipe__b__pc1"]
        assert json.loads((trace_dir / "stages.json").read_text(encoding="utf-8")) == [
            "a__pc0",
            "b__pc1",
        ]

    def test_traced_subpipeline_emits_tree_metadata_while_stages_stay_flat(
        self, tmp_path: Path
    ) -> None:
        @phase
        def child_step(ctx: dict) -> dict:
            return {"child": True}

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield after(ctx)
            return state

        trace_dir = tmp_path / "trace"
        result = run_native_pipeline(
            compile_pipeline(parent),
            artifact_root=tmp_path,
            trace_dir=trace_dir,
        )

        assert result.suspended is False
        stages = json.loads((trace_dir / "stages.json").read_text(encoding="utf-8"))
        assert stages == ["child_step__pc0", "after__pc1"]
        assert all(isinstance(stage, str) for stage in stages)

        tree = json.loads((trace_dir / "tree.json").read_text(encoding="utf-8"))
        nodes = {node["path"]: node for node in tree["nodes"]}
        assert nodes["root"]["kind"] == "pipeline"
        assert nodes["root"]["children"] == ["root/child_call", "root/after"]
        assert nodes["root/child_call"]["kind"] == "subpipeline"
        assert nodes["root/child_call"]["parent_path"] == "root"
        assert nodes["root/child_call/child_step"]["kind"] == "phase"
        assert nodes["root/child_call/child_step"]["parent_path"] == "root/child_call"
        assert nodes["root/after"]["kind"] == "phase"
        assert nodes["root/after"]["parent_path"] == "root"

    def test_traced_parallel_map_phase_mapper_emits_item_tree_metadata(
        self, tmp_path: Path
    ) -> None:
        @phase
        def mapper(ctx: dict) -> dict:
            return {"value": ctx["item"]["id"]}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield parallel_map(
                items="items",
                step=mapper,
                name="critique_batch",
                path_template="critique/{id}",
            )
            return state

        trace_dir = tmp_path / "trace"
        result = run_native_pipeline(
            compile_pipeline(parent),
            artifact_root=tmp_path,
            initial_state={"items": [{"id": "a"}, {"id": "b"}]},
            trace_dir=trace_dir,
        )

        assert result.suspended is False
        stages = json.loads((trace_dir / "stages.json").read_text(encoding="utf-8"))
        assert len(stages) == 2
        assert all(isinstance(stage, str) for stage in stages)

        tree = json.loads((trace_dir / "tree.json").read_text(encoding="utf-8"))
        nodes = {node["path"]: node for node in tree["nodes"]}
        assert nodes["root/critique_batch"]["kind"] == "parallel_map"
        assert "root/critique_batch/critique" in nodes["root/critique_batch"]["children"]
        assert nodes["root/critique_batch/critique"]["children"] == [
            "root/critique_batch/critique/a",
            "root/critique_batch/critique/b",
        ]
        assert nodes["root/critique_batch/critique/a/mapper"]["parent_path"] == "root/critique_batch/critique/a"
        assert nodes["root/critique_batch/critique/b/mapper"]["parent_path"] == "root/critique_batch/critique/b"

    def test_traced_resume_and_child_suspension_emit_path_addressed_events(
        self, tmp_path: Path
    ) -> None:
        @phase
        def child_step(ctx: dict) -> StepResult:
            if ctx["state"].get("resume_child"):
                return StepResult(outputs={"child": "resumed"})
            return StepResult(
                outputs={"resume_child": True},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=HumanSuspension(
                        kind="human",
                        resume_cursor=json.dumps({"phase": "child_step"}),
                    ),
                ),
            )

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @phase
        def parent_after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield parent_after(ctx)
            return state

        trace_dir = tmp_path / "trace"
        first = run_native_pipeline(
            compile_pipeline(parent),
            artifact_root=tmp_path,
            trace_dir=trace_dir,
        )
        assert first.suspended is True

        resumed = run_native_pipeline(
            compile_pipeline(parent),
            artifact_root=tmp_path,
            trace_dir=trace_dir,
            resume=True,
        )
        assert resumed.suspended is False

        events = [
            json.loads(line)
            for line in (trace_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        suspended_events = [event for event in events if event["kind"] == "pipeline_suspended"]
        resumed_events = [event for event in events if event["kind"] == "pipeline_resumed"]
        assert suspended_events[-1]["payload"]["reason"] == "child_suspended"
        assert suspended_events[-1]["payload"]["trace"]["path"] == "root/child_flow"
        assert resumed_events[-1]["payload"]["reason"] in {"child_suspended", "native_resume"}
        assert resumed_events[-1]["payload"]["trace"]["path"] in {
            "root/child_flow",
            "root/child_call/child_step",
        }

        checkpoint = json.loads((trace_dir / "checkpoint.json").read_text(encoding="utf-8"))
        assert checkpoint["tree_file"] == "tree.json"
        tree = json.loads((trace_dir / "tree.json").read_text(encoding="utf-8"))
        nodes = {node["path"]: node for node in tree["nodes"]}
        assert nodes["root/child_call"]["kind"] == "subpipeline"

    def test_trace_dir_compatibility_uses_injected_backend_for_trace_artifacts(
        self, tmp_path: Path
    ) -> None:
        backend = _MemoryNativePersistenceBackend()

        @phase
        def write(ctx: dict) -> dict:
            Path(ctx["artifact_root"], "artifact.txt").write_text("ok", encoding="utf-8")
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield write(ctx)
            return state

        trace_dir = tmp_path / "trace"
        result = run_native_pipeline(
            compile_pipeline(my_pipe),
            artifact_root=tmp_path,
            trace_dir=trace_dir,
            persistence_backend=backend,
        )

        assert result.suspended is False
        trace_keys = {name for (_, name) in backend.trace_artifacts}
        assert {"state.json", "stages.json", "tree.json", "artifacts.json", "checkpoint.json"} <= trace_keys
        events = next(iter(backend.events.values()))
        assert events[0]["kind"] == "pipeline.init"
        assert any(event["kind"] == "checkpoint" for event in events)


class TestCancellationBoundarySentinel:
    def test_noop_cancellation_boundary_is_observable_without_changing_execution(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        observed: list[dict[str, object]] = []

        def record_boundary(**payload: object) -> None:
            observed.append(dict(payload))

        monkeypatch.setattr(
            "arnold.pipeline.native.runtime._check_cancellation_boundary",
            record_boundary,
        )

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

        @phase
        def parent_step(ctx: dict) -> dict:
            return {"parent": True}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield parent_step(ctx)
            state = yield child(ctx, id="child_call")
            return state

        result = run_native_pipeline(
            compile_pipeline(parent),
            artifact_root=tmp_path,
            initial_envelope=RunEnvelope(cancellation=True),
        )

        assert result.suspended is False
        assert result.state == {"parent": True, "child": "done"}
        assert [entry["boundary"] for entry in observed] == [
            "step_enter",
            "step_exit",
            "child_enter",
            "step_enter",
            "step_exit",
            "child_exit",
        ]
        assert all(entry["envelope"].cancellation is True for entry in observed)


# ── decision branching ────────────────────────────────────────────────


class TestDecisionBranching:
    """The runtime correctly follows decision branches."""

    def test_decision_takes_then_branch(self) -> None:
        @phase
        def then_phase(ctx: dict) -> dict:
            return {"branch": "then"}

        @phase
        def else_phase(ctx: dict) -> dict:
            return {"branch": "else"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield then_phase(ctx)
            else:
                s = yield else_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("branch") == "then"

    def test_decision_takes_else_branch(self) -> None:
        @phase
        def then_phase(ctx: dict) -> dict:
            return {"branch": "then"}

        @phase
        def else_phase(ctx: dict) -> dict:
            return {"branch": "else"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield then_phase(ctx)
            else:
                s = yield else_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("branch") == "else"

    def test_decision_returns_string_label(self) -> None:
        @phase
        def left_phase(ctx: dict) -> dict:
            return {"side": "left"}

        @phase
        def right_phase(ctx: dict) -> dict:
            return {"side": "right"}

        @decision(vocabulary={"left", "right"})
        def branch(ctx: dict) -> str:
            return "right"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if branch(ctx) == "left":
                s = yield left_phase(ctx)
            else:
                s = yield right_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("side") == "right"

    def test_decision_no_else_passes_through(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"before": True}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"after": True}

        @decision(vocabulary={"pass", "fail"})
        def check(ctx: dict) -> str:
            return "fail"  # skip the then-branch

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            if check(ctx) == "pass":
                s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"before": True}
        assert "after" not in result.state

    def test_decision_before_first_phase(self) -> None:
        @phase
        def yes_phase(ctx: dict) -> dict:
            return {"path": "yes"}

        @phase
        def no_phase(ctx: dict) -> dict:
            return {"path": "no"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield yes_phase(ctx)
            else:
                s = yield no_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("path") == "no"


# ── while loop execution ──────────────────────────────────────────────


class TestWhileLoopExecution:
    """The runtime executes while loops via guard + back-edge jumps."""

    def test_while_loop_iterates_multiple_times(self) -> None:
        counter = {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @decision
        def guard(ctx: dict) -> str:
            if counter["count"] < 3:
                return "__truthy__"
            return "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx):
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("count") == 3
        # Should have 3 phase executions + 3 guard evaluations

    def test_while_loop_with_vocabulary_guard(self) -> None:
        counter = {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: dict) -> str:
            return "again" if counter["count"] < 2 else "done"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx) == "again":
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("count") == 2

    def test_while_loop_zero_iterations(self) -> None:
        @phase
        def body(ctx: dict) -> dict:
            return {"executed": True}

        @decision
        def guard(ctx: dict) -> str:
            return "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx):
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert "executed" not in result.state

    def test_while_loop_followed_by_phase(self) -> None:
        counter = {"count": 0}

        @phase
        def setup(ctx: dict) -> dict:
            return {"ready": True}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @phase
        def cleanup(ctx: dict) -> dict:
            return {"done": True}

        @decision
        def guard(ctx: dict) -> str:
            return "__truthy__" if counter["count"] < 2 else "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield setup(ctx)
            while guard(ctx):
                s = yield body(ctx)
            s = yield cleanup(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("ready") is True
        assert result.state.get("count") == 2
        assert result.state.get("done") is True

    def test_subpipeline_body_preserves_loop_iteration_tracking(self) -> None:
        recorded_iterations: list[int] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def should_halt_loop(self, instr, state, iteration):
                recorded_iterations.append(iteration)
                return False, None

        @phase
        def child_body(ctx: dict) -> dict:
            current = ctx["state"].get("count", 0)
            return {"count": current + 1}

        @workflow(
            name="child_flow",
            inputs={"type": "object", "required": ["count"]},
            outputs={"type": "object", "required": ["count"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_body(ctx)
            return state

        @phase
        def after_child(ctx: dict) -> dict:
            return {"count": ctx["state"]["count"]}

        @decision
        def guard(ctx: dict) -> str:
            return "__truthy__" if ctx["state"].get("count", 0) < 2 else "__falsy__"

        @pipeline
        def parent(ctx: dict) -> dict:
            state: dict = {}
            while guard(ctx):
                state = yield child(ctx)
                state = yield after_child(ctx)
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog, hooks=RecordingHooks())

        assert result.state["count"] == 2
        assert recorded_iterations == [1, 2]

    def test_loop_body_context_uses_iteration_path_segments(self) -> None:
        seen_run_paths: list[str] = []
        seen_step_paths: list[str] = []
        counter = {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            seen_run_paths.append(ctx["run_path"])
            seen_step_paths.append(ctx["step_path"])
            counter["count"] += 1
            return {"count": counter["count"]}

        @decision(name="critique_loop", vocabulary={"again", "done"})
        def guard(ctx: dict) -> str:
            return "again" if counter["count"] < 2 else "done"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state: dict = {}
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)

        assert result.state["count"] == 2
        assert seen_run_paths == [
            "root/critique_loop[1]",
            "root/critique_loop[2]",
        ]
        assert seen_step_paths == [
            "root/critique_loop[1]/body",
            "root/critique_loop[2]/body",
        ]

    def test_nested_loop_iterations_are_scoped_by_full_run_path(self) -> None:
        seen_run_paths: list[str] = []
        counts_by_child: dict[str, int] = {}

        @phase
        def body(ctx: dict) -> dict:
            child_id = ctx["call_site_path"][0]
            seen_run_paths.append(ctx["run_path"])
            counts_by_child[child_id] = counts_by_child.get(child_id, 0) + 1
            return {"count": counts_by_child[child_id]}

        @decision(name="critique_loop", vocabulary={"again", "done"})
        def guard(ctx: dict) -> str:
            child_id = ctx["call_site_path"][0]
            return "again" if counts_by_child.get(child_id, 0) < 2 else "done"

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["count"]},
        )
        def child(ctx: dict) -> dict:
            state: dict = {}
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_a", outputs={"count": "a_count"})
            state = yield child(ctx, id="child_b", outputs={"count": "b_count"})
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(prog)

        assert result.state["a_count"] == 2
        assert result.state["b_count"] == 2
        assert seen_run_paths == [
            "root/child_a/critique_loop[1]",
            "root/child_a/critique_loop[2]",
            "root/child_b/critique_loop[1]",
            "root/child_b/critique_loop[2]",
        ]

    def test_resume_path_stack_round_trips_legacy_loop_and_subpipeline_frames(
        self,
        tmp_path: Path,
    ) -> None:
        @phase
        def step(ctx: dict) -> dict:
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        cursor_path = tmp_path / "resume_cursor.json"
        cursor_path.write_text(
            json.dumps(
                {
                    "stage": "my_pipe__step__pc0",
                    "resume_cursor": None,
                    "stages": [],
                    "loops": {"critique_loop": 2},
                    "frames": {"__state__": {}},
                    "run_path": "root/child_call/critique_loop[2]",
                    "step_path": "root/child_call/critique_loop[2]/step",
                    "call_site_path": ["child_call", "critique_loop[2]"],
                    "path_stack": [
                        {
                            "kind": "subpipeline",
                            "segment": "child_call",
                            "parent_run_path": "root",
                        },
                        {
                            "header_pc": 1,
                            "segment": "critique_loop[2]",
                            "parent_run_path": "root/child_call",
                        },
                    ],
                    "native": {"pc": 0, "version": 1},
                }
            ),
            encoding="utf-8",
        )

        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            max_phases=1,
        )

        assert result.suspended is True
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["path_stack"] == [
            {
                "kind": "subpipeline",
                "segment": "child_call",
                "parent_run_path": "root",
            },
            {
                "kind": "loop",
                "header_pc": 1,
                "segment": "critique_loop[2]",
                "parent_run_path": "root/child_call",
            },
        ]

    def test_runtime_subpipeline_cycle_guard_rejects_recursive_program(self) -> None:
        recursive = NativeProgram(
            name="recursive",
            instructions=(
                NativeInstruction(pc=0, op="subpipeline", name="recursive"),
                NativeInstruction(pc=1, op="halt"),
            ),
            stable_id="workflow.recursive",
        )
        recursive_instr = NativeInstruction(
            pc=0,
            op="subpipeline",
            name="recursive",
            subprogram=recursive,
        )
        object.__setattr__(recursive, "instructions", (recursive_instr, recursive.instructions[1]))

        with pytest.raises(
            NativeRuntimeError,
            match="Runtime subpipeline cycle detected: workflow.recursive -> workflow.recursive",
        ):
            run_native_pipeline(recursive)

    def test_runtime_entry_validation_rejects_parallel_map_cycle_before_execution(self) -> None:
        phase_calls: list[str] = []

        def setup(ctx: object) -> dict:
            phase_calls.append("setup")
            return {}

        root = NativeProgram(
            name="mapper_parent",
            stable_id="workflow.mapper_parent",
            instructions=(
                NativeInstruction(pc=0, op="phase", name="setup", func=setup, next_pc=1),
                NativeInstruction(pc=1, op="parallel_map", name="fanout", next_pc=2),
                NativeInstruction(pc=2, op="halt"),
            ),
        )
        child = NativeProgram(
            name="mapper_child",
            stable_id="workflow.mapper_child",
            instructions=(
                NativeInstruction(
                    pc=0,
                    op="subpipeline",
                    name="parent_call",
                    subprogram=root,
                ),
                NativeInstruction(pc=1, op="halt"),
            ),
        )
        object.__setattr__(
            root,
            "instructions",
            (
                root.instructions[0],
                NativeInstruction(
                    pc=1,
                    op="parallel_map",
                    name="fanout",
                    subprogram=ParallelMapInstruction(
                        name="fanout",
                        items_ref="items",
                        mapper=child,
                        mapper_name="mapper_child",
                        path_template="fanout/{index}",
                        merge_pc=2,
                    ),
                    next_pc=2,
                ),
                root.instructions[2],
            ),
        )

        with pytest.raises(
            NativeRuntimeError,
            match=(
                "Runtime subpipeline cycle detected: "
                "workflow.mapper_parent -> workflow.mapper_child -> workflow.mapper_parent"
            ),
        ):
            run_native_pipeline(root, initial_state={"items": [1]})

        assert phase_calls == []


# ── NativeExecutionResult ─────────────────────────────────────────────


class TestNativeExecutionResult:
    """NativeExecutionResult carries correct metadata."""

    def test_defaults(self) -> None:
        result = NativeExecutionResult(state={}, stages=[], pc=0)
        assert result.state == {}
        assert result.stages == []
        assert result.pc == 0
        assert result.suspended is False
        assert result.cursor_path is None

    def test_suspended_result(self) -> None:
        result = NativeExecutionResult(
            state={"x": 1},
            stages=["pipe__a__pc0"],
            pc=1,
            suspended=True,
            cursor_path="/tmp/cur.json",
        )
        assert result.suspended is True
        assert result.cursor_path == "/tmp/cur.json"

    def test_importable_from_package(self) -> None:
        from arnold.pipeline.native import NativeExecutionResult, run_native_pipeline
        assert NativeExecutionResult is not None
        assert callable(run_native_pipeline)

    def test_run_ignores_deprecated_flag_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_native_pipeline still executes when the old flag is ``0``."""
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)

        assert result.state == {"x": 1}


# ── on_checkpoint hook ─────────────────────────────────────────────────


class TestOnCheckpointHook:
    """on_checkpoint(cursor, state) fires after cursor persistence and clean completion."""

    def test_fires_on_max_phases_suspension(self, tmp_path: Path) -> None:
        """on_checkpoint fires with the cursor dict and state after max_phases suspension."""
        captured_cursors: list[dict] = []
        captured_states: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured_cursors.append(dict(cursor))
                captured_states.append(dict(state))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            max_phases=1,
            hooks=hooks,
        )

        assert result.suspended
        assert len(captured_cursors) == 1, "on_checkpoint should fire once on suspension"
        assert len(captured_states) == 1

        cursor = captured_cursors[0]
        state = captured_states[0]

        # Verify cursor shape matches persist_native_cursor output
        assert "native" in cursor
        assert cursor["native"]["pc"] == result.pc
        assert cursor["native"]["version"] == 1
        assert "stage" in cursor
        assert "stages" in cursor
        assert cursor["stages"] == result.stages
        assert "frames" in cursor
        assert "__state__" in cursor["frames"]
        assert cursor["frames"]["__state__"] == {"x": 1}
        assert "final" not in cursor  # suspension, not final

        # Verify state matches
        assert state == {"x": 1}

    def test_fires_on_clean_completion(self) -> None:
        """on_checkpoint fires with the cursor dict and state after clean completion."""
        captured_cursors: list[dict] = []
        captured_states: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured_cursors.append(dict(cursor))
                captured_states.append(dict(state))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert not result.suspended
        assert len(captured_cursors) == 1, "on_checkpoint should fire once on clean completion"
        assert len(captured_states) == 1

        cursor = captured_cursors[0]
        state = captured_states[0]

        # Verify cursor shape
        assert "native" in cursor
        assert cursor["native"]["pc"] == result.pc
        assert cursor["native"]["version"] == 1
        assert "stage" in cursor
        assert "stages" in cursor
        assert cursor["stages"] == result.stages
        assert "frames" in cursor
        assert "__state__" in cursor["frames"]
        assert cursor["final"] is True  # clean completion marker

        # Verify state matches final state
        assert state == {"x": 1, "y": 2}

    def test_not_fired_on_exception(self) -> None:
        """on_checkpoint is NOT called when a phase raises an exception."""
        captured: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append(dict(cursor))

        hooks = RecordingHooks()

        @phase
        def good(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def bad(ctx: dict) -> dict:
            raise RuntimeError("fail")

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield good(ctx)
            s = yield bad(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        with pytest.raises(RuntimeError, match="fail"):
            run_native_pipeline(prog, hooks=hooks)

        assert len(captured) == 0, "on_checkpoint must not fire on exception"

    def test_on_checkpoint_has_no_megaplan_imports(self) -> None:
        """Verify that hooks.py contains no megaplan-specific imports."""
        import ast
        import inspect
        from arnold.pipeline.native import hooks as hooks_mod

        source = inspect.getsource(hooks_mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = (
                    node.module if isinstance(node, ast.ImportFrom) else None
                )
                # For plain imports, check each alias
                if module_name is None:
                    for alias in node.names:
                        if "megaplan" in alias.name.lower():
                            pytest.fail(
                                f"hooks.py imports megaplan: {alias.name}"
                            )
                elif "megaplan" in (module_name or "").lower():
                    pytest.fail(
                        f"hooks.py imports megaplan: {module_name}"
                    )

    def test_on_checkpoint_with_multi_suspension(self, tmp_path: Path) -> None:
        """on_checkpoint fires on each suspension when resuming multiple times."""
        captured: list[tuple[dict, dict]] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append((dict(cursor), dict(state)))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # First suspension (after phase a)
        r1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, hooks=hooks)
        assert r1.suspended
        assert len(captured) == 1
        assert captured[0][1] == {"a": 1}

        # Second suspension (after phase b)
        r2 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, resume=True, hooks=hooks)
        assert r2.suspended
        assert len(captured) == 2
        assert captured[1][1] == {"a": 1, "b": 2}

        # Clean completion (phases c)
        r3 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True, hooks=hooks)
        assert not r3.suspended
        assert len(captured) == 3
        assert captured[2][1] == {"a": 1, "b": 2, "c": 3}
        assert captured[2][0].get("final") is True


# ── Executor-owned key merge: CAS (typed-ports-on) ────────────────────


class TestMergeStateCAS:
    """merge_state with CAS semantics (typed-ports-on behaviour).

    Proves that a Megaplan-aware merge_state hook applies each output key
    through versioned StateDelta replacement, tracks _state_meta.versions,
    and rejects stale writes with StateDeltaConflict.
    """

    def test_cas_merge_tracks_versions(self) -> None:
        """merge_state via CAS bumps _state_meta.versions for each key."""
        from arnold_pipelines.megaplan.state_delta import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": "hello"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 2, "z": [1, 2]}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state["x"] == 2
        assert result.state["y"] == "hello"
        assert result.state["z"] == [1, 2]

        meta = result.state.get("_state_meta", {})
        versions = meta.get("versions", {})
        # x was written twice (step_a→1, step_b→2), version should be 2
        assert versions["x"] == 2
        # y was written once, version should be 1
        assert versions["y"] == 1
        # z was written once, version should be 1
        assert versions["z"] == 1

    def test_cas_merge_accumulates_owned_keys(self) -> None:
        """merge_state via CAS adds each merged key to owned_keys."""
        from arnold_pipelines.megaplan.state_delta import (
            StateDelta,
            apply_delta,
        )

        recorded_owned: list[frozenset[str]] = []

        class CASHooks(NullNativeRuntimeHooks):
            def on_stage_complete(self, instr, ctx, result, state, owned_keys):
                recorded_owned.append(frozenset(owned_keys))

            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": 3, "a": 99}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            s = yield step_c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        assert len(recorded_owned) == 3
        assert recorded_owned[0] == frozenset({"a"})
        assert recorded_owned[1] == frozenset({"a", "b"})
        assert recorded_owned[2] == frozenset({"a", "b", "c"})

    def test_cas_stale_write_rejected(self) -> None:
        """A stale-version write through merge_state raises StateDeltaConflict.

        The native runtime pre-applies ``state.update(outputs)`` before
        calling ``merge_state``, so the value is already present.  The
        CAS hook's role is to detect the stale version and refuse to bump
        ``_state_meta.versions`` — proving the conflict-detection path
        is exercised without crashing the pipeline.
        """
        from arnold_pipelines.megaplan.state_delta import (
            StateDelta,
            StateDeltaConflict,
            apply_delta,
        )

        # Simulate a hook that always passes version=0 — the second write
        # should conflict because _state_meta.versions[x] is already 1.
        stale_attempted: list[bool] = []

        class StaleCASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    try:
                        state, _ = apply_delta(
                            state,
                            StateDelta(
                                op="replace", key=k, value=v, version=0
                            ),
                        )
                        new_owned.add(k)
                    except StateDeltaConflict:
                        stale_attempted.append(True)
                        # Do not mutate state or add to owned_keys on conflict
                return state, frozenset(new_owned)

        hooks = StaleCASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": "first"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": "second"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # The stale write was attempted and rejected
        assert len(stale_attempted) == 1
        # Version should be 1 (only the first CAS write succeeded;
        # the runtime's pre-apply put the value in state but the CAS
        # hook refused to bump the version on the stale attempt).
        assert result.state["_state_meta"]["versions"]["x"] == 1

    def test_cas_bootstrap_version_zero(self) -> None:
        """First write to a key with version=0 succeeds and sets version to 1."""
        from arnold_pipelines.megaplan.state_delta import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step(ctx: dict) -> dict:
            return {"key": "value"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state["key"] == "value"
        assert result.state["_state_meta"]["versions"]["key"] == 1


# ── Executor-owned key merge: plain dict.update (typed-ports-off) ─────


class TestMergeStatePlainUpdate:
    """merge_state with plain dict.update (typed-ports-off behaviour).

    Proves that when typed ports are off, state merge is a simple
    dict.update — no _state_meta tracking, no CAS, no conflict detection.
    """

    def test_plain_update_no_versions(self) -> None:
        """merge_state via dict.update does not create _state_meta."""
        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": 2}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 99, "z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # Values are correct (last-writer-wins)
        assert result.state["x"] == 99
        assert result.state["y"] == 2
        assert result.state["z"] == 3

        # No _state_meta tracking
        assert "_state_meta" not in result.state

    def test_plain_update_accumulates_owned_keys(self) -> None:
        """merge_state via dict.update adds all output keys to owned_keys."""
        recorded_owned: list[frozenset[str]] = []

        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def on_stage_complete(self, instr, ctx, result, state, owned_keys):
                recorded_owned.append(frozenset(owned_keys))

            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2, "c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        assert len(recorded_owned) == 2
        assert recorded_owned[0] == frozenset({"a"})
        assert recorded_owned[1] == frozenset({"a", "b", "c"})

    def test_plain_update_silent_overwrite(self) -> None:
        """Plain update silently overwrites — no conflict detection."""
        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": "first"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": "second"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # Last writer wins silently — no error, no version tracking
        assert result.state["x"] == "second"
        assert "_state_meta" not in result.state

    def test_plain_update_versus_cas_consistency(self) -> None:
        """Same pipeline yields identical key-values with both merge modes."""
        from arnold_pipelines.megaplan.state_delta import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        class PlainHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": "a"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 2, "z": [1, 2, 3]}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        cas_result = run_native_pipeline(prog, hooks=CASHooks())
        plain_result = run_native_pipeline(prog, hooks=PlainHooks())

        # Both modes produce the same final values for non-meta keys
        for key in ("x", "y", "z"):
            assert cas_result.state[key] == plain_result.state[key], (
                f"key {key!r} differs: CAS={cas_result.state[key]!r} "
                f"vs plain={plain_result.state[key]!r}"
            )

        # But only CAS tracks _state_meta
        assert "_state_meta" in cas_result.state
        assert "_state_meta" not in plain_result.state


# ── Control-override vs additive-override behaviour ────────────────────


class TestControlOverrideShortCircuit:
    """Control overrides skip the decision body; additive overrides do not."""

    def test_control_override_skips_decision_body(self) -> None:
        """When __override_route__ is set, the decision body is NOT called."""
        body_calls: list[str] = []

        @phase
        def on_left(ctx: dict) -> dict:
            return {"path": "left"}

        @phase
        def on_override(ctx: dict) -> dict:
            return {"path": "override"}

        @decision(vocabulary={"left", "right", "override"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "left"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "left":
                s = yield on_left(ctx)
            elif decide(ctx) == "right":
                s = yield on_left(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            else:
                s = {}
            return s

        prog = compile_pipeline(my_pipe)

        # Hook that injects a control override via __override_route__
        class ControlOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "override"
                return ctx

        hooks = ControlOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Decision body was NEVER called
        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s); "
            f"control override should short-circuit it"
        )

        # Override route was followed
        assert result.state.get("path") == "override"

    def test_additive_override_still_calls_body(self) -> None:
        """Additive overrides mutate state but the decision body IS called."""
        body_calls: list[str] = []

        @phase
        def step_a(ctx: dict) -> dict:
            return {"before": True}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"after": True}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            state = ctx.get("state", {})
            # Additive override should have set this
            if state.get("meta", {}).get("note_added"):
                return "yes"
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            if decide(ctx) == "yes":
                s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Hook that applies an additive override (mutates state, no
        # __override_route__ set).
        class AdditiveOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    state = ctx.get("state")
                    if isinstance(state, dict):
                        state.setdefault("meta", {})["note_added"] = True
                        ctx["state"] = state
                return ctx

        hooks = AdditiveOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Decision body WAS called (the additive override caused it to
        # choose "yes" based on the modified state)
        assert body_calls == ["decide"], (
            f"Decision body calls: {body_calls}; "
            f"additive override should NOT short-circuit the body"
        )

        # The additive override's state mutation was effective
        assert result.state.get("before") is True
        assert result.state.get("after") is True

    def test_override_application_is_recorded(self) -> None:
        """When a control override fires, its application is observable."""
        override_record: list[dict[str, object]] = []

        @phase
        def final(ctx: dict) -> dict:
            return {"done": True}

        @decision(vocabulary={"pass", "override"})
        def decide(ctx: dict) -> str:
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield final(ctx)
            elif decide(ctx) == "override":
                s = yield final(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        class RecordingOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "override"
                    override_record.append({
                        "action": "override",
                        "phase": instr.name,
                    })
                return ctx

            def on_step_end(self, instr, ctx, result):
                if isinstance(result, dict) and "__override_route__" in result:
                    override_record.append({
                        "action": result["__override_route__"],
                        "phase": instr.name,
                        "event": "on_step_end",
                    })
                return result

        hooks = RecordingOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Override was recorded in on_step_start
        assert any(
            e.get("action") == "override" and e.get("phase") == "decide"
            for e in override_record
        ), f"No override_record entry for on_step_start: {override_record}"

        # The synthetic result from the short-circuit carries the override
        # metadata and is visible in on_step_end.
        assert any(
            e.get("event") == "on_step_end"
            for e in override_record
        ), f"No on_step_end entry in override_record: {override_record}"

        # Final state confirms the pipeline completed
        assert result.state.get("done") is True

    def test_control_override_falls_back_to_override_label(self) -> None:
        """When the action name is not in the vocabulary, 'override' is used."""
        body_calls: list[str] = []

        @phase
        def on_pass(ctx: dict) -> dict:
            return {"branch": "pass"}

        @phase
        def on_override(ctx: dict) -> dict:
            return {"branch": "override"}

        @decision(vocabulary={"pass", "override"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield on_pass(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Inject an action name that is NOT in the vocabulary
        class FallbackOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    # "abort" is not in {"pass", "override"} vocabulary
                    ctx["__override_route__"] = "abort"
                return ctx

        hooks = FallbackOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Body was NOT called — the override short-circuit fired,
        # fell back to "override" label.
        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s)"
        )

        # The "override" branch was taken
        assert result.state.get("branch") == "override"

    def test_control_override_with_matching_action_label(self) -> None:
        """When the action name IS in the vocabulary, it is used directly."""
        body_calls: list[str] = []

        @phase
        def on_pass(ctx: dict) -> dict:
            return {"branch": "pass"}

        @phase
        def on_abort(ctx: dict) -> dict:
            return {"branch": "abort"}

        @decision(vocabulary={"pass", "abort"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield on_pass(ctx)
            elif decide(ctx) == "abort":
                s = yield on_abort(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        class ExactMatchOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    # "abort" IS in the vocabulary — used as-is
                    ctx["__override_route__"] = "abort"
                return ctx

        hooks = ExactMatchOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s)"
        )
        assert result.state.get("branch") == "abort"

    def test_no_override_falls_through_to_normal_execution(self) -> None:
        """When __override_route__ is not set, decisions execute normally."""
        body_calls: list[str] = []

        @phase
        def on_yes(ctx: dict) -> dict:
            return {"branch": "yes"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "yes"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield on_yes(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Null hooks (no override) — decisions execute normally
        result = run_native_pipeline(prog, hooks=NullNativeRuntimeHooks())

        assert body_calls == ["decide"]
        assert result.state.get("branch") == "yes"


# ── parallel fan-out / fan-in runtime (M5a baseline) ──────────────────


class TestParallelRuntime:
    """Runtime executes parallel blocks compiled from ``for x in parallel(...)``."""

    def test_parallel_branches_run_sequentially(self) -> None:
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            for branch in parallel([branch_a, branch_b]):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"a": 1, "b": 2}
        assert len(result.stages) == 2

    def test_parallel_with_reducer(self) -> None:
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"value": 1}

        @phase
        def branch_b(ctx: dict) -> dict:
            return {"value": 2}

        def reducer(results: list[dict]) -> dict:
            return {"total": sum(r["value"] for r in results)}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            for branch in parallel([branch_a, branch_b], reducer=reducer):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        # Reducer is currently stored in IR; the no-op sequential runtime does
        # not invoke it automatically, so state is the last branch's output.
        # This test documents the current M5a contract.
        assert "value" in result.state

    def test_yield_parallel_call_compiles(self) -> None:
        """``yield parallel([...])`` compiles into a resumable parallel instruction.

        As of T3 the compiler lowers ``yield parallel(...)`` directly
        without requiring a ``for`` loop body wrapper.  The resulting
        parallel instruction has a single downstream next_pc and stores
        branch metadata via ParallelInstruction subprogram.
        """
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield parallel([branch_a, branch_b])
            return state

        prog = compile_pipeline(my_pipe)
        # Should produce a parallel instruction
        parallel_instrs = [i for i in prog.instructions if i.op == "parallel"]
        assert len(parallel_instrs) == 1
        pinstr = parallel_instrs[0]
        # next_pc should point to instruction after the parallel (halt in this case)
        assert pinstr.next_pc is not None
        assert pinstr.next_pc == len(prog.instructions) - 1  # halt is last
        # Should have ParallelInstruction subprogram
        assert pinstr.subprogram is not None
        assert pinstr.subprogram.branches == ("branch_a", "branch_b")
        assert pinstr.subprogram.reducer is None
        assert pinstr.subprogram.merge_pc == pinstr.next_pc
        # parallel_blocks should have one entry
        assert len(prog.parallel_blocks) == 1


# ── T3: Human-gate suspension persistence ────────────────────────────


class TestHumanGateSuspension:
    """Native initial human-gate suspension: detect metadata before calling
    the decision body, write ``awaiting_user.json``, construct
    ``HumanSuspension``, and persist a graph-compatible cursor with
    additive native restoration metadata.
    """

    @staticmethod
    def _compile_review_loop_human_gate_program(
        *,
        override_routes: dict[str, str | None] | None = None,
    ) -> NativeProgram:
        @phase
        def draft(ctx: dict) -> dict:
            return {"draft_ready": True}

        @phase
        def panel_review(ctx: dict) -> dict:
            review_count = ctx["state"].get("review_count", 0) + 1
            return {"path": "panel_review", "review_count": review_count}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="draft",
            choices=("continue", "stop"),
            override_routes=override_routes,
        )
        def human_gate(ctx: dict) -> str:
            raise AssertionError("human-gate decision body should not run")

        @pipeline
        def review_loop(ctx: dict) -> dict:
            state = yield draft(ctx)
            while human_gate(ctx) == "continue":
                state = yield panel_review(ctx)
            return state

        return compile_pipeline(review_loop)

    def test_human_gate_suspends_without_calling_body(self, tmp_path: Path) -> None:
        """A human-gate decision suspends immediately without calling the body."""
        body_called: list[bool] = []

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            body_called.append(True)
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path)

        # Should be suspended, NOT complete
        assert result.suspended is True
        # Decision body should NOT have been called
        assert len(body_called) == 0
        # Only do_work should have completed
        assert len(result.stages) == 1

    def test_human_gate_writes_awaiting_user_json(self, tmp_path: Path) -> None:
        """Human-gate suspension writes awaiting_user.json with correct keys."""
        import json

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        checkpoint_path = tmp_path / "awaiting_user.json"
        assert checkpoint_path.exists(), "awaiting_user.json should be written"

        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        # Canonical top-level keys from write_human_gate_checkpoint
        assert "pipeline" in checkpoint
        assert "version" in checkpoint
        assert "artifact_stage" in checkpoint
        assert "stage" in checkpoint
        assert "choices" in checkpoint
        assert "message" in checkpoint
        assert checkpoint["choices"] == ["continue", "stop"]
        assert checkpoint["artifact_stage"] == "do_work"

    def test_human_gate_persists_resume_cursor(self, tmp_path: Path) -> None:
        """Human-gate suspension persists resume_cursor.json with native metadata."""
        import json

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        cursor_path = tmp_path / "resume_cursor.json"
        assert cursor_path.exists(), "resume_cursor.json should be persisted"

        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        # Graph-compatible top-level fields
        assert "stage" in cursor
        assert "resume_cursor" in cursor
        # Native metadata
        assert "native" in cursor
        assert cursor["native"]["suspension_kind"] == "human_gate"
        assert isinstance(cursor["native"]["pc"], int)
        assert isinstance(cursor["native"]["version"], int)
        # Additive native restoration metadata
        assert cursor.get("suspension_kind") == "human_gate"
        assert cursor.get("choices") == ["continue", "stop"]

    def test_human_gate_uses_injected_persistence_backend(self, tmp_path: Path) -> None:
        backend = _MemoryNativePersistenceBackend()

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                state = yield after(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        first = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            persistence_backend=backend,
        )
        assert first.suspended is True
        assert not (tmp_path / "awaiting_user.json").exists()
        assert not (tmp_path / "resume_cursor.json").exists()
        assert backend.human_gate_writes[-1][1]["choices"] == ["continue", "stop"]
        assert backend.resume_writes[-1][1]["native"]["suspension_kind"] == "human_gate"

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            human_input={"choice": "continue"},
            persistence_backend=backend,
        )
        assert resumed.suspended is False
        assert resumed.state["after"] is True
        assert backend.human_gate_deletes
        assert backend.resume_deletes
        assert not backend.human_gate
        assert not backend.resume

    def test_human_gate_resume_routes_by_choice(self, tmp_path: Path) -> None:
        """Resume after human-gate reads _resume_choice from awaiting_user.json
        and routes to the correct branch."""
        import json

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @phase
        def continue_phase(ctx: dict) -> dict:
            return {"path": "continue"}

        @phase
        def stop_phase(ctx: dict) -> dict:
            return {"path": "stop"}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            return "continue"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                s = yield continue_phase(ctx)
            else:
                s = yield stop_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # First run: should suspend at human-gate
        result1 = run_native_pipeline(prog, artifact_root=tmp_path)
        assert result1.suspended is True
        assert "path" not in result1.state  # Neither branch executed

        # Inject _resume_choice into awaiting_user.json
        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["_resume_choice"] = "continue"
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

        # Resume
        result2 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert result2.suspended is False
        assert result2.state.get("path") == "continue"
        # Checkpoint should be cleaned up after resume
        assert not checkpoint_path.exists(), "Checkpoint should be cleaned up after resume"

    def test_human_gate_resume_stop_choice(self, tmp_path: Path) -> None:
        """Resume with 'stop' choice routes to the stop branch."""
        import json

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @phase
        def continue_phase(ctx: dict) -> dict:
            return {"path": "continue"}

        @phase
        def stop_phase(ctx: dict) -> dict:
            return {"path": "stop"}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="do_work",
            choices=("continue", "stop"),
        )
        def human_decide(ctx: dict) -> str:
            return "continue"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if human_decide(ctx) == "continue":
                s = yield continue_phase(ctx)
            else:
                s = yield stop_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        # Inject "stop" choice
        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["_resume_choice"] = "stop"
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

        result2 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert result2.state.get("path") == "stop"

    def test_human_gate_human_input_continue_routes_loop_and_re_suspends(
        self,
        tmp_path: Path,
    ) -> None:
        """Explicit continue input enters the loop body and pauses at the next gate."""
        import json

        prog = self._compile_review_loop_human_gate_program()
        first = run_native_pipeline(prog, artifact_root=tmp_path)
        checkpoint_path = tmp_path / "awaiting_user.json"
        assert first.suspended is True
        assert checkpoint_path.exists()

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            human_input={"choice": "continue"},
        )

        assert resumed.suspended is True
        assert resumed.state.get("path") == "panel_review"
        assert resumed.state.get("review_count") == 1
        assert checkpoint_path.exists()
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint["choices"] == ["continue", "stop"]
        assert "_resume_choice" not in checkpoint

    def test_human_gate_human_input_stop_routes_to_halt_and_cleans_checkpoint(
        self,
        tmp_path: Path,
    ) -> None:
        """Explicit stop input exits the loop, reaches halt, and clears the gate file."""
        prog = self._compile_review_loop_human_gate_program()
        first = run_native_pipeline(prog, artifact_root=tmp_path)
        checkpoint_path = tmp_path / "awaiting_user.json"
        assert first.suspended is True
        assert checkpoint_path.exists()

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            human_input={"choice": "stop"},
        )

        halt_pc = next(instr.pc for instr in prog.instructions if instr.op == "halt")
        assert resumed.suspended is False
        assert resumed.pc == halt_pc
        assert resumed.state.get("draft_ready") is True
        assert "review_count" not in resumed.state
        assert "_pipeline_paused" not in resumed.state
        assert "awaiting_user" not in resumed.state
        assert not checkpoint_path.exists()

    def test_human_gate_declared_override_resume_routes_loop_branch(
        self,
        tmp_path: Path,
    ) -> None:
        """Declared override input can route to a branch outside human choices."""
        import json

        prog = self._compile_review_loop_human_gate_program(
            override_routes={"force_continue": "continue"}
        )
        first = run_native_pipeline(prog, artifact_root=tmp_path)
        checkpoint_path = tmp_path / "awaiting_user.json"
        assert first.suspended is True
        assert checkpoint_path.exists()

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            override_input={"override": "force_continue"},
        )

        assert resumed.suspended is True
        assert resumed.state.get("path") == "panel_review"
        assert resumed.state.get("review_count") == 1
        assert checkpoint_path.exists()
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint["choices"] == ["continue", "stop"]
        assert "_resume_choice" not in checkpoint

    def test_human_gate_invalid_human_input_choice_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        """Invalid explicit choices fail before branch routing or checkpoint cleanup."""
        prog = self._compile_review_loop_human_gate_program()
        run_native_pipeline(prog, artifact_root=tmp_path)
        checkpoint_path = tmp_path / "awaiting_user.json"
        cursor_path = tmp_path / "resume_cursor.json"
        before_checkpoint = checkpoint_path.read_text(encoding="utf-8")
        before_cursor = cursor_path.read_text(encoding="utf-8")

        with pytest.raises(NativeRuntimeError, match="valid choices"):
            run_native_pipeline(
                prog,
                artifact_root=tmp_path,
                resume=True,
                human_input={"choice": "retry"},
            )

        assert checkpoint_path.exists()
        assert cursor_path.exists()
        assert checkpoint_path.read_text(encoding="utf-8") == before_checkpoint
        assert cursor_path.read_text(encoding="utf-8") == before_cursor

    def test_human_gate_invalid_override_input_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        """Undeclared override labels fail before checkpoint cleanup."""
        prog = self._compile_review_loop_human_gate_program(
            override_routes={"force_continue": "continue"}
        )
        run_native_pipeline(prog, artifact_root=tmp_path)
        checkpoint_path = tmp_path / "awaiting_user.json"
        cursor_path = tmp_path / "resume_cursor.json"
        before_checkpoint = checkpoint_path.read_text(encoding="utf-8")
        before_cursor = cursor_path.read_text(encoding="utf-8")

        with pytest.raises(NativeRuntimeError, match="no declared branch or override route"):
            run_native_pipeline(
                prog,
                artifact_root=tmp_path,
                resume=True,
                override_input={"override": "force_stop"},
            )

        assert checkpoint_path.exists()
        assert cursor_path.exists()
        assert checkpoint_path.read_text(encoding="utf-8") == before_checkpoint
        assert cursor_path.read_text(encoding="utf-8") == before_cursor

    def test_ordinary_decision_unaffected(self) -> None:
        """Ordinary (non-human-gate) decisions execute normally."""
        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @decision(vocabulary={"pass", "fail"})
        def check(ctx: dict) -> str:
            return "pass"

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield do_work(ctx)
            if check(ctx) == "pass":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.suspended is False
        assert result.state.get("after") is True

    def test_human_gate_cursor_has_native_suspension_kind(self, tmp_path: Path) -> None:
        """The native cursor sub-dict includes suspension_kind for human-gate."""
        import json

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            choices=("continue", "stop"),
        )
        def gate(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            if gate(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        cursor = json.loads(
            (tmp_path / "resume_cursor.json").read_text(encoding="utf-8")
        )
        native = cursor["native"]
        assert native["suspension_kind"] == "human_gate"
        assert native["pc"] >= 0
        assert native["version"] == 1

    def test_phase_suspension_cursor_persists_path_metadata_for_child_run(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import ContractResult, ContractStatus, StepResult, Suspension

        @phase
        def review(ctx: dict) -> StepResult:
            return StepResult(
                outputs={"review": "waiting"},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(kind="human", resume_cursor="review-cursor"),
                ),
            )

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield review(ctx)
            return state

        prog = compile_pipeline(parent)
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            run_path="root/child_call",
        )

        assert result.state["review"] == "waiting"
        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["run_path"] == "root/child_call"
        assert cursor["step_path"] == "root/child_call/review"
        assert cursor["call_site_path"] == ["child_call"]

    def test_human_gate_cursor_is_classified_as_native(self, tmp_path: Path) -> None:
        """classify_resume_cursor correctly identifies a human-gate native cursor."""
        from arnold.pipeline.native.checkpoint import classify_resume_cursor

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            choices=("continue", "stop"),
        )
        def gate(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            if gate(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        classification = classify_resume_cursor(tmp_path)
        assert classification == "native", (
            f"Human-gate cursor should be classified as 'native', got {classification!r}"
        )

    def test_human_gate_with_resume_input_schema(self, tmp_path: Path) -> None:
        """Human-gate with resume_input_schema embeds schema in cursor and checkpoint."""
        import json

        schema = {"type": "object", "properties": {"note": {"type": "string"}}}

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            choices=("continue", "stop"),
            resume_input_schema=schema,
        )
        def gate(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            if gate(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)

        # Check cursor
        cursor = json.loads(
            (tmp_path / "resume_cursor.json").read_text(encoding="utf-8")
        )
        assert cursor.get("resume_input_schema") == schema

        # Check awaiting_user.json
        checkpoint = json.loads(
            (tmp_path / "awaiting_user.json").read_text(encoding="utf-8")
        )
        assert "resume_input_schema" in checkpoint
        assert checkpoint["resume_input_schema"] == schema

    def test_human_gate_preserves_envelope(self, tmp_path: Path) -> None:
        """Human-gate suspension preserves the accumulated envelope in cursor."""
        import json

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1, "envelope": {"phase": "step", "data": "hello"}}

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            choices=("continue", "stop"),
        )
        def gate(ctx: dict) -> str:
            return "continue"

        @phase
        def after(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            if gate(ctx) == "continue":
                s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path)
        assert result.suspended is True
        # Envelope should have been accumulated
        assert result.envelope is not None


class TestPhaseContractSuspension:
    """Shared ContractStatus.SUSPENDED handling for ordinary phases."""

    def test_phase_suspension_persists_same_pc_cursor_without_completion(
        self,
        tmp_path: Path,
    ) -> None:
        import json

        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        completed: list[str] = []

        class Hooks(NullNativeRuntimeHooks):
            def on_stage_complete(self, instr, ctx, result, state, owned_keys):
                completed.append(instr.name)

        @phase
        def human_review(ctx: dict) -> StepResult:
            suspension = Suspension(
                kind="human",
                awaitable="review",
                prompt="Review",
                resume_cursor="pack-1.human_review",
            )
            return StepResult(
                outputs={"review_status": "waiting"},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=suspension,
                    payload={"checkpoint": "human_review"},
                ),
            )

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield human_review(ctx)
            s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=Hooks())

        assert result.suspended is True
        assert result.pc == 0
        assert result.stages == []
        assert completed == []
        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["stage"].endswith("__human_review__pc0")
        assert cursor["native"]["pc"] == 0
        assert cursor["native"]["suspension_kind"] == "phase_suspended"
        assert cursor["resume_cursor"] == "pack-1.human_review"
        assert cursor["stages"] == []
        assert cursor["frames"]["__state__"]["review_status"] == "waiting"
        assert cursor["contract_result"]["status"] == "suspended"
        assert cursor["suspension"]["resume_cursor"] == "pack-1.human_review"

    def test_phase_suspension_resume_merges_initial_state_over_restored_state(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        @phase
        def human_review(ctx: dict) -> StepResult:
            if ctx["state"].get("approved"):
                return StepResult(
                    outputs={
                        "approved": ctx["state"]["approved"],
                        "review_status": "done",
                    },
                    contract_result=ContractResult(
                        status=ContractStatus.COMPLETED,
                        payload={"status": "passed"},
                    ),
                )
            return StepResult(
                outputs={"approved": False, "review_status": "waiting"},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        awaitable="review",
                        prompt="Review",
                        resume_cursor="review-cursor",
                    ),
                ),
            )

        @phase
        def after(ctx: dict) -> dict:
            return {"after": ctx["state"]["review_status"]}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield human_review(ctx)
            s = yield after(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        first = run_native_pipeline(prog, artifact_root=tmp_path)
        assert first.suspended is True
        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            initial_state={"approved": True},
        )

        assert resumed.suspended is False
        assert resumed.state["approved"] is True
        assert resumed.state["review_status"] == "done"
        assert resumed.state["after"] == "done"

    def test_resume_skips_fulfilled_side_effect_without_replaying(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        calls = {"write": 0}

        @phase(
            operation="file_write",
            target="out.txt",
            effect_class="filesystem_mutation",
        )
        def write_once(ctx: dict) -> StepResult:
            calls["write"] += 1
            (Path(ctx["artifact_root"]) / "out.txt").write_text(
                f"call-{calls['write']}\n",
                encoding="utf-8",
            )
            return StepResult(
                outputs={"status": "waiting"},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        awaitable="review",
                        prompt="Review",
                        resume_cursor="review-cursor",
                    ),
                ),
            )

        @phase
        def after(ctx: dict) -> dict:
            return {"after": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield write_once(ctx)
            s = yield after(ctx)
            return s

        hooks = EffectLedgerHooks()
        prog = compile_pipeline(my_pipe)
        first = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)
        assert first.suspended is True

        resumed = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            resume=True,
            hooks=hooks,
        )

        assert resumed.suspended is False
        assert calls["write"] == 1
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "call-1\n"

    def test_resume_blocks_unreconciled_unowned_file_write(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        @phase(
            operation="file_write",
            target="out.txt",
            effect_class="filesystem_mutation",
        )
        def write_then_suspend(ctx: dict) -> StepResult:
            (Path(ctx["artifact_root"]) / "out.txt").write_text(
                "partial\n",
                encoding="utf-8",
            )
            return StepResult(
                outputs={"status": "waiting"},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        awaitable="review",
                        prompt="Review",
                        resume_cursor="review-cursor",
                    ),
                ),
            )

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield write_then_suspend(ctx)
            return state

        hooks = EffectLedgerHooks()
        prog = compile_pipeline(my_pipe)
        first = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)
        assert first.suspended is True

        cursor_path = tmp_path / "resume_cursor.json"
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        cursor["effect"]["lifecycle_state"] = "intended"
        cursor["effect"]["expected_content"] = "complete\n"
        cursor_path.write_text(json.dumps(cursor), encoding="utf-8")

        with pytest.raises(
            NativeRuntimeError,
            match="Cannot resume native side-effecting step",
        ):
            run_native_pipeline(
                prog,
                artifact_root=tmp_path,
                resume=True,
                hooks=hooks,
            )

    def test_phase_suspension_resume_rejects_malformed_saved_state(
        self,
        tmp_path: Path,
    ) -> None:
        import json

        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        @phase
        def human_review(ctx: dict) -> StepResult:
            return StepResult(
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(kind="human", resume_cursor="review-cursor"),
                )
            )

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield human_review(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, artifact_root=tmp_path)
        cursor_path = tmp_path / "resume_cursor.json"
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        cursor["frames"]["__state__"] = "not-an-object"
        cursor_path.write_text(json.dumps(cursor), encoding="utf-8")

        with pytest.raises(NativeRuntimeError, match="frames.__state__"):
            run_native_pipeline(prog, artifact_root=tmp_path, resume=True)

    def test_phase_suspension_preserves_composite_child_suspensions(
        self,
        tmp_path: Path,
    ) -> None:
        import json

        from arnold.pipeline.contract_reduce import reduce_contract_results
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            StepResult,
            Suspension,
        )

        left = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=Suspension(
                kind="human",
                awaitable="review",
                prompt="Review left",
                resume_cursor="left-cursor",
            ),
        )
        right = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=Suspension(
                kind="human",
                awaitable="review",
                prompt="Review right",
                resume_cursor="right-cursor",
            ),
        )
        composite = reduce_contract_results(
            (left, right),
            child_ids=("left_child", "right_child"),
        )

        @phase
        def composite_review(ctx: dict) -> StepResult:
            return StepResult(
                outputs={"review_status": "waiting"},
                contract_result=composite,
            )

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield composite_review(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path)

        assert result.suspended is True
        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["native"]["suspension_kind"] == "phase_suspended"
        assert cursor["resume_cursor"] is None
        assert cursor["suspension"]["kind"] == "composite_suspension"
        assert cursor["suspension"]["resume_cursor"] is None

        pending = cursor["contract_result"]["payload"]["pending_suspensions"]
        assert [entry["child_id"] for entry in pending] == ["left_child", "right_child"]
        assert [entry["cursor"] for entry in pending] == ["left-cursor", "right-cursor"]
        assert [
            entry["suspension"]["resume_cursor"] for entry in pending
        ] == ["left-cursor", "right-cursor"]
        assert set(cursor["suspension"]["resume_input_schema"]["required"]) == {
            "left_child",
            "right_child",
        }
