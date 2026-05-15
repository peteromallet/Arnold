from __future__ import annotations

import argparse
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from .._core.io import config_dir
from .._core import user_config as _user_config_module
from .._core.user_config import VALID_VENDORS
from ..types import CliError, DEFAULT_AGENT_ROUTING, KNOWN_AGENTS, parse_agent_spec


def _resolve_default_vendor() -> str:
    """Module-local hop to the user-config default.

    Indirection exists so tests can ``monkeypatch.setattr(profiles, "_resolve_default_vendor", ...)``
    without having to reach into ``megaplan._core.user_config``. Production
    callers go through here, never call ``user_config.default_vendor`` directly.
    """
    return _user_config_module.default_vendor()

VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())

# Profile-level metadata keys that are *not* phase mappings. These are
# stripped before validation so the loader doesn't complain about them,
# and surfaced via ``ProfileSource.metadata`` for downstream consumers
# (currently just ``--vendor`` / ``--critic`` rejection on locked profiles).
PROFILE_METADATA_KEYS = frozenset({"vendor_locked"})

VALID_CRITIC_CHOICES = ("kimi", "cross")
VALID_DEPTH_CHOICES = ("minimal", "low", "medium", "high", "xhigh", "max")
VALID_DEEPSEEK_PROVIDER_CHOICES = ("fireworks", "direct")
DEFAULT_DEEPSEEK_PROVIDER = "direct"
KIMI_SPEC = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
FIREWORKS_DEEPSEEK_V4_PRO_SPEC = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
DIRECT_DEEPSEEK_V4_PRO_SPEC = "hermes:deepseek:deepseek-v4-pro"
_PREMIUM_VENDORS = frozenset({"claude", "codex"})

# Author-side phases that ``--depth`` rewrites. Critic phases (critique,
# gate, review) and mechanical phases (prep, finalize, execute,
# loop_execute) are intentionally excluded — see the asymmetry principle
# in docs/megaplan-rubric.md.
DEPTH_AUTHOR_PHASES = frozenset({
    "plan",
    "revise",
    "loop_plan",
    "tiebreaker_researcher",
    "tiebreaker_challenger",
})


def _known_profiles_text(profiles: dict[str, dict[str, str]]) -> str:
    names = sorted(profiles)
    return ", ".join(names) if names else "(none)"


def _raise_invalid_profile(path: Any, profile_name: str, key: str, message: str) -> None:
    raise CliError(
        "invalid_profile",
        f"Invalid profile '{profile_name}' in {path}: {message} (key: {key})",
    )


