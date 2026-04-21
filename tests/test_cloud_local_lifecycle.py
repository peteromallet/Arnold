from __future__ import annotations

import shutil
import subprocess

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

_docker_info = subprocess.run(
    ["docker", "info"],
    capture_output=True,
    text=True,
    check=False,
)
if _docker_info.returncode != 0:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"docker daemon unavailable: {_docker_info.stderr.strip()}",
        allow_module_level=True,
    )


def _spec() -> CloudSpec:
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
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        local=LocalSpec(compose_project="megaplan-local-smoke", workdir="workspace"),
        toolchains=[],
    )


@pytest.mark.slow
def test_local_provider_lifecycle_smoke(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec = _spec()
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
