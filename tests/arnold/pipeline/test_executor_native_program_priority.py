"""Tests for executor native_program priority and resource-bundle fallback.

Covers:
* ``_find_native_program`` prefers ``pipeline.native_program`` over
  resource-bundle ``NativeProgram`` instances.
* ``_find_native_program`` falls back to resource-bundle ``NativeProgram``
  when ``pipeline.native_program`` is ``None`` (transitional compatibility).
* ``_find_native_bundle`` prefers adapters in resource_bundles but still
  finds ``NativeProgram`` through the priority chain.
* End-to-end: ``run_pipeline`` dispatches through the native path when
  ``pipeline.native_program`` is set, and also when only a bare
  ``NativeProgram`` resource bundle is present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.execution.hooks import NullExecutorHooks
from arnold.pipeline.executor import (
    _find_native_bundle,
    _find_native_program,
    _should_dispatch_native,
    _run_native_dispatched,
    run_pipeline,
)
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope


# ---------------------------------------------------------------------------
# Minimal step for constructing fixture pipelines
# ---------------------------------------------------------------------------


class _FakeStep:
    """A step that does nothing — used only for structural tests."""

    def __init__(self, name: str = "fake", kind: str = "produce") -> None:
        self.name = name
        self.kind = kind

    def run(self, ctx: StepContext) -> StepResult:
        raise NotImplementedError("test-only stub")


def _make_pipeline(
    *,
    native_program: NativeProgram | None = None,
    resource_bundles: tuple[Any, ...] = (),
) -> Pipeline:
    """Return a minimal single-stage Pipeline with the given native fields."""
    s = Stage(
        name="s",
        step=_FakeStep("s"),
        edges=(Edge(label="halt", target="halt"),),
    )
    return Pipeline(
        stages={"s": s},
        entry="s",
        native_program=native_program,
        resource_bundles=resource_bundles,
    )


def _make_env(tmp_path: Path) -> RuntimeEnvelope:
    return RuntimeEnvelope(
        plugin_id="test",
        run_id="r1",
        artifact_root=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# _find_native_program — priority & fallback
# ---------------------------------------------------------------------------


class TestFindNativeProgram:
    """``_find_native_program`` returns the correct program or ``None``."""

    def test_returns_native_program_when_set(self) -> None:
        program = NativeProgram(name="explicit")
        pipeline = _make_pipeline(native_program=program)
        assert _find_native_program(pipeline) is program

    def test_returns_none_when_nothing_set(self) -> None:
        pipeline = _make_pipeline()
        assert _find_native_program(pipeline) is None

    def test_falls_back_to_resource_bundle_native_program(self) -> None:
        program = NativeProgram(name="bundle-fallback")
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(program,),
        )
        assert _find_native_program(pipeline) is program

    def test_prefers_native_program_over_resource_bundle(self) -> None:
        explicit = NativeProgram(name="explicit-wins")
        bundled = NativeProgram(name="bundled-loses")
        pipeline = _make_pipeline(
            native_program=explicit,
            resource_bundles=(bundled,),
        )
        result = _find_native_program(pipeline)
        assert result is explicit
        assert result is not bundled

    def test_returns_none_when_resource_bundles_have_no_native_program(self) -> None:
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=("not-a-program", 42),
        )
        assert _find_native_program(pipeline) is None

    def test_native_program_set_to_nonnative_skipped(self) -> None:
        """When native_program is not a NativeProgram, it is ignored."""
        bundled = NativeProgram(name="bundled")
        pipeline = Pipeline(
            stages={
                "s": Stage(
                    name="s",
                    step=_FakeStep("s"),
                    edges=(Edge(label="halt", target="halt"),),
                ),
            },
            entry="s",
            native_program="not-a-native-program",  # type: ignore[arg-type]
            resource_bundles=(bundled,),
        )
        result = _find_native_program(pipeline)
        assert result is bundled


# ---------------------------------------------------------------------------
# _find_native_bundle — adapter & program priority
# ---------------------------------------------------------------------------


class _FakeAdapter:
    """A resource bundle that exposes ``run_native_pipeline``."""

    def __init__(self, name: str = "adapter") -> None:
        self.name = name

    def run_native_pipeline(self, **kwargs: Any) -> Any:
        return {"adapter": self.name, **kwargs}


class TestFindNativeBundle:
    """``_find_native_bundle`` resolves adapters and programs correctly."""

    def test_returns_none_when_nothing_set(self) -> None:
        pipeline = _make_pipeline()
        assert _find_native_bundle(pipeline) is None

    def test_returns_program_from_native_program_field(self) -> None:
        program = NativeProgram(name="from-field")
        pipeline = _make_pipeline(native_program=program)
        assert _find_native_bundle(pipeline) is program

    def test_returns_program_from_resource_bundle_fallback(self) -> None:
        program = NativeProgram(name="from-bundle")
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(program,),
        )
        assert _find_native_bundle(pipeline) is program

    def test_adapter_in_bundles_takes_priority_over_native_program(self) -> None:
        """Adapters (objects with ``run_native_pipeline``) are preferred."""
        adapter = _FakeAdapter("adapter-wins")
        program = NativeProgram(name="program-loses")
        pipeline = _make_pipeline(
            native_program=program,
            resource_bundles=(adapter,),
        )
        assert _find_native_bundle(pipeline) is adapter

    def test_adapter_in_bundles_found_even_without_native_program(self) -> None:
        adapter = _FakeAdapter()
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(adapter,),
        )
        assert _find_native_bundle(pipeline) is adapter

    def test_adapter_seen_before_bundled_native_program(self) -> None:
        """First adapter wins even if a NativeProgram appears later."""
        adapter = _FakeAdapter("first-adapter")
        program = NativeProgram(name="later-program")
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(adapter, program),
        )
        assert _find_native_bundle(pipeline) is adapter

    def test_bundled_native_program_returned_when_no_adapter(self) -> None:
        program = NativeProgram(name="only-bundle")
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(program,),
        )
        assert _find_native_bundle(pipeline) is program


# ---------------------------------------------------------------------------
# _should_dispatch_native — decision logic
# ---------------------------------------------------------------------------


class TestShouldDispatchNative:
    """``_should_dispatch_native`` gates the native dispatch path."""

    def test_dispatches_native_when_native_program_set(self) -> None:
        program = NativeProgram(name="test")
        pipeline = _make_pipeline(native_program=program)
        assert _should_dispatch_native(pipeline, None) is True

    def test_dispatches_native_from_bundled_program(self) -> None:
        program = NativeProgram(name="bundle-only")
        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(program,),
        )
        assert _should_dispatch_native(pipeline, None) is True

    def test_does_not_dispatch_when_no_native_evidence(self) -> None:
        pipeline = _make_pipeline()
        assert _should_dispatch_native(pipeline, None) is False

    def test_graph_marker_overrides_native_capability(self) -> None:
        program = NativeProgram(name="test")
        pipeline = _make_pipeline(native_program=program)
        from arnold.pipeline.native.routing import RUNTIME_GRAPH

        assert _should_dispatch_native(pipeline, RUNTIME_GRAPH) is False

    def test_native_marker_with_native_capability_dispatches(self) -> None:
        program = NativeProgram(name="test")
        pipeline = _make_pipeline(native_program=program)
        from arnold.pipeline.native.routing import RUNTIME_NATIVE

        assert _should_dispatch_native(pipeline, RUNTIME_NATIVE) is True

    def test_graph_kill_switch_overrides_native_capability(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_PIPELINE_RUNTIME", "graph")
        program = NativeProgram(name="test")
        pipeline = _make_pipeline(native_program=program)
        assert _should_dispatch_native(pipeline, None) is False

    def test_native_kill_switch_forces_native_when_capable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_PIPELINE_RUNTIME", "native")
        program = NativeProgram(name="test")
        pipeline = _make_pipeline(native_program=program)
        assert _should_dispatch_native(pipeline, None) is True


# ---------------------------------------------------------------------------
# End-to-end dispatch — run_pipeline routes through native when appropriate
# ---------------------------------------------------------------------------


class TestRunPipelineNativeDispatch:
    """Integration: ``run_pipeline`` dispatches through the native path."""

    def test_run_pipeline_dispatches_native_with_native_program(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Pipeline with native_program → native dispatch path is taken."""
        program = NativeProgram(name="e2e-explicit")

        # Patch run_native_pipeline to avoid real execution.
        dispatched: dict[str, Any] = {}

        def fake_run_native(
            prog: NativeProgram, **kwargs: Any
        ) -> dict[str, Any]:
            dispatched["program"] = prog
            dispatched["kwargs"] = kwargs
            return {"native": True, "state": kwargs.get("initial_state", {})}

        monkeypatch.setattr(
            "arnold.pipeline.native.runtime.run_native_pipeline",
            fake_run_native,
        )

        pipeline = _make_pipeline(native_program=program)
        env = _make_env(tmp_path)

        result = run_pipeline(pipeline, {"key": "val"}, env)

        assert dispatched["program"] is program
        assert result == {"native": True, "state": {"key": "val"}}

    def test_run_pipeline_dispatches_native_with_bundled_program(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Bare NativeProgram in resource_bundles → native dispatch (compat)."""
        program = NativeProgram(name="e2e-bundle")

        dispatched: dict[str, Any] = {}

        def fake_run_native(
            prog: NativeProgram, **kwargs: Any
        ) -> dict[str, Any]:
            dispatched["program"] = prog
            dispatched["kwargs"] = kwargs
            return {"native": True, "state": kwargs.get("initial_state", {})}

        monkeypatch.setattr(
            "arnold.pipeline.native.runtime.run_native_pipeline",
            fake_run_native,
        )

        pipeline = _make_pipeline(
            native_program=None,
            resource_bundles=(program,),
        )
        env = _make_env(tmp_path)

        result = run_pipeline(pipeline, {"key": "val"}, env)

        assert dispatched["program"] is program
        assert result == {"native": True, "state": {"key": "val"}}

    def test_run_pipeline_falls_back_to_graph_when_no_native(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Pipeline with no native evidence → graph walk path is taken."""
        from arnold.pipeline.executor import _step_at

        called: dict[str, Any] = {}

        def fake_step_at(**kwargs: Any) -> Any:
            called.update(kwargs)
            return kwargs.get("envelope")

        monkeypatch.setattr(
            "arnold.pipeline.executor._step_at",
            fake_step_at,
        )

        pipeline = _make_pipeline()
        env = _make_env(tmp_path)

        result = run_pipeline(pipeline, {"key": "val"}, env)

        assert called.get("pipeline") is pipeline
        assert result is env

    def test_native_program_preferred_in_dispatched_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When both native_program and bundle NativeProgram exist,
        the native_program field is the one passed to run_native_pipeline."""
        explicit = NativeProgram(name="explicit-wins")
        bundled = NativeProgram(name="bundled-loses")

        dispatched: dict[str, Any] = {}

        def fake_run_native(
            prog: NativeProgram, **kwargs: Any
        ) -> dict[str, Any]:
            dispatched["program"] = prog
            return {"native": True}

        monkeypatch.setattr(
            "arnold.pipeline.native.runtime.run_native_pipeline",
            fake_run_native,
        )

        pipeline = _make_pipeline(
            native_program=explicit,
            resource_bundles=(bundled,),
        )
        env = _make_env(tmp_path)

        run_pipeline(pipeline, {}, env)

        assert dispatched["program"] is explicit
        assert dispatched["program"] is not bundled

    def test_adapter_bundle_dispatches_through_adapter_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Adapter in resource_bundles runs via its run_native_pipeline."""
        adapter = _FakeAdapter("adapter-e2e")
        program = NativeProgram(name="also-present")

        dispatched: dict[str, Any] = {}

        def fake_adapter_run(**kwargs: Any) -> Any:
            dispatched["adapter_kwargs"] = kwargs
            return {"adapter_result": True}

        monkeypatch.setattr(adapter, "run_native_pipeline", fake_adapter_run)

        pipeline = _make_pipeline(
            native_program=program,
            resource_bundles=(adapter,),
        )
        env = _make_env(tmp_path)

        result = run_pipeline(pipeline, {"key": "val"}, env)

        assert dispatched["adapter_kwargs"]["program"] is program
        assert result == {"adapter_result": True}
