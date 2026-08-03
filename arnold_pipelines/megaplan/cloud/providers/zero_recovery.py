"""Finite zero-recovery canary host fencing and predeploy receipts.

This module is deliberately SSH-provider-specific substrate.  It is not a
general launch authority and exposes no arbitrary host command surface.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shlex
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any, Mapping

from arnold_pipelines.megaplan.types import CliError


PREDEPLOY_SCHEMA = "arnold.cloud.zero_recovery_predeploy.v1"
FENCE_SCHEMA = "arnold.cloud.zero_recovery_host_fence.v1"
BOOTSTRAP_RECLAIM_SCHEMA = "arnold.cloud.zero_recovery_bootstrap_reclaim.v1"
BOOTSTRAP_RECLAIM_RECEIPT_SCHEMA = (
    "arnold.cloud.zero_recovery_bootstrap_fence_reclaim_receipt.v1"
)
PRESERVATION_SCHEMA = "arnold.cloud.zero_recovery_container_preservation.v1"
PREDEPLOY_TTL_SECONDS = 300
ZERO_RECOVERY_UNITS = (
    "megaplan-watchdog-ensure.timer",
    "megaplan-resident-ensure.timer",
    "megaplan-progress-audit.timer",
    "megaplan-repair-trigger.path",
    "megaplan-watchdog-ensure.service",
    "megaplan-resident-ensure.service",
    "megaplan-progress-audit.service",
    "megaplan-repair-trigger.service",
)
ZERO_RECOVERY_SESSIONS = (
    "agent",
    "heartbeat",
    "watchdog",
    "megaplan-resident-discord",
)
ZERO_RECOVERY_PROCESS_TOKENS = (
    "arnold-watchdog",
    "arnold-heartbeat",
    "arnold-progress-auditor",
    "arnold-repair-trigger",
    "megaplan resident discord",
)

_IDENTITY_FIELDS = (
    "schema",
    "status",
    "lifecycle",
    "container_state",
    "container",
    "container_id",
    "image_id",
    "image_ref",
    "workspace_bind",
    "started_at",
    "finished_at",
    "restart_count",
)
_TRANSACTION_FIELDS = {
    "schema",
    "transaction_id",
    "issued_at",
    "expires_at",
    "target",
    "container_observation",
    "capacity_observation",
    "transaction_digest",
}
_BOOTSTRAP_FIELDS = {
    "schema",
    "transaction_id",
    "issued_at",
    "expires_at",
    "target",
    "container_observation",
    "prelaunch_observation",
    "capacity_inventory",
    "command_class",
    "command_argv",
    "transaction_digest",
}


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _identity(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {field: observation.get(field) for field in _IDENTITY_FIELDS}


def _contains_enospc(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return "no space left on device" in lowered or "enospc" in lowered
    if isinstance(value, Mapping):
        return any(_contains_enospc(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_enospc(item) for item in value)
    return False


def _require_exact_stopped_container(
    outer: Mapping[str, Any], target: Mapping[str, Any]
) -> None:
    if (
        outer.get("schema") != "arnold.cloud.ssh_container_observation.v1"
        or outer.get("status") != "available"
        or outer.get("lifecycle") != "stopped"
        or outer.get("container_state") not in {"created", "exited", "dead"}
        or outer.get("container") != target.get("container")
        or not isinstance(outer.get("container_id"), str)
        or not outer.get("container_id")
        or not isinstance(outer.get("image_id"), str)
        or not outer.get("image_id")
        or outer.get("image_ref") != target.get("container")
        or not isinstance(outer.get("started_at"), str)
        or not outer.get("started_at")
        or not isinstance(outer.get("finished_at"), str)
        or not outer.get("finished_at")
        or type(outer.get("restart_count")) is not int
        or outer.get("restart_count") < 0
        or outer.get("workspace_bind")
        != {
            "status": "present",
            "type": "bind",
            "source": target.get("workspace"),
            "destination": "/workspace",
            "rw": True,
        }
    ):
        raise CliError(
            "zero_recovery_bootstrap_no_go",
            "bootstrap reclaim requires the exact preserved stopped container identity",
        )


def _require_predeploy_go(
    *,
    outer: Mapping[str, Any],
    capacity: Mapping[str, Any],
    target: Mapping[str, Any],
) -> None:
    embedded = capacity.get("container")
    # Docker preserves historical State.Error text after the filesystem is
    # healthy. Only fresh capacity evidence is launch authority.
    fresh_capacity = {
        key: value for key, value in capacity.items() if key != "container"
    }
    if _contains_enospc(fresh_capacity):
        raise CliError(
            "zero_recovery_predeploy_no_go",
            "host/container ENOSPC evidence is a hard zero-recovery predeploy NO-GO",
        )
    try:
        _require_exact_stopped_container(outer, target)
    except CliError as exc:
        raise CliError("zero_recovery_predeploy_no_go", exc.message) from exc
    if (
        not isinstance(embedded, Mapping)
        or _identity(embedded) != _identity(outer)
        or capacity.get("schema") != "arnold.cloud.ssh_workspace_prelaunch.v1"
        or capacity.get("status") != "go"
        or capacity.get("verdict") != "GO"
        or capacity.get("workspace") != target.get("workspace")
        or capacity.get("returncode") != 0
        or capacity.get("errors") != []
    ):
        raise CliError(
            "zero_recovery_predeploy_no_go",
            "capacity evidence did not bind the exact outer container/spec target",
        )


def build_predeploy_transaction(
    *,
    outer: Mapping[str, Any],
    capacity: Mapping[str, Any],
    target: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _require_predeploy_go(outer=outer, capacity=capacity, target=target)
    payload: dict[str, Any] = {
        "schema": PREDEPLOY_SCHEMA,
        "transaction_id": uuid.uuid4().hex,
        "issued_at": _format_time(issued),
        "expires_at": _format_time(issued + timedelta(seconds=PREDEPLOY_TTL_SECONDS)),
        "target": dict(target),
        "container_observation": dict(outer),
        "capacity_observation": dict(capacity),
    }
    payload["transaction_digest"] = _digest(payload)
    return payload


def validate_predeploy_transaction(
    transaction: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    outer: Mapping[str, Any],
    capacity: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(transaction, dict) or set(transaction) != _TRANSACTION_FIELDS:
        raise CliError(
            "zero_recovery_predeploy_invalid",
            "zero-recovery predeploy transaction has an inexact schema",
        )
    expected_digest = transaction.get("transaction_digest")
    unsigned = dict(transaction)
    unsigned.pop("transaction_digest", None)
    if (
        not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or _digest(unsigned) != expected_digest
    ):
        raise CliError(
            "zero_recovery_predeploy_invalid",
            "zero-recovery predeploy transaction digest mismatch",
        )
    issued = _parse_time(transaction.get("issued_at"))
    expires = _parse_time(transaction.get("expires_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if (
        issued is None
        or expires is None
        or expires <= issued
        or (expires - issued).total_seconds() != PREDEPLOY_TTL_SECONDS
        or current < issued
        or current >= expires
    ):
        raise CliError(
            "zero_recovery_predeploy_expired",
            "zero-recovery predeploy transaction is stale or has an invalid lifetime",
        )
    if transaction.get("target") != dict(target):
        raise CliError(
            "zero_recovery_predeploy_mismatch",
            "zero-recovery predeploy transaction target mismatch",
        )
    recorded_outer = transaction.get("container_observation")
    recorded_capacity = transaction.get("capacity_observation")
    if not isinstance(recorded_outer, Mapping) or not isinstance(
        recorded_capacity, Mapping
    ):
        raise CliError(
            "zero_recovery_predeploy_invalid",
            "zero-recovery predeploy transaction evidence is malformed",
        )
    _require_predeploy_go(
        outer=recorded_outer, capacity=recorded_capacity, target=target
    )
    _require_predeploy_go(outer=outer, capacity=capacity, target=target)
    if _identity(recorded_outer) != _identity(outer):
        raise CliError(
            "zero_recovery_predeploy_mismatch",
            "container identity changed before zero-recovery deploy",
        )
    return dict(transaction)


def _require_bootstrap_no_go(
    *,
    outer: Mapping[str, Any],
    prelaunch: Mapping[str, Any],
    inventory: Mapping[str, Any],
    target: Mapping[str, Any],
) -> None:
    _require_exact_stopped_container(outer, target)
    embedded = prelaunch.get("container")
    if (
        prelaunch.get("schema") != "arnold.cloud.ssh_workspace_prelaunch.v1"
        or prelaunch.get("status") != "no-go"
        or prelaunch.get("verdict") != "NO-GO"
        or prelaunch.get("workspace") != target.get("workspace")
        or not isinstance(embedded, Mapping)
        or _identity(embedded) != _identity(outer)
    ):
        raise CliError(
            "zero_recovery_bootstrap_no_go",
            "bootstrap reclaim is restricted to a fresh ENOSPC prelaunch NO-GO",
        )
    filesystem = inventory.get("filesystem")
    scopes = inventory.get("scopes")
    thresholds = prelaunch.get("thresholds")
    checks = prelaunch.get("checks")
    capacity = prelaunch.get("capacity")
    mount = prelaunch.get("mount")
    scope_paths = [item.get("path") for item in scopes if isinstance(item, Mapping)] if isinstance(scopes, list) else []
    if (
        inventory.get("schema") != "arnold.cloud.ssh_capacity_inventory.v1"
        or inventory.get("status") != "available"
        or inventory.get("workspace") != target.get("workspace")
        or inventory.get("returncode") != 0
        or not isinstance(filesystem, Mapping)
        or not isinstance(filesystem.get("free_bytes"), int)
        or isinstance(filesystem.get("free_bytes"), bool)
        or not isinstance(filesystem.get("free_inodes"), int)
        or isinstance(filesystem.get("free_inodes"), bool)
        or not isinstance(scopes, list)
        or not isinstance(inventory.get("docker_disk_usage"), list)
        or inventory.get("errors") != []
        or inventory.get("mount") != mount
        or scope_paths != target.get("capacity_scopes")
        or any(
            not isinstance(item, Mapping)
            or set(item) != {"path", "status", "size_bytes"}
            or item.get("status") not in {"available", "absent"}
            or type(item.get("size_bytes")) is not int
            or item.get("size_bytes") < 0
            for item in (scopes or [])
        )
        or not isinstance(thresholds, Mapping)
        or set(thresholds)
        != {"min_free_bytes", "min_free_inodes", "receipt_reserve_bytes"}
        or any(type(value) is not int or value < 0 for value in thresholds.values())
        or not isinstance(checks, Mapping)
        or checks != {"byte_floor": False, "inode_floor": True}
        or prelaunch.get("errors") != ["prelaunch_free_bytes_below_reserve"]
        or prelaunch.get("returncode") != 3
        or not isinstance(capacity, Mapping)
        or set(capacity) != {"free_bytes", "free_inodes"}
        or capacity.get("free_bytes") != filesystem.get("free_bytes")
        or capacity.get("free_inodes") != filesystem.get("free_inodes")
        or capacity.get("free_bytes")
        >= thresholds.get("min_free_bytes") + thresholds.get("receipt_reserve_bytes")
        or capacity.get("free_inodes") < thresholds.get("min_free_inodes")
        or target.get("capacity_floor_bytes")
        != thresholds.get("min_free_bytes") + thresholds.get("receipt_reserve_bytes")
    ):
        raise CliError(
            "zero_recovery_bootstrap_no_go",
            "bootstrap reclaim capacity inventory is incomplete or ambiguous",
        )


def build_bootstrap_reclaim_transaction(
    *,
    outer: Mapping[str, Any],
    prelaunch: Mapping[str, Any],
    inventory: Mapping[str, Any],
    target: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _require_bootstrap_no_go(
        outer=outer,
        prelaunch=prelaunch,
        inventory=inventory,
        target=target,
    )
    payload: dict[str, Any] = {
        "schema": BOOTSTRAP_RECLAIM_SCHEMA,
        "transaction_id": uuid.uuid4().hex,
        "issued_at": _format_time(issued),
        "expires_at": _format_time(issued + timedelta(seconds=PREDEPLOY_TTL_SECONDS)),
        "target": dict(target),
        "container_observation": dict(outer),
        "prelaunch_observation": dict(prelaunch),
        "capacity_inventory": dict(inventory),
        "command_class": "docker_dangling_build_cache_prune",
        "command_argv": ["docker", "builder", "prune", "-f"],
    }
    payload["transaction_digest"] = _digest(payload)
    return payload


def validate_bootstrap_reclaim_transaction(
    transaction: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    outer: Mapping[str, Any],
    prelaunch: Mapping[str, Any],
    inventory: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(transaction, dict) or set(transaction) != _BOOTSTRAP_FIELDS:
        raise CliError(
            "zero_recovery_bootstrap_invalid",
            "bootstrap reclaim transaction has an inexact schema",
        )
    unsigned = dict(transaction)
    expected_digest = unsigned.pop("transaction_digest", None)
    issued = _parse_time(transaction.get("issued_at"))
    expires = _parse_time(transaction.get("expires_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if (
        transaction.get("schema") != BOOTSTRAP_RECLAIM_SCHEMA
        or not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or _digest(unsigned) != expected_digest
        or issued is None
        or expires is None
        or (expires - issued).total_seconds() != PREDEPLOY_TTL_SECONDS
        or current < issued
        or current >= expires
        or transaction.get("target") != dict(target)
        or transaction.get("command_class")
        != "docker_dangling_build_cache_prune"
        or transaction.get("command_argv")
        != ["docker", "builder", "prune", "-f"]
    ):
        raise CliError(
            "zero_recovery_bootstrap_invalid",
            "bootstrap reclaim transaction digest, lifetime, target, or command mismatch",
        )
    _require_bootstrap_no_go(
        outer=outer,
        prelaunch=prelaunch,
        inventory=inventory,
        target=target,
    )
    if (
        transaction.get("container_observation") != dict(outer)
        or transaction.get("prelaunch_observation") != dict(prelaunch)
        or transaction.get("capacity_inventory") != dict(inventory)
    ):
        raise CliError(
            "zero_recovery_bootstrap_mismatch",
            "bootstrap reclaim evidence changed before the first mutation",
        )
    return dict(transaction)


_BOOTSTRAP_RECLAIM_SCRIPT = r"""
import base64
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

config = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
workspace = config["target"]["workspace"]
expected_container = config["container_observation"]
expected_inventory = config["capacity_inventory"]
units = config["units"]
failure_stage = "before_intent"
prune_started = False
settle_observations = []
last_systemd_jobs = []
authority_root = pathlib.Path("/var/lib/arnold-zero-recovery")
authority_dir_fd = None

def open_authority_directory():
    created = False
    try:
        os.mkdir(authority_root, 0o700)
        created = True
    except FileExistsError:
        pass
    if created:
        parent_fd = os.open(
            authority_root.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            parent = os.fstat(parent_fd)
            if (
                not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != 0
                or parent.st_gid != 0
            ):
                raise RuntimeError("authority_parent_identity_invalid")
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    observed = os.lstat(authority_root)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or stat.S_ISLNK(observed.st_mode)
        or observed.st_uid != 0
        or observed.st_gid != 0
        or stat.S_IMODE(observed.st_mode) != 0o700
    ):
        raise RuntimeError("authority_directory_identity_invalid")
    fd = os.open(
        authority_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    opened = os.fstat(fd)
    if (
        opened.st_dev != observed.st_dev
        or opened.st_ino != observed.st_ino
        or opened.st_uid != 0
        or opened.st_gid != 0
        or stat.S_IMODE(opened.st_mode) != 0o700
    ):
        os.close(fd)
        raise RuntimeError("authority_directory_identity_changed")
    return fd

def authority_filename(suffix):
    transaction_id = config["transaction_id"]
    if (
        not isinstance(transaction_id, str)
        or not transaction_id
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for character in transaction_id)
    ):
        raise RuntimeError("authority_transaction_id_invalid")
    return transaction_id + suffix

def write_authority_file(name, raw):
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=authority_dir_fd,
    )
    try:
        os.fchmod(fd, 0o600)
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != 0
            or opened.st_gid != 0
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
        ):
            raise RuntimeError("authority_file_identity_invalid:" + name)
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.fsync(authority_dir_fd)

