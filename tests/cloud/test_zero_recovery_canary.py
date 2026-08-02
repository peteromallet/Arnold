from __future__ import annotations

import argparse
import base64
import json
import shlex
import subprocess
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.providers import zero_recovery
from arnold_pipelines.megaplan.cloud.providers.ssh_preflight import (
    capacity_inventory_command,
    parse_capacity_inventory_result,
)
from arnold_pipelines.megaplan.cloud.providers.ssh import (
    _ZERO_RECOVERY_CANARY_RUNTIME_FORMAT,
    _ZERO_RECOVERY_OAUTH_INSTALL_SCRIPT,
    SshProvider,
    _zero_recovery_canary_runtime_command,
    _require_advertised_branch_commit,
)
from arnold_pipelines.megaplan.workers._impl import (
    _record_zero_recovery_dispatch,
    _record_zero_recovery_dispatch_terminal,
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
from arnold_pipelines.megaplan.chain.spec import (
    _finite_canary_conformance_has_trust_evidence,
    _finite_canary_fence_is_valid,
)


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


def test_canary_runtime_inspect_has_one_exact_object_and_unambiguous_type() -> None:
    argv = shlex.split(
        _zero_recovery_canary_runtime_command(
            "megaplan-cloud-agent-finite-canary"
        )
    )
    assert argv == [
        "docker",
        "inspect",
        "--type=container",
        "--format",
        _ZERO_RECOVERY_CANARY_RUNTIME_FORMAT,
        "megaplan-cloud-agent-finite-canary",
    ]
    assert argv.count("container") == 0


def test_moved_advertised_branch_rejects_even_when_old_commit_is_reachable() -> None:
    admitted = "a" * 40
    branch = "safe/canary"
    _require_advertised_branch_commit(
        stdout=f"{admitted}\trefs/heads/{branch}\n",
        branch=branch,
        source_commit=admitted,
    )
    with pytest.raises(CliError, match="branch tip"):
        _require_advertised_branch_commit(
            stdout=f"{'b' * 40}\trefs/heads/{branch}\n",
            branch=branch,
            source_commit=admitted,
        )


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


@pytest.mark.parametrize("action", ["exec", "quickstart", "retire-chain", "retire-stale-status"])
def test_zero_cli_denies_generic_action_before_provider_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, action: str
) -> None:
    (tmp_path / "cloud.yaml").write_text("zero-profile", encoding="utf-8")
    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    called = False

    def provider(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be created")

    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    args = argparse.Namespace(
        cloud_action=action, command="echo hostile", cloud_yaml=None, on_box=True
    )
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
    assert "for key, value in os.environ.items()" not in source
    for forbidden_env in ("OPENAI_API_KEY", "DISCORD_TOKEN", "ARNOLD_", "MEGAPLAN_USE_AGENT_DISPATCHER"):
        assert forbidden_env not in source
    assert "except BaseException as exc" in source
    assert "finite_canary_phase_checkpoint.v1" in source
    assert source.count('"--phase-model"') == 4


def test_oauth_installer_is_strict_atomic_no_follow_and_stdin_only() -> None:
    source = _ZERO_RECOVERY_OAUTH_INSTALL_SCRIPT
    for required in (
        "object_pairs_hook=reject_duplicates", "os.lstat", "os.O_NOFOLLOW",
        "os.O_EXCL", "os.replace", "os.fsync", "follow_symlinks=False",
    ):
        assert required in source
    assert "write_text" not in source

    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    calls: list[tuple[str, str | None]] = []
    provider._remote_run_compatible = lambda command, **kwargs: (
        calls.append((command, kwargs.get("input")))
        or subprocess.CompletedProcess([], 0, "", "")
    )
    secret = '{"auth_mode":"chatgpt","tokens":{"access_token":"DO_NOT_LEAK"}}'
    provider.seed_zero_recovery_codex_oauth(secret)
    assert calls[0][1] == secret
    assert "DO_NOT_LEAK" not in calls[0][0]
    with pytest.raises(CliError):
        provider.seed_zero_recovery_codex_oauth(
            '{"auth_mode":"chatgpt","auth_mode":"chatgpt"}'
        )


def test_dispatch_ledger_has_one_matching_start_terminal_pair(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    start = _record_zero_recovery_dispatch(
        tmp_path, step="plan", agent="codex", model="gpt-5.6-sol", effort="high"
    )
    _record_zero_recovery_dispatch_terminal(
        tmp_path, start=start, worker=SimpleNamespace(model_actual="gpt-5.6-sol")
    )
    rows = [json.loads(line) for line in (tmp_path / "zero_recovery_dispatch_ledger.ndjson").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["start", "terminal"]
    assert rows[0]["dispatch_id"] == rows[1]["dispatch_id"]
    with pytest.raises(CliError, match="second plan dispatch"):
        _record_zero_recovery_dispatch(
            tmp_path, step="plan", agent="codex", model="gpt-5.6-sol", effort="high"
        )
    with pytest.raises(CliError, match="actual model"):
        _record_zero_recovery_dispatch_terminal(
            tmp_path, start=start, worker=SimpleNamespace(model_actual="other")
        )


def test_synthetic_passed_receipts_without_real_fence_or_reviewer_are_rejected() -> None:
    forged_fence = {
        "schema": "arnold.cloud.zero_recovery_host_fence.v1",
        "status": "passed",
        "stage": "verify",
        "transaction_id": "forged",
        "transaction_digest": "a" * 64,
        "marker": {},
        "units": [],
        "forbidden_sessions": [],
        "forbidden_processes": [],
        "observed_at": "2026-08-03T00:00:00Z",
    }
    assert _finite_canary_fence_is_valid(forged_fence) is False

    self_attested = {
        "schema": "arnold.megaplan.finite_canary_conformance_receipt.v1",
        "status": "passed",
        "subject": {"canary_id": "forged"},
        "run_receipt_sha256": "b" * 64,
        "checks": ["exact_phase_order"],
    }
    assert _finite_canary_conformance_has_trust_evidence(self_attested) is False


def test_malformed_status_still_reconciles_running_exact_canary() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = SshSpec(
        host="host", workspace_dir="/opt/megaplan-cloud/workspace",
        container="megaplan-cloud-agent-finite-canary",
    )
    commands: list[str] = []

    def remote(command: str, **kwargs):
        commands.append(command)
        stdout = "not-json" if command.startswith("python3 ") else ""
        return subprocess.CompletedProcess([], 0, stdout, "")

    observations = iter(
        [
            {"status": "available", "container": provider._ssh.container, "lifecycle": "running"},
            {"status": "available", "container": provider._ssh.container, "lifecycle": "stopped"},
        ]
    )
    provider._remote_run_compatible = remote
    provider.observe_container = lambda: next(observations)
    provider._observe_zero_recovery_canary_runtime = lambda **kwargs: {}
    payload = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )
    assert payload["status"] == "unknown"
    assert payload["reconciled_stop"] is True
    assert sum(shlex.split(command)[:2] == ["docker", "stop"] for command in commands) == 1


def test_execute_attempts_exact_stop_even_when_first_observation_raises() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    commands: list[str] = []
    provider._observe_zero_recovery_canary_runtime = lambda **kwargs: (_ for _ in ()).throw(
        CliError("observation_failed", "boom")
    )
    provider._remote_run_compatible = lambda command, **kwargs: (
        commands.append(command) or subprocess.CompletedProcess([], 0, "", "")
    )
    provider.observe_container = lambda: {
        "status": "available", "container": provider._ssh.container, "lifecycle": "stopped"
    }
    with pytest.raises(CliError, match="terminal reconciliation failed"):
        provider.execute_zero_recovery_canary(
            '{"auth_mode":"chatgpt"}', source_commit="a" * 40, source_tree="b" * 40
        )
    assert [shlex.split(command) for command in commands] == [
        ["docker", "stop", provider._ssh.container]
    ]
