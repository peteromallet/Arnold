"""Fail-closed tests for the SSH isolated chain-runner boot profile."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.providers.ssh import (
    SshProvider,
    _ISOLATED_CHAIN_RUNNER_COMMAND,
    _ISOLATED_CHAIN_RUNNER_ENTRYPOINT,
)
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
    load_spec,
)
from arnold_pipelines.megaplan.cloud.template import render_entrypoint
from arnold_pipelines.megaplan.types import CliError


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
            "Status": "running",
            "Running": True,
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

    provider = CaptureSshProvider(_spec())
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


def test_isolated_deploy_existing_name_fails_without_stop_remove_or_run() -> None:
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
            raise AssertionError(f"unexpected mutation after collision: {command}")

        def _sync_deploy_dir(self, deploy_dir: Path) -> None:
            del deploy_dir

    with pytest.raises(CliError, match="target exists"):
        CollisionProvider(
            _spec(isolated_chain_runner_image_id=image_id)
        ).deploy(Path("/tmp/deploy"), secrets={})

    assert len(commands) == 2
    assert commands[0].startswith("docker image inspect")
    assert not any("docker rm" in command for command in commands)
    assert not any(command.startswith("docker run") for command in commands)


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
        _spec(isolated_chain_runner_image_id=image_id)
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

    provider = IdTargetProvider(_spec())
    provider.attest_isolated_chain_runner_runtime()
    provider.ssh_exec("true")
    assert remote_commands == [f"docker exec {container_id} bash -lc true"]
    assert "isolated-chain-runner" not in remote_commands[0]


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
