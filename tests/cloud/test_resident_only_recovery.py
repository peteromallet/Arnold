from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
from subprocess import CompletedProcess
import sys
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.cli import _register_cloud_subcommands
from arnold_pipelines.megaplan.cloud.providers.resident_recovery import (
    DOWN_SCHEMA,
    FENCE_SCHEMA,
    HEALTH_SCHEMA,
    RECOVER_SCHEMA,
    RESIDENT_ONLY_COMMAND,
    START_SCHEMA,
    parse_resident_down_receipt,
    parse_resident_recovery_receipt,
    resident_down_command,
    resident_custody_host_root,
    resident_only_container_name,
    resident_recover_command,
)
from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.resident.discord import (
    RESTART_RESIDENT_COMMAND,
    ResidentDiscordService,
    register_discord_application_commands,
)
from arnold_pipelines.megaplan.resident.cli import _require_discord_runtime_launch
from arnold_pipelines.megaplan.resident.listener_recovery import (
    LISTENER_RECOVERY_SEED_SCHEMA,
    _consume_recovery_seed_once,
)
from arnold_pipelines.megaplan.types import CliError


SOURCE_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
RESIDENT_IMAGE_ID = "sha256:" + "d" * 64
RESIDENT_ID = "c" * 64
WORKSPACE = "/opt/megaplan-cloud/workspace"
SOURCE = "megaplan-cloud-agent"
RUNTIME_PATH = "/workspace/.cloud-watchdog/runtime/arnold-current"
RUNTIME_COMMIT = "1" * 40
RUNTIME_TREE = "2" * 40
RUNTIME_PYTHON = "/usr/local/bin/python3.13"
RUNTIME_PYTHON_SHA256 = "3" * 64
RUNTIME_ARGS = {
    "expected_runtime_path": RUNTIME_PATH,
    "expected_runtime_commit": RUNTIME_COMMIT,
    "expected_runtime_tree": RUNTIME_TREE,
    "expected_runtime_python_path": RUNTIME_PYTHON,
    "expected_runtime_python_sha256": RUNTIME_PYTHON_SHA256,
}


def _emulate_root_custody_for_local_transaction(script: str) -> str:
    """Keep the integration deterministic on a non-root developer machine."""
    return script.replace(
        'if os.geteuid() != 0:\n    raise RuntimeError("resident_recovery_requires_root_custody")',
        "if False:\n    raise RuntimeError(\"resident_recovery_requires_root_custody\")",
    ).replace(
        'if os.geteuid() != 0:\n    raise RuntimeError("resident_down_requires_root_custody")',
        "if False:\n    raise RuntimeError(\"resident_down_requires_root_custody\")",
    ).replace(".st_uid != 0", ".st_uid != os.geteuid()")


def _relocate_custody_for_local_transaction(command: str, root: Path) -> str:
    argv = shlex.split(command)
    config = json.loads(base64.b64decode(argv[2], validate=True))
    config["custody_host_parent"] = str(root.parent)
    config["custody_host_root"] = str(root)
    argv[2] = base64.b64encode(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    return shlex.join(argv)


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(
            prelaunch_min_free_bytes=123,
            prelaunch_min_free_inodes=45,
            prelaunch_receipt_reserve_bytes=67,
        ),
        secrets=[],
        ssh=SshSpec(host="testhost", container=SOURCE, workspace_dir=WORKSPACE),
    )


def _source_observation(*, lifecycle: str = "stopped") -> dict[str, object]:
    return {
        "schema": "arnold.cloud.ssh_container_observation.v1",
        "status": "available",
        "lifecycle": lifecycle,
        "container_id": SOURCE_ID,
        "image_id": IMAGE_ID,
        "workspace_bind": {
            "status": "present",
            "type": "bind",
            "source": WORKSPACE,
            "destination": "/workspace",
            "rw": True,
        },
    }


def _recover_receipt(*, status: str = "healthy") -> dict[str, object]:
    resident = resident_only_container_name(SOURCE)
    fence = {
        "schema": FENCE_SCHEMA,
        "status": "fenced",
        "outage_epoch": "discord-enospc-20260803",
        "source_container": SOURCE,
        "source_container_id": SOURCE_ID,
        "source_image_id": IMAGE_ID,
        "workspace": WORKSPACE,
        "prior_restart_policy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
        "fence_intent_sha256": "a" * 64,
        "applied_restart_policy": {"Name": "no", "MaximumRetryCount": 0},
        "rollback_required": True,
    }
    start = {
        "schema": START_SCHEMA,
        "status": "started",
        "outage_epoch": "discord-enospc-20260803",
        "source_container": SOURCE,
        "source_container_id": SOURCE_ID,
        "source_image_id": IMAGE_ID,
        "resident_image_id": RESIDENT_IMAGE_ID,
        "workspace": WORKSPACE,
        "resident_container": resident,
        "resident_container_id": RESIDENT_ID,
        "resident_command_sha256": "d" * 64,
        "resident_env_sha256": "f" * 64,
        "intent_sha256": "9" * 64,
        "recovery_seed_sha256": "e" * 64,
        "runtime_path": RUNTIME_PATH,
        "runtime_commit": RUNTIME_COMMIT,
        "runtime_tree": RUNTIME_TREE,
        "runtime_python_path": RUNTIME_PYTHON,
        "runtime_python_sha256": RUNTIME_PYTHON_SHA256,
        "restart_policy": "no",
        "listener_only": True,
        "started_at": "2026-08-03T10:00:00.000000000Z",
    }
    health = {
        "schema": HEALTH_SCHEMA,
        "status": status,
        "reason": "discord_ready" if status == "healthy" else "readiness_timeout",
        "outage_epoch": "discord-enospc-20260803",
        "resident_container": resident,
        "resident_container_id": RESIDENT_ID,
        "listener_only": True,
        "resident_running": status == "healthy",
        "evidence_since": "2026-08-03T10:00:00.000000000Z",
    }
    return {
        "schema": RECOVER_SCHEMA,
        "status": status,
        "outage_epoch": "discord-enospc-20260803",
        "new_attempt": True,
        "source_fence_receipt": fence,
        "start_receipt": start,
        "health_receipt": health,
        "receipt_paths": {
            "fence_intent": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/transaction.fence.intent.json",
            "fence": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/transaction.fence.json",
            "intent": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/transaction.intent.json",
            "seed": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/seed/launch-seed.json",
            "start": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/transaction.start.json",
            "health": resident_custody_host_root(SOURCE_ID) + "/discord-enospc-20260803/transaction.health.json",
        },
    }


