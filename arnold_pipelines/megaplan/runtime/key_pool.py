"""Dynamic API key pooling for Hermes-backed providers.

KeyPool is re-exported from the canonical SSoT at arnold.agent.providers.pool.
This module retains the megaplan-specific wrappers, blocking guards, and the
_pool singleton that wires envelope/governor context.
"""

from __future__ import annotations

import sys
from typing import Any

# ---------------------------------------------------------------------------
# Re-export KeyPool from the SSoT (arnold.agent.providers.pool)
# ---------------------------------------------------------------------------
from arnold.agent.providers.pool import (  # noqa: F401
    KeyEntry,
    KeyPool as _BaseKeyPool,
    minimax_openrouter_model,
    resolve_kimi_base_url,
    _DEFAULT_BASE_URLS,
    _ENV_ALIASES,
    _PROVIDER_BASE_URL_VARS,
    _PROVIDER_KEY_VARS,
    provider_credential_env_vars,
)

# KeyPathSource that resolves the megaplan api_keys.json path.
import os
from pathlib import Path
from arnold.agent.providers.pool import KeyPathSource as _KeyPathSource


class _MegaplanKeyPathSource:
    """Supplies the api_keys.json path for the megaplan-local key pool."""

    def keys_path(self) -> Path:
        override = os.environ.get("MEGAPLAN_API_KEYS_PATH")
        if override:
            return Path(override).expanduser()
        repo_root = Path(__file__).resolve().parents[1]
        candidates = (
            repo_root / "auto_improve" / "api_keys.json",
        )
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]


class KeyPool(_BaseKeyPool):
    """Megaplan-aware key pool that charges the active Governor on acquire."""

    current_envelope = staticmethod(lambda: _current_envelope())

    def acquire(self, provider: str) -> str:
        key = super().acquire(provider)
        if key:
            _charge_governor_for_current_envelope(self)
        return key


_pool = KeyPool(keys_path_source=_MegaplanKeyPathSource())


def _current_envelope(*_args):  # type: ignore[no-untyped-def]
    """Return the envelope visible to this task via ContextVar, or ``None``.

    Wired onto _pool so governor/envelope integration works without subclassing.
    """
    from arnold.runtime.envelope import _envelope_ctx

    return _envelope_ctx.get()


def _load_hermes_env() -> dict[str, str]:
    return _pool.load_hermes_env()
def _get_api_credential(env_var: str, hermes_env: dict[str, str] | None = None) -> str:
    return _pool.get_api_credential(env_var, hermes_env)
def _charge_governor_for_current_envelope(pool: KeyPool | None = None) -> None:
    """Charge the governor for the current task envelope if one is active.

    Invoked outside the KeyPool lock so a BudgetExceeded raised here
    does not strand the pool lock.  charge() is a no-op when no governor
    is attached to this execution tree.
    """
    active_pool = pool or _pool
    envelope = active_pool.current_envelope()
    if envelope is not None:
        from arnold_pipelines.megaplan.runtime.governor import current_governor

        gov = current_governor()
        if gov is not None:
            gov.charge(envelope)


def acquire_key(provider: str) -> str:
    return _pool.acquire(provider)
def report_429(provider: str, key: str, cooldown_secs: float = 60) -> None:
    _pool.report_429(provider, key, cooldown_secs)
def report_failure(provider: str, key: str) -> None:
    _pool.report_failure(provider, key)
def has_keys(provider: str) -> bool:
    return _pool.has_keys(provider)
