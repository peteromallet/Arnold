"""Provider-aware routing contracts for managed Arnold agents.

This module is deliberately process- and Megaplan-free.  Callers provide an
optional backend override and an optional model/agent spec; the resolver
returns the backend adapter and backend-local model that must be launched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from arnold.agent.contracts import AgentSpec, format_agent_spec, parse_agent_spec


MANAGED_AGENT_BACKENDS = frozenset({"hermes", "codex", "claude"})
MANAGED_AGENT_BACKEND_ALIASES = {
    "chatgpt": "codex",
    "shannon": "claude",
}
DEFAULT_MANAGED_AGENT_MODELS = {
    "hermes": "deepseek:deepseek-v4-pro",
    "codex": "gpt-5.6-terra",
    "claude": "opus",
}

_HERMES_PROVIDER_PREFIXES = (
    "deepseek:",
    "fireworks:",
    "google:",
    "kimi:",
    "minimax:",
    "mimo:",
    "openrouter:",
    "xai:",
    "zhipu:",
)
_HERMES_BARE_PREFIXES = (
    "deepseek-",
    "glm-",
    "kimi-",
    "minimax-",
    "mimo-",
    "qwen-",
)
_HERMES_MODEL_ALIASES = {
    # The direct Zhipu route is Arnold's canonical GLM 5.2 provider path.
    "glm-5.2": "zhipu:glm-5.2",
    # Preserve the existing Fireworks spelling used in managed profiles.
    "glm-5p2": "fireworks:accounts/fireworks/models/glm-5p2",
}


@dataclass(frozen=True, slots=True)
class ManagedAgentRoute:
    """Resolved backend selection and backend-local invocation model."""

    backend: str
    model: str
    model_spec: str
    effort: str | None
    backend_source: str


@dataclass(frozen=True, slots=True)
class ManagedAgentCapabilities:
    """Truthful upstream capabilities used by the durable launch contract."""

    persistent_session: bool
    exact_session_resume: bool
    generic_tool_policy: str
    max_output_tokens: str
    provider_timeout: str
    raw_stream: str


MANAGED_AGENT_CAPABILITIES = {
    "codex": ManagedAgentCapabilities(
        persistent_session=True,
        exact_session_resume=True,
        generic_tool_policy="full_toolset_only",
        max_output_tokens="upstream_model_managed",
        provider_timeout="supervisor_enforced",
        raw_stream="codex_cli_jsonl",
    ),
    "hermes": ManagedAgentCapabilities(
        persistent_session=True,
        exact_session_resume=True,
        generic_tool_policy="native_toolset_filter",
        max_output_tokens="native_request_cap",
        provider_timeout="supervisor_enforced",
        raw_stream="hermes_launcher_stdout_and_stderr",
    ),
    "claude": ManagedAgentCapabilities(
        persistent_session=True,
        exact_session_resume=True,
        generic_tool_policy="claude_builtin_tools_filter",
        max_output_tokens="claude_code_environment_cap",
        provider_timeout="launcher_and_supervisor_enforced",
        raw_stream="claude_cli_stream_json",
    ),
}


def managed_agent_capabilities(backend: str) -> ManagedAgentCapabilities:
    canonical = _canonical_backend(backend)
    if canonical == "auto":
        raise ValueError("managed-agent capabilities require a concrete backend")
    return MANAGED_AGENT_CAPABILITIES[canonical]


def _canonical_backend(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized == "auto":
        return normalized
    normalized = MANAGED_AGENT_BACKEND_ALIASES.get(normalized, normalized)
    if normalized not in MANAGED_AGENT_BACKENDS:
        choices = ", ".join(["auto", *sorted(MANAGED_AGENT_BACKENDS)])
        raise ValueError(
            f"unsupported managed-agent backend {value!r}; expected one of {choices}"
        )
    return normalized


def _agent_backend(agent: str) -> str | None:
    normalized = str(agent).strip().lower()
    normalized = MANAGED_AGENT_BACKEND_ALIASES.get(normalized, normalized)
    return normalized if normalized in MANAGED_AGENT_BACKENDS else None


def infer_managed_agent_backend(model: str) -> str | None:
    """Infer a backend from an agent spec or an unambiguous bare model."""

    normalized = str(model or "").strip()
    if not normalized:
        return None
    parsed = parse_agent_spec(normalized)
    if backend := _agent_backend(parsed.agent):
        return backend

    lowered = normalized.lower()
    if (
        lowered.startswith("gpt-5")
        or "/gpt-5" in lowered
        or lowered.startswith("codex-")
    ):
        return "codex"
    if any(token in lowered for token in ("claude", "sonnet", "opus", "haiku")):
        return "claude"
    if lowered.startswith(_HERMES_PROVIDER_PREFIXES) or lowered.startswith(
        _HERMES_BARE_PREFIXES
    ):
        return "hermes"
    return None


def _normalize_hermes_model(model: str) -> str:
    normalized = str(model).strip()
    return _HERMES_MODEL_ALIASES.get(normalized.lower(), normalized)


def resolve_managed_agent_route(
    *,
    backend: str = "auto",
    model: str | None = None,
    default_backend: str = "codex",
    default_models: Mapping[str, str] | None = None,
) -> ManagedAgentRoute:
    """Resolve one safe managed-agent backend/model pairing.

    ``backend="auto"`` follows an explicit agent/model spec, then an
    unambiguous bare model family, and finally ``default_backend``.  Explicit
    backend overrides remain supported, but a model that clearly belongs to a
    different backend is rejected before a manifest or process is created.
    """

    requested_backend = _canonical_backend(backend)
    fallback_backend = _canonical_backend(default_backend)
    if fallback_backend == "auto":
        raise ValueError("default managed-agent backend must be concrete")

    normalized_model = str(model or "").strip() or None
    parsed = parse_agent_spec(normalized_model) if normalized_model else None
    spec_backend = _agent_backend(parsed.agent) if parsed is not None else None
    inferred_backend = (
        spec_backend
        or (infer_managed_agent_backend(normalized_model) if normalized_model else None)
    )
    if (
        requested_backend != "auto"
        and inferred_backend is not None
        and inferred_backend != requested_backend
    ):
        raise ValueError(
            "managed-agent backend/model mismatch: "
            f"backend {requested_backend!r} cannot execute model {normalized_model!r}; "
            f"use backend {inferred_backend!r} or backend 'auto'"
        )

    resolved_backend = (
        inferred_backend if requested_backend == "auto" and inferred_backend else
        fallback_backend if requested_backend == "auto" else
        requested_backend
    )
    defaults = dict(DEFAULT_MANAGED_AGENT_MODELS)
    if default_models:
        defaults.update(
            {
                _canonical_backend(key): str(value).strip()
                for key, value in default_models.items()
                if str(value).strip()
            }
        )

    effort = parsed.effort if parsed is not None and spec_backend is not None else None
    if parsed is not None and spec_backend is not None:
        runtime_model = parsed.model or defaults[resolved_backend]
    else:
        runtime_model = normalized_model or defaults[resolved_backend]
    if resolved_backend == "hermes":
        runtime_model = _normalize_hermes_model(runtime_model)

    model_spec = format_agent_spec(
        AgentSpec(agent=resolved_backend, model=runtime_model, effort=effort)
    )
    return ManagedAgentRoute(
        backend=resolved_backend,
        model=runtime_model,
        model_spec=model_spec,
        effort=effort,
        backend_source=(
            "explicit_backend"
            if requested_backend != "auto"
            else "model_spec"
            if inferred_backend is not None
            else "default_backend"
        ),
    )


__all__ = [
    "DEFAULT_MANAGED_AGENT_MODELS",
    "MANAGED_AGENT_BACKENDS",
    "MANAGED_AGENT_CAPABILITIES",
    "ManagedAgentCapabilities",
    "ManagedAgentRoute",
    "infer_managed_agent_backend",
    "managed_agent_capabilities",
    "resolve_managed_agent_route",
]
