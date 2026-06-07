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

    def test_model_supports_metadata_only_direct_construction(self) -> None:
        invocation = StepInvocation(
            kind="model",
            metadata={"adapter_config": {"prompt": "hi", "temperature": 0.2}},
        )
        assert invocation == StepInvocation.model(
            adapter_config={"prompt": "hi", "temperature": 0.2},
        )

    def test_carries_json_compatible_metadata(self) -> None:
        invocation = StepInvocation(
            kind="human",
            metadata={"prompt": "approve?", "attempt": 1, "labels": ["gate"]},
        )
        assert invocation.metadata["prompt"] == "approve?"
        assert invocation.metadata["attempt"] == 1
        assert invocation.metadata["labels"] == ["gate"]

    def test_model_factory_stores_adapter_config_in_canonical_metadata(self) -> None:
        invocation = StepInvocation.model(
            adapter_config={"prompt": "hi", "temperature": 0.2},
        )
        assert invocation == StepInvocation(
            kind="model",
            metadata={"adapter_config": {"prompt": "hi", "temperature": 0.2}},
        )

    def test_with_adapter_config_factory_constructs_canonical_metadata(self) -> None:
        invocation = StepInvocation.with_adapter_config(
            kind="tool",
            adapter_config={"name": "formatter", "version": 2},
        )
        assert invocation == StepInvocation(
            kind="tool",
            metadata={"adapter_config": {"name": "formatter", "version": 2}},
        )

    def test_model_factory_preserves_existing_metadata(self) -> None:
        invocation = StepInvocation.model(
            adapter_config={"prompt": "hi"},
            metadata={"validation_step": "review"},
        )
        assert invocation.metadata == {
            "validation_step": "review",
            "adapter_config": {"prompt": "hi"},
        }

    def test_factory_allows_empty_metadata(self) -> None:
        invocation = StepInvocation.model(metadata={})
        assert invocation == StepInvocation(kind="model", metadata={})

    def test_with_adapter_config_authors_unknown_kind(self) -> None:
        invocation = StepInvocation.with_adapter_config(
            kind="custom-collector-v2",
            adapter_config={"endpoint": "queue://writer"},
        )
        assert invocation.kind == "custom-collector-v2"
        assert invocation.metadata == {
            "adapter_config": {"endpoint": "queue://writer"},
        }

    def test_unknown_non_model_kind_supports_direct_authoring_without_metadata(self) -> None:
        invocation = StepInvocation(kind="custom-collector-v2")
        assert invocation == StepInvocation.with_adapter_config(
            kind="custom-collector-v2",
            metadata={},
        )

    def test_factory_rejects_conflicting_adapter_config(self) -> None:
        with pytest.raises(ValueError, match="conflicting adapter_config"):
            StepInvocation.with_adapter_config(
                kind="model",
                adapter_config={"prompt": "new"},
                metadata={"adapter_config": {"prompt": "old"}},
            )

    def test_factory_allows_matching_adapter_config_from_metadata(self) -> None:
        invocation = StepInvocation.with_adapter_config(
            kind="model",
            adapter_config={"prompt": "same"},
            metadata={"adapter_config": {"prompt": "same"}, "worker": "codex"},
        )
        assert invocation.metadata == {
            "adapter_config": {"prompt": "same"},
            "worker": "codex",
        }

    def test_factory_and_direct_construction_share_canonical_metadata_shape(self) -> None:
        direct = StepInvocation(
            kind="model",
            metadata={
                "adapter_config": {"prompt": "same"},
                "worker": "codex",
            },
        )
        factory = StepInvocation.with_adapter_config(
            kind="model",
            adapter_config={"prompt": "same"},
            metadata={"worker": "codex"},
        )
        assert factory == direct


class TestStepInvocationAdapterRegistry:
    class _CustomAdapter:
        def __init__(self, response: Any) -> None:
            self._response = response
            self.calls: list[StepInvocation] = []

        def invoke(self, invocation: StepInvocation) -> Any:
            self.calls.append(invocation)
            return self._response

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
        registry = StepInvocationAdapterRegistry()
        registry.register("tool", self._CustomAdapter(response={"ok": True}))
        with pytest.raises(ValueError, match="already registered"):
            registry.register("tool", self._CustomAdapter(response={"ok": False}))

    def test_duplicate_normal_model_registration_is_rejected(self) -> None:
        registry = StepInvocationAdapterRegistry()
        with pytest.raises(ValueError, match="already registered"):
            registry.register("model", self._CustomAdapter(response={"ok": False}))

    def test_replace_reserved_requires_reserved_placeholder(self) -> None:
        registry = StepInvocationAdapterRegistry()
        registry.register("tool", self._CustomAdapter(response={"ok": True}))
        with pytest.raises(ValueError, match="reserved placeholder"):
            registry.replace_reserved("tool", self._CustomAdapter(response={"ok": False}))

    def test_replace_reserved_unknown_kind_fails_closed(self) -> None:
        registry = StepInvocationAdapterRegistry()
        with pytest.raises(KeyError, match="unknown adapter kind 'tool'"):
            registry.replace_reserved("tool", self._CustomAdapter(response={"ok": False}))

    def test_replace_reserved_installs_concrete_model_adapter(self) -> None:
        registry = StepInvocationAdapterRegistry()
        adapter = self._CustomAdapter(response={"rendered": True})
        registry.replace_reserved("model", adapter)

        invocation = StepInvocation(kind="model", metadata={"prompt": "hi"})
        assert registry.resolve("model") is adapter
        assert registry.invoke(invocation) == {"rendered": True}
        assert adapter.calls == [invocation]