def _raise_claude_via_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route Claude through OpenRouter.

    The harness historically defaulted bare hermes calls (model=None, or a
    non-prefixed ``anthropic/claude-*`` slash form) to OpenRouter's
    ``anthropic/claude-opus-4.6`` endpoint. That route consumes OPENROUTER_API_KEY
    quotas instead of the operator's Claude Code (shannon) subscription, and the
    fallback was completely silent. The user pays for Claude Code; they do not
    want Claude calls billed against OpenRouter without explicit opt-in.

    We block the silent path here and tell the caller exactly how to recover.
    Explicit ``openrouter:`` prefixed models still work — only the silent
    *default* is removed.
    """
    # Import lazily to keep this module import-cycle-safe (megaplan.types is
    # otherwise independent of megaplan.runtime, but the lazy import is
    # the cheapest insurance).
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="claude_via_openrouter_blocked",
        message=(
            "Refusing to route Claude through OpenRouter. " + reason + " "
            "The megaplan harness silently defaulted Claude calls to "
            "anthropic/claude-opus-4.6 via OpenRouter, but the operator has a "
            "Claude Code subscription that should be used instead. Pick an "
            "explicit path:\n"
            "  --agent shannon   (use Claude Code, recommended)\n"
            "  --agent claude    (same as shannon)\n"
            "  --phase-model <phase>=claude:claude-opus-4-7:medium\n"
            "If you actually want OpenRouter for some reason, set the model "
            "explicitly with a provider prefix, e.g. "
            "--hermes openrouter:anthropic/claude-opus-4.6"
        ),
        valid_next=[
            "rerun with --agent shannon",
            "rerun with --phase-model <phase>=claude:claude-opus-4-7:medium",
            "rerun with --hermes openrouter:anthropic/claude-opus-4.6 (explicit)",
        ],
    )


def _is_claude_model_name(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered.startswith("anthropic/claude")
        or lowered.startswith("claude-")
        or lowered.startswith("claude/")
    )


# ChatGPT-subscription Codex backend.  The same OAuth bundle the `codex` CLI
# uses (imported from ~/.codex/auth.json into ~/.hermes/auth.json) is the only
# credential — no OPENAI_API_KEY required.
_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"

# megaplan depth tokens accepted after ``codex:<model>:``.  xhigh/max are CLI
# reasoning levels the Responses API does not accept, so they map down to high.
_CODEX_EFFORT_LEVELS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})


def _normalize_codex_effort(effort: str) -> str:
    """Map megaplan depth tokens to Responses-API reasoning effort."""
    if effort in ("xhigh", "max"):
        return "high"
    return effort


def _is_codex_model_name(name: str) -> bool:
    """Match codex gpt-5.x family (case-insensitive)."""
    lowered = name.lower()
    return lowered.startswith("gpt-5")


def _is_deepseek_model_name(name: str) -> bool:
    """Match bare deepseek model names (case-insensitive)."""
    lowered = name.lower()
    return lowered.startswith("deepseek-") or lowered.startswith("deepseek/")


def _fireworks_deepseek_model_name(name: str) -> str | None:
    """Return the bare DeepSeek model from a Fireworks model id, if present."""

    lowered = name.lower()
    marker = "/models/"
    candidate = name
    if marker in lowered:
        candidate = name[lowered.rfind(marker) + len(marker):]
    candidate = candidate.strip("/")
    if _is_deepseek_model_name(candidate):
        return candidate
    return None


def _raise_codex_via_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route codex/gpt-5.x through OpenRouter.

    The harness would otherwise default bare ``gpt-5.5`` (etc.) to OpenRouter,
    silently consuming OPENROUTER_API_KEY quotas.  The user intends these models
    to run through the proper codex path, not OpenRouter.

    Explicit ``openrouter:`` prefixed models still work — only the silent
    *default* is removed.
    """
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="codex_via_openrouter_blocked",
        message=(
            "Refusing to route codex/gpt-5.x through OpenRouter. " + reason + " "
            "Codex models (gpt-5.5, gpt-5.4, etc.) will not be silently billed "
            "to your OpenRouter key. Pick an explicit path:\n"
            "  --agent codex                    (use the codex vendor path)\n"
            "  --hermes codex:gpt-5.6-sol:high  (ChatGPT subscription, no API key)\n"
            "  --hermes openrouter:gpt-5.5      (explicit OpenRouter opt-in)\n"
            "If you actually want OpenRouter, set the model explicitly with "
            "an ``openrouter:`` prefix."
        ),
        valid_next=[
            "rerun with --agent codex",
            "rerun with --hermes codex:gpt-5.6-sol:high (subscription token)",
            "rerun with --hermes openrouter:gpt-5.5 (explicit)",
        ],
    )


