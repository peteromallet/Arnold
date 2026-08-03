from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
import os
import runpy
import shlex
import socket
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest
from jsonschema import validate

from arnold_pipelines.megaplan._core.io import ensure_runtime_layout
from arnold_pipelines.megaplan.workers import _impl as worker_impl
from arnold_pipelines.megaplan.audits.robustness import validate_critique_checks
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
)
from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud.providers import ssh as ssh_provider_module
from arnold_pipelines.megaplan.cloud.providers import zero_recovery
from arnold_pipelines.megaplan.cloud.providers.ssh_preflight import (
    capacity_inventory_command,
    parse_capacity_inventory_result,
)
from arnold_pipelines.megaplan.cloud.providers.ssh import (
    _ZERO_RECOVERY_CANARY_RUNTIME_FORMAT,
    _ZERO_RECOVERY_OAUTH_INSTALL_SCRIPT,
    _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT,
    _ZERO_RECOVERY_WORKSPACE_RESEAL_SCRIPT,
    SshProvider,
    _zero_recovery_canary_runtime_command,
    _require_advertised_branch_commit,
)
from arnold_pipelines.megaplan.workers._impl import (
    _assert_zero_recovery_plan_unchanged,
    _assert_zero_recovery_source_unchanged,
    _read_codex_observed_model,
    _codex_step_cost,
    _record_zero_recovery_dispatch,
    _record_zero_recovery_dispatch_terminal,
    _prepare_zero_recovery_schema_input,
    _quiesce_zero_recovery_model_uid,
    _reclaim_zero_recovery_tree,
    _restore_zero_recovery_schema_input,
    run_command,
    _zero_recovery_global_scratch_observation,
    _zero_recovery_plan_snapshot,
    _zero_recovery_runtime_usage,
    _zero_recovery_source_identity,
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
    _finite_canary_global_scratch_is_valid,
    _finite_canary_completion_contract_is_valid,
    _finite_canary_custody_contract,
    _finite_canary_conformance_has_trust_evidence,
    _finite_canary_fence_is_valid,
    _finite_canary_review_inputs_match,
)


@pytest.mark.parametrize("dev_shm", ["root_nonwritable", "absent_ipc_none"])
def test_finite_canary_receipt_accepts_only_safe_global_scratch(
    dev_shm: str,
) -> None:
    value = {
        "/tmp": "root_nonwritable",
        "/var/tmp": "root_nonwritable",
        "/dev/shm": dev_shm,
    }
    assert _finite_canary_global_scratch_is_valid(value)
    value["/tmp"] = "writable"
    assert not _finite_canary_global_scratch_is_valid(value)


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
        zero_recovery_workspace_dir=(
            "/opt/megaplan-cloud/workspace/"
            "critique-ledger-safe-v3-canary-20260802"
        ),
    )


def test_zero_profile_spec_is_strict_and_requires_distinct_predecessor(tmp_path: Path) -> None:
    base = """provider: ssh\nmode: idle\nzero_recovery_canary: true\nzero_recovery_workspace_dir: /opt/megaplan-cloud/workspace/canary-run\nrepo:\n  url: https://github.com/o/r.git\n  workspace: /workspace/Arnold\nagents:\n  default: codex\nssh:\n  host: host\n  container: canary\nsecrets: []\n"""
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


def test_bootstrap_accepts_normal_counter_drift_below_exact_byte_floor() -> None:
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
    changed["filesystem"] = {
        **changed["filesystem"],
        "free_bytes": 1,
        "free_inodes": 19,
    }
    changed_prelaunch = _prelaunch(go=False)
    changed_prelaunch["capacity"] = {"free_bytes": 1, "free_inodes": 19}
    zero_recovery.validate_bootstrap_reclaim_transaction(
        proposal, target=_target(), outer=_outer(), prelaunch=changed_prelaunch,
        inventory=changed, now=now + timedelta(seconds=1),
    )


def test_bootstrap_rejects_fresh_inventory_that_reaches_the_byte_floor() -> None:
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    proposal = zero_recovery.build_bootstrap_reclaim_transaction(
        outer=_outer(), prelaunch=_prelaunch(go=False), inventory=_inventory(),
        target=_target(), now=now,
    )
    changed = _inventory()
    changed["filesystem"] = {**changed["filesystem"], "free_bytes": 101}
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
    assert script.index("stopped_units = settle_units(before)") < script.index('prune = run(["docker", "builder", "prune", "-f"])')
    assert script.index("install_persistent_masks(before_items)") < script.index(
        'daemon_reload = run(["systemctl", "daemon-reload"])'
    )
    assert script.index(
        'daemon_reload = run(["systemctl", "daemon-reload"])'
    ) < script.index(
        "persistent_units = settle_units(before_items, require_persistent=True)"
    )
    assert script.index(
        "persistent_units = settle_units(before_items, require_persistent=True)"
    ) < script.index("jobs = require_no_recovery_unit_jobs()")
    assert script.index("os.fsync(mask_dir_fd)") < script.index(
        "persistent_units_before_prune, systemd_jobs_before_prune = ("
    )
    assert script.index(
        "persistent_units_before_prune, systemd_jobs_before_prune = ("
    ) < script.index("prune_started = True")
    assert script.index("prune_started = True") < script.index('prune = run(["docker", "builder", "prune", "-f"])')
    assert "bootstrap_fence_reclaim_failure.v1" in script
    assert "observe_inventory() != expected_inventory" not in script
    assert "capacity_inventory_changed_or_no_longer_below_floor" in script
    assert '"live_pre_inventory": pre_inventory' in script
    assert "os.O_WRONLY | os.O_CREAT | os.O_EXCL" in script
    assert '"prune_started": prune_started' in script
    assert "file=sys.stderr" in script
    for forbidden in ("docker system prune", "docker container prune", "docker image prune", "docker volume prune", "docker rm", "rm -rf", '"-a"', '"--all"'):
        assert forbidden not in script


def _remote_script_function(
    source: str, name: str, namespace: dict[str, object]
) -> dict[str, object]:
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    compiled = compile(
        ast.Module(body=[function], type_ignores=[]),
        filename=f"<remote-{name}>",
        mode="exec",
    )
    exec(compiled, namespace)
    return namespace


def _remote_bootstrap_function(
    name: str, namespace: dict[str, object]
) -> dict[str, object]:
    return _remote_script_function(
        zero_recovery._BOOTSTRAP_RECLAIM_SCRIPT, name, namespace
    )


def _remote_fence_function(
    name: str, namespace: dict[str, object]
) -> dict[str, object]:
    return _remote_script_function(zero_recovery._FENCE_SCRIPT, name, namespace)


@pytest.mark.parametrize("remote", [_remote_bootstrap_function, _remote_fence_function])
@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "expected"),
    [
        (0, "one\ntwo\n", "", ["one", "two"]),
        (1, "", "no server running on /tmp/tmux-0/default\n", []),
        (
            1,
            "",
            "error connecting to /tmp/tmux-0/default (No such file or directory)\n",
            [],
        ),
        (1, "", "failed to connect to server: No such file or directory\n", []),
    ],
)
def test_remote_tmux_observation_accepts_sessions_or_absent_server(
    remote: object,
    returncode: int,
    stdout: str,
    stderr: str,
    expected: list[str],
) -> None:
    namespace = remote(
        "observe_tmux_sessions",
        {
            "run": lambda _argv: SimpleNamespace(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            ),
            "RuntimeError": RuntimeError,
        },
    )
    assert namespace["observe_tmux_sessions"]() == expected


@pytest.mark.parametrize("remote", [_remote_bootstrap_function, _remote_fence_function])
def test_remote_tmux_observation_rejects_unknown_failure(remote: object) -> None:
    namespace = remote(
        "observe_tmux_sessions",
        {
            "run": lambda _argv: SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="permission denied\n",
            ),
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="tmux_observation_unknown"):
        namespace["observe_tmux_sessions"]()


@pytest.mark.parametrize("remote", [_remote_bootstrap_function, _remote_fence_function])
def test_remote_unit_observation_rejects_non_root_persistent_mask(
    remote: object,
) -> None:
    stat_module = __import__("stat")

    class MaskRoot:
        def __truediv__(self, _unit: str) -> str:
            return "/etc/systemd/system/unit.service"

    fake_os = SimpleNamespace(
        path=SimpleNamespace(lexists=lambda _path: True),
        lstat=lambda _path: SimpleNamespace(
            st_mode=stat_module.S_IFLNK | 0o777,
            st_uid=1,
            st_gid=0,
        ),
        readlink=lambda _path: "/dev/null",
    )
    namespace = remote(
        "show_unit",
        {
            "run": lambda *_args, **_kwargs: SimpleNamespace(
                returncode=0,
                stdout="loaded\ninactive\nmasked\n",
            ),
            "pathlib": SimpleNamespace(Path=lambda _path: MaskRoot()),
            "os": fake_os,
            "stat": stat_module,
            "RuntimeError": RuntimeError,
        },
    )
    assert namespace["show_unit"]("unit.service")["persistent_mask"] is False


