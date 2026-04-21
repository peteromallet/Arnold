from __future__ import annotations

import pytest

from megaplan.cloud.providers.local import LocalProvider
from megaplan.cloud.providers.railway import RailwayProvider
from megaplan.cloud.providers.ssh import SshProvider
from megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from megaplan.types import CliError


def _base_spec(provider: str) -> dict[str, object]:
    return {
        "provider": provider,
        "repo": RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        "agents": {"default": "codex"},
        "codex": CodexSpec(model="ops-model", reasoning="medium"),
        "mode": "idle",
        "megaplan": MegaplanSpec(ref="main"),
        "resources": ResourcesSpec(volume="agent-volume", port=8080),
        "secrets": [],
        "toolchains": [],
    }


def test_missing_railway_cli_raises_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: None)

    with pytest.raises(CliError) as excinfo:
        RailwayProvider(
            CloudSpec(
                **_base_spec("railway"),
                railway=RailwaySpec(service="svc", session="ses", project=None),
            )
        )

    assert excinfo.value.code == "provider_unavailable"
    assert "railway" in excinfo.value.message
    assert "https://docs.railway.app/develop/cli" in excinfo.value.message


def test_missing_docker_cli_raises_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megaplan.cloud.providers.local.shutil.which", lambda _name: None)

    with pytest.raises(CliError) as excinfo:
        LocalProvider(
            CloudSpec(
                **_base_spec("local"),
                local=LocalSpec(compose_project="demo", workdir="workspace"),
            )
        )

    assert excinfo.value.code == "provider_unavailable"
    assert "docker" in excinfo.value.message
    assert "https://docs.docker.com/get-docker/" in excinfo.value.message


def test_missing_ssh_cli_raises_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megaplan.cloud.providers.ssh.shutil.which", lambda _name: None)

    with pytest.raises(CliError) as excinfo:
        SshProvider(
            CloudSpec(
                **_base_spec("ssh"),
                ssh=SshSpec(host="deploy.example.com"),
            )
        )

    assert excinfo.value.code == "provider_unavailable"
    assert "ssh" in excinfo.value.message
    assert "https://www.openssh.com/" in excinfo.value.message
