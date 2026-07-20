from __future__ import annotations

from pathlib import Path

import pytest

from agentbox.bootstrap import bootstrap, bootstrap_status
from agentbox.config import AgentBoxConfig


@pytest.fixture
def config(tmp_path: Path) -> AgentBoxConfig:
    return AgentBoxConfig(workspace_root=tmp_path / "workspace")


def test_bootstrap_creates_expected_directories_and_units(config: AgentBoxConfig) -> None:
    result = bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    assert result["ok"] is True
    assert config.workspace_root.exists()
    assert config.repos_root.exists()
    assert config.runs_root.exists()
    assert config.locks_root.exists()
    assert config.ops_store_root.exists()
    assert config.credentials_root.exists()

    systemd_dir = config.workspace_root / "systemd"
    assert (systemd_dir / "arnold-guardian.service").exists()
    resident_unit = systemd_dir / "agentbox-discord-resident.service"
    assert resident_unit.exists()
    resident_text = resident_unit.read_text(encoding="utf-8")
    assert "Environment=MEGAPLAN_RESIDENT_MODEL_PROVIDER=codex" in resident_text
    assert "Environment=MEGAPLAN_RESIDENT_MODEL=gpt-5.6-sol" in resident_text
    assert "Environment=MEGAPLAN_RESIDENT_MODE=production" in resident_text
    assert "Environment=MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=production" in resident_text
    assert "KillMode=process" in resident_text


def test_bootstrap_is_idempotent(config: AgentBoxConfig) -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    first = bootstrap(config, project_root=project_root)
    assert first["ok"] is True
    assert first["created"]

    second = bootstrap(config, project_root=project_root)
    assert second["ok"] is True
    assert second["created"] == []
    assert second["updated"] == []


def test_bootstrap_does_not_delete_existing_content(config: AgentBoxConfig) -> None:
    existing_repo = config.repos_root / "existing-repo"
    existing_repo.mkdir(parents=True, exist_ok=True)
    marker = existing_repo / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    assert result["ok"] is True
    assert marker.exists()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_bootstrap_creates_ssh_profile_if_missing(config: AgentBoxConfig) -> None:
    result = bootstrap(config, user="agentbox")

    ssh_config = config.workspace_root / "ssh" / "config"
    assert ssh_config.exists()
    assert "Host agentbox" in ssh_config.read_text(encoding="utf-8")
    assert "User agentbox" in ssh_config.read_text(encoding="utf-8")
    assert result["created"]


def test_bootstrap_does_not_overwrite_existing_ssh_profile(config: AgentBoxConfig) -> None:
    ssh_dir = config.workspace_root / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    ssh_config = ssh_dir / "config"
    ssh_config.write_text("Host agentbox\n    Hostname 10.0.0.1\n", encoding="utf-8")

    bootstrap(config)

    text = ssh_config.read_text(encoding="utf-8")
    assert "10.0.0.1" in text
    assert "Hostname localhost" not in text


def test_bootstrap_status_reports_existing_paths(config: AgentBoxConfig) -> None:
    bootstrap(config, project_root=Path(__file__).resolve().parent.parent.parent)

    status = bootstrap_status(config)

    assert status["workspace_root"] == str(config.workspace_root)
    assert status["layout_directories"][str(config.repos_root)]["exists"] is True
    assert status["systemd_units"]["arnold-guardian"]["exists"] is True
    assert status["systemd_units"]["agentbox-discord-resident"]["exists"] is True
