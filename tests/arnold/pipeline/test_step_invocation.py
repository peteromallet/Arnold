"""Focused tests for the neutral StepInvocation foundation (M2 T8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import (
    MediaUsage,
    ModelAdapterNotImplementedError,
    StepInvocation,
    StepInvocationAdapterRegistry,
    StepInvocationResult,
    unwrap_step_invocation_result,
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


# ── T5: StepInvocationResult + unwrap_step_invocation_result ────────────────


class TestStepInvocationResult:
    """Focused tests for the StepInvocationResult envelope (T5)."""

    def test_construct_with_payload_only(self) -> None:
        result = StepInvocationResult(payload="hello")
        assert result.payload == "hello"
        assert result.media_usage == ()

    def test_construct_with_payload_and_media_usage(self) -> None:
        mu = MediaUsage(unit="image", count=2)
        result = StepInvocationResult(
            payload={"key": "value"},
            media_usage=(mu,),
        )
        assert result.payload == {"key": "value"}
        assert result.media_usage == (mu,)

    def test_default_media_usage_is_empty_tuple(self) -> None:
        result = StepInvocationResult(payload=42)
        assert result.media_usage == ()

    def test_frozen_dataclass(self) -> None:
        result = StepInvocationResult(payload="x")
        with pytest.raises(Exception):
            result.payload = "y"  # type: ignore[misc]

    def test_equality(self) -> None:
        mu = MediaUsage(unit="image", count=1)
        a = StepInvocationResult(payload="p", media_usage=(mu,))
        b = StepInvocationResult(payload="p", media_usage=(mu,))
        assert a == b
        assert a != StepInvocationResult(payload="p")
        assert a != StepInvocationResult(payload="other", media_usage=(mu,))

    def test_payload_can_be_any_type(self) -> None:
        for value in ["str", 42, 3.14, None, {"k": "v"}, [1, 2], (3, 4)]:
            result = StepInvocationResult(payload=value)
            assert result.payload == value


class TestUnwrapStepInvocationResult:
    """Focused tests for unwrap_step_invocation_result (T5)."""

    def test_plain_return_unwraps_to_payload_and_empty_media_usage(self) -> None:
        payload, media_usage = unwrap_step_invocation_result("hello")
        assert payload == "hello"
        assert media_usage == ()

    def test_dict_plain_return_unwraps_unchanged(self) -> None:
        obj = {"status": "ok", "data": [1, 2, 3]}
        payload, media_usage = unwrap_step_invocation_result(obj)
        assert payload is obj  # same identity for plain returns
        assert media_usage == ()

    def test_int_plain_return_unwraps_unchanged(self) -> None:
        payload, media_usage = unwrap_step_invocation_result(42)
        assert payload == 42
        assert media_usage == ()

    def test_none_plain_return_unwraps_unchanged(self) -> None:
        payload, media_usage = unwrap_step_invocation_result(None)
        assert payload is None
        assert media_usage == ()

    def test_envelope_return_extracts_payload_and_media_usage(self) -> None:
        mu = MediaUsage(unit="image", count=1)
        envelope = StepInvocationResult(payload="payload", media_usage=(mu,))
        payload, media_usage = unwrap_step_invocation_result(envelope)
        assert payload == "payload"
        assert media_usage == (mu,)

    def test_envelope_with_empty_media_usage(self) -> None:
        envelope = StepInvocationResult(payload="result", media_usage=())
        payload, media_usage = unwrap_step_invocation_result(envelope)
        assert payload == "result"
        assert media_usage == ()

    def test_envelope_with_multiple_media_usage_items(self) -> None:
        mu1 = MediaUsage(unit="image", count=2)
        mu2 = MediaUsage(unit="video_second", count=30.0)
        envelope = StepInvocationResult(
            payload="done",
            media_usage=(mu1, mu2),
        )
        payload, media_usage = unwrap_step_invocation_result(envelope)
        assert payload == "done"
        assert media_usage == (mu1, mu2)

    def test_plain_return_is_backward_compatible_with_existing_adapters(self) -> None:
        """Existing adapters returning plain values work without changes."""
        # Simulating a plain adapter return (e.g. a JSON-like dict)
        adapter_output = {"text": "response", "finish_reason": "stop"}
        payload, media_usage = unwrap_step_invocation_result(adapter_output)
        assert payload == adapter_output
        assert media_usage == ()

    def test_envelope_is_opt_in(self) -> None:
        """Adapters that don't use StepInvocationResult are unaffected."""
        plain = "legacy response"
        payload, media_usage = unwrap_step_invocation_result(plain)
        assert payload == "legacy response"
        assert media_usage == ()

    def test_envelope_payload_can_be_dict_for_backward_compat(self) -> None:
        """Envelope payload can be a dict, matching common adapter output shapes."""
        data = {"text": "hi", "tool_calls": []}
        envelope = StepInvocationResult(payload=data)
        payload, media_usage = unwrap_step_invocation_result(envelope)
        assert payload == data
        assert media_usage == ()


