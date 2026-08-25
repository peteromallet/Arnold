"""Provider catalog for first-run onboarding.

Single source of truth for the providers Arnold offers at first run, ordered
by ``RANK_ORDER`` (found-first onboarding shows the top of this list first).

The ``env_keys`` of every provider that appears in
``arnold_pipelines.megaplan.workers.omp._OMP_CREDENTIAL_ENV`` MUST match that
table exactly; ``tests/agentbox/test_onboarding_detect.py`` imports the worker
table and asserts parity in both directions so the two cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ways a provider's credentials can be wired into omp:
#   env        - key present in the process environment or an omp-loaded .env
#   api_key    - static key persisted into omp's own stores (agent.db / models.yml)
#   oauth      - OAuth login resolved from omp's own store (agent.db auth_credentials)
#   cli_proxy  - foreign CLI's own credential store referenced by omp (grok CLI,
#                command-backed models.yml apiKey)
AUTH_KINDS = frozenset({"env", "api_key", "oauth", "cli_proxy"})

# Found-first display rank: proven Arnold routes first, long-tail catalog
# providers after.
RANK_ORDER: tuple[str, ...] = (
    "deepseek",
    "openrouter",
    "xai",
    "anthropic",
    "kimi-code",
    "zai",
    "moonshot",
    "fireworks",
    "openai-codex",
    "grok",
    # Long tail — present in the oh-my-pi fork catalog
    # (packages/catalog/src/provider-models/descriptors.ts) but not yet wired
    # by an Arnold worker route.
    "google",
    "openai",
    "minimax",
    "perplexity",
)


@dataclass(frozen=True)
class ProviderSpec:
    """One onboarding-able provider.

    ``default_route`` is the canonical ``provider/model`` route offered when
    nothing better is known; values mirror
    ``arnold_pipelines.megaplan.workers.omp._OMP_CATALOG_MODELS`` for ranked
    providers and the fork catalog ``defaultModel`` for the tail.
    """

    id: str
    env_keys: tuple[str, ...]
    default_route: str
    auth_kinds: frozenset[str]


PROVIDERS: dict[str, ProviderSpec] = {
    spec.id: spec
    for spec in (
        ProviderSpec(
            id="deepseek",
            env_keys=("DEEPSEEK_API_KEY",),
            default_route="deepseek/deepseek-v4-flash",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="openrouter",
            env_keys=("OPENROUTER_API_KEY",),
            default_route="openrouter/openai/gpt-5.5",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="xai",
            env_keys=("XAI_API_KEY",),
            default_route="xai/grok-4-fast-non-reasoning",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="anthropic",
            env_keys=("ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"),
            default_route="anthropic/claude-opus-4-8",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        # omp-native credential route: omp also resolves kimi credentials from
        # its own store (OAuth / CLI login), so no Arnold env gate applies —
        # but KIMI_API_KEY remains accepted (workers.omp._OMP_CREDENTIAL_ENV).
        ProviderSpec(
            id="kimi-code",
            env_keys=("KIMI_API_KEY",),
            default_route="kimi-code/kimi-for-coding",
            auth_kinds=frozenset({"env", "api_key", "oauth"}),
        ),
        ProviderSpec(
            id="zai",
            env_keys=("ZAI_API_KEY", "ZHIPU_API_KEY"),
            default_route="zai/glm-5.2",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="moonshot",
            env_keys=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
            default_route="moonshot/kimi-k2.7-code",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="fireworks",
            env_keys=("FIREWORKS_API_KEY",),
            default_route="fireworks/kimi-k2.7-code",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        # omp-native credential route: ChatGPT-subscription OAuth resolved
        # from omp's agent.db — deliberately no env keys in the worker table.
        ProviderSpec(
            id="openai-codex",
            env_keys=(),
            default_route="openai-codex/gpt-5.6-sol",
            auth_kinds=frozenset({"oauth"}),
        ),
        # omp-native credential route: grok CLI-proxy OIDC token via a
        # command-backed models.yml apiKey (~/.omp/agent/grok-token.py).
        ProviderSpec(
            id="grok",
            env_keys=(),
            default_route="grok/grok-4.6",
            auth_kinds=frozenset({"cli_proxy"}),
        ),
        # ---- long tail (fork catalog descriptors.ts) ----
        ProviderSpec(
            id="google",
            env_keys=("GEMINI_API_KEY",),
            default_route="google/gemini-3.1-pro-preview",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="openai",
            env_keys=("OPENAI_API_KEY",),
            default_route="openai/gpt-5.5",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="minimax",
            env_keys=("MINIMAX_API_KEY",),
            default_route="minimax/MiniMax-M3",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
        ProviderSpec(
            id="perplexity",
            env_keys=("PERPLEXITY_API_KEY",),
            default_route="perplexity/sonar",
            auth_kinds=frozenset({"env", "api_key"}),
        ),
    )
}

__all__ = ["AUTH_KINDS", "PROVIDERS", "RANK_ORDER", "ProviderSpec"]