class _ResidentProvider(SshProvider):
    def __init__(self, *, observation=None, capacity=None, remote_payload=None):
        super().__init__(_spec())
        self.observation = observation or _source_observation()
        self.capacity = capacity or {"status": "go", "verdict": "GO"}
        self.remote_payload = remote_payload or _recover_receipt()
        self.effects: list[dict[str, object]] = []

    def observe_container(self):
        return self.observation

    def observe_prelaunch_capacity(self):
        return self.capacity

    def _remote_run(self, command, *, capture_output=True, input=None, surface="remote"):
        self.effects.append({"command": command, "input": input, "surface": surface})
        return CompletedProcess([], 0, json.dumps(self.remote_payload), "")


def test_recover_builder_contains_only_fixed_listener_process_and_no_secret_value() -> None:
    command, script = resident_recover_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        **RUNTIME_ARGS,
        workspace=WORKSPACE,
        outage_epoch="discord-enospc-20260803",
        min_free_bytes=123,
        min_free_inodes=45,
        receipt_reserve_bytes=67,
        health_timeout_seconds=45,
    )
    argv = shlex.split(command)
    config = json.loads(base64.b64decode(argv[2], validate=True))

    assert argv[:2] == ["python3", "-"]
    assert config["resident_argv_template"] == list(RESIDENT_ONLY_COMMAND)
    assert config["listener_recovery_seed_schema"] == LISTENER_RECOVERY_SEED_SCHEMA
    assert config["expected_runtime_python_path"] == RUNTIME_PYTHON
    assert config["expected_runtime_python_sha256"] == RUNTIME_PYTHON_SHA256
    assert config["expected_resident_image_id"] == RESIDENT_IMAGE_ID
    assert config["custody_host_root"].startswith(
        "/var/lib/arnold/megaplan-resident-recovery/"
    )
    assert "--listener-only" in RESIDENT_ONLY_COMMAND
    assert "__RECOVERY_SEED_PATH__" in RESIDENT_ONLY_COMMAND
    assert "resident-runtime.env" not in config["listener_capture_command"]
    assert ".cloud-hot-env" not in config["listener_capture_command"]
    assert "--ignored=matching" in config["listener_capture_command"]
    assert config["listener_capture_command"].index("--ignored=matching") < config[
        "listener_capture_command"
    ].index("resident discord --help")
    assert (
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=\"$runtime_src\""
        in config["listener_capture_command"]
    )
    assert "arnold-watchdog" not in " ".join(RESIDENT_ONLY_COMMAND)
    assert "tmux" not in " ".join(RESIDENT_ONLY_COMMAND)
    assert "fake-never-printed" not in command + script
    assert ". /workspace/.secrets" not in script
    assert "--env-file" in script
    assert '"--entrypoint", capture["runtime_python_path"]' in script
    assert 'cfg["expected_source_image_id"], "-lc", command' not in script
    assert 'cfg["expected_resident_image_id"]' in script
    assert "dst=/workspace/.megaplan/resident-only-custody" not in script
    assert "dst=/run/megaplan-resident-recovery,readonly" in script
    assert "docker\", \"create" in script
    assert "docker\", \"start" in script
    assert "resident_recovery_requires_root_custody" in script
    assert "info.st_uid != 0" in script
    assert "--restart\", \"no" in script
    assert "one-secret-value" not in command + script
    compile(script, "<resident-recover>", "exec")


def test_recovery_image_dependency_floor_includes_discord_listener_runtime() -> None:
    dockerfile = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "templates"
        / "Dockerfile"
    ).read_text(encoding="utf-8")

    assert '"PyYAML>=6.0"' in dockerfile
    assert '"discord.py>=2.6,<3"' in dockerfile
    assert "import discord, httpx, psutil, pydantic, ulid, yaml" in dockerfile


def test_recovery_seed_is_single_use_within_the_exact_container(tmp_path: Path) -> None:
    consumption_root = tmp_path / "consumed"
    seed = {"schema": LISTENER_RECOVERY_SEED_SCHEMA, "nonce": "a" * 64}

    _consume_recovery_seed_once(
        seed,
        consumption_root,
        required_uid=os.getuid(),
    )
    with pytest.raises(CliError, match="already consumed"):
        _consume_recovery_seed_once(
            seed,
            consumption_root,
            required_uid=os.getuid(),
        )


