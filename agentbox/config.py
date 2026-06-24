"""Configuration loading and root layout for AgentBox."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

import yaml


AGENTBOX_CONFIG_ENV = "AGENTBOX_CONFIG"
DEFAULT_CONFIG_PATH = Path("/workspace/agentbox.yaml")
DEFAULT_WORKSPACE_ROOT = Path("/workspace")
DEFAULT_CREDENTIALS_ROOT = Path("/workspace/credentials")
OPERATION_RUNS_FILENAME = "operation_runs.json"


class AgentBoxConfigError(ValueError):
    """Raised when AgentBox configuration is invalid."""


@dataclass(frozen=True)
class AgentBoxConfig:
    """Absolute filesystem roots used by the host-local AgentBox provider."""

    workspace_root: Path | str = DEFAULT_WORKSPACE_ROOT
    repos_root: Path | str | None = None
    runs_root: Path | str | None = None
    locks_root: Path | str | None = None
    ops_store_root: Path | str | None = None
    credentials_root: Path | str | None = None

    def __post_init__(self) -> None:
        workspace_root = _absolute_path("workspace_root", self.workspace_root)
        object.__setattr__(self, "workspace_root", workspace_root)
        object.__setattr__(
            self,
            "repos_root",
            _absolute_path("repos_root", self.repos_root or workspace_root / "repos"),
        )
        object.__setattr__(
            self,
            "runs_root",
            _absolute_path("runs_root", self.runs_root or workspace_root / "runs"),
        )
        object.__setattr__(
            self,
            "locks_root",
            _absolute_path("locks_root", self.locks_root or workspace_root / "locks"),
        )
        object.__setattr__(
            self,
            "ops_store_root",
            _absolute_path("ops_store_root", self.ops_store_root or workspace_root / "ops"),
        )
        object.__setattr__(
            self,
            "credentials_root",
            _absolute_path(
                "credentials_root",
                self.credentials_root or workspace_root / "credentials",
            ),
        )

    @property
    def operation_runs_path(self) -> Path:
        """JSON file used by FileBackedDurableOpsStore under ``ops_store_root``."""

        return self.ops_store_root / OPERATION_RUNS_FILENAME

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "AgentBoxConfig":
        if values is None:
            return cls()
        if not isinstance(values, Mapping):
            raise AgentBoxConfigError("AgentBox config must be a YAML mapping.")

        allowed = {
            "workspace_root",
            "repos_root",
            "runs_root",
            "locks_root",
            "ops_store_root",
            "credentials_root",
        }
        unknown = sorted(set(values) - allowed)
        if unknown:
            names = ", ".join(unknown)
            raise AgentBoxConfigError(f"Unknown AgentBox config key(s): {names}.")

        return cls(**{key: value for key, value in values.items() if value is not None})


def load_agentbox_config(
    *,
    environ: Mapping[str, str] | None = None,
    default_config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> AgentBoxConfig:
    """Load AgentBox config from ``AGENTBOX_CONFIG`` or the default YAML path."""

    env = os.environ if environ is None else environ
    configured_path = env.get(AGENTBOX_CONFIG_ENV)
    if configured_path:
        return _load_config_file(Path(configured_path), missing_ok=False)

    return _load_config_file(Path(default_config_path), missing_ok=True)


def _load_config_file(path: Path, *, missing_ok: bool) -> AgentBoxConfig:
    if not path.exists():
        if missing_ok:
            return AgentBoxConfig()
        raise AgentBoxConfigError(f"AgentBox config file does not exist: {path}")

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AgentBoxConfigError(f"Invalid AgentBox YAML config at {path}: {exc}") from exc

    return AgentBoxConfig.from_mapping(loaded or {})


def _absolute_path(name: str, value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise AgentBoxConfigError(f"{name} must be an absolute path: {path}")
    return path


__all__ = [
    "AGENTBOX_CONFIG_ENV",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_CREDENTIALS_ROOT",
    "DEFAULT_WORKSPACE_ROOT",
    "OPERATION_RUNS_FILENAME",
    "AgentBoxConfig",
    "AgentBoxConfigError",
    "load_agentbox_config",
]
