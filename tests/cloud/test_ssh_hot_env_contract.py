"""Focused tests for the canonical SSH deploy hot-env contract."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from arnold.workflow.effect_protocol import EffectProtocol
from arnold_pipelines.megaplan.cloud.hot_env import HOT_ENV_INSTALL_SCRIPT
from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.cloud.ssh_effect_adapter import SshEffectAdapter
from arnold_pipelines.megaplan.custody.action_validator import GateResult
from arnold_pipelines.megaplan.types import CliError


def _adapter() -> SshEffectAdapter:
    protocol = MagicMock(spec=EffectProtocol)
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-hot-env-test"
    protocol.reserve_and_start.return_value = reservation

    class FenceBypassAdapter(SshEffectAdapter):
        def _check_stale_fence(self, target, fence_token):
            return True

    return FenceBypassAdapter(
        protocol,
        action_gate_check=lambda _boundary, _target_key: GateResult.AUTHORIZED,
        production_enabled=False,
    )


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://example.invalid/repo.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="example.invalid"),
    )


class CaptureDeploy(SshProvider):
    def __init__(self, spec: CloudSpec, *, fail_hot_env: bool = False) -> None:
        super().__init__(spec, ssh_effect_adapter=_adapter())
        self.calls: list[tuple[str, str, str | None]] = []
        self.fail_hot_env = fail_hot_env

    def _remote_run(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str = "remote_command",
        raise_on_failure: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, raise_on_failure
        self.calls.append((surface, command, input))
        return subprocess.CompletedProcess(
            args=[command],
            returncode=1 if self.fail_hot_env and surface == "deploy_cloud_hot_env" else 0,
            stdout="",
            stderr="",
        )


def test_deploy_hot_env_is_credentials_only_and_mode_600() -> None:
    provider = CaptureDeploy(_spec())

    assert provider.deploy(Path("/tmp/deploy"), secrets={"OPENAI_API_KEY": "sk-test"}) == 0

    hot_calls = [item for item in provider.calls if item[0] == "deploy_cloud_hot_env"]
    assert len(hot_calls) == 1
    _, command, payload = hot_calls[0]
    assert "docker exec -i megaplan-cloud-agent" in command
    assert payload == "export OPENAI_API_KEY=sk-test\n"
    assert "/workspace/.cloud-hot-env" in HOT_ENV_INSTALL_SCRIPT
    assert "0o600" in HOT_ENV_INSTALL_SCRIPT
    assert "O_NOFOLLOW" in HOT_ENV_INSTALL_SCRIPT


@pytest.mark.parametrize(
    "name",
    [
        "MEGAPLAN_RUNTIME_SRC",
        "MEGAPLAN_RUNTIME_MODEL",
        "CLOUD_WATCHDOG_SYNC_ENABLED",
        "MEGAPLAN_RESIDENT_MODE",
    ],
)
def test_deploy_rejects_forbidden_hot_env_names_before_mutation(name: str) -> None:
    provider = CaptureDeploy(_spec())

    with pytest.raises(CliError) as caught:
        provider.deploy(
            Path("/tmp/deploy"),
            secrets={name: "/workspace/stale"},
        )

    assert caught.value.code == "cloud_hot_env_rejected"
    assert provider.calls == []


def test_deploy_fails_closed_when_hot_env_verification_fails() -> None:
    provider = CaptureDeploy(_spec(), fail_hot_env=True)

    with pytest.raises(CliError) as caught:
        provider.deploy(Path("/tmp/deploy"), secrets={"GITHUB_TOKEN": "gh-secret"})

    # The WBC adapter wraps mutation failures in the provider_failed boundary
    # while retaining the fail-closed detail.
    assert caught.value.code == "provider_failed"
    assert "installation or verification failed" in caught.value.message
    assert [surface for surface, _, _ in provider.calls][-1] == (
        "deploy_cloud_hot_env_fail_closed_stop"
    )
    hot_index = next(
        index
        for index, (surface, _, _) in enumerate(provider.calls)
        if surface == "deploy_cloud_hot_env"
    )
    assert not any(
        "docker rm" in command
        for _, command, _ in provider.calls[hot_index + 1 :]
    )


def test_deploy_does_not_print_secret_and_orders_install_after_start(capsys) -> None:
    provider = CaptureDeploy(_spec())
    secret = "super-secret-token"

    provider.deploy(Path("/tmp/deploy"), secrets={"GITHUB_TOKEN": secret})

    output = capsys.readouterr()
    assert secret not in output.out
    assert secret not in output.err
    surfaces = [surface for surface, _, _ in provider.calls]
    assert surfaces.index("deploy_run") < surfaces.index("deploy_cloud_hot_env")


@pytest.mark.parametrize("value", ["secret\nMODEL=gpt-5.5", "secret\r\nMEGAPLAN_RUNTIME_SRC=/tmp/stale"])
def test_deploy_rejects_dotenv_record_separator_before_mutation(value: str) -> None:
    provider = CaptureDeploy(_spec())

    with pytest.raises(CliError) as caught:
        provider.deploy(Path("/tmp/deploy"), secrets={"OPENAI_API_KEY": value})

    assert caught.value.code == "cloud_hot_env_rejected"
    assert provider.calls == []
