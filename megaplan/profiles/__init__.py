from __future__ import annotations

import argparse
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from .._core.io import config_dir
from ..types import CliError, DEFAULT_AGENT_ROUTING, KNOWN_AGENTS, parse_agent_spec

VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())


def _known_profiles_text(profiles: dict[str, dict[str, str]]) -> str:
    names = sorted(profiles)
    return ", ".join(names) if names else "(none)"


def _raise_invalid_profile(path: Any, profile_name: str, key: str, message: str) -> None:
    raise CliError(
        "invalid_profile",
        f"Invalid profile '{profile_name}' in {path}: {message} (key: {key})",
    )


def _validate_profile_map(path: Any, profile_name: str, raw_profile: Any) -> dict[str, str]:
    if not isinstance(raw_profile, dict):
        raise CliError(
            "invalid_profile",
            f"Invalid profile '{profile_name}' in {path}: expected a TOML table of phase keys",
        )
    validated: dict[str, str] = {}
    for phase, raw_spec in raw_profile.items():
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


def _parse_profiles_doc(path: Any, content: str) -> dict[str, dict[str, str]]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise CliError("invalid_profile", f"Malformed TOML in {path}: {exc}") from exc
    if not data:
        return {}
    if not isinstance(data, dict):
        raise CliError("invalid_profile", f"Invalid profile file {path}: expected a TOML object at the top level")
    raw_profiles = data.get("profiles", {})
    if raw_profiles in ({}, None):
        return {}
    if not isinstance(raw_profiles, dict):
        raise CliError("invalid_profile", f"Invalid profile file {path}: [profiles] must be a TOML table")
    profiles: dict[str, dict[str, str]] = {}
    for profile_name, raw_profile in raw_profiles.items():
        profiles[profile_name] = _validate_profile_map(path, profile_name, raw_profile)
    return profiles


def _load_profiles_file(path: Any) -> dict[str, dict[str, str]]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
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
        for profile_name, phase_map in _load_profiles_file(path).items():
            sources.append(("built-in", profile_name, dict(phase_map)))

    user_path = config_dir(home) / "profiles.toml"
    for profile_name, phase_map in _load_profiles_file(user_path).items():
        sources.append(("user", profile_name, dict(phase_map)))

    if project_dir is not None:
        project_path = Path(project_dir) / ".megaplan" / "profiles.toml"
        for profile_name, phase_map in _load_profiles_file(project_path).items():
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


def apply_profile_expansion(
    args: argparse.Namespace,
    project_dir: Path | None,
    state: dict | None = None,
) -> argparse.Namespace:
    if getattr(args, "_profile_applied", False):
        return args

    profile_name = getattr(args, "profile", None)
    if profile_name is None and state is not None:
        profile_name = (state.get("config") or {}).get("profile")
    phase_models = list(getattr(args, "phase_model", None) or [])

    if profile_name:
        profiles = load_profiles(project_dir=project_dir)
        resolved = resolve_profile(profile_name, profiles)
        phase_models.extend(profile_to_phase_models(resolved))
        args.profile = profile_name

    # Merge persisted --phase-model overrides from plan state. CLI flags on the
    # current step invocation take precedence; persisted values fill in gaps for
    # steps not specified on the CLI.
    if state is not None:
        persisted = list((state.get("config") or {}).get("phase_model") or [])
        cli_steps = {pm.split("=", 1)[0] for pm in phase_models if "=" in pm}
        for pm in persisted:
            if "=" in pm and pm.split("=", 1)[0] not in cli_steps:
                phase_models.append(pm)

    args.phase_model = phase_models
    args._profile_applied = True
    return args


__all__ = [
    "VALID_PHASE_KEYS",
    "apply_profile_expansion",
    "load_profile_sources",
    "load_profiles",
    "profile_to_phase_models",
    "resolve_profile",
]
