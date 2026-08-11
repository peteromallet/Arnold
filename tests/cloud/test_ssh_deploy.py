"""Tests for SshProvider.deploy() persistent mounts."""

from __future__ import annotations

import shlex
from pathlib import Path

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
    assert "MEGAPLAN_RESIDENT_STORE_ROOT" in entrypoint
    assert "--store-root" in entrypoint
    assert "MEGAPLAN_RUNTIME_PYTHON" in entrypoint
    assert 'exec \\"\\$runtime_python\\" -P -m arnold_pipelines.megaplan resident discord' in entrypoint
    assert "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE" in entrypoint
    assert "MEGAPLAN_RESIDENT_MODE:-production" in entrypoint
    assert "/workspace/.megaplan/resident-runtime.env" in entrypoint
    assert entrypoint.index("/workspace/.cloud-hot-env") < entrypoint.index(
        "/workspace/.megaplan/resident-runtime.env"
    )
    assert "tmux new-session -d -s megaplan-resident-discord -c /workspace" in entrypoint
    assert "runtime_src=/workspace/arnold" in entrypoint
    assert "export MEGAPLAN_RUNTIME_SRC=/workspace/arnold" in entrypoint
    assert r'cd \"\$runtime_src\"' in entrypoint


def test_entrypoint_boot_supervisors_use_fixed_workspace_runtime() -> None:
    from arnold_pipelines.megaplan.cloud.template import render_entrypoint

    entrypoint = render_entrypoint(_minimal_cloud_spec())

    # Heartbeat, watchdog, and resident all execute from the fixed
    # /workspace/arnold checkout (P4 config cleanup): hot env is
    # credentials-only and the legacy runtime selectors are retired, so
    # runtime_src is a literal, never an env-expanded selector chain.
    assert entrypoint.count("runtime_src=/workspace/arnold") == 3
    assert entrypoint.count(r'cd \"\$runtime_src\"') == 3
    assert r"MEGAPLAN_RUNTIME_SRC:-\${CLOUD_WATCHDOG_ARNOLD_SRC" not in entrypoint
    assert "CLOUD_WATCHDOG_ARNOLD_SRC" not in entrypoint
    assert (
        r'exec \"\$runtime_src/arnold_pipelines/megaplan/cloud/wrappers/'
        r'arnold-heartbeat\"'
    ) in entrypoint
    assert (
        r'exec \"\$runtime_src/arnold_pipelines/megaplan/cloud/wrappers/'
        r'arnold-watchdog\"'
    ) in entrypoint
    assert (
        "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/"
        "arnold-heartbeat"
    ) not in entrypoint
    assert (
        "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/"
        "arnold-watchdog"
    ) not in entrypoint
    assert "tmux new-session -d -s megaplan-resident-discord -c /workspace/arnold" not in entrypoint


def test_entrypoint_runtime_selector_quoting_is_valid_bash() -> None:
    import subprocess

    from arnold_pipelines.megaplan.cloud.template import render_entrypoint

    entrypoint = render_entrypoint(_minimal_cloud_spec())
    syntax = subprocess.run(
        ["bash", "-n"],
        input=entrypoint,
        capture_output=True,
        text=True,
        check=False,
    )

    assert syntax.returncode == 0, syntax.stderr


def test_cloud_image_installs_pinned_railway_cli() -> None:
    dockerfile = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/templates/Dockerfile"
    ).read_text()

    assert "@railway/cli@4.12.0" in dockerfile
    assert "ln -sf /opt/zero-recovery-node/bin/railway /usr/local/bin/railway" in dockerfile
    assert "railway --version" in dockerfile


def test_cloud_image_installs_account_management_before_finite_uid_creation() -> None:
    dockerfile = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/templates/Dockerfile"
    ).read_text()

    package_install = dockerfile.index("apt-get install -y --no-install-recommends")
    passwd_package = dockerfile.index("      passwd \\")
    finite_group = dockerfile.index("/usr/sbin/groupadd --gid 65532 finite-model")
    finite_user = dockerfile.index("/usr/sbin/useradd --uid 65532 --gid 65532")

    assert package_install < passwd_package < finite_group < finite_user
    assert "RUN groupadd " not in dockerfile
    assert "&& useradd " not in dockerfile


def test_cloud_image_bakes_source_runtime_floor_without_pypi_name_collision() -> None:
    dockerfile = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/templates/Dockerfile"
    ).read_text()

    assert 'ARG MEGAPLAN_INSTALL_SPEC=""' in dockerfile
    for requirement in (
        '"PyYAML>=6.0"',
        '"pydantic>=2.0"',
        '"python-ulid>=3.0"',
        '"psutil>=5.9"',
        '"httpx>=0.27"',
        '"discord.py>=2.6,<3"',
    ):
        assert requirement in dockerfile
    assert "import discord, httpx, psutil, pydantic, ulid, yaml" in dockerfile
    assert 'ARG MEGAPLAN_INSTALL_SPEC="arnold[agent]"' not in dockerfile


def test_entrypoint_persists_railway_auth_without_rendered_secret() -> None:
    import subprocess

    from arnold_pipelines.megaplan.cloud.template import render_entrypoint

    entrypoint = render_entrypoint(_minimal_cloud_spec())

    assert "RAILWAY_CREDS_DIR=/workspace/.creds/railway" in entrypoint
    assert 'ln -s "$RAILWAY_CREDS_DIR" /root/.railway' in entrypoint
    assert "/workspace/.creds/railway-config.json" in entrypoint
    assert '[[ ! -s "$RAILWAY_CREDS_DIR/config.json" ]]' in entrypoint
    assert "railway login" not in entrypoint
    assert "RAILWAY_TOKEN=" not in entrypoint
    assert "RAILWAY_API_TOKEN=" not in entrypoint
    syntax = subprocess.run(
        ["bash", "-n"],
        input=entrypoint,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_resident_self_heal_starts_the_production_bot_boundary() -> None:
    ensure_script = (
        Path(__file__).parents[2]
        / "arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident"
    ).read_text()

    assert "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE" in ensure_script
    assert "MEGAPLAN_RESIDENT_MODE:-production" in ensure_script
    assert "MEGAPLAN_RESIDENT_STORE_ROOT" in ensure_script
    assert "MEGAPLAN_RUNTIME_PYTHON" in ensure_script
    assert 'exec \\"\\$runtime_python\\" -P -m arnold_pipelines.megaplan resident discord' in ensure_script
    assert '"$runtime_python" -P -m arnold_pipelines.megaplan resident health' in ensure_script
    assert "--store-root" in ensure_script
    assert "/workspace/.megaplan/resident-runtime.env" in ensure_script
    assert ensure_script.index("/workspace/.cloud-hot-env") < ensure_script.index(
        "/workspace/.megaplan/resident-runtime.env"
    )
    assert 'readlink -f "/proc/$pane_pid/exe"' in ensure_script
    assert '"MEGAPLAN_RUNTIME_SRC=$runtime_src"' in ensure_script
    assert '"MEGAPLAN_RUNTIME_PYTHON=$runtime_python"' in ensure_script