# ── T6: Adapter envelope fixture tests (fake non-model adapter) ───────────


class TestFakeAdapterEnvelopeIntegration:
    """Fake non-model adapter returning StepInvocationResult → StepResult.hook_metadata.

    These tests verify the full integration path: a fake worker (standing in
    for a non-model adapter) returns a :class:`StepInvocationResult` envelope,
    :class:`AgentStep.run` unwraps it, and the resulting
    :class:`StepResult.hook_metadata` correctly captures ``media_usage`` while
    payload/state behavior remains unchanged.

    No generated artifacts are read — assertions target in-memory
    :class:`StepResult` fields only.
    """

    @staticmethod
    def _make_ctx(tmp_path: Path) -> StepContext:
        from arnold.pipeline.types import StepContext

        return StepContext(
            artifact_root=str(tmp_path),
            state=None,
            inputs={},
            mode="test",
        )

    # -- helpers: fake workers ------------------------------------------------

    @staticmethod
    def _fake_envelope_worker(payload: Any, media_usage: tuple[MediaUsage, ...]) -> Any:
        """Return a callable that produces a StepInvocationResult envelope."""

        def _worker(**kw: Any) -> StepInvocationResult:
            return StepInvocationResult(payload=payload, media_usage=media_usage)

        return _worker

    @staticmethod
    def _fake_plain_worker(payload: Any) -> Any:
        """Return a callable that produces a plain (non-envelope) value."""

        def _worker(**kw: Any) -> Any:
            return payload

        return _worker

    # -- envelope with media_usage → hook_metadata present -------------------

    def test_envelope_with_media_usage_attaches_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """media_usage tuple appears in StepResult.hook_metadata['media_usage']."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker("fake response", (mu,))
        step = AgentStep(name="adapter_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" in result.hook_metadata
        assert result.hook_metadata["media_usage"] == (mu,)

    def test_envelope_with_multiple_media_usage_items_in_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """Multiple MediaUsage items are preserved in hook_metadata."""
        from arnold.pipeline.steps.agent import AgentStep

        mu1 = MediaUsage(unit="image", count=2)
        mu2 = MediaUsage(unit="video_second", count=30.0)
        mu3 = MediaUsage(unit="audio_second", count=15)
        worker = self._fake_envelope_worker("multi-media", (mu1, mu2, mu3))
        step = AgentStep(name="multi_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (mu1, mu2, mu3)

    # -- envelope with empty media_usage → no hook_metadata key --------------

    def test_envelope_with_empty_media_usage_omits_hook_metadata_key(
        self, tmp_path: Path
    ) -> None:
        """Empty media_usage tuple → no 'media_usage' key in hook_metadata."""
        from arnold.pipeline.steps.agent import AgentStep

        worker = self._fake_envelope_worker("no media", ())
        step = AgentStep(name="no_media_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata

    # -- plain return (non-envelope) → no hook_metadata key ------------------

    def test_plain_return_omits_media_usage_in_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """Plain (non-envelope) adapter returns do not add 'media_usage' key."""
        from arnold.pipeline.steps.agent import AgentStep

        worker = self._fake_plain_worker("plain old response")
        step = AgentStep(name="plain_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata

    # -- payload behavior unchanged ------------------------------------------

    def test_envelope_payload_used_as_artifact_content(
        self, tmp_path: Path
    ) -> None:
        """The envelope payload (not the wrapper) becomes the artifact content."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker("envelope payload text", (mu,))
        step = AgentStep(name="payload_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.contract_result is not None
        artifact_path = Path(result.contract_result.payload["artifact_path"])
        assert artifact_path.read_text(encoding="utf-8") == "envelope payload text"

    def test_envelope_payload_preserves_non_string_types_via_str_coercion(
        self, tmp_path: Path
    ) -> None:
        """Non-string envelope payloads are str()-coerced, same as plain returns."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker(42, (mu,))
        step = AgentStep(name="int_payload", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.contract_result is not None
        artifact_path = Path(result.contract_result.payload["artifact_path"])
        assert artifact_path.read_text(encoding="utf-8") == "42"

    # -- state behavior unchanged --------------------------------------------

    def test_envelope_does_not_affect_state_patch_behavior(
        self, tmp_path: Path
    ) -> None:
        """State patching via _usage_extractor works identically with envelopes."""
        from arnold.pipeline.steps.agent import AgentStep

        def usage_extractor(**kw: Any) -> dict[str, Any]:
            return {"tokens": 150, "model": "fake-model"}

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker("state test", (mu,))
        step = AgentStep(
            name="state_test",
            _worker=worker,
            _usage_extractor=usage_extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"tokens": 150, "model": "fake-model"}

    def test_envelope_without_usage_extractor_still_has_empty_state_patch(
        self, tmp_path: Path
    ) -> None:
        """Without _usage_extractor, state_patch remains empty for envelope returns."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker("no extractor", (mu,))
        step = AgentStep(name="no_extractor", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}

    def test_plain_and_envelope_same_payload_produce_identical_artifact(
        self, tmp_path: Path
    ) -> None:
        """Envelope and plain returns with same payload → identical artifacts."""
        from arnold.pipeline.steps.agent import AgentStep

        payload = "same content"
        ctx_plain = self._make_ctx(tmp_path / "plain")
        ctx_env = self._make_ctx(tmp_path / "envelope")

        # Plain return
        plain_worker = self._fake_plain_worker(payload)
        plain_step = AgentStep(name="compare", _worker=plain_worker)
        plain_result = plain_step.run(ctx_plain)

        # Envelope return with media_usage
        mu = MediaUsage(unit="image", count=1)
        env_worker = self._fake_envelope_worker(payload, (mu,))
        env_step = AgentStep(name="compare", _worker=env_worker)
        env_result = env_step.run(ctx_env)

        # Artifact content should be identical
        plain_artifact = Path(plain_result.contract_result.payload["artifact_path"])
        env_artifact = Path(env_result.contract_result.payload["artifact_path"])
        assert plain_artifact.read_text(encoding="utf-8") == payload
        assert env_artifact.read_text(encoding="utf-8") == payload

        # But hook_metadata differs
        assert "media_usage" not in plain_result.hook_metadata
        assert env_result.hook_metadata["media_usage"] == (mu,)

    # -- ContractResult shape unchanged --------------------------------------

    def test_envelope_contract_result_shape_unchanged(
        self, tmp_path: Path
    ) -> None:
        """ContractResult payload keys are unchanged by envelope wrapping."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)
        worker = self._fake_envelope_worker("contract test", (mu,))
        step = AgentStep(
            name="contract_test",
            _worker=worker,
            _output_label="json",
            _output_suffix="json",
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.contract_result is not None
        assert set(result.contract_result.payload.keys()) == {
            "artifact_path",
            "label",
        }
        assert result.contract_result.payload["label"] == "json"

    # -- No artifact files read for core assertions --------------------------

    def test_hook_metadata_assertions_require_no_artifact_reads(
        self, tmp_path: Path
    ) -> None:
        """Core assertions on hook_metadata and payload are in-memory only."""
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="video_second", count=30)
        worker = self._fake_envelope_worker(b"binary-like payload", (mu,))
        step = AgentStep(name="no_read_test", _worker=worker)
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        from arnold.pipeline.types import StepResult

        # These assertions use only in-memory StepResult fields
        assert isinstance(result, StepResult)
        assert result.hook_metadata["media_usage"] == (mu,)
        assert result.contract_result is not None
        assert "artifact_path" in result.contract_result.payload
        assert result.contract_result.payload["label"] == "markdown"
        # Next/kind are predictable
        assert result.next == "done"
        assert result.verdict is None

    # -- PanelReviewerStep integration ---------------------------------------

    def test_panel_reviewer_envelope_attaches_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """PanelReviewerStep also unwraps envelopes correctly."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        mu = MediaUsage(unit="image", count=2)
        worker = self._fake_envelope_worker("panel response", (mu,))
        step = PanelReviewerStep(
            name="panel_review.expert",
            _worker=worker,
            _reviewer_id="expert",
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (mu,)
        assert result.outputs.get("expert") is not None

    def test_panel_reviewer_plain_return_omits_media_usage(
        self, tmp_path: Path
    ) -> None:
        """PanelReviewerStep plain return does not add 'media_usage' key."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        worker = self._fake_plain_worker("plain panel response")
        step = PanelReviewerStep(
            name="panel_review.plain",
            _worker=worker,
            _reviewer_id="plain",
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata
        assert result.outputs.get("plain") is not None


# ── T7: UsageExtraction + normalize_usage_extraction ────────────────────────

class TestUsageExtraction:
    """Focused tests for the UsageExtraction dataclass (T7)."""

    def test_construct_defaults(self) -> None:
        from arnold.pipeline import UsageExtraction

        ue = UsageExtraction()
        assert ue.state_patch == {}
        assert ue.media_usage == ()

    def test_construct_with_state_patch_only(self) -> None:
        from arnold.pipeline import UsageExtraction

        ue = UsageExtraction(state_patch={"tokens": 100, "model": "gpt-4"})
        assert ue.state_patch == {"tokens": 100, "model": "gpt-4"}
        assert ue.media_usage == ()

    def test_construct_with_media_usage_only(self) -> None:
        from arnold.pipeline import MediaUsage, UsageExtraction

        mu = MediaUsage(unit="image", count=1)
        ue = UsageExtraction(media_usage=(mu,))
        assert ue.state_patch == {}
        assert ue.media_usage == (mu,)

    def test_construct_with_both(self) -> None:
        from arnold.pipeline import MediaUsage, UsageExtraction

        mu = MediaUsage(unit="video_second", count=30.0)
        ue = UsageExtraction(
            state_patch={"tokens": 50},
            media_usage=(mu,),
        )
        assert ue.state_patch == {"tokens": 50}
        assert ue.media_usage == (mu,)

    def test_multiple_media_usage(self) -> None:
        from arnold.pipeline import MediaUsage, UsageExtraction

        mu1 = MediaUsage(unit="image", count=2)
        mu2 = MediaUsage(unit="audio_second", count=15)
        ue = UsageExtraction(media_usage=(mu1, mu2))
        assert ue.media_usage == (mu1, mu2)

    def test_frozen(self) -> None:
        from arnold.pipeline import UsageExtraction

        ue = UsageExtraction(state_patch={"k": "v"})
        with pytest.raises(Exception):
            ue.state_patch = {}  # type: ignore[misc]

    def test_equality(self) -> None:
        from arnold.pipeline import MediaUsage, UsageExtraction

        mu = MediaUsage(unit="image", count=1)
        a = UsageExtraction(state_patch={"t": 1}, media_usage=(mu,))
        b = UsageExtraction(state_patch={"t": 1}, media_usage=(mu,))
        assert a == b
        assert a != UsageExtraction(state_patch={"t": 2}, media_usage=(mu,))
        assert a != UsageExtraction(state_patch={"t": 1})


class TestNormalizeUsageExtraction:
    """Focused tests for normalize_usage_extraction (T7)."""

    def test_usage_extraction_returns_state_patch_and_media_usage(self) -> None:
        from arnold.pipeline import (
            MediaUsage,
            UsageExtraction,
            normalize_usage_extraction,
        )

        mu = MediaUsage(unit="image", count=2)
        ue = UsageExtraction(
            state_patch={"tokens": 100},
            media_usage=(mu,),
        )
        sp, mu_out = normalize_usage_extraction(ue)
        assert sp == {"tokens": 100}
        assert mu_out == (mu,)

    def test_usage_extraction_empty_defaults(self) -> None:
        from arnold.pipeline import UsageExtraction, normalize_usage_extraction

        ue = UsageExtraction()
        sp, mu_out = normalize_usage_extraction(ue)
        assert sp == {}
        assert mu_out == ()

    def test_legacy_dict_returns_state_patch_with_empty_media_usage(self) -> None:
        from arnold.pipeline import normalize_usage_extraction

        legacy = {"tokens": 200, "model": "claude"}
        sp, mu_out = normalize_usage_extraction(legacy)
        assert sp == {"tokens": 200, "model": "claude"}
        assert mu_out == ()

    def test_legacy_empty_dict(self) -> None:
        from arnold.pipeline import normalize_usage_extraction

        sp, mu_out = normalize_usage_extraction({})
        assert sp == {}
        assert mu_out == ()

    def test_legacy_dict_copy_not_same_object(self) -> None:
        """normalize_usage_extraction returns a copy, not the original dict."""
        from arnold.pipeline import normalize_usage_extraction

        original = {"key": "value"}
        sp, mu_out = normalize_usage_extraction(original)
        assert sp == original
        assert sp is not original  # defensive copy

    def test_legacy_dict_never_routes_to_media_usage(self) -> None:
        """Legacy dict keys are NOT interpreted as media_usage."""
        from arnold.pipeline import normalize_usage_extraction

        # A dict that happens to have a key that might look like usage
        legacy = {"media_usage": "some string", "tokens": 5}
        sp, mu_out = normalize_usage_extraction(legacy)
        # The full dict goes to state_patch — no media_usage extracted
        assert sp == {"media_usage": "some string", "tokens": 5}
        assert mu_out == ()

    def test_unrecognised_shape_returns_empty(self) -> None:
        from arnold.pipeline import normalize_usage_extraction

        sp, mu_out = normalize_usage_extraction("not a dict or UsageExtraction")
        assert sp == {}
        assert mu_out == ()

    def test_unrecognised_int_returns_empty(self) -> None:
        from arnold.pipeline import normalize_usage_extraction

        sp, mu_out = normalize_usage_extraction(42)
        assert sp == {}
        assert mu_out == ()


# ── T7: AgentStep.run + _usage_extractor returning UsageExtraction ──────────

class TestAgentStepUsageExtractionIntegration:
    """AgentStep.run handles _usage_extractor returning UsageExtraction (T7)."""

    @staticmethod
    def _make_ctx(tmp_path: Path) -> Any:
        from arnold.pipeline.types import StepContext

        return StepContext(
            artifact_root=str(tmp_path),
            state=None,
            inputs={},
            mode="test",
        )

    @staticmethod
    def _fake_worker(payload: Any = "response") -> Any:
        def _worker(**kw: Any) -> Any:
            return payload

        return _worker

    def test_extractor_returning_usage_extraction_merges_state_patch(
        self, tmp_path: Path
    ) -> None:
        """state_patch from UsageExtraction is merged correctly."""
        from arnold.pipeline import MediaUsage, UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="image", count=1)

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"tokens": 42, "model": "test"},
                media_usage=(mu,),
            )

        step = AgentStep(
            name="ue_test",
            _worker=self._fake_worker("hello"),
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"tokens": 42, "model": "test"}

    def test_extractor_returning_usage_extraction_routes_media_usage_to_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """media_usage from UsageExtraction appears in hook_metadata."""
        from arnold.pipeline import MediaUsage, UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        mu = MediaUsage(unit="video_second", count=30.0)

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(media_usage=(mu,))

        step = AgentStep(
            name="ue_media_test",
            _worker=self._fake_worker("video"),
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (mu,)

    def test_extractor_media_usage_merges_with_envelope_media_usage(
        self, tmp_path: Path
    ) -> None:
        """Envelope and extractor media_usage are concatenated."""
        from arnold.pipeline import (
            MediaUsage,
            StepInvocationResult,
            UsageExtraction,
        )
        from arnold.pipeline.steps.agent import AgentStep

        envelope_mu = MediaUsage(unit="image", count=2)
        extractor_mu = MediaUsage(unit="audio_second", count=10)

        def worker(**kw: Any) -> StepInvocationResult:
            return StepInvocationResult(
                payload="merged test",
                media_usage=(envelope_mu,),
            )

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"source": "extractor"},
                media_usage=(extractor_mu,),
            )

        step = AgentStep(
            name="merge_test",
            _worker=worker,
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (envelope_mu, extractor_mu)
        assert result.state_patch == {"source": "extractor"}

    def test_extractor_returning_usage_extraction_empty_media_usage(
        self, tmp_path: Path
    ) -> None:
        """UsageExtraction with empty media_usage + no envelope → no key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(state_patch={"k": "v"}, media_usage=())

        step = AgentStep(
            name="ue_empty_media",
            _worker=self._fake_worker("plain"),
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata
        assert result.state_patch == {"k": "v"}

    def test_extractor_only_state_patch_no_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """UsageExtraction with only state_patch does not add hook_metadata key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(state_patch={"cost": 0.05})

        step = AgentStep(
            name="ue_state_only",
            _worker=self._fake_worker("data"),
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata
        assert result.state_patch == {"cost": 0.05}

    def test_legacy_dict_extractor_still_only_updates_state_patch(
        self, tmp_path: Path
    ) -> None:
        """Legacy dict extractor never puts anything into hook_metadata."""
        from arnold.pipeline.steps.agent import AgentStep

        def legacy_extractor(**kw: Any) -> dict:
            return {"tokens": 99, "media_usage": "not-structured"}

        step = AgentStep(
            name="legacy_test",
            _worker=self._fake_worker("legacy"),
            _usage_extractor=legacy_extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        # The entire dict goes to state_patch
        assert result.state_patch == {"tokens": 99, "media_usage": "not-structured"}
        # Nothing routes to hook_metadata
        assert "media_usage" not in result.hook_metadata

    def test_extractor_exception_does_not_block_step(
        self, tmp_path: Path
    ) -> None:
        """Extractor raising is caught; step completes with empty state_patch."""
        from arnold.pipeline.steps.agent import AgentStep

        def failing_extractor(**kw: Any) -> Any:
            raise RuntimeError("extraction failed")

        step = AgentStep(
            name="fail_test",
            _worker=self._fake_worker("ok"),
            _usage_extractor=failing_extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata
        # Contract result still produced
        assert result.contract_result is not None
        assert result.contract_result.payload["label"] == "markdown"

    def test_no_extractor_no_media_usage_key(self, tmp_path: Path) -> None:
        """Without _usage_extractor and with plain return → no media_usage."""
        from arnold.pipeline.steps.agent import AgentStep

        step = AgentStep(
            name="no_extractor",
            _worker=self._fake_worker("plain"),
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata


# ── T7: PanelReviewerStep.run + _usage_extractor returning UsageExtraction ───

class TestPanelReviewerStepUsageExtractionIntegration:
    """PanelReviewerStep.run handles _usage_extractor returning UsageExtraction (T7)."""

    @staticmethod
    def _make_ctx(tmp_path: Path) -> Any:
        from arnold.pipeline.types import StepContext

        return StepContext(
            artifact_root=str(tmp_path),
            state=None,
            inputs={},
            mode="test",
        )

    @staticmethod
    def _fake_worker(payload: Any = "panel response") -> Any:
        def _worker(**kw: Any) -> Any:
            return payload

        return _worker

    def test_extractor_returning_usage_extraction_merges_state_patch(
        self, tmp_path: Path
    ) -> None:
        """state_patch from UsageExtraction merged correctly in PanelReviewerStep."""
        from arnold.pipeline import MediaUsage, UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        mu = MediaUsage(unit="image", count=3)

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"input_tokens": 77, "output_tokens": 23},
                media_usage=(mu,),
            )

        step = PanelReviewerStep(
            name="panel_review.ue",
            _worker=self._fake_worker("review"),
            _reviewer_id="ue_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"input_tokens": 77, "output_tokens": 23}

    def test_extractor_routes_media_usage_to_hook_metadata(
        self, tmp_path: Path
    ) -> None:
        """media_usage from UsageExtraction in hook_metadata for panel step."""
        from arnold.pipeline import MediaUsage, UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        mu = MediaUsage(unit="song", count=1)

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(media_usage=(mu,))

        step = PanelReviewerStep(
            name="panel_review.song",
            _worker=self._fake_worker("song review"),
            _reviewer_id="song_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (mu,)

    def test_extractor_merges_with_envelope_media_usage(
        self, tmp_path: Path
    ) -> None:
        """Envelope + extractor media_usage concatenated in panel step."""
        from arnold.pipeline import (
            MediaUsage,
            StepInvocationResult,
            UsageExtraction,
        )
        from arnold.pipeline.steps.panel import PanelReviewerStep

        env_mu = MediaUsage(unit="video_second", count=60)
        ext_mu = MediaUsage(unit="audio_second", count=20)

        def worker(**kw: Any) -> StepInvocationResult:
            return StepInvocationResult(
                payload="merged panel",
                media_usage=(env_mu,),
            )

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"reviewer": "pessimist"},
                media_usage=(ext_mu,),
            )

        step = PanelReviewerStep(
            name="panel_review.merge",
            _worker=worker,
            _reviewer_id="merge_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.hook_metadata["media_usage"] == (env_mu, ext_mu)
        assert result.state_patch == {"reviewer": "pessimist"}

    def test_legacy_dict_extractor_no_hook_metadata_leak(
        self, tmp_path: Path
    ) -> None:
        """Legacy dict in panel step does not leak into hook_metadata."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        def legacy_extractor(**kw: Any) -> dict:
            return {"input_tokens": 10, "output_tokens": 5}

        step = PanelReviewerStep(
            name="panel_review.legacy",
            _worker=self._fake_worker("legacy panel"),
            _reviewer_id="legacy_reviewer",
            _usage_extractor=legacy_extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"input_tokens": 10, "output_tokens": 5}
        assert "media_usage" not in result.hook_metadata

    def test_no_extractor_panel_step_no_media_usage_key(
        self, tmp_path: Path
    ) -> None:
        """Panel step without extractor and plain return → no media_usage key."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        step = PanelReviewerStep(
            name="panel_review.plain",
            _worker=self._fake_worker("plain"),
            _reviewer_id="plain",
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata

    def test_extractor_returning_usage_extraction_empty_media_usage(
        self, tmp_path: Path
    ) -> None:
        """Panel UsageExtraction with empty media_usage + plain worker → no key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"reviewer_tokens": 15},
                media_usage=(),
            )

        step = PanelReviewerStep(
            name="panel_review.empty_media",
            _worker=self._fake_worker("text only"),
            _reviewer_id="empty_media_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"reviewer_tokens": 15}
        assert "media_usage" not in result.hook_metadata

    def test_extractor_only_state_patch_no_hook_metadata_key(
        self, tmp_path: Path
    ) -> None:
        """Panel UsageExtraction with only state_patch → no media_usage key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(state_patch={"cost": 0.03})

        step = PanelReviewerStep(
            name="panel_review.state_only",
            _worker=self._fake_worker("data"),
            _reviewer_id="state_only_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert "media_usage" not in result.hook_metadata
        assert result.state_patch == {"cost": 0.03}

    def test_extractor_exception_does_not_block_step(
        self, tmp_path: Path
    ) -> None:
        """Panel extractor raising is caught; step completes + outputs populated."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        def failing_extractor(**kw: Any) -> Any:
            raise ValueError("panel extraction failure")

        step = PanelReviewerStep(
            name="panel_review.fail",
            _worker=self._fake_worker("ok"),
            _reviewer_id="fail_reviewer",
            _usage_extractor=failing_extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata
        # Outputs still populated (reviewer_id key)
        assert "fail_reviewer" in result.outputs
        assert result.next == "halt"


# ── T8: Legacy state-patch identity + text-only absence cross-checks ──────────

class TestLegacyExtractionStatePatchIdentity:
    """Legacy dict and UsageExtraction produce identical state_patch content (T8).

    These tests prove that upgrading a ``_usage_extractor`` from returning a
    plain ``dict`` to returning a ``UsageExtraction`` does **not** change the
    state_patch content — the same key/value pairs land in ``StepResult.state_patch``
    regardless of which path is taken.
    """

    @staticmethod
    def _make_ctx(tmp_path: Path) -> Any:
        from arnold.pipeline.types import StepContext

        return StepContext(
            artifact_root=str(tmp_path),
            state=None,
            inputs={},
            mode="test",
        )

    @staticmethod
    def _fake_worker(payload: Any = "response") -> Any:
        def _worker(**kw: Any) -> Any:
            return payload

        return _worker

    def test_agent_legacy_dict_and_usage_extraction_produce_same_state_patch(
        self, tmp_path: Path
    ) -> None:
        """AgentStep: legacy dict vs UsageExtraction → identical state_patch."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        expected = {"tokens": 150, "model": "gpt-4", "cost": 0.03}

        # Legacy dict path
        def legacy_extractor(**kw: Any) -> dict[str, Any]:
            return expected

        step_legacy = AgentStep(
            name="cmp_legacy",
            _worker=self._fake_worker("hello"),
            _usage_extractor=legacy_extractor,
        )
        result_legacy = step_legacy.run(self._make_ctx(tmp_path / "legacy"))

        # UsageExtraction path (same state_patch, no media_usage)
        def ue_extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(state_patch=dict(expected), media_usage=())

        step_ue = AgentStep(
            name="cmp_ue",
            _worker=self._fake_worker("hello"),
            _usage_extractor=ue_extractor,
        )
        result_ue = step_ue.run(self._make_ctx(tmp_path / "ue"))

        # State patches must be byte-identical
        assert result_legacy.state_patch == expected
        assert result_ue.state_patch == expected
        assert result_legacy.state_patch == result_ue.state_patch
        # Neither path emits media_usage key
        assert "media_usage" not in result_legacy.hook_metadata
        assert "media_usage" not in result_ue.hook_metadata

    def test_panel_legacy_dict_and_usage_extraction_produce_same_state_patch(
        self, tmp_path: Path
    ) -> None:
        """PanelReviewerStep: legacy dict vs UsageExtraction → identical state_patch."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        expected = {"input_tokens": 80, "output_tokens": 20}

        # Legacy dict path
        def legacy_extractor(**kw: Any) -> dict[str, Any]:
            return expected

        step_legacy = PanelReviewerStep(
            name="panel_review.cmp_legacy",
            _worker=self._fake_worker("review"),
            _reviewer_id="cmp_legacy",
            _usage_extractor=legacy_extractor,
        )
        result_legacy = step_legacy.run(self._make_ctx(tmp_path / "legacy"))

        # UsageExtraction path
        def ue_extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(state_patch=dict(expected), media_usage=())

        step_ue = PanelReviewerStep(
            name="panel_review.cmp_ue",
            _worker=self._fake_worker("review"),
            _reviewer_id="cmp_ue",
            _usage_extractor=ue_extractor,
        )
        result_ue = step_ue.run(self._make_ctx(tmp_path / "ue"))

        assert result_legacy.state_patch == expected
        assert result_ue.state_patch == expected
        assert result_legacy.state_patch == result_ue.state_patch
        assert "media_usage" not in result_legacy.hook_metadata
        assert "media_usage" not in result_ue.hook_metadata

    def test_agent_legacy_dict_unchanged_regardless_of_key_names(
        self, tmp_path: Path
    ) -> None:
        """Legacy dict with 'media'/'usage'-like keys stays entirely in state_patch."""
        from arnold.pipeline.steps.agent import AgentStep

        legacy = {"media_usage": "not-structured", "usage": {"tokens": 5}}

        def legacy_extractor(**kw: Any) -> dict[str, Any]:
            return legacy

        step = AgentStep(
            name="key_test",
            _worker=self._fake_worker("text"),
            _usage_extractor=legacy_extractor,
        )
        result = step.run(self._make_ctx(tmp_path))

        # The entire dict — including keys that look like media keys — stays in state_patch
        assert result.state_patch == legacy
        assert "media_usage" not in result.hook_metadata

    def test_panel_legacy_dict_unchanged_regardless_of_key_names(
        self, tmp_path: Path
    ) -> None:
        """Panel legacy dict with suspicious keys stays entirely in state_patch."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        legacy = {"media_usage": "should-not-leak", "count": 3}

        def legacy_extractor(**kw: Any) -> dict[str, Any]:
            return legacy

        step = PanelReviewerStep(
            name="panel_review.key_test",
            _worker=self._fake_worker("text"),
            _reviewer_id="key_reviewer",
            _usage_extractor=legacy_extractor,
        )
        result = step.run(self._make_ctx(tmp_path))

        assert result.state_patch == legacy
        assert "media_usage" not in result.hook_metadata


class TestTextOnlyStepsNoMediaKey:
    """Token/text-only steps never emit a media_usage hook metadata key (T8).

    These tests lock down the invariant that when neither the adapter envelope
    nor the ``_usage_extractor`` reports any media usage, the
    ``hook_metadata`` dict does **not** contain a ``media_usage`` key — not
    even an empty tuple value.
    """

    @staticmethod
    def _make_ctx(tmp_path: Path) -> Any:
        from arnold.pipeline.types import StepContext

        return StepContext(
            artifact_root=str(tmp_path),
            state=None,
            inputs={},
            mode="test",
        )

    @staticmethod
    def _fake_worker(payload: Any = "text response") -> Any:
        def _worker(**kw: Any) -> Any:
            return payload

        return _worker

    def test_agent_text_only_no_extractor_no_media_key(
        self, tmp_path: Path
    ) -> None:
        """AgentStep: plain text worker, no extractor → absolutely no media_usage key."""
        from arnold.pipeline.steps.agent import AgentStep

        step = AgentStep(
            name="text_only",
            _worker=self._fake_worker("just some text"),
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata
        assert result.contract_result is not None

    def test_panel_text_only_no_extractor_no_media_key(
        self, tmp_path: Path
    ) -> None:
        """PanelReviewerStep: plain text worker, no extractor → no media_usage key."""
        from arnold.pipeline.steps.panel import PanelReviewerStep

        step = PanelReviewerStep(
            name="panel_review.text_only",
            _worker=self._fake_worker("just text"),
            _reviewer_id="text_only",
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {}
        assert "media_usage" not in result.hook_metadata
        assert "text_only" in result.outputs

    def test_agent_token_extractor_only_state_patch_no_media_key(
        self, tmp_path: Path
    ) -> None:
        """AgentStep: token-only extractor (UsageExtraction, no media) → no key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.agent import AgentStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"input_tokens": 200, "output_tokens": 50},
                media_usage=(),
            )

        step = AgentStep(
            name="token_only",
            _worker=self._fake_worker("token response"),
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"input_tokens": 200, "output_tokens": 50}
        assert "media_usage" not in result.hook_metadata

    def test_panel_token_extractor_only_state_patch_no_media_key(
        self, tmp_path: Path
    ) -> None:
        """PanelReviewerStep: token-only extractor (UsageExtraction, no media) → no key."""
        from arnold.pipeline import UsageExtraction
        from arnold.pipeline.steps.panel import PanelReviewerStep

        def extractor(**kw: Any) -> UsageExtraction:
            return UsageExtraction(
                state_patch={"reviewer_tokens": 10},
                media_usage=(),
            )

        step = PanelReviewerStep(
            name="panel_review.token_only",
            _worker=self._fake_worker("review text"),
            _reviewer_id="token_reviewer",
            _usage_extractor=extractor,
        )
        ctx = self._make_ctx(tmp_path)
        result = step.run(ctx)

        assert result.state_patch == {"reviewer_tokens": 10}
        assert "media_usage" not in result.hook_metadata
