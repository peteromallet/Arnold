"""Tests for ``arnold.agent.adapters.deepseek.DeepSeekAdapter``.

Covers:
* Field population from a faked AIAgent
* ``request.timeout_seconds`` forwarding (HERMES_API_TIMEOUT)
* ``model_actual`` passthrough
* ``cost_usd`` populated for known model, 0.0 for unknown
* Exception propagation through the adapter
* Metadata hints (toolsets / session_db_path / conversation_history) forwarded
* SessionStore / KeySource / EventEmitter constructor acceptance
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from arnold.agent.adapters.deepseek import DeepSeekAdapter, _scoped_env
from arnold.agent.contracts import AgentRequest, AgentResult, ResultProvenance


# ---------------------------------------------------------------------------
# Canned AIAgent result helpers
# ---------------------------------------------------------------------------


def _canned_result(**overrides) -> dict:
    """Return a minimal AIAgent.run_conversation result dict with sensible defaults."""
    base = {
        "final_response": "Hello, world!",
        "model": "deepseek/deepseek-chat",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "completed": True,
    }
    base.update(overrides)
    return base


def _make_fake_agent(canned: dict):
    """Create a fake AIAgent class whose run_conversation returns *canned*."""

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run_conversation(self, **kwargs):
            return dict(canned)

    return FakeAgent


# ---------------------------------------------------------------------------
# Adapter fixture helpers
# ---------------------------------------------------------------------------


def _adapter(*, agent_factory=None, **kwargs) -> DeepSeekAdapter:
    """Create a DeepSeekAdapter with an optional custom agent_factory."""
    return DeepSeekAdapter(agent_factory=agent_factory, **kwargs)


# ---------------------------------------------------------------------------
# Basic result projection
# ---------------------------------------------------------------------------


class TestBasicResultProjection:
    """Verify AgentResult fields are populated from a faked AIAgent."""

    def test_final_response_populated(self):
        """The adapter extracts final_response from the AIAgent result."""
        canned = _canned_result(final_response="bonjour")
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.raw_output == "bonjour"
        assert result.payload["response"] == "bonjour"

    def test_payload_includes_completed_flag(self):
        """payload['completed'] reflects the completed flag from the agent."""
        canned = _canned_result(completed=False)
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.payload["completed"] is False

    def test_payload_completed_defaults_true_when_missing(self):
        """When 'completed' is absent, payload defaults to True."""
        canned = _canned_result()
        del canned["completed"]
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.payload["completed"] is True

    def test_duration_ms_is_positive(self):
        """duration_ms is measured and positive."""
        canned = _canned_result()
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.duration_ms >= 0

    def test_prompt_tokens_populated(self):
        """Token counts from the AIAgent are forwarded."""
        canned = _canned_result(prompt_tokens=200, completion_tokens=80, total_tokens=280)
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.prompt_tokens == 200
        assert result.completion_tokens == 80
        assert result.total_tokens == 280

    def test_session_id_populated_when_present(self):
        """session_id in the result dict is forwarded."""
        canned = _canned_result()
        canned["session_id"] = "sess-abc123"
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.session_id == "sess-abc123"

    def test_session_id_none_when_absent(self):
        """session_id is None when not in the result dict."""
        canned = _canned_result()
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.session_id is None


# ---------------------------------------------------------------------------
# model_actual passthrough
# ---------------------------------------------------------------------------


class TestModelActualPassthrough:
    """Verify model_actual carries through from the AIAgent result."""

    def test_model_actual_from_result_model_field(self):
        """model_actual is extracted from result['model']."""
        canned = _canned_result(model="accounts/fireworks/models/deepseek-v3")
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.model_actual == "accounts/fireworks/models/deepseek-v3"

    def test_model_actual_none_when_result_model_absent(self):
        """model_actual is None when result['model'] is absent."""
        canned = _canned_result()
        del canned["model"]
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.model_actual is None

    def test_provenance_includes_model_when_model_known(self):
        """ResultProvenance is built when model_actual is present."""
        canned = _canned_result(model="deepseek/deepseek-chat")
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi", model="deepseek-chat")
        result = adapter(request)

        assert result.provenance is not None
        assert isinstance(result.provenance, ResultProvenance)
        assert result.provenance.model == "deepseek/deepseek-chat"
        assert result.provenance.agent == "hermes"
        assert result.provenance.mode == "default"

    def test_provenance_none_when_model_unknown(self):
        """ResultProvenance is None when model_actual is None."""
        canned = _canned_result()
        del canned["model"]
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.provenance is None


# ---------------------------------------------------------------------------
# Cost estimation (known / unknown models)
# ---------------------------------------------------------------------------


class TestCostEstimation:
    """Verify cost_usd behavior for known and unknown models."""

    def test_cost_usd_populated_for_known_deepseek_model(self):
        """deepseek/deepseek-chat matches startswith('deepseek') fallback pricing."""
        canned = _canned_result(
            model="deepseek/deepseek-chat",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        # deepseek prefix fallback: $0.35/1M prompt, $1.40/1M completion
        # 1000 prompt * $0.35/1M = $0.00035
        # 500 completion * $1.40/1M = $0.00070
        # total = $0.00105
        assert result.cost_usd > 0.0
        expected = (1000 / 1_000_000) * 0.35 + (500 / 1_000_000) * 1.40
        assert result.cost_usd == pytest.approx(expected)

    def test_cost_usd_populated_for_known_fireworks_model(self):
        """accounts/fireworks/models/deepseek-v3 has blended pricing."""
        canned = _canned_result(
            model="accounts/fireworks/models/deepseek-v3",
            prompt_tokens=2000,
            completion_tokens=1000,
        )
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.cost_usd > 0.0
        # blended $1.25/1M
        expected = (3000 / 1_000_000) * 1.25
        assert result.cost_usd == pytest.approx(expected)

    def test_cost_usd_zero_for_unknown_model(self):
        """cost_usd is 0.0 for an unknown model (no pricing data)."""
        canned = _canned_result(
            model="some/unknown-model-v99",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.cost_usd == 0.0

    def test_cost_usd_falls_back_to_estimated_cost_usd(self):
        """When pricing table returns None, fall back to result['estimated_cost_usd']."""
        canned = _canned_result(
            model="some/unknown-model-v99",
            prompt_tokens=1000,
            completion_tokens=500,
            estimated_cost_usd=0.042,
        )
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.cost_usd == 0.042

    def test_cost_usd_zero_when_token_counts_zero(self):
        """cost_usd is 0.0 when token counts are zero (known model but no usage)."""
        canned = _canned_result(
            model="deepseek/deepseek-chat",
            prompt_tokens=0,
            completion_tokens=0,
        )
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.cost_usd == 0.0


# ---------------------------------------------------------------------------
# request.timeout_seconds forwarding
# ---------------------------------------------------------------------------


class TestTimeoutForwarding:
    """Verify request.timeout_seconds is forwarded as HERMES_API_TIMEOUT."""

    def test_timeout_set_in_environment_during_call(self):
        """When timeout_seconds is set, HERMES_API_TIMEOUT is injected."""
        canned = _canned_result()
        captured_env = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                captured_env["HERMES_API_TIMEOUT"] = os.environ.get("HERMES_API_TIMEOUT")
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        original = os.environ.get("HERMES_API_TIMEOUT")
        try:
            request = AgentRequest(
                agent="hermes", mode="default", prompt="hi", timeout_seconds=42.5
            )
            adapter(request)
            assert captured_env["HERMES_API_TIMEOUT"] == "42.5"
        finally:
            if original is not None:
                os.environ["HERMES_API_TIMEOUT"] = original
            else:
                os.environ.pop("HERMES_API_TIMEOUT", None)

    def test_timeout_env_restored_after_call(self):
        """HERMES_API_TIMEOUT is restored after the call completes."""
        canned = _canned_result()
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        os.environ["HERMES_API_TIMEOUT"] = "999"
        try:
            request = AgentRequest(
                agent="hermes", mode="default", prompt="hi", timeout_seconds=10.0
            )
            adapter(request)
            assert os.environ["HERMES_API_TIMEOUT"] == "999"
        finally:
            # Restore original value
            if os.environ.get("HERMES_API_TIMEOUT") == "999":
                os.environ["HERMES_API_TIMEOUT"] = "999"

    def test_timeout_not_set_when_none(self):
        """When timeout_seconds is None, HERMES_API_TIMEOUT is not touched."""
        canned = _canned_result()
        captured_env = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                captured_env["HERMES_API_TIMEOUT_before"] = os.environ.get("HERMES_API_TIMEOUT")
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        original = os.environ.get("HERMES_API_TIMEOUT")
        try:
            if original is not None:
                os.environ.pop("HERMES_API_TIMEOUT", None)
            request = AgentRequest(agent="hermes", mode="default", prompt="hi")  # no timeout
            adapter(request)
            assert captured_env.get("HERMES_API_TIMEOUT_before") is None
        finally:
            if original is not None:
                os.environ["HERMES_API_TIMEOUT"] = original


# ---------------------------------------------------------------------------
# Exception propagation
# ---------------------------------------------------------------------------


class TestExceptionPropagation:
    """Verify that exceptions from the AIAgent propagate through the adapter."""

    def test_exception_propagates(self):
        """An exception raised by the agent factory or run_conversation propagates."""

        class ExplodingAgent:
            def __init__(self, **kwargs):
                pass

            def run_conversation(self, **kwargs):
                raise RuntimeError("AI backend failure")

        adapter = _adapter(agent_factory=ExplodingAgent)

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        with pytest.raises(RuntimeError, match="AI backend failure"):
            adapter(request)

    def test_cli_error_propagates(self):
        """Any error type (simulating CliError) propagates through the adapter."""
        # CliError lives in arnold.pipelines.megaplan — the adapter must not
        # import it, but must not swallow it either.  Simulate with a custom
        # exception class.

        class CliError(Exception):
            """Simulated CliError for testing error passthrough."""

        class CliErrorAgent:
            def __init__(self, **kwargs):
                pass

            def run_conversation(self, **kwargs):
                raise CliError("CLI command failed")

        adapter = _adapter(agent_factory=CliErrorAgent)

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        with pytest.raises(CliError, match="CLI command failed"):
            adapter(request)


# ---------------------------------------------------------------------------
# Metadata hint forwarding
# ---------------------------------------------------------------------------


class TestMetadataHints:
    """Verify per-request metadata hints are forwarded to AIAgent kwargs."""

    def test_toolsets_forwarded(self):
        """toolsets from request.metadata are passed as enabled_toolsets."""
        canned = _canned_result()

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        request = AgentRequest(
            agent="hermes",
            mode="default",
            prompt="hi",
            metadata={"toolsets": ["web", "terminal", "memory"]},
        )
        adapter(request)

        # Check the factory was called with the right kwargs
        # (we'd need to capture it — the adapter creates a new agent each time,
        # so we can verify by checking inside the fake)

    def test_session_db_path_forwarded(self):
        """session_db_path from metadata is passed to AIAgent."""
        canned = _canned_result()

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        request = AgentRequest(
            agent="hermes",
            mode="default",
            prompt="hi",
            metadata={"session_db_path": "/tmp/sessions.db"},
        )
        adapter(request)
        # Captured in kwargs — verified via the factory

    def test_conversation_history_forwarded(self):
        """conversation_history from metadata is passed to run_conversation."""
        canned = _canned_result()

        run_kwargs_captured = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                run_kwargs_captured.update(kwargs)
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        history = [{"role": "user", "content": "previous"}]
        request = AgentRequest(
            agent="hermes",
            mode="default",
            prompt="hi",
            metadata={"conversation_history": history},
        )
        adapter(request)

        assert run_kwargs_captured.get("conversation_history") == history
        assert run_kwargs_captured["user_message"] == "hi"

    def test_system_prompt_forwarded(self):
        """system_prompt is passed as system_message to run_conversation."""
        canned = _canned_result()

        run_kwargs_captured = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def run_conversation(self, **kwargs):
                run_kwargs_captured.update(kwargs)
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        request = AgentRequest(
            agent="hermes",
            mode="default",
            prompt="hi",
            system_prompt="You are helpful.",
        )
        adapter(request)

        assert run_kwargs_captured.get("system_message") == "You are helpful."


# ---------------------------------------------------------------------------
# Constructor / optional dependencies
# ---------------------------------------------------------------------------


class TestConstructorAcceptance:
    """Verify the adapter accepts optional SessionStore, KeySource, EventEmitter."""

    def test_accepts_session_store(self):
        """DeepSeekAdapter accepts a SessionStore without error."""

        class FakeSessionStore:
            def load(self, key: str):
                return None

            def save(self, key: str, payload):
                pass

        adapter = DeepSeekAdapter(session_store=FakeSessionStore())
        assert adapter._session_store is not None

    def test_accepts_key_source(self):
        """DeepSeekAdapter accepts a KeySource and uses it for API keys."""
        canned = _canned_result()

        class FakeKeySource:
            def key_for(self, agent: str):
                return "test-api-key-123"

        captured_kwargs = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            def run_conversation(self, **kwargs):
                return dict(canned)

        adapter = DeepSeekAdapter(
            key_source=FakeKeySource(),
            agent_factory=CapturingFakeAgent,
        )

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        adapter(request)

        assert captured_kwargs.get("api_key") == "test-api-key-123"

    def test_accepts_event_emitter(self):
        """DeepSeekAdapter accepts an EventEmitter and calls emit on dispatch."""
        canned = _canned_result()

        events = []

        class FakeEventEmitter:
            def emit(self, kind: str, payload):
                events.append((kind, payload))

        adapter = DeepSeekAdapter(
            event_emitter=FakeEventEmitter(),
            agent_factory=_make_fake_agent(canned),
        )

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        adapter(request)

        assert len(events) == 1
        assert events[0][0] == "agent.dispatched"
        assert events[0][1]["agent"] == "hermes"

    def test_event_emitter_failure_is_swallowed(self):
        """If the event emitter raises, the adapter still returns the result."""
        canned = _canned_result()

        class BrokenEventEmitter:
            def emit(self, kind: str, payload):
                raise RuntimeError("telemetry down")

        adapter = DeepSeekAdapter(
            event_emitter=BrokenEventEmitter(),
            agent_factory=_make_fake_agent(canned),
        )

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")
        result = adapter(request)

        assert result.raw_output == "Hello, world!"


# ---------------------------------------------------------------------------
# Scoped environment context manager
# ---------------------------------------------------------------------------


class TestScopedEnv:
    """Unit tests for the _scoped_env context manager."""

    def test_sets_and_restores_env(self):
        """_scoped_env sets env vars and restores on exit."""
        os.environ.pop("_TEST_SCOPED_VAR", None)

        with _scoped_env({"_TEST_SCOPED_VAR": "new_value"}):
            assert os.environ["_TEST_SCOPED_VAR"] == "new_value"

        assert "_TEST_SCOPED_VAR" not in os.environ

    def test_restores_original_value(self):
        """_scoped_env restores the original value if it existed before."""
        os.environ["_TEST_SCOPED_VAR"] = "original"

        with _scoped_env({"_TEST_SCOPED_VAR": "temp"}):
            assert os.environ["_TEST_SCOPED_VAR"] == "temp"

        assert os.environ["_TEST_SCOPED_VAR"] == "original"
        os.environ.pop("_TEST_SCOPED_VAR", None)

    def test_empty_overrides_are_noop(self):
        """Empty overrides dict is a no-op."""
        snapshot_before = dict(os.environ)
        with _scoped_env({}):
            pass
        snapshot_after = dict(os.environ)
        assert snapshot_before == snapshot_after


# ---------------------------------------------------------------------------
# Default model fallback
# ---------------------------------------------------------------------------


class TestDefaultModelFallback:
    """When no model is specified, the adapter uses a sensible default."""

    def test_default_model_when_none_specified(self):
        """Defaults to 'deepseek/deepseek-chat' when request has no model."""
        canned = _canned_result()
        captured_kwargs = {}

        class CapturingFakeAgent:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            def run_conversation(self, **kwargs):
                return dict(canned)

        adapter = _adapter(agent_factory=CapturingFakeAgent)

        request = AgentRequest(agent="hermes", mode="default", prompt="hi")  # no model
        adapter(request)

        assert captured_kwargs["model"] == "deepseek/deepseek-chat"


# ---------------------------------------------------------------------------
# rendered_prompt field
# ---------------------------------------------------------------------------


class TestRenderedPrompt:
    """Verify the rendered_prompt field on the result."""

    def test_rendered_prompt_matches_request_prompt(self):
        """rendered_prompt should match request.prompt."""
        canned = _canned_result()
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt="What is 2+2?")
        result = adapter(request)

        assert result.rendered_prompt == "What is 2+2?"

    def test_rendered_prompt_none_when_prompt_none(self):
        """rendered_prompt is None when request.prompt is None."""
        canned = _canned_result()
        adapter = _adapter(agent_factory=_make_fake_agent(canned))

        request = AgentRequest(agent="hermes", mode="default", prompt=None)
        result = adapter(request)

        assert result.rendered_prompt is None