def run(argv, timeout_seconds=None):
    timeout = timeout_seconds
    if timeout is None:
        timeout = 300 if argv[:4] == ["docker", "builder", "prune", "-f"] else 30
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)

def show_unit(unit, timeout_seconds=None):
    result = run(["systemctl", "show", unit, "--property=LoadState", "--property=ActiveState", "--property=UnitFileState", "--value"], timeout_seconds=timeout_seconds)
    values = result.stdout.splitlines()
    if result.returncode != 0 or len(values) != 3 or not values[0] or not values[1]:
        raise RuntimeError("unit_observation_unknown:" + unit)
    persistent = pathlib.Path("/etc/systemd/system") / unit
    if os.path.lexists(persistent):
        persistent_identity = os.lstat(persistent)
        persistent_mask = (
            stat.S_ISLNK(persistent_identity.st_mode)
            and persistent_identity.st_uid == 0
            and persistent_identity.st_gid == 0
            and os.readlink(persistent) == "/dev/null"
        )
    else:
        persistent_mask = False
    return {"unit": unit, "load_state": values[0], "active_state": values[1], "unit_file_state": values[2], "persistent_mask": persistent_mask}

def settle_units(before_items, require_persistent=False):
    global settle_observations
    deadline = time.monotonic() + 5.0
    reset_units = set()
    originally_absent = {
        item["unit"] for item in before_items if item["load_state"] == "not-found"
    }
    while True:
        current = []
        for before_item in before_items:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("unit_settle_timeout")
            try:
                current.append(show_unit(before_item["unit"], timeout_seconds=min(0.5, remaining)))
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("unit_settle_observation_timeout:" + before_item["unit"]) from exc
        settle_observations.append(current)
        pending = False
        for item in current:
            unit = item["unit"]
            if unit in originally_absent and not require_persistent:
                if item["load_state"] != "not-found":
                    raise RuntimeError("unit_appeared_during_settle:" + unit)
                continue
            if item["load_state"] not in {"loaded", "masked"}:
                raise RuntimeError("unit_load_state_drift_during_settle:" + unit)
            admitted_mask_states = {"masked"} if require_persistent else {"masked-runtime", "masked"}
            if item["unit_file_state"] not in admitted_mask_states:
                raise RuntimeError("unit_mask_state_drift_during_settle:" + unit)
            if require_persistent and item["persistent_mask"] is not True:
                raise RuntimeError("unit_persistent_mask_missing_during_settle:" + unit)
            active = item["active_state"]
            if active == "inactive":
                continue
            if active == "failed":
                if unit in reset_units:
                    raise RuntimeError("unit_failed_after_reset:" + unit)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("unit_settle_timeout")
                try:
                    reset = run(
                        ["systemctl", "reset-failed", unit],
                        timeout_seconds=min(1.0, remaining),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("unit_reset_failed:" + unit) from exc
                if reset.returncode != 0:
                    raise RuntimeError("unit_reset_failed:" + unit)
                reset_units.add(unit)
                pending = True
                continue
            if active in {"activating", "deactivating"}:
                pending = True
                continue
            raise RuntimeError("unit_invalid_active_state_during_settle:" + unit + ":" + active)
        if not pending:
            return current
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("unit_settle_timeout")
        time.sleep(min(0.2, remaining))

def require_no_recovery_unit_jobs():
    global last_systemd_jobs
    jobs = run(["systemctl", "list-jobs", "--no-legend", "--no-pager"])
    if jobs.returncode != 0:
        raise RuntimeError("systemd_jobs_observation_unknown")
    last_systemd_jobs = [
        line.strip()
        for line in jobs.stdout.splitlines()
        if line.strip() and any(unit in line.split() for unit in units)
    ]
    if last_systemd_jobs:
        raise RuntimeError("recovery_unit_job_queued:" + last_systemd_jobs[0])
    return last_systemd_jobs

def install_persistent_masks(before_items):
    mask_root = pathlib.Path("/etc/systemd/system")
    for item in before_items:
        persistent = mask_root / item["unit"]
        if os.path.lexists(persistent):
            identity = os.lstat(persistent)
            if (
                not stat.S_ISLNK(identity.st_mode)
                or identity.st_uid != 0
                or identity.st_gid != 0
                or os.readlink(persistent) != "/dev/null"
            ):
                raise RuntimeError("persistent_mask_path_conflict:" + item["unit"])
        else:
            temporary = persistent.with_name(
                persistent.name + "." + config["transaction_id"] + ".tmp"
            )
            os.symlink("/dev/null", temporary)
            os.replace(temporary, persistent)
    mask_dir_fd = os.open(
        mask_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        mask_root_identity = os.fstat(mask_dir_fd)
        if (
            not stat.S_ISDIR(mask_root_identity.st_mode)
            or mask_root_identity.st_uid != 0
            or mask_root_identity.st_gid != 0
        ):
            raise RuntimeError("persistent_mask_directory_identity_invalid")
        os.fsync(mask_dir_fd)
    finally:
        os.close(mask_dir_fd)

def establish_persistent_fence(before_items):
    global failure_stage
    failure_stage = "install_persistent_unit_masks_before_prune"
    install_persistent_masks(before_items)
    failure_stage = "daemon_reload_persistent_masks_before_prune"
    daemon_reload = run(["systemctl", "daemon-reload"])
    if daemon_reload.returncode != 0:
        raise RuntimeError("systemd_daemon_reload_failed")
    failure_stage = "settle_persistent_units_before_prune"
    persistent_units = settle_units(before_items, require_persistent=True)
    failure_stage = "verify_no_recovery_unit_jobs_before_prune"
    jobs = require_no_recovery_unit_jobs()
    return persistent_units, jobs

def safe_unit_observations():
    observed = []
    for unit in units:
        try:
            observed.append(show_unit(unit, timeout_seconds=0.5))
        except Exception as exc:
            observed.append({"unit": unit, "observation_error": str(exc)})
    return observed

def write_failure_receipt(exc_type, exc):
    name = authority_filename(".bootstrap-fence-reclaim-failure.json")
    path = authority_root / name
    receipt = {
        "schema": "arnold.cloud.zero_recovery_bootstrap_fence_reclaim_failure.v1",
        "status": "failed",
        "transaction_id": config["transaction_id"],
        "transaction_digest": config["transaction_digest"],
        "stage": failure_stage,
        "error_type": exc_type.__name__,
        "error": str(exc),
        "prune_started": prune_started,
        "units_observed": safe_unit_observations(),
        "settle_observations": settle_observations,
        "systemd_jobs": last_systemd_jobs,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "receipt_path": str(path),
    }
    receipt["receipt_digest"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    emitted = dict(receipt)
    try:
        write_authority_file(
            name,
            (json.dumps(receipt, sort_keys=True) + "\n").encode(),
        )
        emitted["durable_receipt_written"] = True
    except Exception as receipt_exc:
        emitted["durable_receipt_written"] = False
        emitted["durable_receipt_error"] = type(receipt_exc).__name__ + ":" + str(receipt_exc)
    print(json.dumps(emitted, sort_keys=True), file=sys.stderr)

def failure_excepthook(exc_type, exc, traceback):
    write_failure_receipt(exc_type, exc)

def observe_container():
    result = run([
        "docker", "inspect", "--type", "container", "--format",
        "{{json .State}}\n{{json .RestartCount}}\n{{json .Id}}\n{{json .Image}}\n{{json .Config.Image}}\n{{json .Mounts}}",
        config["target"]["container"],
    ])
    if result.returncode != 0:
        raise RuntimeError("container_observation_unknown")
    lines = result.stdout.splitlines()
    if len(lines) != 6:
        raise RuntimeError("container_observation_malformed")
    state, restart_count, container_id, image_id, image_ref, mounts = [json.loads(line) for line in lines]
    workspace_mounts = [item for item in mounts if item.get("Destination") == "/workspace"]
    if len(workspace_mounts) != 1:
        raise RuntimeError("container_workspace_bind_ambiguous")
    mount = workspace_mounts[0]
    observed = {
        "lifecycle": "stopped" if state.get("Running") is False and state.get("Paused") is False and state.get("Restarting") is False else "not-stopped",
        "container_state": state.get("Status"),
        "container_id": container_id,
        "image_id": image_id,
        "image_ref": image_ref,
        "started_at": state.get("StartedAt"),
        "finished_at": state.get("FinishedAt"),
        "restart_count": restart_count,
        "workspace_bind": {
            "status": "present",
            "type": mount.get("Type"),
            "source": mount.get("Source"),
            "destination": mount.get("Destination"),
            "rw": mount.get("RW"),
        },
    }
    for key in ("lifecycle", "container_state", "container_id", "image_id", "image_ref", "workspace_bind", "started_at", "finished_at", "restart_count"):
        if observed[key] != expected_container[key]:
            raise RuntimeError("container_identity_changed:" + key)
    return observed

def observe_inventory():
    values = os.statvfs(workspace)
    workspace_stat = os.stat(workspace, follow_symlinks=False)
    scopes = []
    errors = []
    for expected in expected_inventory["scopes"]:
        path = expected["path"]
        item = {"path": path}
        try:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise RuntimeError("scope_type_unknown")
            usage = run(["du", "-sb", "--one-file-system", "--", path])
            fields = usage.stdout.split()
            if usage.returncode != 0 or len(fields) != 2 or not fields[0].isdigit() or fields[1] != path:
                raise RuntimeError("scope_du_unknown")
            item.update({"status": "available", "size_bytes": int(fields[0])})
        except FileNotFoundError:
            item.update({"status": "absent", "size_bytes": 0})
        except Exception as exc:
            errors.append(path + ":" + str(exc))
            item.update({"status": "unknown", "size_bytes": None})
        scopes.append(item)
    docker = run(["docker", "system", "df", "--format", "{{json .}}"])
    rows = []
    if docker.returncode != 0:
        errors.append("docker_disk_usage_unknown")
    else:
        rows = [json.loads(line) for line in docker.stdout.splitlines() if line.strip()]
    mount = {
        "st_dev": workspace_stat.st_dev,
        "device_major": os.major(workspace_stat.st_dev),
        "device_minor": os.minor(workspace_stat.st_dev),
        "inode": workspace_stat.st_ino,
    }
    best = None
    with open("/proc/self/mountinfo", "r", encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split()
            if "-" not in fields or len(fields) < 10:
                continue
            dash = fields.index("-")
            mount_point = fields[4].replace("\\040", " ")
            if workspace == mount_point or workspace.startswith(mount_point.rstrip("/") + "/"):
                if best is None or len(mount_point) > len(best[0]):
                    best = (mount_point, fields[dash + 1], fields[dash + 2])
    if best is None:
        raise RuntimeError("workspace_mount_identity_unknown")
    mount.update({"mount_point": best[0], "filesystem": best[1], "mount_source": best[2]})
    return {
        "schema": "arnold.cloud.ssh_capacity_inventory.v1",
        "workspace": workspace,
        "filesystem": {
            "free_bytes": values.f_bavail * values.f_frsize,
            "free_inodes": values.f_favail,
            "block_size": values.f_frsize,
        },
        "mount": mount,
        "scopes": scopes,
        "docker_disk_usage": rows,
        "errors": errors,
        "status": "available" if not errors else "unknown",
        "returncode": 0 if not errors else 3,
    }

# All evidence is rechecked in this one fixed remote program immediately before
# its O_EXCL intent reservation and first containment mutation.
container_pre = observe_container()
if observe_inventory() != expected_inventory:
    raise RuntimeError("capacity_inventory_changed")

authority_dir_fd = open_authority_directory()
intent_name = authority_filename(".bootstrap-fence-reclaim.intent")
write_authority_file(intent_name, (config["transaction_digest"] + "\n").encode())
sys.excepthook = failure_excepthook

failure_stage = "observe_units_before_fence"
before = [show_unit(unit) for unit in units]
failure_stage = "stop_units"
for item in before:
    if item["load_state"] not in {"not-found", "loaded", "masked"}:
        raise RuntimeError("unit_load_state_unknown:" + item["unit"])
    if item["load_state"] != "not-found":
        stopped = run(["systemctl", "stop", item["unit"]])
        if stopped.returncode != 0:
            raise RuntimeError("unit_stop_failed:" + item["unit"])

failure_stage = "runtime_mask_units"
for item in before:
    if item["load_state"] != "not-found":
        masked = run(["systemctl", "mask", "--runtime", "--now", item["unit"]])
        if masked.returncode != 0:
            raise RuntimeError("unit_runtime_mask_failed:" + item["unit"])

failure_stage = "settle_units_before_prune"
stopped_units = settle_units(before)
failure_stage = "observe_container_after_stop"
container_after_stop = observe_container()

persistent_units_before_prune, systemd_jobs_before_prune = (
    establish_persistent_fence(before)
)

failure_stage = "verify_no_recovery_sessions_before_prune"
tmux_before = run(["tmux", "list-sessions", "-F", "#S"])
if tmux_before.returncode == 0:
    sessions_before = [line.strip() for line in tmux_before.stdout.splitlines() if line.strip()]
elif tmux_before.returncode == 1 and "no server running" in tmux_before.stderr.lower():
    sessions_before = []
else:
    raise RuntimeError("tmux_observation_unknown")
if set(sessions_before) & set(config["sessions"]):
    raise RuntimeError("forbidden_recovery_session_before_prune")
failure_stage = "verify_no_recovery_processes_before_prune"
ps_before = run(["ps", "-eo", "pid=,args="])
if ps_before.returncode != 0:
    raise RuntimeError("process_observation_unknown")
ignored_before = {os.getpid(), os.getppid()}
for line in ps_before.stdout.splitlines():
    fields = line.strip().split(None, 1)
    if len(fields) == 2 and fields[0].isdigit() and int(fields[0]) not in ignored_before and any(token in fields[1] for token in config["process_tokens"]):
        raise RuntimeError("forbidden_recovery_process_before_prune")

# The only destructive command in this route. No -a, image, container, volume,
# workspace, deploy, or host-cache deletion is reachable from the config.
failure_stage = "docker_dangling_build_cache_prune"
prune_started = True
prune = run(["docker", "builder", "prune", "-f"])
if prune.returncode != 0:
    raise RuntimeError("docker_dangling_build_cache_prune_failed")
container_after_prune = observe_container()

failure_stage = "reverify_persistent_units_after_prune"
after = settle_units(before, require_persistent=True)
for item in after:
    if item["active_state"] == "inactive" and item["persistent_mask"] is True:
        item["state"] = "masked"
    else:
        raise RuntimeError("unit_still_available:" + item["unit"])

container_after = observe_container()
tmux = run(["tmux", "list-sessions", "-F", "#S"])
if tmux.returncode == 0:
    sessions = [line.strip() for line in tmux.stdout.splitlines() if line.strip()]
elif tmux.returncode == 1 and "no server running" in tmux.stderr.lower():
    sessions = []
else:
    raise RuntimeError("tmux_observation_unknown")
forbidden_sessions = sorted(set(sessions) & set(config["sessions"]))
ps = run(["ps", "-eo", "pid=,args="])
if ps.returncode != 0:
    raise RuntimeError("process_observation_unknown")
ignored = {os.getpid(), os.getppid()}
forbidden_processes = []
for line in ps.stdout.splitlines():
    fields = line.strip().split(None, 1)
    if len(fields) == 2 and fields[0].isdigit() and int(fields[0]) not in ignored and any(token in fields[1] for token in config["process_tokens"]):
        forbidden_processes.append({"pid": int(fields[0]), "argv": fields[1]})
if forbidden_sessions or forbidden_processes:
    raise RuntimeError("forbidden_recovery_runtime_present")

failure_stage = "reverify_no_recovery_unit_jobs_after_prune"
systemd_jobs = require_no_recovery_unit_jobs()

final_inventory = observe_inventory()
if final_inventory.get("status") != "available":
    raise RuntimeError("post_reclaim_inventory_unknown")
pre_free = expected_inventory["filesystem"]["free_bytes"]
post_free = final_inventory["filesystem"]["free_bytes"]
post_inodes = final_inventory["filesystem"]["free_inodes"]
if post_free < config["target"]["capacity_floor_bytes"]:
    raise RuntimeError("post_reclaim_capacity_floor_not_met")
receipt = {
    "schema": "arnold.cloud.zero_recovery_bootstrap_fence_reclaim_receipt.v1",
    "status": "passed",
    "transaction_id": config["transaction_id"],
    "transaction_digest": config["transaction_digest"],
    "command_class": "docker_dangling_build_cache_prune",
    "command_argv": ["docker", "builder", "prune", "-f"],
    "returncode": prune.returncode,
    "pre_inventory_digest": config["pre_inventory_digest"],
    "pre_mount": expected_inventory["mount"],
    "post_mount": final_inventory["mount"],
    "pre_free_bytes": pre_free,
    "pre_free_inodes": expected_inventory["filesystem"]["free_inodes"],
    "post_free_bytes": post_free,
    "post_free_inodes": post_inodes,
    "reclaimed_bytes_delta": post_free - pre_free,
    "units_before": before,
    "units_after_stop": stopped_units,
    "units_before_prune": persistent_units_before_prune,
    "units": after,
    "container_pre": container_pre,
    "container_after_stop": container_after_stop,
    "container_after_prune": container_after_prune,
    "container": container_after,
    "forbidden_sessions": forbidden_sessions,
    "forbidden_processes": forbidden_processes,
    "systemd_jobs_before_prune": systemd_jobs_before_prune,
    "systemd_jobs": systemd_jobs,
    "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
receipt_name = authority_filename(".bootstrap-fence-reclaim-receipt.json")
write_authority_file(
    receipt_name,
    (json.dumps(receipt, sort_keys=True) + "\n").encode(),
)
os.close(authority_dir_fd)
print(json.dumps(receipt, sort_keys=True))
""".strip()


def bootstrap_reclaim_command(transaction: Mapping[str, Any]) -> str:
    target = transaction.get("target")
    if (
        not isinstance(transaction, dict)
        or set(transaction) != _BOOTSTRAP_FIELDS
        or not isinstance(target, Mapping)
    ):
        raise CliError("zero_recovery_bootstrap_invalid", "invalid reclaim transaction")
    config = dict(transaction)
    config["units"] = list(ZERO_RECOVERY_UNITS)
    config["sessions"] = list(ZERO_RECOVERY_SESSIONS)
    config["process_tokens"] = list(ZERO_RECOVERY_PROCESS_TOKENS)
    inventory = transaction.get("capacity_inventory")
    if not isinstance(inventory, Mapping):
        raise CliError("zero_recovery_bootstrap_invalid", "invalid reclaim inventory")
    config["pre_inventory_digest"] = _digest(inventory)
    encoded = base64.b64encode(_canonical_bytes(config)).decode("ascii")
    return shlex.join(["python3", "-c", _BOOTSTRAP_RECLAIM_SCRIPT, encoded])


def parse_bootstrap_reclaim_receipt(
    *, stdout: str, transaction_id: str, transaction_digest: str
) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[0]) if len(lines) == 1 else None
    except json.JSONDecodeError as exc:
        raise CliError("zero_recovery_bootstrap_unknown", "invalid reclaim JSON") from exc
    required = {
        "schema", "status", "transaction_id", "transaction_digest",
        "command_class", "command_argv", "returncode", "pre_inventory_digest", "pre_mount", "post_mount",
        "pre_free_bytes", "pre_free_inodes", "post_free_bytes", "post_free_inodes",
        "reclaimed_bytes_delta", "units_before",
        "units_after_stop", "units_before_prune", "units", "container_pre",
        "container_after_stop", "container_after_prune", "container",
        "forbidden_sessions", "forbidden_processes",
        "systemd_jobs_before_prune", "systemd_jobs",
        "observed_at",
    }
    units = payload.get("units") if isinstance(payload, dict) else None
    units_before_prune = (
        payload.get("units_before_prune") if isinstance(payload, dict) else None
    )
    def persistent_units_valid(value: Any, *, terminal: bool) -> bool:
        expected_fields = {
            "unit", "load_state", "active_state", "unit_file_state",
            "persistent_mask",
        } | ({"state"} if terminal else set())
        return bool(
            isinstance(value, list)
            and [item.get("unit") for item in value if isinstance(item, dict)]
            == list(ZERO_RECOVERY_UNITS)
            and all(
                isinstance(item, dict)
                and set(item) == expected_fields
                and item.get("load_state") in {"loaded", "masked"}
                and item.get("active_state") == "inactive"
                and item.get("unit_file_state") == "masked"
                and item.get("persistent_mask") is True
                and (not terminal or item.get("state") == "masked")
                for item in value
            )
        )
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema") != BOOTSTRAP_RECLAIM_RECEIPT_SCHEMA
        or payload.get("status") != "passed"
        or payload.get("transaction_id") != transaction_id
        or payload.get("transaction_digest") != transaction_digest
        or payload.get("command_class") != "docker_dangling_build_cache_prune"
        or payload.get("command_argv") != ["docker", "builder", "prune", "-f"]
        or payload.get("returncode") != 0
        or not isinstance(payload.get("pre_inventory_digest"), str)
        or len(payload.get("pre_inventory_digest")) != 64
        or not isinstance(payload.get("pre_mount"), dict)
        or payload.get("post_mount") != payload.get("pre_mount")
        or any(type(payload.get(key)) is not int for key in ("pre_free_bytes", "pre_free_inodes", "post_free_bytes", "post_free_inodes", "reclaimed_bytes_delta"))
        or payload.get("reclaimed_bytes_delta") != payload.get("post_free_bytes") - payload.get("pre_free_bytes")
        or not persistent_units_valid(units_before_prune, terminal=False)
        or not persistent_units_valid(units, terminal=True)
        or not isinstance(payload.get("container"), dict)
        or payload.get("container", {}).get("lifecycle") != "stopped"
        or payload.get("container_pre") != payload.get("container")
        or payload.get("container_after_stop") != payload.get("container")
        or payload.get("container_after_prune") != payload.get("container")
        or payload.get("forbidden_sessions") != []
        or payload.get("forbidden_processes") != []
        or payload.get("systemd_jobs_before_prune") != []
        or payload.get("systemd_jobs") != []
        or _parse_time(payload.get("observed_at")) is None
    ):
        raise CliError("zero_recovery_bootstrap_unknown", "reclaim receipt failed strict verification")
    return payload


_PRESERVE_SCRIPT = r"""
import base64
import json
import pathlib
import subprocess
import sys

config = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
source = config["source"]
archive = config["archive"]

def inspect(name):
    result = subprocess.run(
        ["docker", "inspect", "--type", "container", "--format", "{{json .State}}\n{{json .RestartCount}}\n{{json .Id}}\n{{json .Image}}\n{{json .Config.Image}}\n{{json .Mounts}}", name],
        text=True, capture_output=True, check=False, timeout=30,
    )
    return result

if inspect(archive).returncode == 0:
    raise RuntimeError("preservation_archive_collision")
before = inspect(source)
if before.returncode != 0 or before.stdout != config["inspect_stdout"]:
    raise RuntimeError("preservation_source_identity_changed")
rename = subprocess.run(["docker", "rename", source, archive], text=True, capture_output=True, check=False, timeout=30)
if rename.returncode != 0:
    raise RuntimeError("preservation_rename_failed")
after = inspect(archive)
original = inspect(source)
if after.returncode != 0 or after.stdout != config["inspect_stdout"] or original.returncode == 0:
    raise RuntimeError("preservation_postcondition_failed")
receipt = {
    "schema": "arnold.cloud.zero_recovery_container_preservation.v1",
    "status": "passed",
    "transaction_id": config["transaction_id"],
    "transaction_digest": config["transaction_digest"],
    "source_name": source,
    "archive_name": archive,
    "container_id": config["container_id"],
    "image_id": config["image_id"],
    "workspace_bind": config["workspace_bind"],
    "started_at": config["started_at"],
    "finished_at": config["finished_at"],
    "restart_count": config["restart_count"],
    "command_argv": ["docker", "rename", source, archive],
}
root = pathlib.Path(config["workspace"]) / ".megaplan" / "zero-recovery"
path = root / "preserved-v2-container-receipt.json"
fd = __import__("os").open(path, __import__("os").O_WRONLY | __import__("os").O_CREAT | __import__("os").O_EXCL, 0o600)
with __import__("os").fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    handle.flush()
    __import__("os").fsync(handle.fileno())
print(json.dumps(receipt, sort_keys=True))
""".strip()


def preserve_container_command(transaction: Mapping[str, Any]) -> tuple[str, str]:
    outer = transaction.get("container_observation")
    target = transaction.get("target")
    if not isinstance(outer, Mapping) or not isinstance(target, Mapping):
        raise CliError("zero_recovery_preservation_invalid", "missing preservation identity")
    container_id = outer.get("container_id")
    source = target.get("container")
    if not isinstance(container_id, str) or len(container_id) < 12 or not isinstance(source, str):
        raise CliError("zero_recovery_preservation_invalid", "invalid preservation identity")
    archive = f"{source}-v2-preserved-{container_id[:12]}"
    state = {
        "Status": outer.get("container_state"),
        "Running": False,
        "Paused": False,
        "Restarting": False,
        "OOMKilled": outer.get("oom_killed"),
        "ExitCode": outer.get("exit_code"),
        "Error": outer.get("error"),
        "StartedAt": outer.get("started_at"),
        "FinishedAt": outer.get("finished_at"),
    }
    mount = outer.get("workspace_bind")
    docker_mount = [{
        "Type": mount.get("type"), "Source": mount.get("source"),
        "Destination": mount.get("destination"), "RW": mount.get("rw"),
    }] if isinstance(mount, Mapping) else []
    inspect_stdout = "\n".join(
        json.dumps(value, separators=(",", ":"))
        for value in (
            state, outer.get("restart_count"), container_id, outer.get("image_id"),
            outer.get("image_ref"), docker_mount,
        )
    ) + "\n"
    config = {
        "source": source, "archive": archive,
        "workspace": target.get("workspace"),
        "transaction_id": transaction.get("transaction_id"),
        "transaction_digest": transaction.get("transaction_digest"),
        "container_id": container_id, "image_id": outer.get("image_id"),
        "workspace_bind": mount, "started_at": outer.get("started_at"),
        "finished_at": outer.get("finished_at"),
        "restart_count": outer.get("restart_count"), "inspect_stdout": inspect_stdout,
    }
    encoded = base64.b64encode(_canonical_bytes(config)).decode("ascii")
    return shlex.join(["python3", "-c", _PRESERVE_SCRIPT, encoded]), archive


def parse_preservation_receipt(
    *, stdout: str, transaction: Mapping[str, Any], archive: str
) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[0]) if len(lines) == 1 else None
    except json.JSONDecodeError as exc:
        raise CliError("zero_recovery_preservation_unknown", "invalid preservation JSON") from exc
    outer = transaction["container_observation"]
    required = {"schema", "status", "transaction_id", "transaction_digest", "source_name", "archive_name", "container_id", "image_id", "workspace_bind", "started_at", "finished_at", "restart_count", "command_argv"}
    if (
        not isinstance(payload, dict) or set(payload) != required
        or payload.get("schema") != PRESERVATION_SCHEMA or payload.get("status") != "passed"
        or payload.get("transaction_id") != transaction.get("transaction_id")
        or payload.get("transaction_digest") != transaction.get("transaction_digest")
        or payload.get("source_name") != transaction["target"]["container"]
        or payload.get("archive_name") != archive
        or payload.get("container_id") != outer.get("container_id")
        or payload.get("image_id") != outer.get("image_id")
        or payload.get("workspace_bind") != outer.get("workspace_bind")
        or payload.get("started_at") != outer.get("started_at")
        or payload.get("finished_at") != outer.get("finished_at")
        or payload.get("restart_count") != outer.get("restart_count")
        or payload.get("command_argv") != ["docker", "rename", transaction["target"]["container"], archive]
    ):
        raise CliError("zero_recovery_preservation_unknown", "preservation receipt mismatch")
    return payload


_FENCE_SCRIPT = r"""
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

workspace, action, config_b64 = sys.argv[1:4]
config = json.loads(__import__("base64").b64decode(config_b64).decode("utf-8"))
units = config["units"]
authority_root = pathlib.Path("/var/lib/arnold-zero-recovery")
failure_stage = "before_intent"
marker_published = False
last_fence_jobs = []

def open_authority_directory(create):
    created = False
    if create:
        try:
            os.mkdir(authority_root, 0o700)
            created = True
        except FileExistsError:
            pass
    if created:
        parent_fd = os.open(
            authority_root.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            parent = os.fstat(parent_fd)
            if (
                not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != 0
                or parent.st_gid != 0
            ):
                raise RuntimeError("authority_parent_identity_invalid")
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    try:
        observed = os.lstat(authority_root)
    except FileNotFoundError as exc:
        raise RuntimeError("authority_directory_missing") from exc
    if (
        not stat.S_ISDIR(observed.st_mode)
        or stat.S_ISLNK(observed.st_mode)
        or observed.st_uid != 0
        or observed.st_gid != 0
        or stat.S_IMODE(observed.st_mode) != 0o700
    ):
        raise RuntimeError("authority_directory_identity_invalid")
    fd = os.open(
        authority_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    opened = os.fstat(fd)
    if (
        opened.st_dev != observed.st_dev
        or opened.st_ino != observed.st_ino
        or opened.st_uid != 0
        or opened.st_gid != 0
        or stat.S_IMODE(opened.st_mode) != 0o700
    ):
        os.close(fd)
        raise RuntimeError("authority_directory_identity_changed")
    return fd

def read_authority_file(directory_fd, name):
    observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if (
        not stat.S_ISREG(observed.st_mode)
        or observed.st_uid != 0
        or observed.st_gid != 0
        or stat.S_IMODE(observed.st_mode) != 0o600
        or observed.st_nlink != 1
    ):
        raise RuntimeError("authority_file_identity_invalid:" + name)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        if (
            opened.st_dev != observed.st_dev
            or opened.st_ino != observed.st_ino
            or opened.st_uid != 0
            or opened.st_gid != 0
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
        ):
            raise RuntimeError("authority_file_identity_changed:" + name)
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read()
    finally:
        os.close(fd)
    identity = {
        "path": str(authority_root / name),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "uid": opened.st_uid,
        "gid": opened.st_gid,
        "mode": stat.S_IMODE(opened.st_mode),
        "st_dev": opened.st_dev,
        "st_ino": opened.st_ino,
    }
    return raw, identity

def write_authority_file(directory_fd, name, raw):
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        os.fchmod(fd, 0o600)
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != 0
            or opened.st_gid != 0
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
        ):
            raise RuntimeError("authority_file_identity_invalid:" + name)
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.fsync(directory_fd)
    return read_authority_file(directory_fd, name)

def strict_object(raw, label):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(label + "_duplicate_field")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(label + "_invalid_json") from exc
    if not isinstance(value, dict):
        raise RuntimeError(label + "_not_object")
    return value

def require_expected_marker(raw):
    expected = {
        "schema": "arnold.cloud.zero_recovery_marker.v2",
        "profile": "ZERO_RECOVERY_NONROOT_FINITE_CANARY",
        "scope": "HOST_GLOBAL_PERSISTENT_CONTAINMENT",
        "active": True,
    }
    value = strict_object(raw, "existing_zero_recovery_marker")
    expected_raw = (json.dumps(expected, sort_keys=True) + "\n").encode()
    if value != expected or raw != expected_raw:
        raise RuntimeError("existing_zero_recovery_marker_transaction_mismatch")
    return value

def persist_or_require_exact(directory_fd, name, raw, label):
    try:
        return write_authority_file(directory_fd, name, raw)
    except FileExistsError:
        existing_raw, identity = read_authority_file(directory_fd, name)
        if existing_raw != raw:
            raise RuntimeError(label + "_subject_mismatch")
        return existing_raw, identity

def run(argv, timeout_seconds=30):
    return subprocess.run(
        argv, text=True, capture_output=True, check=False, timeout=timeout_seconds,
    )

def show_unit(unit, timeout_seconds=30):
    result = run(
        ["systemctl", "show", unit, "--property=LoadState", "--property=ActiveState", "--property=UnitFileState", "--value"],
        timeout_seconds=timeout_seconds,
    )
    values = result.stdout.splitlines()
    if result.returncode != 0 or len(values) != 3 or not values[0] or not values[1] or (values[0] != "not-found" and not values[2]):
        raise RuntimeError("unit_observation_unknown:" + unit)
    persistent = pathlib.Path("/etc/systemd/system") / unit
    if os.path.lexists(persistent):
        persistent_identity = os.lstat(persistent)
        persistent_mask = (
            stat.S_ISLNK(persistent_identity.st_mode)
            and persistent_identity.st_uid == 0
            and persistent_identity.st_gid == 0
            and os.readlink(persistent) == "/dev/null"
        )
    else:
        persistent_mask = False
    return {"unit": unit, "load_state": values[0], "active_state": values[1], "unit_file_state": values[2], "persistent_mask": persistent_mask}

def settle_units(before_items):
    deadline = time.monotonic() + 5.0
    reset_units = set()
    originally_absent = {
        item["unit"] for item in before_items if item["load_state"] == "not-found"
    }
    while True:
        current = []
        for before_item in before_items:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("unit_settle_timeout")
            try:
                current.append(
                    show_unit(
                        before_item["unit"], timeout_seconds=min(0.5, remaining)
                    )
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "unit_settle_observation_timeout:" + before_item["unit"]
                ) from exc
        pending = False
        for item in current:
            unit = item["unit"]
            if unit in originally_absent:
                if (
                    item["load_state"] != "not-found"
                    or item["active_state"] != "inactive"
                    or item["unit_file_state"] not in {"", "disabled"}
                    or item["persistent_mask"] is not False
                ):
                    raise RuntimeError("unit_absence_drift_during_settle:" + unit)
                continue
            if (
                item["load_state"] not in {"loaded", "masked"}
                or item["unit_file_state"] != "masked"
                or item["persistent_mask"] is not True
            ):
                raise RuntimeError("unit_persistent_mask_drift_during_settle:" + unit)
            active = item["active_state"]
            if active == "inactive":
                continue
            if active == "failed":
                if unit in reset_units:
                    raise RuntimeError("unit_failed_after_reset:" + unit)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("unit_settle_timeout")
                try:
                    reset = run(
                        ["systemctl", "reset-failed", unit],
                        timeout_seconds=min(1.0, remaining),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("unit_reset_failed:" + unit) from exc
                if reset.returncode != 0:
                    raise RuntimeError("unit_reset_failed:" + unit)
                reset_units.add(unit)
                pending = True
                continue
            if active in {"activating", "deactivating"}:
                pending = True
                continue
            raise RuntimeError(
                "unit_invalid_active_state_during_settle:" + unit + ":" + active
            )
        if not pending:
            return current
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("unit_settle_timeout")
        time.sleep(min(0.2, remaining))

def observe_recovery_unit_jobs():
    global last_fence_jobs
    result = run(
        ["systemctl", "list-jobs", "--no-legend", "--no-pager"],
        timeout_seconds=1.0,
    )
    if result.returncode != 0:
        raise RuntimeError("systemd_jobs_observation_unknown")
    jobs = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and any(unit in line.split() for unit in units)
    ]
    if jobs:
        raise RuntimeError("recovery_unit_job_queued:" + jobs[0])
    last_fence_jobs = jobs
    return jobs

def safe_fence_unit_observations():
    observed = []
    for unit in units:
        try:
            observed.append(show_unit(unit, timeout_seconds=0.5))
        except Exception as exc:
            observed.append({"unit": unit, "observation_error": str(exc)})
    return observed

def write_fence_failure_receipt(exc_type, exc):
    name = (
        config["transaction_id"] + ".host-zero-recovery-fence-" + action
        + "-failure.json"
    )
    path = authority_root / name
    receipt = {
        "schema": "arnold.cloud.zero_recovery_host_fence_failure.v1",
        "status": "failed",
        "stage": failure_stage,
        "action": action,
        "transaction_id": config["transaction_id"],
        "transaction_digest": config["transaction_digest"],
        "marker_published": marker_published,
        "error_type": exc_type.__name__,
        "error": str(exc),
        "units_observed": safe_fence_unit_observations(),
        "systemd_jobs": last_fence_jobs,
        "receipt_path": str(path),
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    receipt["receipt_digest"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    emitted = dict(receipt)
    try:
        write_authority_file(
            authority_dir_fd,
            name,
            (json.dumps(receipt, sort_keys=True) + "\n").encode(),
        )
        emitted["durable_receipt_written"] = True
    except Exception as receipt_exc:
        emitted["durable_receipt_written"] = False
        emitted["durable_receipt_error"] = (
            type(receipt_exc).__name__ + ":" + str(receipt_exc)
        )
    print(json.dumps(emitted, sort_keys=True), file=sys.stderr)

def fence_failure_excepthook(exc_type, exc, traceback):
    write_fence_failure_receipt(exc_type, exc)

if action not in {"apply", "verify"}:
    raise RuntimeError("unsupported_fence_action")
authority_dir_fd = open_authority_directory(action == "apply")

intent = {
    "schema": "arnold.cloud.zero_recovery_host_fence_intent.v1",
    "action": action,
    "transaction_id": config["transaction_id"],
    "transaction_digest": config["transaction_digest"],
}
intent_raw = (json.dumps(intent, sort_keys=True) + "\n").encode()
intent_name = (
    config["transaction_id"] + ".host-zero-recovery-fence-" + action + ".intent"
)
persist_or_require_exact(
    authority_dir_fd, intent_name, intent_raw, "existing_fence_intent"
)
sys.excepthook = fence_failure_excepthook
failure_stage = "observe_units_before_fence"

before = [show_unit(unit) for unit in units]
for item in before:
    if item["load_state"] == "not-found":
        item["state"] = "absent"
    elif item["load_state"] in {"loaded", "masked"}:
        item["state"] = "present"
    else:
        raise RuntimeError("unit_load_state_unknown:" + item["unit"])

marker_name = "active.json"
expected_marker = {
    "schema": "arnold.cloud.zero_recovery_marker.v2",
    "profile": "ZERO_RECOVERY_NONROOT_FINITE_CANARY",
    "scope": "HOST_GLOBAL_PERSISTENT_CONTAINMENT",
    "active": True,
}
expected_marker_raw = (json.dumps(expected_marker, sort_keys=True) + "\n").encode()
try:
    marker_raw, marker_identity = read_authority_file(
        authority_dir_fd, marker_name
    )
except FileNotFoundError:
    marker_raw = None
    marker_identity = None
if marker_raw is not None:
    require_expected_marker(marker_raw)
    marker_published = True
elif action == "verify":
    raise RuntimeError("zero_recovery_marker_missing")

if action == "apply":
    failure_stage = "install_persistent_unit_masks"
    for item in before:
        if item["state"] == "present":
            result = run(["systemctl", "mask", "--now", item["unit"]])
            if result.returncode != 0:
                raise RuntimeError("unit_mask_stop_failed:" + item["unit"])
    mask_root_fd = os.open(
        "/etc/systemd/system",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        mask_root_identity = os.fstat(mask_root_fd)
        if (
            not stat.S_ISDIR(mask_root_identity.st_mode)
            or mask_root_identity.st_uid != 0
            or mask_root_identity.st_gid != 0
        ):
            raise RuntimeError("persistent_mask_directory_identity_invalid")
        os.fsync(mask_root_fd)
    finally:
        os.close(mask_root_fd)
    failure_stage = "daemon_reload_persistent_unit_masks"
    daemon_reload = run(["systemctl", "daemon-reload"])
    if daemon_reload.returncode != 0:
        raise RuntimeError("systemd_daemon_reload_failed")

failure_stage = "settle_persistent_units"
after = settle_units(before)
for item in after:
    if item["load_state"] == "not-found":
        item["state"] = "absent"
    elif (
        item["active_state"] == "inactive"
        and item["unit_file_state"] == "masked"
        and item["persistent_mask"] is True
    ):
        item["state"] = "masked"
    else:
        raise RuntimeError("unit_still_available:" + item["unit"])

failure_stage = "verify_no_recovery_unit_jobs"
systemd_jobs = observe_recovery_unit_jobs()

failure_stage = "verify_no_recovery_sessions"
tmux = run(["tmux", "list-sessions", "-F", "#S"])
if tmux.returncode == 0:
    sessions = [line.strip() for line in tmux.stdout.splitlines() if line.strip()]
elif tmux.returncode == 1 and "no server running" in tmux.stderr.lower():
    sessions = []
else:
    raise RuntimeError("tmux_observation_unknown")
forbidden_sessions = sorted(set(sessions) & set(config["sessions"]))

failure_stage = "verify_no_recovery_processes"
ps = run(["ps", "-eo", "pid=,args="])
if ps.returncode != 0:
    raise RuntimeError("process_observation_unknown")
ignored = {os.getpid(), os.getppid()}
forbidden_processes = []
for line in ps.stdout.splitlines():
    fields = line.strip().split(None, 1)
    if len(fields) != 2 or not fields[0].isdigit() or int(fields[0]) in ignored:
        continue
    if any(token in fields[1] for token in config["process_tokens"]):
        forbidden_processes.append({"pid": int(fields[0]), "argv": fields[1]})
if forbidden_sessions or forbidden_processes:
    raise RuntimeError("forbidden_recovery_runtime_present")

failure_stage = "publish_global_containment_marker"
marker_raw, marker_identity = persist_or_require_exact(
    authority_dir_fd,
    marker_name,
    expected_marker_raw,
    "existing_zero_recovery_marker",
)
require_expected_marker(marker_raw)
marker_published = True

def build_fence_receipt(
    stage, marker_subject, observed_units, sessions, processes, jobs
):
    return {
        "schema": "arnold.cloud.zero_recovery_host_fence.v1",
        "status": "passed",
        "stage": stage,
        "transaction_id": config["transaction_id"],
        "transaction_digest": config["transaction_digest"],
        "marker": marker_subject,
        "units": observed_units,
        "forbidden_sessions": sessions,
        "forbidden_processes": processes,
        "systemd_jobs": jobs,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

def persist_or_reuse_fence_receipt(directory_fd, name, receipt):
    raw = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    try:
        write_authority_file(directory_fd, name, raw)
        return receipt
    except FileExistsError:
        existing_raw, _ = read_authority_file(directory_fd, name)
        existing = strict_object(existing_raw, "existing_fence_receipt")
        canonical_existing = (json.dumps(existing, sort_keys=True) + "\n").encode()
        if (
            existing_raw != canonical_existing
            or set(existing) != set(receipt)
            or existing.get("schema") != "arnold.cloud.zero_recovery_host_fence.v1"
            or existing.get("status") != "passed"
        ):
            raise RuntimeError("existing_fence_receipt_noncanonical")
        existing_subject = dict(existing)
        current_subject = dict(receipt)
        existing_subject.pop("observed_at", None)
        current_subject.pop("observed_at", None)
        if existing_subject != current_subject:
            raise RuntimeError("existing_fence_receipt_subject_mismatch")
        return existing

receipt = build_fence_receipt(
    action,
    marker_identity,
    after,
    forbidden_sessions,
    forbidden_processes,
    systemd_jobs,
)
receipt_name = (
    config["transaction_id"] + ".host-zero-recovery-fence-" + action + ".json"
)
receipt = persist_or_reuse_fence_receipt(
    authority_dir_fd, receipt_name, receipt
)
os.close(authority_dir_fd)
print(json.dumps(receipt, sort_keys=True))
""".strip()


def fence_command(
    workspace: str, *, action: str, transaction_id: str, transaction_digest: str
) -> str:
    if action not in {"apply", "verify"}:
        raise CliError("invalid_provider_observation_target", "invalid fence action")
    path = PurePosixPath(workspace)
    if not path.is_absolute() or ".." in path.parts or workspace == "/":
        raise CliError("invalid_provider_observation_target", "invalid fence workspace")
    if (
        not isinstance(transaction_id, str)
        or not transaction_id
        or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
            for character in transaction_id
        )
    ):
        raise CliError("invalid_provider_observation_target", "invalid transaction id")
    if (
        not isinstance(transaction_digest, str)
        or len(transaction_digest) != 64
        or any(character not in "0123456789abcdef" for character in transaction_digest)
    ):
        raise CliError("invalid_provider_observation_target", "invalid transaction digest")
    config = {
        "units": list(ZERO_RECOVERY_UNITS),
        "sessions": list(ZERO_RECOVERY_SESSIONS),
        "process_tokens": list(ZERO_RECOVERY_PROCESS_TOKENS),
        "transaction_id": transaction_id,
        "transaction_digest": transaction_digest,
    }
    encoded = base64.b64encode(_canonical_bytes(config)).decode("ascii")
    return shlex.join(["python3", "-c", _FENCE_SCRIPT, workspace, action, encoded])


def parse_fence_receipt(
    *, stdout: str, transaction_id: str, transaction_digest: str, stage: str
) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[0]) if len(lines) == 1 else None
    except json.JSONDecodeError as exc:
        raise CliError("zero_recovery_fence_unknown", "fence output was invalid JSON") from exc
    required = {
        "schema",
        "status",
        "stage",
        "transaction_id",
        "transaction_digest",
        "marker",
        "units",
        "forbidden_sessions",
        "forbidden_processes",
        "systemd_jobs",
        "observed_at",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise CliError("zero_recovery_fence_unknown", "fence receipt schema mismatch")
    units = payload.get("units")
    marker = payload.get("marker")
    unit_names = [item.get("unit") for item in units] if isinstance(units, list) else []
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
    if (
        payload.get("schema") != FENCE_SCHEMA
        or payload.get("status") != "passed"
        or payload.get("stage") != stage
        or payload.get("transaction_id") != transaction_id
        or payload.get("transaction_digest") != transaction_digest
        or not isinstance(marker, dict)
        or set(marker)
        != {"path", "sha256", "uid", "gid", "mode", "st_dev", "st_ino"}
        or marker.get("path") != "/var/lib/arnold-zero-recovery/active.json"
        or marker.get("sha256") != hashlib.sha256(marker_raw).hexdigest()
        or marker.get("uid") != 0
        or marker.get("gid") != 0
        or marker.get("mode") != 0o600
        or type(marker.get("st_dev")) is not int
        or type(marker.get("st_ino")) is not int
        or marker.get("st_dev") < 0
        or marker.get("st_ino") <= 0
        or unit_names != list(ZERO_RECOVERY_UNITS)
        or any(
            not isinstance(item, dict)
            or set(item)
            != {
                "unit", "load_state", "active_state", "unit_file_state",
                "persistent_mask", "state",
            }
            or item.get("state") not in {"absent", "masked"}
            or any(not isinstance(item.get(key), str) or not item.get(key) for key in ("unit", "load_state", "active_state"))
            or not isinstance(item.get("unit_file_state"), str)
            or (
                item.get("state") == "masked"
                and (
                    item.get("active_state") != "inactive"
                    or item.get("unit_file_state") != "masked"
                    or item.get("persistent_mask") is not True
                )
            )
            or (
                item.get("state") == "absent"
                and (
                    item.get("load_state") != "not-found"
                    or item.get("active_state") != "inactive"
                    or item.get("unit_file_state") not in {"", "disabled"}
                    or item.get("persistent_mask") is not False
                )
            )
            for item in (units or [])
        )
        or payload.get("forbidden_sessions") != []
        or payload.get("forbidden_processes") != []
        or payload.get("systemd_jobs") != []
        or _parse_time(payload.get("observed_at")) is None
    ):
        raise CliError("zero_recovery_fence_unknown", "fence receipt failed strict verification")
    return payload


__all__ = [
    "FENCE_SCHEMA",
    "PREDEPLOY_SCHEMA",
    "ZERO_RECOVERY_PROCESS_TOKENS",
    "ZERO_RECOVERY_SESSIONS",
    "ZERO_RECOVERY_UNITS",
    "build_predeploy_transaction",
    "fence_command",
    "parse_fence_receipt",
    "validate_predeploy_transaction",
]
