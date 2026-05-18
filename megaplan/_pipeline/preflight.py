"""Credential preflight for YAML pipelines.

Walks the resolved profile slots used by a YAML pipeline, maps agents and
providers to credential requirements, and validates that the user has the
required credentials before any stage fires.

Non-TTY mode: prints a structured credential message to stderr and exits 7.
TTY mode: renders a structured prompt with options.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# ── Agent → provider → required env var mappings ──────────────────────
# Reuses and extends the mappings from megaplan.cloud.preflight.

_AGENT_ENV_HINTS: dict[str, tuple[str, ...]] = {
    "claude": ("ANTHROPIC_API_KEY",),
    "shannon": ("ANTHROPIC_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
}

_PROVIDER_ENV_HINTS: dict[str, tuple[str, ...]] = {
    "deepseek": ("DEEPSEEK_API_KEY",),
    "fireworks": ("FIREWORKS_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}

# ── Credential checking ───────────────────────────────────────────────


def _parse_agent_spec(spec: str) -> tuple[str, str | None]:
    """Parse an agent spec string into (agent, model)."""
    from megaplan.types import parse_agent_spec

    return parse_agent_spec(spec)


def _check_credential(env_var: str) -> bool:
    """Check if an environment variable is set (non-empty)."""
    return bool(os.environ.get(env_var, "").strip())


def _required_env_vars_for_slot(agent_spec: str, slot_name: str) -> list[tuple[str, str]]:
    """Return list of (env_var, display_name) required for a slot.

    For hermes specs, extracts the provider from the model string
    (e.g. ``hermes:fireworks:model`` → FIREWORKS_API_KEY).
    """
    agent, model = _parse_agent_spec(agent_spec)
    required: list[tuple[str, str]] = []

    if agent == "hermes" and model:
        # Extract provider: hermes:provider:actual-model
        parts = model.split(":", 1)
        provider = parts[0] if parts else None
        if provider and provider in _PROVIDER_ENV_HINTS:
            for env_var in _PROVIDER_ENV_HINTS[provider]:
                required.append((env_var, f"{agent}/{provider}"))
        else:
            # Unknown provider — assume it needs whatever the agent normally needs
            pass
    elif agent in _AGENT_ENV_HINTS:
        for env_var in _AGENT_ENV_HINTS[agent]:
            required.append((env_var, agent))

    return required


def preflight_check_profile(
    profile: dict[str, str],
    *,
    pipeline_name: str = "",
    profile_name: str = "",
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
        required = _required_env_vars_for_slot(spec, slot)
        for env_var, display_name in required:
            if not _check_credential(env_var):
                missing.append(
                    {
                        "slot": slot,
                        "spec": spec,
                        "agent": display_name,
                        "env_var": env_var,
                    }
                )

    return missing


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
    else:
        # Non-TTY: add a hint but no interactive prompt
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
        # In TTY mode, we could prompt for input. For Sprint A, just exit 7
        # with the structured message. Interactive credential input (option 3)
        # is deferred to a follow-up.
        sys.exit(7)
    else:
        # Non-TTY: structured message to stderr, exit 7
        print(message, file=sys.stderr)
        sys.exit(7)
