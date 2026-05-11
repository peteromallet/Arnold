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
        resolved = resolve_profile(profile_name, profiles)
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
    "VALID_PHASE_KEYS",
    "apply_profile_expansion",
    "load_profile_sources",
    "load_profiles",
    "profile_to_phase_models",
    "resolve_profile",
]