def test_down_builder_is_exact_stop_remove_not_generic_shell() -> None:
    command, script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        expected_resident_container_id=RESIDENT_ID,
        workspace=WORKSPACE,
        outage_epoch="discord-enospc-20260803",
    )
    assert shlex.split(command)[:2] == ["python3", "-"]
    assert '["docker", "stop", "--time", "15"' in script
    assert '["docker", "rm"' in script
    assert "docker system prune" not in script
    assert "docker rm -f" not in script
    compile(script, "<resident-down>", "exec")


def test_recover_rejects_mutable_workspace_interpreter() -> None:
    with pytest.raises(CliError, match="immutable accepted image"):
        resident_recover_command(
            source_container=SOURCE,
            expected_source_container_id=SOURCE_ID,
            expected_source_image_id=IMAGE_ID,
            expected_resident_image_id=RESIDENT_IMAGE_ID,
            expected_runtime_path=RUNTIME_PATH,
            expected_runtime_commit=RUNTIME_COMMIT,
            expected_runtime_tree=RUNTIME_TREE,
            expected_runtime_python_path=RUNTIME_PATH + "/.venv/bin/python",
            expected_runtime_python_sha256=RUNTIME_PYTHON_SHA256,
            workspace=WORKSPACE,
            outage_epoch="discord-enospc-20260803",
            min_free_bytes=0,
            min_free_inodes=0,
            receipt_reserve_bytes=0,
            health_timeout_seconds=5,
        )


def test_provider_recover_cas_capacity_and_receipt_binding() -> None:
    provider = _ResidentProvider()

    payload = provider.resident_recover(
        outage_epoch="discord-enospc-20260803",
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        **RUNTIME_ARGS,
        health_timeout_seconds=45,
    )

    assert payload["status"] == "healthy"
    assert len(provider.effects) == 1
    assert provider.effects[0]["surface"] == "resident_only_recover"
    assert provider.effects[0]["input"]


def test_provider_recover_fails_closed_before_effect_on_source_mismatch() -> None:
    provider = _ResidentProvider(observation=_source_observation(lifecycle="running"))

    with pytest.raises(CliError, match="compare-and-swap"):
        provider.resident_recover(
            outage_epoch="discord-enospc-20260803",
            expected_source_container_id=SOURCE_ID,
            expected_source_image_id=IMAGE_ID,
            expected_resident_image_id=RESIDENT_IMAGE_ID,
            **RUNTIME_ARGS,
        )

    assert provider.effects == []


def test_provider_recover_fails_closed_before_effect_below_capacity_floor() -> None:
    provider = _ResidentProvider(capacity={"status": "no-go", "verdict": "NO-GO"})

    with pytest.raises(CliError, match="capacity"):
        provider.resident_recover(
            outage_epoch="discord-enospc-20260803",
            expected_source_container_id=SOURCE_ID,
            expected_source_image_id=IMAGE_ID,
            expected_resident_image_id=RESIDENT_IMAGE_ID,
            **RUNTIME_ARGS,
        )

    assert provider.effects == []


def test_provider_recover_rejects_health_for_a_different_container() -> None:
    receipt = _recover_receipt()
    receipt["health_receipt"]["resident_container_id"] = "e" * 64
    provider = _ResidentProvider(remote_payload=receipt)

    with pytest.raises(CliError, match="admitted transaction"):
        provider.resident_recover(
            outage_epoch="discord-enospc-20260803",
            expected_source_container_id=SOURCE_ID,
            expected_source_image_id=IMAGE_ID,
            expected_resident_image_id=RESIDENT_IMAGE_ID,
            **RUNTIME_ARGS,
        )


def test_provider_down_binds_exact_receipt() -> None:
    down = {
        "schema": DOWN_SCHEMA,
        "status": "down",
        "outage_epoch": "discord-enospc-20260803",
        "resident_container": resident_only_container_name(SOURCE),
        "resident_container_id": RESIDENT_ID,
        "removed": True,
        "source_fence_rollback": {
            "status": "restored",
            "prior_restart_policy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
            "current_restart_policy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
            "source_container_id": SOURCE_ID,
        },
    }
    provider = _ResidentProvider(
        observation=_source_observation(lifecycle="running"),
        remote_payload=down,
    )

    payload = provider.resident_down(
        outage_epoch="discord-enospc-20260803",
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        expected_resident_container_id=RESIDENT_ID,
    )

    assert payload == down
    assert provider.effects[0]["surface"] == "resident_only_down"


def test_cli_registers_complete_recover_and_down_contract() -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)

    recover = parser.parse_args(
        [
            "resident-recover",
            "--outage-epoch",
            "discord-enospc-20260803",
            "--expected-source-container-id",
            SOURCE_ID,
            "--expected-source-image-id",
            IMAGE_ID,
            "--expected-resident-image-id",
            RESIDENT_IMAGE_ID,
            "--expected-runtime-path",
            RUNTIME_PATH,
            "--expected-runtime-commit",
            RUNTIME_COMMIT,
            "--expected-runtime-tree",
            RUNTIME_TREE,
            "--expected-runtime-python-path",
            RUNTIME_PYTHON,
            "--expected-runtime-python-sha256",
            RUNTIME_PYTHON_SHA256,
        ]
    )
    down = parser.parse_args(
        [
            "resident-down",
            "--outage-epoch",
            "discord-enospc-20260803",
            "--expected-source-container-id",
            SOURCE_ID,
            "--expected-source-image-id",
            IMAGE_ID,
            "--expected-resident-image-id",
            RESIDENT_IMAGE_ID,
            "--expected-resident-container-id",
            RESIDENT_ID,
        ]
    )

    assert recover.cloud_action == "resident-recover"
    assert recover.health_timeout_seconds == 45
    assert down.cloud_action == "resident-down"


