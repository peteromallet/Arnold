from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

from .._core import user_config as _user_config_module
from .._core.user_config import VALID_VENDORS
from ..types import (
    PREMIUM_AGENT,
    _PREMIUM_VENDORS,
    format_agent_spec,
    is_premium_placeholder_agent,
    parse_agent_spec,
    resolve_premium_placeholder_spec,
)
from arnold.pipelines.megaplan.step_contracts import build_default_agent_routing

log = logging.getLogger("megaplan")

# One-shot guard so the stale-override warning fires at most once per phase
# per process (apply_profile_expansion runs many times per plan).
_WARNED_STALE_OVERRIDE: set[tuple[str, str]] = set()

DEFAULT_AGENT_ROUTING: dict[str, str] = build_default_agent_routing()
KNOWN_AGENTS = ["claude", "codex", "hermes", "shannon"]
ROBUSTNESS_LEVELS = ("bare", "light", "full", "thorough", "extreme")
ROBUSTNESS_ALIASES: dict[str, str] = {
    "tiny": "bare",
    "standard": "full",
    "robust": "thorough",
    "superrobust": "extreme",
}
ROBUSTNESS_ACCEPTED = tuple(ROBUSTNESS_LEVELS) + tuple(ROBUSTNESS_ALIASES.keys())

VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())
PROFILE_METADATA_KEYS = frozenset({
    "vendor_locked",
    "default",
    "extends",
    "tier_models",
    "prep_models",
    "max_tasks_per_batch",
    "adaptive_critique",
    "critic_model",
})

SYSTEM_DEFAULT_PROFILE = "partnered"
VALID_CRITIC_CHOICES = ("kimi", "cross")
VALID_DEPTH_CHOICES = ("minimal", "low", "medium", "high", "xhigh", "max")
VALID_DEEPSEEK_PROVIDER_CHOICES = ("fireworks", "direct")
DEFAULT_DEEPSEEK_PROVIDER = "direct"
KIMI_SPEC = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
FIREWORKS_DEEPSEEK_V4_PRO_SPEC = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
DIRECT_DEEPSEEK_V4_PRO_SPEC = "hermes:deepseek:deepseek-v4-pro"
DIRECT_DEEPSEEK_V4_FLASH_SPEC = "hermes:deepseek:deepseek-v4-flash"
PREP_MODEL_STAGES = ("triage", "fanout", "distill")
CANONICAL_PREP_MODELS: dict[str, str] = {
    "triage": DIRECT_DEEPSEEK_V4_PRO_SPEC,
    "fanout": DIRECT_DEEPSEEK_V4_PRO_SPEC,
    "distill": DIRECT_DEEPSEEK_V4_PRO_SPEC,
}
READ_ONLY_PREP_AGENTS = frozenset({"claude", "shannon", "codex", "hermes"})
DEPTH_AUTHOR_PHASES = frozenset({
    "plan",
    "revise",
    "loop_plan",
    "tiebreaker_researcher",
    "tiebreaker_challenger",
})

_CLAUDE_MODEL_TO_CODEX_SPEC: tuple[tuple[str, str], ...] = (
    ("haiku", "codex:gpt-5.4"),
    ("sonnet", "codex:gpt-5.4"),
    ("opus", "codex:gpt-5.5"),
)
_CODEX_MODEL_TO_CLAUDE_SPEC: tuple[tuple[str, str], ...] = (
    ("gpt-5.4", "claude:claude-sonnet-4-6"),
    ("gpt-5.5", "claude:claude-opus-4-7"),
)
_NAMED_VENDOR_PROFILES = {"all-codex": "codex", "variable-codex": "codex"}


def _cli_error(code: str, message: str) -> Exception:
    from ..types import CliError

    return CliError(code, message)


def _known_profiles_text(profiles: dict[str, dict[str, str]]) -> str:
    names = sorted(profiles)
    return ", ".join(names) if names else "(none)"


def _resolve_default_vendor() -> str:
    return _user_config_module.default_vendor()


