"""Neutral profile loading and validation helpers for Arnold pipelines.

This neutral module is isolated from Megaplan policy imports.  The profile
package re-exports its generic contract without duplicating the implementation.

This module owns only generic mechanics:

* parse TOML profile documents
* split declared metadata keys from stage-slot keys
* validate agent-spec shape against an injected allowlist
* validate declared stage keys, including dotted ``stage.suffix`` forms
* merge built-in, user, and project layers in caller-defined order

It intentionally knows nothing about Megaplan defaults, phase names,
robustness, vendor policy, or credential preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
import tomllib

_DEFAULT_PREMIUM_AGENTS = frozenset({"claude", "codex"})
_DEFAULT_EFFORT_TOKENS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})


@dataclass(frozen=True)
class ProfileLoadError(ValueError):
    """Structured profile-loading failure."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class AgentSpecShape:
    """Parsed neutral agent-spec shape."""

    agent: str
    model: str | None = None
    effort: str | None = None


def _raise_invalid_profile(path: Any, profile_name: str, key: str, message: str) -> None:
    raise ProfileLoadError(
        "invalid_profile",
        f"Invalid profile '{profile_name}' in {path}: {message} (key: {key})",
    )


def parse_agent_spec_shape(
    spec: str,
    *,
    known_agents: frozenset[str] | None = None,
    premium_agents: frozenset[str] = _DEFAULT_PREMIUM_AGENTS,
    effort_tokens: frozenset[str] = _DEFAULT_EFFORT_TOKENS,
) -> AgentSpecShape:
    """Parse and validate a generic ``agent[:model][:effort]`` spec."""
    if not isinstance(spec, str) or not spec.strip():
        raise ProfileLoadError(
            "invalid_agent_spec",
            f"Agent spec must be a non-empty string, got {type(spec).__name__}",
        )

    candidate = spec.strip()
    parts = candidate.split(":")
    if any(part == "" for part in parts):
        raise ProfileLoadError(
            "invalid_agent_spec",
            f"Agent spec contains an empty segment: {spec!r}",
        )

    agent = parts[0]
    if known_agents is not None and agent not in known_agents:
        raise ProfileLoadError(
            "invalid_agent_spec",
            f"Unknown agent '{agent}' in spec {spec!r}. Valid agents: {', '.join(sorted(known_agents))}",
        )

    if len(parts) == 1:
        return AgentSpecShape(agent=agent)

    if agent not in premium_agents:
        return AgentSpecShape(agent=agent, model=":".join(parts[1:]))

    if len(parts) == 2 and parts[1] in effort_tokens:
        return AgentSpecShape(agent=agent, effort=parts[1])

    if len(parts) == 2:
        return AgentSpecShape(agent=agent, model=parts[1])

    if len(parts) == 3 and parts[2] in effort_tokens:
        return AgentSpecShape(agent=agent, model=parts[1], effort=parts[2])

    raise ProfileLoadError(
        "invalid_agent_spec",
        f"Unsupported premium agent spec shape: {spec!r}",
    )


