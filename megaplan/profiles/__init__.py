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
PROFILE_METADATA_KEYS = frozenset({"vendor_locked", "default", "extends"})

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
# in docs/megaplan-decision.md.
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
        elif key == "default":
            if not isinstance(value, str):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"expected a string for 'default', got {type(value).__name__}",
                )
            validated["default"] = value
        elif key == "extends":
            if not isinstance(value, str):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"expected a string for 'extends', got {type(value).__name__}",
                )
            validated["extends"] = value
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


# ---------------------------------------------------------------------------
# Pipeline-local profile loading
# ---------------------------------------------------------------------------


def _flatten_profile_keys(
    d: dict[str, Any], prefix: str, out: dict[str, Any]
) -> None:
    """Flatten nested dicts into dotted compound keys.

    ``{"panel_review": {"pessimist": "claude:low"}}`` becomes
    ``{"panel_review.pessimist": "claude:low"}``.
    """
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and not any(
            isinstance(v, dict) for v in value.values()
        ):
            # Shallow dict of scalar values → flatten to dotted keys
            for sub_key, sub_value in value.items():
                out[f"{full_key}.{sub_key}"] = sub_value
        elif isinstance(value, dict):
            _flatten_profile_keys(value, full_key, out)
        else:
            out[full_key] = value


def _pipeline_local_profiles_dir(pipeline_name: str, *, builtin: bool = True) -> Path | None:
    """Return the pipeline-local profiles directory if it exists."""
    import megaplan._pipeline

    if builtin:
        package_file = Path(megaplan._pipeline.__file__).resolve()
        base = package_file.parent.parent / "pipelines" / pipeline_name / "profiles"
    else:
        base = Path.home() / ".megaplan" / "pipelines" / pipeline_name / "profiles"
    return base if base.is_dir() else None