def effective_premium_vendor(
    args: argparse.Namespace | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    """Return the concrete vendor that symbolic ``premium`` specs mean."""

    def _validate(source: str, value: Any) -> str:
        if not isinstance(value, str) or value not in VALID_VENDORS:
            raise _cli_error(
                "invalid_vendor",
                f"{source} must be one of {', '.join(VALID_VENDORS)}; got {value!r}",
            )
        return value

    cli_vendor = getattr(args, "vendor", None) if args is not None else None
    if cli_vendor is not None:
        return _validate("CLI --vendor", cli_vendor)
    if config is not None and "vendor" in config:
        return _validate("loaded config vendor", config.get("vendor"))
    return _validate("project default vendor", _resolve_default_vendor())


def normalize_robustness(value: Any) -> str:
    if isinstance(value, str):
        if value in ROBUSTNESS_LEVELS:
            return value
        if value in ROBUSTNESS_ALIASES:
            return ROBUSTNESS_ALIASES[value]
    return "full"


def validate_prep_stage_provider(
    raw_spec: Any,
    *,
    stage: str,
    path: Any | None = None,
    profile_name: str | None = None,
) -> str:
    from . import _raise_invalid_profile

    key = f"prep_models.{stage}"
    has_profile_context = path is not None and profile_name is not None

    def _fail(message: str) -> None:
        if has_profile_context:
            _raise_invalid_profile(path, str(profile_name), key, message)
        raise _cli_error("invalid_profile", f"Invalid prep model {key}: {message}")

    if stage not in PREP_MODEL_STAGES:
        _fail(f"unknown prep stage '{stage}'. Valid stages: {', '.join(PREP_MODEL_STAGES)}")
    if not isinstance(raw_spec, str) or not raw_spec.strip():
        _fail(f"expected a non-empty string agent spec, got {type(raw_spec).__name__}")
    spec = raw_spec.strip()
    parsed = parse_agent_spec(spec)
    if parsed.agent not in KNOWN_AGENTS and not is_premium_placeholder_agent(parsed.agent):
        _fail(
            f"unknown agent '{parsed.agent}' in spec {spec!r}. Valid agents: "
            f"{', '.join(KNOWN_AGENTS)} (and 'premium' symbolic placeholder)"
        )
    if parsed.agent not in READ_ONLY_PREP_AGENTS:
        _fail(
            "prep stages currently support only read-only providers: "
            f"{', '.join(sorted(READ_ONLY_PREP_AGENTS))}"
        )
    return spec


def _validate_projected_tier_models(
    tier_models: Any,
    *,
    path: Any = "<calibration_projection>",
    profile_name: str = "calibration_projection",
) -> dict[str, dict[int, str]]:
    from . import _extract_tier_models, _validate_tier_models

    extracted = _extract_tier_models(
        tier_models or {},
        path=path,
        profile_name=profile_name,
    )
    return _validate_tier_models(path, profile_name, extracted)


def _canonicalize_tier_models_for_json(
    tier_models: dict[str, dict[int, str]] | None,
) -> dict[str, dict[str, str]]:
    if not tier_models:
        return {}
    canonical: dict[str, dict[str, str]] = {}
    for phase, tiers in sorted(tier_models.items()):
        canonical[str(phase)] = {
            str(tier): spec for tier, spec in sorted(tiers.items())
        }
    return canonical


def _prep_flat_spec_from_profile(resolved: dict[str, str]) -> str | None:
    spec = resolved.get("prep")
    return spec if isinstance(spec, str) and spec else None


def resolve_prep_models(
    *,
    flat_prep_spec: str | None,
    prep_models: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    explicit = dict(prep_models or {})
    resolved: dict[str, str] = {}
    canonical_fallback_used: dict[str, bool] = {}
    flat_agent = parse_agent_spec(flat_prep_spec).agent if flat_prep_spec else None
    for stage in PREP_MODEL_STAGES:
        if stage in explicit:
            resolved[stage] = explicit[stage]
            canonical_fallback_used[stage] = False
        elif flat_agent == "codex" and stage in {"triage", "distill"}:
            resolved[stage] = flat_prep_spec or "codex"
            canonical_fallback_used[stage] = False
        else:
            resolved[stage] = CANONICAL_PREP_MODELS[stage]
            canonical_fallback_used[stage] = True
    trace = {
        "flat_prep_input": flat_prep_spec,
        "explicit_prep_models": explicit,
        "resolved_stage_models": dict(resolved),
        "canonical_fallback_used": canonical_fallback_used,
    }
    return resolved, trace


def resolve_pipeline_profile(
    cli_profile: str | None,
    *,
    pipeline_name: str,
    system_profiles: dict[str, dict[str, str]] | None = None,
    system_metadata: dict[str, dict[str, Any]] | None = None,
    pipeline_local_profiles: dict[str, dict[str, str]] | None = None,
    pipeline_local_metadata: dict[str, dict[str, Any]] | None = None,
    default_profile: str | None = None,
) -> dict[str, str]:
    from . import (
        _load_pipeline_local_metadata,
        _load_pipeline_local_profiles,
        _resolve_with_inheritance,
        load_profile_metadata,
        load_profiles,
    )

    if system_profiles is None:
        system_profiles = load_profiles()
    if system_metadata is None:
        system_metadata = load_profile_metadata()
    if pipeline_local_profiles is None:
        pipeline_local_profiles = _load_pipeline_local_profiles(pipeline_name)
    if pipeline_local_metadata is None:
        pipeline_local_metadata = _load_pipeline_local_metadata(pipeline_name)

    if cli_profile:
        profile_name = cli_profile
        if cli_profile.startswith("@"):
            rest = cli_profile[1:]
            if ":" in rest:
                ref_pipeline, ref_profile = rest.split(":", 1)
                if ref_pipeline == pipeline_name or not ref_pipeline:
                    profile_name = ref_profile
                else:
                    cross_local = _load_pipeline_local_profiles(ref_pipeline)
                    cross_meta = _load_pipeline_local_metadata(ref_pipeline)
                    return _resolve_with_inheritance(
                        ref_profile,
                        system_profiles=system_profiles,
                        system_metadata=system_metadata,
                        pipeline_local_profiles=cross_local,
                        pipeline_local_metadata=cross_meta,
                    )
            else:
                profile_name = rest

        if profile_name in pipeline_local_profiles:
            return _resolve_with_inheritance(
                profile_name,
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles=pipeline_local_profiles,
                pipeline_local_metadata=pipeline_local_metadata,
            )
        if profile_name in system_profiles:
            return _resolve_with_inheritance(
                profile_name,
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles=pipeline_local_profiles,
                pipeline_local_metadata=pipeline_local_metadata,
            )
        raise _cli_error(
            "unknown_profile",
            f"Unknown profile '{cli_profile}'. "
            f"Known pipeline-local: {_known_profiles_text(pipeline_local_profiles)}. "
            f"Known system: {_known_profiles_text(system_profiles)}",
        )

    if pipeline_local_profiles:
        first_name = next(iter(pipeline_local_profiles))
        return _resolve_with_inheritance(
            first_name,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles=pipeline_local_profiles,
            pipeline_local_metadata=pipeline_local_metadata,
        )

    if default_profile and default_profile.startswith("@"):
        rest = default_profile[1:]
        if ":" in rest:
            _ref_pipeline, ref_profile = rest.split(":", 1)
            if ref_profile in pipeline_local_profiles:
                return _resolve_with_inheritance(
                    ref_profile,
                    system_profiles=system_profiles,
                    system_metadata=system_metadata,
                    pipeline_local_profiles=pipeline_local_profiles,
                    pipeline_local_metadata=pipeline_local_metadata,
                )
            if ref_profile in system_profiles:
                return _resolve_with_inheritance(
                    ref_profile,
                    system_profiles=system_profiles,
                    system_metadata=system_metadata,
                    pipeline_local_profiles=pipeline_local_profiles,
                    pipeline_local_metadata=pipeline_local_metadata,
                )

    for _pname, pmeta in system_metadata.items():
        default_ref = pmeta.get("default")
        if default_ref and isinstance(default_ref, str) and default_ref in system_profiles:
            return _resolve_with_inheritance(
                default_ref,
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles=pipeline_local_profiles,
                pipeline_local_metadata=pipeline_local_metadata,
            )

    if SYSTEM_DEFAULT_PROFILE in system_profiles:
        return _resolve_with_inheritance(
            SYSTEM_DEFAULT_PROFILE,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles=pipeline_local_profiles,
            pipeline_local_metadata=pipeline_local_metadata,
        )

    raise _cli_error(
        "unknown_profile",
        f"Cannot resolve profile for pipeline '{pipeline_name}'. "
        f"No CLI flag, no pipeline-local profiles, no matching system profile, "
        f"and the system default profile '{SYSTEM_DEFAULT_PROFILE}' is not available. "
        f"Pipeline-local: {_known_profiles_text(pipeline_local_profiles)}. "
        f"System: {_known_profiles_text(system_profiles)}.",
    )


def profile_to_phase_models(profile: dict[str, str]) -> list[str]:
    return [f"{phase}={spec}" for phase, spec in profile.items()]


def _swap_premium_spec(spec: str, target_vendor: str) -> str:
    parsed = parse_agent_spec(spec)
    if is_premium_placeholder_agent(parsed.agent):
        raise _cli_error(
            "profile_resolution_mismatch",
            f"Unresolved premium placeholder reached vendor swap: {spec!r}",
        )
    if parsed.agent not in _PREMIUM_VENDORS:
        return spec
    if parsed.agent == target_vendor:
        return spec
    if parsed.model is None and parsed.effort is None:
        return target_vendor
    if parsed.model is None and parsed.effort is not None:
        return f"{target_vendor}:{parsed.effort}"
    model_l = parsed.model.lower()
    if parsed.agent == "claude" and target_vendor == "codex" and parsed.effort is None:
        for needle, codex_spec in _CLAUDE_MODEL_TO_CODEX_SPEC:
            if needle in model_l:
                return codex_spec
    if parsed.agent == "codex" and target_vendor == "claude" and parsed.effort is None:
        for needle, claude_spec in _CODEX_MODEL_TO_CLAUDE_SPEC:
            if needle in model_l:
                return claude_spec
    raise _cli_error(
        "vendor_swap_model_conflict",
        f"Vendor swap would overwrite explicit model pin '{parsed.model}' "
        f"on spec '{spec}' → refusing to produce '{target_vendor}:{parsed.model}'",
    )


def apply_vendor_rewrite(
    profile: dict[str, str],
    vendor: str,
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
    prep_models: dict[str, str] | None = None,
) -> dict[str, str]:
    from ..types import CliError

    if vendor not in VALID_VENDORS:
        raise _cli_error(
            "invalid_vendor",
            f"--vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
        )
    def _resolve_symbolic(spec: str) -> str:
        return format_agent_spec(resolve_premium_placeholder_spec(spec, vendor))

    if tier_models is not None:
        for phase, tiers in tier_models.items():
            for tier_int, spec in tiers.items():
                try:
                    tiers[tier_int] = _swap_premium_spec(_resolve_symbolic(spec), vendor)
                except CliError as e:
                    if e.code == "vendor_swap_model_conflict":
                        raise _cli_error(
                            "vendor_swap_model_conflict",
                            f"Vendor swap conflict on phase '{phase}' tier {tier_int}: {e.message}",
                        ) from e
                    raise
    if prep_models is not None:
        for stage, spec in prep_models.items():
            try:
                prep_models[stage] = _swap_premium_spec(_resolve_symbolic(spec), vendor)
            except CliError as e:
                if e.code == "vendor_swap_model_conflict":
                    raise _cli_error(
                        "vendor_swap_model_conflict",
                        f"Vendor swap conflict on prep stage '{stage}': {e.message}",
                    ) from e
                raise
    result: dict[str, str] = {}
    for phase, spec in profile.items():
        try:
            result[phase] = _swap_premium_spec(_resolve_symbolic(spec), vendor)
        except CliError as e:
            if e.code == "vendor_swap_model_conflict":
                raise _cli_error(
                    "vendor_swap_model_conflict",
                    f"Vendor swap conflict on phase '{phase}': {e.message}",
                ) from e
            raise
    return result


def apply_critic_rewrite(
    profile: dict[str, str],
    critic: str,
    *,
    vendor: str,
    profile_name: str | None = None,
) -> dict[str, str]:
    if critic not in VALID_CRITIC_CHOICES:
        raise _cli_error(
            "invalid_critic",
            f"--critic must be one of {', '.join(VALID_CRITIC_CHOICES)}; got {critic!r}",
        )
    missing = [phase for phase in ("critique", "review") if phase not in profile]
    if missing:
        suffix = f" in profile '{profile_name}'" if profile_name else ""
        raise _cli_error(
            "invalid_critic",
            f"--critic requires both 'critique' and 'review' phases{suffix}; "
            f"missing: {', '.join(missing)}",
        )
    if critic == "kimi":
        result = dict(profile)
        result["critique"] = KIMI_SPEC
        result["review"] = KIMI_SPEC
        return result
    other = "codex" if vendor == "claude" else "claude"
    result = dict(profile)
    for phase in ("critique", "review"):
        parsed = parse_agent_spec(profile[phase])
        if parsed.agent not in _PREMIUM_VENDORS:
            continue
        if parsed.model is None and parsed.effort is None:
            result[phase] = other
        elif parsed.model is None and parsed.effort is not None:
            result[phase] = f"{other}:{parsed.effort}"
        else:
            raise _cli_error(
                "vendor_swap_model_conflict",
                f"Critic cross-swap would overwrite explicit model pin "
                f"'{parsed.model}' on phase '{phase}' spec '{profile[phase]}'",
            )
    return result


def apply_depth_rewrite(
    profile: dict[str, str],
    depth: str,
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
) -> dict[str, str]:
    if depth not in VALID_DEPTH_CHOICES:
        raise _cli_error(
            "invalid_depth",
            f"--depth must be one of {', '.join(VALID_DEPTH_CHOICES)}; got {depth!r}",
        )
    result = dict(profile)
    for phase, spec in profile.items():
        if phase not in DEPTH_AUTHOR_PHASES:
            continue
        parsed = parse_agent_spec(spec)
        if parsed.agent not in _PREMIUM_VENDORS:
            continue
        if parsed.model is not None:
            result[phase] = f"{parsed.agent}:{parsed.model}:{depth}"
        else:
            result[phase] = f"{parsed.agent}:{depth}"
    if tier_models is not None:
        for phase, tiers in tier_models.items():
            if phase not in DEPTH_AUTHOR_PHASES:
                continue
            for tier_int, spec in tiers.items():
                parsed = parse_agent_spec(spec)
                if parsed.agent not in _PREMIUM_VENDORS:
                    continue
                if parsed.model is not None:
                    tiers[tier_int] = f"{parsed.agent}:{parsed.model}:{depth}"
                else:
                    tiers[tier_int] = f"{parsed.agent}:{depth}"
    return result


def _swap_deepseek_provider_spec(spec: str, provider: str) -> str:
    if provider == "direct" and spec == FIREWORKS_DEEPSEEK_V4_PRO_SPEC:
        return DIRECT_DEEPSEEK_V4_PRO_SPEC
    if provider == "fireworks" and spec == DIRECT_DEEPSEEK_V4_PRO_SPEC:
        return FIREWORKS_DEEPSEEK_V4_PRO_SPEC
    return spec


def apply_deepseek_provider_rewrite(
    profile: dict[str, str],
    provider: str,
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
) -> dict[str, str]:
    if provider not in VALID_DEEPSEEK_PROVIDER_CHOICES:
        raise _cli_error(
            "invalid_deepseek_provider",
            f"--deepseek-provider must be one of {', '.join(VALID_DEEPSEEK_PROVIDER_CHOICES)}; "
            f"got {provider!r}",
        )
    if tier_models is not None:
        for _phase, tiers in tier_models.items():
            for tier_int, spec in tiers.items():
                tiers[tier_int] = _swap_deepseek_provider_spec(spec, provider)
    return {
        phase: _swap_deepseek_provider_spec(spec, provider)
        for phase, spec in profile.items()
    }


_PREMIUM_CREDENTIAL_ENV: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
}


def _credential_configured(env_var: str) -> bool:
    if os.environ.get(env_var, "").strip():
        return True
    try:
        from ..runtime.key_pool import _get_api_credential

        return bool(_get_api_credential(env_var))
    except Exception:
        return False


def _premium_cli_route_available(vendor: str) -> bool:
    if vendor not in _PREMIUM_VENDORS:
        return False
    try:
        from ..workers._impl import _is_agent_available
    except Exception:
        return False
    if vendor == "claude":
        return _is_agent_available("claude") or _is_agent_available("shannon")
    return _is_agent_available(vendor)


def _premium_credential_configured(vendor: str) -> bool:
    env_var = _PREMIUM_CREDENTIAL_ENV.get(vendor)
    if env_var and _credential_configured(env_var):
        return True
    return _premium_cli_route_available(vendor)


def _deepseek_credential_configured() -> bool:
    return (
        _credential_configured("DEEPSEEK_API_KEY")
        or _credential_configured("FIREWORKS_API_KEY")
    )


def _best_available_floor_spec(spec: str) -> tuple[str, str | None]:
    parsed = parse_agent_spec(spec)
    if parsed.agent not in _PREMIUM_VENDORS:
        return spec, None
    missing_primary = (
        f"no premium credential or CLI route detected for vendor={parsed.agent}"
    )
    if _premium_credential_configured(parsed.agent):
        return spec, None
    other = "codex" if parsed.agent == "claude" else "claude"
    missing_other = f"no premium credential or CLI route detected for vendor={other}"
    if _premium_credential_configured(other):
        return _swap_premium_spec(spec, other), missing_primary
    if _deepseek_credential_configured():
        return (
            DIRECT_DEEPSEEK_V4_PRO_SPEC,
            f"{missing_primary}; {missing_other}; using DeepSeek credential floor",
        )
    return spec, None


def _record_routing_degradation(
    degradations: list[dict[str, Any]],
    *,
    phase: str,
    tier: int | None,
    from_spec: str,
    to_spec: str,
    reason: str | None,
) -> None:
    if from_spec == to_spec or not reason:
        return
    item: dict[str, Any] = {
        "phase": phase,
        "from": from_spec,
        "to": to_spec,
        "reason": reason,
    }
    if tier is not None:
        item["tier"] = tier
    degradations.append(item)


def _warn_routing_degradations(degradations: list[dict[str, Any]]) -> None:
    if not degradations:
        return
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for item in degradations:
        phase = str(item.get("phase") or "?")
        to_spec = str(item.get("to") or "?")
        reason = str(item.get("reason") or "unknown reason")
        tier = item.get("tier")
        grouped.setdefault((phase, to_spec, reason), []).append(
            str(tier) if tier is not None else ""
        )
    parts: list[str] = []
    for (phase, to_spec, reason), tiers in grouped.items():
        tier_values = [tier for tier in tiers if tier]
        if tier_values:
            parts.append(f"{phase} tier {','.join(tier_values)} -> {to_spec} ({reason})")
        else:
            parts.append(f"{phase} -> {to_spec} ({reason})")
    log.warning("M_WARN_ROUTING_DEGRADED %s", "; ".join(parts))


def apply_available_model_floor(
    profile: dict[str, str],
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
    degradations: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    result = dict(profile)
    local_degradations: list[dict[str, Any]] = []
    if "finalize" in result:
        original = result["finalize"]
        floored, reason = _best_available_floor_spec(original)
        result["finalize"] = floored
        _record_routing_degradation(
            local_degradations,
            phase="finalize",
            tier=None,
            from_spec=original,
            to_spec=floored,
            reason=reason,
        )
    if tier_models is not None:
        execute_tiers = tier_models.get("execute")
        if isinstance(execute_tiers, dict):
            for tier_int, spec in list(execute_tiers.items()):
                floored, reason = _best_available_floor_spec(spec)
                execute_tiers[tier_int] = floored
                _record_routing_degradation(
                    local_degradations,
                    phase="execute",
                    tier=tier_int,
                    from_spec=spec,
                    to_spec=floored,
                    reason=reason,
                )
    if degradations is not None:
        degradations.extend(local_degradations)
    _warn_routing_degradations(local_degradations)
    return result


def _profile_has_premium_slots(profile: dict[str, str]) -> bool:
    for spec in profile.values():
        parsed = parse_agent_spec(spec)
        if parsed.agent in _PREMIUM_VENDORS or is_premium_placeholder_agent(parsed.agent):
            return True
    return False


def _validate_resolved_profile_invariants(
    profile_name: str,
    resolved: dict[str, str],
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
    prep_models: dict[str, str] | None = None,
) -> None:
    bad: list[str] = []
    for phase, spec in resolved.items():
        if is_premium_placeholder_agent(parse_agent_spec(spec).agent):
            bad.append(f"{phase}={spec}")
    if tier_models:
        for phase, tiers in tier_models.items():
            for tier_int, spec in tiers.items():
                if is_premium_placeholder_agent(parse_agent_spec(spec).agent):
                    bad.append(f"tier_models.{phase}.{tier_int}={spec}")
    if prep_models:
        for stage, spec in prep_models.items():
            if is_premium_placeholder_agent(parse_agent_spec(spec).agent):
                bad.append(f"prep_models.{stage}={spec}")
    if bad:
        raise _cli_error(
            "profile_resolution_mismatch",
            f"profile={profile_name} resolved with symbolic premium placeholders still present: "
            f"{', '.join(bad)}",
        )


def _validate_named_profile_invariants(
    profile_name: str,
    resolved: dict[str, str],
    *,
    tier_models: dict[str, dict[int, str]] | None = None,
) -> None:
    expected = _NAMED_VENDOR_PROFILES.get(profile_name)
    if expected is None:
        return
    bad: list[str] = []
    for phase, spec in resolved.items():
        if phase == "feedback":
            continue
        agent, _model = parse_agent_spec(spec)
        if agent != expected:
            bad.append(f"{phase}={spec}")
    premium_agents = frozenset({"claude", "codex"})
    if tier_models:
        for phase, tiers in tier_models.items():
            if phase == "feedback":
                continue
            for tier_int, spec in tiers.items():
                agent, _model = parse_agent_spec(spec)
                if agent in premium_agents and agent != expected:
                    bad.append(f"tier_models.{phase}.{tier_int}={spec}")
    if bad:
        raise _cli_error(
            "profile_resolution_mismatch",
            f"profile={profile_name} expected {expected} on every non-feedback "
            f"phase but resolved to: {', '.join(bad)}. "
            f"Mark the profile vendor_locked=true or pass --vendor {expected} explicitly.",
        )


def apply_profile_expansion(
    args: argparse.Namespace,
    project_dir: Path | None,
    state: dict | None = None,
) -> argparse.Namespace:
    from . import (
        _resolve_prep_models_with_inheritance,
        _resolve_tier_models_with_inheritance,
        load_profile_metadata,
        load_profiles,
        resolve_profile,
    )
    from ..types import CliError

    if getattr(args, "_profile_applied", False):
        return args

    preexpanded_tier_models = bool(getattr(args, "tier_models", None))
    cli_phase_models = list(getattr(args, "phase_model", None) or [])
    raw_cli_steps = {pm.split("=", 1)[0] for pm in cli_phase_models if "=" in pm}
    if preexpanded_tier_models:
        live_steps = getattr(args, "_live_phase_model_steps", set())
        cli_steps = set(live_steps) if isinstance(live_steps, set) else set()
    else:
        cli_steps = raw_cli_steps
    args._live_phase_model_steps = set(cli_steps)

    phase_models = list(cli_phase_models)

    profile_name = getattr(args, "profile", None)
    if profile_name is None and state is not None:
        profile_name = (state.get("config") or {}).get("profile")
    if profile_name is None:
        vendor_without_profile = getattr(args, "vendor", None)
        if vendor_without_profile is None and state is not None:
            vendor_without_profile = (state.get("config") or {}).get("vendor")
        if vendor_without_profile in VALID_VENDORS:
            profile_name = f"all-{vendor_without_profile}"
            args.profile = profile_name

    profile_steps: set[str] = set()
    if profile_name:
        profiles = load_profiles(project_dir=project_dir)
        metadata = load_profile_metadata(project_dir=project_dir)
        resolved = resolve_profile(profile_name, profiles)
        profile_meta = metadata.get(profile_name, {})
        vendor_locked = bool(profile_meta.get("vendor_locked", False))

        tier_models: dict[str, dict[int, str]] | None = None
        try:
            tier_models = _resolve_tier_models_with_inheritance(
                profile_name,
                system_profiles=profiles,
                system_metadata=metadata,
                pipeline_local_profiles={},
                pipeline_local_metadata={},
            )
        except CliError:
            tier_models = None
        if not tier_models:
            tier_models = None

        try:
            inherited_prep_models = _resolve_prep_models_with_inheritance(
                profile_name,
                system_profiles=profiles,
                system_metadata=metadata,
                pipeline_local_profiles={},
                pipeline_local_metadata={},
            )
        except CliError:
            inherited_prep_models = {}

        cli_vendor = getattr(args, "vendor", None)
        cli_critic = getattr(args, "critic", None)
        cli_depth = getattr(args, "depth", None)
        cli_deepseek_provider = getattr(args, "deepseek_provider", None)
        state_vendor = None
        state_critic = None
        state_depth = None
        state_deepseek_provider = None
        if state is not None:
            cfg = state.get("config") or {}
            state_vendor = cfg.get("vendor")
            state_critic = cfg.get("critic")
            state_depth = cfg.get("depth")
            state_deepseek_provider = cfg.get("deepseek_provider")
        effective_vendor_flag = cli_vendor or state_vendor
        effective_critic_flag = cli_critic or state_critic
        effective_depth_flag = cli_depth or state_depth
        effective_deepseek_provider_flag = (
            cli_deepseek_provider
            or state_deepseek_provider
            or DEFAULT_DEEPSEEK_PROVIDER
        )

        if not vendor_locked:
            state_config = (state.get("config") or {}) if state is not None else None
            vendor = effective_premium_vendor(args, state_config)
            if _profile_has_premium_slots(resolved) or inherited_prep_models:
                resolved = apply_vendor_rewrite(
                    resolved,
                    vendor,
                    tier_models=tier_models,
                    prep_models=inherited_prep_models,
                )
            if effective_depth_flag is not None:
                resolved = apply_depth_rewrite(resolved, effective_depth_flag, tier_models=tier_models)
            if effective_critic_flag is not None:
                if effective_critic_flag not in VALID_CRITIC_CHOICES:
                    raise _cli_error(
                        "invalid_critic",
                        f"--critic must be one of {', '.join(VALID_CRITIC_CHOICES)}; got {effective_critic_flag!r}",
                    )
                resolved = apply_critic_rewrite(
                    resolved,
                    effective_critic_flag,
                    vendor=vendor,
                    profile_name=profile_name,
                )
        elif effective_depth_flag is not None:
            resolved = apply_depth_rewrite(resolved, effective_depth_flag, tier_models=tier_models)

        routing_degradations: list[dict[str, Any]] = []
        resolved = apply_available_model_floor(
            resolved,
            tier_models=tier_models,
            degradations=routing_degradations,
        )
        resolved = apply_deepseek_provider_rewrite(resolved, effective_deepseek_provider_flag, tier_models=tier_models)

        _validate_named_profile_invariants(profile_name, resolved, tier_models=tier_models)

        prep_models, prep_trace = resolve_prep_models(
            flat_prep_spec=_prep_flat_spec_from_profile(resolved),
            prep_models=inherited_prep_models,
        )
        _validate_resolved_profile_invariants(
            profile_name,
            resolved,
            tier_models=tier_models,
            prep_models=prep_models,
        )

        if tier_models:
            for phase in ("execute", "critique"):
                if phase in cli_steps:
                    tier_models.pop(phase, None)
        args.tier_models = tier_models
        args.routing_degradations = routing_degradations
        args.prep_models = prep_models
        args.prep_model_resolver_trace = prep_trace

        for pm in profile_to_phase_models(resolved):
            if "=" not in pm:
                continue
            step = pm.split("=", 1)[0]
            if step in cli_steps:
                continue
            phase_models.append(pm)
            profile_steps.add(step)
        args.profile = profile_name
    elif state is not None:
        config = state.get("config") or {}
        state_prep_models = config.get("prep_models")
        if isinstance(state_prep_models, dict):
            args.prep_models = dict(state_prep_models)
        state_prep_trace = config.get("prep_model_resolver_trace")
        if isinstance(state_prep_trace, dict):
            args.prep_model_resolver_trace = dict(state_prep_trace)

    if state is not None:
        persisted = list((state.get("config") or {}).get("phase_model") or [])
        profile_block_start = len(cli_phase_models)
        profile_default_specs: dict[str, str] = {}
        for entry in phase_models[profile_block_start:]:
            if isinstance(entry, str) and "=" in entry:
                _ps, _pv = entry.split("=", 1)
                profile_default_specs.setdefault(_ps, _pv)
        latest_persisted_index_by_step = {
            pm.split("=", 1)[0]: index
            for index, pm in enumerate(persisted)
            if isinstance(pm, str) and "=" in pm
        }
        for index, pm in enumerate(persisted):
            if "=" not in pm:
                continue
            step = pm.split("=", 1)[0]
            if latest_persisted_index_by_step.get(step) != index:
                continue
            persisted_spec = pm.split("=", 1)[1]
            if step in cli_steps:
                continue
            if step in profile_steps:
                current_default = profile_default_specs.get(step)
                if (
                    current_default is not None
                    and current_default != persisted_spec
                    and (step, persisted_spec) not in _WARNED_STALE_OVERRIDE
                ):
                    _WARNED_STALE_OVERRIDE.add((step, persisted_spec))
                    log.warning(
                        "M_WARN_STALE_PHASE_OVERRIDE persisted phase_model pin "
                        "%s=%s shadows the profile default %s=%s, which has since "
                        "changed. The persisted pin still wins. If this is stale, "
                        "clear it with `megaplan override set-model` / `set-vendor`.",
                        step, persisted_spec, step, current_default,
                    )
                phase_models.insert(profile_block_start, pm)
                profile_block_start += 1
                cli_steps.add(step)
            else:
                phase_models.append(pm)
                cli_steps.add(step)

    # Persisted phase_model pins are merged after profile tier tables are
    # resolved, so they must suppress the matching tier table here too. Without
    # this, a stored execute=codex:... pin can still leave tier_models.execute
    # active and route lower-complexity batches through a profile default.
    tier_models_after_persisted = getattr(args, "tier_models", None)
    if tier_models_after_persisted:
        for phase in ("execute", "critique"):
            if phase in cli_steps:
                tier_models_after_persisted.pop(phase, None)
        args.tier_models = tier_models_after_persisted or None

    args.phase_model = phase_models
    args._profile_applied = True
    return args


__all__ = [
    "CANONICAL_PREP_MODELS",
    "DEFAULT_AGENT_ROUTING",
    "DEFAULT_DEEPSEEK_PROVIDER",
    "DEPTH_AUTHOR_PHASES",
    "DIRECT_DEEPSEEK_V4_FLASH_SPEC",
    "DIRECT_DEEPSEEK_V4_PRO_SPEC",
    "FIREWORKS_DEEPSEEK_V4_PRO_SPEC",
    "KIMI_SPEC",
    "KNOWN_AGENTS",
    "PREP_MODEL_STAGES",
    "PROFILE_METADATA_KEYS",
    "READ_ONLY_PREP_AGENTS",
    "ROBUSTNESS_ACCEPTED",
    "ROBUSTNESS_LEVELS",
    "SYSTEM_DEFAULT_PROFILE",
    "VALID_CRITIC_CHOICES",
    "VALID_DEEPSEEK_PROVIDER_CHOICES",
    "VALID_DEPTH_CHOICES",
    "VALID_PHASE_KEYS",
    "_canonicalize_tier_models_for_json",
    "_resolve_default_vendor",
    "_validate_named_profile_invariants",
    "_validate_projected_tier_models",
    "_validate_resolved_profile_invariants",
    "apply_critic_rewrite",
    "apply_available_model_floor",
    "apply_deepseek_provider_rewrite",
    "apply_depth_rewrite",
    "apply_profile_expansion",
    "apply_vendor_rewrite",
    "effective_premium_vendor",
    "normalize_robustness",
    "profile_to_phase_models",
    "resolve_pipeline_profile",
    "resolve_prep_models",
    "validate_prep_stage_provider",
]