def _split_profile_dict(
    path: Any,
    profile_name: str,
    raw_profile: Any,
    *,
    metadata_keys: frozenset[str] = frozenset(),
    passthrough_keys: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(raw_profile, dict):
        raise ProfileLoadError(
            "invalid_profile",
            f"Invalid profile '{profile_name}' in {path}: expected a TOML table of declared stage keys",
        )
    flattened: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    _flatten_stage_entries(raw_profile, "", flattened, metadata, metadata_keys, passthrough_keys)
    return flattened, metadata


def _flatten_stage_entries(
    raw_profile: dict[str, Any],
    prefix: str,
    flattened: dict[str, Any],
    metadata: dict[str, Any],
    metadata_keys: frozenset[str],
    passthrough_keys: frozenset[str] = frozenset(),
) -> None:
    for key, value in raw_profile.items():
        text_key = str(key)
        if not prefix and text_key in metadata_keys:
            metadata[text_key] = value
            continue
        full_key = f"{prefix}.{text_key}" if prefix else text_key
        if isinstance(value, dict):
            # Short-circuit: if this key is registered for dict-value passthrough,
            # place the entire dict as-is instead of recursing.
            if full_key in passthrough_keys:
                flattened[full_key] = value
            else:
                _flatten_stage_entries(value, full_key, flattened, metadata, metadata_keys, passthrough_keys)
        else:
            flattened[full_key] = value


def _declared_stage_for_key(key: str, declared_stage_keys: frozenset[str]) -> str | None:
    if key in declared_stage_keys:
        return key
    prefix = key.split(".", 1)[0]
    if "." in key and prefix in declared_stage_keys:
        return prefix
    return None


def validate_declared_stage_keys(
    path: Any,
    profile_name: str,
    stage_map: dict[str, Any],
    *,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> dict[str, str]:
    """Validate stage keys and generic agent-spec shapes.

    When *stage_value_validators* is provided, keys whose declared stage
    matches a registered validator may carry a ``dict`` value (instead of a
    string agent spec).  The validator callable receives the raw dict and
    must return a validated string representation.  Keys without a
    registered validator must still carry a string agent spec.
    """
    validators = stage_value_validators or {}
    validated: dict[str, str] = {}
    for key, raw_spec in stage_map.items():
        declared_stage = _declared_stage_for_key(key, declared_stage_keys)
        if declared_stage is None:
            _raise_invalid_profile(
                path,
                profile_name,
                key,
                "unknown declared stage prefix "
                f"'{key.split('.', 1)[0]}'. Valid stages: {', '.join(sorted(declared_stage_keys))}",
            )
        validator = validators.get(declared_stage) if validators else None
        if validator is not None and isinstance(raw_spec, dict):
            # Dict-value passthrough: hand the raw dict to the registered validator.
            try:
                validated[str(key)] = validator(raw_spec)
            except Exception as exc:
                _raise_invalid_profile(
                    path,
                    profile_name,
                    key,
                    f"stage value validator rejected dict value for '{key}': {exc}",
                )
            continue
        if not isinstance(raw_spec, str):
            _raise_invalid_profile(
                path,
                profile_name,
                key,
                f"expected a string agent spec, got {type(raw_spec).__name__}",
            )
        try:
            parse_agent_spec_shape(raw_spec, known_agents=known_agents)
        except ProfileLoadError as exc:
            _raise_invalid_profile(path, profile_name, key, str(exc))
        validated[str(key)] = raw_spec
    return validated


def parse_profiles_doc(
    path: Any,
    content: str,
    *,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    metadata_keys: frozenset[str] = frozenset(),
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    """Return ``(profile_maps, profile_metadata)`` for one TOML document."""
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileLoadError("invalid_profile", f"Malformed TOML in {path}: {exc}") from exc
    if not data:
        return {}, {}
    if not isinstance(data, dict):
        raise ProfileLoadError(
            "invalid_profile",
            f"Invalid profile file {path}: expected a TOML object at the top level",
        )

    raw_profiles = data.get("profiles", {})
    if raw_profiles in ({}, None):
        return {}, {}
    if not isinstance(raw_profiles, dict):
        raise ProfileLoadError(
            "invalid_profile",
            f"Invalid profile file {path}: [profiles] must be a TOML table",
        )

    passthrough_keys: frozenset[str] = frozenset(stage_value_validators) if stage_value_validators else frozenset()

    profiles: dict[str, dict[str, str]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for profile_name, raw_profile in raw_profiles.items():
        stage_map, raw_metadata = _split_profile_dict(
            path,
            str(profile_name),
            raw_profile,
            metadata_keys=metadata_keys,
            passthrough_keys=passthrough_keys,
        )
        profiles[str(profile_name)] = validate_declared_stage_keys(
            path,
            str(profile_name),
            stage_map,
            declared_stage_keys=declared_stage_keys,
            known_agents=known_agents,
            stage_value_validators=stage_value_validators,
        )
        if raw_metadata:
            metadata[str(profile_name)] = dict(raw_metadata)
    return profiles, metadata


def _load_profiles_file(
    path: Path,
    *,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    metadata_keys: frozenset[str] = frozenset(),
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, {}
    except OSError as exc:
        raise ProfileLoadError("invalid_profile", f"Unable to read profile file {path}: {exc}") from exc
    return parse_profiles_doc(
        path,
        content,
        declared_stage_keys=declared_stage_keys,
        known_agents=known_agents,
        metadata_keys=metadata_keys,
        stage_value_validators=stage_value_validators,
    )


def _iter_existing_paths(paths: Iterable[Path | None]) -> list[Path]:
    return [Path(path) for path in paths if path is not None]


def load_profile_sources(
    *,
    built_in_paths: Iterable[Path] = (),
    user_path: Path | None = None,
    project_path: Path | None = None,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    metadata_keys: frozenset[str] = frozenset(),
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> list[tuple[str, str, dict[str, str]]]:
    """Load profile sources in built-in, user, then project order."""
    sources: list[tuple[str, str, dict[str, str]]] = []
    ordered = (
        ("built-in", _iter_existing_paths(built_in_paths)),
        ("user", _iter_existing_paths((user_path,))),
        ("project", _iter_existing_paths((project_path,))),
    )
    for source_label, paths in ordered:
        for path in paths:
            profile_maps, _metadata = _load_profiles_file(
                path,
                declared_stage_keys=declared_stage_keys,
                known_agents=known_agents,
                metadata_keys=metadata_keys,
                stage_value_validators=stage_value_validators,
            )
            for profile_name, stage_map in profile_maps.items():
                sources.append((source_label, profile_name, dict(stage_map)))
    return sources


def merge_profile_layers(
    layers: Iterable[tuple[str, str, dict[str, str]]],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for _source_label, profile_name, stage_map in layers:
        merged[profile_name] = dict(stage_map)
    return merged


def load_profiles(
    *,
    built_in_paths: Iterable[Path] = (),
    user_path: Path | None = None,
    project_path: Path | None = None,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    metadata_keys: frozenset[str] = frozenset(),
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> dict[str, dict[str, str]]:
    return merge_profile_layers(
        load_profile_sources(
            built_in_paths=built_in_paths,
            user_path=user_path,
            project_path=project_path,
            declared_stage_keys=declared_stage_keys,
            known_agents=known_agents,
            metadata_keys=metadata_keys,
            stage_value_validators=stage_value_validators,
        )
    )


def load_profile_metadata(
    *,
    built_in_paths: Iterable[Path] = (),
    user_path: Path | None = None,
    project_path: Path | None = None,
    declared_stage_keys: frozenset[str],
    known_agents: frozenset[str] | None = None,
    metadata_keys: frozenset[str] = frozenset(),
    stage_value_validators: dict[str, Callable[[Any], str]] | None = None,
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    ordered_paths = (
        _iter_existing_paths(built_in_paths),
        _iter_existing_paths((user_path,)),
        _iter_existing_paths((project_path,)),
    )
    for paths in ordered_paths:
        for path in paths:
            _profiles, file_metadata = _load_profiles_file(
                path,
                declared_stage_keys=declared_stage_keys,
                known_agents=known_agents,
                metadata_keys=metadata_keys,
                stage_value_validators=stage_value_validators,
            )
            for profile_name, profile_metadata in file_metadata.items():
                metadata[profile_name] = dict(profile_metadata)
    return metadata


def resolve_default_profile(
    profiles: dict[str, dict[str, str]],
    *,
    metadata: dict[str, dict[str, Any]] | None = None,
    default_name: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Resolve the default profile from a set of loaded profiles.

    Resolution order:

    1. If *default_name* is given and exists in *profiles*, use it.
    2. Otherwise, look through *metadata* for a profile whose ``"default"``
       metadata key is a string referencing another existing profile.
    3. Otherwise, look through *metadata* for a profile whose ``"default"``
       metadata key is ``True`` (bool), then select that profile.
    4. Otherwise, return the first profile in insertion order.

    Returns a ``(profile_name, stage_map)`` tuple.

    Raises :exc:`ProfileLoadError` if *profiles* is empty or the
    explicitly requested *default_name* is not found.
    """
    if not profiles:
        raise ProfileLoadError(
            "no_profiles",
            "Cannot resolve a default profile: no profiles available.",
        )

    # 1. Explicit name.
    if default_name is not None:
        if default_name in profiles:
            return default_name, dict(profiles[default_name])
        raise ProfileLoadError(
            "unknown_profile",
            f"Cannot resolve default profile '{default_name}': "
            f"not found among available profiles: {', '.join(sorted(profiles))}.",
        )

    # 2. Metadata default field (string reference to another profile).
    if metadata:
        for pname, pmeta in metadata.items():
            default_ref = pmeta.get("default")
            if isinstance(default_ref, str) and default_ref in profiles:
                return default_ref, dict(profiles[default_ref])

    # 3. Metadata default field (bool True — self-referencing).
    if metadata:
        for pname, pmeta in metadata.items():
            default_ref = pmeta.get("default")
            if default_ref is True and pname in profiles:
                return pname, dict(profiles[pname])

    # 4. First profile (insertion order, Python ≥ 3.7).
    first_name = next(iter(profiles))
    return first_name, dict(profiles[first_name])


__all__ = [
    "AgentSpecShape",
    "ProfileLoadError",
    "load_profile_metadata",
    "load_profile_sources",
    "load_profiles",
    "merge_profile_layers",
    "parse_agent_spec_shape",
    "parse_profiles_doc",
    "resolve_default_profile",
    "validate_declared_stage_keys",
]