def _raise_generic_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route an unrecognised model through OpenRouter.

    Any model not matching a known provider prefix or bare model guard
    MUST NOT silently fall through to OpenRouter.  The caller must use
    an explicit ``openrouter:`` prefix if they genuinely want OpenRouter.
    """
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="openrouter_blocked",
        message=(
            "Refusing to silently route an unrecognised model through OpenRouter. "
            + reason
            + " "
            "To use OpenRouter, prefix the model with ``openrouter:``. "
            "To use a native provider, use the appropriate prefix "
            "(``deepseek:``, ``fireworks:``, ``google:``, ``kimi:``, "
            "``zhipu:``, ``minimax:``, ``mimo:``, ``xai:``) or the ``hermes:`` agent."
        ),
        valid_next=[
            "rerun with --hermes openrouter:<model>",
            "rerun with --hermes deepseek:<model>",
            "rerun with --hermes kimi:<model>",
            "rerun with --hermes mimo:<model>",
            "rerun with --hermes xai:grok-4.6",
            "rerun with --agent claude / --agent codex / --agent shannon",
        ],
    )


def resolve_model(model: str | None) -> tuple[str, dict[str, Any]]:
    agent_kwargs: dict[str, Any] = {}
    if model is None or not str(model).strip():
        # No model specified — the previous behaviour silently defaulted to
        # anthropic/claude-opus-4.6 via OpenRouter. Refuse that silent path.
        _raise_claude_via_openrouter_blocked(
            "No model was specified, so no provider could be selected."
        )
    resolved_model = str(model).strip()
    # Allow an explicit ``openrouter:`` prefix to opt into OpenRouter for any
    # model (Claude included). This is the documented escape hatch.
    if resolved_model.startswith("openrouter:"):
        resolved_model = resolved_model[len("openrouter:"):]
        agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["openrouter"]
        agent_kwargs["api_key"] = acquire_key("openrouter")
        return resolved_model, agent_kwargs
    if resolved_model.startswith("zhipu:"):
        resolved_model = resolved_model[len("zhipu:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["zhipu"]) or _DEFAULT_BASE_URLS["zhipu"]
        agent_kwargs["api_key"] = acquire_key("zhipu")
    elif resolved_model.startswith("kimi:"):
        resolved_model = resolved_model[len("kimi:"):]
        kimi_key = acquire_key("kimi")
        agent_kwargs["api_key"] = kimi_key
        agent_kwargs["base_url"] = resolve_kimi_base_url(
            kimi_key,
            _DEFAULT_BASE_URLS["kimi"],
            _get_api_credential(_PROVIDER_BASE_URL_VARS["kimi"]),
        )
    elif resolved_model.startswith("google:"):
        resolved_model = resolved_model[len("google:"):]
        agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["google"]
        agent_kwargs["api_key"] = acquire_key("google")
    elif resolved_model.startswith("deepseek:"):
        resolved_model = resolved_model[len("deepseek:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["deepseek"]) or _DEFAULT_BASE_URLS["deepseek"]
        agent_kwargs["api_key"] = acquire_key("deepseek")
    elif resolved_model.startswith("fireworks:"):
        resolved_model = resolved_model[len("fireworks:"):]
        direct_deepseek_model = _fireworks_deepseek_model_name(resolved_model)
        if direct_deepseek_model is not None:
            resolved_model = direct_deepseek_model
            agent_kwargs["base_url"] = (
                _get_api_credential(_PROVIDER_BASE_URL_VARS["deepseek"])
                or _DEFAULT_BASE_URLS["deepseek"]
            )
            agent_kwargs["api_key"] = acquire_key("deepseek")
            return resolved_model, agent_kwargs
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["fireworks"]) or _DEFAULT_BASE_URLS["fireworks"]
        agent_kwargs["api_key"] = acquire_key("fireworks")
    elif resolved_model.startswith("mimo:"):
        resolved_model = resolved_model[len("mimo:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["mimo"]) or _DEFAULT_BASE_URLS["mimo"]
        agent_kwargs["api_key"] = acquire_key("mimo")
    elif resolved_model.startswith("xai:"):
        resolved_model = resolved_model[len("xai:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS.get("xai", "")) or _DEFAULT_BASE_URLS.get("xai", "https://api.x.ai/v1")
        agent_kwargs["api_key"] = acquire_key("xai")
    elif resolved_model.startswith("minimax:"):
        resolved_model = resolved_model[len("minimax:"):]
        minimax_key = acquire_key("minimax")
        if minimax_key:
            agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["minimax"]) or _DEFAULT_BASE_URLS["minimax"]
            agent_kwargs["api_key"] = minimax_key
        else:
            resolved_model = "minimax/" + resolved_model
            agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["openrouter"]
            agent_kwargs["api_key"] = acquire_key("openrouter")
    elif resolved_model.startswith("codex:"):
        # GPT-5.x via the ChatGPT-subscription Codex backend
        # (chatgpt.com/backend-api/codex) using the Codex OAuth bundle — the
        # same subscription the `codex` CLI uses, no API key required.  The
        # tokens live in the Hermes auth store (~/.hermes/auth.json) and are
        # imported from ~/.codex/auth.json on first use, so the CLI's token is
        # honored without sharing the CLI's refresh session.
        resolved_model = resolved_model[len("codex:"):]
        effort = None
        candidate, sep, tail = resolved_model.rpartition(":")
        if sep and tail in _CODEX_EFFORT_LEVELS:
            resolved_model, effort = candidate, tail
        from arnold.agent.hermes_cli.auth import resolve_codex_runtime_credentials

        try:
            creds = resolve_codex_runtime_credentials(force_refresh=False)
        except Exception as exc:
            from arnold_pipelines.megaplan.types import CliError

            raise CliError(
                code="codex_auth_unavailable",
                message=(
                    "No Codex (ChatGPT subscription) credentials available for "
                    f"model {resolved_model!r}: {exc} "
                    "Log in once with `codex login` (or `hermes login "
                    "--provider openai-codex`) so the OAuth bundle can be "
                    "imported."
                ),
                valid_next=["rerun after `codex login` / `hermes login`"],
            )
        api_key = str(creds.get("api_key") or "").strip()
        if not api_key:
            from arnold_pipelines.megaplan.types import CliError

            raise CliError(
                code="codex_auth_unavailable",
                message=(
                    "Codex credentials resolved but contained no usable access "
                    f"token for model {resolved_model!r}. Re-login with "
                    "`codex login`."
                ),
                valid_next=["rerun after `codex login`"],
            )
        agent_kwargs["base_url"] = str(creds.get("base_url") or _CODEX_BASE_URL).rstrip("/")
        agent_kwargs["api_key"] = api_key
        agent_kwargs["provider"] = "openai-codex"
        if effort:
            agent_kwargs["reasoning_config"] = {
                "enabled": True,
                "effort": _normalize_codex_effort(effort),
            }
    else:
        # Non-prefixed models (e.g. "qwen/qwen3.5-27b") — historically
        # routed through OpenRouter, but we now refuse all silent
        # OpenRouter fallbacks.  Recognised bare model families are
        # routed to their native provider APIs; everything else errors.
        if _is_claude_model_name(resolved_model):
            _raise_claude_via_openrouter_blocked(
                f"Model {resolved_model!r} would silently route to OpenRouter."
            )
        if _is_codex_model_name(resolved_model):
            _raise_codex_via_openrouter_blocked(
                f"Model {resolved_model!r} would silently route to OpenRouter."
            )
        if _is_deepseek_model_name(resolved_model):
            # Bare deepseek-v4-pro / deepseek/... → direct DeepSeek API.
            agent_kwargs["base_url"] = (
                _get_api_credential(_PROVIDER_BASE_URL_VARS["deepseek"])
                or _DEFAULT_BASE_URLS["deepseek"]
            )
            agent_kwargs["api_key"] = acquire_key("deepseek")
        else:
            _raise_generic_openrouter_blocked(
                f"Model {resolved_model!r} has no provider prefix and is not "
                f"a recognised bare model (claude-*, gpt-5.*, deepseek-*)."
            )
    return resolved_model, agent_kwargs
