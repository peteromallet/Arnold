"""Credential preflight for YAML pipelines.

Rehomed from ``arnold_pipelines.megaplan._pipeline.preflight`` during the M4
burn-down (T4).

Walks the resolved profile slots used by a YAML pipeline, maps agents and
providers to credential requirements, and validates that the user has the
required credentials before any stage fires.

Non-TTY mode: prints a structured credential message to stderr and exits 7.
TTY mode: renders a structured prompt with options.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from arnold.agent.providers.pool import provider_credential_env_vars

# ── Agent → provider → required env var mappings ──────────────────────
# Reuses and extends the mappings from arnold_pipelines.megaplan.cloud.preflight.

_AGENT_ENV_HINTS: dict[str, tuple[str, ...]] = {
    "claude": ("ANTHROPIC_API_KEY",),
    "shannon": ("ANTHROPIC_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
}

# omp provider → credential env hints (mirrors workers.omp._OMP_CREDENTIAL_ENV).
# The z.ai route reads ZAI_API_KEY, with ZHIPU_API_KEY accepted as a legacy
# alias.  omp-native credential routes (openai-codex, grok, kimi-code) resolve
# credentials from omp's own store and must not be gated here.
_PROVIDER_ENV_HINTS: dict[str, tuple[str, ...]] = {
    "deepseek": ("DEEPSEEK_API_KEY",),
    "fireworks": ("FIREWORKS_API_KEY",),
    "zai": ("ZAI_API_KEY", "ZHIPU_API_KEY"),
    "zhipu": ("ZAI_API_KEY", "ZHIPU_API_KEY"),
    "moonshot": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    "kimi": ("KIMI_API_KEY",),
    "kimi-code": ("KIMI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "minimax": ("MINIMAX_API_KEY",),
    "mimo": ("MINIMAX_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "anthropic": ("ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"),
}
# The non-omp names are kept here because premium/vendor profiles use them
# directly rather than through ``provider_credential_env_vars``.
_PROVIDER_ENV_HINTS.update(
    {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
    }
)

# ── Credential checking ───────────────────────────────────────────────


def _parse_agent_spec(spec: str) -> tuple[str, str | None]:
    """Parse an agent spec string into (agent, model)."""
    from arnold_pipelines.megaplan.types import parse_agent_spec

    return parse_agent_spec(spec)


def _check_credential(env_var: str) -> bool:
    """Check if an environment variable is set (non-empty)."""
    return bool(os.environ.get(env_var, "").strip())


def _provider_credential_configured(provider: str) -> bool:
    """Return whether any accepted key alias for *provider* is configured."""

    return any(_check_credential(name) for name in _PROVIDER_ENV_HINTS.get(provider, ()))


def _resolve_concrete_slot_spec(spec: str, *, vendor: str | None = None) -> str:
    """Resolve symbolic premium placeholders to concrete specs for preflight."""
    from arnold_pipelines.megaplan.profiles import (
        DIRECT_DEEPSEEK_V4_PRO_SPEC,
        FIREWORKS_DEEPSEEK_V4_PRO_SPEC,
        effective_premium_vendor,
    )
    from arnold_pipelines.megaplan.types import (
        format_agent_spec,
        is_premium_placeholder_spec,
        parse_agent_spec,
        resolve_premium_placeholder_spec,
    )

    if not is_premium_placeholder_spec(spec):
        return spec
    resolved_vendor = effective_premium_vendor(argparse.Namespace(vendor=vendor))
    concrete_spec = format_agent_spec(resolve_premium_placeholder_spec(spec, resolved_vendor))
    if vendor is not None:
        return concrete_spec
    parsed = parse_agent_spec(concrete_spec)
    if parsed.agent not in {"claude", "codex"}:
        return concrete_spec

    current_env = "ANTHROPIC_API_KEY" if parsed.agent == "claude" else "OPENAI_API_KEY"
    if _check_credential(current_env):
        return concrete_spec

    other_vendor = "codex" if parsed.agent == "claude" else "claude"
    other_env = "OPENAI_API_KEY" if other_vendor == "codex" else "ANTHROPIC_API_KEY"
    if _check_credential(other_env):
        return format_agent_spec(resolve_premium_placeholder_spec(spec, other_vendor))

    if _check_credential("DEEPSEEK_API_KEY"):
        return DIRECT_DEEPSEEK_V4_PRO_SPEC
    if _check_credential("FIREWORKS_API_KEY"):
        return FIREWORKS_DEEPSEEK_V4_PRO_SPEC
    return concrete_spec


# Slots that are opt-in / non-blocking and so must NOT hard-fail preflight.
# ``feedback`` only runs when explicitly requested, so its credential remains
# soft. If feedback IS used without the key, it fails at runtime on a
# throwaway template rather than blocking the whole run up front.
_SOFT_SLOTS: frozenset[str] = frozenset({"feedback"})


# Which single-vendor profile to recommend when a given premium credential is
# present but the chosen profile demands one the user lacks.
_VENDOR_FALLBACK_PROFILES: tuple[tuple[str, str, str], ...] = (
    # (env var present → recommend this profile → one-line why)
    ("ANTHROPIC_API_KEY", "all-claude", "Claude-only, every phase on Anthropic"),
    ("OPENAI_API_KEY", "partnered-codex", "Codex-only, every phase on OpenAI"),
)


def _credential_guidance(profile_name: str) -> list[str]:
    """Return guidance lines tailored to the credentials actually present.

    Three distinct situations, kept honestly separate:

    * **You already have a usable vendor key** (but not the one this profile
      wants): point at the matching single-vendor profile you can run *right
      now* — e.g. you have Anthropic, so `--profile all-claude` works.
    * **You have no model credentials at all**: a getting-started list of every
      supported key and what it unlocks — not a misleading "run with what you
      have" header when you have nothing.
    * **You lack a DeepSeek/Fireworks key**: a note that adding one unlocks the
      cheaper cost-tiered profiles (only shown when it adds information).
    """
    have_deepseek = _check_credential("DEEPSEEK_API_KEY") or _check_credential(
        "FIREWORKS_API_KEY"
    )
    have_any = (
        have_deepseek
        or _check_credential("ANTHROPIC_API_KEY")
        or _check_credential("OPENAI_API_KEY")
    )

    # Single-vendor profiles you can run immediately with a key you already
    # have (skip the profile you just tried — re-running it won't help).
    runnable: list[str] = []
    for env_var, rec_profile, why in _VENDOR_FALLBACK_PROFILES:
        if rec_profile != profile_name and _check_credential(env_var):
            runnable.append(
                f"  • re-run with `--profile {rec_profile}` ({why}) — "
                f"works with your {env_var}."
            )

    lines: list[str] = []
    if runnable:
        lines.append("You can run right now with credentials you already have:")
        lines.extend(runnable)

    if not have_any:
        # Brand-new user: nothing usable is configured. Note: uses "profile X"
        # (no `--` token) so it reads as a key-setup guide, not a "switch
        # profiles to fix this" loop.
        lines.append("No model credentials found. Set at least one of:")
        lines.append("  • ANTHROPIC_API_KEY — Claude (profile all-claude)")
        lines.append("  • OPENAI_API_KEY — Codex (profile partnered-codex)")
        lines.append(
            "  • DEEPSEEK_API_KEY (https://platform.deepseek.com) or "
            "FIREWORKS_API_KEY — DeepSeek; the cheapest option and what the "
            "cost-tiered profiles (solo, directed, partnered, …) are built on."
        )
    elif not have_deepseek:
        if lines:  # separate the hint from the runnable list above
            lines.append("")
        lines.append(
            "Recommend to the user that they add a DeepSeek key — it's the "
            "cheapest model and unlocks the cost-tiered profiles (solo, "
            "directed, partnered, …), which route mechanical work to DeepSeek "
            "instead of paying premium rates for it. They can set "
            "DEEPSEEK_API_KEY (https://platform.deepseek.com) or "
            "FIREWORKS_API_KEY."
        )
    return lines


def _required_env_vars_for_slot(agent_spec: str, slot_name: str) -> list[tuple[str, str]]:
    """Return list of (env_var, display_name) required for a slot.

    For omp specs, extracts the provider from the model string
    (e.g. ``omp:fireworks/glm-5.2`` → FIREWORKS_API_KEY).
    """
    agent, model = _parse_agent_spec(agent_spec)
    required: list[tuple[str, str]] = []

    if agent == "omp" and model:
        # Extract provider: omp:provider/model (legacy omp:provider/model
        # forms are accepted for back-compat).
        provider: str | None = None
        if model.startswith("omp:"):
            model = model[len("omp:"):]
        provider, _, model = model.partition("/")
        if not provider and ":" in model:
            provider, model = model.split(":", 1)
        if provider and provider in _PROVIDER_ENV_HINTS:
            # Aliases are alternatives, not independent requirements.  Keep
            # the canonical name in the legacy return shape while the caller
            # checks all accepted aliases before declaring it missing.
            env_vars = _PROVIDER_ENV_HINTS[provider]
            if env_vars:
                required.append((env_vars[0], f"{agent}/{provider}"))
    elif agent in _AGENT_ENV_HINTS:
        for env_var in _AGENT_ENV_HINTS[agent]:
            required.append((env_var, agent))

    return required


def preflight_check_profile(
    profile: dict[str, str],
    *,
    pipeline_name: str = "",
    profile_name: str = "",
    vendor: str | None = None,
) -> list[dict[str, Any]]:
    """Check that all slots in a resolved profile have their credentials available.

    Parameters
    ----------
    profile:
        The resolved profile (slot → agent spec).
    pipeline_name:
        The pipeline name for error messages.
    profile_name:
        The profile name for error messages.

    Returns
    -------
    list[dict]
        List of missing credentials, each with: slot, agent, env_var, display_name.
        Empty list means all credentials are available.
    """
    missing: list[dict[str, Any]] = []

    for slot, spec in profile.items():
        if not isinstance(spec, str) or not spec.strip():
            continue
        if slot in _SOFT_SLOTS:
            # Opt-in / non-blocking slot — don't gate the whole run on it.
            continue
        concrete_spec = _resolve_concrete_slot_spec(spec, vendor=vendor)
        required = _required_env_vars_for_slot(concrete_spec, slot)
        parsed_agent, parsed_model = _parse_agent_spec(concrete_spec)
        omp_provider: str | None = None
        if parsed_agent == "omp" and parsed_model:
            candidate = parsed_model
            if candidate.startswith("omp:"):
                candidate = candidate[len("omp:"):]
            provider, _, _ = candidate.partition("/")
            if not provider and ":" in candidate:
                provider, _ = candidate.split(":", 1)
            omp_provider = provider or None
        if omp_provider in _PROVIDER_ENV_HINTS:
            # A provider prefix is a direct routing contract.  Validate its
            # own aliases here so one configured GLM/ZAI key is sufficient and
            # no empty-key construction can be reached later.
            if _provider_credential_configured(omp_provider):
                continue
        for env_var, display_name in required:
            if not _check_credential(env_var):
                missing.append(
                    {
                        "slot": slot,
                        "spec": concrete_spec,
                        "agent": display_name,
                        "env_var": env_var,
                    }
                )

    return missing


def _onboarding_provider_ids(spec: str, env_var: str) -> set[str]:
    """Map one missing slot onto candidate onboarding catalog provider ids.

    ``omp:<provider>/model`` specs name their provider directly; agent-level
    slots (claude/codex) map by the catalog's accepted env-key aliases.
    """
    from agentbox.onboarding.catalog import PROVIDERS

    ids: set[str] = set()
    candidate = spec.strip()
    if candidate.startswith("omp:"):
        candidate = candidate[len("omp:"):]
    provider = candidate.partition("/")[0]
    if not provider and ":" in candidate:
        provider, _ = candidate.split(":", 1)
    if provider in PROVIDERS:
        ids.add(provider)
    ids.update(pid for pid, p in PROVIDERS.items() if env_var in p.env_keys)
    return ids


def _slots_ready_after_flow(missing: list[dict[str, Any]]) -> bool:
    """True iff every previously-missing slot now has a READY provider.

    The onboarding flow persists into omp's own stores — never this process's
    environment — so readiness is re-checked from the read-only machine scan
    (detect.scan_providers) instead of re-running the env-var-only check.
    """
    from agentbox.onboarding import detect

    status = {p.id: p.status for p in detect.scan_providers().providers}
    for entry in missing:
        ids = _onboarding_provider_ids(
            str(entry.get("spec", "")), str(entry["env_var"])
        )
        if not any(status.get(pid) == detect.READY for pid in ids):
            return False
    return True


def render_credential_failure(
    missing: list[dict[str, Any]],
    *,
    pipeline_name: str = "",
    profile_name: str = "",
    is_tty: bool | None = None,
) -> str:
    """Render a structured credential-failure message.

    Parameters
    ----------
    missing:
        List of missing credentials from :func:`preflight_check_profile`.
    pipeline_name:
        The pipeline name.
    profile_name:
        The profile name.
    is_tty:
        Whether stdout is a TTY. Auto-detected if None.

    Returns
    -------
    str
        The rendered message.
    """
    if is_tty is None:
        is_tty = sys.stdout.isatty()

    lines: list[str] = []

    if pipeline_name and profile_name:
        lines.append(
            f"Pipeline '{pipeline_name}' (profile '{profile_name}') "
            f"needs credentials for:"
        )
    else:
        lines.append("Missing credentials for:")

    # Group by env_var for cleaner display
    by_env: dict[str, list[str]] = {}
    for m in missing:
        key = m["env_var"]
        by_env.setdefault(key, []).append(f"{m['agent']} (slot: {m['slot']})")

    for env_var, slots in by_env.items():
        lines.append(f"  • {', '.join(slots)} — no {env_var} found")

    # Vendor-aware guidance: point the user at a profile that works with the
    # credentials they DO have (or list what to set), instead of leaving them
    # to guess.
    guidance = _credential_guidance(profile_name)
    if guidance:
        lines.append("")
        lines.extend(guidance)

    if is_tty:
        lines.append("")
        lines.append("Options:")
        lines.append("  [1] Abort")
        lines.append(
            f"  [2] Pick a different profile "
            f"(run `megaplan list profiles --pipeline {pipeline_name}`)"
        )
        lines.append("  [3] Provide a key now (paste, will not be persisted)")
        lines.append("  [4] Sign in (opens auth flow)")
    elif not guidance:
        # Non-TTY with no tailored guidance — fall back to the generic hint.
        lines.append("")
        lines.append(
            "Set the required environment variables and re-run, "
            "or pick a different profile."
        )

    return "\n".join(lines)


def preflight_or_raise(
    profile: dict[str, str],
    *,
    pipeline_name: str = "",
    profile_name: str = "",
    vendor: str | None = None,
) -> None:
    """Run credential preflight and exit with code 7 if credentials are missing.

    In TTY mode, renders the interactive prompt. In non-TTY mode, prints
    to stderr and exits 7.

    Raises SystemExit(7) on credential failure.
    """
    missing = preflight_check_profile(
        profile,
        pipeline_name=pipeline_name,
        profile_name=profile_name,
        vendor=vendor,
    )

    if not missing:
        return  # All good

    is_tty = sys.stdout.isatty()
    message = render_credential_failure(
        missing,
        pipeline_name=pipeline_name,
        profile_name=profile_name,
        is_tty=is_tty,
    )

    if is_tty:
        print(message)
        try:
            choice = input("Select an option [1]: ").strip()
        except (EOFError, KeyboardInterrupt, OSError):
            sys.exit(7)  # No answer: fail closed exactly as before.
        if choice == "4":
            # Sign in: hand the terminal to the interactive onboarding flow.
            # The flow persists into omp's own stores (never this process's
            # environment), so afterwards readiness is re-checked from
            # detect.scan_providers READY statuses for the failing slots'
            # providers. Onboarding must never crash past this point — any
            # failure falls through to exit 7.
            try:
                from agentbox.onboarding.flow import run_flow

                ready = run_flow().exit_code == 0 and _slots_ready_after_flow(
                    missing
                )
            except Exception:
                ready = False  # Onboarding unavailable/failed: exit 7 path.
            if ready:
                return  # Every previously-missing slot is ready; continue.
        sys.exit(7)
    else:
        # Non-TTY: structured message to stderr, exit 7
        print(message, file=sys.stderr)
        sys.exit(7)
