from __future__ import annotations

from arnold.pipelines.megaplan.chain import ChainSpec, MilestoneSpec
from arnold.pipelines.megaplan.cloud.preflight import (
    AGENTS_DEFAULT_WARNING,
    resolve_cloud_chain_runtime_dependencies,
)


def test_cloud_chain_dependency_resolution_uses_profile_despite_cloud_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")
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
    # Post-cutover Shannon runs from megaplan/vendor/shannon via bun — no ``shannon``
    # binary on PATH, so it is no longer a required runtime command.
    assert result["runtime_commands"] == ["bun", "claude", "tmux"]
    assert result["env_hints"] == ["ANTHROPIC_API_KEY"]
    assert result["milestones"][0]["profile"] == "premium"
    assert result["milestones"][0]["resolved_phase_map"]["execute"] == "claude:low"


def test_cloud_chain_dependency_resolution_honors_phase_model_override(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")
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


def test_cloud_chain_no_profile_codex_vendor_requires_only_openai(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[MilestoneSpec(label="m1", idea="idea.txt", vendor="codex")],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert result["required_agents"] == ["codex", "hermes"]
    assert result["runtime_commands"] == ["codex", "tmux"]
    assert result["env_hints"] == ["OPENAI_API_KEY"]
    resolved = result["milestones"][0]["resolved_phase_map"]
    assert resolved["prep"] == "hermes"
    assert resolved["execute"] == "codex"
    assert resolved["feedback"] == "codex:low"
    assert all(not spec.startswith("premium") for spec in resolved.values())


def test_cloud_chain_no_profile_claude_vendor_requires_only_anthropic(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "codex")
    chain_spec = ChainSpec(
        milestones=[MilestoneSpec(label="m1", idea="idea.txt", vendor="claude")],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert result["required_agents"] == ["claude", "hermes"]
    assert result["runtime_commands"] == ["bun", "claude", "tmux"]
    assert result["env_hints"] == ["ANTHROPIC_API_KEY"]
    resolved = result["milestones"][0]["resolved_phase_map"]
    assert resolved["prep"] == "hermes"
    assert resolved["execute"] == "claude"
    assert resolved["feedback"] == "claude:low"
    assert all(not spec.startswith("premium") for spec in resolved.values())


def test_cloud_chain_default_fallback_resolves_symbolic_defaults_to_config_vendor(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "codex")
    chain_spec = ChainSpec(
        milestones=[MilestoneSpec(label="m1", idea="idea.txt")],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert result["required_agents"] == ["codex", "hermes"]
    assert result["runtime_commands"] == ["codex", "tmux"]
    assert result["env_hints"] == ["OPENAI_API_KEY"]
    resolved = result["milestones"][0]["resolved_phase_map"]
    assert resolved["prep"] == "hermes"
    assert resolved["execute"] == "codex"
    assert resolved["feedback"] == "codex:low"
    assert all(not spec.startswith("premium") for spec in resolved.values())


def test_cloud_chain_dependency_resolution_reports_hermes_provider_without_binary(
    monkeypatch,
) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")
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


def test_cloud_chain_codex_vendor_premium_profile_requires_only_openai(
    monkeypatch,
) -> None:
    """Vendor-neutral premium profile with codex vendor → only OpenAI env."""
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="premium",
                vendor="codex",
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert result["runtime_commands"] == ["codex", "tmux"]
    assert result["env_hints"] == ["OPENAI_API_KEY"]
    assert "ANTHROPIC_API_KEY" not in result["env_hints"]
    assert result["required_agents"] == ["codex"]
    milestone = result["milestones"][0]
    assert milestone["resolved_phase_map"]["execute"] == "codex:low"
    assert milestone["required_agents"] == ["codex"]


def test_cloud_chain_claude_vendor_premium_profile_requires_only_anthropic(
    monkeypatch,
) -> None:
    """Vendor-neutral premium profile with claude vendor → only Anthropic env."""
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "codex")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="premium",
                vendor="claude",
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert result["runtime_commands"] == ["bun", "claude", "tmux"]
    assert result["env_hints"] == ["ANTHROPIC_API_KEY"]
    assert "OPENAI_API_KEY" not in result["env_hints"]
    assert result["required_agents"] == ["claude"]
    milestone = result["milestones"][0]
    assert milestone["resolved_phase_map"]["execute"] == "claude:low"
    assert milestone["required_agents"] == ["claude"]


def test_cloud_chain_apex_profile_reports_both_providers(
    monkeypatch,
) -> None:
    """Mixed apex profile requires both Anthropic and OpenAI."""
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="apex",
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    assert "claude" in result["runtime_commands"]
    assert "codex" in result["runtime_commands"]
    assert "bun" in result["runtime_commands"]
    assert "tmux" in result["runtime_commands"]
    assert "ANTHROPIC_API_KEY" in result["env_hints"]
    assert "OPENAI_API_KEY" in result["env_hints"]
    assert "claude" in result["required_agents"]
    assert "codex" in result["required_agents"]


def test_cloud_chain_explicit_codex_pins_override_claude_vendor(
    monkeypatch,
) -> None:
    """Concrete codex phase_model pins → OPENAI_API_KEY even under claude vendor."""
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="premium",
                vendor="claude",
                phase_model=["execute=codex:high"],
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    milestone = result["milestones"][0]
    assert milestone["resolved_phase_map"]["execute"] == "codex:high"
    assert "codex" in result["runtime_commands"]
    assert "OPENAI_API_KEY" in result["env_hints"]


def test_cloud_chain_explicit_claude_pins_override_codex_vendor(
    monkeypatch,
) -> None:
    """Concrete claude phase_model pins → ANTHROPIC_API_KEY even under codex vendor."""
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "codex")
    chain_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="idea.txt",
                profile="premium",
                vendor="codex",
                phase_model=["execute=claude:high"],
            )
        ],
    )

    result = resolve_cloud_chain_runtime_dependencies(chain_spec)

    milestone = result["milestones"][0]
    assert milestone["resolved_phase_map"]["execute"] == "claude:high"
    assert "claude" in result["runtime_commands"]
    assert "ANTHROPIC_API_KEY" in result["env_hints"]
