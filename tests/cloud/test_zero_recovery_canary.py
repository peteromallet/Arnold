from __future__ import annotations

import argparse
import base64
import json
import shlex
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.providers import zero_recovery
from arnold_pipelines.megaplan.cloud.providers.ssh_preflight import (
    capacity_inventory_command,
    parse_capacity_inventory_result,
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


def _outer(*, error: str = "historic ENOSPC") -> dict[str, object]:
    return {
        "schema": "arnold.cloud.ssh_container_observation.v1",
        "status": "available",
        "lifecycle": "stopped",
        "container_state": "exited",
        "container": "megaplan-cloud-agent",
        "container_id": "a" * 64,
        "image_id": "sha256:" + "b" * 64,
        "image_ref": "megaplan-cloud-agent",
        "workspace_bind": {
            "status": "present", "type": "bind",
            "source": "/opt/megaplan-cloud/workspace",
            "destination": "/workspace", "rw": True,
        },
        "started_at": "2026-08-02T00:00:00Z",
        "finished_at": "2026-08-02T00:01:00Z",
        "restart_count": 0,
        "error": error,
        "exit_code": 137,
        "oom_killed": False,
    }


def _target() -> dict[str, object]:
    return {
        "host": "host", "user": "root", "port": 22,
        "container": "megaplan-cloud-agent",
        "canary_container": "megaplan-cloud-agent-finite-canary",
        "workspace": "/opt/megaplan-cloud/workspace",
        "capacity_scopes": [
            "/opt/megaplan-cloud/workspace",
            "/opt/megaplan-cloud/deploy",
            "/opt/megaplan-cloud/cache",
        ],
        "capacity_floor_bytes": 101,
    }


def _mount() -> dict[str, object]:
    return {
        "st_dev": 1, "device_major": 0, "device_minor": 1, "inode": 2,
        "mount_point": "/", "filesystem": "ext4", "mount_source": "/dev/sda1",
    }


def _inventory() -> dict[str, object]:
    rows = [
        {"Type": kind, "TotalCount": "1", "Active": "0", "Size": "1B", "Reclaimable": "1B"}
        for kind in ("Images", "Containers", "Local Volumes", "Build Cache")
    ]
    return {
        "schema": "arnold.cloud.ssh_capacity_inventory.v1",
        "workspace": "/opt/megaplan-cloud/workspace",
        "filesystem": {"free_bytes": 0, "free_inodes": 20, "block_size": 4096},
        "mount": _mount(),
        "scopes": [
            {"path": path, "status": "available", "size_bytes": 1}
            for path in _target()["capacity_scopes"]
        ],
        "docker_disk_usage": rows,
        "errors": [], "status": "available", "returncode": 0,
    }


def _prelaunch(*, go: bool) -> dict[str, object]:
    if go:
        return {
            "schema": "arnold.cloud.ssh_workspace_prelaunch.v1", "status": "go",
            "verdict": "GO", "workspace": "/opt/megaplan-cloud/workspace",
            "returncode": 0, "errors": [], "container": _outer(),
        }
    return {
        "schema": "arnold.cloud.ssh_workspace_prelaunch.v1", "status": "no-go",
        "verdict": "NO-GO", "workspace": "/opt/megaplan-cloud/workspace",
        "returncode": 3, "errors": ["prelaunch_free_bytes_below_reserve"],
        "thresholds": {"min_free_bytes": 100, "min_free_inodes": 10, "receipt_reserve_bytes": 1},
        "checks": {"byte_floor": False, "inode_floor": True},
        "capacity": {"free_bytes": 0, "free_inodes": 20},
        "mount": _mount(), "container": _outer(),
    }


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh", repo=RepoSpec(url="https://github.com/o/r.git", branch="a" * 40),
        agents={"default": "codex"}, codex=CodexSpec(), mode="idle",
        megaplan=MegaplanSpec(codex_auth="chatgpt"), resources=ResourcesSpec(),
        secrets=[], ssh=SshSpec(host="host", container="megaplan-cloud-agent-finite-canary"),
        zero_recovery_canary=True,
        zero_recovery_predecessor_container="megaplan-cloud-agent",
    )


def test_zero_profile_spec_is_strict_and_requires_distinct_predecessor(tmp_path: Path) -> None:
    base = """provider: ssh\nmode: idle\nzero_recovery_canary: true\nrepo:\n  url: https://github.com/o/r.git\nagents:\n  default: codex\nssh:\n  host: host\n  container: canary\nsecrets: []\n"""
    path = tmp_path / "cloud.yaml"
    path.write_text(base, encoding="utf-8")
    with pytest.raises(CliError):
        load_spec(path)
    path.write_text(base + "zero_recovery_predecessor_container: old\n", encoding="utf-8")
    assert load_spec(path).zero_recovery_predecessor_container == "old"
    path.write_text(base.replace("true", "1") + "zero_recovery_predecessor_container: old\n", encoding="utf-8")
    with pytest.raises(CliError):
        load_spec(path)


