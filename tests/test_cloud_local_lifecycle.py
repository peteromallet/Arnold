from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from megaplan.cloud.cli import _materialized_deploy_dir
from megaplan.cloud.providers.local import LocalProvider
from megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
)


if shutil.which("docker") is None:  # pragma: no cover - environment-dependent
    pytest.skip("docker not available", allow_module_level=True)

try:
    _docker_info = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
except subprocess.TimeoutExpired:  # pragma: no cover - environment-dependent
    pytest.skip("docker daemon unavailable: docker info timed out", allow_module_level=True)
if _docker_info.returncode != 0:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"docker daemon unavailable: {_docker_info.stderr.strip()}",
        allow_module_level=True,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _spec(*, port: int = 8080) -> CloudSpec:
    return CloudSpec(
        provider="local",
        repo=RepoSpec(
            url="https://github.com/example/cloud-app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=port),
        secrets=[],
        local=LocalSpec(compose_project="megaplan-local-smoke", workdir="workspace"),
        toolchains=[],
    )


@pytest.mark.slow
def test_local_provider_lifecycle_smoke(tmp_path, monkeypatch) -> None:
    docker_config = os.environ.get("DOCKER_CONFIG")
    if docker_config is None:
        default_docker_config = Path.home() / ".docker"
        if default_docker_config.exists():
            monkeypatch.setenv("DOCKER_CONFIG", str(default_docker_config))

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec = _spec(port=_free_port())
    provider = LocalProvider(spec)

    with _materialized_deploy_dir(spec) as deploy_dir:
        try:
            assert provider.build(deploy_dir) == 0
            assert provider.deploy(deploy_dir, secrets={}) == 0
            result = provider.ssh_exec("which megaplan")
            assert result.returncode == 0
            assert "megaplan" in result.stdout
        finally:
            provider.destroy()
