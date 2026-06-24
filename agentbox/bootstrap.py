"""Idempotent bootstrap for a persistent AgentBox machine."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from agentbox.config import AgentBoxConfig


SYSTEMD_UNIT_NAMES = ("arnold-guardian", "agentbox-discord-resident")


def bootstrap(
    config: AgentBoxConfig,
    *,
    user: str | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Ensure the AgentBox workspace layout and systemd unit templates exist.

    This is intentionally idempotent: running it repeatedly must never delete
    existing repos, worktrees, runs, locks, or credentials.
    """

    created: list[str] = []
    updated: list[str] = []

    dirs = _layout_directories(config)
    for directory in dirs:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(str(directory))

    ssh_config_path = _ensure_ssh_config(config, user=user)
    if ssh_config_path.get("created"):
        created.append(ssh_config_path["path"])
    elif ssh_config_path.get("updated"):
        updated.append(ssh_config_path["path"])

    systemd_dir = config.workspace_root / "systemd"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    for unit_name in SYSTEMD_UNIT_NAMES:
        unit_path = systemd_dir / f"{unit_name}.service"
        template = _load_unit_template(unit_name, project_root=project_root)
        rendered = _render_unit_template(template, config)
        if not unit_path.exists():
            unit_path.write_text(rendered, encoding="utf-8")
            created.append(str(unit_path))
        else:
            existing = unit_path.read_text(encoding="utf-8")
            if existing != rendered:
                unit_path.write_text(rendered, encoding="utf-8")
                updated.append(str(unit_path))

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "layout_directories": [str(directory) for directory in dirs],
        "systemd_dir": str(systemd_dir),
    }


def bootstrap_status(config: AgentBoxConfig) -> dict[str, Any]:
    """Report which layout paths exist and which systemd units are installed."""

    dirs = _layout_directories(config)
    systemd_dir = config.workspace_root / "systemd"
    units: dict[str, dict[str, Any]] = {}
    for unit_name in SYSTEMD_UNIT_NAMES:
        unit_path = systemd_dir / f"{unit_name}.service"
        units[unit_name] = {
            "path": str(unit_path),
            "exists": unit_path.exists(),
        }
    ssh_path = config.workspace_root / "ssh" / "config"
    return {
        "workspace_root": str(config.workspace_root),
        "layout_directories": {
            str(directory): {"exists": directory.exists(), "writable": _is_writable(directory)}
            for directory in dirs
        },
        "systemd_dir": str(systemd_dir),
        "systemd_units": units,
        "ssh_config_path": str(ssh_path),
        "ssh_config_exists": ssh_path.exists(),
    }


def _layout_directories(config: AgentBoxConfig) -> tuple[Path, ...]:
    return (
        config.workspace_root,
        config.repos_root,
        config.runs_root,
        config.locks_root,
        config.ops_store_root,
        config.credentials_root,
    )


def _is_writable(path: Path) -> bool:
    try:
        return path.exists() and os.access(path, os.W_OK)
    except OSError:
        return False


def _ensure_ssh_config(
    config: AgentBoxConfig,
    *,
    user: str | None = None,
) -> dict[str, Any]:
    ssh_dir = config.workspace_root / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    config_path = ssh_dir / "config"

    if config_path.exists():
        return {"created": False, "updated": False, "path": str(config_path)}

    hostname = "localhost"
    user_line = f"    User {user}\n" if user else ""
    config_path.write_text(
        f"Host agentbox\n"
        f"    Hostname {hostname}\n"
        f"    Port 22\n"
        f"    StrictHostKeyChecking accept-new\n"
        f"{user_line}\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    return {"created": True, "updated": False, "path": str(config_path)}


def _load_unit_template(unit_name: str, *, project_root: Path | str | None = None) -> str:
    """Load a systemd unit template from package data or the source tree."""

    relative_path = f"systemd/{unit_name}.service"

    try:
        from importlib.resources import files

        package_files = files("agentbox")
        candidate = package_files / relative_path
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    except (ImportError, ModuleNotFoundError, FileNotFoundError, OSError):
        pass

    if project_root is not None:
        candidate = Path(project_root) / "agentbox" / relative_path
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")

    source_tree = Path(__file__).resolve().parent
    candidate = source_tree / relative_path
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")

    raise FileNotFoundError(f"systemd unit template not found: {unit_name}")


def _render_unit_template(template: str, config: AgentBoxConfig) -> str:
    working_dir = str(Path(__file__).resolve().parent.parent)
    substitutions = {
        "{{WORKSPACE_ROOT}}": str(config.workspace_root),
        "{{CREDENTIALS_ROOT}}": str(config.credentials_root),
        "{{PYTHON}}": shutil.which("python") or shutil.which("python3") or "python3",
        "{{WORKING_DIRECTORY}}": working_dir,
    }
    rendered = template
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


__all__ = [
    "SYSTEMD_UNIT_NAMES",
    "bootstrap",
    "bootstrap_status",
]