def test_bootstrap_existing_persistent_mask_requires_root_identity() -> None:
    stat_module = __import__("stat")

    class MaskPath:
        name = "unit.service"

        def with_name(self, _name: str) -> "MaskPath":
            return self

    class MaskRoot:
        def __truediv__(self, _unit: str) -> MaskPath:
            return MaskPath()

    fake_os = SimpleNamespace(
        path=SimpleNamespace(lexists=lambda _path: True),
        lstat=lambda _path: SimpleNamespace(
            st_mode=stat_module.S_IFLNK | 0o777,
            st_uid=1,
            st_gid=0,
        ),
        readlink=lambda _path: "/dev/null",
    )
    namespace = _remote_bootstrap_function(
        "install_persistent_masks",
        {
            "pathlib": SimpleNamespace(Path=lambda _path: MaskRoot()),
            "os": fake_os,
            "stat": stat_module,
            "config": {"transaction_id": "tx"},
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="persistent_mask_path_conflict"):
        namespace["install_persistent_masks"]([{"unit": "unit.service"}])


def _assignment_target(node: ast.stmt) -> str | None:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id
    return None


def test_bootstrap_top_level_intent_to_unit_observation_executes() -> None:
    tree = ast.parse(zero_recovery._BOOTSTRAP_RECLAIM_SCRIPT)
    hook_index = next(
        index
        for index, node in enumerate(tree.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Attribute)
        and node.targets[0].attr == "excepthook"
    )
    start = next(
        index
        for index, node in enumerate(tree.body)
        if _assignment_target(node) == "authority_dir_fd"
        and isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
    )
    assert hook_index < start
    end = next(
        index
        for index in range(start + 1, len(tree.body))
        if _assignment_target(tree.body[index]) == "before"
    )
    calls: list[tuple[object, ...]] = []
    namespace = {
        "open_authority_directory": lambda: calls.append(("open",)) or 7,
        "authority_filename": lambda suffix: "tx" + suffix,
        "write_authority_file": lambda name, raw: calls.append(
            ("write", name, raw)
        ),
        "config": {"transaction_digest": "d" * 64},
        "sys": SimpleNamespace(excepthook=None),
        "failure_excepthook": object(),
        "failure_stage": "",
        "show_unit": lambda unit: {"unit": unit},
        "units": ["one", "two"],
    }
    exec(
        compile(
            ast.Module(body=tree.body[start : end + 1], type_ignores=[]),
            "<bootstrap-top-level-transition>",
            "exec",
        ),
        namespace,
    )
    assert namespace["authority_dir_fd"] == 7
    assert namespace["before"] == [{"unit": "one"}, {"unit": "two"}]
    assert calls[0] == ("open",)
    assert calls[1][0] == "write"


def test_fence_top_level_authority_to_unit_observation_executes() -> None:
    tree = ast.parse(zero_recovery._FENCE_SCRIPT)
    hook_index = next(
        index
        for index, node in enumerate(tree.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Attribute)
        and node.targets[0].attr == "excepthook"
    )
    authority_index = next(
        index
        for index, node in enumerate(tree.body)
        if _assignment_target(node) == "authority_dir_fd"
        and isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
    )
    assert hook_index < authority_index
    start = authority_index - 1
    assert isinstance(tree.body[start], ast.If)
    end = next(
        index
        for index in range(authority_index + 1, len(tree.body))
        if _assignment_target(tree.body[index]) == "before"
    )
    calls: list[tuple[object, ...]] = []
    namespace = {
        "action": "apply",
        "RuntimeError": RuntimeError,
        "open_authority_directory": lambda create: calls.append(
            ("open", create)
        ) or 9,
        "config": {
            "transaction_id": "tx",
            "transaction_digest": "d" * 64,
        },
        "json": json,
        "persist_or_require_exact": lambda *args: calls.append(
            ("persist", *args)
        ),
        "sys": SimpleNamespace(excepthook=None),
        "fence_failure_excepthook": object(),
        "show_unit": lambda unit: {"unit": unit},
        "units": ["one", "two"],
        "failure_stage": "",
    }
    exec(
        compile(
            ast.Module(body=tree.body[start : end + 1], type_ignores=[]),
            "<fence-top-level-transition>",
            "exec",
        ),
        namespace,
    )
    assert calls[0] == ("open", True)
    assert calls[1][0] == "persist"
    assert namespace["authority_dir_fd"] == 9
    assert namespace["before"] == [{"unit": "one"}, {"unit": "two"}]


@pytest.mark.parametrize(
    ("remote", "writer_name", "hook_name", "error", "schema"),
    [
        (
            _remote_bootstrap_function,
            "write_failure_receipt",
            "failure_excepthook",
            "authority_directory_identity_invalid",
            "arnold.cloud.zero_recovery_bootstrap_failure_envelope.v1",
        ),
        (
            _remote_fence_function,
            "write_fence_failure_receipt",
            "fence_failure_excepthook",
            "authority_directory_identity_invalid",
            "arnold.cloud.zero_recovery_host_fence_failure_envelope.v1",
        ),
        (
            _remote_fence_function,
            "write_fence_failure_receipt",
            "fence_failure_excepthook",
            "existing_fence_intent_subject_mismatch",
            "arnold.cloud.zero_recovery_host_fence_failure_envelope.v1",
        ),
    ],
)
def test_pre_intent_authority_and_conflicting_intent_failures_emit_typed_envelope(
    remote: object,
    writer_name: str,
    hook_name: str,
    error: str,
    schema: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    namespace: dict[str, object] = {
        "config": {
            "transaction_id": "tx-pre-intent",
            "transaction_digest": "d" * 64,
        },
        "authority_root": Path("/unavailable-authority"),
        "authority_dir_fd": None,
        "failure_stage": "before_intent",
        "prune_started": False,
        "marker_published": False,
        "settle_observations": [],
        "last_systemd_jobs": [],
        "last_fence_jobs": [],
        "units": [],
        "action": "apply",
        "safe_unit_observations": lambda: [],
        "safe_fence_unit_observations": lambda: [],
        "authority_filename": lambda suffix: "tx-pre-intent" + suffix,
        "datetime": datetime,
        "timezone": timezone,
        "hashlib": hashlib,
        "json": json,
        "os": os,
        "sys": sys,
    }
    remote(writer_name, namespace)
    remote(hook_name, namespace)
    namespace[hook_name](RuntimeError, RuntimeError(error), None)
    emitted = json.loads(capsys.readouterr().err.strip())
    assert emitted == {
        "schema": schema,
        "status": "failed",
        "stage": "before_intent",
        **({"action": "apply"} if "host_fence" in schema else {}),
        "transaction_id": "tx-pre-intent",
        "transaction_digest": "d" * 64,
        "error_type": "RuntimeError",
        "error": error,
        "durable_receipt_written": False,
        "durable_receipt_error": "authority_directory_unavailable",
        "failure_receipt": emitted["failure_receipt"],
    }
    assert emitted["failure_receipt"]["status"] == "failed"
    assert emitted["failure_receipt"]["stage"] == "before_intent"


class _FakeSettleTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, value: float) -> None:
        self.sleeps.append(value)
        self.now += value


def _settle_namespace(
    states: list[str], *, reset_returncode: int = 0
) -> tuple[dict[str, object], list[list[str]], _FakeSettleTime]:
    remaining = list(states)
    calls: list[list[str]] = []
    fake_time = _FakeSettleTime()

    def show_unit(
        unit: str, timeout_seconds: float | None = None
    ) -> dict[str, object]:
        assert timeout_seconds is not None and 0 < timeout_seconds <= 0.5
        active = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return {
            "unit": unit,
            "load_state": "loaded",
            "active_state": active,
            "unit_file_state": "masked-runtime",
            "persistent_mask": False,
        }

    def run(
        argv: list[str], timeout_seconds: float | None = None
    ) -> SimpleNamespace:
        assert timeout_seconds is not None and 0 < timeout_seconds <= 1.0
        calls.append(argv)
        return SimpleNamespace(returncode=reset_returncode, stdout="", stderr="")

    namespace: dict[str, object] = {
        "time": fake_time,
        "show_unit": show_unit,
        "run": run,
        "settle_observations": [],
        "RuntimeError": RuntimeError,
        "subprocess": subprocess,
        "set": set,
        "min": min,
    }
    return _remote_bootstrap_function("settle_units", namespace), calls, fake_time


def test_bootstrap_unit_settle_accepts_already_inactive_masked_unit() -> None:
    namespace, calls, fake_time = _settle_namespace(["inactive"])
    result = namespace["settle_units"](
        [{"unit": "unit.service", "load_state": "loaded"}]
    )
    assert result[0]["active_state"] == "inactive"
    assert calls == []
    assert fake_time.sleeps == []


def test_bootstrap_unit_settle_resets_failed_then_requires_inactive() -> None:
    namespace, calls, fake_time = _settle_namespace(["failed", "inactive"])
    result = namespace["settle_units"](
        [{"unit": "unit.service", "load_state": "loaded"}]
    )
    assert result[0]["active_state"] == "inactive"
    assert calls == [["systemctl", "reset-failed", "unit.service"]]
    assert fake_time.sleeps == [0.2]


def test_bootstrap_unit_settle_polls_deactivating_then_inactive() -> None:
    namespace, calls, fake_time = _settle_namespace(["deactivating", "inactive"])
    result = namespace["settle_units"](
        [{"unit": "unit.service", "load_state": "loaded"}]
    )
    assert result[0]["active_state"] == "inactive"
    assert calls == []
    assert fake_time.sleeps == [0.2]


def test_bootstrap_unit_settle_timeout_cannot_reach_prune() -> None:
    namespace, calls, fake_time = _settle_namespace(["deactivating"])
    with pytest.raises(RuntimeError, match="unit_settle_timeout"):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "loaded"}]
        )
    assert fake_time.now >= 5.0
    assert not any(argv[:3] == ["docker", "builder", "prune"] for argv in calls)


def test_bootstrap_unit_settle_reset_failure_cannot_reach_prune() -> None:
    namespace, calls, _ = _settle_namespace(["failed"], reset_returncode=1)
    with pytest.raises(RuntimeError, match="unit_reset_failed:unit.service"):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "loaded"}]
        )
    assert calls == [["systemctl", "reset-failed", "unit.service"]]
    assert not any(argv[:3] == ["docker", "builder", "prune"] for argv in calls)


def test_bootstrap_unit_settle_rejects_active_without_polling() -> None:
    namespace, calls, fake_time = _settle_namespace(["active"])
    with pytest.raises(
        RuntimeError,
        match="unit_invalid_active_state_during_settle:unit.service:active",
    ):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "loaded"}]
        )
    assert calls == []
    assert fake_time.sleeps == []


def test_bootstrap_queued_recovery_job_cannot_reach_prune() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str]) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout="42 unit.service stop running\n",
            stderr="",
        )

    namespace = _remote_bootstrap_function(
        "require_no_recovery_unit_jobs",
        {
            "run": run,
            "units": ["unit.service"],
            "last_systemd_jobs": [],
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="recovery_unit_job_queued"):
        namespace["require_no_recovery_unit_jobs"]()
    assert calls == [["systemctl", "list-jobs", "--no-legend", "--no-pager"]]
    assert not any(argv[:3] == ["docker", "builder", "prune"] for argv in calls)


def test_bootstrap_ignores_unrelated_job_and_emits_empty_recovery_jobs() -> None:
    namespace = _remote_bootstrap_function(
        "require_no_recovery_unit_jobs",
        {
            "run": lambda _argv: SimpleNamespace(
                returncode=0,
                stdout="42 unrelated.service start running\n",
                stderr="",
            ),
            "units": ["unit.service"],
            "last_systemd_jobs": [],
            "RuntimeError": RuntimeError,
        },
    )
    assert namespace["require_no_recovery_unit_jobs"]() == []


@pytest.mark.parametrize(
    "failure",
    ["persistent_install", "daemon_reload", "persistent_settle", "queued_job"],
)
def test_bootstrap_persistent_fence_failure_cannot_reach_prune(
    failure: str,
) -> None:
    calls: list[list[str]] = []

    def install(_before: list[dict[str, str]]) -> None:
        if failure == "persistent_install":
            raise RuntimeError("persistent install failed")

    def run(argv: list[str]) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(
            returncode=1 if failure == "daemon_reload" else 0,
            stdout="",
            stderr="",
        )

    def settle(
        _before: list[dict[str, str]], *, require_persistent: bool
    ) -> list[dict[str, str]]:
        assert require_persistent is True
        if failure == "persistent_settle":
            raise RuntimeError("persistent settle failed")
        return []

    def jobs() -> list[str]:
        if failure == "queued_job":
            raise RuntimeError("recovery_unit_job_queued")
        return []

    namespace = _remote_bootstrap_function(
        "establish_persistent_fence",
        {
            "failure_stage": "",
            "install_persistent_masks": install,
            "run": run,
            "settle_units": settle,
            "require_no_recovery_unit_jobs": jobs,
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError):
        namespace["establish_persistent_fence"]([])
    assert not any(argv[:3] == ["docker", "builder", "prune"] for argv in calls)


def test_bootstrap_failure_receipt_is_typed_durable_and_never_overwritten(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observations = [
        {
            "unit": unit,
            "load_state": "loaded",
            "active_state": "deactivating",
            "unit_file_state": "masked-runtime",
            "persistent_mask": False,
        }
        for unit in zero_recovery.ZERO_RECOVERY_UNITS
    ]
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    authority_dir_fd = os.open(
        authority_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )

    def write_authority_file(name: str, raw: bytes) -> None:
        fd = os.open(
            authority_root / name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)

    namespace = _remote_bootstrap_function(
        "write_failure_receipt",
        {
            "config": {
                "transaction_id": "tx-1",
                "transaction_digest": "d" * 64,
            },
            "authority_root": authority_root,
            "authority_dir_fd": authority_dir_fd,
            "authority_filename": lambda suffix: "tx-1" + suffix,
            "write_authority_file": write_authority_file,
            "failure_stage": "settle_units_before_prune",
            "prune_started": False,
            "safe_unit_observations": lambda: observations,
            "settle_observations": [observations],
            "last_systemd_jobs": [],
            "datetime": datetime,
            "timezone": timezone,
            "hashlib": hashlib,
            "json": json,
            "os": os,
            "sys": sys,
        },
    )
    writer = namespace["write_failure_receipt"]
    writer(RuntimeError, RuntimeError("unit_settle_timeout"))
    path = (
        authority_root / "tx-1.bootstrap-fence-reclaim-failure.json"
    )
    before = path.read_bytes()
    payload = json.loads(before)
    assert path.stat().st_mode & 0o777 == 0o600
    assert payload["schema"] == (
        "arnold.cloud.zero_recovery_bootstrap_fence_reclaim_failure.v1"
    )
    assert payload["stage"] == "settle_units_before_prune"
    assert payload["prune_started"] is False
    assert payload["units_observed"] == observations
    unsigned = dict(payload)
    digest = unsigned.pop("receipt_digest")
    assert digest == hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    writer(RuntimeError, RuntimeError("must-not-overwrite"))
    assert path.read_bytes() == before
    emitted = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert emitted[0]["durable_receipt_written"] is True
    assert emitted[0]["schema"] == (
        "arnold.cloud.zero_recovery_bootstrap_failure_envelope.v1"
    )
    assert emitted[0]["failure_receipt"] == payload
    assert emitted[1]["durable_receipt_written"] is False
    assert emitted[1]["durable_receipt_error"].startswith("FileExistsError:")
    os.close(authority_dir_fd)


def test_bootstrap_success_receipt_parser_binds_empty_systemd_jobs() -> None:
    transaction_id = "tx-1"
    transaction_digest = "d" * 64
    container = {"lifecycle": "stopped"}
    units = [
        {
            "unit": unit,
            "load_state": "loaded",
            "active_state": "inactive",
            "unit_file_state": "masked",
            "persistent_mask": True,
            "state": "masked",
        }
        for unit in zero_recovery.ZERO_RECOVERY_UNITS
    ]
    receipt = {
        "schema": zero_recovery.BOOTSTRAP_RECLAIM_RECEIPT_SCHEMA,
        "status": "passed",
        "transaction_id": transaction_id,
        "transaction_digest": transaction_digest,
        "command_class": "docker_dangling_build_cache_prune",
        "command_argv": ["docker", "builder", "prune", "-f"],
        "returncode": 0,
        "pre_inventory_digest": "a" * 64,
        "live_pre_inventory": {
            "schema": "arnold.cloud.ssh_capacity_inventory.v1",
            "status": "available",
            "returncode": 0,
            "errors": [],
            "mount": {"st_dev": 1},
            "filesystem": {"free_bytes": 1, "free_inodes": 2},
        },
        "pre_mount": {"st_dev": 1},
        "post_mount": {"st_dev": 1},
        "pre_free_bytes": 1,
        "pre_free_inodes": 2,
        "post_free_bytes": 3,
        "post_free_inodes": 2,
        "reclaimed_bytes_delta": 2,
        "units_before": units,
        "units_after_stop": units,
        "units_before_prune": [
            {key: value for key, value in item.items() if key != "state"}
            for item in units
        ],
        "units": units,
        "container_pre": container,
        "container_after_stop": container,
        "container_after_prune": container,
        "container": container,
        "forbidden_sessions": [],
        "forbidden_processes": [],
        "systemd_jobs_before_prune": [],
        "systemd_jobs": [],
        "observed_at": "2026-08-03T00:00:00Z",
    }
    receipt["live_pre_inventory_digest"] = hashlib.sha256(
        json.dumps(
            receipt["live_pre_inventory"], sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert zero_recovery.parse_bootstrap_reclaim_receipt(
        stdout=json.dumps(receipt),
        transaction_id=transaction_id,
        transaction_digest=transaction_digest,
        proposal_inventory_digest="a" * 64,
    ) == receipt
    hostile = dict(receipt)
    hostile["systemd_jobs"] = ["42 hostile.service start running"]
    with pytest.raises(CliError, match="strict verification"):
        zero_recovery.parse_bootstrap_reclaim_receipt(
            stdout=json.dumps(hostile),
            transaction_id=transaction_id,
            transaction_digest=transaction_digest,
            proposal_inventory_digest="a" * 64,
        )


def _fence_settle_namespace(
    states: list[str], *, reset_returncode: int = 0
) -> tuple[dict[str, object], list[list[str]], _FakeSettleTime]:
    remaining = list(states)
    calls: list[list[str]] = []
    fake_time = _FakeSettleTime()

    def show_unit(
        unit: str, timeout_seconds: float = 30
    ) -> dict[str, object]:
        assert 0 < timeout_seconds <= 0.5
        active = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return {
            "unit": unit,
            "load_state": "masked",
            "active_state": active,
            "unit_file_state": "masked",
            "persistent_mask": True,
        }

    def run(
        argv: list[str], timeout_seconds: float = 30
    ) -> SimpleNamespace:
        assert 0 < timeout_seconds <= 1.0
        calls.append(argv)
        return SimpleNamespace(returncode=reset_returncode, stdout="", stderr="")

    namespace: dict[str, object] = {
        "time": fake_time,
        "show_unit": show_unit,
        "run": run,
        "RuntimeError": RuntimeError,
        "subprocess": subprocess,
        "set": set,
        "min": min,
    }
    return _remote_fence_function("settle_units", namespace), calls, fake_time


def test_fence_unit_settle_resets_failed_then_requires_inactive() -> None:
    namespace, calls, fake_time = _fence_settle_namespace(["failed", "inactive"])
    result = namespace["settle_units"](
        [{"unit": "unit.service", "load_state": "masked"}]
    )
    assert result[0]["active_state"] == "inactive"
    assert calls == [["systemctl", "reset-failed", "unit.service"]]
    assert fake_time.sleeps == [0.2]


def test_fence_unit_settle_polls_deactivating_then_inactive() -> None:
    namespace, calls, fake_time = _fence_settle_namespace(
        ["deactivating", "inactive"]
    )
    result = namespace["settle_units"](
        [{"unit": "unit.service", "load_state": "masked"}]
    )
    assert result[0]["active_state"] == "inactive"
    assert calls == []
    assert fake_time.sleeps == [0.2]


def test_fence_unit_settle_timeout_is_finite() -> None:
    namespace, calls, fake_time = _fence_settle_namespace(["deactivating"])
    with pytest.raises(RuntimeError, match="unit_settle_timeout"):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "masked"}]
        )
    assert fake_time.now >= 5.0
    assert calls == []


def test_fence_unit_settle_rejects_active_without_polling() -> None:
    namespace, calls, fake_time = _fence_settle_namespace(["active"])
    with pytest.raises(
        RuntimeError,
        match="unit_invalid_active_state_during_settle:unit.service:active",
    ):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "masked"}]
        )
    assert calls == []
    assert fake_time.sleeps == []