def test_cli_dispatches_recover_and_preserves_failed_health_exit(
    tmp_path, monkeypatch, capsys
) -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)
    args = parser.parse_args(
        [
            "resident-recover",
            "--outage-epoch",
            "discord-enospc-20260803",
            "--expected-source-container-id",
            SOURCE_ID,
            "--expected-source-image-id",
            IMAGE_ID,
            "--expected-resident-image-id",
            RESIDENT_IMAGE_ID,
            "--expected-runtime-path",
            RUNTIME_PATH,
            "--expected-runtime-commit",
            RUNTIME_COMMIT,
            "--expected-runtime-tree",
            RUNTIME_TREE,
            "--expected-runtime-python-path",
            RUNTIME_PYTHON,
            "--expected-runtime-python-sha256",
            RUNTIME_PYTHON_SHA256,
        ]
    )

    class Provider:
        def resident_recover(self, **kwargs):
            assert kwargs == {
                "outage_epoch": "discord-enospc-20260803",
                "expected_source_container_id": SOURCE_ID,
                "expected_source_image_id": IMAGE_ID,
                "expected_resident_image_id": RESIDENT_IMAGE_ID,
                "expected_runtime_path": RUNTIME_PATH,
                "expected_runtime_commit": RUNTIME_COMMIT,
                "expected_runtime_tree": RUNTIME_TREE,
                "expected_runtime_python_path": RUNTIME_PYTHON,
                "expected_runtime_python_sha256": RUNTIME_PYTHON_SHA256,
                "health_timeout_seconds": 45,
            }
            return {"schema": RECOVER_SCHEMA, "status": "failed"}

    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    monkeypatch.setattr(cloud_cli, "_provider_for_action", lambda spec, args: Provider())

    assert cloud_cli.run_cloud_cli(tmp_path, args) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_cli_dispatches_exact_down(tmp_path, monkeypatch, capsys) -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)
    args = parser.parse_args(
        [
            "resident-down",
            "--outage-epoch",
            "discord-enospc-20260803",
            "--expected-source-container-id",
            SOURCE_ID,
            "--expected-source-image-id",
            IMAGE_ID,
            "--expected-resident-image-id",
            RESIDENT_IMAGE_ID,
            "--expected-resident-container-id",
            RESIDENT_ID,
        ]
    )

    class Provider:
        def resident_down(self, **kwargs):
            assert kwargs["expected_resident_container_id"] == RESIDENT_ID
            return {"schema": DOWN_SCHEMA, "status": "down", "removed": True}

    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    monkeypatch.setattr(cloud_cli, "_provider_for_action", lambda spec, args: Provider())

    assert cloud_cli.run_cloud_cli(tmp_path, args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "down"


def test_listener_only_disables_all_passive_reconciliation_and_loops(monkeypatch) -> None:
    class FakeIntents:
        message_content = False

        @classmethod
        def default(cls):
            return cls()

    class FakeClient:
        def __init__(self, *, intents):
            self.intents = intents
            self.user = SimpleNamespace(id="bot")
            self.guilds = []
            self.handlers = {}

        def event(self, callback):
            self.handlers[callback.__name__] = callback
            return callback

        async def start(self, token):
            assert token == "token"
            await self.handlers["on_ready"]()

    fake_discord = SimpleNamespace(
        Intents=FakeIntents,
        Client=FakeClient,
        app_commands=SimpleNamespace(CommandTree=None),
    )
    monkeypatch.setitem(__import__("sys").modules, "discord", fake_discord)

    class Runtime:
        config = SimpleNamespace(
            allows_operational_discord_delivery=True,
            special_requests_enabled=True,
        )
        outbound = object()

        async def recover_restart_interrupted_turns(self, identity):
            raise AssertionError("listener-only must not reconcile restart turns")

        async def recover_abandoned_turns(self):
            raise AssertionError("listener-only must not recover abandoned turns")

    service = ResidentDiscordService(
        runtime=Runtime(),
        token="token",
        scheduler=object(),
        transcriber=object(),
        attachment_downloader=object(),
        listener_only=True,
    )
    monkeypatch.setattr(
        service,
        "_seed_special_requests_job",
        lambda: (_ for _ in ()).throw(AssertionError("must not seed schedules")),
    )
    monkeypatch.setattr(
        service,
        "_ensure_scheduler_started",
        lambda client: (_ for _ in ()).throw(AssertionError("must not start loop")),
    )
    monkeypatch.setattr(service, "_log_transcription_readiness", lambda: None)

    asyncio.run(service.start())

    assert service._scheduler_task is None


def test_listener_only_omits_restart_command_and_handler_refuses_direct_call() -> None:
    class Tree:
        def __init__(self):
            self.names = []

        def command(self, *, name, description):
            def decorate(callback):
                self.names.append(name)
                return callback

            return decorate

    class Response:
        def __init__(self):
            self.messages = []

        async def send_message(self, content, *, ephemeral):
            self.messages.append((content, ephemeral))

    restart_calls = []
    service = object.__new__(ResidentDiscordService)
    service.listener_only = True
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_action=lambda subject, action: SimpleNamespace(allowed=True)
        )
    )
    service.restart_operation = lambda: restart_calls.append(True)
    tree = Tree()

    registered = register_discord_application_commands(tree, service)
    interaction = SimpleNamespace(
        user=SimpleNamespace(id="123"),
        guild_id="456",
        channel_id="789",
        channel=SimpleNamespace(parent=None),
        response=Response(),
    )
    asyncio.run(service.handle_restart_resident_interaction(interaction))

    assert RESTART_RESIDENT_COMMAND not in registered
    assert RESTART_RESIDENT_COMMAND not in tree.names
    assert restart_calls == []
    assert interaction.response.messages == [
        (
            "Resident restart is unavailable while listener-only recovery is active.",
            True,
        )
    ]


