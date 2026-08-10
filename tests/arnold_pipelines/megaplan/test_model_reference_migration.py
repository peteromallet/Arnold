"""B4 oracle tests — model-reference and credential migration.

Verifies that every live profile spec uses the exact ``omp:<provider>/<modelId>``
grammar, that no production code emits double-colon omp specs, that the
credential map (ZAI_API_KEY, Fireworks, Moonshot/Kimi, OpenRouter, xAI,
DeepSeek, Anthropic) resolves through the transitional key pool, and that the
per-host thinking/effort maps are honored.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

import pytest

from arnold.agent.contracts import parse_agent_spec
from arnold_pipelines.megaplan.types import is_premium_placeholder_agent
from arnold_pipelines.megaplan.profiles import load_profiles
from arnold_pipelines.megaplan.workers.omp import (
    OMP_AGENT,
    format_omp_spec,
    omp_route_from_legacy,
    omp_thinking_level,
    parse_omp_spec,
    validate_omp_catalog_model,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

# All live omp providers from the frozen B1 table.
_OMP_PROVIDERS = frozenset(
    {"deepseek", "fireworks", "zai", "moonshot", "kimi-code", "openrouter", "xai", "anthropic"}
)

_DOUBLE_COLON_OMP_RE = re.compile(r"omp:[^/]+:")


def _iter_profile_specs(profile_toml: dict) -> list[str]:
    specs: list[str] = []

    def _collect(value):
        if isinstance(value, str):
            specs.append(value)
        elif isinstance(value, list):
            for item in value:
                _collect(item)
        elif isinstance(value, dict):
            for item in value.values():
                _collect(item)

    _collect(profile_toml)
    return specs


class TestLiveProfileSpecs:
    @pytest.mark.parametrize("path", sorted((REPO_ROOT / "arnold_pipelines/megaplan/profiles").glob("*.toml")))
    def test_profile_has_no_hermes_or_double_colon_omp(self, path: Path):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for spec in _iter_profile_specs(data):
            assert "hermes:" not in spec, f"{path.name}: leftover hermes spec {spec!r}"
            assert not _DOUBLE_COLON_OMP_RE.search(spec), f"{path.name}: double-colon omp {spec!r}"
            if spec.startswith("omp"):
                parsed = parse_omp_spec(spec)
                provider, model_id = parsed
                assert provider in _OMP_PROVIDERS, f"{path.name}: unknown provider {provider}"
                # Every route must resolve to a verified catalog row.
                validate_omp_catalog_model(provider, model_id)

    def test_all_profiles_load(self):
        profiles = load_profiles()
        for name in (
            "all-deepseek-pro",
            "all-deepseek-flash",
            "all-deepseek-pro-direct",
            "all-fireworks-deepseek",
            "all-open",
            "apex",
            "arnold-openrouter",
            "directed",
            "partnered",
            "partnered-3",
            "partnered-4",
            "partnered-5",
            "partnered-5-glm",
            "premium",
            "solo",
            "variable",
        ):
            assert name in profiles, f"profile {name} missing after migration"

    def test_omp_profiles_route_through_omp_agent(self):
        profiles = load_profiles()
        for name, profile in profiles.items():
            for phase, spec in profile.items():
                if phase.startswith("tier") or phase in ("adaptive_critique",):
                    continue
                if not isinstance(spec, str) or ":" not in spec:
                    continue
                parsed = parse_agent_spec(spec)
                if parsed.agent in ("claude", "codex"):
                    continue
                if is_premium_placeholder_agent(parsed.agent):
                    continue
                assert parsed.agent == OMP_AGENT, (
                    f"profile {name} phase {phase}: non-omp spec {spec!r}"
                )


class TestProductionCodeHasNoDoubleColon:
    def test_no_double_colon_omp_in_production(self):
        roots = [
            REPO_ROOT / "arnold",
            REPO_ROOT / "arnold_pipelines",
        ]
        offenders: list[str] = []
        for root in roots:
            for path in sorted(root.rglob("*.py")):
                if "__pycache__" in str(path):
                    continue
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if _DOUBLE_COLON_OMP_RE.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
        # Deliberate rejection fixtures in tests are excluded from this scan
        # (they exist to prove the double-colon form is refused); production
        # code must never emit it.
        assert offenders == [], f"double-colon omp specs in production: {offenders}"


class TestLegacyRouteTranslation:
    def test_exact_route_table(self):
        assert omp_route_from_legacy("hermes:deepseek:deepseek-v4-pro") == "omp:deepseek/deepseek-v4-pro"
        assert omp_route_from_legacy("hermes:deepseek:deepseek-v4-flash") == "omp:deepseek/deepseek-v4-flash"
        assert omp_route_from_legacy("hermes:zhipu:glm-5.2") == "omp:zai/glm-5.2"
        assert (
            omp_route_from_legacy("hermes:fireworks:accounts/fireworks/models/glm-5p2")
            == "omp:fireworks/glm-5.2"
        )
        assert (
            omp_route_from_legacy("hermes:fireworks:accounts/fireworks/models/kimi-k2p6")
            == "omp:fireworks/kimi-k2.6"
        )
        assert omp_route_from_legacy("hermes:glm-5.1") == "omp:zai/glm-5.1"
        assert (
            omp_route_from_legacy("hermes:openrouter:deepseek/deepseek-chat")
            == "omp:openrouter/deepseek/deepseek-chat"
        )

    def test_unchanged_inputs(self):
        assert omp_route_from_legacy("omp:deepseek/deepseek-v4-pro") == "omp:deepseek/deepseek-v4-pro"
        assert omp_route_from_legacy("claude:sonnet-4.6:medium") == "claude:sonnet-4.6:medium"
        assert omp_route_from_legacy("codex:gpt-5.5") == "codex:gpt-5.5"
        assert omp_route_from_legacy("hermes") == OMP_AGENT


class TestCredentialMap:
    def test_omp_spec_grammar_roundtrip(self):
        spec = format_omp_spec("zai", "glm-5.2")
        assert spec == "omp:zai/glm-5.2"
        provider, model = parse_omp_spec(spec)
        assert provider == "zai"
        assert model == "glm-5.2"

    def test_transitional_resolver_consumes_b1_table(self, monkeypatch):
        from arnold_pipelines.megaplan.runtime import key_pool as key_pool_module
        from arnold_pipelines.megaplan.runtime.key_pool import resolve_model

        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw")
        monkeypatch.setenv("ZAI_API_KEY", "zai")
        monkeypatch.setenv("KIMI_API_KEY", "kimi")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or")
        monkeypatch.setenv("XAI_API_KEY", "xai")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant")
        # The KeyPool singleton caches loaded keys per TTL; force a reload so
        # the monkeypatched env is observed regardless of prior tests.
        monkeypatch.setattr(key_pool_module, "_pool", key_pool_module.KeyPool(
            keys_path_source=key_pool_module._MegaplanKeyPathSource(),
        ))

        resolved, kwargs = resolve_model("omp:deepseek/deepseek-v4-pro")
        assert kwargs["api_key"] == "ds"
        resolved, kwargs = resolve_model("omp:fireworks/kimi-k2.7-code")
        assert kwargs["api_key"] == "fw"
        resolved, kwargs = resolve_model("omp:zai/glm-5.2")
        assert kwargs["api_key"] == "zai"
        resolved, kwargs = resolve_model("omp:moonshot/kimi-k2.7-code")
        assert kwargs["api_key"] == "kimi"
        resolved, kwargs = resolve_model("omp:openrouter/openai/gpt-5.5")
        assert kwargs["api_key"] == "or"
        resolved, kwargs = resolve_model("omp:xai/grok-4-fast-non-reasoning")
        assert kwargs["api_key"] == "xai"
        resolved, kwargs = resolve_model("omp:anthropic/claude-opus-4-8")
        assert kwargs["api_key"] == "ant"

    def test_zai_credential_alias(self):
        from arnold.agent.providers.pool import provider_credential_env_vars

        aliases = provider_credential_env_vars("zhipu")
        assert "ZAI_API_KEY" in aliases


class TestThinkingMaps:
    def test_per_host_effort_maps(self):
        # OpenRouter DeepSeek: high-only.
        assert omp_thinking_level("medium", "openrouter", "deepseek/deepseek-chat") == "high"
        # GLM-5.2 on zai: high/max.
        assert omp_thinking_level("low", "zai", "glm-5.2") == "high"
        assert omp_thinking_level("max", "zai", "glm-5.2") == "max"
        # Fireworks minimal → thinking off.
        assert omp_thinking_level("minimal", "fireworks", "kimi-k2.7-code") == "off"
        # Kimi K3 ladder.
        assert omp_thinking_level("low", "moonshot", "kimi-k2.7-code") == "low"
        assert omp_thinking_level("max", "kimi-code", "kimi-for-coding") == "max"
        # xAI non-reasoning.
        assert omp_thinking_level("high", "xai", "grok-4-fast-non-reasoning") == "off"
        # Anthropic adaptive: full ladder.
        assert omp_thinking_level("xhigh", "anthropic", "claude-opus-4-8") == "xhigh"

    def test_no_universal_effort_ladder(self):
        # Distinct hosts must NOT be silently normalized to one ladder.
        assert omp_thinking_level("xhigh", "zai", "glm-5.2") != omp_thinking_level(
            "xhigh", "openrouter", "deepseek/deepseek-chat"
        )
        assert omp_thinking_level("low", "zai", "glm-5.2") != omp_thinking_level(
            "low", "kimi-code", "kimi-for-coding"
        )

    def test_off_and_auto(self):
        assert omp_thinking_level("off", "deepseek", "deepseek-v4-pro") == "off"
        assert omp_thinking_level("auto", "deepseek", "deepseek-v4-pro") is None
        assert omp_thinking_level(None, "deepseek", "deepseek-v4-pro") is None