def test_fence_unit_settle_reset_failure_is_fail_closed() -> None:
    namespace, calls, _ = _fence_settle_namespace(["failed"], reset_returncode=1)
    with pytest.raises(RuntimeError, match="unit_reset_failed:unit.service"):
        namespace["settle_units"](
            [{"unit": "unit.service", "load_state": "masked"}]
        )
    assert calls == [["systemctl", "reset-failed", "unit.service"]]


def test_fence_rejects_queued_recovery_unit_job() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], timeout_seconds: float = 30) -> SimpleNamespace:
        calls.append(argv)
        assert timeout_seconds == 1.0
        return SimpleNamespace(
            returncode=0,
            stdout="42 unit.service stop running\n",
            stderr="",
        )

    namespace = _remote_fence_function(
        "observe_recovery_unit_jobs",
        {
            "run": run,
            "units": ["unit.service"],
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="recovery_unit_job_queued"):
        namespace["observe_recovery_unit_jobs"]()
    assert calls == [["systemctl", "list-jobs", "--no-legend", "--no-pager"]]


def test_fence_real_emitter_and_parser_accept_apply_and_verify_receipts() -> None:
    transaction_id = "tx-fence"
    transaction_digest = "a" * 64
    marker_raw = (
        json.dumps(
            {
                "active": True,
                "profile": "ZERO_RECOVERY_NONROOT_FINITE_CANARY",
                "schema": "arnold.cloud.zero_recovery_marker.v2",
                "scope": "HOST_GLOBAL_PERSISTENT_CONTAINMENT",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    marker = {
        "path": "/var/lib/arnold-zero-recovery/active.json",
        "sha256": hashlib.sha256(marker_raw).hexdigest(),
        "uid": 0,
        "gid": 0,
        "mode": 0o600,
        "st_dev": 1,
        "st_ino": 2,
    }
    units = [
        {
            "unit": unit,
            "load_state": "not-found",
            "active_state": "inactive",
            "unit_file_state": "disabled",
            "persistent_mask": False,
            "state": "absent",
        }
        for unit in zero_recovery.ZERO_RECOVERY_UNITS
    ]
    namespace = _remote_fence_function(
        "build_fence_receipt",
        {
            "config": {
                "transaction_id": transaction_id,
                "transaction_digest": transaction_digest,
            },
            "datetime": datetime,
            "timezone": timezone,
        },
    )
    emitter = namespace["build_fence_receipt"]
    receipts = {}
    for action in ("apply", "verify"):
        emitted = emitter(action, marker, units, [], [], [])
        receipt = zero_recovery.parse_fence_receipt(
            stdout=json.dumps(emitted),
            transaction_id=transaction_id,
            transaction_digest=transaction_digest,
            stage=action,
        )
        assert receipt["systemd_jobs"] == []
        assert all(item["state"] == "absent" for item in receipt["units"])
        receipts[action] = receipt
    assert _finite_canary_fence_is_valid(receipts["verify"])
    missing_jobs = dict(receipts["verify"])
    missing_jobs.pop("systemd_jobs")
    with pytest.raises(CliError, match="schema mismatch"):
        zero_recovery.parse_fence_receipt(
            stdout=json.dumps(missing_jobs),
            transaction_id=transaction_id,
            transaction_digest=transaction_digest,
            stage="verify",
        )


def test_fence_script_orders_settle_and_job_gate_before_receipt() -> None:
    script = zero_recovery._FENCE_SCRIPT
    assert "/var/lib/arnold-zero-recovery" in script
    assert "pathlib.Path(workspace)" not in script
    assert "os.O_NOFOLLOW" in script
    assert script.index("after = settle_units(before)") < script.index(
        "systemd_jobs = observe_recovery_unit_jobs()"
    )
    assert script.index("systemd_jobs = observe_recovery_unit_jobs()") < script.index(
        "receipt = build_fence_receipt("
    )


def test_fence_receipt_reuse_is_idempotent_only_for_same_subject() -> None:
    existing = {
        "schema": "arnold.cloud.zero_recovery_host_fence.v1",
        "status": "passed",
        "stage": "apply",
        "observed_at": "2026-08-03T00:00:00Z",
    }

    def write(*_args: object) -> None:
        raise FileExistsError("immutable")

    namespace = _remote_fence_function(
        "persist_or_reuse_fence_receipt",
        {
            "json": json,
            "write_authority_file": write,
            "read_authority_file": lambda *_args: (
                (json.dumps(existing, sort_keys=True) + "\n").encode(),
                {},
            ),
            "strict_object": lambda raw, _label: json.loads(raw),
            "RuntimeError": RuntimeError,
            "FileExistsError": FileExistsError,
        },
    )
    persist = namespace["persist_or_reuse_fence_receipt"]
    current = {**existing, "observed_at": "2026-08-03T00:00:01Z"}
    assert persist(1, "receipt", current) == existing
    hostile = {**current, "stage": "verify"}
    with pytest.raises(RuntimeError, match="existing_fence_receipt_subject_mismatch"):
        persist(1, "receipt", hostile)


def test_fence_marker_accepts_only_identical_global_marker_bytes() -> None:
    transaction_id = "tx-fence"
    transaction_digest = "a" * 64

    def strict_object(raw: bytes, _label: str) -> dict[str, object]:
        value = json.loads(raw)
        assert isinstance(value, dict)
        return value

    namespace = _remote_fence_function(
        "require_expected_marker",
        {
            "config": {
                "transaction_id": transaction_id,
                "transaction_digest": transaction_digest,
            },
            "strict_object": strict_object,
            "json": json,
            "RuntimeError": RuntimeError,
        },
    )
    require_marker = namespace["require_expected_marker"]
    exact = (
        json.dumps(
            {
                "active": True,
                "profile": "ZERO_RECOVERY_NONROOT_FINITE_CANARY",
                "schema": "arnold.cloud.zero_recovery_marker.v2",
                "scope": "HOST_GLOBAL_PERSISTENT_CONTAINMENT",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert require_marker(exact)["profile"] == "ZERO_RECOVERY_NONROOT_FINITE_CANARY"
    stale = exact.replace(b"HOST_GLOBAL_PERSISTENT_CONTAINMENT", b"STALE_SCOPE")
    with pytest.raises(
        RuntimeError, match="existing_zero_recovery_marker_transaction_mismatch"
    ):
        require_marker(stale)


def test_fence_authority_directory_rejects_symlink_and_wrong_owner(
    tmp_path: Path,
) -> None:
    stat_module = __import__("stat")
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    symlink = tmp_path / "authority-link"
    symlink.symlink_to(target, target_is_directory=True)
    bootstrap_symlink_namespace = _remote_bootstrap_function(
        "open_authority_directory",
        {
            "authority_root": symlink,
            "os": os,
            "stat": stat_module,
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="authority_directory_identity_invalid"):
        bootstrap_symlink_namespace["open_authority_directory"]()
    symlink_namespace = _remote_fence_function(
        "open_authority_directory",
        {
            "authority_root": symlink,
            "os": os,
            "stat": stat_module,
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="authority_directory_identity_invalid"):
        symlink_namespace["open_authority_directory"](False)

    fake_os = SimpleNamespace(
        lstat=lambda _path: SimpleNamespace(
            st_mode=stat_module.S_IFDIR | 0o700,
            st_uid=1,
            st_gid=0,
            st_dev=1,
            st_ino=2,
        ),
        mkdir=lambda *_args: None,
        O_RDONLY=os.O_RDONLY,
        O_DIRECTORY=os.O_DIRECTORY,
        O_NOFOLLOW=os.O_NOFOLLOW,
        close=lambda _fd: None,
    )
    wrong_owner_namespace = _remote_fence_function(
        "open_authority_directory",
        {
            "authority_root": target,
            "os": fake_os,
            "stat": stat_module,
            "RuntimeError": RuntimeError,
        },
    )
    with pytest.raises(RuntimeError, match="authority_directory_identity_invalid"):
        wrong_owner_namespace["open_authority_directory"](False)


def test_fence_authority_file_rejects_symlink_and_never_overwrites(
    tmp_path: Path,
) -> None:
    stat_module = __import__("stat")
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        target = tmp_path / "target"
        target.write_text("target", encoding="utf-8")
        (tmp_path / "marker").symlink_to(target)
        reader_namespace = _remote_fence_function(
            "read_authority_file",
            {
                "os": os,
                "stat": stat_module,
                "RuntimeError": RuntimeError,
                "authority_root": tmp_path,
                "hashlib": hashlib,
            },
        )
        with pytest.raises(RuntimeError, match="authority_file_identity_invalid"):
            reader_namespace["read_authority_file"](directory_fd, "marker")

        existing = tmp_path / "receipt"
        existing.write_text("immutable", encoding="utf-8")
        before = existing.read_bytes()
        writer_namespace = _remote_fence_function(
            "write_authority_file",
            {
                "os": os,
                "stat": stat_module,
                "RuntimeError": RuntimeError,
                "read_authority_file": lambda *_args: None,
            },
        )
        with pytest.raises(FileExistsError):
            writer_namespace["write_authority_file"](
                directory_fd, "receipt", b"replacement"
            )
        assert existing.read_bytes() == before
    finally:
        os.close(directory_fd)


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


@pytest.mark.parametrize("action", ["init", "exec", "quickstart", "retire-chain", "retire-stale-status"])
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
        cloud_action=action, command="echo hostile", cloud_yaml=None, on_box=True,
        force=True,
    )
    assert cloud_cli.run_cloud_cli(tmp_path, args) == 1
    assert called is False


def test_zero_cli_denies_force_init_of_malformed_canonical_profile_before_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    canonical = (
        tmp_path
        / ".megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml"
    )
    canonical.parent.mkdir(parents=True)
    malformed = "zero_recovery_canary: [malformed\n"
    canonical.write_text(malformed, encoding="utf-8")
    monkeypatch.setattr(
        cloud_cli,
        "_run_init",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("canonical profile must not reach init")
        ),
    )
    args = argparse.Namespace(
        cloud_action="init", cloud_yaml=str(canonical), force=True
    )
    assert cloud_cli.run_cloud_cli(tmp_path, args) == 1
    assert canonical.read_text(encoding="utf-8") == malformed


@pytest.mark.parametrize("action", ["build", "deploy", "reclaim-dangling-build-cache"])
def test_zero_mutations_require_manifest_admission_before_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, action: str
) -> None:
    (tmp_path / "cloud.yaml").write_text("zero-profile", encoding="utf-8")
    monkeypatch.setattr(cloud_cli, "_load_cloud_spec", lambda root, args: _spec())
    admitted = False
    provider_called = False

    def admission(*args, **kwargs):
        nonlocal admitted
        admitted = True
        raise CliError("zero_recovery_canary_invalid", "blocked before mutation")

    def provider(*args, **kwargs):
        nonlocal provider_called
        provider_called = True
        raise AssertionError("provider must not be created")

    monkeypatch.setattr(cloud_cli, "_validate_zero_recovery_canary_spec", admission)
    monkeypatch.setattr(cloud_cli, "_provider_for_action", provider)
    args = argparse.Namespace(
        cloud_action=action, cloud_yaml=None, apply=True,
    )
    assert cloud_cli.run_cloud_cli(tmp_path, args) == 1
    assert admitted is True
    assert provider_called is False


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
    assert "/workspace/.creds" not in source

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
        tmp_path,
        start=start,
        worker=SimpleNamespace(
            model_actual="gpt-5.6-sol", model_evidence="codex_cli_turn_context",
            privilege_receipt_path=".zero-recovery-plan-privilege-receipt.json",
            privilege_receipt_sha256="a" * 64,
            rollout_path="sessions/2026/08/03/rollout-session.jsonl",
            rollout_sha256="b" * 64,
        ),
    )
    rows = [json.loads(line) for line in (tmp_path / "zero_recovery_dispatch_ledger.ndjson").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["start", "terminal"]
    assert rows[0]["dispatch_id"] == rows[1]["dispatch_id"]
    with pytest.raises(CliError, match="second plan dispatch"):
        _record_zero_recovery_dispatch(
            tmp_path, step="plan", agent="codex", model="gpt-5.6-sol", effort="high"
        )
    with pytest.raises(CliError, match="admitted model boundary"):
        _record_zero_recovery_dispatch_terminal(
            tmp_path,
            start=start,
            worker=SimpleNamespace(
                model_actual="other", model_evidence="codex_cli_turn_context",
                privilege_receipt_path="x", privilege_receipt_sha256="a" * 64,
                rollout_path="sessions/x", rollout_sha256="b" * 64,
            ),
        )
    with pytest.raises(CliError, match="admitted model boundary"):
        _record_zero_recovery_dispatch_terminal(
            tmp_path,
            start=start,
            worker=SimpleNamespace(model_actual="gpt-5.6-sol", model_evidence=None),
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
        "systemd_jobs": [],
        "observed_at": "2026-08-03T00:00:00Z",
    }
    assert _finite_canary_fence_is_valid(forged_fence) is False
    forged_fence["stage"] = "verify"
    forged_fence["units"] = [
        {
            "unit": unit, "load_state": "loaded", "active_state": "active",
            "unit_file_state": "enabled", "state": "masked",
        }
        for unit in zero_recovery.ZERO_RECOVERY_UNITS
    ]
    assert _finite_canary_fence_is_valid(forged_fence) is False

    self_attested = {
        "schema": "arnold.megaplan.finite_canary_conformance_receipt.v1",
        "status": "passed",
        "subject": {"canary_id": "forged"},
        "run_receipt_sha256": "b" * 64,
        "checks": ["exact_phase_order"],
    }
    assert _finite_canary_conformance_has_trust_evidence(self_attested) is False


def test_complete_recomputed_but_fake_reviewer_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "arnold_pipelines/megaplan/chain/spec.py"
    source.parent.mkdir(parents=True)
    source.write_text("trusted validator", encoding="utf-8")
    actual_source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    forged = {
        "schema": "arnold.megaplan.finite_canary_conformance_receipt.v1",
        "status": "passed", "subject": {"canary_id": "forged"},
        "run_receipt_sha256": "b" * 64,
        "checks": ["exact_phase_order", "single_dispatch_pairs", "terminal_finalized", "artifact_hashes", "zero_recovery_fence"],
        "reviewer": {
            "kind": "detached_host_process",
            "identity": "arnold.chain.finite_canary_validator",
            "source_sha256": "a" * 64,
        },
        "reviewed_at": "2026-08-03T00:00:00Z",
        "trust_anchor": "arnold.detached_host_reviewer.v1",
        "review_input_sha256": {"detached_reviewer_source": "a" * 64},
        "review_execution": {"mode": "detached_subprocess", "exit_code": 0, "result": "passed"},
    }
    forged["attestation_digest"] = hashlib.sha256(
        json.dumps(forged, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert _finite_canary_conformance_has_trust_evidence(forged) is True
    assert not _finite_canary_review_inputs_match(
        forged,
        {"detached_reviewer_source": (source.resolve(), actual_source_hash)},
        tmp_path,
    )


def test_codex_actual_model_comes_from_rollout_not_requested_value(tmp_path: Path) -> None:
    assert _codex_step_cost(None, {}, "gpt-requested")[3] is None
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        json.dumps({"type": "turn_context", "payload": {"model": "gpt-provider-actual"}})
        + "\n",
        encoding="utf-8",
    )
    assert _read_codex_observed_model(rollout) == "gpt-provider-actual"
    from arnold_pipelines.megaplan.workers import _impl as worker_impl

    original = worker_impl._codex_session_jsonl_path
    worker_impl._codex_session_jsonl_path = lambda _session, **_kwargs: rollout
    try:
        assert _codex_step_cost("session", {}, "gpt-requested")[3] == "gpt-provider-actual"
    finally:
        worker_impl._codex_session_jsonl_path = original
    rollout.write_text('{"type":"turn_context","payload":{}}\n', encoding="utf-8")
    assert _read_codex_observed_model(rollout) is None


def test_malformed_status_still_reconciles_observed_stopped_exact_canary() -> None:
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
            {"status": "available", "container": provider._ssh.container, "lifecycle": "stopped"},
            {"status": "available", "container": provider._ssh.container, "lifecycle": "stopped"},
        ]
    )
    provider._remote_run_compatible = remote
    provider.observe_container = lambda: next(observations)
    provider._observe_zero_recovery_canary_runtime = lambda **kwargs: {}
    provider._reseal_zero_recovery_workspace = lambda _runtime: {}
    payload = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )
    assert payload["status"] == "unknown"
    assert payload["reconciled_stop"] is True
    assert sum(shlex.split(command)[:2] == ["docker", "stop"] for command in commands) == 1


def test_status_poll_never_stops_running_canary_without_receipt() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    commands: list[str] = []

    def remote(command: str, **kwargs):
        commands.append(command)
        assert command.startswith("python3 ")
        envelope = {
            "schema": "arnold.cloud.zero_recovery_canary_status.v1",
            "receipt_b64": None,
            "receipt_sha256": None,
            "receipt_count": 0,
        }
        return subprocess.CompletedProcess([], 0, json.dumps(envelope), "")

    provider._remote_run_compatible = remote
    provider.observe_container = lambda: {
        "status": "available",
        "container": provider._ssh.container,
        "lifecycle": "running",
    }
    provider._reconcile_zero_recovery_canary_stop = lambda: (_ for _ in ()).throw(
        AssertionError("status poll attempted terminal reconciliation")
    )

    payload = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )

    assert payload["status"] == "in_progress"
    assert payload["reconciled_stop"] is False
    assert payload["container_observation"]["lifecycle"] == "running"
    assert not any(
        shlex.split(command)[:2] == ["docker", "stop"] for command in commands
    )


def _valid_zero_recovery_status_receipt() -> bytes:
    payload = {
        "schema": "arnold.megaplan.finite_canary_run_receipt.v2",
        "status": "passed",
        "canary_id": "critique-ledger-safe-v3-canary",
        "plan_name": "critique-ledger-cl2-planning-canary",
        "phases": ["init", "plan", "critique", "gate", "finalize"],
        "phase_results": [
            {"phase": phase} for phase in ("init", "plan", "critique", "gate", "finalize")
        ],
        "terminal_state": "finalized",
        "failure": None,
        "started_at": "2026-08-03T00:00:00Z",
        "completed_at": "2026-08-03T00:01:00Z",
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "canary_spec_sha256": "c" * 64,
        "launch_manifest_sha256": {},
        "state_sha256": "d" * 64,
        "gate_sha256": "e" * 64,
        "dispatch_ledger_sha256": "f" * 64,
        "dispatches": [],
        "import_root": "/workspace/Arnold/arnold_pipelines/megaplan/__init__.py",
        "dispatch_integrity": "complete",
        "phase_commands": [],
        "phase_receipt_sha256": [],
        "phase_receipts_manifest_sha256": "1" * 64,
        "repository_integrity": [],
        "privilege_receipt_sha256": [],
        "privilege_receipts_manifest_sha256": "2" * 64,
    }
    payload["receipt_digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_running_receipt_is_nonterminal_until_stopped_and_resealed() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    commands: list[str] = []
    raw = _valid_zero_recovery_status_receipt()

    def remote(command: str, **kwargs):
        commands.append(command)
        if command.startswith("python3 "):
            envelope = {
                "schema": "arnold.cloud.zero_recovery_canary_status.v1",
                "receipt_b64": base64.b64encode(raw).decode("ascii"),
                "receipt_sha256": hashlib.sha256(raw).hexdigest(),
                "receipt_count": 1,
            }
            return subprocess.CompletedProcess([], 0, json.dumps(envelope), "")
        return subprocess.CompletedProcess([], 0, "", "")

    observations = iter(
        [
            {"status": "available", "container": provider._ssh.container, "lifecycle": "running"},
            {"status": "available", "container": provider._ssh.container, "lifecycle": "stopped"},
            {"status": "available", "container": provider._ssh.container, "lifecycle": "stopped"},
        ]
    )
    provider._remote_run_compatible = remote
    provider.observe_container = lambda: next(observations)
    provider._observe_zero_recovery_canary_runtime = lambda **kwargs: {}
    def reseal(_runtime):
        receipt = {"status": "sealed"}
        provider._zero_recovery_terminal_workspace_receipt = receipt
        return receipt

    provider._reseal_zero_recovery_workspace = reseal

    running = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )
    stopped = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )

    assert running["status"] == "in_progress"
    assert running["receipt"]["status"] == "passed"
    assert running["reconciled_stop"] is False
    assert stopped["status"] == "available"
    assert stopped["reconciled_stop"] is True
    assert stopped["terminal_workspace"] == {"status": "sealed"}
    assert sum(
        shlex.split(command)[:2] == ["docker", "stop"] for command in commands
    ) == 1


@pytest.mark.parametrize(
    "status_stdout",
    [
        "not-json",
        json.dumps(
            {
                "schema": "arnold.cloud.zero_recovery_canary_status.v1",
                "receipt_b64": None,
                "receipt_sha256": None,
                "receipt_count": 2,
            }
        ),
    ],
)
def test_running_malformed_or_duplicate_receipt_is_non_cancelling(
    status_stdout: str,
) -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    commands: list[str] = []
    provider._remote_run_compatible = lambda command, **kwargs: (
        commands.append(command)
        or subprocess.CompletedProcess([], 0, status_stdout, "")
    )
    provider.observe_container = lambda: {
        "status": "available",
        "container": provider._ssh.container,
        "lifecycle": "running",
    }

    payload = provider.zero_recovery_canary_status(
        source_commit="a" * 40, source_tree="b" * 40
    )

    assert payload["status"] == "in_progress"
    assert payload["reconciled_stop"] is False
    assert not any(
        shlex.split(command)[:2] == ["docker", "stop"] for command in commands
    )


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
            '{"auth_mode":"chatgpt"}', source_commit="a" * 40,
            source_tree="b" * 40, manifest_sha256={},
        )
    assert [shlex.split(command) for command in commands] == [
        ["docker", "stop", provider._ssh.container]
    ]


@pytest.mark.parametrize("read_failure", [SystemExit("read aborted"), None])
def test_status_only_reconciles_after_observed_stopped_state(read_failure) -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    commands: list[str] = []

    def remote(command: str, **kwargs):
        commands.append(command)
        if command.startswith("python3 "):
            if read_failure is not None:
                raise read_failure
            return subprocess.CompletedProcess([], 0, "not-json", "")
        return subprocess.CompletedProcess([], 0, "", "")

    provider._remote_run_compatible = remote
    if read_failure is None:
        provider.observe_container = lambda: (_ for _ in ()).throw(
            RuntimeError("observation failed")
        )
        expected = RuntimeError
    else:
        provider.observe_container = lambda: {
            "status": "available", "container": provider._ssh.container,
            "lifecycle": "stopped",
        }
        provider._observe_zero_recovery_canary_runtime = lambda **kwargs: {}
        provider._reseal_zero_recovery_workspace = lambda _runtime: {}
        expected = SystemExit
    with pytest.raises(expected):
        provider.zero_recovery_canary_status(
            source_commit="a" * 40, source_tree="b" * 40
        )
    stop_command = ["docker", "stop", provider._ssh.container]
    parsed_commands = [shlex.split(command) for command in commands]
    if read_failure is None:
        assert stop_command not in parsed_commands
    else:
        assert stop_command in parsed_commands


def test_isolated_workspace_creator_is_single_use_empty_nofollow_and_custodied(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "workspace"
    parent.mkdir()
    child = parent / "canary-run"
    argv = [
        "python3", "-c", _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT,
        str(parent), str(child),
    ]
    assert "os.mkdir(name, 0o700" in _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT
    assert "os.fchown(child_fd, 0, 65532)" in _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT
    if os.geteuid() != 0:
        pytest.skip("numeric root custody transition requires a root Linux host")
    created = subprocess.run(argv, text=True, capture_output=True, check=True)
    payload = json.loads(created.stdout)
    assert payload == {
        "schema": "arnold.cloud.zero_recovery_isolated_workspace.v1",
        "status": "created",
        "parent": str(parent),
        "parent_realpath": str(parent),
        "bind_source": str(child),
        "bind_source_realpath": str(child),
        "bind_destination": "/workspace",
        "initial_custody": payload["initial_custody"],
        "runtime_access": payload["runtime_access"],
        "transition_digest": payload["transition_digest"],
        "created_empty": True,
        "never_reused": True,
    }
    assert payload["initial_custody"]["mode"] == "0700"
    assert payload["runtime_access"]["mode"] == "0750"
    assert (os.lstat(child).st_mode & 0o777) == 0o750
    assert list(child.iterdir()) == []
    assert subprocess.run(argv, text=True, capture_output=True).returncode != 0

    symlink_child = parent / "symlink-run"
    symlink_child.symlink_to(tmp_path)
    assert subprocess.run(
        ["python3", "-c", _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT,
         str(parent), str(symlink_child)],
        text=True, capture_output=True,
    ).returncode != 0

    nonempty_child = parent / "nonempty-run"
    nonempty_child.mkdir()
    (nonempty_child / "prior").write_text("historical", encoding="utf-8")
    assert subprocess.run(
        ["python3", "-c", _ZERO_RECOVERY_WORKSPACE_PREP_SCRIPT,
         str(parent), str(nonempty_child)],
        text=True, capture_output=True,
    ).returncode != 0

    sealed = subprocess.run(
        [
            "python3", "-c", _ZERO_RECOVERY_WORKSPACE_RESEAL_SCRIPT,
            str(child), str(payload["runtime_access"]["st_dev"]),
            str(payload["runtime_access"]["st_ino"]),
            payload["transition_digest"],
        ],
        text=True, capture_output=True, check=True,
    )
    terminal = json.loads(sealed.stdout)
    assert terminal["status"] == "sealed"
    assert terminal["transition"]["after"] == {
        "st_dev": payload["runtime_access"]["st_dev"],
        "st_ino": payload["runtime_access"]["st_ino"],
        "uid": 0,
        "gid": 0,
        "mode": "0700",
    }


def test_runtime_workspace_identity_reconstructs_exact_creation_receipt() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    initial = {
        "mode": "0700", "uid": 0, "gid": 0,
        "st_dev": 12, "st_ino": 34, "empty": True,
    }
    runtime_access = {
        "mode": "0750", "uid": 0, "gid": 65532,
        "st_dev": 12, "st_ino": 34,
    }
    digest = hashlib.sha256(
        json.dumps(
            {"initial_custody": initial, "runtime_access": runtime_access},
            sort_keys=True, separators=(",", ":"),
        ).encode()
    ).hexdigest()
    observation = {
        "env": [
            "ZERO_RECOVERY_WORKSPACE_DEV=12",
            "ZERO_RECOVERY_WORKSPACE_INO=34",
            f"ZERO_RECOVERY_WORKSPACE_TRANSITION_DIGEST={digest}",
        ]
    }
    receipt = provider._zero_recovery_workspace_creation_from_runtime(observation)
    assert receipt["initial_custody"] == initial
    assert receipt["runtime_access"] == runtime_access
    assert receipt["transition_digest"] == digest
    observation["env"][-1] = "ZERO_RECOVERY_WORKSPACE_TRANSITION_DIGEST=" + "0" * 64
    with pytest.raises(CliError, match="transition binding"):
        provider._zero_recovery_workspace_creation_from_runtime(observation)


def test_zero_deploy_mounts_only_fresh_child_without_shared_caches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = SshProvider(_spec())
    provider._consumed_zero_recovery_transactions = set()
    transaction = {"transaction_id": "tx", "transaction_digest": "d" * 64}
    monkeypatch.setattr(
        ssh_provider_module, "validate_predeploy_transaction",
        lambda *args, **kwargs: transaction,
    )
    monkeypatch.setattr(ssh_provider_module, "fence_command", lambda *args, **kwargs: "fence")
    monkeypatch.setattr(ssh_provider_module, "parse_fence_receipt", lambda *args, **kwargs: {})
    provider.observe_zero_recovery_predecessor = lambda: {}
    provider.observe_zero_recovery_predecessor_capacity = lambda: {}
    provider.observe_container = lambda: {"lifecycle": "missing"}
    provider._prepare_zero_recovery_isolated_workspace = lambda: {
        "bind_source": provider._spec.zero_recovery_workspace_dir,
        "runtime_access": {"st_dev": 12, "st_ino": 34},
        "transition_digest": "e" * 64,
    }
    runtime_checks: list[bool] = []
    provider._observe_zero_recovery_canary_runtime = lambda **kwargs: runtime_checks.append(True) or {}
    calls: list[tuple[str, str]] = []

    def remote(command: str, **kwargs):
        calls.append((kwargs["surface"], command))
        return subprocess.CompletedProcess([], 0, "{}\n", "")

    provider._remote_run_compatible = remote
    assert provider._deploy_direct(tmp_path, secrets={}, predeploy_transaction=transaction) == 0
    run_command = next(command for surface, command in calls if surface == "deploy_run")
    argv = shlex.split(run_command)
    assert argv[:3] == ["docker", "run", "-d"]
    assert "--restart" in argv and argv[argv.index("--restart") + 1] == "no"
    assert "--init" in argv
    mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "-v"]
    assert mounts == [
        f"{provider._spec.zero_recovery_workspace_dir}:/workspace"
    ]
    assert provider._ssh.workspace_dir + ":/workspace" not in mounts
    assert all(provider._ssh.cache_dir not in value for value in mounts)
    assert "/var/run/docker.sock" not in run_command
    assert "--privileged" not in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--pids-limit") + 1] == "256"
    assert argv[argv.index("--memory") + 1] == "4g"
    assert argv[argv.index("--memory-swap") + 1] == "4g"
    assert "-p" not in argv
    assert runtime_checks == [True]


def test_runtime_rejects_any_mount_beyond_exact_isolated_workspace() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider._ssh = provider._spec.ssh
    exact_mount = {
        "Type": "bind",
        "Source": provider._spec.zero_recovery_workspace_dir,
        "Destination": "/workspace",
        "RW": True,
        "Propagation": "rprivate",
    }

    def output(mounts: list[dict[str, object]]) -> str:
        return "\n".join(json.dumps(value) for value in (
            {"Running": True},
            ["MEGAPLAN_ZERO_RECOVERY_CANARY=1"],
            ["/usr/local/bin/entrypoint.sh"],
            {"Name": "no", "MaximumRetryCount": 0},
            True,
            mounts,
            ["ALL"],
            [
                "CAP_CHOWN", "CAP_DAC_READ_SEARCH", "CAP_KILL",
                "CAP_SETGID", "CAP_SETPCAP", "CAP_SETUID",
            ],
            ["no-new-privileges:true"],
            "none",
            {"/run/megaplan-zero-recovery": "rw,noexec,nosuid,nodev,size=256m,mode=0711"},
            256,
            4_294_967_296,
            4_294_967_296,
            {},
        ))

    provider._remote_run_compatible = lambda *args, **kwargs: subprocess.CompletedProcess(
        [], 0, output([exact_mount]), ""
    )
    observed = provider._observe_zero_recovery_canary_runtime()
    assert observed["host_bind_count"] == 1
    assert observed["init"] is True
    assert observed["cap_add"] == [
        "CHOWN", "DAC_READ_SEARCH", "KILL", "SETGID", "SETPCAP", "SETUID"
    ]
    provider._remote_run_compatible = lambda *args, **kwargs: subprocess.CompletedProcess(
        [], 0, output([
            exact_mount,
            {"Type": "bind", "Source": provider._ssh.workspace_dir,
             "Destination": "/historical", "RW": True},
        ]), ""
    )
    with pytest.raises(CliError, match="runtime"):
        provider._observe_zero_recovery_canary_runtime()


def test_zero_recovery_global_scratch_accepts_absent_dev_shm_under_ipc_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_lstat(path: os.PathLike[str] | str) -> SimpleNamespace:
        if Path(path) == Path("/dev/shm"):
            raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)

    monkeypatch.setattr(os, "lstat", fake_lstat)
    assert _zero_recovery_global_scratch_observation() == {
        "/tmp": "root_nonwritable",
        "/var/tmp": "root_nonwritable",
        "/dev/shm": "absent_ipc_none",
    }


