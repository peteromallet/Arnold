"""Fail-closed tests for the SSH isolated chain-runner boot profile."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from arnold.workflow.effect_protocol import EffectProtocol

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.providers.ssh import (
    SshProvider,
    _ISOLATED_GH_AUTH_ATTEST_SCRIPT,
    _ISOLATED_GIT_CREDENTIAL_INSTALL_SCRIPT,
    _ISOLATED_CHAIN_RUNNER_COMMAND,
    _ISOLATED_CHAIN_RUNNER_ENTRYPOINT,
)
from arnold_pipelines.megaplan.cloud.auth import seed_isolated_git_credentials
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
    load_spec,
)
from arnold_pipelines.megaplan.cloud.ssh_effect_adapter import SshEffectAdapter
from arnold_pipelines.megaplan.cloud.template import render_entrypoint
from arnold_pipelines.megaplan.custody.action_validator import GateResult
from arnold_pipelines.megaplan.types import CliError


def _authorized_effect_adapter() -> SshEffectAdapter:
    """Real adapter with an explicit authorized gate and a bypassed stale
    fence, so isolated deploy command capture runs through the actual WBC
    route (SSH mutations are otherwise action-off)."""
    protocol = MagicMock(spec=EffectProtocol)
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-isolated-deploy"
    protocol.reserve_and_start.return_value = reservation

    class FenceBypassAdapter(SshEffectAdapter):
        def _check_stale_fence(self, target, fence_token):
            return True

    return FenceBypassAdapter(
        protocol,
        action_gate_check=lambda _boundary, _target_key: GateResult.AUTHORIZED,
        production_enabled=False,
    )


def _spec(**overrides: object) -> CloudSpec:
    values: dict[str, object] = {
        "provider": "ssh",
        "repo": RepoSpec(
            url="https://github.com/example/app.git",
            workspace="/workspace/app",
        ),
        "agents": {"default": "codex"},
        "codex": CodexSpec(),
        "mode": "idle",
        "megaplan": MegaplanSpec(),
        "resources": ResourcesSpec(),
        "secrets": [],
        "ssh": SshSpec(host="testhost", container="isolated-chain-runner"),
        "isolated_chain_runner": True,
        "isolated_chain_runner_image_id": "sha256:" + "a" * 64,
    }
    values.update(overrides)
    return CloudSpec(**values)  # type: ignore[arg-type]


def _yaml(*, provider: str = "ssh", mode: str = "idle", flag: str = "true") -> str:
    provider_block = "ssh:\n  host: testhost\n" if provider == "ssh" else ""
    return (
        f"provider: {provider}\n"
        f"mode: {mode}\n"
        f"isolated_chain_runner: {flag}\n"
        f"isolated_chain_runner_image_id: sha256:{'a' * 64}\n"
        "repo:\n"
        "  url: https://github.com/example/app.git\n"
        "  workspace: /workspace/app\n"
        f"{provider_block}"
        "secrets: []\n"
    )


def _runtime_mounts(*extra: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "Type": "bind",
            "Source": "/opt/megaplan-cloud/workspace",
            "Destination": "/workspace",
            "RW": True,
        },
        {
            "Type": "bind",
            "Source": "/opt/megaplan-cloud/cache/pip",
            "Destination": "/root/.cache/pip",
            "RW": True,
        },
        {
            "Type": "bind",
            "Source": "/opt/megaplan-cloud/cache/npm",
            "Destination": "/root/.npm",
            "RW": True,
        },
        *extra,
    ]


_IMAGE_ENV = ["PATH=/usr/local/bin:/usr/bin:/bin"]


def _runtime_env(*extra: str) -> list[str]:
    return [
        *_IMAGE_ENV,
        "PORT=8080",
        "MEGAPLAN_ISOLATED_CHAIN_RUNNER=1",
        *extra,
    ]


def _runtime_fields(
    image_id: str,
    *,
    container_id: str,
    state_status: str = "running",
    running: bool = True,
    env: list[str] | None = None,
    mounts: list[dict[str, object]] | None = None,
    entrypoint: list[str] | None = None,
    command: list[str] | None = None,
    privileged: bool = False,
    devices: list[object] | None = None,
    device_requests: list[object] | None = None,
    healthcheck: dict[str, object] | None = None,
) -> list[object]:
    return [
        {
            "Status": state_status,
            "Running": running,
            "Paused": False,
            "Restarting": False,
        },
        _runtime_env() if env is None else env,
        [_ISOLATED_CHAIN_RUNNER_ENTRYPOINT] if entrypoint is None else entrypoint,
        list(_ISOLATED_CHAIN_RUNNER_COMMAND) if command is None else command,
        image_id,
        image_id,
        {"Name": "unless-stopped", "MaximumRetryCount": 0},
        _runtime_mounts() if mounts is None else mounts,
        container_id,
        privileged,
        [] if devices is None else devices,
        [] if device_requests is None else device_requests,
        ["ALL"],
        ["CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL", "SETGID", "SETUID"],
        ["no-new-privileges:true"],
        "bridge",
        "",
        "private",
        True,
        1024,
        8 * 1024 * 1024 * 1024,
        8 * 1024 * 1024 * 1024,
        {"8080/tcp": [{"HostIp": "", "HostPort": "8080"}]},
        {"Test": ["NONE"]} if healthcheck is None else healthcheck,
    ]


def test_isolated_chain_runner_spec_accepts_only_ssh_idle(tmp_path: Path) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")

    spec = load_spec(cloud_yaml)

    assert spec.provider == "ssh"
    assert spec.mode == "idle"
    assert spec.isolated_chain_runner is True


@pytest.mark.parametrize(
    ("provider", "mode"),
    [("local", "idle"), ("ssh", "auto"), ("ssh", "chain")],
)
def test_isolated_chain_runner_rejects_other_profiles(
    tmp_path: Path,
    provider: str,
    mode: str,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        _yaml(provider=provider, mode=mode),
        encoding="utf-8",
    )

    with pytest.raises(
        CliError,
        match=r"isolated_chain_runner: true.*provider: ssh.*mode: idle",
    ):
        load_spec(cloud_yaml)


def test_isolated_chain_runner_flag_is_strict_boolean(tmp_path: Path) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(flag="1"), encoding="utf-8")

    with pytest.raises(CliError, match="must be a boolean"):
        load_spec(cloud_yaml)


def test_isolated_chain_runner_requires_empty_startup_secrets(tmp_path: Path) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        _yaml().replace("secrets: []", "secrets: [BASH_ENV]"),
        encoding="utf-8",
    )

    with pytest.raises(CliError, match=r"requires `secrets: \[\]`"):
        load_spec(cloud_yaml)


def test_isolated_image_pin_must_be_exact_sha256(tmp_path: Path) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        _yaml().replace("sha256:" + "a" * 64, "isolated:latest"),
        encoding="utf-8",
    )
    with pytest.raises(CliError, match="exact sha256 image ID"):
        load_spec(cloud_yaml)


def test_isolated_deploy_requires_pin_before_provider_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        "\n".join(
            line
            for line in _yaml().splitlines()
            if not line.startswith("isolated_chain_runner_image_id:")
        )
        + "\n",
        encoding="utf-8",
    )
    provider_called = False

    def provider(*args, **kwargs):
        nonlocal provider_called
        del args, kwargs
        provider_called = True
        raise AssertionError("unpinned deploy must not create a provider")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    result = cloud_cli.run_cloud_cli(
        tmp_path,
        argparse.Namespace(cloud_action="deploy", cloud_yaml=str(cloud_yaml)),
    )
    assert result == 1
    assert provider_called is False


def test_isolated_chain_runner_and_zero_recovery_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        _yaml()
        + "zero_recovery_canary: true\n"
        + "zero_recovery_predecessor_container: predecessor\n"
        + "zero_recovery_workspace_dir: /opt/megaplan-cloud/workspace/canary\n",
        encoding="utf-8",
    )

    with pytest.raises(CliError, match="mutually exclusive"):
        load_spec(cloud_yaml)


def test_isolated_entrypoint_is_marker_gated_healthserver_only() -> None:
    rendered = render_entrypoint(_spec())

    assert '"${MEGAPLAN_ISOLATED_CHAIN_RUNNER:-}" != "1"' in rendered
    assert "exit 64" in rendered
    assert rendered.rstrip().endswith(
        "exec python3 /usr/local/bin/healthserver.py"
    )
    for forbidden in (
        "tmux",
        "heartbeat",
        "watchdog",
        "progress-auditor",
        "progress auditor",
        "repair-loop",
        "repair loop",
        "meta-repair",
        "resident",
        "discord",
        "notification",
        "sweep",
        "chain start",
        "bash -l",
        "agent session",
    ):
        assert forbidden not in rendered.lower()


def test_isolated_entrypoint_refuses_boot_without_exact_marker(tmp_path: Path) -> None:
    entrypoint = tmp_path / "entrypoint.sh"
    entrypoint.write_text(render_entrypoint(_spec()), encoding="utf-8")

    result = subprocess.run(
        ["bash", str(entrypoint)],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 64
    assert "MEGAPLAN_ISOLATED_CHAIN_RUNNER=1" in result.stderr


def test_normal_and_zero_recovery_entrypoint_routes_are_unchanged() -> None:
    normal = replace(
        _spec(),
        isolated_chain_runner=False,
        isolated_chain_runner_image_id=None,
    )
    zero = replace(normal, zero_recovery_canary=True)

    normal_entrypoint = render_entrypoint(normal)
    zero_entrypoint = render_entrypoint(zero)

    assert "tmux new-session" in normal_entrypoint
    assert "arnold-watchdog" in normal_entrypoint
    assert zero_entrypoint == """#!/usr/bin/env bash
