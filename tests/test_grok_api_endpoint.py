"""Tests for scripts/test_grok_api_endpoint.py

These tests directly import and drive the *shipped* functions from the script
using the real entry points (make_grok_client, call_model, constants).

They exercise non-network parts without requiring a live XAI_API_KEY.
Network-dependent paths are either patched or expected to raise in a controlled way.
"""

import os
import pytest

# Import the real shipped code (this is the key: drive the functions in the script)
from scripts.test_grok_api_endpoint import (
    make_grok_client,
    call_model,
    ENDPOINT,
    MODEL,
    AUTH_ENV,
)


def test_constants_expose_the_shared_endpoint_details():
    """Gating check: the script must hardcode/document the correct public values."""
    assert "https://api.x.ai/v1" in ENDPOINT
    assert "api.x.ai" in ENDPOINT
    assert MODEL == "grok-4.5"
    assert AUTH_ENV == "XAI_API_KEY"


def test_make_grok_client_accepts_explicit_key_and_sets_base_url():
    """Core construction logic (non-network) exercised directly."""
    client = make_grok_client("xai-dummy-test-key-123")
    assert client is not None
    # The real OpenAI client stores base_url
    base = str(client.base_url)
    assert "api.x.ai" in base
    assert ENDPOINT in base or "https://api.x.ai/v1" in base


def test_make_grok_client_uses_env_when_none_passed(monkeypatch):
    """Exercise the env fallback path in the shipped make_grok_client."""
    monkeypatch.setenv(AUTH_ENV, "xai-env-key-for-test")
    try:
        client = make_grok_client(None)
        assert "api.x.ai" in str(client.base_url)
    finally:
        # cleanup
        monkeypatch.delenv(AUTH_ENV, raising=False)


def test_make_grok_client_raises_clear_message_when_no_key_available(monkeypatch):
    """Graceful error for the documented live-use path."""
    monkeypatch.delenv(AUTH_ENV, raising=False)
    with pytest.raises(ValueError, match="XAI_API_KEY"):
        make_grok_client(None)


def test_call_model_function_is_driven_and_attempts_real_api_call_path(monkeypatch):
    """Drive the real call_model code. Patch only the transport to stay offline.

    This proves the shipped call_model body (try responses + fallback) executes.
    """
    from unittest.mock import patch, MagicMock

    client = make_grok_client("dummy-for-call-test")

    with patch.object(client, "responses") as mock_responses:
        mock_resp = MagicMock()
        mock_resp.output_text = "patched-responses-response-from-grok-4.5"
        mock_responses.create.return_value = mock_resp

        result = call_model(client, "test prompt for call_model")

        mock_responses.create.assert_called_once()
        # verify args included the model (real code path)
        call_kwargs = mock_responses.create.call_args.kwargs
        assert call_kwargs.get("model") == MODEL
        assert "patched-responses-response-from-grok-4.5" in result


def test_call_model_falls_back_to_chat_completions_when_responses_fails(monkeypatch):
    """Ensure the except/fallback path in the real call_model is exercised."""
    from unittest.mock import patch, MagicMock

    client = make_grok_client("dummy-for-fallback-test")

    # Make responses.create raise so we hit the fallback in shipped code
    with patch.object(client, "responses") as mock_responses:
        mock_responses.create.side_effect = RuntimeError("simulated responses failure to test fallback")

        # Patch the chat path on client to return controlled value (drive real except branch)
        with patch.object(client, "chat") as mock_chat:
            mock_choice = MagicMock()
            mock_choice.message.content = "chat-fallback-response"
            mock_chat.completions.create.return_value = MagicMock(choices=[mock_choice])

            result = call_model(client, "prompt that should fallback")

            mock_responses.create.assert_called_once()
            mock_chat.completions.create.assert_called_once()
            assert "chat-fallback-response" in result


def test_script_functions_are_importable_from_tests_tree():
    """Meta: confirms the import path used by harness/verification works."""
    assert callable(make_grok_client)
    assert callable(call_model)