def test_zero_recovery_global_scratch_still_requires_tmp_and_var_tmp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_lstat(path: os.PathLike[str] | str) -> SimpleNamespace:
        if Path(path) == Path("/tmp"):
            raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)

    monkeypatch.setattr(os, "lstat", fake_lstat)
    with pytest.raises(CliError, match="required global scratch path is absent"):
        _zero_recovery_global_scratch_observation()


def test_zero_recovery_runtime_seeds_private_files_before_directory_handoff() -> None:
    source = Path("arnold_pipelines/megaplan/workers/_impl.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _prepare_zero_recovery_model_runtime(")
    end = source.index("\ndef _reclaim_zero_recovery_tree", start)
    prepare = source[start:end]
    seed = prepare.index("_zero_recovery_copy_private_file(")
    handoff = prepare.index(
        "os.chown(directory, _ZERO_RECOVERY_MODEL_UID, _ZERO_RECOVERY_MODEL_GID)"
    )
    runtime_handoff = prepare.index(
        "os.chown(runtime, _ZERO_RECOVERY_MODEL_UID, _ZERO_RECOVERY_MODEL_GID)"
    )
    assert seed < handoff < runtime_handoff

    copy_start = source.index("def _zero_recovery_copy_private_file(")
    copy_end = source.index("\ndef _prepare_zero_recovery_model_runtime", copy_start)
    copy = source[copy_start:copy_end]
    assert copy.index("os.fchmod(fd, 0o600)") < copy.index("os.fchown(fd,")
    assert prepare.index("os.fchmod(output_fd, 0o600)") < prepare.index(
        "os.fchown(output_fd,"
    )
    assert '".megaplan/worker_tmp"' in source
    assert "any surviving" in source

    reclaim_start = source.index("def _reclaim_zero_recovery_tree(")
    reclaim_end = source.index("\ndef _zero_recovery_runtime_usage", reclaim_start)
    reclaim = source[reclaim_start:reclaim_end]
    assert reclaim.index("os.chown(path, 0, 0") < reclaim.index("with os.scandir(path)")

    verify_start = source.index("def _verify_zero_recovery_worker_boundaries(")
    verify_end = source.index("\ndef _record_zero_recovery_dispatch", verify_start)
    verify = source[verify_start:verify_end]
    finish = verify.index("_finish_zero_recovery_model_runtime(")
    source_check = verify.index("_assert_zero_recovery_source_unchanged(")
    revoke = verify.index("_restore_zero_recovery_schema_input(")
    assert finish < revoke < source_check

    run_start = source.index("def _run_codex_step_uncapped(")
    run_end = source.index("\ndef run_codex_step(", run_start)
    run = source[run_start:run_end]
    baseline = run.index("worker_source_before = _zero_recovery_source_identity(")
    grant = run.index("schema_grant = _prepare_zero_recovery_schema_input(")
    outer_quiesce = run.rindex("_quiesce_zero_recovery_model_uid()")
    outer_revoke = run.rindex("_restore_zero_recovery_schema_input(schema_grant)")
    assert baseline < grant < outer_quiesce < outer_revoke