def test_listener_recovery_requires_custody_seed_and_public_env_cannot_spoof(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_RESIDENT_LISTENER_RECOVERY", "1")
    monkeypatch.setenv("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED", "0")
    with pytest.raises(CliError, match="requires a recovery launch seed"):
        _require_discord_runtime_launch(listener_only=True)

    from arnold_pipelines.megaplan.resident import cli as resident_cli

    recovery_calls = []
    monkeypatch.setattr(
        resident_cli,
        "require_listener_recovery_seed",
        lambda path: recovery_calls.append(path),
    )
    _require_discord_runtime_launch(
        listener_only=True,
        recovery_seed="/run/megaplan-resident-recovery/launch-seed.json",
    )
    assert recovery_calls == [
        "/run/megaplan-resident-recovery/launch-seed.json"
    ]

    from arnold_pipelines.megaplan.cloud import runtime_attestation

    ordinary_calls = []

    def reject_stale_ordinary(component, *, create):
        ordinary_calls.append((component, create))
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "source_revision_mismatch",
        )

    monkeypatch.setattr(
        runtime_attestation,
        "require_configured_runtime_launch",
        reject_stale_ordinary,
    )
    with pytest.raises(CliError, match="source_revision_mismatch"):
        _require_discord_runtime_launch(
            listener_only=False,
        )
    assert ordinary_calls == [("resident", True)]


