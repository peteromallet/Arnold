"""Tests that materialize_deploy_dir does NOT emit railway artifacts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    RepoSpec,
    CodexSpec,
    MegaplanSpec,
    ResourcesSpec,
    LocalSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.cloud.template import materialize_deploy_dir


def _ssh_spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )


def _local_spec() -> CloudSpec:
    return CloudSpec(
        provider="local",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        local=LocalSpec(),
    )


class TestMaterializeNoRailway:
    """materialize_deploy_dir must NOT emit railway.toml or other railway artifacts."""

    def test_no_railway_toml_for_ssh(self) -> None:
        """SSH provider: deploy dir must not contain railway.toml."""
        spec = _ssh_spec()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "deploy"
            materialize_deploy_dir(spec, dest)
            assert not (dest / "railway.toml").exists(), (
                "railway.toml must not be materialized for ssh provider"
            )
            assert not (dest / "Railwayfile").exists()
            # Also check no .railway/ directory
            assert not (dest / ".railway").exists()

    def test_no_railway_toml_for_local(self) -> None:
        """Local provider: deploy dir must not contain railway.toml."""
        spec = _local_spec()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "deploy"
            materialize_deploy_dir(spec, dest)
            assert not (dest / "railway.toml").exists(), (
                "railway.toml must not be materialized for local provider"
            )
            assert not (dest / "Railwayfile").exists()

    def test_expected_files_exist_for_ssh(self) -> None:
        """SSH deploy dir must contain the core deployment files."""
        spec = _ssh_spec()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "deploy"
            materialize_deploy_dir(spec, dest)
            assert (dest / "Dockerfile").exists()
            assert (dest / "entrypoint.sh").exists()
            assert (dest / "healthserver.py").exists()
            assert (dest / "wrappers").is_dir()

    def test_no_docker_compose_for_ssh(self) -> None:
        """SSH provider must NOT emit docker-compose.yaml."""
        spec = _ssh_spec()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "deploy"
            materialize_deploy_dir(spec, dest)
            assert not (dest / "docker-compose.yaml").exists(), (
                "docker-compose.yaml must only be emitted for local provider"
            )

    def test_docker_compose_exists_for_local(self) -> None:
        """Local provider must emit docker-compose.yaml."""
        spec = _local_spec()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "deploy"
            materialize_deploy_dir(spec, dest)
            assert (dest / "docker-compose.yaml").exists(), (
                "docker-compose.yaml must be emitted for local provider"
            )
            # The local workdir must also be created
            assert (dest / spec.local.workdir).is_dir()
