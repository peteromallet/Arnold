"""Tests for SshProvider.deploy() persistent mounts."""

from __future__ import annotations

import shlex
from pathlib import Path
from unittest.mock import MagicMock, patch

from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    RepoSpec,
    CodexSpec,
    MegaplanSpec,
    ResourcesSpec,
    SshSpec,
)


def _minimal_cloud_spec(**ssh_overrides) -> CloudSpec:
    """Build a minimal valid CloudSpec with provider=ssh."""
    ssh = SshSpec(
        host="testhost",
        **ssh_overrides,
    )
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=ssh,
    )


class TestSshDeployPersistentMounts:
    """SshProvider.deploy() must create remote dirs and run Docker with
    persistent workspace + cache mounts, without requiring real SSH/Docker."""

    def _build_deploy_command(self, spec: CloudSpec) -> str:
        """Reconstruct the exact deploy remote command that SshProvider would
        send, by calling _remote_run with a mock that captures the command."""
        from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider

        captured_commands: list[str] = []

        class CaptureSshProvider(SshProvider):
            def _remote_run(self, command, *, capture_output=True, input=None):
                captured_commands.append(command)
                # Return a mock completed process
                from subprocess import CompletedProcess
                return CompletedProcess(args=[], returncode=0, stdout="", stderr="")

            def _run(self, argv, *, capture_output=True, input=None):
                # For the docker rm/run calls
                captured_commands.append(" ".join(argv))
                from subprocess import CompletedProcess
                return CompletedProcess(args=[], returncode=0, stdout="", stderr="")

            def _sync_deploy_dir(self, deploy_dir):
                pass  # skip for this test

        provider = CaptureSshProvider(spec)
        provider.deploy(Path("/tmp/fake"), secrets={"OPENAI_API_KEY": "sk-test"})
        # Return the concatenated commands for assertion
        return "\n".join(captured_commands)

    def test_deploy_creates_workspace_and_cache_dirs(self) -> None:
        """deploy() must mkdir -p the workspace_dir and cache subdirs."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)

        # Should create workspace_dir
        assert shlex.quote(spec.ssh.workspace_dir) in commands
        # Should create cache_dir/pip
        assert shlex.quote(f"{spec.ssh.cache_dir}/pip") in commands
        # Should create cache_dir/npm
        assert shlex.quote(f"{spec.ssh.cache_dir}/npm") in commands

    def test_deploy_creates_remote_dir(self) -> None:
        """deploy() must mkdir -p the remote_dir."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        assert shlex.quote(spec.ssh.remote_dir) in commands

    def test_deploy_mounts_workspace_volume(self) -> None:
        """Docker run must include -v <workspace_dir>:/workspace."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        workspace_mount = f"-v {shlex.quote(spec.ssh.workspace_dir)}:/workspace"
        assert workspace_mount in commands, (
            f"Expected workspace mount not found in:\n{commands}"
        )

    def test_deploy_mounts_pip_cache(self) -> None:
        """Docker run must include -v <cache_dir>/pip:/root/.cache/pip."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        pip_mount = (
            f"-v {shlex.quote(f'{spec.ssh.cache_dir}/pip')}:/root/.cache/pip"
        )
        assert pip_mount in commands, (
            f"Expected pip cache mount not found in:\n{commands}"
        )

    def test_deploy_mounts_npm_cache(self) -> None:
        """Docker run must include -v <cache_dir>/npm:/root/.npm."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        npm_mount = (
            f"-v {shlex.quote(f'{spec.ssh.cache_dir}/npm')}:/root/.npm"
        )
        assert npm_mount in commands, (
            f"Expected npm cache mount not found in:\n{commands}"
        )

    def test_deploy_uses_custom_paths(self) -> None:
        """When workspace_dir/cache_dir are overridden, deploy uses them."""
        spec = _minimal_cloud_spec(
            workspace_dir="/data/ws",
            cache_dir="/data/cache",
            remote_dir="/data/deploy",
        )
        commands = self._build_deploy_command(spec)
        assert "/data/ws" in commands
        assert "/data/cache/pip" in commands
        assert "/data/cache/npm" in commands
        assert "/data/deploy" in commands

    def test_deploy_includes_restart_policy(self) -> None:
        """Docker run must include --restart unless-stopped."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        assert "--restart unless-stopped" in commands

    def test_deploy_binds_container_port(self) -> None:
        """Docker run must publish the resources.port."""
        spec = _minimal_cloud_spec()
        commands = self._build_deploy_command(spec)
        port = spec.resources.port
        assert f"-p {port}:{port}" in commands


def test_entrypoint_starts_discord_resident_from_shared_secret_env() -> None:
    from arnold_pipelines.megaplan.cloud.template import render_entrypoint

    entrypoint = render_entrypoint(_minimal_cloud_spec())

    assert "/workspace/.secrets/megaplan-resident-discord.env" in entrypoint
    assert "tmux has-session -t megaplan-resident-discord" in entrypoint
    assert "python -m arnold_pipelines.megaplan resident discord" in entrypoint
    assert "export MEGAPLAN_RESIDENT_MODE=production MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=production" in entrypoint
    assert "resident discord --mode production" in entrypoint
    assert "--store-root /workspace/arnold/.megaplan/resident" in entrypoint


def test_resident_self_heal_starts_the_production_bot_boundary() -> None:
    ensure_script = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident"
    ).read_text()

    assert (
        "export MEGAPLAN_RESIDENT_MODE=production "
        "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=production"
    ) in ensure_script
    assert "resident discord --mode production" in ensure_script
    assert "--store-root /workspace/arnold/.megaplan/resident" in ensure_script