def test_zero_entrypoint_is_healthserver_only() -> None:
    rendered = render_entrypoint(_spec())
    assert "exec python3 /usr/local/bin/healthserver.py" in rendered
    for forbidden in ("tmux", "watchdog", "heartbeat", "resident", "discord", "marker", "agent"):
        assert forbidden not in rendered.lower()


def test_historical_container_enospc_does_not_block_fresh_go() -> None:
    transaction = zero_recovery.build_predeploy_transaction(
        outer=_outer(error="no space left on device"), capacity=_prelaunch(go=True),
        target=_target(), now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert transaction["schema"] == zero_recovery.PREDEPLOY_SCHEMA


def test_bootstrap_requires_exact_byte_floor_and_fresh_identical_evidence() -> None:
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    proposal = zero_recovery.build_bootstrap_reclaim_transaction(
        outer=_outer(), prelaunch=_prelaunch(go=False), inventory=_inventory(),
        target=_target(), now=now,
    )
    zero_recovery.validate_bootstrap_reclaim_transaction(
        proposal, target=_target(), outer=_outer(), prelaunch=_prelaunch(go=False),
        inventory=_inventory(), now=now + timedelta(seconds=1),
    )
    changed = _inventory()
    changed["filesystem"] = {**changed["filesystem"], "free_bytes": 1}
    with pytest.raises(CliError):
        zero_recovery.validate_bootstrap_reclaim_transaction(
            proposal, target=_target(), outer=_outer(), prelaunch=_prelaunch(go=False),
            inventory=changed, now=now + timedelta(seconds=1),
        )


def test_bootstrap_remote_program_orders_fence_before_bounded_prune() -> None:
    proposal = zero_recovery.build_bootstrap_reclaim_transaction(
        outer=_outer(), prelaunch=_prelaunch(go=False), inventory=_inventory(),
        target=_target(), now=datetime.now(timezone.utc),
    )
    command = zero_recovery.bootstrap_reclaim_command(proposal)
    argv = shlex.split(command)
    script = argv[2]
    config = json.loads(base64.b64decode(argv[3]))
    assert config["command_argv"] == ["docker", "builder", "prune", "-f"]
    assert script.index('"systemctl", "mask", "--runtime", "--now"') < script.index('prune = run(["docker", "builder", "prune", "-f"])')
    for forbidden in ("docker system prune", "docker container prune", "docker image prune", "docker volume prune", "docker rm", "rm -rf", '"-a"', '"--all"'):
        assert forbidden not in script


def test_inventory_command_and_parser_reject_scope_or_docker_ambiguity() -> None:
    command = capacity_inventory_command(
        workspace_dir="/opt/megaplan-cloud/workspace",
        remote_dir="/opt/megaplan-cloud/deploy",
        cache_dir="/opt/megaplan-cloud/cache",
    )
    assert "/etc" not in command
    payload = _inventory()
    payload.pop("returncode")
    bad = json.loads(json.dumps(payload))
    bad["scopes"].reverse()
    parsed = parse_capacity_inventory_result(
        returncode=0, stdout=json.dumps(bad), stderr="",
        expected_paths=_target()["capacity_scopes"],
    )
    assert parsed["status"] == "unknown"


def test_zero_cli_denies_generic_action_before_provider_creation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    called = False

    def provider(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be created")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    args = argparse.Namespace(cloud_action="exec", command="echo hostile", cloud_yaml=None)
    assert cloud_cli.run_cloud_cli(tmp_path, args) == 1
    assert called is False


def test_zero_deploy_source_has_no_reachable_container_removal() -> None:
    module_text = Path("arnold_pipelines/megaplan/cloud/providers/ssh.py").read_text(encoding="utf-8")
    source = module_text[module_text.index("    def _deploy_direct("):module_text.index("    def ssh_exec(")]
    assert "if not self._spec.zero_recovery_canary" in source
    assert source.index("if not self._spec.zero_recovery_canary") < source.index("docker rm -f")
    assert "--restart no" in source


def test_runner_stops_after_first_failed_phase_and_has_no_forbidden_commands() -> None:
    source = Path(".megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py").read_text(encoding="utf-8")
    assert "break" in source and "if completed.returncode != 0" in source
    for forbidden in ('"auto"', '"chain"', '"resume"', '"revise"', '"execute"', '"review"', '"override"', "tmux"):
        assert forbidden not in source.lower()
    assert '"DISCORD_TOKEN"' in source
    assert source.count('"--phase-model"') == 4
