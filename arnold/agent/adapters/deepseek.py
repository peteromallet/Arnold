"""DeepSeek adapter — wraps ``arnold.agent.run_agent.AIAgent``.

Conforms to :data:`arnold.agent.adapters.BackendAdapter` (``Callable[[AgentRequest], AgentResult]``).

Key behaviours
--------------

* Creates an ``AIAgent`` via an injectable factory (defaults to the real
  ``AIAgent`` class so integration tests can swap in a fake).
* Resolves the API key from a :class:`KeySource` when provided, otherwise
  falls back to the environment.
* Reads ``request.timeout_seconds`` as a **top-level** field and passes it
  as ``HERMES_API_TIMEOUT`` via ``monkeypatch.setenv`` for the duration of
  the call.
* Forwards per-request hints from ``request.metadata``:
  ``toolsets``, ``session_db_path``, ``conversation_history``.
* Maps ``request.prompt`` → ``user_message`` and
  ``request.system_prompt`` → ``system_message`` on ``run_conversation``.
* Projects the ``AIAgent.run_conversation`` result dict into an
  :class:`~arnold.agent.contracts.AgentResult`.
* Estimates cost via :mod:`arnold.agent.adapters._pricing` for known
  models; ``cost_usd`` is ``0.0`` when no pricing data is available
  (rather than ``None``, because :class:`AgentResult` declares it as
  ``float``).

No imports from ``arnold.pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

import os
import time
import urllib.error
from typing import Any, Callable, Dict, Optional
from unittest import mock

from arnold.agent.adapters import BackendAdapter, EventEmitter, KeySource, SessionStore
from arnold.agent.adapters._pricing import estimate_cost_usd
from arnold.agent.contracts import AgentRequest, AgentResult, ResultProvenance
from arnold.pipeline.cost_types import CanonicalUsage
from arnold.agent.costing.token_cost import PricingEntry, estimate_usage_cost
from arnold.security.llm_proxy import broker_production_mode_requested


_PROVIDER_DEFAULT_BASE_URLS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "mimo": "https://api.xiaomimimo.com/v1",
    "xai": "https://api.x.ai/v1",
}

_PROVIDER_KEY_VARS: dict[str, tuple[str, ...]] = {
    "deepseek": ("DEEPSEEK_API_KEY", "HERMES_API_KEY"),
    "mimo": ("MIMO_API_KEY",),
    "xai": ("XAI_API_KEY",),
}

_PROVIDER_BASE_URL_VARS: dict[str, str] = {
    "deepseek": "DEEPSEEK_BASE_URL",
    "mimo": "MIMO_BASE_URL",
    "xai": "XAI_BASE_URL",
}


def _provider_model(model: str | None) -> tuple[str, str | None]:
    """Return ``(provider, model_name)`` for Hermes provider-prefixed models."""
    if not model:
        return "deepseek", model
    provider, sep, rest = model.partition(":")
    if sep and provider in _PROVIDER_DEFAULT_BASE_URLS and rest:
        return provider, rest
    return "deepseek", model


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _provider_base_url(provider: str, fallback: str | None = None) -> str:
    env_name = _PROVIDER_BASE_URL_VARS.get(provider, "")
    return (
        (os.getenv(env_name, "").strip() if env_name else "")
        or fallback
        or _PROVIDER_DEFAULT_BASE_URLS[provider]
    )


def _provider_headers(provider: str, key: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "mimo":
        # Xiaomi's curl examples use `api-key`; the OpenAI SDK path uses the
        # bearer token. Send both for compatibility with either gateway mode.
        headers["api-key"] = key
    return headers


def _provider_display_name(provider: str) -> str:
    if provider == "deepseek":
        return "DeepSeek"
    if provider == "mimo":
        return "MiMo"
    if provider == "xai":
        return "xAI"
    return provider

# ---------------------------------------------------------------------------
# Injectable AIAgent factory
# ---------------------------------------------------------------------------

_AIAgentFactory = Callable[..., Any]
"""Signature: ``(**overrides) -> AIAgent``."""


def _default_aiaagent_factory(**kwargs: Any) -> Any:
    """Create a real ``AIAgent`` from ``arnold.agent.run_agent``.

    This is the default factory; callers can inject a fake for testing.
    """
    from arnold.agent.run_agent import AIAgent

    return AIAgent(**kwargs)


# ---------------------------------------------------------------------------
# DeepSeekAdapter
# ---------------------------------------------------------------------------


class DeepSeekAdapter:
    """Adapts ``AIAgent`` into the :data:`BackendAdapter` seam.

    Args:
        session_store: Optional :class:`SessionStore` for session persistence.
        key_source: Optional :class:`KeySource` for API key resolution.
        event_emitter: Optional :class:`EventEmitter` for runtime telemetry.
        agent_factory: Injectable ``AIAgent`` factory (default: real ``AIAgent``).
    """

    def __init__(
        self,
        *,
        session_store: SessionStore | None = None,
        key_source: KeySource | None = None,
        event_emitter: EventEmitter | None = None,
        agent_factory: _AIAgentFactory | None = None,
        key_pool: Any | None = None,
        base_url: str = "https://api.deepseek.com/",
        transport: Callable[[str, dict[str, Any], dict[str, str], float | None], dict[str, Any]] | None = None,
        pricing_rows: dict[tuple[str, str], PricingEntry] | None = None,
    ) -> None:
        self._session_store = session_store
        self._key_source = key_source
        self._event_emitter = event_emitter
        self._agent_factory = agent_factory or _default_aiaagent_factory
        self._key_pool = key_pool
        self._base_url = base_url
        self._transport = transport
        self._pricing_rows = pricing_rows

    # ------------------------------------------------------------------
    # BackendAdapter conformance
    # ------------------------------------------------------------------

    def __call__(self, request: AgentRequest) -> AgentResult:
        """Execute *request* through an ``AIAgent`` and return an ``AgentResult``."""
        if self._transport is not None or self._key_pool is not None:
            return self._dispatch_openai_compatible(request)
        return self._dispatch(request)

    def _dispatch_openai_compatible(self, request: AgentRequest) -> AgentResult:
        started_at = time.monotonic()
        raw_model = request.resolved_model or request.model or "deepseek-chat"
        provider, model = _provider_model(raw_model)
        key = ""
        if self._key_pool is not None:
            key = self._key_pool.acquire(provider)
        if not key and not broker_production_mode_requested():
            key = _first_env(_PROVIDER_KEY_VARS[provider])
        if not key:
            raise LookupError(f"no {_provider_display_name(provider)} API key available")

        model = model or ("mimo-v2.5-pro" if provider == "mimo" else "deepseek-chat")
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt or ""})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if request.effort:
            payload["reasoning_effort"] = request.effort
        payload.update(request.metadata or {})

        base_url = _provider_base_url(
            provider,
            self._base_url if provider == "deepseek" else None,
        )
        if self._key_pool is not None and hasattr(self._key_pool, "resolve_base_url"):
            resolved = self._key_pool.resolve_base_url(provider)
            if resolved:
                base_url = resolved
        url = base_url.rstrip("/") + "/chat/completions"
        if not base_url.rstrip("/").endswith("/v1"):
            url = base_url.rstrip("/") + "/v1/chat/completions"
        headers = _provider_headers(provider, key)
        transport = self._transport
        if transport is None:
            raise LookupError(f"no {provider} transport configured")
        try:
            response = transport(url, payload, headers, request.timeout_seconds)
        except urllib.error.HTTPError as exc:
            if self._key_pool is not None and exc.code == 429:
                self._key_pool.report_429(provider, key)
            elif self._key_pool is not None and exc.code in {401, 403}:
                self._key_pool.report_failure(provider, key)
            raise

        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or response.get("result") or ""
        usage = response.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        cost = estimate_usage_cost(
            model,
            CanonicalUsage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                request_count=1,
            ),
            provider="deepseek",
            pricing_rows=self._pricing_rows,
        )
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return AgentResult(
            payload={"response": content, "completed": True},
            raw_output=content,
            duration_ms=elapsed_ms,
            cost_usd=float(cost.amount_usd or 0.0),
            model_actual=response.get("model") or model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provenance=ResultProvenance(
                agent=request.agent,
                mode=request.mode,
                model=response.get("model") or model,
                resolved_model=request.resolved_model or request.model,
                effort=request.effort,
                metadata={"provider": provider},
            ),
            metadata={
                "cost_status": cost.status,
                "pricing_version": cost.pricing_version,
            },
        )

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, request: AgentRequest) -> AgentResult:
        started_at = time.monotonic()

        # --- resolve API key -----------------------------------------------
        raw_model = request.resolved_model or request.model or "deepseek/deepseek-chat"
        provider, model = _provider_model(raw_model)

        api_key: str | None = None
        if self._key_source is not None:
            api_key = self._key_source.key_for(request.agent)
        # Fall back to environment — AIAgent does its own env loading too,
        # but an explicit key from KeySource takes priority.
        if provider == "deepseek":
            api_key = api_key or os.getenv("HERMES_API_KEY") or os.getenv("OPENAI_API_KEY")
        api_key = api_key or _first_env(_PROVIDER_KEY_VARS[provider])

        # --- gather model / metadata hints ---------------------------------
        model = model or ("mimo-v2.5-pro" if provider == "mimo" else "deepseek/deepseek-chat")
        metadata: dict[str, Any] = request.metadata or {}
        toolsets: list[str] | None = metadata.get("toolsets")
        session_db_path: str | None = metadata.get("session_db_path")
        conversation_history: list[dict[str, Any]] | None = metadata.get(
            "conversation_history"
        )

        # --- build AIAgent kwargs ------------------------------------------
        agent_kwargs: dict[str, Any] = {
            "model": model,
            "quiet_mode": True,
            "save_trajectories": False,
        }
        if provider in _PROVIDER_DEFAULT_BASE_URLS:
            agent_kwargs["provider"] = provider
            agent_kwargs["base_url"] = _provider_base_url(provider)
        if api_key:
            agent_kwargs["api_key"] = api_key
        if toolsets:
            agent_kwargs["enabled_toolsets"] = list(toolsets)
        if session_db_path:
            agent_kwargs["session_db_path"] = session_db_path

        # --- timeout -------------------------------------------------------
        timeout = request.timeout_seconds
        timeout_env: dict[str, str] = {}
        if timeout is not None:
            timeout_env["HERMES_API_TIMEOUT"] = str(timeout)

        # --- create agent and run ------------------------------------------
        agent = self._agent_factory(**agent_kwargs)

        with _scoped_env(timeout_env):
            result_dict: dict[str, Any] = agent.run_conversation(
                user_message=request.prompt or "",
                system_message=request.system_prompt,
                conversation_history=conversation_history,
            )

        elapsed_ms = int((time.monotonic() - started_at) * 1000)

        # --- emit event if emitter is provided -----------------------------
        if self._event_emitter is not None:
            try:
                self._event_emitter.emit(
                    "agent.dispatched",
                    {
                        "agent": request.agent,
                        "model": model,
                        "duration_ms": elapsed_ms,
                    },
                )
            except Exception:
                pass  # best-effort telemetry

        # --- project result ------------------------------------------------
        return self._project_result(request, result_dict, elapsed_ms)

    # ------------------------------------------------------------------
    # Result projection
    # ------------------------------------------------------------------

    @staticmethod
    def _project_result(
        request: AgentRequest,
        result: dict[str, Any],
        duration_ms: int,
    ) -> AgentResult:
        """Convert an ``AIAgent.run_conversation`` return dict into an
        :class:`AgentResult`."""
        final_response: str = result.get("final_response") or ""
        model_actual: str | None = result.get("model") or None
        prompt_tokens: int = result.get("prompt_tokens") or 0
        completion_tokens: int = result.get("completion_tokens") or 0
        total_tokens: int = result.get("total_tokens") or 0

        # Cost estimation — use inline _pricing for known models,
        # fall back to the AIAgent's own estimate, then to 0.0.
        cost_usd: float = 0.0
        inline_estimate = estimate_cost_usd(
            model=model_actual,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if inline_estimate is not None:
            cost_usd = inline_estimate
        elif "estimated_cost_usd" in result and isinstance(
            result["estimated_cost_usd"], (int, float)
        ):
            cost_usd = float(result["estimated_cost_usd"])

        # payload: the raw final response text, plus any structured fields
        payload: dict[str, Any] = {
            "response": final_response,
            "completed": result.get("completed", True),
        }

        # Build provenance if we have a model
        provenance: ResultProvenance | None = None
        if model_actual:
            provenance = ResultProvenance(
                agent=request.agent,
                mode=request.mode,
                model=model_actual,
                resolved_model=request.resolved_model or request.model,
                effort=request.effort,
                session_id=getattr(
                    getattr(request, "provenance", None), "session_id", None
                ),
            )

        return AgentResult(
            payload=payload,
            raw_output=final_response,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            session_id=result.get("session_id"),
            trace_output=None,
            rendered_prompt=request.prompt,
            model_actual=model_actual,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provenance=provenance,
        )


# ---------------------------------------------------------------------------
# Scoped environment helper
# ---------------------------------------------------------------------------


class _scoped_env:
    """Context manager that temporarily sets/overrides environment variables.

    Restores original values (or deletes them) on exit.
    """

    def __init__(self, overrides: dict[str, str]) -> None:
        self._overrides = overrides
        self._originals: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self._overrides.items():
            self._originals[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *args: Any) -> None:
        for key, original in self._originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original
