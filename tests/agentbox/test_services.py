from __future__ import annotations

import os
import signal
import shutil
import subprocess
import sys

from agentbox.reset_notifications import list_reset_notifications
from agentbox.services import (
    DISCORD_RESIDENT_RESTART_COMMAND,
    list_services,
    restart_service,
    service_logs,
)


def test_list_services_returns_expected_service_names() -> None:
    services = list_services()
    names = {service["name"] for service in services}
    assert "arnold-guardian" in names
    assert "agentbox-discord-resident" in names


def test_list_services_returns_unknown_when_systemctl_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)

    services = list_services()

    assert all(service["status"] == "unknown" for service in services)
    assert all(service["loaded"] is None for service in services)
    assert all(service["active"] is None for service in services)


def test_service_logs_returns_ok_false_for_unknown_service() -> None:
    result = service_logs("nonexistent")
    assert result["ok"] is False
    assert "unknown service" in result["error"]


def test_restart_service_returns_ok_false_for_unknown_service() -> None:
    result = restart_service("nonexistent")
    assert result["ok"] is False
    assert "unknown service" in result["error"]


def test_resident_restart_uses_guarded_tmux_pane_without_systemctl(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "list-panes":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "%39\t1989952\t0\tbash\t"
                    "python -m arnold_pipelines.megaplan resident discord --mode dev\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "agentbox.services._wait_for_tmux_resident",
        lambda pane_id, *, old_pane_pid: {
            "ok": True,
            "pane_id": pane_id,
            "old_pane_pid": old_pane_pid,
            "pane_pid": 2000001,
            "resident_pid": 2000002,
        },
    )

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is True
    assert result["backend"] == "tmux"
    assert result["safety"]["stop_scope"] == (
        "canonical Discord resident tmux pane only"
    )
    assert result["health"]["resident_pid"] == 2000002
    assert result["notification"]["delivery"]["status"] == "pending"
    assert calls[0][:5] == [
        "tmux",
        "list-panes",
        "-t",
        "=megaplan-resident-discord",
        "-F",
    ]
    assert calls[1] == ["tmux", "respawn-pane", "-k", "-t", "%39"]


def test_resident_tmux_restart_refuses_unrecognized_pane_command(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="%39\t1989952\t0\tbash\tpython -m unrelated.worker\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["backend"] == "tmux"
    assert result["safety"]["command_marker_present"] is False
    assert "does not match" in result["error"]
    assert len(calls) == 1


def test_resident_restart_refuses_unsafe_installed_kill_mode(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="KillMode=control-group\nExecStop=\nExecStopPost=\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["safety"]["required_kill_mode"] == "process"
    assert calls == [
        [
            "systemctl",
            "show",
            "-p",
            "KillMode",
            "-p",
            "ExecStop",
            "-p",
            "ExecStopPost",
            "agentbox-discord-resident.service",
        ]
    ]
    assert DISCORD_RESIDENT_RESTART_COMMAND in result["fix_command"]


def test_resident_restart_targets_only_guarded_service(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        calls.append(argv)
        stdout = (
            "KillMode=process\nExecStop=\nExecStopPost=\n"
            if argv[1] == "show"
            else ""
        )
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is True
    assert result["safety"]["stop_scope"] == "resident main process only"
    assert result["safety"]["preserves"] == [
        "resident-managed detached subagents",
        "tmux-backed Megaplan and cloud chains",
    ]
    assert calls == [
        [
            "systemctl",
            "show",
            "-p",
            "KillMode",
            "-p",
            "ExecStop",
            "-p",
            "ExecStopPost",
            "agentbox-discord-resident.service",
        ],
        ["systemctl", "restart", "agentbox-discord-resident.service"],
    ]
    assert result["notification"]["restart"]["status"] == "succeeded"
    assert result["notification"]["delivery"]["status"] == "pending"


def test_failed_guarded_restart_never_enables_a_success_confirmation(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        if argv[1] == "show":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="KillMode=process\nExecStop=\nExecStopPost=\n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="restart failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is False
    assert result["notification"]["restart"]["status"] == "failed"
    assert result["notification"]["delivery"]["status"] == "restart_failed"
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"restart_failed": 1}


def test_resident_restart_refuses_custom_stop_hook(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "KillMode=process\n"
                "ExecStop={ path=/usr/bin/pkill ; argv[]=/usr/bin/pkill worker ; }\n"
                "ExecStopPost=\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["safety"]["custom_stop_hooks"] == ["ExecStop"]
    assert "no ExecStop/ExecStopPost hooks" in result["error"]


def test_main_process_stop_preserves_detached_agent_and_cloud_session() -> None:
    """Exercise the process boundary selected by systemd KillMode=process.

    This deliberately signals only the simulated resident main PID. The
    resident-launched worker is session-detached like the managed Codex
    supervisor, while the second process represents an independent tmux/cloud
    session. No live systemd unit, bot, tmux server, or remote host is touched.
    """

    sleeper = "import time; time.sleep(60)"
    resident_script = (
        "import subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-c', {sleeper!r}], "
        "start_new_session=True); "
        "print(child.pid, flush=True); "
        "time.sleep(60)"
    )
    resident = subprocess.Popen(
        [sys.executable, "-c", resident_script],
        stdout=subprocess.PIPE,
        text=True,
    )
    cloud_session = subprocess.Popen(
        [sys.executable, "-c", sleeper],
        start_new_session=True,
    )
    managed_agent_pid: int | None = None
    try:
        assert resident.stdout is not None
        managed_agent_pid = int(resident.stdout.readline().strip())

        os.kill(resident.pid, signal.SIGTERM)
        resident.wait(timeout=5)

        os.kill(managed_agent_pid, 0)
        assert cloud_session.poll() is None
    finally:
        if resident.poll() is None:
            resident.terminate()
            resident.wait(timeout=5)
        if managed_agent_pid is not None:
            try:
                os.kill(managed_agent_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if cloud_session.poll() is None:
            cloud_session.terminate()
        cloud_session.wait(timeout=5)
