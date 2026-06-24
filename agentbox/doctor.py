"""Read-only health checks for an AgentBox host."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from typing import Any

from agentbox.config import AgentBoxConfig
from agentbox.repos import list_repos


@dataclass
class DoctorReport:
    """Aggregated result of an AgentBox host checkup."""

    ok: bool
    checks: list[dict[str, Any]]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": self.checks,
            "summary": self.summary,
        }


def checkup(config: AgentBoxConfig) -> DoctorReport:
    """Run read-only health checks and return a report."""

    checks: list[dict[str, Any]] = []

    checks.append(_check_workspace_directories(config))
    checks.append(_check_command("git", fatal=True))
    checks.append(_check_command("gh", fatal=False))
    checks.append(_check_command("tmux", fatal=True))
    checks.append(_check_python_imports())
    checks.append(_check_credentials_root(config))
    checks.append(_check_systemd_templates(config))
    checks.append(_check_registered_repos(config))

    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]

    if failures:
        ok = False
        summary = f"{len(failures)} failure(s), {len(warnings)} warning(s). Run `agentbox bootstrap` if the workspace is missing."
    elif warnings:
        ok = True
        summary = f"Healthy with {len(warnings)} warning(s)."
    else:
        ok = True
        summary = "All checks passed."

    return DoctorReport(ok=ok, checks=checks, summary=summary)


def _check_workspace_directories(config: AgentBoxConfig) -> dict[str, Any]:
    missing: list[str] = []
    for directory in (
        config.workspace_root,
        config.repos_root,
        config.runs_root,
        config.locks_root,
        config.ops_store_root,
        config.credentials_root,
    ):
        if not directory.exists():
            missing.append(str(directory))
    if missing:
        return {
            "name": "workspace_directories",
            "status": "fail",
            "message": f"Missing directories: {', '.join(missing)}",
            "fix_command": "agentbox bootstrap",
        }
    return {
        "name": "workspace_directories",
        "status": "ok",
        "message": "Workspace directories exist.",
    }


def _check_command(name: str, *, fatal: bool) -> dict[str, Any]:
    path = shutil.which(name)
    if path:
        return {
            "name": f"{name}_installed",
            "status": "ok",
            "message": f"{name} found at {path}",
        }
    message = f"{name} is not installed or not on PATH"
    if fatal:
        return {
            "name": f"{name}_installed",
            "status": "fail",
            "message": message,
            "fix_command": f"install {name}",
        }
    return {
        "name": f"{name}_installed",
        "status": "warn",
        "message": message,
        "fix_command": f"install {name} (optional)",
    }


def _check_python_imports() -> dict[str, Any]:
    python_ok = _module_available("agentbox")
    if not python_ok:
        return {
            "name": "python_imports",
            "status": "fail",
            "message": "agentbox package is not importable",
            "fix_command": "pip install -e .",
        }
    return {
        "name": "python_imports",
        "status": "ok",
        "message": "python and agentbox are importable",
    }


def _check_credentials_root(config: AgentBoxConfig) -> dict[str, Any]:
    if config.credentials_root.exists():
        return {
            "name": "credentials_root",
            "status": "ok",
            "message": f"Credentials root exists at {config.credentials_root}",
        }
    return {
        "name": "credentials_root",
        "status": "fail",
        "message": f"Credentials root missing: {config.credentials_root}",
        "fix_command": "agentbox bootstrap",
    }


def _check_systemd_templates(config: AgentBoxConfig) -> dict[str, Any]:
    systemd_dir = config.workspace_root / "systemd"
    missing: list[str] = []
    for unit_name in ("arnold-guardian", "agentbox-discord-resident"):
        if not (systemd_dir / f"{unit_name}.service").exists():
            missing.append(unit_name)
    if missing:
        return {
            "name": "systemd_templates",
            "status": "warn",
            "message": f"Missing systemd units: {', '.join(missing)}",
            "fix_command": "agentbox bootstrap",
        }
    return {
        "name": "systemd_templates",
        "status": "ok",
        "message": f"Systemd templates present in {systemd_dir}",
    }


def _check_registered_repos(config: AgentBoxConfig) -> dict[str, Any]:
    repos = list_repos(config)
    if repos:
        return {
            "name": "registered_repos",
            "status": "ok",
            "message": f"{len(repos)} repo(s) registered",
        }
    return {
        "name": "registered_repos",
        "status": "ok",
        "message": "No repos registered yet (optional)",
    }


def _module_available(name: str) -> bool:
    spec = importlib.util.find_spec(name)
    return spec is not None


__all__ = [
    "DoctorReport",
    "checkup",
]
