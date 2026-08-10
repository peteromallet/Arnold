"""LLM provider proxy resolution for broker-covered API-key paths."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from arnold.security.redaction import redact_text

if TYPE_CHECKING:
    from arnold.security.broker_client import BrokerClient

LOGGER = logging.getLogger(__name__)

BROKER_SOCKET_ENV = "ARNOLD_BROKER_SOCKET"
BROKER_URL_ENV = "ARNOLD_BROKER_URL"
LLM_PROXY_BASE_URL_ENV = "ARNOLD_LLM_PROXY_BASE_URL"
BROKER_LLM_PROXY_BASE_URL_ENV = "ARNOLD_BROKER_LLM_PROXY_BASE_URL"
BROKER_PRODUCTION_ENV = "ARNOLD_BROKER_PRODUCTION"

COVERED_OPENAI_COMPATIBLE_PROVIDERS: frozenset[str] = frozenset(
    {
        "ai-gateway",
        "anthropic",
        "copilot",
        "custom",
        "deepseek",
        "fireworks",
        "kimi-coding",
        "kilocode",
        "mimo",
        "minimax",
        "minimax-cn",
        "opencode-go",
        "opencode-zen",
        "openrouter",
        "zai",
    }
)

DEFERRED_OAUTH_PROVIDERS: frozenset[str] = frozenset(
    {"anthropic-oauth", "nous", "openai-codex"}
)


class LlmProxyUnavailable(RuntimeError):
    """Raised when broker production mode cannot provide a covered LLM proxy."""


@dataclass(frozen=True, slots=True)
class LlmProxyCredential:
    """Agent-visible broker proxy credential for an upstream LLM provider."""

    provider: str
    base_url: str
    broker_auth: str
    upstream_base_url: str
    expires_at: int | None = None


def broker_production_mode_requested(
    *, environ: Mapping[str, str] | None = None
) -> bool:
    source = os.environ if environ is None else environ
    explicit = str(source.get(BROKER_PRODUCTION_ENV, "")).strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return bool(
        str(source.get(BROKER_SOCKET_ENV, "")).strip()
        or str(source.get(BROKER_URL_ENV, "")).strip()
    )


def covered_openai_compatible_provider(provider: str) -> bool:
    return _normalize_provider(provider) in COVERED_OPENAI_COMPATIBLE_PROVIDERS


def broker_llm_proxy_base_url(
    *, environ: Mapping[str, str] | None = None
) -> str | None:
    source = os.environ if environ is None else environ
    for name in (LLM_PROXY_BASE_URL_ENV, BROKER_LLM_PROXY_BASE_URL_ENV):
        value = str(source.get(name, "")).strip().rstrip("/")
        if value:
            return value
    broker_url = str(source.get(BROKER_URL_ENV, "")).strip().rstrip("/")
    if broker_url and broker_url.startswith(("http://", "https://")):
        return f"{broker_url}/llm"
    return None


def resolve_brokered_llm_proxy(
    provider: str,
    upstream_base_url: str,
    *,
    broker_client: "BrokerClient | None" = None,
    environ: Mapping[str, str] | None = None,
) -> LlmProxyCredential | None:
    """Return proxy credentials for a covered API-key provider in broker mode.

    Non-broker mode returns ``None`` so callers keep their existing raw-key
    behavior. Broker mode fails closed for covered providers when a local proxy
    URL or broker-scoped credential cannot be resolved.
    """

    normalized = _normalize_provider(provider)
    if not broker_production_mode_requested(environ=environ):
        return None
    if normalized not in COVERED_OPENAI_COMPATIBLE_PROVIDERS:
        return None

    proxy_root = broker_llm_proxy_base_url(environ=environ)
    if not proxy_root:
        raise LlmProxyUnavailable(
            "broker production mode is enabled but no LLM proxy base URL is configured"
        )

    upstream = str(upstream_base_url or "").strip().rstrip("/")
    if not upstream:
        raise LlmProxyUnavailable("covered LLM provider has no upstream base URL")

    if broker_client is None:
        from arnold.security.broker_client import BrokerClient

        client = BrokerClient.from_environment(environ=environ)
    else:
        client = broker_client
    credential = client.issue_llm_proxy_credential(
        provider=normalized,
        proxy_base_url=f"{proxy_root}/{normalized}",
        upstream_base_url=upstream,
    )
    if not credential or not credential.broker_auth:
        raise LlmProxyUnavailable("broker did not issue an LLM proxy credential")
    return credential


def warn_deferred_oauth_provider(provider: str) -> None:
    normalized = _normalize_provider(provider)
    if normalized in DEFERRED_OAUTH_PROVIDERS and broker_production_mode_requested():
        LOGGER.warning(
            "LLM provider %s uses an OAuth/refresh-token path that is deferred "
            "from M2 broker production coverage; this path is non-production "
            "until M5-M6 provider credential brokering lands",
            redact_text(normalized),
        )


def credential_from_payload(provider: str, payload: Mapping[str, Any]) -> LlmProxyCredential:
    raw = payload.get("proxy") or payload.get("credential")
    if not isinstance(raw, Mapping):
        raise LlmProxyUnavailable("broker response did not include LLM proxy credentials")
    base_url = str(raw.get("base_url") or "").strip().rstrip("/")
    broker_auth = str(raw.get("broker_auth") or "").strip()
    upstream_base_url = str(raw.get("upstream_base_url") or "").strip().rstrip("/")
    if not base_url or not broker_auth:
        raise LlmProxyUnavailable("broker response included incomplete LLM proxy credentials")
    expires_at = raw.get("expires_at")
    return LlmProxyCredential(
        provider=str(raw.get("provider") or provider),
        base_url=base_url,
        broker_auth=broker_auth,
        upstream_base_url=upstream_base_url,
        expires_at=expires_at if isinstance(expires_at, int) else None,
    )


def _normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "main":
        return "custom"
    if normalized == "codex":
        return "openai-codex"
    return normalized


__all__ = [
    "BROKER_LLM_PROXY_BASE_URL_ENV",
    "BROKER_PRODUCTION_ENV",
    "COVERED_OPENAI_COMPATIBLE_PROVIDERS",
    "DEFERRED_OAUTH_PROVIDERS",
    "LLM_PROXY_BASE_URL_ENV",
    "LlmProxyCredential",
    "LlmProxyUnavailable",
    "broker_llm_proxy_base_url",
    "broker_production_mode_requested",
    "covered_openai_compatible_provider",
    "credential_from_payload",
    "resolve_brokered_llm_proxy",
    "warn_deferred_oauth_provider",
]
