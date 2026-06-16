"""Smoke test: editable-install Kimi wiring for partnered-3/4.

These tests verify that the full path from profile selection through agent-mode
resolution and key-pool model resolution produces Kimi direct-API arguments.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import arnold
from arnold.pipeline.model_seam import classify_model_family, ModelFamily
from arnold.pipelines.megaplan.profiles import apply_profile_expansion
from arnold.pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.pipelines.megaplan.workers import resolve_agent_mode


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _worker_args(profile: str) -> Namespace:
    return Namespace(
        agent=None,
        confirm_self_review=False,
        ephemeral=False,
        fresh=False,
        hermes=None,
        persist=False,
        deepseek_provider=None,
        phase_model=[],
        profile=profile,
    )


def test_editable_install_package_is_local() -> None:
    """The installed arnold package points at this checkout (editable install)."""
    import arnold
    pkg_file = Path(arnold.__file__).resolve()
    expected = PROJECT_ROOT / "arnold" / "__init__.py"
    assert pkg_file == expected, f"arnold is not the editable install: {pkg_file}"


def test_partnered_kimi_profiles_resolve_to_kimi_direct_api() -> None:
    """partnered-3/4 premium phases resolve to hermes:kimi:kimi-k2.7-code."""
    for profile_name in ("partnered-3", "partnered-4"):
        args = _worker_args(profile_name)
        apply_profile_expansion(args, PROJECT_ROOT)

        # Patch agent availability so resolve_agent_mode doesn't bail out.
        with patch("arnold.pipelines.megaplan.workers._impl._is_agent_available", return_value=True):
            for phase in ("plan", "critique_evaluator", "review", "feedback", "loop_plan"):
                agent, _mode, _refreshed, model = resolve_agent_mode(phase, args)
                assert agent == "hermes", (
                    f"{profile_name}.{phase} agent should be hermes, got {agent!r}"
                )
                assert model == "kimi:kimi-k2.7-code", (
                    f"{profile_name}.{phase} model should be kimi:kimi-k2.7-code, got {model!r}"
                )

                # Resolve the model string that the hermes worker will receive.
                resolved_model, agent_kwargs = resolve_model(model)
                assert resolved_model == "kimi-k2.7-code"
                assert agent_kwargs["base_url"] == "https://api.kimi.com/coding/v1", (
                    f"{profile_name}.{phase} base_url should be Kimi coding, got {agent_kwargs['base_url']!r}"
                )
                assert agent_kwargs["api_key"].startswith("sk-kimi-"), (
                    f"{profile_name}.{phase} api_key should be read from ~/.hermes/.env"
                )

                # The model seam should classify it as a Kimi-family model.
                assert classify_model_family(resolved_model) is ModelFamily.KIMI


def test_partnered_kimi_tier_models_resolve_to_kimi_direct_api() -> None:
    """Tier 4/5 critique in partnered-3/4 routes to Kimi direct API."""
    for profile_name in ("partnered-3", "partnered-4"):
        args = _worker_args(profile_name)
        apply_profile_expansion(args, Path("/Users/peteromalley/Documents/megaplan"))

        critique_tiers = args.tier_models["critique"]
        for tier in (4, 5):
            spec = critique_tiers[tier]
            assert spec == "hermes:kimi:kimi-k2.7-code", (
                f"{profile_name} critique tier {tier} should be hermes:kimi:kimi-k2.7-code, got {spec!r}"
            )
            resolved_model, agent_kwargs = resolve_model("kimi:kimi-k2.7-code")
            assert resolved_model == "kimi-k2.7-code"
            assert agent_kwargs["base_url"] == "https://api.kimi.com/coding/v1"
            assert agent_kwargs["api_key"].startswith("sk-kimi-")


def test_partnered_3_high_execute_tiers_route_to_kimi() -> None:
    """partnered-3 uses Kimi, not Codex or Zhipu, for premium execute tiers."""
    args = _worker_args("partnered-3")
    apply_profile_expansion(args, Path("/Users/peteromalley/Documents/megaplan"))

    execute_tiers = args.tier_models["execute"]
    for tier in (4, 5):
        spec = execute_tiers[tier]
        assert spec == "hermes:kimi:kimi-k2.7-code", (
            f"partnered-3 execute tier {tier} should be hermes:kimi:kimi-k2.7-code, got {spec!r}"
        )


def test_hermes_runtime_uses_kimi_coding_api_with_kimi_key() -> None:
    """The hermes runtime initialized from resolved kwargs hits the Kimi coding API.

    With the current key this returns from the provider, proving the wiring is correct
    (base_url, api_key, model all flow through). A valid key would succeed.
    """
    from arnold.pipelines.megaplan.workers.hermes import _import_hermes_runtime

    AIAgent, SessionDB = _import_hermes_runtime()
    model, agent_kwargs = resolve_model("kimi:kimi-k2.7-code")

    agent = AIAgent(
        model=model,
        base_url=agent_kwargs["base_url"],
        api_key=agent_kwargs["api_key"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        session_id="smoke-test",
        session_db=SessionDB(),
        max_tokens=64,
    )

    result = agent.chat("Reply exactly: Kimi direct API OK")
    assert "Kimi direct API OK" in result
