from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agentbox.bootstrap import bootstrap
from agentbox.config import AgentBoxConfig
from agentbox.doctor import checkup


@pytest.fixture
def config(tmp_path: Path) -> AgentBoxConfig:
    return AgentBoxConfig(workspace_root=tmp_path / "workspace")


def test_doctor_passes_after_bootstrap(config: AgentBoxConfig, monkeypatch) -> None:
    bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")

    report = checkup(config)

    assert report.ok is True
    names = {check["name"] for check in report.checks}
    assert "workspace_directories" in names
    assert "git_installed" in names
    assert "tmux_installed" in names


def test_doctor_reports_failure_when_git_missing(config: AgentBoxConfig, monkeypatch) -> None:
    bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    def fake_which(name: str) -> str | None:
        return None if name == "git" else f"/usr/bin/{name}"

    monkeypatch.setattr(shutil, "which", fake_which)

    report = checkup(config)

    assert report.ok is False
    git_check = next(check for check in report.checks if check["name"] == "git_installed")
    assert git_check["status"] == "fail"


def test_doctor_reports_failure_when_tmux_missing(config: AgentBoxConfig, monkeypatch) -> None:
    bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    def fake_which(name: str) -> str | None:
        return None if name == "tmux" else f"/usr/bin/{name}"

    monkeypatch.setattr(shutil, "which", fake_which)

    report = checkup(config)

    assert report.ok is False
    tmux_check = next(check for check in report.checks if check["name"] == "tmux_installed")
    assert tmux_check["status"] == "fail"


def test_doctor_warns_when_gh_missing(config: AgentBoxConfig, monkeypatch) -> None:
    bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    def fake_which(name: str) -> str | None:
        return None if name == "gh" else f"/usr/bin/{name}"

    monkeypatch.setattr(shutil, "which", fake_which)

    report = checkup(config)

    assert report.ok is True
    gh_check = next(check for check in report.checks if check["name"] == "gh_installed")
    assert gh_check["status"] == "warn"
