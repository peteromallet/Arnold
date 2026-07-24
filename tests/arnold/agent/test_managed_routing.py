from __future__ import annotations

import pytest

from arnold.agent.routing import (
    infer_managed_agent_backend,
    resolve_managed_agent_route,
)


@pytest.mark.parametrize(
    ("model", "backend"),
    [
        ("hermes:glm-5.2", "hermes"),
        ("hermes:zhipu:glm-5.2", "hermes"),
        ("zhipu:glm-5.2", "hermes"),
        ("codex:gpt-5.6-terra", "codex"),
        ("gpt-5.6-sol", "codex"),
        ("claude:opus", "claude"),
        ("claude-sonnet-4-6", "claude"),
    ],
)
def test_infers_backend_from_agent_specs_and_model_families(
    model: str, backend: str
) -> None:
    assert infer_managed_agent_backend(model) == backend


def test_hermes_glm_52_uses_direct_zhipu_route() -> None:
    route = resolve_managed_agent_route(model="hermes:glm-5.2")

    assert route.backend == "hermes"
    assert route.model == "zhipu:glm-5.2"
    assert route.model_spec == "hermes:zhipu:glm-5.2"
    assert route.backend_source == "model_spec"


@pytest.mark.parametrize(
    ("model", "backend", "runtime_model", "effort"),
    [
        ("codex:gpt-5.6-sol:high", "codex", "gpt-5.6-sol", "high"),
        ("claude:opus:high", "claude", "opus", "high"),
        ("hermes:zhipu:glm-5.2", "hermes", "zhipu:glm-5.2", None),
    ],
)
def test_resolves_each_supported_provider(
    model: str, backend: str, runtime_model: str, effort: str | None
) -> None:
    route = resolve_managed_agent_route(model=model)

    assert (route.backend, route.model, route.effort) == (
        backend,
        runtime_model,
        effort,
    )


def test_explicit_compatible_backend_is_preserved() -> None:
    route = resolve_managed_agent_route(
        backend="chatgpt", model="gpt-custom", default_backend="codex"
    )

    assert route.backend == "codex"
    assert route.model == "gpt-custom"
    assert route.backend_source == "explicit_backend"


@pytest.mark.parametrize(
    ("backend", "model", "expected"),
    [
        ("codex", "hermes:glm-5.2", "hermes"),
        ("hermes", "codex:gpt-5.6-sol", "codex"),
        ("claude", "gpt-5.6-sol", "codex"),
    ],
)
def test_rejects_explicit_backend_model_mismatch(
    backend: str, model: str, expected: str
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"backend/model mismatch:.*use backend {expected!r}",
    ):
        resolve_managed_agent_route(backend=backend, model=model)


def test_backend_default_can_be_overridden_without_a_model() -> None:
    route = resolve_managed_agent_route(
        backend="hermes",
        default_models={"hermes": "zhipu:glm-5.2"},
    )

    assert route.model_spec == "hermes:zhipu:glm-5.2"


def test_unknown_backend_fails_clearly() -> None:
    with pytest.raises(ValueError, match="unsupported managed-agent backend"):
        resolve_managed_agent_route(backend="other", model="model")
