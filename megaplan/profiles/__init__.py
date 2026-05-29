from __future__ import annotations

import argparse
import logging
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

log = logging.getLogger("megaplan")

# One-shot guard so the stale-override warning fires at most once per phase
# per process (apply_profile_expansion runs many times per plan).
_WARNED_STALE_OVERRIDE: set[tuple[str, str]] = set()

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

# System-level fallback when no user, project, or pipeline YAML
# ``default_profile`` / metadata ``default`` field is set.  The
# constant is the single source of truth — shipped system TOMLs no
# longer carry a ``default = \"partnered\"`` key.
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
_PREMIUM_VENDORS = frozenset({"claude", "codex"})

# Author-side phases that ``--depth`` rewrites. Critic phases (critique,
# gate, review) and mechanical phases (prep, finalize, execute,
# loop_execute) are intentionally excluded — see the asymmetry principle
# in docs/megaplan-setup.md.
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
        elif key == "tier_models":
            tier_data = _extract_tier_models(value, path=path, profile_name=profile_name)
            validated_tiers = _validate_tier_models(path, profile_name, tier_data)
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
            from megaplan.types import CRITIC_MODEL_CHOICES

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


def _validate_prep_models(path: Any, profile_name: str, value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        _raise_invalid_profile(
            path,
            profile_name,
            "prep_models",
            f"expected a TOML table for prep_models, got {type(value).__name__}",
        )
    validated: dict[str, str] = {}
    for stage, raw_spec in value.items():
        validated[str(stage)] = validate_prep_stage_provider(
            raw_spec,
            stage=stage,
            path=path,
            profile_name=profile_name,
        )
    return validated


def validate_prep_stage_provider(
    raw_spec: Any,
    *,
    stage: str,
    path: Any | None = None,
    profile_name: str | None = None,
) -> str:
    key = f"prep_models.{stage}"
    has_profile_context = path is not None and profile_name is not None

    def _fail(message: str) -> None:
        if has_profile_context:
            _raise_invalid_profile(path, str(profile_name), key, message)
        raise CliError("invalid_profile", f"Invalid prep model {key}: {message}")

    if stage not in PREP_MODEL_STAGES:
        _fail(f"unknown prep stage '{stage}'. Valid stages: {', '.join(PREP_MODEL_STAGES)}")
    if not isinstance(raw_spec, str) or not raw_spec.strip():
        _fail(f"expected a non-empty string agent spec, got {type(raw_spec).__name__}")
    spec = raw_spec.strip()
    parsed = parse_agent_spec(spec)
    if parsed.agent not in KNOWN_AGENTS:
        _fail(
            f"unknown agent '{parsed.agent}' in spec {spec!r}. Valid agents: {', '.join(KNOWN_AGENTS)}"
        )
    if parsed.agent not in READ_ONLY_PREP_AGENTS:
        _fail(
            "prep stages currently support only read-only providers: "
            f"{', '.join(sorted(READ_ONLY_PREP_AGENTS))}"
        )
    return spec


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
        parsed = parse_agent_spec(raw_spec)
        if parsed.agent not in KNOWN_AGENTS:
            _raise_invalid_profile(
                path,
                profile_name,
                phase,
                f"unknown agent '{parsed.agent}' in spec {raw_spec!r}. Valid agents: {', '.join(KNOWN_AGENTS)}",
            )
        validated[str(phase)] = raw_spec
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
    tier_models: dict[str, dict[int, str]],
) -> dict[str, dict[int, str]]:
    """Validate tier model entries: phase names must be known, tier keys
    must be 1..5, and values must use valid ``agent:model`` specs."""
    validated: dict[str, dict[int, str]] = {}
    for phase, tiers in tier_models.items():
        if phase not in VALID_PHASE_KEYS:
            _raise_invalid_profile(
                path,
                profile_name,
                f"tier_models.{phase}",
                f"unknown phase '{phase}' in tier_models. Valid phases: {', '.join(sorted(VALID_PHASE_KEYS))}",
            )
        v_tiers: dict[int, str] = {}
        for tier_int, spec in tiers.items():
            if not isinstance(tier_int, int) or tier_int < 1 or tier_int > 5:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase}.{tier_int}",
                    f"tier key must be an integer 1..5, got {tier_int!r}",
                )
            if not isinstance(spec, str):
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase}.{tier_int}",
                    f"expected a string agent spec, got {type(spec).__name__}",
                )
            agent, _model = parse_agent_spec(spec)
            if agent not in KNOWN_AGENTS:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    f"tier_models.{phase}.{tier_int}",
                    f"unknown agent '{agent}' in spec {spec!r}. Valid agents: {', '.join(KNOWN_AGENTS)}",
                )
            v_tiers[tier_int] = spec
        if v_tiers:
            validated[phase] = v_tiers
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