def test_zero_recovery_schema_grant_is_exact_root_owned_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schema = tmp_path / "plan.json"
    schema.write_text("{}\n", encoding="utf-8")
    real_lstat = os.lstat
    real_fstat = os.fstat
    real_fchmod = os.fchmod
    identity = real_lstat(schema)
    mode = 0o600

    def fake_lstat(path: os.PathLike[str] | str) -> SimpleNamespace | os.stat_result:
        if Path(path) != schema:
            return real_lstat(path)
        return SimpleNamespace(
            st_mode=stat.S_IFREG | mode,
            st_nlink=1,
            st_uid=0,
            st_gid=0,
            st_dev=identity.st_dev,
            st_ino=identity.st_ino,
        )

    def fake_fstat(fd: int) -> SimpleNamespace:
        observed = real_fstat(fd)
        return SimpleNamespace(
            st_mode=stat.S_IFREG | mode,
            st_nlink=1,
            st_uid=0,
            st_gid=0,
            st_dev=observed.st_dev,
            st_ino=observed.st_ino,
        )

    def fake_fchmod(fd: int, granted_mode: int) -> None:
        nonlocal mode
        real_fchmod(fd, granted_mode)
        mode = granted_mode

    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "lstat", fake_lstat)
    monkeypatch.setattr(os, "fstat", fake_fstat)
    monkeypatch.setattr(os, "fchmod", fake_fchmod)

    grant = _prepare_zero_recovery_schema_input(schema)
    assert grant is not None
    assert mode == 0o644
    _restore_zero_recovery_schema_input(grant)
    assert mode == 0o600