def _load_pipeline_local_profiles(
    pipeline_name: str,
) -> dict[str, dict[str, str]]:
    """Load pipeline-local profiles for *pipeline_name*.

    Pipeline-local profiles define their own TOML slot keys matching YAML
    stage IDs. They bypass ``DEFAULT_AGENT_ROUTING`` validation — the keys
    are validated against the pipeline's stage definitions at compile time,
    not against the fixed planning phase keys.

    Dotted keys (e.g. ``panel_review.pessimist``) are flattened into
    compound keys (``panel_review.pessimist``) so the flat ``dict[str, str]``
    shape is preserved.

    Discovery order: built-in first, then user (~/.megaplan/...).
    User profiles with the same name shadow built-in ones.
    """
    import tomllib as _tomllib

    profiles: dict[str, dict[str, str]] = {}

    for is_builtin in (True, False):
        profiles_dir = _pipeline_local_profiles_dir(pipeline_name, builtin=is_builtin)
        if profiles_dir is None:
            continue
        for toml_file in sorted(profiles_dir.iterdir()):
            if not toml_file.is_file() or not toml_file.name.endswith(".toml"):
                continue
            try:
                raw_text = toml_file.read_text(encoding="utf-8")
                data = _tomllib.loads(raw_text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            raw_profiles = data.get("profiles", {})
            if not isinstance(raw_profiles, dict):
                continue
            for profile_name, raw_profile in raw_profiles.items():
                if not isinstance(raw_profile, dict):
                    continue
                # Flatten nested dicts from dotted TOML keys
                flat: dict[str, Any] = {}
                _flatten_profile_keys(raw_profile, "", flat)
                # Split metadata from phase slots
                phase_map, _raw_meta = _split_profile_dict(
                    toml_file, profile_name, flat
                )
                # Validate agent specs only — allow any slot keys
                validated: dict[str, str] = {}
                for slot, raw_spec in phase_map.items():
                    if not isinstance(raw_spec, str):
                        continue
                    agent, _model = parse_agent_spec(raw_spec)
                    if agent not in KNOWN_AGENTS:
                        continue
                    validated[str(slot)] = raw_spec
                if validated:
                    profiles[profile_name] = validated

    return profiles


def _load_pipeline_local_metadata(
    pipeline_name: str,
) -> dict[str, dict[str, Any]]:
    """Load metadata for pipeline-local profiles."""
    import tomllib as _tomllib

    metadata: dict[str, dict[str, Any]] = {}

    for is_builtin in (True, False):
        profiles_dir = _pipeline_local_profiles_dir(pipeline_name, builtin=is_builtin)
        if profiles_dir is None:
            continue
        for toml_file in sorted(profiles_dir.iterdir()):
            if not toml_file.is_file() or not toml_file.name.endswith(".toml"):
                continue
            try:
                raw_text = toml_file.read_text(encoding="utf-8")
                data = _tomllib.loads(raw_text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            raw_profiles = data.get("profiles", {})
            if not isinstance(raw_profiles, dict):
                continue
            for profile_name, raw_profile in raw_profiles.items():
                if not isinstance(raw_profile, dict):
                    continue
                _phase_map, raw_meta = _split_profile_dict(
                    toml_file, profile_name, raw_profile
                )
                validated_meta = _validate_metadata(
                    toml_file, profile_name, raw_meta
                )
                if validated_meta:
                    metadata[profile_name] = validated_meta

    return metadata


# ---------------------------------------------------------------------------
# Profile inheritance with cycle detection
# ---------------------------------------------------------------------------


def _resolve_extends_ref(
    ref: str,
    *,
    system_profiles: dict[str, dict[str, str]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str]:
    """Resolve an ``extends`` reference to a concrete profile map.

    Supported formats:
    * ``system:<profile>`` — look up in system profiles.
    * ``@<pipeline>:<profile>`` — look up in pipeline-local profiles.
    """
    if ref.startswith("system:"):
        profile_name = ref[len("system:"):]
        if profile_name in system_profiles:
            return _resolve_with_inheritance(
                profile_name,
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles=pipeline_local_profiles,
                pipeline_local_metadata=pipeline_local_metadata,
                _visited=_visited,
            )
        raise CliError(
            "unknown_profile",
            f"extends references unknown system profile '{profile_name}' "
            f"(from '{ref}')",
        )
    elif ref.startswith("@"):
        # @<pipeline>:<profile>
        rest = ref[1:]  # strip @
        if ":" in rest:
            pipeline_name, profile_name = rest.split(":", 1)
            # Load that pipeline's local profiles
            pl_profiles = _load_pipeline_local_profiles(pipeline_name)
            if profile_name in pl_profiles:
                return _resolve_with_inheritance(
                    profile_name,
                    system_profiles=system_profiles,
                    system_metadata=system_metadata,
                    pipeline_local_profiles=pl_profiles,
                    pipeline_local_metadata=_load_pipeline_local_metadata(pipeline_name),
                    _visited=_visited,
                )
            raise CliError(
                "unknown_profile",
                f"extends references unknown pipeline-local profile "
                f"'{profile_name}' in pipeline '{pipeline_name}' (from '{ref}')",
            )
        raise CliError(
            "invalid_profile",
            f"Invalid extends reference '{ref}': "
            f"@<pipeline>:<profile> format requires a colon",
        )
    else:
        raise CliError(
            "invalid_profile",
            f"Invalid extends reference '{ref}': "
            f"must be 'system:<profile>' or '@<pipeline>:<profile>'",
        )


def _resolve_with_inheritance(
    profile_name: str,
    *,
    system_profiles: dict[str, dict[str, str]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str]:
    """Resolve a profile, applying ``extends`` inheritance with cycle detection.

    The child profile's keys override the parent's. Inheritance chains are
    resolved depth-first. Cycle detection uses a visited set.
    """
    if _visited is None:
        _visited = set()

    if profile_name in _visited:
        raise CliError(
            "invalid_profile",
            f"Cycle detected in profile inheritance: "
            f"{' -> '.join(sorted(_visited))} -> {profile_name}",
        )
    _visited.add(profile_name)

    # Find the profile in pipeline-local first, then system
    profile: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None

    if profile_name in pipeline_local_profiles:
        profile = pipeline_local_profiles[profile_name]
        metadata = pipeline_local_metadata.get(profile_name, {})
    elif profile_name in system_profiles:
        profile = system_profiles[profile_name]
        metadata = system_metadata.get(profile_name, {})

    if profile is None:
        raise CliError(
            "unknown_profile",
            f"Unknown profile '{profile_name}'",
        )

    extends_ref = metadata.get("extends") if metadata else None
    if extends_ref and isinstance(extends_ref, str):
        parent = _resolve_extends_ref(
            extends_ref,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles=pipeline_local_profiles,
            pipeline_local_metadata=pipeline_local_metadata,
            _visited=_visited,
        )
        # Child overrides parent
        merged = dict(parent)
        merged.update(profile)
        return merged

    return dict(profile)


# ---------------------------------------------------------------------------
# 4-layer profile resolution for YAML pipelines
# ---------------------------------------------------------------------------


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
    """Resolve a profile for a YAML pipeline using the locked 4-layer order.

    Resolution order (locked decision #8):
    1. CLI flag (e.g. ``--profile @writing-panel-strict:premium``).
    2. Pipeline-local profiles (``pipelines/<name>/profiles/*.toml``).
    3. System profiles (``megaplan/profiles/*.toml``).
    4. Profile ``default`` field → fail-loud.

    Parameters
    ----------
    cli_profile:
        The raw ``--profile`` value from the CLI. May be a plain name
        (``"partnered"``) or a pipeline-scoped name (``"@writing-panel-strict:premium"``).
    pipeline_name:
        The pipeline name from ``pipeline.yaml`` (``spec.name``).
    system_profiles:
        Pre-loaded system profiles. Loaded lazily if None.
    system_metadata:
        Pre-loaded system profile metadata.
    pipeline_local_profiles:
        Pre-loaded pipeline-local profiles.
    pipeline_local_metadata:
        Pre-loaded pipeline-local profile metadata.
    default_profile:
        The ``default_profile`` field from ``pipeline.yaml``.

    Returns
    -------
    dict[str, str]
        The resolved profile map (slot → agent spec).
    """
    if system_profiles is None:
        system_profiles = load_profiles()
    if system_metadata is None:
        system_metadata = load_profile_metadata()
    if pipeline_local_profiles is None:
        pipeline_local_profiles = _load_pipeline_local_profiles(pipeline_name)
    if pipeline_local_metadata is None:
        pipeline_local_metadata = _load_pipeline_local_metadata(pipeline_name)

    # ── Layer 1: CLI flag ──────────────────────────────────────────
    if cli_profile:
        profile_name = cli_profile
        # Parse @pipeline:profile syntax
        if cli_profile.startswith("@"):
            rest = cli_profile[1:]
            if ":" in rest:
                ref_pipeline, ref_profile = rest.split(":", 1)
                if ref_pipeline == pipeline_name or not ref_pipeline:
                    profile_name = ref_profile
                else:
                    # Cross-pipeline reference — load that pipeline's profiles
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

        # Try pipeline-local first for unscoped names, then system
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
        raise CliError(
            "unknown_profile",
            f"Unknown profile '{cli_profile}'. "
            f"Known pipeline-local: {_known_profiles_text(pipeline_local_profiles)}. "
            f"Known system: {_known_profiles_text(system_profiles)}",
        )

    # ── Layer 2: Pipeline-local profiles ───────────────────────────
    if pipeline_local_profiles:
        # Use the first pipeline-local profile as default
        first_name = next(iter(pipeline_local_profiles))
        return _resolve_with_inheritance(
            first_name,
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles=pipeline_local_profiles,
            pipeline_local_metadata=pipeline_local_metadata,
        )

    # ── Layer 3: System profiles (match by name from default_profile) ──
    if default_profile:
        # Parse @pipeline:profile syntax in default_profile
        if default_profile.startswith("@"):
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

    # ── Layer 4: Profile default field ─────────────────────────────
    # Scan system profiles for one with a "default" metadata field
    for pname, pmeta in system_metadata.items():
        default_ref = pmeta.get("default")
        if default_ref and isinstance(default_ref, str) and default_ref in system_profiles:
            return _resolve_with_inheritance(
                default_ref,
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles=pipeline_local_profiles,
                pipeline_local_metadata=pipeline_local_metadata,
            )

    # ── Fail loud ──────────────────────────────────────────────────
    raise CliError(
        "unknown_profile",
        f"Cannot resolve profile for pipeline '{pipeline_name}'. "
        f"No CLI flag, no pipeline-local profiles, no matching system profile, "
        f"and no system profile with a 'default' field. "
        f"Pipeline-local: {_known_profiles_text(pipeline_local_profiles)}. "
        f"System: {_known_profiles_text(system_profiles)}.",
    )


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


# Profiles whose name asserts the vendor. If resolution drifts away from the
# asserted vendor on any non-feedback phase, fail loudly: the resolved
# phase_model is persisted into state.config and silently invalidates the
# user's requested profile for the whole sprint.
#
# Only `all-codex` is in this list (not `all-claude`) because:
#   - `all-claude` matches the harness-wide default vendor; when no
#     `--vendor` is set it resolves to claude anyway, so the name is
#     accurate even without locking. Locking it would also break the
#     documented `--vendor codex --profile all-claude` flip.
#   - `all-codex` is opinionated; without locking, the silent default-vendor
#     fallback turned `--profile all-codex` into all-claude.
_NAMED_VENDOR_PROFILES = {"all-codex": "codex"}


def _validate_named_profile_invariants(
    profile_name: str, resolved: dict[str, str]
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
    if bad:
        raise CliError(
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
        # warrants apex may also warrant deep thinking).
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

        _validate_named_profile_invariants(profile_name, resolved)

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
    "resolve_pipeline_profile",
    "_load_pipeline_local_profiles",
    "_load_pipeline_local_metadata",
    "_resolve_with_inheritance",
]
