"""T5 (C4): Canonicalize and test the C4 public authoring surface.

Verifies:
1. ``ReadRef``, ``WriteRef``, ``derive_binding_map`` are present in BOTH the
   import block and ``__all__`` of ``arnold/pipeline/__init__.py``.
2. A model pipeline can be authored with ``instruction`` inside
   ``adapter_config`` via the public API.
3. A non-model ``kind='tool'`` pipeline can be authored via the public API;
   a fail-closed adapter registered in a local registry dispatches and raises
   ``AdapterNotImplementedError``; the global (process-wide) default registry
   is unchanged so route-bypass logic (unregistered kind fails via
   ``validate_invocation_requirements``) continues to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import arnold.pipeline as _pub
from arnold.pipeline import (
    Pipeline,
    Port,
    PortCardinality,
    PortRef,
    ReadRef,
    Stage,
    StepInvocation,
    StepInvocationAdapter,
    StepInvocationAdapterRegistry,
    WriteRef,
    derive_binding_map,
)
from arnold.pipeline.step_invocation import ModelAdapterNotImplementedError
from arnold.pipeline.validator import UNKNOWN_ADAPTER_CODE, validate


# ---------------------------------------------------------------------------
# 1. Public surface — exports present in both import block and __all__
# ---------------------------------------------------------------------------


class TestPublicSurfaceExports:
    def test_read_ref_in_all(self) -> None:
        assert "ReadRef" in _pub.__all__

    def test_write_ref_in_all(self) -> None:
        assert "WriteRef" in _pub.__all__

    def test_derive_binding_map_in_all(self) -> None:
        assert "derive_binding_map" in _pub.__all__

    def test_read_ref_importable(self) -> None:
        assert ReadRef is not None

    def test_write_ref_importable(self) -> None:
        assert WriteRef is not None

    def test_derive_binding_map_callable(self) -> None:
        assert callable(derive_binding_map)


# ---------------------------------------------------------------------------
# 2. Model pipeline with instruction inside adapter_config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NullModelStep:
    name: str = "model_stage"
    kind: str = "model"

    def run(self, ctx: Any) -> Any:  # pragma: no cover
        return object()


class TestModelPipelineAuthoring:
    def test_invocation_carries_instruction(self) -> None:
        invocation = StepInvocation.model(adapter_config={"instruction": "Summarize the input."})
        assert invocation.kind == "model"
        assert invocation.metadata["adapter_config"]["instruction"] == "Summarize the input."

    def test_model_pipeline_builds(self) -> None:
        step = _NullModelStep()
        stage = Stage(
            name="summarize",
            step=step,
            invocation=StepInvocation.model(adapter_config={"instruction": "Summarize."}),
        )
        pipeline = Pipeline(stages={"summarize": stage}, entry="summarize")
        assert "summarize" in pipeline.stages

    def test_model_pipeline_validate_passes(self) -> None:
        step = _NullModelStep()
        stage = Stage(
            name="summarize",
            step=step,
            invocation=StepInvocation.model(adapter_config={"instruction": "Summarize."}),
        )
        pipeline = Pipeline(stages={"summarize": stage}, entry="summarize")
        diag = validate(pipeline)
        unknown_adapter_defects = [d for d in diag.defects if "does not resolve to a registered adapter" in d]
        assert unknown_adapter_defects == [], (
            f"model pipeline should not have UNKNOWN_ADAPTER defects: {unknown_adapter_defects}"
        )

    def test_model_invocation_via_fresh_registry_raises_not_implemented(self) -> None:
        registry = StepInvocationAdapterRegistry()
        invocation = StepInvocation.model(adapter_config={"instruction": "x"})
        with pytest.raises(ModelAdapterNotImplementedError):
            registry.invoke(invocation)


# ---------------------------------------------------------------------------
# 3. Non-model kind='tool' pipeline with fail-closed adapter
# ---------------------------------------------------------------------------


class _FailClosedToolAdapter:
    """Fail-closed tool adapter: dispatch always raises AdapterNotImplementedError."""

    def invoke(self, invocation: StepInvocation) -> Any:
        raise NotImplementedError(
            f"kind='tool' adapter is fail-closed: {invocation.metadata!r}"
        )


@dataclass(frozen=True)
class _NullToolStep:
    name: str = "tool_stage"
    kind: str = "tool"

    def run(self, ctx: Any) -> Any:  # pragma: no cover
        return object()


class TestToolPipelineAuthoring:
    def test_tool_pipeline_builds(self) -> None:
        step = _NullToolStep()
        stage = Stage(
            name="lookup",
            step=step,
            invocation=StepInvocation.with_adapter_config(
                kind="tool", adapter_config={"tool_name": "calculator"}
            ),
        )
        pipeline = Pipeline(stages={"lookup": stage}, entry="lookup")
        assert "lookup" in pipeline.stages

    def test_tool_adapter_in_local_registry_raises_not_implemented(self) -> None:
        local_registry = StepInvocationAdapterRegistry()
        local_registry.register("tool", _FailClosedToolAdapter())
        invocation = StepInvocation.with_adapter_config(
            kind="tool", adapter_config={"tool_name": "calculator"}
        )
        with pytest.raises(NotImplementedError):
            local_registry.invoke(invocation)

    def test_local_tool_registration_does_not_affect_default_registry(self) -> None:
        from arnold.pipeline import get_default_adapter_registry
        local_registry = StepInvocationAdapterRegistry()
        local_registry.register("tool", _FailClosedToolAdapter())
        default_registry = get_default_adapter_registry()
        # 'tool' must NOT be in the global default — route-bypass must continue to fail
        assert "tool" not in default_registry.registered_kinds

    def test_route_bypass_validate_still_flags_unregistered_tool(self) -> None:
        """Unregistered kind='tool' still produces UNKNOWN_ADAPTER_CODE from validate().

        Confirms the route-bypass invariant: the static validator creates its
        own fresh registry (only 'model'), so an unregistered kind is always
        flagged regardless of test-local registrations.
        """
        step = _NullToolStep()
        stage = Stage(
            name="lookup",
            step=step,
            invocation=StepInvocation.with_adapter_config(
                kind="tool", adapter_config={"tool_name": "x"}
            ),
        )
        pipeline = Pipeline(stages={"lookup": stage}, entry="lookup")
        diag = validate(pipeline)
        unknown_adapter_defects = [d for d in diag.defects if "does not resolve to a registered adapter" in d]
        assert len(unknown_adapter_defects) >= 1, (
            "validate() must flag unregistered kind='tool' as UNKNOWN_ADAPTER"
        )