def _split_profile_dict(
    path: Any, profile_name: str, raw_profile: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a raw profile table into (phase_map, metadata).

    Phase entries are everything whose key is a known phase from
    ``VALID_PHASE_KEYS``. Metadata entries are the recognised
    profile-level keys from ``PROFILE_METADATA_KEYS`` (currently just
    ``vendor_locked``). Anything else is an error — surfaced by the
    existing validator.
    """
    if not isinstance(raw_profile, dict):
        raise CliError(
            "invalid_profile",
            f"Invalid profile '{profile_name}' in {path}: expected a TOML table of phase keys",
        )
    phase_map: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for key, value in raw_profile.items():
        if key in PROFILE_METADATA_KEYS:
            metadata[str(key)] = value
        else:
            phase_map[str(key)] = value
    return phase_map, metadata


def _validate_metadata(path: Any, profile_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
    validated: dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "vendor_locked":
            if not isinstance(value, bool):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"expected a boolean for 'vendor_locked', got {type(value).__name__}",
                )
            validated["vendor_locked"] = value
        # Future metadata keys go here.
    return validated


def _validate_profile_map(path: Any, profile_name: str, raw_profile: Any) -> dict[str, str]:
    phase_map, _metadata = _split_profile_dict(path, profile_name, raw_profile)
    validated: dict[str, str] = {}
    for phase, raw_spec in phase_map.items():
        if phase not in VALID_PHASE_KEYS:
            _raise_invalid_profile(
                path,
                profile_name,
                str(phase),
                f"unknown phase '{phase}'. Valid phases: {', '.join(sorted(VALID_PHASE_KEYS))}",
            )
        if not isinstance(raw_spec, str):
            _raise_invalid_profile(path, profile_name, phase, f"expected a string agent spec, got {type(raw_spec).__name__}")
        agent, _model = parse_agent_spec(raw_spec)
        if agent not in KNOWN_AGENTS:
            _raise_invalid_profile(
                path,
                profile_name,
                phase,
                f"unknown agent '{agent}' in spec {raw_spec!r}. Valid agents: {', '.join(KNOWN_AGENTS)}",
            )
        validated[str(phase)] = raw_spec
    return validated


def _parse_profiles_doc(
    path: Any, content: str
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    """Return (profiles_phase_maps, profiles_metadata).

    Both dicts are keyed by profile name. Metadata is empty when a
    profile declares no metadata keys.
    """
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise CliError("invalid_profile", f"Malformed TOML in {path}: {exc}") from exc
    if not data:
        return {}, {}
    if not isinstance(data, dict):
        raise CliError("invalid_profile", f"Invalid profile file {path}: expected a TOML object at the top level")
    raw_profiles = data.get("profiles", {})
    if raw_profiles in ({}, None):
        return {}, {}
    if not isinstance(raw_profiles, dict):
        raise CliError("invalid_profile", f"Invalid profile file {path}: [profiles] must be a TOML table")
    profiles: dict[str, dict[str, str]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for profile_name, raw_profile in raw_profiles.items():
        _phase_map, raw_metadata = _split_profile_dict(path, profile_name, raw_profile)
        profiles[profile_name] = _validate_profile_map(path, profile_name, raw_profile)
        validated_metadata = _validate_metadata(path, profile_name, raw_metadata)
        if validated_metadata:
            metadata[profile_name] = validated_metadata
    return profiles, metadata


def _load_profiles_file(
    path: Any,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, {}
    except OSError as exc:
        raise CliError("invalid_profile", f"Unable to read profile file {path}: {exc}") from exc
    return _parse_profiles_doc(path, content)


def _built_in_profile_files() -> list[Any]:
    return sorted(
        (
            entry
            for entry in files("megaplan.profiles").iterdir()
            if entry.is_file() and entry.name.endswith(".toml")
        ),
        key=lambda entry: entry.name,
    )


def load_profile_sources(
    home: Path | None = None,
    project_dir: Path | None = None,
) -> list[tuple[str, str, dict[str, str]]]:
    sources: list[tuple[str, str, dict[str, str]]] = []

    for path in _built_in_profile_files():
        profile_maps, _metadata = _load_profiles_file(path)
        for profile_name, phase_map in profile_maps.items():
            sources.append(("built-in", profile_name, dict(phase_map)))

    user_path = config_dir(home) / "profiles.toml"
    user_profiles, _user_metadata = _load_profiles_file(user_path)
    for profile_name, phase_map in user_profiles.items():
        sources.append(("user", profile_name, dict(phase_map)))

    if project_dir is not None:
        project_path = Path(project_dir) / ".megaplan" / "profiles.toml"
        project_profiles, _project_metadata = _load_profiles_file(project_path)
        for profile_name, phase_map in project_profiles.items():
            sources.append(("project", profile_name, dict(phase_map)))

    return sources


def load_profiles(
    home: Path | None = None,
    project_dir: Path | None = None,
) -> dict[str, dict[str, str]]:
    profiles: dict[str, dict[str, str]] = {}
    for _source_label, profile_name, phase_map in load_profile_sources(home=home, project_dir=project_dir):
        profiles[profile_name] = dict(phase_map)
    return profiles


def load_profile_metadata(
    home: Path | None = None,
    project_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Return per-profile metadata (the non-phase keys, e.g. ``vendor_locked``).

    Later layers override earlier ones, mirroring ``load_profiles``.
    """
    metadata: dict[str, dict[str, Any]] = {}

    for path in _built_in_profile_files():
        _profiles, file_meta = _load_profiles_file(path)
        for profile_name, meta in file_meta.items():
            metadata[profile_name] = dict(meta)

    user_path = config_dir(home) / "profiles.toml"
    _user_profiles, user_meta = _load_profiles_file(user_path)
    for profile_name, meta in user_meta.items():
        metadata[profile_name] = dict(meta)

    if project_dir is not None:
        project_path = Path(project_dir) / ".megaplan" / "profiles.toml"
        _project_profiles, project_meta = _load_profiles_file(project_path)
        for profile_name, meta in project_meta.items():
            metadata[profile_name] = dict(meta)

    return metadata


def resolve_profile(name: str, profiles: dict[str, dict[str, str]]) -> dict[str, str]:
    try:
        return dict(profiles[name])
    except KeyError as exc:
        raise CliError(
            "unknown_profile",
            f"Unknown profile '{name}'. Known profiles: {_known_profiles_text(profiles)}",
        ) from exc


def profile_to_phase_models(profile: dict[str, str]) -> list[str]:
    return [f"{phase}={spec}" for phase, spec in profile.items()]


# ---------------------------------------------------------------------------
# Vendor / critic rewrite logic
# ---------------------------------------------------------------------------


def _swap_premium_spec(spec: str, target_vendor: str) -> str:
    """Swap claude:X <-> codex:X to match ``target_vendor``.

    Non-premium specs (hermes, anything without a known prefix) are
    returned unchanged. The effort suffix (e.g. ``:medium``) is
    preserved verbatim.
    """
    agent, model = parse_agent_spec(spec)
    if agent not in _PREMIUM_VENDORS:
        return spec
    if agent == target_vendor:
        return spec
    return f"{target_vendor}:{model}" if model is not None else target_vendor


def apply_vendor_rewrite(
    profile: dict[str, str],
    vendor: str,
) -> dict[str, str]:
    """Return a copy of ``profile`` with premium slots swapped to ``vendor``.

    Profiles with no claude/codex slots are a silent no-op. Caller is
    responsible for rejecting vendor-locked profiles before getting here.
    """
    if vendor not in VALID_VENDORS:
        raise CliError(
            "invalid_vendor",
            f"--vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
        )
    # feedback is locked at claude:low for cross-run comparability
    return {
        phase: _swap_premium_spec(spec, vendor)
        for phase, spec in profile.items()
        if phase != "feedback"
    } | {"feedback": profile.get("feedback", "claude:low")}


def apply_critic_rewrite(
    profile: dict[str, str],
    critic: str,
    *,
    vendor: str,
    profile_name: str | None = None,
) -> dict[str, str]:
    """Return a copy of ``profile`` with critique+review rewritten per ``critic``.

    ``vendor`` is the *post-vendor-rewrite* vendor — i.e. the result of
    ``apply_vendor_rewrite``. For ``--critic cross`` we pick the
    opposite of ``vendor`` so the critic disagrees with the author by
    construction. Effort tiers are preserved from whatever the profile
    already had for each of the two phases.
    """
    if critic not in VALID_CRITIC_CHOICES:
        raise CliError(
            "invalid_critic",
            f"--critic must be one of {', '.join(VALID_CRITIC_CHOICES)}; got {critic!r}",
        )
    missing = [phase for phase in ("critique", "review") if phase not in profile]
    if missing:
        suffix = f" in profile '{profile_name}'" if profile_name else ""
        raise CliError(
            "invalid_critic",
            f"--critic requires both 'critique' and 'review' phases{suffix}; "
            f"missing: {', '.join(missing)}",
        )

    if critic == "kimi":
        result = dict(profile)
        result["critique"] = KIMI_SPEC
        result["review"] = KIMI_SPEC
        return result

    # critic == "cross": flip premium vendor on critique+review only.
    other = "codex" if vendor == "claude" else "claude"
    result = dict(profile)
    for phase in ("critique", "review"):
        agent, model = parse_agent_spec(profile[phase])
        # Preserve hermes specs as-is when crossing — only premium slots
        # have a meaningful "other vendor."
        if agent not in _PREMIUM_VENDORS:
            continue
        result[phase] = f"{other}:{model}" if model is not None else other
    return result


def apply_depth_rewrite(
    profile: dict[str, str],
    depth: str,
) -> dict[str, str]:
    """Return a copy of ``profile`` with author-phase effort set to ``depth``.

    Only rewrites slots whose agent is claude/codex *and* whose phase is in
    :data:`DEPTH_AUTHOR_PHASES`. Critic phases plateau at their existing
    depth (asymmetry principle); hermes specs are never touched; bare
    ``claude`` (no effort suffix) becomes ``claude:<depth>``.
    """
    if depth not in VALID_DEPTH_CHOICES:
        raise CliError(
            "invalid_depth",
            f"--depth must be one of {', '.join(VALID_DEPTH_CHOICES)}; got {depth!r}",
        )
    result = dict(profile)
    for phase, spec in profile.items():
        if phase not in DEPTH_AUTHOR_PHASES:
            continue
        agent, _model = parse_agent_spec(spec)
        if agent not in _PREMIUM_VENDORS:
            continue
        result[phase] = f"{agent}:{depth}"
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
) -> dict[str, str]:
    """Return a copy of ``profile`` with canonical DeepSeek v4-pro provider swapped.

    This is a provider dial, not a profile-tier dial: it only rewrites the
    canonical DeepSeek V4 Pro specs between Fireworks-direct and DeepSeek's
    direct API. Kimi, non-DeepSeek Fireworks models, and DeepSeek Flash stay
    exactly as declared by the profile.
    """
    if provider not in VALID_DEEPSEEK_PROVIDER_CHOICES:
        raise CliError(
            "invalid_deepseek_provider",
            f"--deepseek-provider must be one of {', '.join(VALID_DEEPSEEK_PROVIDER_CHOICES)}; "
            f"got {provider!r}",
        )
    return {
        phase: _swap_deepseek_provider_spec(spec, provider)
        for phase, spec in profile.items()
    }


