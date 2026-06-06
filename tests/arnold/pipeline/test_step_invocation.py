"""Focused tests for the neutral StepInvocation foundation (M2 T8)."""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline import (
    ModelAdapterNotImplementedError,
    StepInvocation,
    StepInvocationAdapterRegistry,
)


class TestStepInvocation:
    def test_defaults_to_empty_metadata(self) -> None:
        invocation = StepInvocation(kind="tool")
        assert invocation.kind == "tool"
        assert invocation.metadata == {}

    def test_carries_json_compatible_metadata(self) -> None:
        invocation = StepInvocation(
            kind="human",
            metadata={"prompt": "approve?", "attempt": 1, "labels": ["gate"]},
        )
        assert invocation.metadata["prompt"] == "approve?"
        assert invocation.metadata["attempt"] == 1
        assert invocation.metadata["labels"] == ["gate"]


class TestStepInvocationAdapterRegistry:
    def test_registry_starts_with_only_model_placeholder(self) -> None:
        registry = StepInvocationAdapterRegistry()
        assert registry.registered_kinds == ("model",)

    def test_model_placeholder_raises_clear_m3_error(self) -> None:
        registry = StepInvocationAdapterRegistry()
        adapter = registry.resolve("model")
        with pytest.raises(
            ModelAdapterNotImplementedError,
            match="reserved for M3",
        ):
            adapter.invoke(StepInvocation(kind="model", metadata={"prompt": "hi"}))

    @pytest.mark.parametrize(
        "kind",
        [
            "tool",
            "human",
            "state",
            "render-job",
            "custom-collector-v2",
            "arbitrary-unknown-kind",
        ],
    )
    def test_unknown_kind_fails_closed(self, kind: str) -> None:
        registry = StepInvocationAdapterRegistry()
        with pytest.raises(KeyError, match=f"unknown adapter kind {kind!r}"):
            registry.resolve(kind)

    def test_duplicate_registration_is_rejected(self) -> None:
        class _CustomAdapter:
            def invoke(self, invocation: StepInvocation) -> Any:
                return invocation.metadata

        registry = StepInvocationAdapterRegistry()
        registry.register("tool", _CustomAdapter())
        with pytest.raises(ValueError, match="already registered"):
            registry.register("tool", _CustomAdapter())