def test_zero_recovery_schema_grant_rejects_writable_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schema = tmp_path / "plan.json"
    schema.write_text("{}\n", encoding="utf-8")
    identity = os.lstat(schema)
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        os,
        "lstat",
        lambda _path: SimpleNamespace(
            st_mode=stat.S_IFREG | 0o666,
            st_nlink=1,
            st_uid=0,
            st_gid=0,
            st_dev=identity.st_dev,
            st_ino=identity.st_ino,
        ),
    )
    with pytest.raises(CliError, match="root-owned immutable"):
        _prepare_zero_recovery_schema_input(schema)


def test_zero_recovery_schema_grant_reseals_when_post_grant_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = tmp_path / "plan.json"
    schema.write_text("{}\n", encoding="utf-8")
    identity = os.lstat(schema)
    real_fstat = os.fstat
    real_fchmod = os.fchmod
    mode = 0o600
    chmod_calls: list[int] = []

    def root_stat(*, nlink: int = 1) -> SimpleNamespace:
        return SimpleNamespace(
            st_mode=stat.S_IFREG | mode,
            st_nlink=nlink,
            st_uid=0,
            st_gid=0,
            st_dev=identity.st_dev,
            st_ino=identity.st_ino,
        )

    def fake_fstat(fd: int) -> SimpleNamespace:
        observed = real_fstat(fd)
        assert (observed.st_dev, observed.st_ino) == (
            identity.st_dev,
            identity.st_ino,
        )
        return root_stat(nlink=2 if mode == 0o644 else 1)

    def fake_fchmod(fd: int, granted_mode: int) -> None:
        nonlocal mode
        real_fchmod(fd, granted_mode)
        mode = granted_mode
        chmod_calls.append(granted_mode)

    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "lstat", lambda _path: root_stat())
    monkeypatch.setattr(os, "fstat", fake_fstat)
    monkeypatch.setattr(os, "fchmod", fake_fchmod)

    with pytest.raises(CliError, match="did not seal exact identity"):
        _prepare_zero_recovery_schema_input(schema)

    assert chmod_calls == [0o644, 0o600]
    assert mode == 0o600


def test_zero_recovery_boundary_revokes_at_empty_milestone_before_late_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []

    def late_failure(
        _runtime: dict[str, object] | None,
        *,
        output_path: Path,
        on_process_empty: Callable[[], None] | None,
    ) -> None:
        assert output_path == tmp_path / "output.json"
        assert on_process_empty is not None
        events.append("empty")
        on_process_empty()
        raise CliError("seeded_late_failure", "after process emptiness")

    monkeypatch.setattr(
        worker_impl, "_finish_zero_recovery_model_runtime", late_failure
    )
    monkeypatch.setattr(
        worker_impl,
        "_restore_zero_recovery_schema_input",
        lambda _grant: events.append("revoke"),
    )
    monkeypatch.setattr(
        worker_impl,
        "_assert_zero_recovery_source_unchanged",
        lambda _root, _plan_dir, _before: events.append("source"),
    )
    monkeypatch.setattr(
        worker_impl,
        "_assert_zero_recovery_plan_unchanged",
        lambda _root, _plan_dir, *, output_path, before: events.append("plan"),
    )

    with pytest.raises(CliError, match="after process emptiness"):
        worker_impl._verify_zero_recovery_worker_boundaries(
            root=tmp_path,
            plan_dir=tmp_path / "plan",
            output_path=tmp_path / "output.json",
            runtime={"step": "plan"},
            schema_grant={"path": tmp_path / "schema.json"},
            source_before={},
            plan_before={},
        )

    assert events == ["empty", "revoke", "source", "plan"]


def test_zero_recovery_quiescence_rekills_then_requires_consecutive_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = iter(
        [
            "101 1 S Mon Aug  3 07:00:00 2026\n",
            "101 1 Z Mon Aug  3 07:00:00 2026\n",
            "",
            "",
        ]
    )
    kills: list[list[str]] = []

    def fake_run(argv, **kwargs):
        if argv[0] == "/usr/bin/ps":
            return subprocess.CompletedProcess(argv, 0, next(observations), "")
        assert argv[0] == "/bin/kill"
        kills.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monotonic = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr(worker_impl.subprocess, "run", fake_run)
    monkeypatch.setattr(worker_impl.time, "monotonic", lambda: next(monotonic))
    monkeypatch.setattr(worker_impl.time, "sleep", lambda _seconds: None)

    _quiesce_zero_recovery_model_uid()

    assert kills == [["/bin/kill", "-KILL", "101"]]


@pytest.mark.parametrize(
    ("process_state", "classification"),
    [("Z", "unreaped zombies"), ("S", "surviving processes")],
)
def test_zero_recovery_quiescence_reports_exact_persistent_process(
    monkeypatch: pytest.MonkeyPatch,
    process_state: str,
    classification: str,
) -> None:
    def fake_run(argv, **kwargs):
        if argv[0] == "/usr/bin/ps":
            return subprocess.CompletedProcess(
                argv,
                0,
                f"202 7 {process_state} Mon Aug  3 07:01:00 2026\n",
                "",
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monotonic = iter([0.0, 6.0])
    monkeypatch.setattr(worker_impl.subprocess, "run", fake_run)
    monkeypatch.setattr(worker_impl.time, "monotonic", lambda: next(monotonic))

    with pytest.raises(CliError) as exc:
        _quiesce_zero_recovery_model_uid()

    detail = str(exc.value)
    assert classification in detail
    assert "pid=202 ppid=7" in detail
    assert f"stat={process_state}" in detail
    assert "started=Mon Aug  3 07:01:00 2026" in detail


def test_zero_recovery_runtime_accounts_for_and_seals_inert_unix_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ownership: list[tuple[Path, int, int, bool]] = []
    monkeypatch.setattr(
        os,
        "chown",
        lambda path, uid, gid, *, follow_symlinks: ownership.append(
            (Path(path), uid, gid, follow_symlinks)
        ),
    )
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="zr-") as temporary:
        runtime = Path(temporary) / "runtime"
        runtime.mkdir()
        ipc = runtime / "ipc.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(ipc))
        finally:
            listener.close()

        assert _zero_recovery_runtime_usage(runtime) == (1, 0)
        _reclaim_zero_recovery_tree(runtime)
        socket_stat = os.lstat(ipc)
        assert stat.S_ISSOCK(socket_stat.st_mode)
        assert stat.S_IMODE(socket_stat.st_mode) == 0o600
        assert (ipc, 0, 0, False) in ownership


def test_zero_recovery_runtime_accounts_for_and_unlinks_ephemeral_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(os, "chown", lambda *_args, **_kwargs: None)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    target = tmp_path / "outside-target"
    target.write_text("trusted", encoding="utf-8")
    alias = runtime / "alias"
    alias.symlink_to(target)

    assert _zero_recovery_runtime_usage(runtime) == (
        1,
        len(os.fsencode(str(target))),
    )
    _reclaim_zero_recovery_tree(runtime)
    assert not alias.exists() and not alias.is_symlink()
    assert target.read_text(encoding="utf-8") == "trusted"


def test_zero_recovery_runtime_still_rejects_fifo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(os, "chown", lambda *_args, **_kwargs: None)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    fifo = runtime / "fifo"
    os.mkfifo(fifo)

    with pytest.raises(CliError, match="forbidden or linked object"):
        _zero_recovery_runtime_usage(runtime)
    with pytest.raises(CliError, match="forbidden filesystem object"):
        _reclaim_zero_recovery_tree(runtime)


def test_streaming_run_command_reuses_and_removes_its_single_stdin_file(
    tmp_path: Path,
) -> None:
    result = run_command(
        ["/bin/cat", "-"],
        cwd=tmp_path,
        stdin_text="sealed prompt\n",
        activity_guard=lambda _kind, _text: None,
        timeout=5,
    )
    assert result.returncode == 0
    assert result.stdout == "sealed prompt\n"
    worker_tmp = tmp_path / ".megaplan/worker_tmp"
    assert worker_tmp.is_dir()
    assert list(worker_tmp.iterdir()) == []


def _git_canary_fixture(root: Path) -> tuple[str, str, Path]:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "canary@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Canary"], cwd=root, check=True)
    (root / ".gitignore").write_text(
        "ignored-shadow.py\n.megaplan/schemas/\n", encoding="utf-8"
    )
    (root / ".gitattributes").write_text(
        "*.pypeline linguist-language=Python\n", encoding="utf-8"
    )
    (root / "engine.py").write_text("ADMITTED = True\n", encoding="utf-8")
    (root / "idea.md").write_text("# Canary idea\n", encoding="utf-8")
    (root / "NORTHSTAR.md").write_text(
        "# North Star\n\nFinite canary.\n", encoding="utf-8"
    )
    (root / ".vscode").mkdir()
    (root / ".vscode/settings.json").write_text(
        '{\n  "files.associations": {\n    "*.pypeline": "python"\n  }\n}\n',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git", "add", ".gitattributes", ".gitignore", "engine.py",
            "idea.md", "NORTHSTAR.md", ".vscode/settings.json",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "commit", "-qm", "admitted"], cwd=root, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        capture_output=True, check=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True,
        capture_output=True, check=True,
    ).stdout.strip()
    plan_dir = root / ".megaplan/plans/critique-ledger-cl2-planning-canary"
    plan_dir.mkdir(parents=True)
    (root / ".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts").mkdir(
        parents=True
    )
    return head, tree, plan_dir