set -euo pipefail

if [[ "${MEGAPLAN_ZERO_RECOVERY_CANARY:-}" != "1" ]]; then
  echo "zero-recovery canary requires MEGAPLAN_ZERO_RECOVERY_CANARY=1" >&2
  exit 64
fi
export MEGAPLAN_ZERO_RECOVERY_CANARY=1
exec python3 /usr/local/bin/healthserver.py
"""


def test_stale_normal_image_is_forced_through_fixed_isolated_boot_command() -> None:
    commands: list[str] = []
    stale_image_id = "sha256:" + "a" * 64
    container_id = "b" * 64

    class CaptureSshProvider(SshProvider):
        def observe_container(self):
            if any(command.startswith("docker run") for command in commands):
                return {
                    "status": "available",
                    "lifecycle": "running",
                    "container_id": container_id,
                }
            return {"status": "available", "lifecycle": "missing"}

        def _remote_run_compatible(
            self,
            command: str,
            *,
            capture_output: bool = True,
            input: str | None = None,
            surface: str,
        ):
            del capture_output, input, surface
            commands.append(command)
            from subprocess import CompletedProcess

            if command.startswith("docker image inspect"):
                payload: object = (
                    _IMAGE_ENV if ".Config.Env" in command else stale_image_id
                )
                return CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(payload) + "\n",
                    stderr="",
                )
            if command.startswith("docker inspect --type=container"):
                fields = _runtime_fields(
                    stale_image_id, container_id=container_id
                )
                return CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                    stderr="",
                )
            return CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        def _sync_deploy_dir(self, deploy_dir: Path) -> None:
            del deploy_dir

    provider = CaptureSshProvider(
        _spec(),
        ssh_effect_adapter=_authorized_effect_adapter(),
    )
    assert provider.deploy(Path("/tmp/deploy"), secrets={}) == 0

    combined = "\n".join(commands)
    docker_run = next(command for command in commands if command.startswith("docker run"))
    argv = shlex.split(docker_run)
    assert "MEGAPLAN_ISOLATED_CHAIN_RUNNER=1" in combined
    assert docker_run.count("-e MEGAPLAN_ISOLATED_CHAIN_RUNNER=1") == 1
    assert "MEGAPLAN_ZERO_RECOVERY_CANARY" not in docker_run
    assert "--restart unless-stopped" in docker_run
    for required in (
        "--no-healthcheck",
        "--init",
        "--cap-drop ALL",
        "--security-opt no-new-privileges:true",
        "--network bridge",
        "--ipc private",
        "--pids-limit 1024",
        "--memory 8g",
        "--memory-swap 8g",
    ):
        assert required in docker_run
    assert argv[argv.index("--entrypoint") + 1] == _ISOLATED_CHAIN_RUNNER_ENTRYPOINT
    assert _ISOLATED_CHAIN_RUNNER_ENTRYPOINT.endswith("/bin/python3")
    assert _ISOLATED_CHAIN_RUNNER_COMMAND[:3] == ("-I", "-S", "-c")
    compile(_ISOLATED_CHAIN_RUNNER_COMMAND[3], "<isolated-healthserver>", "exec")
    assert "BASH_ENV" not in _ISOLATED_CHAIN_RUNNER_COMMAND[3]
    assert "/usr/local/bin/healthserver.py" not in _ISOLATED_CHAIN_RUNNER_COMMAND[3]
    assert stale_image_id in argv
    assert argv[argv.index(stale_image_id) + 1 :] == list(
        _ISOLATED_CHAIN_RUNNER_COMMAND
    )
    observation = provider._isolated_chain_runner_deploy_observation
    assert observation["container_id"] == container_id
    assert observation["image_id"] == stale_image_id
    assert observation["entrypoint"] == [_ISOLATED_CHAIN_RUNNER_ENTRYPOINT]
    assert observation["command"] == list(_ISOLATED_CHAIN_RUNNER_COMMAND)
    assert observation["host_config"]["privileged"] is False
    assert observation["host_config"]["healthcheck"] == {"Test": ["NONE"]}


def test_isolated_deploy_rejects_stopped_mismatched_identity_without_mutation() -> None:
    commands: list[str] = []
    image_id = "sha256:" + "e" * 64

    class CollisionProvider(SshProvider):
        def observe_container(self):
            return {
                "status": "available",
                "lifecycle": "stopped",
                "container_id": "f" * 64,
            }

        def _remote_run_compatible(
            self,
            command: str,
            *,
            capture_output: bool = True,
            input: str | None = None,
            surface: str,
        ):
            del capture_output, input, surface
            commands.append(command)
            if command.startswith("docker image inspect"):
                payload: object = _IMAGE_ENV if ".Config.Env" in command else image_id
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(payload) + "\n",
                    stderr="",
                )
            if command.startswith("docker inspect --type=container"):
                fields = _runtime_fields(
                    "sha256:" + "d" * 64,
                    container_id="f" * 64,
                    state_status="exited",
                    running=False,
                )
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected mutation after collision: {command}")

        def _sync_deploy_dir(self, deploy_dir: Path) -> None:
            del deploy_dir

    with pytest.raises(CliError, match="mismatched"):
        CollisionProvider(
            _spec(isolated_chain_runner_image_id=image_id),
            ssh_effect_adapter=_authorized_effect_adapter(),
        ).deploy(Path("/tmp/deploy"), secrets={})

    assert len(commands) == 3
    assert commands[0].startswith("docker image inspect")
    assert not any("docker rm" in command for command in commands)
    assert not any("docker start" in command for command in commands)
    assert not any(command.startswith("docker run") for command in commands)


def test_isolated_deploy_recovers_exact_stopped_identity_in_place() -> None:
    commands: list[str] = []
    image_id = "sha256:" + "9" * 64
    container_id = "8" * 64
    lifecycle = {"value": "stopped"}

    class RecoverStoppedProvider(SshProvider):
        def observe_container(self):
            if lifecycle["value"] == "stopped":
                return {
                    "status": "available",
                    "lifecycle": "stopped",
                    "container_id": container_id,
                }
            return {
                "status": "available",
                "lifecycle": "running",
                "container_id": container_id,
            }

        def _remote_run_compatible(
            self,
            command: str,
            *,
            capture_output: bool = True,
            input: str | None = None,
            surface: str,
        ):
            del capture_output, input, surface
            commands.append(command)
            if command.startswith("docker image inspect"):
                payload: object = _IMAGE_ENV if ".Config.Env" in command else image_id
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(payload) + "\n",
                    stderr="",
                )
            if command.startswith("docker inspect --type=container"):
                fields = _runtime_fields(
                    image_id,
                    container_id=container_id,
                    state_status=("exited" if lifecycle["value"] == "stopped" else "running"),
                    running=lifecycle["value"] == "running",
                )
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                    stderr="",
                )
            if command == f"docker start {container_id}":
                lifecycle["value"] = "running"
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected provider command: {command}")

        def _sync_deploy_dir(self, deploy_dir: Path) -> None:
            del deploy_dir

    provider = RecoverStoppedProvider(
        _spec(isolated_chain_runner_image_id=image_id),
        ssh_effect_adapter=_authorized_effect_adapter(),
    )
    assert provider.deploy(Path("/tmp/deploy"), secrets={}) == 0

    assert sum(command.startswith("docker start ") for command in commands) == 1
    assert f"docker start {container_id}" in commands
    assert not any(command.startswith("docker run") for command in commands)
    assert not any("docker rm" in command for command in commands)
    assert provider._isolated_chain_runner_deploy_observation["lifecycle"] == "running"


def test_isolated_redeploy_accepts_only_exact_running_attestation_without_mutation() -> None:
    commands: list[str] = []
    image_id = "sha256:" + "1" * 64

    class IdempotentProvider(SshProvider):
        def observe_container(self):
            return {
                "status": "available",
                "lifecycle": "running",
                "container_id": "2" * 64,
            }

        def _remote_run_compatible(
            self,
            command: str,
            *,
            capture_output: bool = True,
            input: str | None = None,
            surface: str,
        ):
            del capture_output, input, surface
            commands.append(command)
            if command.startswith("docker image inspect"):
                payload: object = _IMAGE_ENV if ".Config.Env" in command else image_id
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(payload) + "\n",
                    stderr="",
                )
            if command.startswith("docker inspect --type=container"):
                fields = _runtime_fields(image_id, container_id="2" * 64)
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected redeploy mutation: {command}")

        def _sync_deploy_dir(self, deploy_dir: Path) -> None:
            del deploy_dir

    assert IdempotentProvider(
        _spec(isolated_chain_runner_image_id=image_id),
        ssh_effect_adapter=_authorized_effect_adapter(),
    ).deploy(Path("/tmp/deploy"), secrets={}) == 0
    assert len(commands) == 5
    assert not any("docker rm" in command for command in commands)
    assert not any(command.startswith("docker run") for command in commands)


def test_isolated_runtime_rejects_stale_baked_entrypoint_observation() -> None:
    image_id = "sha256:" + "c" * 64

    class StaleEntrypointProvider(SshProvider):
        def _remote_run_compatible(self, *args, **kwargs):
            del args, kwargs
            from subprocess import CompletedProcess

            fields = _runtime_fields(
                image_id,
                container_id="d" * 64,
                entrypoint=["/usr/local/bin/entrypoint.sh"],
                command=[],
            )
            return CompletedProcess(
                args=[],
                returncode=0,
                stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                stderr="",
            )

    provider = StaleEntrypointProvider(_spec())
    provider._isolated_chain_runner_image_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
    }
    with pytest.raises(CliError) as exc_info:
        provider._observe_isolated_chain_runner_runtime(
            expected_image_id=image_id,
            target="d" * 64,
        )
    assert exc_info.value.code == "isolated_chain_runner_runtime_mismatch"


def test_isolated_image_rejects_bash_env_before_first_container_process() -> None:
    commands: list[str] = []
    image_id = "sha256:" + "3" * 64

    class BashEnvImageProvider(SshProvider):
        def _remote_run_compatible(self, command: str, **kwargs):
            del kwargs
            commands.append(command)
            payload: object = (
                [*_IMAGE_ENV, "BASH_ENV=/workspace/hook"]
                if ".Config.Env" in command
                else image_id
            )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(payload) + "\n", stderr=""
            )

    with pytest.raises(CliError) as exc_info:
        BashEnvImageProvider(
            _spec(isolated_chain_runner_image_id=image_id)
        )._resolve_isolated_chain_runner_image_id()

    assert exc_info.value.code == "isolated_chain_runner_image_env_rejected"
    assert len(commands) == 2
    assert not any(command.startswith("docker run") for command in commands)


def test_isolated_runtime_rejects_extra_mount_shadowing_python() -> None:
    image_id = "sha256:" + "4" * 64
    shadow = {
        "Type": "bind",
        "Source": "/opt/megaplan-cloud/workspace/hostile-python",
        "Destination": _ISOLATED_CHAIN_RUNNER_ENTRYPOINT,
        "RW": True,
    }

    class ShadowMountProvider(SshProvider):
        def _remote_run_compatible(self, *args, **kwargs):
            del args, kwargs
            fields = _runtime_fields(
                image_id,
                container_id="5" * 64,
                mounts=_runtime_mounts(shadow),
            )
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                stderr="",
            )

    provider = ShadowMountProvider(_spec())
    provider._isolated_chain_runner_image_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
    }
    with pytest.raises(CliError) as exc_info:
        provider._observe_isolated_chain_runner_runtime(
            expected_image_id=image_id,
            target="5" * 64,
        )
    assert exc_info.value.code == "isolated_chain_runner_runtime_mismatch"


@pytest.mark.parametrize(
    "field_overrides",
    [
        {"privileged": True},
        {"devices": [{"PathOnHost": "/dev/kvm"}]},
        {"device_requests": [{"Driver": "nvidia"}]},
        {"healthcheck": {"Test": ["CMD-SHELL", "hostile"]}},
    ],
)
def test_isolated_runtime_rejects_unsafe_host_config(
    field_overrides: dict[str, object],
) -> None:
    image_id = "sha256:" + "6" * 64

    class UnsafeHostProvider(SshProvider):
        def _remote_run_compatible(self, *args, **kwargs):
            del args, kwargs
            fields = _runtime_fields(
                image_id,
                container_id="7" * 64,
                **field_overrides,
            )
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                stderr="",
            )

    provider = UnsafeHostProvider(_spec())
    provider._isolated_chain_runner_image_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin"
    }
    with pytest.raises(CliError) as exc_info:
        provider._observe_isolated_chain_runner_runtime(
            expected_image_id=image_id,
            target="7" * 64,
        )
    assert exc_info.value.code == "isolated_chain_runner_runtime_mismatch"


def test_isolated_python_argv_disables_site_pth_loading() -> None:
    assert _ISOLATED_CHAIN_RUNNER_COMMAND[:3] == ("-I", "-S", "-c")
    assert all("site" not in item.lower() for item in _ISOLATED_CHAIN_RUNNER_COMMAND)
    assert all(".pth" not in item.lower() for item in _ISOLATED_CHAIN_RUNNER_COMMAND)


def test_isolated_attestation_rejects_name_swap_and_never_targets_replacement() -> None:
    image_id = "sha256:" + "a" * 64
    original_id = "8" * 64
    replacement_id = "9" * 64
    observe_count = 0
    commands: list[str] = []

    class NameSwapProvider(SshProvider):
        def observe_container(self):
            nonlocal observe_count
            observe_count += 1
            return {
                "status": "available",
                "lifecycle": "running",
                "container_id": original_id if observe_count == 1 else replacement_id,
            }

        def _remote_run_compatible(self, command: str, **kwargs):
            del kwargs
            commands.append(command)
            if command.startswith("docker image inspect"):
                payload: object = _IMAGE_ENV if ".Config.Env" in command else image_id
            else:
                assert original_id in command
                assert "isolated-chain-runner" not in command
                payload = None
                fields = _runtime_fields(image_id, container_id=original_id)
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(payload) + "\n", stderr=""
            )

    provider = NameSwapProvider(_spec())
    with pytest.raises(CliError) as exc_info:
        provider.attest_isolated_chain_runner_runtime()
    assert exc_info.value.code == "isolated_chain_runner_name_replaced"
    assert replacement_id not in "\n".join(commands)
    with pytest.raises(CliError) as io_exc:
        provider._container_io_target()
    assert io_exc.value.code == "isolated_chain_runner_attestation_required"


def test_isolated_exec_targets_attested_container_id_not_mutable_name() -> None:
    image_id = "sha256:" + "a" * 64
    container_id = "b" * 64
    remote_commands: list[str] = []

    class IdTargetProvider(SshProvider):
        def observe_container(self):
            return {
                "status": "available",
                "lifecycle": "running",
                "container_id": container_id,
            }

        def _remote_run_compatible(self, command: str, **kwargs):
            del kwargs
            if command.startswith("docker image inspect"):
                payload: object = _IMAGE_ENV if ".Config.Env" in command else image_id
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout=json.dumps(payload) + "\n", stderr=""
                )
            fields = _runtime_fields(image_id, container_id=container_id)
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="\n".join(json.dumps(field) for field in fields) + "\n",
                stderr="",
            )

        def _remote_run(self, command: str, **kwargs):
            del kwargs
            remote_commands.append(command)
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    provider = IdTargetProvider(
        _spec(), ssh_effect_adapter=_authorized_effect_adapter()
    )
    provider.attest_isolated_chain_runner_runtime()
    provider.ssh_exec("true")
    assert remote_commands == [f"docker exec {container_id} bash -lc true"]
    assert "isolated-chain-runner" not in remote_commands[0]


def test_isolated_git_auth_uses_stdin_exact_id_and_nonsecret_receipt() -> None:
    token = "ghp_adversarial_secret_value"
    container_id = "c" * 64
    calls: list[tuple[str, str | None, str]] = []

    class CredentialProvider(SshProvider):
        def attest_isolated_chain_runner_runtime(self):
            self._isolated_chain_runner_container_id = container_id
            return {"status": "available", "container_id": container_id}

        def _remote_run_compatible(
            self,
            command: str,
            *,
            capture_output: bool = True,
            input: str | None = None,
            surface: str,
        ):
            del capture_output
            calls.append((command, input, surface))
            stdout = ""
            if surface == "isolated_chain_runner_git_auth_seed":
                stdout = json.dumps(
                    {
                        "schema": "arnold.cloud.isolated_chain_runner_git_auth.v1",
                        "status": "seeded",
                        "credential_file_mode": "0600",
                        "config_file_mode": "0600",
                        "credential_scope": "github.com",
                        "credential_helper": "store",
                        "user_name": "Arnold Megaplan",
                        "user_email": "megaplan@arnold.invalid",
                    }
                )
            elif surface == "isolated_chain_runner_gh_auth_attest":
                stdout = json.dumps(
                    {
                        "schema": "arnold.cloud.isolated_chain_runner_gh_auth.v1",
                        "status": "authenticated",
                        "hostname": "github.com",
                        "config_file_mode": "0600",
                    }
                )
            return subprocess.CompletedProcess([], 0, stdout, "")

    receipt = CredentialProvider(_spec()).seed_isolated_chain_runner_git_credentials(
        token
    )

    assert receipt["status"] == "seeded"
    assert token not in json.dumps(receipt)
    assert receipt["user_name"] == "Arnold Megaplan"
    assert receipt["user_email"] == "megaplan@arnold.invalid"
    assert len(calls) == 4
    assert [surface for _, _, surface in calls] == [
        "isolated_chain_runner_git_auth_seed",
        "isolated_chain_runner_gh_auth_seed",
        "isolated_chain_runner_gh_auth_status",
        "isolated_chain_runner_gh_auth_attest",
    ]
    for command, stdin, _surface in calls:
        assert token not in command
        assert container_id in shlex.split(command)
        assert "isolated-chain-runner" not in command
        assert stdin == token if "_auth_seed" in _surface else stdin is None
    gh_login = shlex.split(calls[1][0])
    assert gh_login[-9:] == [
        "gh",
        "auth",
        "login",
        "--hostname",
        "github.com",
        "--git-protocol",
        "https",
        "--with-token",
        "--insecure-storage",
    ]


def test_isolated_git_auth_rejects_container_name_swap_after_seed() -> None:
    original_id = "d" * 64
    replacement_id = "e" * 64
    attestations = 0

    class SwapProvider(SshProvider):
        def attest_isolated_chain_runner_runtime(self):
            nonlocal attestations
            attestations += 1
            container_id = original_id if attestations == 1 else replacement_id
            self._isolated_chain_runner_container_id = container_id
            return {"status": "available", "container_id": container_id}

        def _remote_run_compatible(self, command: str, **kwargs):
            surface = kwargs["surface"]
            assert original_id in command
            assert replacement_id not in command
            stdout = ""
            if surface == "isolated_chain_runner_git_auth_seed":
                stdout = json.dumps(
                    {
                        "schema": "arnold.cloud.isolated_chain_runner_git_auth.v1",
                        "status": "seeded",
                        "credential_file_mode": "0600",
                        "config_file_mode": "0600",
                        "credential_scope": "github.com",
                        "credential_helper": "store",
                        "user_name": "Arnold Megaplan",
                        "user_email": "megaplan@arnold.invalid",
                    }
                )
            elif surface == "isolated_chain_runner_gh_auth_attest":
                stdout = json.dumps(
                    {
                        "schema": "arnold.cloud.isolated_chain_runner_gh_auth.v1",
                        "status": "authenticated",
                        "hostname": "github.com",
                        "config_file_mode": "0600",
                    }
                )
            return subprocess.CompletedProcess([], 0, stdout, "")

    with pytest.raises(CliError) as exc_info:
        SwapProvider(_spec()).seed_isolated_chain_runner_git_credentials(
            "ghp_secret"
        )
    assert exc_info.value.code == "isolated_chain_runner_name_replaced"


def test_isolated_git_installer_atomic_modes_replacement_and_no_token_output(
    tmp_path: Path,
) -> None:
    home = tmp_path / "root"
    home.mkdir(mode=0o700)
    script = _ISOLATED_GIT_CREDENTIAL_INSTALL_SCRIPT.replace(
        'if home != "/root":', f'if home != {str(home)!r}:'
    )
    uid, gid = os.getuid(), os.getgid()
    script = script.replace(
        "current.st_uid != 0 or current.st_gid != 0",
        f"current.st_uid != {uid} or current.st_gid != {gid}",
    ).replace(
        "existing.st_uid != 0\n            or existing.st_gid != 0",
        f"existing.st_uid != {uid}\n            or existing.st_gid != {gid}",
    ).replace(
        "stale.st_uid != 0\n                or stale.st_gid != 0",
        f"stale.st_uid != {uid}\n                or stale.st_gid != {gid}",
    ).replace(
        "os.fchown(fd, 0, 0)", f"os.fchown(fd, {uid}, {gid})"
    ).replace(
        "installed.st_uid != 0\n            or installed.st_gid != 0",
        f"installed.st_uid != {uid}\n            or installed.st_gid != {gid}",
    )
    token = "ghp_mode_test_secret"

    for _ in range(2):
        result = subprocess.run(
            ["python", "-I", "-S", "-c", script, str(home)],
            input=token,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        receipt = json.loads(result.stdout)
        assert receipt["user_name"] == "Arnold Megaplan"
        assert receipt["user_email"] == "megaplan@arnold.invalid"
        assert token not in result.stderr
        assert token not in result.stdout

    credential = home / ".config" / "megaplan" / "git-credentials"
    config = home / ".gitconfig"
    assert credential.stat().st_mode & 0o777 == 0o600
    assert config.stat().st_mode & 0o777 == 0o600
    assert credential.read_text() == (
        "https://x-access-token:ghp_mode_test_secret@github.com\n"
    )
    config_text = config.read_text()
    assert token not in config_text
    assert f"store --file {credential}" in config_text
    assert "name = Arnold Megaplan" in config_text
    assert "email = megaplan@arnold.invalid" in config_text
    assert not list(credential.parent.glob("*.isolated-new"))
    git_env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
    identity = subprocess.run(
        ["git", "config", "--global", "--get-regexp", r"^user\.(name|email)$"],
        env=git_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert identity.returncode == 0
    assert identity.stdout.splitlines() == [
        "user.name Arnold Megaplan",
        "user.email megaplan@arnold.invalid",
    ]
    credential_fill = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        env=git_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert credential_fill.returncode == 0
    assert "username=x-access-token" in credential_fill.stdout
    assert f"password={token}" in credential_fill.stdout
    gh_hosts = home / ".config" / "gh" / "hosts.yml"
    gh_hosts.write_text("github.com: {}\n", encoding="utf-8")
    gh_hosts.chmod(0o600)
    attest_script = (
        _ISOLATED_GH_AUTH_ATTEST_SCRIPT.replace(
            "/root/.config/gh/hosts.yml", str(gh_hosts)
        )
        .replace("/root/.gitconfig", str(config))
        .replace("/root/.config/megaplan/git-credentials", str(credential))
        .replace("current.st_uid != 0", f"current.st_uid != {uid}")
        .replace("current.st_gid != 0", f"current.st_gid != {gid}")
    )
    attest = subprocess.run(
        ["python", "-I", "-S", "-c", attest_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert attest.returncode == 0, attest.stderr
    assert json.loads(attest.stdout)["config_file_mode"] == "0600"


def test_isolated_git_seed_discovers_gh_without_token_in_argv_or_messages() -> None:
    token = "ghp_local_discovery_secret"
    observed: dict[str, object] = {}

    def runner(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, token + "\n", "")

    class Provider:
        def seed_isolated_chain_runner_git_credentials(self, value: str):
            assert value == token
            return {"status": "seeded"}

    messages: list[str] = []
    receipt = seed_isolated_git_credentials(
        _spec(),
        Provider(),
        required=True,
        runner=runner,
        writer=messages.append,
    )
    assert observed["argv"] == ["gh", "auth", "token"]
    assert token not in repr(observed["argv"])
    assert observed["kwargs"]["stdin"] is subprocess.DEVNULL
    assert token not in json.dumps(receipt)
    assert token not in "".join(messages)


def test_isolated_git_seed_failure_redaction_covers_stdin_only_token() -> None:
    provider = SshProvider(_spec())
    token = "ghp_failure_echo_secret"
    provider._ephemeral_redaction_values = (token,)
    redacted = provider._redact_failure_text(f"remote unexpectedly echoed {token}")
    assert token not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.parametrize(
    "action",
    ["chain", "preflight", "sync-megaplan", "status", "logs", "chains"],
)
def test_every_isolated_container_touch_attests_before_action_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")
    attestations: list[str] = []

    class Provider:
        def attest_isolated_chain_runner_runtime(self):
            attestations.append(action)
            raise CliError("isolated_chain_runner_not_deployed", "not deployed")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", lambda *_args: Provider())
    args = argparse.Namespace(
        cloud_action=action,
        cloud_yaml=str(cloud_yaml),
        on_box=False,
        fresh=True,
        prepare_only=False,
        skip_remote=False,
    )
    result = cloud_cli.run_cloud_cli(tmp_path, args)
    assert result == 1
    assert attestations == [action]


def test_direct_isolated_chain_without_deployment_fails_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")

    class MissingProvider:
        def attest_isolated_chain_runner_runtime(self):
            raise CliError("isolated_chain_runner_not_deployed", "not deployed")

    monkeypatch.setattr(
        cloud_cli, "_provider_for_action", lambda *_args: MissingProvider()
    )
    monkeypatch.setattr(
        cloud_cli,
        "_run_chain_wrapper",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("unattested chain must never launch")
        ),
    )
    result = cloud_cli.run_cloud_cli(
        tmp_path,
        argparse.Namespace(
            cloud_action="chain",
            cloud_yaml=str(cloud_yaml),
            on_box=False,
            fresh=True,
            prepare_only=False,
        ),
    )
    assert result == 1


_DENIED_ISOLATED_ACTIONS = (
    "init",
    "quickstart",
    "launch-epic",
    "epic-chain",
    "bootstrap",
    "attach",
    "exec",
    "resume",
    "pause-chain",
    "resume-chain",
    "retire-chain",
    "retire-stale-status",
    "supervise",
    "down",
    "destroy",
    "reclaim-dangling-build-cache",
    "run-zero-recovery-canary",
    "zero-recovery-canary-status",
    "zero-recovery-preflight",
)


@pytest.mark.parametrize("action", _DENIED_ISOLATED_ACTIONS)
def test_isolated_action_aliases_reject_before_provider_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")
    provider_called = False

    def provider(*args, **kwargs):
        nonlocal provider_called
        del args, kwargs
        provider_called = True
        raise AssertionError("denied action must not create a provider")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    monkeypatch.setattr(
        cloud_cli,
        "_run_init",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("denied init must not mutate the profile")
        ),
    )

    result = cloud_cli.run_cloud_cli(
        tmp_path,
        argparse.Namespace(cloud_action=action, cloud_yaml=str(cloud_yaml)),
    )

    assert result == 1
    assert provider_called is False


@pytest.mark.parametrize("action", ["chain", "sync-megaplan"])
def test_isolated_on_box_alias_rejects_before_provider_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")
    provider_called = False

    def provider(*args, **kwargs):
        nonlocal provider_called
        del args, kwargs
        provider_called = True
        raise AssertionError("on-box alias must not create a provider")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    result = cloud_cli.run_cloud_cli(
        tmp_path,
        argparse.Namespace(
            cloud_action=action,
            cloud_yaml=str(cloud_yaml),
            on_box=True,
            fresh=True,
            prepare_only=False,
        ),
    )

    assert result == 1
    assert provider_called is False


def test_isolated_chain_launch_requires_fresh_before_provider_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(_yaml(), encoding="utf-8")
    provider_called = False

    def provider(*args, **kwargs):
        nonlocal provider_called
        del args, kwargs
        provider_called = True
        raise AssertionError("non-fresh chain must not create a provider")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    result = cloud_cli.run_cloud_cli(
        tmp_path,
        argparse.Namespace(
            cloud_action="chain",
            cloud_yaml=str(cloud_yaml),
            on_box=False,
            fresh=False,
            prepare_only=False,
        ),
    )

    assert result == 1
    assert provider_called is False


def test_isolated_action_allowlist_contains_only_bounded_surfaces() -> None:
    assert cloud_cli._ISOLATED_CHAIN_RUNNER_CLOUD_ACTIONS == {
        "build",
        "deploy",
        "preflight",
        "sync-megaplan",
        "chain",
        "status",
        "logs",
        "chains",
        "capacity-inventory",
    }
