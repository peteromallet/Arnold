from __future__ import annotations

import pytest


def test_hermes_direct_zhipu_route_fails_closed_with_provider_context() -> None:
    from arnold_pipelines.megaplan.workers.hermes import (
        HermesProviderCredentialError,
        _validate_hermes_provider_credentials,
    )

    with pytest.raises(HermesProviderCredentialError) as caught:
        _validate_hermes_provider_credentials(
            "zhipu:glm-5.2",
            {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "api_key": "",
            },
            resolved_model="glm-5.2",
        )

    error = caught.value
    assert error.code == "provider_credentials_missing"
    assert "zhipu" in error.message
    assert "ZAI_API_KEY" in error.message
    assert "GLM_API_KEY" in error.message
    assert "ZHIPU_API_KEY" in error.message
    external = error.extra["_external_error"]
    assert external["provider"] == "zhipu"
    assert external["error_kind"] == "auth"
    assert external["provider_error_code"] == "missing_credentials"
    assert external["error_layer"] == "credential_preflight"
    assert external["nonretryable"] is True


def test_hermes_direct_route_with_key_is_unchanged() -> None:
    from arnold_pipelines.megaplan.workers.hermes import (
        _validate_hermes_provider_credentials,
    )

    _validate_hermes_provider_credentials(
        "zhipu:glm-5.2",
        {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "configured",
        },
        resolved_model="glm-5.2",
    )


def test_fireworks_deepseek_rewrite_reports_the_effective_provider() -> None:
    from arnold_pipelines.megaplan.workers.hermes import (
        HermesProviderCredentialError,
        _validate_hermes_provider_credentials,
    )

    with pytest.raises(HermesProviderCredentialError) as caught:
        _validate_hermes_provider_credentials(
            "fireworks:accounts/foo/models/deepseek-v4-pro",
            {
                "base_url": "https://api.deepseek.com",
                "api_key": "",
            },
        )
    assert caught.value.extra["_external_error"]["provider"] == "deepseek"


def test_zhipu_credential_alias_is_accepted_by_key_pool(monkeypatch) -> None:
    from arnold.agent.providers.pool import KeyPool, provider_credential_env_vars

    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.setenv("ZAI_API_KEY", "zai-test")

    assert provider_credential_env_vars("zhipu")[:3] == (
        "ZHIPU_API_KEY",
        "GLM_API_KEY",
        "ZAI_API_KEY",
    )
    pool = KeyPool(ttl_seconds=0)
    assert pool.has_keys("zhipu") is True


def test_pipeline_preflight_treats_zai_glm_and_zhipu_as_alternative_aliases(
    monkeypatch,
) -> None:
    from arnold_pipelines.megaplan.preflight import preflight_check_profile

    for name in ("ZHIPU_API_KEY", "GLM_API_KEY", "Z_AI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ZAI_API_KEY", "zai-test")

    assert preflight_check_profile(
        {"execute": "omp:zai/glm-5.2"},
        profile_name="partnered-5-glm",
    ) == []


def test_cloud_preflight_advertises_all_zhipu_aliases() -> None:
    from arnold_pipelines.megaplan import chain as chain_module
    from arnold_pipelines.megaplan.cloud.preflight import (
        resolve_cloud_chain_runtime_dependencies,
    )

    chain_spec = chain_module.ChainSpec.from_dict(
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": "idea.md",
                    "phase_model": ["execute=omp:zai/glm-5.2"],
                }
            ]
        }
    )
    summary = resolve_cloud_chain_runtime_dependencies(chain_spec)
    assert {"ZHIPU_API_KEY", "GLM_API_KEY", "ZAI_API_KEY"}.issubset(
        set(summary["env_hints"])
    )
    # The omp route reports the upstream provider ``zai`` (zhipu is the
    # legacy hermes-era name); the env hints carry the full GLM alias family.
    zai_requirements = [
        item
        for item in summary["provider_requirements"]
        if item.get("provider") == "zai"
    ]
    assert zai_requirements
    assert {"ZHIPU_API_KEY", "GLM_API_KEY", "ZAI_API_KEY"}.issubset(
        set(zai_requirements[0]["env_hints"])
    )
