"""Executor selection tests — M1 dispatch substrate proof (migrated from archive).

Covers runtime-marker precedence (meta.executor, runtime_envelope.runtime),
legacy _native_execution alias compatibility, resume marker resolution,
and native-program dispatch routing.  The deprecated ``ARNOLD_NATIVE_RUNTIME``
env var is no longer tested — routing now defaults to native when
``pipeline.native_program`` is set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.executor import (
    RUNTIME_GRAPH,
    RUNTIME_NATIVE,
    _resolve_executor_marker,
    _resolve_resume_marker,
    run_pipeline,
    run_pipeline_resume,
)
from arnold.pipeline.native.checkpoint import persist_native_cursor, read_native_cursor
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.runtime.envelope import RuntimeEnvelope


# ── helpers ────────────────────────────────────────────────────────────────


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


# ── runtime marker precedence (meta.executor) ──────────────────────────────


def test_native_marker_and_default_dispatch_to_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native-capable pipeline with meta.executor='native' dispatches native."""
    step = _HaltStep()
    calls: list[dict[str, Any]] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append({"args": args, "kwargs": kwargs})
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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


def test_native_marker_is_normalized_by_shared_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case-insensitive marker 'Native' normalises and dispatches native."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "Native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


# ── persisted state marker precedence ──────────────────────────────────────