@pytest.mark.parametrize(
    "mutation",
    [
        "schema_tampered",
        "schema_missing",
        "schema_extra",
        "lock_tampered",
        "lock_extra",
        "epic_tampered",
        "epic_extra",
    ],
)
def test_runner_post_init_binds_canonical_schema_runtime_and_rejects_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutation: str
) -> None:
    _, _, plan_dir = _git_canary_fixture(tmp_path)
    plan_dir.rmdir()
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    ensure_runtime_layout(tmp_path)
    before = _zero_recovery_source_identity(tmp_path, plan_dir)
    assert before is not None
    assert [item["path"] for item in before["schema_runtime"]] == [
        f".megaplan/schemas/{filename}"
        for filename in sorted(
            path.name for path in (tmp_path / ".megaplan/schemas").iterdir()
        )
    ]

    command = [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "init",
        "--project-dir",
        str(tmp_path),
        "--name",
        "critique-ledger-cl2-planning-canary",
        "--auto-approve",
        "--idea-file",
        str(tmp_path / "idea.md"),
        "--north-star",
        str(tmp_path / "NORTHSTAR.md"),
        "--robustness",
        "full",
        "--no-adaptive-critique",
        "--vendor",
        "codex",
    ]
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        env={
            **os.environ,
            "MEGAPLAN_ZERO_RECOVERY_CANARY": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(Path.cwd()),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    post_init = _assert_zero_recovery_source_unchanged(
        tmp_path, plan_dir, before
    )
    assert post_init is not None

    schema_root = tmp_path / ".megaplan/schemas"
    lock_root = tmp_path / ".megaplan/.state-locks"
    epic_root = (
        tmp_path
        / ".megaplan/epics/critique-ledger-cl2-planning-canary"
    )
    if mutation == "schema_tampered":
        (schema_root / "plan.json").write_text("{}\n", encoding="utf-8")
    elif mutation == "schema_missing":
        (schema_root / "plan.json").unlink()
    elif mutation == "schema_extra":
        (schema_root / "hostile.json").write_text("{}\n", encoding="utf-8")
    elif mutation == "lock_tampered":
        (lock_root / "critique-ledger-cl2-planning-canary.lock").write_text(
            "hostile\n", encoding="utf-8"
        )
    elif mutation == "lock_extra":
        (lock_root / "hostile.lock").write_text("1\n", encoding="utf-8")
    elif mutation == "epic_tampered":
        with (epic_root / "events.jsonl").open("ab") as handle:
            handle.write(b"hostile\n")
    else:
        (epic_root / "hostile.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CliError) as exc:
        _assert_zero_recovery_source_unchanged(tmp_path, plan_dir, post_init)
    assert exc.value.code == "zero_recovery_worker_mutation_denied"


def test_runner_binds_primary_phase_failure_artifact_without_copying_content(
    tmp_path: Path,
) -> None:
    runner = runpy.run_path(
        str(Path(".megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py"))
    )
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    raw = plan_dir / "plan_v1_raw.txt"
    raw.write_text("finite-model UID retained an unreaped child\n", encoding="utf-8")
    raw.chmod(0o600)

    evidence = runner["trusted_phase_failure_artifact"](plan_dir, "plan")

    assert evidence == f"plan_v1_raw.txt:sha256={hashlib.sha256(raw.read_bytes()).hexdigest()}"
    assert "retained" not in evidence
    raw.chmod(0o666)
    assert runner["trusted_phase_failure_artifact"](plan_dir, "plan") == "untrusted"


def test_zero_recovery_schema_mode_drift_reports_exact_transition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, _, plan_dir = _git_canary_fixture(tmp_path)
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    ensure_runtime_layout(tmp_path)
    schema = tmp_path / ".megaplan/schemas/plan.json"
    schema.chmod(0o644)
    before = _zero_recovery_source_identity(tmp_path, plan_dir)
    schema.chmod(0o600)

    with pytest.raises(CliError) as exc:
        _assert_zero_recovery_source_unchanged(tmp_path, plan_dir, before)

    assert exc.value.code == "zero_recovery_worker_mutation_denied"
    assert ".megaplan/schemas/plan.json(0644:" in str(exc.value)
    assert "->0600:" in str(exc.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "tracked_source", "head_ref", "untracked_shadow", "ignored_shadow",
        "assume_unchanged_source", "index_flag", "config_fsmonitor", "hook",
    ],
)
def test_runner_and_worker_reject_repository_identity_or_import_shadow_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutation: str
) -> None:
    head, tree, plan_dir = _git_canary_fixture(tmp_path)
    runner = runpy.run_path(
        str(Path(".megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py"))
    )
    integrity = runner["repository_integrity"]
    integrity(
        tmp_path, source_commit=head, source_tree=tree, checkpoint="baseline"
    )
    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    worker_before = _zero_recovery_source_identity(tmp_path, plan_dir)
    if mutation == "tracked_source":
        (tmp_path / "engine.py").write_text("ADMITTED = False\n", encoding="utf-8")
    elif mutation == "head_ref":
        (tmp_path / ".git/HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    elif mutation == "untracked_shadow":
        (tmp_path / "arnold_pipelines.py").write_text("raise SystemExit\n", encoding="utf-8")
    elif mutation == "ignored_shadow":
        (tmp_path / "ignored-shadow.py").write_text("raise SystemExit\n", encoding="utf-8")
    elif mutation == "assume_unchanged_source":
        subprocess.run(
            ["git", "update-index", "--assume-unchanged", "engine.py"],
            cwd=tmp_path, check=True,
        )
        (tmp_path / "engine.py").write_text("CONCEALED = True\n", encoding="utf-8")
    elif mutation == "index_flag":
        subprocess.run(
            ["git", "update-index", "--skip-worktree", "engine.py"],
            cwd=tmp_path, check=True,
        )
    elif mutation == "config_fsmonitor":
        subprocess.run(
            ["git", "config", "core.fsmonitor", "/bin/false"],
            cwd=tmp_path, check=True,
        )
    else:
        hook = tmp_path / ".git/hooks/post-checkout"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)
    if mutation in {"tracked_source", "head_ref", "untracked_shadow", "ignored_shadow"}:
        with pytest.raises(Exception):
            integrity(tmp_path, source_commit=head, source_tree=tree, checkpoint="hostile")
    with pytest.raises(Exception):
        _assert_zero_recovery_source_unchanged(tmp_path, plan_dir, worker_before)


@pytest.mark.parametrize(
    "mutation",
    ["state", "gate", "lock", "prior_receipt", "output_symlink", "output_hardlink"],
)
def test_worker_boundary_rejects_model_mutation_and_output_aliases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutation: str
) -> None:
    monkeypatch.setenv("MEGAPLAN_ZERO_RECOVERY_CANARY", "1")
    plan_dir = tmp_path / ".megaplan/plans/critique-ledger-cl2-planning-canary"
    receipt_dir = (
        tmp_path
        / ".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts"
    )
    plan_dir.mkdir(parents=True)
    receipt_dir.mkdir(parents=True)
    state = plan_dir / "state.json"
    gate = plan_dir / "gate.json"
    lock = receipt_dir / "single-use-run.lock"
    prior = receipt_dir / "00-init.phase-receipt.json"
    state.write_text("state", encoding="utf-8")
    gate.write_text("gate", encoding="utf-8")
    lock.write_text("lock", encoding="utf-8")
    prior.write_text("receipt", encoding="utf-8")
    output = plan_dir / ".zero-recovery-plan-worker-output.json"
    before = _zero_recovery_plan_snapshot(
        tmp_path, plan_dir, output_path=output
    )
    if mutation == "state":
        state.write_text("altered", encoding="utf-8")
    elif mutation == "gate":
        gate.write_text("altered", encoding="utf-8")
    elif mutation == "lock":
        lock.unlink()
    elif mutation == "prior_receipt":
        prior.write_text("altered", encoding="utf-8")
    elif mutation == "output_symlink":
        output.symlink_to(state)
    else:
        protected = tmp_path / "historical-sibling.txt"
        protected.write_text("preserve", encoding="utf-8")
        os.link(protected, output)
    with pytest.raises(CliError, match="model"):
        _assert_zero_recovery_plan_unchanged(
            tmp_path, plan_dir, output_path=output, before=before
        )


@pytest.mark.parametrize("phase", ["plan", "critique", "gate", "finalize"])
def test_offline_structural_smoke_codex_emits_schema_valid_rollout_bound_output(
    tmp_path: Path, phase: str
) -> None:
    fake = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/"
        "structural-smoke/fake_codex.py"
    )
    source = fake.read_text(encoding="utf-8")
    assert source.startswith("#!/usr/local/bin/node\n")
    assert "socket" not in source
    assert 'require("child_process")' in source
    assert "orphan.unref()" in source
    assert "urllib" not in source
    assert "requests" not in source
    schema_name = "finalize_capture" if phase == "finalize" else phase
    output = tmp_path / f"{phase}.json"
    codex_home = tmp_path / "codex-home"
    ensure_runtime_layout(tmp_path)
    schema = tmp_path / ".megaplan" / "schemas" / f"{schema_name}.json"
    completed = subprocess.run(
        [
            "node",
            str(fake),
            "exec",
            "-o",
            str(output),
            "--output-schema",
            str(schema),
            "-",
        ],
        env={"CODEX_HOME": str(codex_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    validate(json.loads(output.read_text(encoding="utf-8")), json.loads(schema.read_text(encoding="utf-8")))
    if phase == "critique":
        expected = [
            "issue_hints",
            "correctness",
            "scope",
            "all_locations",
            "callers",
            "prerequisite_ordering",
        ]
        assert validate_critique_checks(
            json.loads(output.read_text(encoding="utf-8")), expected_ids=expected
        ) == []
    if phase == "finalize":
        assert compile_task_feasibility(
            json.loads(output.read_text(encoding="utf-8"))
        )["admitted"] is True
    thread = json.loads(completed.stdout.splitlines()[0])
    rollout = list((codex_home / "sessions").glob("*/*/*/rollout-*.jsonl"))
    assert len(rollout) == 1
    assert rollout[0].name.endswith(f"-{thread['thread_id']}.jsonl")
    assert _read_codex_observed_model(rollout[0]) == "gpt-5.6-sol"


def test_custody_contract_separates_two_consumed_substrates_and_15_deferred() -> None:
    custody = json.loads(
        Path(
            ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
            "custody-manifest.json"
        ).read_text(encoding="utf-8")
    )
    contract = _finite_canary_custody_contract(custody)
    assert contract is not None
    substrates, obligations = contract
    assert substrates == [
        {
            "id": "cloud-observation-preflight-repair-v2",
            "disposition": "CONSUMED_BOUNDED_SUBSTRATE",
        },
        {
            "id": "t1.9-zero-recovery-launcher",
            "disposition": "CONSUMED_ON_SUCCESS",
        },
    ]
    assert len(obligations) == 15
    assert {entry["phase"] for entry in obligations} == {"F1", "F2"}
    assert all(entry["status"] == "DEFERRED_POST_CANARY" for entry in obligations)
    assert all(
        entry["operational_disposition"] == "NOT_CONSUMED_OPERATIONAL_CANARY"
        for entry in obligations
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "obligation_omitted", "obligation_extra", "obligation_duplicate",
        "obligation_status_drift", "obligation_reordered", "substrate_blanket",
        "substrate_disposition_drift", "custody_item_status_drift",
    ],
)
def test_custody_contract_rejects_omission_extra_duplicate_or_status_drift(
    mutation: str,
) -> None:
    custody = json.loads(
        Path(
            ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
            "custody-manifest.json"
        ).read_text(encoding="utf-8")
    )
    hostile = copy.deepcopy(custody)
    if mutation == "obligation_omitted":
        hostile["deferred_obligations"].pop()
    elif mutation == "obligation_extra":
        hostile["deferred_obligations"].append(
            {
                "id": "F2.unknown_extra",
                "phase": "F2",
                "status": "DEFERRED_POST_CANARY",
                "operational_disposition": "NOT_CONSUMED_OPERATIONAL_CANARY",
            }
        )
    elif mutation == "obligation_duplicate":
        hostile["deferred_obligations"].append(
            copy.deepcopy(hostile["deferred_obligations"][0])
        )
    elif mutation == "obligation_status_drift":
        hostile["deferred_obligations"][0]["status"] = "COMPLETED"
    elif mutation == "obligation_reordered":
        hostile["deferred_obligations"][0], hostile["deferred_obligations"][1] = (
            hostile["deferred_obligations"][1], hostile["deferred_obligations"][0]
        )
    elif mutation == "substrate_blanket":
        hostile["operational_substrates"] = [
            {
                "id": item["id"],
                "disposition": "NOT_CONSUMED_OPERATIONAL_CANARY",
            }
            for item in hostile["items"]
        ]
    elif mutation == "substrate_disposition_drift":
        hostile["operational_substrates"][0]["disposition"] = (
            "NOT_CONSUMED_OPERATIONAL_CANARY"
        )
    else:
        hostile["items"][0]["status"] = "COMPLETED"
    assert _finite_canary_custody_contract(hostile) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "top_level_extra",
        "contract_timestamp_invalid",
        "gate_omitted",
        "gate_extra",
        "gate_duplicate",
        "gate_reordered",
        "gate_status_drift",
        "gate_owner_drift",
        "gate_evidence_drift",
        "host_control_state_drift",
        "obligation_owner_drift",
        "obligation_acceptance_drift",
        "obligation_evidence_drift",
        "obligation_claim_drift",
    ],
)
def test_custody_v3_rejects_noncanonical_gate_host_and_obligation_fields(
    mutation: str,
) -> None:
    custody = json.loads(
        Path(
            ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
            "custody-manifest.json"
        ).read_text(encoding="utf-8")
    )
    hostile = copy.deepcopy(custody)
    gates = hostile["prelaunch_release_gates"]
    obligation = hostile["deferred_obligations"][0]
    if mutation == "top_level_extra":
        hostile["hostile"] = True
    elif mutation == "contract_timestamp_invalid":
        hostile["contract_updated_at"] = "2026-08-03T02:40:21+00:00"
    elif mutation == "gate_omitted":
        gates.pop()
    elif mutation == "gate_extra":
        extra = copy.deepcopy(gates[-1])
        extra["id"] = "hostile_extra_gate"
        gates.append(extra)
    elif mutation == "gate_duplicate":
        gates.append(copy.deepcopy(gates[0]))
    elif mutation == "gate_reordered":
        gates[0], gates[1] = gates[1], gates[0]
    elif mutation == "gate_status_drift":
        gates[0]["status"] = "ACCEPTED"
    elif mutation == "gate_owner_drift":
        gates[0]["owner"] = "untrusted operator"
    elif mutation == "gate_evidence_drift":
        gates[0]["evidence"]["path"] = "forged.json"
    elif mutation == "host_control_state_drift":
        hostile["trusted_host_control_state_contract"][
            "global_containment_marker"
        ]["schema"] = "arnold.cloud.zero_recovery_marker.v1"
    elif mutation == "obligation_owner_drift":
        obligation["owner_milestone"] = "wrong-owner"
    elif mutation == "obligation_acceptance_drift":
        obligation["acceptance_gate"] = "SELF_ASSERTION_ALLOWED"
    elif mutation == "obligation_evidence_drift":
        obligation["evidence_ref"] = "forged.json#/claim"
    else:
        obligation["required_claim_id"] = "F1.forged"
    assert _finite_canary_custody_contract(hostile) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "obligation_omitted", "obligation_extra", "obligation_duplicate",
        "obligation_status_drift", "obligation_reordered",
        "substrate_omitted", "substrate_extra", "substrate_duplicate",
        "substrate_reordered", "substrate_disposition_drift",
    ],
)
def test_completion_contract_rejects_noncanonical_operational_arrays(
    mutation: str,
) -> None:
    custody = json.loads(
        Path(
            ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
            "custody-manifest.json"
        ).read_text(encoding="utf-8")
    )
    contract = _finite_canary_custody_contract(custody)
    assert contract is not None
    expected_substrates, expected_obligations = contract
    substrates = copy.deepcopy(expected_substrates)
    obligations = copy.deepcopy(expected_obligations)
    if mutation == "obligation_omitted":
        obligations.pop()
    elif mutation == "obligation_extra":
        obligations.append(
            {
                "id": "F2.unknown_extra",
                "phase": "F2",
                "status": "DEFERRED_POST_CANARY",
                "operational_disposition": "NOT_CONSUMED_OPERATIONAL_CANARY",
            }
        )
    elif mutation == "obligation_duplicate":
        obligations.append(copy.deepcopy(obligations[0]))
    elif mutation == "obligation_status_drift":
        obligations[0]["status"] = "COMPLETED"
    elif mutation == "obligation_reordered":
        obligations[0], obligations[1] = obligations[1], obligations[0]
    elif mutation == "substrate_omitted":
        substrates.pop()
    elif mutation == "substrate_extra":
        substrates.append(
            {"id": "unknown", "disposition": "CONSUMED_BOUNDED_SUBSTRATE"}
        )
    elif mutation == "substrate_duplicate":
        substrates.append(copy.deepcopy(substrates[0]))
    elif mutation == "substrate_reordered":
        substrates.reverse()
    else:
        substrates[0]["disposition"] = "NOT_CONSUMED_OPERATIONAL_CANARY"
    assert not _finite_canary_completion_contract_is_valid(
        substrates,
        obligations,
        expected_substrates=expected_substrates,
        expected_obligations=expected_obligations,
    )