def test_host_transactions_fence_recheck_health_freshly_and_target_ids(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".secrets").mkdir(parents=True)
    (workspace / ".secrets" / "megaplan-resident-discord.env").write_text(
        "DISCORD_BOT_TOKEN=fake-never-printed\n"
        "DISCORD_DM_USER_ID=123456789\n"
        "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=production\n"
        "MEGAPLAN_RESIDENT_STORE_ROOT=/workspace/arnold/.megaplan/resident\n",
        encoding="utf-8",
    )
    runtime_workspace = workspace / RUNTIME_PATH.removeprefix("/workspace/")
    runtime_workspace.mkdir(parents=True)
    (runtime_workspace / "accepted-runtime.txt").write_text(
        "accepted\n", encoding="utf-8"
    )
    state_path = tmp_path / "docker-state.json"
    state_path.write_text(
        json.dumps(
            {
                "source_policy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
                "source_running": False,
                "revive_on_fence": True,
                "resident": None,
                "ready": True,
                "listener_supported": True,
                "selector_race": False,
                "post_create_swap": False,
                "rewrite_seed_on_final": False,
                "capture_count": 0,
                "ops": [],
            }
        ),
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"""#!{sys.executable}
import glob, json, os, sys
state_path = os.environ["FAKE_DOCKER_STATE"]
workspace = os.environ["FAKE_DOCKER_WORKSPACE"]
custody_root = os.environ["FAKE_CUSTODY_ROOT"]
source_id = os.environ["FAKE_SOURCE_ID"]
image_id = os.environ["FAKE_IMAGE_ID"]
resident_image_id = os.environ["FAKE_RESIDENT_IMAGE_ID"]
resident_id = os.environ["FAKE_RESIDENT_ID"]
source_name = os.environ["FAKE_SOURCE_NAME"]
resident_name = source_name + "-resident-only"
with open(state_path, "r", encoding="utf-8") as handle:
    state = json.load(handle)
args = sys.argv[1:]
state["ops"].append(args)
def save():
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
def source():
    return {{"Id": source_id, "Image": image_id, "Name": "/" + source_name,
      "State": {{"Running": state["source_running"], "Paused": False, "Restarting": False, "ExitCode": 1, "StartedAt": "2026-08-03T00:00:00Z"}},
      "HostConfig": {{"RestartPolicy": state["source_policy"]}},
      "Mounts": [{{"Type": "bind", "Source": workspace, "Destination": "/workspace", "RW": True}}]}}
if args[0] == "inspect":
    ident = args[-1]
    item = source() if ident in (source_id, source_name) else state["resident"] if ident in (resident_id, resident_name) else None
    save()
    if item is None:
        print("Error: No such container: " + ident, file=sys.stderr); raise SystemExit(1)
    print(json.dumps([item])); raise SystemExit(0)
if args[0] == "update":
    assert args[-1] == source_id
    value = args[args.index("--restart") + 1]
    if value.startswith("on-failure:"):
        state["source_policy"] = {{"Name": "on-failure", "MaximumRetryCount": int(value.split(":", 1)[1])}}
    else:
        state["source_policy"] = {{"Name": value, "MaximumRetryCount": 0}}
    if value == "no" and state.get("revive_on_fence"):
        state["source_running"] = True
        state["revive_on_fence"] = False
    save(); print(source_id); raise SystemExit(0)
if args[0] == "run" and "--rm" in args:
    state["capture_count"] += 1
    if not state["listener_supported"]:
        save(); print("listener unavailable", file=sys.stderr); raise SystemExit(1)
    commit = "{RUNTIME_COMMIT}"
    if state.get("selector_race") and state["capture_count"] % 2 == 0:
        commit = "9" * 40
    print(json.dumps({{
      "schema": "arnold.cloud.resident_only_runtime_capture.v1",
      "runtime_path": "{RUNTIME_PATH}", "runtime_commit": commit,
      "runtime_tree": "{RUNTIME_TREE}", "runtime_python_path": "{RUNTIME_PYTHON}",
      "runtime_python_sha256": "{RUNTIME_PYTHON_SHA256}",
      "workspace_identity": {{"st_dev": 10, "st_ino": 20}},
    }}))
    if state.get("rewrite_seed_on_final") and state["capture_count"] >= 4:
        for seed_path in glob.glob(custody_root + "/*/seed/launch-seed.json"):
            with open(seed_path, "w", encoding="utf-8") as handle:
                handle.write("{{}}\\n")
    save(); raise SystemExit(0)
if args[0] == "create":
    mounts = []
    for index, value in enumerate(args):
        if value != "--mount": continue
        spec = args[index + 1]
        fields = {{part.split("=", 1)[0]: part.split("=", 1)[1] for part in spec.split(",") if "=" in part}}
        mounts.append({{"Type": fields.get("type"), "Source": fields.get("src"), "Destination": fields.get("dst"), "RW": "readonly" not in spec.split(",")}})
    env_rows = []
    if "--env-file" in args:
        with open(args[args.index("--env-file") + 1], "r", encoding="utf-8") as handle:
            env_rows.extend(line.rstrip("\\n") for line in handle)
    env_rows.extend(args[index + 1] for index, value in enumerate(args) if value == "--env")
    env_map = {{row.split("=", 1)[0]: row.split("=", 1)[1] for row in env_rows}}
    entrypoint_index = args.index("--entrypoint")
    image_index = entrypoint_index + 2
    assert args[image_index] == resident_image_id
    state["resident"] = {{"Id": resident_id, "Image": resident_image_id, "Name": "/" + resident_name,
      "State": {{"Running": False, "Paused": False, "Restarting": False, "ExitCode": 0, "StartedAt": ""}},
      "HostConfig": {{"RestartPolicy": {{"Name": "no", "MaximumRetryCount": 0}}, "CapDrop": ["ALL"], "CapAdd": None, "SecurityOpt": ["no-new-privileges:true"], "PidsLimit": 256, "Memory": 2147483648, "MemorySwap": 2147483648}},
      "Config": {{"Entrypoint": [args[entrypoint_index + 1]], "User": "0:0", "WorkingDir": args[args.index("--workdir") + 1], "Cmd": args[image_index + 1:], "Env": env_rows}},
      "Mounts": mounts}}
    if state.get("post_create_swap"):
        runtime_file = os.path.join(workspace, "{RUNTIME_PATH.removeprefix('/workspace/')}", "accepted-runtime.txt")
        with open(runtime_file, "w", encoding="utf-8") as handle:
            handle.write("mutated-after-create\\n")
    save(); print(resident_id); raise SystemExit(0)
if args[0] == "start":
    assert args[-1] == resident_id
    state["resident"]["State"]["Running"] = True
    state["resident"]["State"]["StartedAt"] = "2026-08-03T10:00:00.000000000Z"
    save(); print(resident_id); raise SystemExit(0)
if args[0] == "logs":
    assert args[-1] == resident_id
    save()
    if state["ready"]: print("Resident Discord service ready user_id=1 guild_count=1 listener_only=True")
    raise SystemExit(0)
if args[0] == "stop":
    assert args[-1] in (source_id, resident_id)
    if args[-1] == source_id:
        state["source_running"] = False
    else:
        state["resident"]["State"]["Running"] = False
    save(); print(args[-1]); raise SystemExit(0)
if args[0] == "rm":
    assert args[-1] == resident_id
    state["resident"] = None
    save(); print(resident_id); raise SystemExit(0)
save(); print("unsupported", args, file=sys.stderr); raise SystemExit(2)
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
        "FAKE_DOCKER_STATE": str(state_path),
        "FAKE_DOCKER_WORKSPACE": str(workspace),
        "FAKE_CUSTODY_ROOT": str(tmp_path / "custody" / SOURCE_ID),
        "FAKE_SOURCE_ID": SOURCE_ID,
        "FAKE_IMAGE_ID": IMAGE_ID,
        "FAKE_RESIDENT_IMAGE_ID": RESIDENT_IMAGE_ID,
        "FAKE_RESIDENT_ID": RESIDENT_ID,
        "FAKE_SOURCE_NAME": SOURCE,
    }
    common = {
        "source_container": SOURCE,
        "expected_source_container_id": SOURCE_ID,
        "expected_source_image_id": IMAGE_ID,
        "expected_resident_image_id": RESIDENT_IMAGE_ID,
        "workspace": str(workspace),
        "outage_epoch": "discord-enospc-20260803",
        **RUNTIME_ARGS,
    }
    local_custody_root = tmp_path / "custody" / SOURCE_ID

    command, script = resident_recover_command(
        **common,
        min_free_bytes=0,
        min_free_inodes=0,
        receipt_reserve_bytes=0,
        health_timeout_seconds=5,
    )
    script = _emulate_root_custody_for_local_transaction(script)
    command = _relocate_custody_for_local_transaction(command, local_custody_root)
    encoded = shlex.split(command)[2]
    first = subprocess.run(
        [sys.executable, "-", encoded],
        input=script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert parse_resident_recovery_receipt(first.stdout)["status"] == "healthy"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["source_policy"] == {"Name": "no", "MaximumRetryCount": 0}
    assert state["source_running"] is False
    assert sum(op[0] == "create" for op in state["ops"]) == 1
    resident_env = dict(
        row.split("=", 1) for row in state["resident"]["Config"]["Env"]
    )
    assert resident_env["DISCORD_DM_USER_ID"] == "123456789"
    assert resident_env["MEGAPLAN_RESIDENT_STORE_ROOT"] == (
        "/workspace/arnold/.megaplan/resident"
    )
    assert sum(
        row.startswith("MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=")
        for row in state["resident"]["Config"]["Env"]
    ) == 1

    state["resident"]["State"]["Running"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    second = subprocess.run(
        [sys.executable, "-", encoded],
        input=script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    second_payload = parse_resident_recovery_receipt(second.stdout)
    assert second_payload["status"] == "failed"
    assert second_payload["new_attempt"] is False
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sum(op[0] == "create" for op in state["ops"]) == 1

    # Simulate a manual restart after the failed observation; exact down must
    # still target the immutable ID and restore the predecessor fence.
    state["resident"]["State"]["Running"] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
    down_command, down_script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        workspace=str(workspace),
        outage_epoch="discord-enospc-20260803",
        expected_resident_container_id=RESIDENT_ID,
    )
    down_command = _relocate_custody_for_local_transaction(
        down_command, local_custody_root
    )
    down_script = _emulate_root_custody_for_local_transaction(down_script)
    down = subprocess.run(
        [sys.executable, "-", shlex.split(down_command)[2]],
        input=down_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert down.returncode == 0, down.stderr
    down_payload = parse_resident_down_receipt(down.stdout)
    assert down_payload["source_fence_rollback"]["status"] == "restored"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["resident"] is None
    assert state["source_policy"] == {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }
    stop_ops = [op for op in state["ops"] if op[0] == "stop"]
    rm_ops = [op for op in state["ops"] if op[0] == "rm"]
    assert {op[-1] for op in stop_ops} >= {SOURCE_ID, RESIDENT_ID}
    assert rm_ops and all(op[-1] == RESIDENT_ID for op in rm_ops)

    updates_before_closed_retry = sum(op[0] == "update" for op in state["ops"])
    closed_retry = subprocess.run(
        [sys.executable, "-", encoded],
        input=script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert closed_retry.returncode != 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sum(op[0] == "update" for op in state["ops"]) == updates_before_closed_retry
    assert state["source_policy"] == {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }

    state["listener_supported"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    blocked_common = {**common, "outage_epoch": "discord-enospc-unsupported"}
    blocked_command, blocked_script = resident_recover_command(
        **blocked_common,
        min_free_bytes=0,
        min_free_inodes=0,
        receipt_reserve_bytes=0,
        health_timeout_seconds=5,
    )
    blocked_script = _emulate_root_custody_for_local_transaction(blocked_script)
    blocked_command = _relocate_custody_for_local_transaction(
        blocked_command, local_custody_root
    )
    blocked = subprocess.run(
        [sys.executable, "-", shlex.split(blocked_command)[2]],
        input=blocked_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert blocked.returncode != 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["source_policy"] == {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }
    blocked_prefix = (
        local_custody_root
        / "discord-enospc-unsupported"
        / "transaction"
    )
    assert not Path(str(blocked_prefix) + ".intent.json").exists()
    rollback = json.loads(
        Path(str(blocked_prefix) + ".fence.rollback.json").read_text(
            encoding="utf-8"
        )
    )
    assert rollback["status"] == "restored"

    state["listener_supported"] = True
    state["selector_race"] = True
    state["capture_count"] = 0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    raced_common = {**common, "outage_epoch": "discord-enospc-selector-race"}
    raced_command, raced_script = resident_recover_command(
        **raced_common,
        min_free_bytes=0,
        min_free_inodes=0,
        receipt_reserve_bytes=0,
        health_timeout_seconds=5,
    )
    raced_script = _emulate_root_custody_for_local_transaction(raced_script)
    raced_command = _relocate_custody_for_local_transaction(
        raced_command, local_custody_root
    )
    creates_before_race = sum(op[0] == "create" for op in state["ops"])
    raced = subprocess.run(
        [sys.executable, "-", shlex.split(raced_command)[2]],
        input=raced_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert raced.returncode != 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sum(op[0] == "create" for op in state["ops"]) == creates_before_race
    race_prefix = (
        local_custody_root
        / "discord-enospc-selector-race"
        / "transaction"
    )
    assert not Path(str(race_prefix) + ".intent.json").exists()
    race_rollback = json.loads(
        Path(str(race_prefix) + ".fence.rollback.json").read_text(
            encoding="utf-8"
        )
    )
    assert race_rollback["reason"] == "listener_runtime_selector_race"

    state["selector_race"] = False
    state["post_create_swap"] = True
    state["capture_count"] = 0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    swap_common = {**common, "outage_epoch": "discord-enospc-post-create-swap"}
    swap_command, swap_script = resident_recover_command(
        **swap_common,
        min_free_bytes=0,
        min_free_inodes=0,
        receipt_reserve_bytes=0,
        health_timeout_seconds=5,
    )
    swap_script = _emulate_root_custody_for_local_transaction(swap_script)
    swap_command = _relocate_custody_for_local_transaction(
        swap_command, local_custody_root
    )
    swap = subprocess.run(
        [sys.executable, "-", shlex.split(swap_command)[2]],
        input=swap_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert swap.returncode == 0, swap.stderr
    assert parse_resident_recovery_receipt(swap.stdout)["status"] == "healthy"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["resident"] is not None
    assert state["resident"]["State"]["Running"] is True
    runtime_mount = next(
        mount
        for mount in state["resident"]["Mounts"]
        if mount["Destination"] == RUNTIME_PATH
    )
    expected_snapshot = (
        local_custody_root
        / "discord-enospc-post-create-swap"
        / "runtime"
    )
    assert runtime_mount == {
        "Type": "bind",
        "Source": str(expected_snapshot),
        "Destination": RUNTIME_PATH,
        "RW": False,
    }
    assert (runtime_workspace / "accepted-runtime.txt").read_text(
        encoding="utf-8"
    ) == "mutated-after-create\n"
    assert (expected_snapshot / "accepted-runtime.txt").read_text(
        encoding="utf-8"
    ) == "accepted\n"

    prestart_down_command, prestart_down_script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        expected_resident_container_id=RESIDENT_ID,
        workspace=str(workspace),
        outage_epoch="discord-enospc-post-create-swap",
    )
    prestart_down_command = _relocate_custody_for_local_transaction(
        prestart_down_command, local_custody_root
    )
    prestart_down_script = _emulate_root_custody_for_local_transaction(
        prestart_down_script
    )
    prestart_down = subprocess.run(
        [sys.executable, "-", shlex.split(prestart_down_command)[2]],
        input=prestart_down_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert prestart_down.returncode == 0, prestart_down.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["resident"] is None
    assert state["source_policy"] == {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }

    state["post_create_swap"] = False
    state["rewrite_seed_on_final"] = True
    state["capture_count"] = 0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    rewrite_common = {**common, "outage_epoch": "discord-enospc-seed-rewrite"}
    rewrite_command, rewrite_script = resident_recover_command(
        **rewrite_common,
        min_free_bytes=0,
        min_free_inodes=0,
        receipt_reserve_bytes=0,
        health_timeout_seconds=5,
    )
    rewrite_script = _emulate_root_custody_for_local_transaction(rewrite_script)
    rewrite_command = _relocate_custody_for_local_transaction(
        rewrite_command, local_custody_root
    )
    rewrite = subprocess.run(
        [sys.executable, "-", shlex.split(rewrite_command)[2]],
        input=rewrite_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert rewrite.returncode != 0
    assert "recovery_seed_changed_before_start" in rewrite.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["resident"] is not None
    assert state["resident"]["State"]["Running"] is False

    rewrite_down_command, rewrite_down_script = resident_down_command(
        source_container=SOURCE,
        expected_source_container_id=SOURCE_ID,
        expected_source_image_id=IMAGE_ID,
        expected_resident_image_id=RESIDENT_IMAGE_ID,
        expected_resident_container_id=RESIDENT_ID,
        workspace=str(workspace),
        outage_epoch="discord-enospc-seed-rewrite",
    )
    rewrite_down_command = _relocate_custody_for_local_transaction(
        rewrite_down_command, local_custody_root
    )
    rewrite_down_script = _emulate_root_custody_for_local_transaction(
        rewrite_down_script
    )
    custody_fence_path = (
        local_custody_root
        / "discord-enospc-seed-rewrite"
        / "transaction.fence.json"
    )
    original_fence_bytes = custody_fence_path.read_bytes()
    forged_fence = json.loads(original_fence_bytes)
    forged_fence["prior_restart_policy"] = {
        "Name": "always",
        "MaximumRetryCount": 0,
    }
    custody_fence_path.write_text(
        json.dumps(forged_fence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    forged_down = subprocess.run(
        [sys.executable, "-", shlex.split(rewrite_down_command)[2]],
        input=rewrite_down_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert forged_down.returncode != 0
    assert "source_fence_receipt_invalid" in forged_down.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["resident"] is not None
    assert state["source_policy"] == {"Name": "no", "MaximumRetryCount": 0}
    custody_fence_path.write_bytes(original_fence_bytes)
    rewrite_down = subprocess.run(
        [sys.executable, "-", shlex.split(rewrite_down_command)[2]],
        input=rewrite_down_script,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert rewrite_down.returncode == 0, rewrite_down.stderr

    secret_file = workspace / ".secrets" / "megaplan-resident-discord.env"
    for suffix, malicious_secret, expected_error in (
        (
            "shell-expansion",
            "DISCORD_BOT_TOKEN=$(touch-/workspace/pwn)\n",
            "resident_secret_grammar_invalid",
        ),
        (
            "startup-env",
            "DISCORD_BOT_TOKEN=safe-token\nBASH_ENV=/workspace/pwn\n",
            "resident_secret_name_invalid",
        ),
        (
            "allowlisted-value-shell-expansion",
            "DISCORD_BOT_TOKEN=safe-token\n"
            "MEGAPLAN_RESIDENT_STORE_ROOT=$(touch-/workspace/pwn)\n",
            "resident_secret_grammar_invalid",
        ),
    ):
        secret_file.write_text(malicious_secret, encoding="utf-8")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        mutating_before = sum(
            op[0] in {"update", "create", "start"} for op in state["ops"]
        )
        malicious_command, malicious_script = resident_recover_command(
            **{**common, "outage_epoch": "discord-secret-" + suffix},
            min_free_bytes=0,
            min_free_inodes=0,
            receipt_reserve_bytes=0,
            health_timeout_seconds=5,
        )
        malicious_command = _relocate_custody_for_local_transaction(
            malicious_command, local_custody_root
        )
        malicious_script = _emulate_root_custody_for_local_transaction(
            malicious_script
        )
        malicious = subprocess.run(
            [sys.executable, "-", shlex.split(malicious_command)[2]],
            input=malicious_script,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        assert malicious.returncode != 0
        assert expected_error in malicious.stderr
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert (
            sum(op[0] in {"update", "create", "start"} for op in state["ops"])
            == mutating_before
        )