def _resolve_tier_models_with_inheritance(
    profile_name: str,
    *,
    system_profiles: dict[str, dict[str, str]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, dict[int, str]]:
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
    parent_tiers: dict[str, dict[int, str]] = {}
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

    own_tiers: dict[str, dict[int, str]] = metadata.get("tier_models", {}) if metadata else {}
    if not isinstance(own_tiers, dict):
        own_tiers = {}

    # Parent first, child overrides
    merged: dict[str, dict[int, str]] = {
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
    system_profiles: dict[str, dict[str, str]],
    system_metadata: dict[str, dict[str, Any]],
    pipeline_local_profiles: dict[str, dict[str, str]],
    pipeline_local_metadata: dict[str, dict[str, Any]],
    _visited: set[str] | None = None,
) -> dict[str, str]:
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
    parent_models: dict[str, str] = {}
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
        if stage in PREP_MODEL_STAGES and isinstance(spec, str):
            merged[stage] = spec
    return merged


def _prep_flat_spec_from_profile(resolved: dict[str, str]) -> str | None:
    spec = resolved.get("prep")
    return spec if isinstance(spec, str) and spec else None


def resolve_prep_models(
    *,
    flat_prep_spec: str | None,
    prep_models: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Resolve stage-aware prep models and an auditable trace.

    Legacy flat ``prep`` remains visible in the trace but no longer drives the
    research fan-out defaults.  This prevents a write-capable flat ``prep``
    route from being reused for evidence-gathering stages.

    .. note::

        The flat ``phase_models['prep']`` key may still appear in resolution
        output (``resolved_stage_models`` in the trace), but real prep execution
        uses ``config.prep_models`` through :func:`resolve_prep_stage_model`,
        not the flat agent routing.  The ``flat_agent == 'codex'`` exception
        below (preserving legacy variable-codex triage/distill routing) is
        deferred for removal in a follow-up sprint once profile reliance is
        confirmed — see SD2 in the plan.
    """
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

    # ── Layer 4: Profile default field → SYSTEM_DEFAULT_PROFILE ──
    # Scan all metadata (system + user + project merge) for a profile
    # with a ``default`` metadata field.  A user/project TOML can set
    # its own ``default=`` and it will be picked up here via the merge
    # in ``load_profile_metadata``.
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

    # No metadata-based default found — fall back to the module constant
    if SYSTEM_DEFAULT_PROFILE in system_profiles:
        return _resolve_with_inheritance(
            SYSTEM_DEFAULT_PROFILE,
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
        f"and the system default profile '{SYSTEM_DEFAULT_PROFILE}' is not available. "
        f"Pipeline-local: {_known_profiles_text(pipeline_local_profiles)}. "
        f"System: {_known_profiles_text(system_profiles)}.",
    )


def profile_to_phase_models(profile: dict[str, str]) -> list[str]:
    return [f"{phase}={spec}" for phase, spec in profile.items()]


# ---------------------------------------------------------------------------
# Vendor / critic rewrite logic
# ---------------------------------------------------------------------------


# Cross-vendor capability equivalents for model-pinned Claude specs. Claude
# distinguishes Sonnet/Opus by model name; the Codex side mirrors that with its
# own model ladder so the routed tier profiles (directed/partnered/premium)
# honour --vendor codex instead of refusing on their Sonnet/Opus tier pins:
#   * tier-4 sonnet → codex:gpt-5.4
#   * tier-5 opus   → codex:gpt-5.5
# Both are MODEL pins with no effort suffix — thinking is kept an independent
# axis: effort defaults to codex's default and is set separately
# (--depth / --phase-model), never folded into the tier.
_CLAUDE_MODEL_TO_CODEX_SPEC: tuple[tuple[str, str], ...] = (
    # Haiku has no Codex budget-tier equivalent, so it collapses to the same
    # model as Sonnet (gpt-5.4) — Codex differentiates cheap work by effort,
    # not model. This keeps `all-claude` (tier-1 = claude:claude-haiku-4-5)
    # swappable under --vendor codex instead of refusing on the haiku pin.
    ("haiku", "codex:gpt-5.4"),
    ("sonnet", "codex:gpt-5.4"),
    ("opus", "codex:gpt-5.5"),
)

_CODEX_MODEL_TO_CLAUDE_SPEC: tuple[tuple[str, str], ...] = (
    ("gpt-5.4", "claude:claude-sonnet-4-6"),
    ("gpt-5.5", "claude:claude-opus-4-7"),
)


def _swap_premium_spec(spec: str, target_vendor: str) -> str:
    """Swap claude:X <-> codex:X to match ``target_vendor``.

    Non-premium specs (hermes, shannon) are returned unchanged.
    Effort-only and bare specs are swapped cleanly (claude:low → codex:low).
    A Claude model pin (sonnet/opus) maps to its Codex capability equivalent
    (codex:gpt-5.4 / codex:gpt-5.5). Any other model pin raises
    ``vendor_swap_model_conflict`` because it has no cross-vendor equivalent.
    """
    parsed = parse_agent_spec(spec)
    if parsed.agent not in _PREMIUM_VENDORS:
        return spec
    if parsed.agent == target_vendor:
        return spec
    # Bare agent (no model, no effort) → just swap vendor
    if parsed.model is None and parsed.effort is None:
        return target_vendor
    # Effort-only → swap vendor, keep effort
    if parsed.model is None and parsed.effort is not None:
        return f"{target_vendor}:{parsed.effort}"
    # Model pinned, no explicit effort → map by capability tier where a
    # cross-vendor equivalent exists (claude sonnet/opus → codex effort). This
    # is the routing-table form (e.g. "claude:claude-sonnet-4-6"). A pin that
    # ALSO carries an effort (e.g. "claude:sonnet-4.6:high") is ambiguous —
    # the capability map and the explicit effort can't both win — so it falls
    # through to the conflict below.
    model_l = parsed.model.lower()
    if parsed.agent == "claude" and target_vendor == "codex" and parsed.effort is None:
        for needle, codex_spec in _CLAUDE_MODEL_TO_CODEX_SPEC:
            if needle in model_l:
                return codex_spec
    if parsed.agent == "codex" and target_vendor == "claude" and parsed.effort is None:
        for needle, claude_spec in _CODEX_MODEL_TO_CLAUDE_SPEC:
            if needle in model_l:
                return claude_spec
    raise CliError(
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
    """Return a copy of ``profile`` with premium slots swapped to ``vendor``.

    Profiles with no claude/codex slots are a silent no-op. Caller is
    responsible for rejecting vendor-locked profiles before getting here.

    When *tier_models* or *prep_models* are provided, those entries are also
    rewritten in-place (mutated) using the same ``_swap_premium_spec`` logic.
    Raises ``vendor_swap_model_conflict`` when an explicit model pin
    would be overwritten, naming the offending phase and spec.
    """
    if vendor not in VALID_VENDORS:
        raise CliError(
            "invalid_vendor",
            f"--vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
        )
    # Walk tier entries (mutates in-place so caller sees the rewrite).
    if tier_models is not None:
        for phase, tiers in tier_models.items():
            for tier_int, spec in tiers.items():
                try:
                    tiers[tier_int] = _swap_premium_spec(spec, vendor)
                except CliError as e:
                    if e.code == "vendor_swap_model_conflict":
                        raise CliError(
                            "vendor_swap_model_conflict",
                            f"Vendor swap conflict on phase '{phase}' tier {tier_int}: {e.message}",
                        ) from e
                    raise
    if prep_models is not None:
        for stage, spec in prep_models.items():
            try:
                prep_models[stage] = _swap_premium_spec(spec, vendor)
            except CliError as e:
                if e.code == "vendor_swap_model_conflict":
                    raise CliError(
                        "vendor_swap_model_conflict",
                        f"Vendor swap conflict on prep stage '{stage}': {e.message}",
                    ) from e
                raise
    # feedback is preserved from the profile (skipped during vendor swap for
    # cross-run comparability) and defaults to "claude:low" when absent
    result: dict[str, str] = {}
    for phase, spec in profile.items():
        if phase == "feedback":
            continue
        try:
            result[phase] = _swap_premium_spec(spec, vendor)
        except CliError as e:
            if e.code == "vendor_swap_model_conflict":
                raise CliError(
                    "vendor_swap_model_conflict",
                    f"Vendor swap conflict on phase '{phase}': {e.message}",
                ) from e
            raise
    result["feedback"] = profile.get("feedback", "claude:low")
    return result


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
        parsed = parse_agent_spec(profile[phase])
        # Preserve hermes/shannon specs as-is when crossing — only premium
        # slots have a meaningful "other vendor."
        if parsed.agent not in _PREMIUM_VENDORS:
            continue
        # Bare agent → swap vendor cleanly
        if parsed.model is None and parsed.effort is None:
            result[phase] = other
        # Effort-only → swap vendor, keep effort
        elif parsed.model is None and parsed.effort is not None:
            result[phase] = f"{other}:{parsed.effort}"
        else:
            # Model pinned → cannot cross-swap
            raise CliError(
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
    """Return a copy of ``profile`` with author-phase effort set to ``depth``.

    Only rewrites slots whose agent is claude/codex *and* whose phase is in
    :data:`DEPTH_AUTHOR_PHASES`. Critic phases plateau at their existing
    depth (asymmetry principle); hermes/shannon specs are never touched.

    When *tier_models* is provided, tier entries for author phases are also
    rewritten in-place (mutated). Tiers for non-author phases are skipped.

    Explicit model pins are preserved — only the effort suffix is rewritten.
    ``codex:gpt-5.3-codex:low`` with ``--depth high`` becomes
    ``codex:gpt-5.3-codex:high``, not ``codex:high``.

    Bare ``claude`` (no effort suffix) becomes ``claude:<depth>``.
    Effort-only specs like ``claude:low`` become ``claude:<depth>``.
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
    """Return a copy of ``profile`` with canonical DeepSeek v4-pro provider swapped.

    This is a provider dial, not a profile-tier dial: it only rewrites the
    canonical DeepSeek V4 Pro specs between Fireworks-direct and DeepSeek's
    direct API. Kimi, non-DeepSeek Fireworks models, and DeepSeek Flash stay
    exactly as declared by the profile.

    When *tier_models* is provided, tier entries are also rewritten in-place
    (mutated) using the same ``_swap_deepseek_provider_spec`` logic.
    """
    if provider not in VALID_DEEPSEEK_PROVIDER_CHOICES:
        raise CliError(
            "invalid_deepseek_provider",
            f"--deepseek-provider must be one of {', '.join(VALID_DEEPSEEK_PROVIDER_CHOICES)}; "
            f"got {provider!r}",
        )
    if tier_models is not None:
        for phase, tiers in tier_models.items():
            for tier_int, spec in tiers.items():
                tiers[tier_int] = _swap_deepseek_provider_spec(spec, provider)
    return {
        phase: _swap_deepseek_provider_spec(spec, provider)
        for phase, spec in profile.items()
    }


def _profile_has_premium_slots(profile: dict[str, str]) -> bool:
    for spec in profile.values():
        parsed = parse_agent_spec(spec)
        if parsed.agent in _PREMIUM_VENDORS:
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
_NAMED_VENDOR_PROFILES = {"all-codex": "codex", "variable-codex": "codex"}


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
    # Also validate tier entries: a named-vendor profile must not have
    # tier entries from the *wrong premium vendor* (claude vs codex) on any
    # non-feedback phase.  DeepSeek / hermes entries are always allowed
    # because they represent the cheap-fallback tiers, not a vendor choice.
    _PREMIUM_AGENTS = frozenset({"claude", "codex"})
    if tier_models:
        for phase, tiers in tier_models.items():
            if phase == "feedback":
                continue
            for tier_int, spec in tiers.items():
                agent, _model = parse_agent_spec(spec)
                if agent in _PREMIUM_AGENTS and agent != expected:
                    bad.append(f"tier_models.{phase}.{tier_int}={spec}")
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

        # Resolve tier_models from metadata (with inheritance).
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
            if _profile_has_premium_slots(resolved) or inherited_prep_models:
                resolved = apply_vendor_rewrite(
                    resolved,
                    vendor,
                    tier_models=tier_models,
                    prep_models=inherited_prep_models,
                )
            # Depth rewrite runs against the *post-vendor* state so
            # ``--vendor codex --depth high`` lands on ``codex:high`` for
            # author phases. Honored on locked profiles too (see below).
            if effective_depth_flag is not None:
                resolved = apply_depth_rewrite(resolved, effective_depth_flag, tier_models=tier_models)
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
            resolved = apply_depth_rewrite(resolved, effective_depth_flag, tier_models=tier_models)

        resolved = apply_deepseek_provider_rewrite(resolved, effective_deepseek_provider_flag, tier_models=tier_models)

        _validate_named_profile_invariants(profile_name, resolved, tier_models=tier_models)

        prep_models, prep_trace = resolve_prep_models(
            flat_prep_spec=_prep_flat_spec_from_profile(resolved),
            prep_models=inherited_prep_models,
        )

        # Attach post-rewrite tier map to args for downstream dispatch.
        # If CLI explicitly overrides the execute phase, strip
        # tier_models.execute so tier routing is disabled (CLI wins).
        if tier_models and "execute" in cli_steps:
            tier_models.pop("execute", None)
        args.tier_models = tier_models
        args.prep_models = prep_models
        args.prep_model_resolver_trace = prep_trace

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
    elif state is not None:
        config = state.get("config") or {}
        state_prep_models = config.get("prep_models")
        if isinstance(state_prep_models, dict):
            args.prep_models = dict(state_prep_models)
        state_prep_trace = config.get("prep_model_resolver_trace")
        if isinstance(state_prep_trace, dict):
            args.prep_model_resolver_trace = dict(state_prep_trace)

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
        # Map of the profile defaults currently in force, so we can detect a
        # persisted pin that shadows a profile default that has since drifted.
        profile_default_specs: dict[str, str] = {}
        for entry in phase_models[profile_block_start:]:
            if isinstance(entry, str) and "=" in entry:
                _ps, _pv = entry.split("=", 1)
                profile_default_specs.setdefault(_ps, _pv)
        for pm in persisted:
            if "=" not in pm:
                continue
            step = pm.split("=", 1)[0]
            persisted_spec = pm.split("=", 1)[1]
            if step in cli_steps:
                # Live CLI already covers this phase on the current invocation.
                continue
            if step in profile_steps:
                # Persisted CLI override must beat the profile default — but if
                # the profile default has since drifted away from the persisted
                # pin, the operator is silently running a stale override. Warn
                # once so the shadowing is visible (specfix #4).
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
    "CANONICAL_PREP_MODELS",
    "PREP_MODEL_STAGES",
    "SYSTEM_DEFAULT_PROFILE",
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
    "resolve_prep_models",
    "resolve_profile",
    "resolve_pipeline_profile",
    "validate_prep_stage_provider",
    "_load_pipeline_local_profiles",
    "_load_pipeline_local_metadata",
    "_resolve_with_inheritance",
]