def test_offline_structural_smoke_harness_seeds_dummy_root_auth_and_has_no_network() -> None:
    fixture = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/structural-smoke"
    )
    harness = fixture / "run-offline-structural-smoke.sh"
    completed = subprocess.run(
        ["bash", "-n", str(harness)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    source = harness.read_text(encoding="utf-8")
    assert "--network none" in source
    assert "--pull=false --network none" in source
    assert '--build-arg "PRODUCTION_IMAGE=$production_image"' in source
    assert '--build-arg "PRODUCTION_IMAGE=$production_image_id"' not in source
    assert 'cp -a "$repo_root/." "$workspace_child/Arnold/"' in source
    assert "chmod 0755 /workspace/Arnold" in source
    assert "docker cp" not in source
    assert "/root/.codex/auth.json" in source
    assert "/root/.codex/config.toml" in source
    assert "offline_structural_smoke" in source
    assert "chmod 0600 /root/.codex/auth.json /root/.codex/config.toml" in source
    assert 'mkdir -m 0700 "$evidence_dir/phase-receipts"' in source
    assert "'*.phase-receipt.json'" in source
    assert '"phase_receipts": inventory("phase-receipts")' in source
    dockerfile = (fixture / "Dockerfile").read_text(encoding="utf-8")
    assert "verify-zero-recovery-offline-smoke" in dockerfile

    runner = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py"
    ).read_text(encoding="utf-8")
    assert '"stdout_sha256"' in runner
    assert '"stderr_sha256"' in runner
    assert '"stdout_tail": stdout[-4096:]' in runner
    assert '"stderr_tail": stderr[-4096:]' in runner


def test_offline_structural_smoke_failure_preserves_typed_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "dirty-repo"
    repo.mkdir()
    initialized = subprocess.run(
        ["git", "init", "-q", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    (repo / "untracked").write_text("force preflight failure\n", encoding="utf-8")
    receipt = tmp_path / "failed-smoke-receipt.json"
    harness = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/structural-smoke/"
        "run-offline-structural-smoke.sh"
    ).resolve()
    completed = subprocess.run(
        [str(harness), "unused-image", str(repo), str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 65
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "arnold.megaplan.zero_recovery_offline_structural_smoke_attempt.v1"
    )
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 65
    assert payload["source_commit"] is None
    assert payload["production_image_id"] is None
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert payload["container_runtime_summary"] == {"validated": False}
    evidence = Path(f"{receipt}.evidence")
    assert (evidence / "stdout.log").is_file()
    assert (evidence / "stderr.log").is_file()
    assert json.loads((evidence / "container-inspect.json").read_text()) == {
        "available": False
    }
    before = receipt.read_bytes()
    refused = subprocess.run(
        [str(harness), "unused-image", str(repo), str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 66
    assert receipt.read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "network",
        "restart",
        "capabilities",
        "security",
        "resources",
        "extra_mount",
        "tmpfs",
        "image_ports",
        "host_ports",
        "runtime_ports",
        "init",
    ],
)
def test_offline_structural_smoke_inspect_rejects_runtime_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    container_id = "a" * 64
    container_name = "offline-smoke"
    image_id = "sha256:" + "b" * 64
    bind_source = tmp_path / "workspace-child"
    bind_source.mkdir()
    inspect_payload = [
        {
            "Id": container_id,
            "Name": f"/{container_name}",
            "Image": image_id,
            "HostConfig": {
                "NetworkMode": "none",
                "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                "Init": True,
                "CapDrop": ["ALL"],
                "CapAdd": [
                    "CAP_CHOWN",
                    "CAP_DAC_READ_SEARCH",
                    "CAP_KILL",
                    "CAP_SETGID",
                    "CAP_SETPCAP",
                    "CAP_SETUID",
                ],
                "SecurityOpt": ["no-new-privileges:true"],
                "IpcMode": "none",
                "PidsLimit": 256,
                "Memory": 4_294_967_296,
                "MemorySwap": 4_294_967_296,
                "PortBindings": {},
                "Mounts": [],
                "Tmpfs": {
                    "/run/megaplan-zero-recovery": (
                        "rw,noexec,nosuid,nodev,size=268435456,mode=0711"
                    )
                },
            },
            "Config": {"ExposedPorts": {"8080/tcp": {}}, "Volumes": None},
            "NetworkSettings": {"Ports": {"8080/tcp": None}},
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": str(bind_source.resolve()),
                    "Destination": "/workspace",
                    "Mode": "",
                    "RW": True,
                    "Propagation": "rprivate",
                }
            ],
        }
    ]
    if mutation == "identity":
        inspect_payload[0]["Image"] = "sha256:" + "c" * 64
    elif mutation == "network":
        inspect_payload[0]["HostConfig"]["NetworkMode"] = "bridge"
    elif mutation == "restart":
        inspect_payload[0]["HostConfig"]["RestartPolicy"]["Name"] = "always"
    elif mutation == "init":
        inspect_payload[0]["HostConfig"]["Init"] = False
    elif mutation == "capabilities":
        inspect_payload[0]["HostConfig"]["CapAdd"].append("SYS_ADMIN")
    elif mutation == "security":
        inspect_payload[0]["HostConfig"]["SecurityOpt"] = []
    elif mutation == "resources":
        inspect_payload[0]["HostConfig"]["Memory"] = 0
    elif mutation == "extra_mount":
        inspect_payload[0]["Mounts"].append(
            {
                "Type": "bind",
                "Source": "/var/run/docker.sock",
                "Destination": "/var/run/docker.sock",
                "Mode": "",
                "RW": True,
                "Propagation": "rprivate",
            }
        )
    elif mutation == "tmpfs":
        inspect_payload[0]["HostConfig"]["Tmpfs"] = {
            "/run/megaplan-zero-recovery": (
                "rw,nosuid,nodev,size=268435456,mode=0711"
            )
        }
    elif mutation == "image_ports":
        inspect_payload[0]["Config"]["ExposedPorts"] = {"80/tcp": {}}
    elif mutation == "host_ports":
        inspect_payload[0]["HostConfig"]["PortBindings"] = {
            "8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
        }
    else:
        inspect_payload[0]["NetworkSettings"]["Ports"] = {
            "8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
        }
    inspect_path = tmp_path / "inspect.json"
    inspect_path.write_text(json.dumps(inspect_payload), encoding="utf-8")
    validator = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/structural-smoke/"
        "validate_container_inspect.py"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(inspect_path),
            container_id,
            container_name,
            image_id,
            str(bind_source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "container runtime drift" in completed.stderr


def test_offline_structural_smoke_inspect_emits_normalized_runtime_summary(
    tmp_path: Path,
) -> None:
    bind_source = tmp_path / "workspace-child"
    bind_source.mkdir()
    container_id = "a" * 64
    container_name = "offline-smoke"
    image_id = "sha256:" + "b" * 64
    inspect_payload = [
        {
            "Id": container_id,
            "Name": f"/{container_name}",
            "Image": image_id,
            "HostConfig": {
                "NetworkMode": "none",
                "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                "Init": True,
                "CapDrop": ["ALL"],
                "CapAdd": [
                    "CAP_CHOWN", "CAP_DAC_READ_SEARCH", "CAP_KILL",
                    "CAP_SETGID", "CAP_SETPCAP", "CAP_SETUID",
                ],
                "SecurityOpt": ["no-new-privileges:true"],
                "IpcMode": "none",
                "PidsLimit": 256,
                "Memory": 4_294_967_296,
                "MemorySwap": 4_294_967_296,
                "PortBindings": {},
                "Mounts": [],
                "Tmpfs": {
                    "/run/megaplan-zero-recovery": (
                        "mode=0711,size=268435456,nodev,nosuid,noexec,rw"
                    )
                },
            },
            "Config": {"ExposedPorts": {"8080/tcp": {}}, "Volumes": {}},
            "NetworkSettings": {"Ports": {"8080/tcp": None}},
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": str(bind_source.resolve()),
                    "Destination": "/workspace",
                    "Mode": "",
                    "RW": True,
                    "Propagation": "rprivate",
                }
            ],
        }
    ]
    inspect_path = tmp_path / "inspect.json"
    inspect_path.write_text(json.dumps(inspect_payload), encoding="utf-8")
    validator = Path(
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/structural-smoke/"
        "validate_container_inspect.py"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(inspect_path),
            container_id,
            container_name,
            image_id,
            str(bind_source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["validated"] is True
    assert summary["container_id"] == container_id
    assert summary["image_id"] == image_id
    assert summary["bind"]["source"] == str(bind_source.resolve())
    assert len(summary["summary_digest"]) == 64
