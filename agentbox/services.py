"""Read-only service control helpers for AgentBox systemd units."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


SERVICE_UNITS = {
    "arnold-guardian": "arnold-guardian.service",
    "agentbox-discord-resident": "agentbox-discord-resident.service",
}


def services_available() -> bool:
    """Return whether ``systemctl``/``systemd`` appears present."""

    return shutil.which("systemctl") is not None


def list_services() -> list[dict[str, Any]]:
    """List known AgentBox services and their systemd status."""

    if not services_available():
        return [
            {
                "name": name,
                "unit": unit,
                "status": "unknown",
                "loaded": None,
                "active": None,
                "detail": "systemctl is not available",
            }
            for name, unit in SERVICE_UNITS.items()
        ]

    results: list[dict[str, Any]] = []
    for name, unit in SERVICE_UNITS.items():
        results.append({
            "name": name,
            "unit": unit,
            "unit_file_path": _unit_file_path(unit),
            "loaded": _systemctl_bool(unit, "is-enabled"),
            "active": _systemctl_bool(unit, "is-active"),
            "status": "ok",
        })
    return results


def service_logs(service_name: str, lines: int = 50) -> dict[str, Any]:
    """Return recent logs for a named service."""

    unit = _resolve_unit(service_name)
    if unit is None:
        return {"ok": False, "error": f"unknown service: {service_name}"}

    if not services_available():
        return {
            "ok": False,
            "error": "systemctl is not available",
            "fix_command": "install systemd",
        }

    result = subprocess.run(
        ["systemctl", "status", "-n", str(lines), unit],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "service": service_name,
        "unit": unit,
        "output": result.stdout,
        "error_output": result.stderr,
    }


def restart_service(service_name: str) -> dict[str, Any]:
    """Restart a named service using systemctl."""

    unit = _resolve_unit(service_name)
    if unit is None:
        return {"ok": False, "error": f"unknown service: {service_name}"}

    if not services_available():
        return {
            "ok": False,
            "error": "systemctl is not available",
            "fix_command": "install systemd",
        }

    result = subprocess.run(
        ["systemctl", "restart", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "service": service_name,
        "unit": unit,
        "output": result.stdout,
        "error_output": result.stderr,
    }


def _resolve_unit(service_name: str) -> str | None:
    return SERVICE_UNITS.get(service_name)


def _systemctl_bool(unit: str, command: str) -> bool | None:
    result = subprocess.run(
        ["systemctl", command, unit],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if "inactive" in result.stderr.lower() or "failed" in result.stderr.lower():
        return False
    return False


def _unit_file_path(unit: str) -> str | None:
    result = subprocess.run(
        ["systemctl", "show", "-p", "FragmentPath", "--value", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    path = result.stdout.strip()
    if path and Path(path).exists():
        return path
    return None


__all__ = [
    "SERVICE_UNITS",
    "list_services",
    "restart_service",
    "service_logs",
    "services_available",
]
