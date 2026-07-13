"""Service inspection and guarded control helpers for AgentBox runtimes."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from agentbox.reset_notifications import (
    ResetNotificationError,
    load_reset_reservation,
    mark_reset_failed,
    mark_reset_restarting,
    mark_reset_succeeded,
    mark_reset_supervisor_started,
    prepare_reset_notification,
    reset_notification_root,
    reset_transaction_request,
    wait_for_reset_acknowledgement,
)


SERVICE_UNITS = {
    "arnold-guardian": "arnold-guardian.service",
    "agentbox-discord-resident": "agentbox-discord-resident.service",
}
DISCORD_RESIDENT_SERVICE = "agentbox-discord-resident"
DISCORD_RESIDENT_RESTART_COMMAND = (
    "agentbox services restart agentbox-discord-resident"
)
DISCORD_RESIDENT_SAFE_KILL_MODE = "process"
DISCORD_RESIDENT_TMUX_SESSION = "megaplan-resident-discord"
DISCORD_RESIDENT_TMUX_COMMAND_MARKER = (
    "arnold_pipelines.megaplan resident discord"
)
_TMUX_PANE_FORMAT = (
    "#{pane_id}\t#{pane_pid}\t#{pane_dead}\t"
    "#{pane_current_command}\t#{pane_start_command}"
)


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


def restart_service(
    service_name: str,
    *,
    notification_root: str | Path | None = None,
) -> dict[str, Any]:
    """Restart a named service through its active local supervisor.

    The Discord resident is special: delegated agents and tmux-backed chains
    must survive its restart. On a systemd host, restarting is allowed only when
    the *installed* unit has ``KillMode=process`` and no custom stop hooks. In
    the resident container, where systemd is intentionally absent, the command
    instead respawns the one guarded resident tmux pane. Both paths target only
    the resident runtime and leave other tmux sessions and detached workers
    alone.
    """

    unit = _resolve_unit(service_name)
    if unit is None:
        return {"ok": False, "error": f"unknown service: {service_name}"}

    if not services_available() and service_name == DISCORD_RESIDENT_SERVICE:
        return _restart_discord_resident_tmux(
            service_name,
            unit,
            notification_root=notification_root,
        )

    if not services_available():
        return {
            "ok": False,
            "error": "systemctl is not available",
            "fix_command": "install systemd",
        }

    safety: dict[str, Any] | None = None
    if service_name == DISCORD_RESIDENT_SERVICE:
        safety = _discord_resident_restart_preflight(unit)
        if not safety["ok"]:
            return {
                "ok": False,
                "service": service_name,
                "unit": unit,
                "error": safety["error"],
                "safety": safety,
                "fix_command": (
                    "refresh the installed agentbox-discord-resident.service from "
                    "/workspace/systemd, run `sudo systemctl daemon-reload`, then retry "
                    f"`{DISCORD_RESIDENT_RESTART_COMMAND}`"
                ),
            }

    reservation = None
    if service_name == DISCORD_RESIDENT_SERVICE:
        try:
            reservation = prepare_reset_notification(
                notification_root=notification_root,
                restart_request={
                    "service": service_name,
                    "unit": unit,
                    "backend": "systemd",
                    "old_identity": _systemd_identity(safety or {}),
                },
            )
        except ResetNotificationError as exc:
            return {
                "ok": False,
                "service": service_name,
                "unit": unit,
                "error": (
                    "refusing Discord resident restart: durable post-reset notification "
                    "outbox could not be prepared"
                ),
                "notification": {
                    "ok": False,
                    "error": str(exc),
                    "status": "not_prepared",
                },
                "safety": safety,
            }

    if reservation is not None:
        return _launch_restart_supervisor(
            service_name=service_name,
            unit=unit,
            reservation=reservation,
            safety=safety or {},
            notification_root=notification_root,
        )

    result = subprocess.run(
        ["systemctl", "restart", unit], capture_output=True, text=True, check=False
    )
    payload = {
        "ok": result.returncode == 0,
        "service": service_name,
        "unit": unit,
        "output": result.stdout,
        "error_output": result.stderr,
    }
    if safety is not None:
        payload["safety"] = safety
    return payload


def _restart_discord_resident_tmux(
    service_name: str,
    unit: str,
    *,
    notification_root: str | Path | None = None,
) -> dict[str, Any]:
    """Respawn only the canonical resident pane when systemd is unavailable."""

    safety = _discord_resident_tmux_preflight()
    if not safety["ok"]:
        return {
            "ok": False,
            "service": service_name,
            "unit": unit,
            "backend": "tmux",
            "error": safety["error"],
            "safety": safety,
            "fix_command": (
                f"restore the dedicated {DISCORD_RESIDENT_TMUX_SESSION!r} tmux "
                f"session, then retry `{DISCORD_RESIDENT_RESTART_COMMAND}`"
            ),
        }

    try:
        reservation = prepare_reset_notification(
            notification_root=notification_root,
            restart_request={
                "service": service_name,
                "unit": unit,
                "backend": "tmux",
                "old_identity": _tmux_identity(safety),
            },
        )
    except ResetNotificationError as exc:
        return {
            "ok": False,
            "service": service_name,
            "unit": unit,
            "backend": "tmux",
            "error": (
                "refusing Discord resident restart: durable post-reset notification "
                "outbox could not be prepared"
            ),
            "notification": {
                "ok": False,
                "error": str(exc),
                "status": "not_prepared",
            },
            "safety": safety,
        }

    return _launch_restart_supervisor(
        service_name=service_name,
        unit=unit,
        reservation=reservation,
        safety=safety,
        notification_root=notification_root,
    )


def _launch_restart_supervisor(
    *,
    service_name: str,
    unit: str,
    reservation: Any,
    safety: dict[str, Any],
    notification_root: str | Path | None,
) -> dict[str, Any]:
    """Hand restart custody to a process outside the resident lifecycle."""

    root = (
        Path(notification_root).resolve()
        if notification_root is not None
        else reset_notification_root()
    )
    argv = [
        sys.executable,
        "-m",
        "agentbox.restart_supervisor",
        "--notification-id",
        reservation.notification_id,
        "--notification-root",
        str(root),
    ]
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        notification = mark_reset_supervisor_started(
            reservation, supervisor_pid=process.pid
        )
    except (OSError, ResetNotificationError, ValueError) as exc:
        payload = {
            "ok": False,
            "service": service_name,
            "unit": unit,
            "backend": safety.get("backend"),
            "error": "failed to launch detached Discord resident restart supervisor",
            "safety": safety,
            "supervisor_error_class": exc.__class__.__name__,
        }
        _finalize_reset_notification(payload, reservation)
        return payload
    return {
        "ok": True,
        "accepted": True,
        "restart_completed": False,
        "service": service_name,
        "unit": unit,
        "backend": safety.get("backend"),
        "safety": safety,
        "supervisor_pid": process.pid,
        "notification": {"ok": True, **notification},
    }


def execute_prepared_restart(
    notification_id: str,
    *,
    notification_root: str | Path | None = None,
) -> dict[str, Any]:
    """Execute and externally finalize one already-fenced restart transaction."""

    reservation = load_reset_reservation(
        notification_id, notification_root=notification_root
    )
    request = reset_transaction_request(reservation)
    service_name = str(request.get("service") or DISCORD_RESIDENT_SERVICE)
    unit = str(request.get("unit") or SERVICE_UNITS[DISCORD_RESIDENT_SERVICE])
    backend = str(request.get("backend") or "")
    old_identity = request.get("old_identity")

    if backend == "tmux":
        safety = _discord_resident_tmux_preflight()
        current_identity = _tmux_identity(safety) if safety.get("ok") else None
    elif backend == "systemd":
        safety = _discord_resident_restart_preflight(unit)
        current_identity = _systemd_identity(safety) if safety.get("ok") else None
    else:
        safety = {"ok": False, "error": "unknown restart supervisor backend"}
        current_identity = None

    if not safety.get("ok"):
        payload = {
            "ok": False,
            "service": service_name,
            "unit": unit,
            "backend": backend,
            "error": str(safety.get("error") or "restart safety preflight failed"),
            "safety": safety,
            "finalized_by": "external_supervisor",
        }
        _finalize_reset_notification(payload, reservation)
        return payload

    if _identity_tuple(old_identity) != _identity_tuple(current_identity):
        payload = {
            "ok": True,
            "service": service_name,
            "unit": unit,
            "backend": backend,
            "safety": safety,
            "health": {
                "ok": True,
                "old_identity": old_identity,
                "current_identity": current_identity,
                "identity_changed": True,
            },
            "finalized_by": "external_supervisor_reconciliation",
        }
        _finalize_reset_notification(payload, reservation)
        return payload

    acknowledgement_status = wait_for_reset_acknowledgement(reservation)
    mark_reset_restarting(
        reservation,
        supervisor_pid=_current_pid(),
        acknowledgement_status=acknowledgement_status,
    )
    if backend == "tmux":
        pane_id = str(safety["pane_id"])
        old_pane_pid = int(safety["pane_pid"])
        result = subprocess.run(
            ["tmux", "respawn-pane", "-k", "-t", pane_id],
            capture_output=True,
            text=True,
            check=False,
        )
        health = (
            _wait_for_tmux_resident(pane_id, old_pane_pid=old_pane_pid)
            if result.returncode == 0
            else {"ok": False, "error": "guarded tmux respawn failed"}
        )
    else:
        old_main_pid = int(safety["main_pid"])
        result = subprocess.run(
            ["systemctl", "restart", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        health = (
            _wait_for_systemd_resident(unit, old_main_pid=old_main_pid)
            if result.returncode == 0
            else {"ok": False, "error": "guarded systemd restart failed"}
        )
    payload = {
        "ok": bool(result.returncode == 0 and health.get("ok")),
        "service": service_name,
        "unit": unit,
        "backend": backend,
        "safety": safety,
        "health": health,
        "finalized_by": "external_supervisor",
    }
    if not payload["ok"]:
        payload["error"] = str(health.get("error") or "resident replacement was not verified")
    _finalize_reset_notification(payload, reservation)
    return payload


def _finalize_reset_notification(
    payload: dict[str, Any],
    reservation: Any,
) -> None:
    """Persist whether the guarded restart actually succeeded before any send."""

    try:
        if payload.get("ok"):
            notification = mark_reset_succeeded(
                reservation,
                restart_evidence=payload,
            )
            payload["notification"] = {"ok": True, **notification}
            return
        notification = mark_reset_failed(
            reservation,
            restart_evidence=payload,
        )
        payload["notification"] = {"ok": True, **notification}
    except (OSError, ResetNotificationError, ValueError) as exc:
        # A restart that has already happened must never be reported as
        # confirmed when the outbox transition itself cannot be persisted.
        payload["restart_ok"] = bool(payload.get("ok"))
        payload["ok"] = False
        payload["error"] = (
            "Discord resident restart outcome could not be durably recorded for "
            "post-reset confirmation"
        )
        payload["notification"] = {
            "ok": False,
            "status": "unknown",
            "error": exc.__class__.__name__,
        }


def _discord_resident_tmux_preflight() -> dict[str, Any]:
    """Fail closed unless one pane is the canonical container resident."""

    if shutil.which("tmux") is None:
        return {
            "ok": False,
            "error": "systemctl and tmux are unavailable",
        }
    result = subprocess.run(
        [
            "tmux",
            "list-panes",
            "-t",
            f"={DISCORD_RESIDENT_TMUX_SESSION}",
            "-F",
            _TMUX_PANE_FORMAT,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or len(rows) != 1:
        detail = result.stderr.strip()
        message = (
            "refusing Discord resident restart: expected exactly one pane in "
            f"tmux session {DISCORD_RESIDENT_TMUX_SESSION!r}; observed {len(rows)}"
        )
        if detail:
            message = f"{message} ({detail})"
        return {"ok": False, "error": message, "pane_count": len(rows)}

    fields = rows[0].split("\t", 4)
    if len(fields) != 5:
        return {
            "ok": False,
            "error": "refusing Discord resident restart: invalid tmux pane metadata",
        }
    pane_id, pane_pid, pane_dead, pane_command, pane_start_command = fields
    valid_identity = (
        pane_id.startswith("%")
        and pane_id[1:].isdigit()
        and pane_pid.isdigit()
        and pane_dead == "0"
        and DISCORD_RESIDENT_TMUX_COMMAND_MARKER in pane_start_command
    )
    if not valid_identity:
        return {
            "ok": False,
            "error": (
                "refusing Discord resident restart: tmux pane does not match "
                "the live canonical resident contract"
            ),
            "pane_id": pane_id,
            "pane_pid": pane_pid,
            "pane_dead": pane_dead,
            "pane_command": pane_command,
            "command_marker_present": (
                DISCORD_RESIDENT_TMUX_COMMAND_MARKER in pane_start_command
            ),
        }
    return {
        "ok": True,
        "backend": "tmux",
        "session": DISCORD_RESIDENT_TMUX_SESSION,
        "pane_id": pane_id,
        "pane_pid": int(pane_pid),
        "pane_command": pane_command,
        "stop_scope": "canonical Discord resident tmux pane only",
        "preserves": [
            "resident-managed detached subagents",
            "other tmux-backed Megaplan and cloud chain sessions",
        ],
        "caveat": "an in-flight Discord resident turn is interrupted by the relaunch",
    }


def _wait_for_tmux_resident(
    pane_id: str,
    *,
    old_pane_pid: int,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Wait for tmux to replace the pane shell and launch the resident child."""

    deadline = time.monotonic() + timeout_s
    last_error = "resident process did not become healthy before the timeout"
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane_id, _TMUX_PANE_FORMAT],
            capture_output=True,
            text=True,
            check=False,
        )
        fields = result.stdout.rstrip("\n").split("\t", 4)
        if result.returncode == 0 and len(fields) == 5:
            _, pane_pid_text, pane_dead, _, pane_start_command = fields
            if (
                pane_pid_text.isdigit()
                and int(pane_pid_text) != old_pane_pid
                and pane_dead == "0"
                and DISCORD_RESIDENT_TMUX_COMMAND_MARKER in pane_start_command
            ):
                pane_pid = int(pane_pid_text)
                resident_pid = _resident_descendant_pid(pane_pid)
                if resident_pid is not None:
                    return {
                        "ok": True,
                        "pane_id": pane_id,
                        "old_pane_pid": old_pane_pid,
                        "pane_pid": pane_pid,
                        "resident_pid": resident_pid,
                        "process": DISCORD_RESIDENT_TMUX_COMMAND_MARKER,
                    }
        elif result.stderr.strip():
            last_error = result.stderr.strip()
        time.sleep(0.1)
    return {
        "ok": False,
        "error": last_error,
        "pane_id": pane_id,
        "old_pane_pid": old_pane_pid,
    }


