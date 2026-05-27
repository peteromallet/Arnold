from __future__ import annotations

from megaplan.chain import ChainSpec, MilestoneSpec
from megaplan.cloud.preflight import (
    AGENTS_DEFAULT_WARNING,
    resolve_cloud_chain_runtime_dependencies,
)


def test_cloud_chain_dependency_resolution_uses_profile_despite_cloud_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr("megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        base_branch="setup/cloud",
        milestones=[MilestoneSpec(label="m1", idea="idea.txt", profile="premium")],
    )

    result = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        cloud_default_agent="codex",
    )

    assert result["base_branch"] == "setup/cloud"
    assert result["cloud_default_agent"] == "codex"
    assert result["warning"] == AGENTS_DEFAULT_WARNING
    assert result["runtime_commands"] == ["bun", "claude", "shannon", "tmux"]
    assert result["env_hints"] == ["ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]
    assert result["milestones"][0]["profile"] == "premium"
    assert result["milestones"][0]["resolved_phase_map"]["execute"] == "claude:low"


def test_cloud_chain_dependency_resolution_honors_phase_model_override(
    monkeypatch,
) -> None:
    monkeypatch.setattr("megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="premium",
                phase_model=["execute=codex:medium"],
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    milestone = result["milestones"][0]
    assert milestone["explicit_phase_model"] == ["execute=codex:medium"]
    assert milestone["resolved_phase_map"]["execute"] == "codex:medium"
    assert "codex" in milestone["required_agents"]
    assert "codex" in result["runtime_commands"]
    assert "OPENAI_API_KEY" in result["env_hints"]


def test_cloud_chain_dependency_resolution_uses_cloud_default_when_chain_has_no_explicit_route() -> None:
    chain_spec = ChainSpec(
        milestones=[MilestoneSpec(label="m1", idea="idea.txt")],
    )

    result = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        cloud_default_agent="codex",
    )

    assert result["required_agents"] == ["codex"]
    assert result["runtime_commands"] == ["codex", "tmux"]
    assert result["env_hints"] == ["OPENAI_API_KEY"]
    assert set(result["milestones"][0]["resolved_phase_map"].values()) == {"codex"}


def test_cloud_chain_dependency_resolution_reports_hermes_provider_without_binary(
    monkeypatch,
) -> None:
    monkeypatch.setattr("megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                phase_model=["execute=hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"],
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert "hermes" in result["required_agents"]
    assert "hermes" not in result["runtime_commands"]
    assert {
        "agent": "hermes",
        "provider": "fireworks",
        "model": "accounts/fireworks/models/deepseek-v4-pro",
        "env_hints": ["FIREWORKS_API_KEY"],
    } in result["provider_requirements"]
    assert "FIREWORKS_API_KEY" in result["env_hints"]


def test_cloud_chain_dependency_resolution_reports_direct_deepseek_env_hint() -> None:
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                phase_model=["execute=hermes:deepseek:deepseek-v4-pro"],
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert {
        "agent": "hermes",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "env_hints": ["DEEPSEEK_API_KEY"],
    } in result["provider_requirements"]
    assert "DEEPSEEK_API_KEY" in result["env_hints"]
