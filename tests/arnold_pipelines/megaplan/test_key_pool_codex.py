"""Codex (ChatGPT-subscription) provider resolution for hermes agents.

Covers the ``codex:`` prefix in megaplan's resolve_model: GPT-5.x models run
through the chatgpt.com/backend-api/codex endpoint using the live Codex CLI
OAuth token (same subscription as ``codex exec``, no API key), plus the
runtime reconstruction of streamed output items the codex backend omits from
its final response.
"""

from types import SimpleNamespace

import pytest

from arnold.agent.hermes_cli import auth as hermes_auth
from arnold.agent.run_agent import AIAgent
from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
from arnold_pipelines.megaplan.types import CliError


def _live_cli_tokens() -> dict:
    return {"access_token": "cli-live-token", "refresh_token": "cli-refresh"}


class TestResolveModelCodex:
    def test_resolves_codex_spec_to_subscription_backend(self, monkeypatch) -> None:
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", _live_cli_tokens)
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: False)

        model, kwargs = resolve_model("codex:gpt-5.6-sol:high")

        assert model == "gpt-5.6-sol"
        assert kwargs["provider"] == "openai-codex"
        assert kwargs["base_url"] == "https://chatgpt.com/backend-api/codex"
        assert kwargs["api_key"] == "cli-live-token"
        assert kwargs["reasoning_config"] == {"enabled": True, "effort": "high"}

    def test_codex_spec_without_effort(self, monkeypatch) -> None:
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", _live_cli_tokens)
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: False)

        model, kwargs = resolve_model("codex:gpt-5.5")

        assert model == "gpt-5.5"
        assert kwargs["provider"] == "openai-codex"
        assert "reasoning_config" not in kwargs

    def test_codex_xhigh_maps_to_high(self, monkeypatch) -> None:
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", _live_cli_tokens)
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: False)

        _, kwargs = resolve_model("codex:gpt-5.6-sol:xhigh")

        assert kwargs["reasoning_config"]["effort"] == "high"

    def test_codex_spec_without_credentials_raises(self, monkeypatch) -> None:
        def broken(*_a, **_k):
            raise hermes_auth.AuthError(
                "no session", provider="openai-codex", code="codex_auth_missing", relogin_required=True
            )

        monkeypatch.setattr(hermes_auth, "resolve_codex_runtime_credentials", broken)

        with pytest.raises(CliError) as exc_info:
            resolve_model("codex:gpt-5.6-sol")
        assert exc_info.value.code == "codex_auth_unavailable"

    def test_bare_gpt5_still_blocks_openrouter(self) -> None:
        with pytest.raises(CliError) as exc_info:
            resolve_model("gpt-5.5")
        assert exc_info.value.code == "codex_via_openrouter_blocked"


class TestCodexCredentialResolution:
    def test_prefers_live_cli_token(self, monkeypatch) -> None:
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", _live_cli_tokens)
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: False)

        creds = hermes_auth.resolve_codex_runtime_credentials()

        assert creds["api_key"] == "cli-live-token"
        assert creds["source"] == "codex-cli-live"
        assert creds["provider"] == "openai-codex"

    def test_refreshes_cli_token_in_place_when_expiring(self, monkeypatch) -> None:
        saved: dict = {}
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", _live_cli_tokens)
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: True)
        monkeypatch.setattr(
            hermes_auth,
            "_codex_oauth_refresh",
            lambda _rt, _timeout: {"access_token": "fresh-token", "refresh_token": "fresh-refresh"},
        )
        monkeypatch.setattr(hermes_auth, "_save_codex_cli_tokens", lambda tokens: saved.update(tokens))

        creds = hermes_auth.resolve_codex_runtime_credentials()

        assert creds["api_key"] == "fresh-token"
        assert saved.get("access_token") == "fresh-token"
        assert saved.get("refresh_token") == "fresh-refresh"

    def test_falls_back_to_hermes_store_without_cli(self, monkeypatch) -> None:
        monkeypatch.setattr(hermes_auth, "_import_codex_cli_tokens", lambda: None)
        monkeypatch.setattr(
            hermes_auth,
            "_read_codex_tokens",
            lambda **_k: {"tokens": {"access_token": "store-token", "refresh_token": "store-refresh"}, "last_refresh": "x"},
        )
        monkeypatch.setattr(hermes_auth, "_codex_access_token_is_expiring", lambda *a: False)

        creds = hermes_auth.resolve_codex_runtime_credentials()

        assert creds["api_key"] == "store-token"
        assert creds["source"] == "hermes-auth-store"


class TestCodexEmptyOutputReconstruction:
    def test_reattaches_streamed_output_items(self) -> None:
        response = SimpleNamespace(output=[], status="completed", model="gpt-5.6-sol")
        item = SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text="OMP_GPT_OK")])

        fixed = AIAgent._ensure_codex_output_items(response, [item])

        assert fixed is response
        assert fixed.output == [item]

    def test_leaves_nonempty_output_untouched(self) -> None:
        existing = [SimpleNamespace(type="message")]
        response = SimpleNamespace(output=existing)

        fixed = AIAgent._ensure_codex_output_items(response, [])

        assert fixed is response
        assert fixed.output is existing
