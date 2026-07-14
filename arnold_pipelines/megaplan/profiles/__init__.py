from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from .._core.user_config import config_dir
from ..fallback_chains import normalize_fallback_spec_list
from ..types import CliError, is_premium_placeholder_agent, parse_agent_spec
from .policy import (
    CANONICAL_PREP_MODELS,
    DEFAULT_AGENT_ROUTING,
    DEFAULT_DEEPSEEK_PROVIDER,
    DEPTH_AUTHOR_PHASES,
    DIRECT_DEEPSEEK_V4_FLASH_SPEC,
    DIRECT_DEEPSEEK_V4_PRO_SPEC,
    FIREWORKS_DEEPSEEK_V4_PRO_SPEC,
    KNOWN_AGENTS,
    KIMI_SPEC,
    PREP_MODEL_STAGES,
    PROFILE_METADATA_KEYS,
    READ_ONLY_PREP_AGENTS,
    ROBUSTNESS_ACCEPTED,
    ROBUSTNESS_LEVELS,
    SYSTEM_DEFAULT_PROFILE,
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
    VALID_PHASE_KEYS,
    _canonicalize_tier_models_for_json,
    _prep_flat_spec_from_profile,
    _premium_cli_route_available,
    _resolve_default_vendor,
    _swap_premium_spec,
    _validate_named_profile_invariants,
    _validate_projected_tier_models,
    _validate_resolved_profile_invariants,
    apply_critic_rewrite,
    apply_available_model_floor,
    apply_deepseek_provider_rewrite,
    apply_depth_rewrite,
    apply_profile_expansion,
    apply_vendor_rewrite,
    effective_premium_vendor,
    normalize_robustness,
    profile_to_phase_models,
    resolve_pipeline_profile,
    resolve_prep_models,
    validate_prep_stage_provider,
)


