from __future__ import annotations

import shutil

from agentbox.services import list_services, restart_service, service_logs


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