def test_persisted_graph_marker_wins_over_in_memory_native(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted meta.executor='graph' overrides in-memory 'native'."""
    _write_state(tmp_path, "graph")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted runtime_envelope.runtime wins over meta.executor and memory."""
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

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory runtime_envelope.runtime='graph' overrides meta.executor='native'."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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


# ── legacy _native_execution alias compatibility ───────────────────────────


def test_legacy_native_execution_alias_is_last_resort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deprecated _native_execution=True still selects native as a last resort."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modern runtime_envelope.runtime='graph' wins over _native_execution=True."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory runtime_envelope.runtime='native' wins over persisted _native_execution=False."""
    _write_state_payload(tmp_path, {"_native_execution": False})
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(
        _pipeline(step),
        {"runtime_envelope": {"runtime": "native"}},
        _envelope(tmp_path),
    )

    assert result == "native-result"
    assert step.called is False
    assert calls


# ── native marker without native_program ───────────────────────────────────


def test_native_marker_without_native_program_uses_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline without native_program runs graph even with native marker."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(
        _pipeline(step, native_program=False),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


# ── runner adapter dispatch ────────────────────────────────────────────────


def test_native_marker_dispatches_through_runner_adapter_with_executor_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runner adapter receives full executor context through run_native_pipeline."""
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare NativeProgram in resource_bundles dispatches native (compat)."""
    step = _HaltStep()
    calls: list[dict[str, Any]] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append({"args": args, "kwargs": kwargs})
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline.native_program takes priority over bundle NativeProgram for adapters."""
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


# ── global runtime override ────────────────────────────────────────────────


def test_global_graph_runtime_override_wins_over_native_program(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARNOLD_PIPELINE_RUNTIME=graph forces graph even with native_program."""
    monkeypatch.setenv("ARNOLD_PIPELINE_RUNTIME", "graph")
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "native"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []


# ── resume marker resolution ───────────────────────────────────────────────


def test_graph_resume_ignores_additive_native_cursor_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Graph-born resume ignores stray native cursor fields."""
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted graph marker keeps resume on graph despite in-memory native choice."""
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


def test_resume_uses_persisted_native_marker_over_new_graph_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted native marker keeps resume on native despite in-memory graph choice."""
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native resume propagates schema_registry and human_input to runner."""
    step = _HaltStep()
    runner = _CaptureNativeRunner()
    from arnold.pipeline.schema_registry import ContractSchemaRegistry

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


# ── born-native suspension and completion ──────────────────────────────────


def test_native_born_max_phases_suspension_resumes_to_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native-born pipeline suspended at max_phases resumes and completes natively."""

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
    # On resume the caller-supplied initial_state merges with persisted state;
    # the explicitly-passed meta.executor='graph' is authoritative.
    assert completed.state["first"] is True
    assert completed.state["second_saw_first"] is True
    assert completed.stages == [
        "resume_choice__first__pc0",
        "resume_choice__second__pc1",
    ]


# ── _resolve_executor_marker unit ─────────────────────────────────────────


class TestResolveExecutorMarker:
    """Unit-level tests for ``_resolve_executor_marker`` precedence."""

    def test_returns_none_when_no_state(self, tmp_path: Path) -> None:
        assert _resolve_executor_marker({}, tmp_path) is None

    def test_in_memory_meta_executor_native(self, tmp_path: Path) -> None:
        assert (
            _resolve_executor_marker({"meta": {"executor": "native"}}, tmp_path)
            == RUNTIME_NATIVE
        )

    def test_in_memory_meta_executor_graph(self, tmp_path: Path) -> None:
        assert (
            _resolve_executor_marker({"meta": {"executor": "graph"}}, tmp_path)
            == RUNTIME_GRAPH
        )

    def test_in_memory_runtime_envelope_wins_over_meta(self, tmp_path: Path) -> None:
        assert (
            _resolve_executor_marker(
                {
                    "runtime_envelope": {"runtime": "graph"},
                    "meta": {"executor": "native"},
                },
                tmp_path,
            )
            == RUNTIME_GRAPH
        )

    def test_persisted_wins_over_in_memory(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "graph")
        assert (
            _resolve_executor_marker(
                {"meta": {"executor": "native"}}, tmp_path
            )
            == RUNTIME_GRAPH
        )

    def test_legacy_alias_false(self, tmp_path: Path) -> None:
        assert (
            _resolve_executor_marker({"_native_execution": False}, tmp_path)
            == RUNTIME_GRAPH
        )

    def test_legacy_alias_true(self, tmp_path: Path) -> None:
        assert (
            _resolve_executor_marker({"_native_execution": True}, tmp_path)
            == RUNTIME_NATIVE
        )


# ── _resolve_resume_marker unit ───────────────────────────────────────────


class TestResolveResumeMarker:
    """Unit-level tests for ``_resolve_resume_marker`` cursor-aware resolution."""

    def test_graph_marker_returns_graph(self, tmp_path: Path) -> None:
        assert (
            _resolve_resume_marker(
                {"meta": {"executor": "graph"}}, tmp_path, None
            )
            == RUNTIME_GRAPH
        )

    def test_native_marker_returns_native(self, tmp_path: Path) -> None:
        assert (
            _resolve_resume_marker(
                {"meta": {"executor": "native"}}, tmp_path, None
            )
            == RUNTIME_NATIVE
        )

    def test_graph_cursor_pins_graph(self, tmp_path: Path) -> None:
        assert (
            _resolve_resume_marker(
                {}, tmp_path, {"stage": "some_stage", "resume_cursor": "legacy"}
            )
            == RUNTIME_GRAPH
        )

    def test_native_cursor_pins_native(self, tmp_path: Path) -> None:
        assert (
            _resolve_resume_marker(
                {},
                tmp_path,
                {
                    "native": {"pc": 0, "version": 2},
                    "reentry_stage": "prog__stage__pc0",
                    "stages": [],
                },
            )
            == RUNTIME_NATIVE
        )


# ── default native dispatch (no deprecated flags) ─────────────────────────


def test_native_capable_pipeline_dispatches_native_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native-capable pipeline dispatches native without any env flags set."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(_pipeline(step), {}, _envelope(tmp_path))

    assert result == "native-result"
    assert step.called is False
    assert calls


def test_graph_marker_forces_graph_even_with_native_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit graph marker in initial_state forces graph execution."""
    step = _HaltStep()
    calls: list[Any] = []

    def fake_native(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "native-result"

    monkeypatch.setattr(
        "arnold.pipeline.native.runtime.run_native_pipeline", fake_native
    )

    result = run_pipeline(
        _pipeline(step),
        {"meta": {"executor": "graph"}},
        _envelope(tmp_path),
    )

    assert result is not None
    assert step.called is True
    assert calls == []