def _known_profiles_text(profiles: dict[str, dict[str, Any]]) -> str:
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

    Metadata entries are the recognised profile-level keys from
    ``PROFILE_METADATA_KEYS`` (e.g. ``vendor_locked``, ``tier_models``).
    Everything else is placed in the phase map and validated later
    against the caller-supplied valid phase keys.

    Flattened ``tier_models.*`` keys (from pipeline-local profiles) are
    re-nested into ``metadata[\"tier_models\"]`` before return.
    """
    if not isinstance(raw_profile, dict):
        raise CliError(
            "invalid_profile",
            f"Invalid profile '{profile_name}' in {path}: expected a TOML table of phase keys",
        )
    phase_map: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    # Accumulate flattened tier_models.* keys for re-nesting
    tier_flat: dict[str, Any] = {}
    for key, value in raw_profile.items():
        if key in PROFILE_METADATA_KEYS:
            metadata[str(key)] = value
        elif isinstance(key, str) and key.startswith("tier_models."):
            # Flattened dotted key from pipeline-local profiles
            tier_flat[str(key)] = value
        else:
            phase_map[str(key)] = value
    # Re-nest flattened tier_models.* keys into metadata["tier_models"]
    if tier_flat:
        nested: dict[str, Any] = {}
        for flat_key, flat_value in tier_flat.items():
            # flat_key is "tier_models.execute.1" → ["tier_models", "execute", "1"]
            parts = flat_key.split(".")
            # parts[0] = "tier_models", parts[1] = phase, parts[2] = tier_number
            if len(parts) == 3:
                phase = parts[1]
                tier_key = parts[2]
                nested.setdefault(phase, {})[tier_key] = flat_value
            else:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    flat_key,
                    f"malformed tier_models key: expected tier_models.<phase>.<tier>, got {flat_key!r}",
                )
        if nested:
            metadata["tier_models"] = nested
    return phase_map, metadata


def _validate_metadata(
    path: Any,
    profile_name: str,
    metadata: dict[str, Any],
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    if valid_phase_keys is None:
        valid_phase_keys = VALID_PHASE_KEYS
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
        elif key == "tier_models":
            tier_data = _extract_tier_models(value, path=path, profile_name=profile_name)
            validated_tiers = _validate_tier_models(
                path, profile_name, tier_data, valid_phase_keys=valid_phase_keys,
            )
            if validated_tiers:
                validated["tier_models"] = validated_tiers
        elif key == "prep_models":
            prep_models = _validate_prep_models(path, profile_name, value)
            if prep_models:
                validated["prep_models"] = prep_models
        elif key == "max_tasks_per_batch":
            if not isinstance(value, int):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"expected an integer for 'max_tasks_per_batch', got {type(value).__name__}",
                )
            validated["max_tasks_per_batch"] = value
        elif key == "adaptive_critique":
            if not isinstance(value, bool):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"expected a boolean for 'adaptive_critique', got {type(value).__name__}",
                )
            validated["adaptive_critique"] = value
        elif key == "critic_model":
            from arnold_pipelines.megaplan.types import CRITIC_MODEL_CHOICES

            if not isinstance(value, str) or value not in CRITIC_MODEL_CHOICES:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"'critic_model' must be one of "
                    f"{[c for c in CRITIC_MODEL_CHOICES if c]}; got {value!r}",
                )
            validated["critic_model"] = value
        # Future metadata keys go here.
    return validated


def _validate_prep_models(path: Any, profile_name: str, value: Any) -> dict[str, str | list[str]]:
    if not isinstance(value, dict):
        _raise_invalid_profile(
            path,
            profile_name,
            "prep_models",
            f"expected a TOML table for prep_models, got {type(value).__name__}",
        )
    validated: dict[str, str | list[str]] = {}
    for stage, raw_spec in value.items():
        validated[str(stage)] = validate_prep_stage_provider(
            raw_spec,
            stage=stage,
            path=path,
            profile_name=profile_name,
        )
    return validated


def _validate_phase_spec_value(
    raw_spec: Any,
    *,
    path: Any,
    profile_name: str,
    phase: str,
) -> str | list[str]:
    """Validate a scalar-or-list profile phase spec against known-agent rules.

    Returns the validated value preserving input shape (scalar → str,
    list → list[str]).
    """
    # Use normalize_fallback_spec_list for basic structural validation
    # (rejects non-string, empty strings, empty arrays, non-string members).
    try:
        specs = normalize_fallback_spec_list(raw_spec, path=f"{profile_name}.{phase}")
    except ValueError as exc:
        _raise_invalid_profile(path, profile_name, phase, str(exc))
        raise  # unreachable

    # Validate each element against known-agent rules.
    for index, spec in enumerate(specs):
        parsed = parse_agent_spec(spec)
        if parsed.agent not in KNOWN_AGENTS and not is_premium_placeholder_agent(parsed.agent):
            element_path = f"{phase}[{index}]" if len(specs) > 1 else phase
            _raise_invalid_profile(
                path,
                profile_name,
                element_path,
                f"unknown agent '{parsed.agent}' in spec {spec!r}. Valid agents: "
                f"{', '.join(KNOWN_AGENTS)} (and 'premium' symbolic placeholder)",
            )

    if isinstance(raw_spec, str):
        return specs[0]
    return list(specs)


def _validate_tier_spec_value(
    raw_spec: Any,
    *,
    path: Any,
    profile_name: str,
    phase: str,
    tier_key: object,
) -> str | list[str]:
    """Validate a scalar-or-list tier model spec against known-agent rules."""
    tier_label = f"tier_models.{phase}.{tier_key}"
    try:
        specs = normalize_fallback_spec_list(raw_spec, path=f"{profile_name}.{tier_label}")
    except ValueError as exc:
        _raise_invalid_profile(path, profile_name, tier_label, str(exc))
        raise  # unreachable

    for index, spec in enumerate(specs):
        parsed = parse_agent_spec(spec)
        if parsed.agent not in KNOWN_AGENTS and not is_premium_placeholder_agent(parsed.agent):
            element_path = f"{tier_label}[{index}]" if len(specs) > 1 else tier_label
            _raise_invalid_profile(
                path,
                profile_name,
                element_path,
                f"unknown agent '{parsed.agent}' in spec {spec!r}. Valid agents: "
                f"{', '.join(KNOWN_AGENTS)} (and 'premium' symbolic placeholder)",
            )

    if isinstance(raw_spec, str):
        return specs[0]
    return list(specs)


def _validate_profile_map(
    path: Any,
    profile_name: str,
    raw_profile: Any,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> dict[str, str | list[str]]:
    if valid_phase_keys is None:
        valid_phase_keys = VALID_PHASE_KEYS
    phase_map, _metadata = _split_profile_dict(path, profile_name, raw_profile)
    validated: dict[str, str | list[str]] = {}
    for phase, raw_spec in phase_map.items():
        if phase not in valid_phase_keys:
            _raise_invalid_profile(
                path,
                profile_name,
                str(phase),
                f"unknown phase '{phase}'. Valid phases: {', '.join(sorted(valid_phase_keys))}",
            )
        spec_validated = _validate_phase_spec_value(raw_spec, path=path, profile_name=profile_name, phase=phase)
        validated[str(phase)] = spec_validated
    return validated


def _extract_tier_models(
    raw_tier_data: Any,
    path: Any = None,
    profile_name: str = "",
) -> dict[str, dict[int, str]]:
    """Normalise raw tier-model data into ``{phase: {tier: spec}}``.

    Accepts both nested TOML tables (``{"execute": {"1": "hermes:deepseek-flash", ...}}``)
    and pre-flattened dotted-key forms from pipeline-local loaders
    (re-nested by ``_split_profile_dict`` into the same shape).
    Tier keys are converted from ``str`` to ``int``.

    When *path* and *profile_name* are supplied, invalid inputs (non-string
    phase keys, non-dict tier entries) raise ``CliError`` immediately instead
    of being silently skipped — this ensures profile-load-time rejection.
    Callers that pass already-validated data (e.g. the inheritance resolver)
    can omit *path*/*profile_name* to preserve the lenient passthrough.
    """
    if not isinstance(raw_tier_data, dict):
        if path is not None:
            _raise_invalid_profile(
                path,
                profile_name,
                "tier_models",
                f"expected a TOML table for tier_models, got {type(raw_tier_data).__name__}",
            )
        return {}
    result: dict[str, dict[int, str]] = {}
    for phase, tier_map in raw_tier_data.items():
        if not isinstance(phase, str):
            if path is not None:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase!r}",
                    f"phase key must be a string, got {type(phase).__name__}",
                )
            continue
        if not isinstance(tier_map, dict):
            if path is not None:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase}",
                    f"tier entry must be a TOML table, got {type(tier_map).__name__}",
                )
            continue
        tiers: dict[int, str] = {}
        for tier_key, spec in tier_map.items():
            # Tier keys may be ints (from TOML) or strs (from pipeline-local).
            # Convert to int where possible; pass through unconvertible keys
            # so _validate_tier_models can reject them with a clear error.
            try:
                tier_int = int(tier_key)
            except (ValueError, TypeError):
                tier_int = tier_key
            # Pass through non-string specs — _validate_tier_models rejects them.
            tiers[tier_int] = spec
        if tiers:
            result[phase] = tiers
    return result


def _validate_tier_models(
    path: Any,
    profile_name: str,
    tier_models: dict[str, dict[int, Any]],
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> dict[str, dict[int, str | list[str]]]:
    """Validate tier model entries: phase names must be known, tier keys
    must be 1..10, and values must use valid ``agent:model`` specs.
    Accepts both scalar strings and TOML arrays for each tier spec."""
    if valid_phase_keys is None:
        valid_phase_keys = VALID_PHASE_KEYS
    validated: dict[str, dict[int, str | list[str]]] = {}
    for phase, tiers in tier_models.items():
        if phase not in valid_phase_keys:
            _raise_invalid_profile(
                path,
                profile_name,
                f"tier_models.{phase}",
                f"unknown phase '{phase}' in tier_models. Valid phases: {', '.join(sorted(valid_phase_keys))}",
            )
        v_tiers: dict[int, str | list[str]] = {}
        for tier_int, spec in tiers.items():
            if not isinstance(tier_int, int) or tier_int < 1 or tier_int > 10:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase}.{tier_int}",
                    f"tier key must be an integer 1..10, got {tier_int!r}",
                )
            v_tiers[tier_int] = _validate_tier_spec_value(
                spec,
                path=path,
                profile_name=profile_name,
                phase=phase,
                tier_key=tier_int,
            )
        if v_tiers:
            validated[phase] = v_tiers
    return validated


def _parse_profiles_doc(
    path: Any,
    content: str,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> tuple[dict[str, dict[str, str | list[str]]], dict[str, dict[str, Any]]]:
    """Return (profiles_phase_maps, profiles_metadata).

    Both dicts are keyed by profile name. Metadata is empty when a
    profile declares no metadata keys.
    """
    if valid_phase_keys is None:
        valid_phase_keys = VALID_PHASE_KEYS
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
    profiles: dict[str, dict[str, str | list[str]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for profile_name, raw_profile in raw_profiles.items():
        _phase_map, raw_metadata = _split_profile_dict(path, profile_name, raw_profile)
        profiles[profile_name] = _validate_profile_map(
            path, profile_name, raw_profile, valid_phase_keys=valid_phase_keys,
        )
        validated_metadata = _validate_metadata(
            path, profile_name, raw_metadata, valid_phase_keys=valid_phase_keys,
        )
        if validated_metadata:
            metadata[profile_name] = validated_metadata
    return profiles, metadata


def _load_profiles_file(
    path: Any,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> tuple[dict[str, dict[str, str | list[str]]], dict[str, dict[str, Any]]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, {}
    except OSError as exc:
        raise CliError("invalid_profile", f"Unable to read profile file {path}: {exc}") from exc
    return _parse_profiles_doc(path, content, valid_phase_keys=valid_phase_keys)


def _built_in_profile_files() -> list[Any]:
    """Return built-in profile .toml files, tolerating broken editable installs.

    ``importlib.resources.files`` can return a non-existent path when a package
    is installed editable and the resource reader gets confused by namespace
    packages or stale metadata.  In that case we fall back to the directory
    containing this source file, which is the authoritative filesystem location
    for the loaded module.
    """
    package_name = "arnold_pipelines.megaplan.profiles"
    candidate_roots: list[Path] = []

    # Primary: importlib.resources for installed packages.
    try:
        resource_root = files(package_name)
        if resource_root is not None:
            candidate_roots.append(Path(str(resource_root)))
    except Exception:
        pass

    # Fallback: the directory of this module (works for editable installs).
    candidate_roots.append(Path(__file__).parent)

    # Additional fallback: spec search locations, if available.
    try:
        import importlib.util

        spec = importlib.util.find_spec(package_name)
        if spec is not None and spec.submodule_search_locations:
            candidate_roots.extend(
                Path(str(loc)) for loc in spec.submodule_search_locations
            )
    except Exception:
        pass

    seen: set[Path] = set()
    entries: list[Path] = []
    for root in candidate_roots:
        try:
            if not root.exists() or not root.is_dir():
                continue
        except Exception:
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            for entry in root.iterdir():
                if entry.is_file() and entry.name.endswith(".toml") and not entry.name.startswith("."):
                    entries.append(entry)
        except (OSError, FileNotFoundError):
            continue

    return sorted(entries, key=lambda entry: entry.name)


def load_profile_sources(
    home: Path | None = None,
    project_dir: Path | None = None,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> list[tuple[str, str, dict[str, str | list[str]]]]:
    sources: list[tuple[str, str, dict[str, str | list[str]]]] = []

    for path in _built_in_profile_files():
        profile_maps, _metadata = _load_profiles_file(
            path, valid_phase_keys=valid_phase_keys,
        )
        for profile_name, phase_map in profile_maps.items():
            sources.append(("built-in", profile_name, dict(phase_map)))

    user_path = config_dir(home) / "profiles.toml"
    user_profiles, _user_metadata = _load_profiles_file(
        user_path, valid_phase_keys=valid_phase_keys,
    )
    for profile_name, phase_map in user_profiles.items():
        sources.append(("user", profile_name, dict(phase_map)))

    if project_dir is not None:
        project_path = Path(project_dir) / ".megaplan" / "profiles.toml"
        project_profiles, _project_metadata = _load_profiles_file(
            project_path, valid_phase_keys=valid_phase_keys,
        )
        for profile_name, phase_map in project_profiles.items():
            sources.append(("project", profile_name, dict(phase_map)))

    return sources


def load_profiles(
    home: Path | None = None,
    project_dir: Path | None = None,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> dict[str, dict[str, str | list[str]]]:
    profiles: dict[str, dict[str, str | list[str]]] = {}
    for _source_label, profile_name, phase_map in load_profile_sources(
        home=home, project_dir=project_dir, valid_phase_keys=valid_phase_keys,
    ):
        profiles[profile_name] = dict(phase_map)
    return profiles


def load_profile_metadata(
    home: Path | None = None,
    project_dir: Path | None = None,
    *,
    valid_phase_keys: frozenset[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return per-profile metadata (the non-phase keys, e.g. ``vendor_locked``).

    Later layers override earlier ones, mirroring ``load_profiles``.
    """
    metadata: dict[str, dict[str, Any]] = {}

    for path in _built_in_profile_files():
        _profiles, file_meta = _load_profiles_file(
            path, valid_phase_keys=valid_phase_keys,
        )
        for profile_name, meta in file_meta.items():
            metadata[profile_name] = dict(meta)

    user_path = config_dir(home) / "profiles.toml"
    _user_profiles, user_meta = _load_profiles_file(
        user_path, valid_phase_keys=valid_phase_keys,
    )
    for profile_name, meta in user_meta.items():
        metadata[profile_name] = dict(meta)

    if project_dir is not None:
        project_path = Path(project_dir) / ".megaplan" / "profiles.toml"
        _project_profiles, project_meta = _load_profiles_file(
            project_path, valid_phase_keys=valid_phase_keys,
        )
        for profile_name, meta in project_meta.items():
            metadata[profile_name] = dict(meta)

    return metadata


def resolve_profile(name: str, profiles: dict[str, dict[str, str | list[str]]]) -> dict[str, str | list[str]]:
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
    if builtin:
        pipelines_root = Path(__file__).resolve().parent.parent / "pipelines"
        candidates = (
            pipelines_root / pipeline_name / "profiles",
            pipelines_root / pipeline_name.replace("-", "_") / "profiles",
        )
    else:
        pipelines_root = Path.home() / ".megaplan" / "pipelines"
        candidates = (pipelines_root / pipeline_name / "profiles",)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _load_pipeline_local_profiles(
    pipeline_name: str,
) -> dict[str, dict[str, str | list[str]]]:
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

    profiles: dict[str, dict[str, str | list[str]]] = {}

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
                    if agent not in KNOWN_AGENTS and not is_premium_placeholder_agent(agent):
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
    system_profiles: dict[str, dict[str, str | list[str]]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str | list[str]]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str | list[str]]:
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
    system_profiles: dict[str, dict[str, str | list[str]]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str | list[str]]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str | list[str]]:
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
    profile: dict[str, str | list[str]] | None = None
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


def _resolve_tier_models_with_inheritance(
    profile_name: str,
    *,
    system_profiles: dict[str, dict[str, str | list[str]]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str | list[str]]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, dict[int, str | list[str]]]:
    """Walk the ``extends`` chain and merge ``tier_models`` metadata.

    Parent tier maps are applied first; child entries override per-phase
    and per-tier.  Profiles without ``tier_models`` metadata return an
    empty dict.
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

    metadata: dict[str, Any] | None = None
    if profile_name in pipeline_local_metadata:
        metadata = pipeline_local_metadata.get(profile_name, {})
    elif profile_name in system_metadata:
        metadata = system_metadata.get(profile_name, {})

    if metadata is None:
        raise CliError(
            "unknown_profile",
            f"Unknown profile '{profile_name}'",
        )

    extends_ref = metadata.get("extends") if metadata else None
    parent_tiers: dict[str, dict[int, str | list[str]]] = {}
    if extends_ref and isinstance(extends_ref, str):
        # Resolve the extends reference to a bare profile name
        if extends_ref.startswith("system:"):
            parent_name = extends_ref[len("system:"):]
        elif extends_ref.startswith("@"):
            rest = extends_ref[1:]
            if ":" in rest:
                _pl_name, parent_name = rest.split(":", 1)
            else:
                parent_name = rest
        else:
            parent_name = None
        if parent_name:
            try:
                parent_tiers = _resolve_tier_models_with_inheritance(
                    parent_name,
                    system_profiles=system_profiles,
                    system_metadata=system_metadata,
                    pipeline_local_profiles=pipeline_local_profiles,
                    pipeline_local_metadata=pipeline_local_metadata,
                    _visited=_visited,
                )
            except CliError:
                parent_tiers = {}

    own_tiers: dict[str, dict[int, str | list[str]]] = metadata.get("tier_models", {}) if metadata else {}
    if not isinstance(own_tiers, dict):
        own_tiers = {}

    # Parent first, child overrides
    merged: dict[str, dict[int, str | list[str]]] = {
        phase: dict(tiers)
        for phase, tiers in parent_tiers.items()
    }
    for phase, tiers in own_tiers.items():
        if phase in merged:
            merged[phase].update(tiers)
        else:
            merged[phase] = dict(tiers)

    return merged


def _resolve_prep_models_with_inheritance(
    profile_name: str,
    *,
    system_profiles: dict[str, dict[str, str | list[str]]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str | list[str]]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str | list[str]]:
    """Walk ``extends`` and merge ``prep_models`` metadata.

    Parent prep stage declarations are applied first; child declarations
    override individual stages.  Missing stages are deliberately left missing
    so the canonical fallback resolver can record which slots used defaults.
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

    metadata: dict[str, Any] | None = None
    if profile_name in pipeline_local_metadata:
        metadata = pipeline_local_metadata.get(profile_name, {})
    elif profile_name in system_metadata:
        metadata = system_metadata.get(profile_name, {})

    if metadata is None:
        raise CliError("unknown_profile", f"Unknown profile '{profile_name}'")

    extends_ref = metadata.get("extends") if metadata else None
    parent_models: dict[str, str | list[str]] = {}
    if extends_ref and isinstance(extends_ref, str):
        if extends_ref.startswith("system:"):
            parent_name = extends_ref[len("system:"):]
        elif extends_ref.startswith("@"):
            rest = extends_ref[1:]
            if ":" in rest:
                _pl_name, parent_name = rest.split(":", 1)
            else:
                parent_name = rest
        else:
            parent_name = None
        if parent_name:
            try:
                parent_models = _resolve_prep_models_with_inheritance(
                    parent_name,
                    system_profiles=system_profiles,
                    system_metadata=system_metadata,
                    pipeline_local_profiles=pipeline_local_profiles,
                    pipeline_local_metadata=pipeline_local_metadata,
                    _visited=_visited,
                )
            except CliError:
                parent_models = {}

    own_models = metadata.get("prep_models", {}) if metadata else {}
    if not isinstance(own_models, dict):
        own_models = {}

    merged = dict(parent_models)
    for stage, spec in own_models.items():
        if stage in PREP_MODEL_STAGES and (isinstance(spec, str) or isinstance(spec, list)):
            merged[stage] = spec
    return merged


# ``arnold_pipelines.megaplan.profiles`` historically exposed Megaplan policy
# loading from this package.  A later neutral loader was added at the colliding
# module path ``arnold_pipelines.megaplan.profiles.py``, which Python can never
# import while this package exists.  Keep both contracts explicit: ordinary
# Megaplan calls retain their established positional API, while calls carrying
# neutral-loader keywords are delegated to the adjacent neutral module.
from . import neutral as _neutral_profiles

_load_megaplan_profile_sources = load_profile_sources
_load_megaplan_profiles = load_profiles
_load_megaplan_profile_metadata = load_profile_metadata

ProfileLoadError = _neutral_profiles.ProfileLoadError
AgentSpecShape = _neutral_profiles.AgentSpecShape
parse_agent_spec_shape = _neutral_profiles.parse_agent_spec_shape
parse_profiles_doc = _neutral_profiles.parse_profiles_doc
validate_declared_stage_keys = _neutral_profiles.validate_declared_stage_keys
merge_profile_layers = _neutral_profiles.merge_profile_layers
resolve_default_profile = _neutral_profiles.resolve_default_profile

_NEUTRAL_PROFILE_KEYS = frozenset(
    {
        "built_in_paths",
        "user_path",
        "project_path",
        "declared_stage_keys",
        "known_agents",
        "metadata_keys",
        "stage_value_validators",
    }
)


def _uses_neutral_profile_contract(kwargs: dict[str, Any]) -> bool:
    return bool(_NEUTRAL_PROFILE_KEYS.intersection(kwargs))


def load_profile_sources(*args: Any, **kwargs: Any) -> Any:
    if _uses_neutral_profile_contract(kwargs):
        if args:
            raise TypeError("neutral profile loading accepts keyword arguments only")
        return _neutral_profiles.load_profile_sources(**kwargs)
    return _load_megaplan_profile_sources(*args, **kwargs)


def load_profiles(*args: Any, **kwargs: Any) -> Any:
    if _uses_neutral_profile_contract(kwargs):
        if args:
            raise TypeError("neutral profile loading accepts keyword arguments only")
        return _neutral_profiles.load_profiles(**kwargs)
    return _load_megaplan_profiles(*args, **kwargs)


def load_profile_metadata(*args: Any, **kwargs: Any) -> Any:
    if _uses_neutral_profile_contract(kwargs):
        if args:
            raise TypeError("neutral profile loading accepts keyword arguments only")
        return _neutral_profiles.load_profile_metadata(**kwargs)
    return _load_megaplan_profile_metadata(*args, **kwargs)


__all__ = [
    "AgentSpecShape",
    "CANONICAL_PREP_MODELS",
    "DEFAULT_AGENT_ROUTING",
    "DEFAULT_DEEPSEEK_PROVIDER",
    "DEPTH_AUTHOR_PHASES",
    "DIRECT_DEEPSEEK_V4_FLASH_SPEC",
    "DIRECT_DEEPSEEK_V4_PRO_SPEC",
    "FIREWORKS_DEEPSEEK_V4_PRO_SPEC",
    "KIMI_SPEC",
    "KNOWN_AGENTS",
    "READ_ONLY_PREP_AGENTS",
    "ROBUSTNESS_ACCEPTED",
    "ROBUSTNESS_LEVELS",
    "VALID_CRITIC_CHOICES",
    "VALID_DEEPSEEK_PROVIDER_CHOICES",
    "PREP_MODEL_STAGES",
    "SYSTEM_DEFAULT_PROFILE",
    "VALID_DEPTH_CHOICES",
    "VALID_PHASE_KEYS",
    "PROFILE_METADATA_KEYS",
    "ProfileLoadError",
    "apply_critic_rewrite",
    "apply_available_model_floor",
    "apply_deepseek_provider_rewrite",
    "apply_depth_rewrite",
    "apply_profile_expansion",
    "apply_vendor_rewrite",
    "effective_premium_vendor",
    "load_profile_metadata",
    "load_profile_sources",
    "load_profiles",
    "merge_profile_layers",
    "parse_agent_spec_shape",
    "parse_profiles_doc",
    "profile_to_phase_models",
    "_prep_flat_spec_from_profile",
    "resolve_prep_models",
    "resolve_default_profile",
    "resolve_profile",
    "resolve_pipeline_profile",
    "validate_prep_stage_provider",
    "validate_declared_stage_keys",
    "_canonicalize_tier_models_for_json",
    "_load_pipeline_local_profiles",
    "_load_pipeline_local_metadata",
    "_validate_named_profile_invariants",
    "_validate_projected_tier_models",
    "_validate_resolved_profile_invariants",
    "_resolve_with_inheritance",
    "_resolve_default_vendor",
    "_swap_premium_spec",
    "_premium_cli_route_available",
    "normalize_robustness",
]
