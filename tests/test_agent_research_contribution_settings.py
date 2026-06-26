from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("VIBECOMFY_HEADLESS", "1")

from vibecomfy.comfy_nodes.agent import routes


def test_agent_settings_default_opt_out(tmp_path) -> None:
    result = routes._handle_agent_settings_get(settings_path=tmp_path / "settings.json")

    assert result["ok"] is True
    assert result["research_contribution_enabled"] is False


def test_agent_settings_post_persists_research_contribution(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"

    saved = routes._handle_agent_settings_post(
        {"research_contribution_enabled": True},
        settings_path=settings_path,
    )
    loaded = routes._handle_agent_settings_get(settings_path=settings_path)

    assert saved["ok"] is True
    assert saved["research_contribution_enabled"] is True
    assert loaded["research_contribution_enabled"] is True


def test_research_contribution_run_is_gated_by_opt_in(tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: Any) -> object:
        calls.append(command)
        return type("FakeProcess", (), {"pid": 1234})()

    result = routes._handle_research_contribution_run(
        {},
        settings_path=tmp_path / "settings.json",
        runner=fake_runner,
    )

    assert result["ok"] is True
    assert result["triggered"] is False
    assert calls == []


def test_research_contribution_run_starts_pipeline_when_opted_in(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    routes._handle_agent_settings_post({"research_contribution_enabled": True}, settings_path=settings_path)
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: Any) -> object:
        calls.append(command)
        return type("FakeProcess", (), {"pid": 4321})()

    result = routes._handle_research_contribution_run(
        {},
        settings_path=settings_path,
        runner=fake_runner,
    )

    assert result["ok"] is True
    assert result["triggered"] is True
    assert calls
    assert calls[0][-1] == "--upload"
    assert calls[0][-2].endswith("scripts/pipeline_orchestrate.py")
    assert result["research_contribution_last_trigger"]["pid"] == 4321