def _profile_has_premium_slots(profile: dict[str, str]) -> bool:
    for spec in profile.values():
        agent, _model = parse_agent_spec(spec)
        if agent in _PREMIUM_VENDORS:
            return True
    return False


def apply_profile_expansion(
    args: argparse.Namespace,
    project_dir: Path | None,
    state: dict | None = None,
) -> argparse.Namespace:
    """Expand a --profile into per-phase --phase-model overrides.

    The state fallback is needed because the auto-driver invokes each phase as a
    fresh subprocess that does not propagate the --profile flag, so handlers must
    recover the profile name from state['config']['profile'].
    """
    if getattr(args, "_profile_applied", False):
        return args

    # Snapshot live CLI --phase-model entries *before* we splice in profile
    # defaults. This is what lets us keep CLI > profile precedence even when
    # auto.py spawns step subprocesses without re-passing the original CLI
    # flags: the persisted state below is merged using the same precedence
    # rule (live CLI > persisted CLI > profile).
    cli_phase_models = list(getattr(args, "phase_model", None) or [])
    cli_steps = {pm.split("=", 1)[0] for pm in cli_phase_models if "=" in pm}

    phase_models = list(cli_phase_models)

    profile_name = getattr(args, "profile", None)
    if profile_name is None and state is not None:
        profile_name = (state.get("config") or {}).get("profile")

    profile_steps: set[str] = set()
    if profile_name:
        profiles = load_profiles(project_dir=project_dir)
        metadata = load_profile_metadata(project_dir=project_dir)
        resolved = resolve_profile(profile_name, profiles)
        profile_meta = metadata.get(profile_name, {})
        vendor_locked = bool(profile_meta.get("vendor_locked", False))

        # Resolve vendor + critic + depth with CLI > state > config-default precedence.
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

        # Vendor-locked profiles silently ignore --vendor and --critic.
        # The lock is about which vendor, not which depth — --depth is
        # honored on locked profiles per dial-3 (high-stakes work that
        # warrants poirot may also warrant deep thinking).
        # Resolution order: vendor → depth → critic.
        if not vendor_locked:
            # Always pick a vendor (CLI > state > config default) — even
            # when the profile has no premium slots, picking it is cheap
            # and the rewrite is a no-op. Done this way so the resolved
            # vendor is observable / persistable downstream.
            vendor = effective_vendor_flag
            if vendor is None:
                vendor = _resolve_default_vendor()
            if vendor not in VALID_VENDORS:
                raise CliError(
                    "invalid_vendor",
                    f"--vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
                )
            if _profile_has_premium_slots(resolved):
                resolved = apply_vendor_rewrite(resolved, vendor)
            # Depth rewrite runs against the *post-vendor* state so
            # ``--vendor codex --depth high`` lands on ``codex:high`` for
            # author phases. Honored on locked profiles too (see below).
            if effective_depth_flag is not None:
                resolved = apply_depth_rewrite(resolved, effective_depth_flag)
            # Critic rewrite always runs against the *post-vendor* state.
            if effective_critic_flag is not None:
                if effective_critic_flag not in VALID_CRITIC_CHOICES:
                    raise CliError(
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
            # vendor_locked profile: --vendor / --critic are no-ops, but
            # --depth is still applied to author phases.
            resolved = apply_depth_rewrite(resolved, effective_depth_flag)

        resolved = apply_deepseek_provider_rewrite(resolved, effective_deepseek_provider_flag)

        for pm in profile_to_phase_models(resolved):
            if "=" not in pm:
                continue
            step = pm.split("=", 1)[0]
            # Live CLI always wins over profile defaults for the same phase.
            if step in cli_steps:
                continue
            phase_models.append(pm)
            profile_steps.add(step)
        args.profile = profile_name

    # Merge persisted --phase-model overrides from plan state. Effective
    # precedence is: live CLI args > persisted CLI > profile. Persisted
    # phases that are neither on the live CLI nor in the profile get
    # appended; persisted phases that the profile already covered must
    # *win* over the profile entry, so they get prepended after the live
    # CLI block (i.e. before the profile block) to take advantage of
    # resolve_agent_mode's first-match-wins lookup.
    if state is not None:
        persisted = list((state.get("config") or {}).get("phase_model") or [])
        # Index where profile defaults start (right after live CLI entries).
        profile_block_start = len(cli_phase_models)
        for pm in persisted:
            if "=" not in pm:
                continue
            step = pm.split("=", 1)[0]
            if step in cli_steps:
                # Live CLI already covers this phase on the current invocation.
                continue
            if step in profile_steps:
                # Persisted CLI override must beat the profile default.
                phase_models.insert(profile_block_start, pm)
                profile_block_start += 1
                cli_steps.add(step)
            else:
                # No conflict — just fill the gap.
                phase_models.append(pm)
                cli_steps.add(step)

    args.phase_model = phase_models
    args._profile_applied = True
    return args


__all__ = [
    "DEPTH_AUTHOR_PHASES",
    "VALID_CRITIC_CHOICES",
    "VALID_DEEPSEEK_PROVIDER_CHOICES",
    "DEFAULT_DEEPSEEK_PROVIDER",
    "VALID_DEPTH_CHOICES",
    "VALID_PHASE_KEYS",
    "PROFILE_METADATA_KEYS",
    "apply_critic_rewrite",
    "apply_deepseek_provider_rewrite",
    "apply_depth_rewrite",
    "apply_profile_expansion",
    "apply_vendor_rewrite",
    "load_profile_metadata",
    "load_profile_sources",
    "load_profiles",
    "profile_to_phase_models",
    "resolve_profile",
]
