"""Executor selection tests for native-default and graph fallback routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.skip("archived deleted executor runtime", allow_module_level=True)

from arnold.pipeline.executor import run_pipeline, run_pipeline_resume
from arnold.pipeline.native.checkpoint import persist_native_cursor, read_native_cursor
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import StepIOContractContext, StepIOOperation
from arnold.pipeline.types import Pipeline, Stage, StepContext, StepResult
from arnold_pipelines.megaplan.native_runner import NativeMegaplanRunner
from arnold_pipelines.megaplan import pipeline as _megaplan_pipeline  # noqa: F401 - force real compile_pipeline binding before monkeypatch
from arnold.runtime.envelope import RuntimeEnvelope


class _HaltStep:
    def __init__(self) -> None:
        self.called = False

    def run(self, ctx: StepContext) -> StepResult:
        self.called = True
        return StepResult(next="halt")


class _TrackingStep:
    def __init__(self, next_label: str = "halt") -> None:
        self.next_label = next_label
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        return StepResult(next=self.next_label)


def _pipeline(step: _HaltStep, *, native_program: bool = True) -> Pipeline:
    program = NativeProgram(name="selection_test") if native_program else None
    return Pipeline(
        stages={"only": Stage(name="only", step=step, edges=())},
        entry="only",
        native_program=program,
    )


class _CaptureNativeRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run_native_pipeline(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "runner-result"


def _pipeline_with_runner(step: _HaltStep, runner: _CaptureNativeRunner) -> Pipeline:
    return Pipeline(
        stages={"only": Stage(name="only", step=step, edges=())},
        entry="only",
        resource_bundles=(runner,),
        native_program=NativeProgram(name="selection_test"),
    )


def _pipeline_with_bare_bundle(step: _HaltStep) -> Pipeline:
    return Pipeline(
        stages={"only": Stage(name="only", step=step, edges=())},
        entry="only",
        resource_bundles=(NativeProgram(name="legacy_bundle"),),
    )


def _envelope(tmp_path: Path) -> RuntimeEnvelope:
    return RuntimeEnvelope(
        plugin_id="selection-test",
        run_id="selection-run",
        artifact_root=str(tmp_path),
    )


def _write_state(tmp_path: Path, marker: str) -> None:
    _write_state_payload(tmp_path, {"meta": {"executor": marker}})


def _write_state_payload(tmp_path: Path, payload: dict[str, Any]) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_unmarked_native_capable_pipeline_ignores_deprecated_flag_zero(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(_pipeline(step), {}, _envelope(tmp_path))

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_native_marker_ignores_deprecated_flag_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_unmarked_native_capable_pipeline_runs_with_deprecated_flag_unset(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(_pipeline(step), {}, _envelope(tmp_path))

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_native_marker_is_normalized_by_shared_helper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "Native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_native_marker_and_flag_dispatch_to_native(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[dict[str, Any]] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append({"args": args, "kwargs": kwargs})
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "native"}, "seed": "value"},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls
    assert isinstance(calls[0]["args"][0], NativeProgram)
    assert calls[0]["kwargs"]["artifact_root"] == str(tmp_path)
    assert calls[0]["kwargs"]["initial_state"]["seed"] == "value"
    assert calls[0]["kwargs"]["resume"] is False


def test_persisted_graph_marker_wins_over_in_memory_native(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    _write_state(tmp_path, "graph")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_persisted_runtime_envelope_wins_over_persisted_meta_and_memory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    _write_state_payload(
        tmp_path,
        {
            "runtime_envelope": {"runtime": "graph"},
            "meta": {"executor": "native"},
        },
    )
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {
            "runtime_envelope": {"runtime": "native"},
            "meta": {"executor": "native"},
        },
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_in_memory_runtime_envelope_wins_over_in_memory_meta(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {
            "runtime_envelope": {"runtime": "graph"},
            "meta": {"executor": "native"},
        },
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_legacy_native_execution_alias_is_last_resort(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"_native_execution": True},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_modern_markers_win_over_legacy_native_execution_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {
            "runtime_envelope": {"runtime": "graph"},
            "_native_execution": True,
        },
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_in_memory_modern_marker_wins_over_persisted_legacy_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    _write_state_payload(tmp_path, {"_native_execution": False})
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"runtime_envelope": {"runtime": "native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_native_marker_without_native_program_uses_graph(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step, native_program=False),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_native_marker_dispatches_through_runner_adapter_with_executor_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    runner = _CaptureNativeRunner()
    envelope = _envelope(tmp_path)
    initial_context = StepContext(
        artifact_root=str(tmp_path),
        state={},
        hook_extensions={"step_io_policy_data": {"configured_mode": "warn"}},
    )

    result = run_pipeline(
        _pipeline_with_runner(step, runner),
        {"meta": {"executor": "native"}, "seed": "value"},
        envelope,
        initial_context=initial_context,
    )

    assert result == "runner-result"
    assert step.called is False
    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert isinstance(call["program"], NativeProgram)
    assert call["artifact_root"] == str(tmp_path)
    assert call["initial_state"]["seed"] == "value"
    assert call["resume"] is False
    assert call["initial_envelope"] is envelope
    assert call["schema_registry"] is None
    assert call["initial_context"] is initial_context


def test_bare_native_program_resource_bundle_still_dispatches_native(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    calls: list[dict[str, Any]] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append({"args": args, "kwargs": kwargs})
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline_with_bare_bundle(step),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls
    assert calls[0]["args"][0].name == "legacy_bundle"


def test_pipeline_native_program_is_passed_to_runner_adapter_before_bundle_program(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    runner = _CaptureNativeRunner()
    preferred = NativeProgram(name="preferred_field")
    legacy = NativeProgram(name="legacy_bundle")
    pipeline = Pipeline(
        stages={"only": Stage(name="only", step=step, edges=())},
        entry="only",
        resource_bundles=(legacy, runner),
        native_program=preferred,
    )

    result = run_pipeline(
        pipeline,
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result == "runner-result"
    assert step.called is False
    assert runner.calls[0]["program"] is preferred


def test_global_graph_runtime_override_wins_over_native_program(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    monkeypatch.setenv("ARNOLD_PIPELINE_RUNTIME", "graph")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.runtime.run_native_pipeline", fake_native)

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


def test_graph_resume_ignores_additive_native_cursor_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    first = _TrackingStep(next_label="second")
    second = _TrackingStep()
    pipeline = Pipeline(
        stages={
            "first": Stage(name="first", step=first, edges=()),
            "second": Stage(name="second", step=second, edges=()),
        },
        entry="first",
        native_program=NativeProgram(name="selection_test"),
    )
    _write_state(tmp_path, "graph")
    persist_native_cursor(
        tmp_path,
        stage="second",
        pc=99,
        stages=["native__first__pc0"],
        reentry_stage="native__second__pc1",
    )

    result = run_pipeline_resume(
        pipeline,
        {},
        _envelope(tmp_path),
    )

    assert result is not None
    assert first.calls == []
    assert len(second.calls) == 1


def test_resume_uses_persisted_graph_marker_over_new_native_choice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    _write_state(tmp_path, "graph")
    first = _TrackingStep(next_label="second")
    second = _TrackingStep()
    runner = _CaptureNativeRunner()
    pipeline = Pipeline(
        stages={
            "first": Stage(name="first", step=first, edges=()),
            "second": Stage(name="second", step=second, edges=()),
        },
        entry="first",
        resource_bundles=(runner,),
        native_program=NativeProgram(name="selection_test"),
    )
    persist_native_cursor(
        tmp_path,
        stage="first",
        pc=0,
        stages=[],
        reentry_stage="selection_test__first__pc0",
    )

    result = run_pipeline_resume(
        pipeline,
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
        resume_cursor={"stage": "second"},
    )

    assert result is not None
    assert runner.calls == []
    assert first.calls == []
    assert len(second.calls) == 1


def test_graph_resume_cursor_without_runtime_marker_uses_graph(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    first = _TrackingStep(next_label="second")
    second = _TrackingStep()
    runner = _CaptureNativeRunner()
    pipeline = Pipeline(
        stages={
            "first": Stage(name="first", step=first, edges=()),
            "second": Stage(name="second", step=second, edges=()),
        },
        entry="first",
        resource_bundles=(runner,),
        native_program=NativeProgram(name="selection_test"),
    )
    (tmp_path / "resume_cursor.json").write_text(
        json.dumps({"stage": "second", "resume_cursor": "legacy-cursor"}),
        encoding="utf-8",
    )

    result = run_pipeline_resume(
        pipeline,
        {},
        _envelope(tmp_path),
    )

    assert result is not None
    assert runner.calls == []
    assert first.calls == []
    assert len(second.calls) == 1


def test_resume_uses_persisted_native_marker_over_new_graph_choice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    _write_state(tmp_path, "native")
    step = _HaltStep()
    runner = _CaptureNativeRunner()

    result = run_pipeline_resume(
        _pipeline_with_runner(step, runner),
        {"meta": {"executor": "graph"}},
        _envelope(tmp_path),
        resume_cursor={"stage": "only"},
    )

    assert result == "runner-result"
    assert step.called is False
    assert len(runner.calls) == 1
    assert runner.calls[0]["resume"] is True
    assert runner.calls[0]["initial_state"] == {"meta": {"executor": "graph"}}


def test_native_resume_forwards_runtime_contract_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    step = _HaltStep()
    runner = _CaptureNativeRunner()
    registry = ContractSchemaRegistry(tmp_path)
    envelope = _envelope(tmp_path)
    persist_native_cursor(
        tmp_path,
        stage="selection_test__only__pc0",
        pc=0,
        stages=[],
        reentry_stage="selection_test__only__pc0",
    )

    result = run_pipeline_resume(
        _pipeline_with_runner(step, runner),
        {"seed": "value"},
        envelope,
        human_input={"choice": "continue"},
        schema_registry=registry,
    )

    assert result == "runner-result"
    assert step.called is False
    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call["artifact_root"] == str(tmp_path)
    assert call["initial_state"]["seed"] == "value"
    assert call["initial_envelope"] is envelope
    assert call["resume"] is True
    assert call["schema_registry"] is registry
    assert call["human_input"] == {"choice": "continue"}


def test_native_born_max_phases_suspension_resumes_to_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")

    def first(ctx: dict[str, Any]) -> dict[str, Any]:
        del ctx
        return {"first": True}

    def second(ctx: dict[str, Any]) -> dict[str, Any]:
        return {"second_saw_first": ctx["state"].get("first") is True}

    program = NativeProgram(
        name="resume_choice",
        instructions=(
            NativeInstruction(pc=0, op="phase", name="first", func=first, next_pc=1),
            NativeInstruction(pc=1, op="phase", name="second", func=second, next_pc=2),
            NativeInstruction(pc=2, op="halt", name="halt"),
        ),
    )

    suspended = run_native_pipeline(
        program,
        artifact_root=tmp_path,
        initial_state={"meta": {"executor": "native"}},
        max_phases=1,
    )

    cursor = read_native_cursor(tmp_path)
    assert suspended.suspended is True
    assert suspended.state == {"meta": {"executor": "native"}, "first": True}
    assert suspended.pc == 1
    assert cursor is not None
    assert cursor["native"]["pc"] == 1
    assert cursor["reentry_stage"] == "resume_choice__second__pc1"

    completed = run_native_pipeline(
        program,
        artifact_root=tmp_path,
        initial_state={"meta": {"executor": "graph"}},
        resume=True,
    )

    assert completed.suspended is False
    assert completed.state["meta"]["executor"] == "native"
    assert completed.state["first"] is True
    assert completed.state["second_saw_first"] is True
    assert completed.stages == [
        "resume_choice__first__pc0",
        "resume_choice__second__pc1",
    ]


def test_native_megaplan_runner_wires_runtime_hooks_and_policy_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    compiled = NativeProgram(name="compiled-megaplan")
    calls: list[dict[str, Any]] = []

    def fake_compile(pipeline_func: Any) -> NativeProgram:
        assert pipeline_func.__name__ == "megaplan"
        return compiled

    def fake_run_native_pipeline(program: NativeProgram, **kwargs: Any) -> str:
        calls.append({"program": program, "kwargs": kwargs})
        return "native-result"

    monkeypatch.setattr("arnold.pipeline.native.compiler.compile_pipeline", fake_compile)
    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline",
        fake_run_native_pipeline,
    )

    registry = ContractSchemaRegistry(tmp_path)
    envelope = _envelope(tmp_path)
    telemetry_path = tmp_path / "custom-telemetry.jsonl"
    initial_context = StepContext(
        artifact_root=str(tmp_path),
        state={},
        hook_extensions={
            "step_io_contract_context": StepIOContractContext(
                operation=StepIOOperation.WRITE,
                registry=registry,
            ),
            "step_io_policy_data": {"configured_mode": "enforce"},
            "step_io_policy_path": tmp_path / "policy.json",
            "step_io_telemetry_path": telemetry_path,
        },
    )

    projected = NativeProgram(name="projected-program")
    result = NativeMegaplanRunner().run_native_pipeline(
        program=projected,
        artifact_root=tmp_path,
        initial_state={"meta": {"executor": "native"}},
        initial_envelope=envelope,
        schema_registry=None,
        initial_context=initial_context,
    )

    assert result == "native-result"
    assert len(calls) == 1
    kwargs = calls[0]["kwargs"]
    assert calls[0]["program"] is projected
    assert kwargs["artifact_root"] == tmp_path
    assert kwargs["initial_state"] == {"meta": {"executor": "native"}}
    assert kwargs["resume"] is False
    assert kwargs["initial_envelope"] is envelope
    assert kwargs["schema_registry"] is registry
    assert kwargs["telemetry_path"] is telemetry_path
    hooks = kwargs["hooks"]
    assert hooks.__class__.__name__ == "MegaplanNativeRuntimeHooks"
    assert hooks._plan_dir == str(tmp_path)
    assert hooks._policy_data == {"configured_mode": "enforce"}
    assert hooks._policy_path == str(tmp_path / "policy.json")