def _wait_for_systemd_resident(
    unit: str,
    *,
    old_main_pid: int,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                "-p",
                "MainPID",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                unit,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        properties = _systemctl_properties(result.stdout)
        try:
            main_pid = int(properties.get("MainPID") or 0)
        except ValueError:
            main_pid = 0
        if (
            result.returncode == 0
            and main_pid > 0
            and main_pid != old_main_pid
            and properties.get("ActiveState") == "active"
        ):
            return {
                "ok": True,
                "old_main_pid": old_main_pid,
                "main_pid": main_pid,
                "active_state": properties.get("ActiveState"),
                "sub_state": properties.get("SubState"),
                "identity_changed": True,
            }
        time.sleep(0.1)
    return {
        "ok": False,
        "error": "resident systemd MainPID did not change before the timeout",
        "old_main_pid": old_main_pid,
    }


def _resident_descendant_pid(root_pid: int) -> int | None:
    """Return the canonical resident PID below a pane shell, using local procfs."""

    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        command = cmdline.replace(b"\0", b" ").decode("utf-8", errors="replace")
        if pid != root_pid and DISCORD_RESIDENT_TMUX_COMMAND_MARKER in command:
            return pid
        try:
            children = (
                Path("/proc") / str(pid) / "task" / str(pid) / "children"
            ).read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        pending.extend(int(value) for value in children.split() if value.isdigit())
    return None


def _discord_resident_restart_preflight(unit: str) -> dict[str, Any]:
    """Fail closed unless systemd will signal only the resident main process."""

    result = subprocess.run(
        [
            "systemctl",
            "show",
            "-p",
            "KillMode",
            "-p",
            "ExecStop",
            "-p",
            "ExecStopPost",
            "-p",
            "MainPID",
            unit,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    properties = _systemctl_properties(result.stdout)
    kill_mode = properties.get("KillMode", "")
    custom_stop_hooks = {
        name: properties.get(name, "")
        for name in ("ExecStop", "ExecStopPost")
        if properties.get(name, "")
    }
    try:
        main_pid = int(properties.get("MainPID") or 0)
    except ValueError:
        main_pid = 0
    if (
        result.returncode != 0
        or kill_mode != DISCORD_RESIDENT_SAFE_KILL_MODE
        or custom_stop_hooks
        or main_pid <= 0
    ):
        detail = result.stderr.strip()
        observed = kill_mode or "unavailable"
        message = (
            "refusing Discord resident restart: installed systemd unit must report "
            f"KillMode={DISCORD_RESIDENT_SAFE_KILL_MODE!s} with no ExecStop/ExecStopPost hooks; "
            f"observed KillMode={observed!r}, custom_stop_hooks={sorted(custom_stop_hooks)}, "
            f"MainPID={main_pid}"
        )
        if detail:
            message = f"{message} ({detail})"
        return {
            "ok": False,
            "kill_mode": observed,
            "required_kill_mode": DISCORD_RESIDENT_SAFE_KILL_MODE,
            "custom_stop_hooks": sorted(custom_stop_hooks),
            "main_pid": main_pid,
            "error": message,
        }
    return {
        "ok": True,
        "kill_mode": kill_mode,
        "custom_stop_hooks": [],
        "main_pid": main_pid,
        "stop_scope": "resident main process only",
        "preserves": [
            "resident-managed detached subagents",
            "tmux-backed Megaplan and cloud chains",
        ],
        "caveat": "an in-flight Discord resident turn is interrupted by the relaunch",
    }


def resident_process_identity() -> dict[str, Any] | None:
    """Return the current canonical resident identity without mutating it."""

    if services_available():
        safety = _discord_resident_restart_preflight(
            SERVICE_UNITS[DISCORD_RESIDENT_SERVICE]
        )
        return _systemd_identity(safety) if safety.get("ok") else None
    safety = _discord_resident_tmux_preflight()
    return _tmux_identity(safety) if safety.get("ok") else None


def _systemd_identity(safety: dict[str, Any]) -> dict[str, Any]:
    return {"backend": "systemd", "main_pid": int(safety.get("main_pid") or 0)}


def _tmux_identity(safety: dict[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "backend": "tmux",
        "pane_id": str(safety.get("pane_id") or ""),
        "pane_pid": int(safety.get("pane_pid") or 0),
    }
    resident_pid = safety.get("resident_pid")
    if resident_pid is not None:
        identity["resident_pid"] = int(resident_pid)
    return identity


def _identity_tuple(value: object) -> tuple[str, int] | None:
    if not isinstance(value, dict):
        return None
    backend = str(value.get("backend") or "")
    field = "main_pid" if backend == "systemd" else "pane_pid"
    try:
        pid = int(value.get(field) or 0)
    except (TypeError, ValueError):
        return None
    return (backend, pid) if backend in {"systemd", "tmux"} and pid > 0 else None


def _current_pid() -> int:
    return os.getpid()


def _systemctl_properties(output: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in output.splitlines():
        name, separator, value = line.partition("=")
        if separator and name:
            properties[name] = value.strip()
    return properties


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
    "DISCORD_RESIDENT_RESTART_COMMAND",
    "DISCORD_RESIDENT_SAFE_KILL_MODE",
    "DISCORD_RESIDENT_SERVICE",
    "DISCORD_RESIDENT_TMUX_SESSION",
    "SERVICE_UNITS",
    "list_services",
    "execute_prepared_restart",
    "resident_process_identity",
    "restart_service",
    "service_logs",
    "services_available",
]
