"""Known credential registry for AgentBox host backends."""

from __future__ import annotations

from typing import TypedDict


class CredentialSpec(TypedDict):
    provider: str
    env_var: str


KNOWN_CREDENTIALS: dict[str, CredentialSpec] = {
    "GITHUB_TOKEN": {"provider": "github", "env_var": "GITHUB_TOKEN"},
    "ANTHROPIC_API_KEY": {"provider": "claude", "env_var": "ANTHROPIC_API_KEY"},
    "CLAUDE_API_KEY": {"provider": "claude", "env_var": "CLAUDE_API_KEY"},
    "OPENAI_API_KEY": {"provider": "openai", "env_var": "OPENAI_API_KEY"},
    "CODEX_API_KEY": {"provider": "codex", "env_var": "CODEX_API_KEY"},
    "XAI_API_KEY": {"provider": "xai", "env_var": "XAI_API_KEY"},
    "DISCORD_BOT_TOKEN": {"provider": "discord", "env_var": "DISCORD_BOT_TOKEN"},
}


def provider_for(name: str) -> str | None:
    return KNOWN_CREDENTIALS.get(name, {}).get("provider")


__all__ = [
    "KNOWN_CREDENTIALS",
    "CredentialSpec",
    "provider_for",
]
