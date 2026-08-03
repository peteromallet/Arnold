"""Finite SSH resident-only recovery and exact rollback commands.

The public builders expose only two fixed host transactions.  They do not
accept an arbitrary shell command, read secret contents, or start any of the
ordinary cloud entrypoint supervisors.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.providers.ssh_preflight import (
    validate_container_name,
    validate_workspace_dir,
)
from arnold_pipelines.megaplan.types import CliError


RECOVER_SCHEMA = "arnold.cloud.resident_only_recovery.v1"
DOWN_SCHEMA = "arnold.cloud.resident_only_down.v1"
START_SCHEMA = "arnold.cloud.resident_only_start.v1"
HEALTH_SCHEMA = "arnold.cloud.resident_only_health.v1"
FENCE_SCHEMA = "arnold.cloud.resident_only_source_fence.v1"
_EPOCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_CONTAINER_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

RESIDENT_ONLY_COMMAND = """set -euo pipefail
set -a
. /workspace/.secrets/megaplan-resident-discord.env
[[ ! -f /workspace/.cloud-hot-env ]] || . /workspace/.cloud-hot-env
[[ ! -f /workspace/.megaplan/resident-runtime.env ]] || . /workspace/.megaplan/resident-runtime.env
set +a
runtime_src=${MEGAPLAN_RUNTIME_SRC:-${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}}
runtime_python=${MEGAPLAN_RUNTIME_PYTHON:-python}
store_root=${MEGAPLAN_RESIDENT_STORE_ROOT:-/workspace/arnold/.megaplan/resident}
cd "$runtime_src"
export PYTHONPATH=$runtime_src:${PYTHONPATH:-}
export MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=${MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE:-production}
exec "$runtime_python" -P -m arnold_pipelines.megaplan resident discord --listener-only --mode ${MEGAPLAN_RESIDENT_MODE:-production} --store-root "$store_root"
""".strip()

_LISTENER_PREFLIGHT_COMMAND = """set -euo pipefail
set -a
[[ ! -f /workspace/.cloud-hot-env ]] || . /workspace/.cloud-hot-env
[[ ! -f /workspace/.megaplan/resident-runtime.env ]] || . /workspace/.megaplan/resident-runtime.env
set +a
runtime_src=${MEGAPLAN_RUNTIME_SRC:-${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}}
runtime_python=${MEGAPLAN_RUNTIME_PYTHON:-python}
cd "$runtime_src"
export PYTHONPATH=$runtime_src:${PYTHONPATH:-}
exec "$runtime_python" -P -m arnold_pipelines.megaplan resident discord --help
""".strip()


def validate_outage_epoch(value: str) -> str:
    if not isinstance(value, str) or not _EPOCH_RE.fullmatch(value):
        raise CliError(
            "resident_recovery_invalid",
            "outage epoch must be a 1-64 character safe durable identifier",
        )
    return value


def validate_container_id(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _CONTAINER_ID_RE.fullmatch(value):
        raise CliError("resident_recovery_invalid", f"{label} must be an exact Docker container ID")
    return value


def validate_image_id(value: str) -> str:
    if not isinstance(value, str) or not _IMAGE_ID_RE.fullmatch(value):
        raise CliError("resident_recovery_invalid", "expected source image must be an exact sha256 image ID")
    return value


def resident_only_container_name(source_container: str) -> str:
    source = validate_container_name(source_container)
    suffix = "-resident-only"
    if len(source) + len(suffix) <= 128:
        return source + suffix
    digest = hashlib.sha256(source.encode()).hexdigest()[:12]
    return source[: 128 - len(suffix) - len(digest) - 1] + "-" + digest + suffix


def _encoded_config(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


_RECOVER_SCRIPT = r'''
import base64, hashlib, json, os, stat, subprocess, sys, time

cfg = json.loads(base64.b64decode(sys.argv[1], validate=True))
command = cfg["resident_command"]
listener_preflight = cfg["listener_preflight_command"]
if hashlib.sha256(command.encode()).hexdigest() != cfg["resident_command_sha256"]:
    raise RuntimeError("resident_command_digest_mismatch")
if hashlib.sha256(listener_preflight.encode()).hexdigest() != cfg["listener_preflight_command_sha256"]:
    raise RuntimeError("listener_preflight_command_digest_mismatch")

def call(argv, *, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError("fixed_docker_operation_failed:" + argv[1])
    return result

def inspect(identifier):
    result = call(["docker", "inspect", "--type=container", identifier], check=False)
    if result.returncode != 0:
        diagnostic = (result.stderr or "").strip()
        if result.returncode == 1 and ("No such container" in diagnostic or "No such object" in diagnostic):
            return None
        raise RuntimeError("container_inspect_failed")
    value = json.loads(result.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise RuntimeError("container_inspect_invalid")
    return value[0]

def workspace_mount(item):
    mounts = item.get("Mounts")
    rows = [row for row in mounts if isinstance(row, dict) and row.get("Destination") == "/workspace"] if isinstance(mounts, list) else []
    if len(rows) != 1:
        raise RuntimeError("workspace_bind_missing_or_ambiguous")
    row = rows[0]
    return {"type": row.get("Type"), "source": row.get("Source"), "destination": "/workspace", "rw": row.get("RW")}

def source_identity(item, *, require_fenced):
    state, host = item.get("State"), item.get("HostConfig")
    policy = host.get("RestartPolicy") if isinstance(host, dict) else None
    if (
        item.get("Id") != cfg["expected_source_container_id"]
        or item.get("Image") != cfg["expected_source_image_id"]
        or item.get("Name") != "/" + cfg["source_container"]
        or not isinstance(state, dict)
        or state.get("Running") is not False
        or state.get("Paused") is not False
        or state.get("Restarting") is not False
        or not isinstance(policy, dict)
        or set(policy) != {"Name", "MaximumRetryCount"}
        or not isinstance(policy.get("Name"), str)
        or type(policy.get("MaximumRetryCount")) is not int
        or (require_fenced and policy != {"Name": "no", "MaximumRetryCount": 0})
        or workspace_mount(item) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
    ):
        raise RuntimeError("source_compare_and_swap_failed")
    return policy

def exact_source(*, require_fenced):
    by_id = inspect(cfg["expected_source_container_id"])
    by_name = inspect(cfg["source_container"])
    if by_id is None or by_name is None or by_id.get("Id") != by_name.get("Id"):
        raise RuntimeError("source_name_identity_mismatch")
    return by_id, source_identity(by_id, require_fenced=require_fenced)

def ensure_receipt_root():
    workspace = cfg["workspace"]
    root_stat = os.lstat(workspace)
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode) or os.path.realpath(workspace) != workspace:
        raise RuntimeError("workspace_not_canonical")
    megaplan = os.path.join(workspace, ".megaplan")
    os.makedirs(megaplan, mode=0o700, exist_ok=True)
    if not stat.S_ISDIR(os.lstat(megaplan).st_mode) or stat.S_ISLNK(os.lstat(megaplan).st_mode):
        raise RuntimeError("receipt_parent_invalid")
    root = os.path.join(megaplan, "resident-only-recovery")
    os.makedirs(root, mode=0o700, exist_ok=True)
    if not stat.S_ISDIR(os.lstat(root).st_mode) or stat.S_ISLNK(os.lstat(root).st_mode):
        raise RuntimeError("receipt_root_invalid")
    return root

def write_once(path, payload):
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data); os.fsync(fd)
    finally:
        os.close(fd)
    parent_fd = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)

def read_exact(path):
    item_stat = os.lstat(path)
    if not stat.S_ISREG(item_stat.st_mode) or stat.S_ISLNK(item_stat.st_mode):
        raise RuntimeError("receipt_file_invalid")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)

def resident_identity(item):
    state, host, config = item.get("State"), item.get("HostConfig"), item.get("Config")
    expected_cmd = hashlib.sha256(json.dumps(["-lc", command], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    actual_cmd = hashlib.sha256(json.dumps(config.get("Cmd") if isinstance(config, dict) else None, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (
        item.get("Image") != cfg["expected_source_image_id"]
        or item.get("Name") != "/" + cfg["resident_container"]
        or not isinstance(config, dict) or config.get("Entrypoint") != ["/bin/bash"]
        or actual_cmd != expected_cmd
        or not isinstance(host, dict)
        or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
        or host.get("CapDrop") != ["ALL"] or host.get("CapAdd") not in (None, [])
        or host.get("SecurityOpt") != ["no-new-privileges:true"]
        or host.get("PidsLimit") != 256 or host.get("Memory") != 2147483648
        or host.get("MemorySwap") != 2147483648
        or workspace_mount(item) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
        or not isinstance(state, dict) or not isinstance(state.get("StartedAt"), str)
    ):
        raise RuntimeError("resident_container_identity_mismatch")
    return {"container_id": item.get("Id"), "running": state.get("Running") is True, "exit_code": state.get("ExitCode"), "started_at": state.get("StartedAt")}

root = ensure_receipt_root()
prefix = os.path.join(root, cfg["outage_epoch"])
fence_intent_path, fence_path = prefix + ".fence.intent.json", prefix + ".fence.json"
intent_path, start_path, health_path = prefix + ".intent.json", prefix + ".start.json", prefix + ".health.json"
down_path = prefix + ".down.json"

# Finish all non-mutating prerequisites before changing source policy.
exact_source(require_fenced=False)
if os.path.exists(down_path):
    raise RuntimeError("resident_outage_epoch_already_down")
if not os.path.exists(intent_path) and inspect(cfg["resident_container"]) is not None:
    raise RuntimeError("resident_singleton_collision")
statvfs = os.statvfs(cfg["workspace"])
if statvfs.f_bavail * statvfs.f_frsize < cfg["min_free_bytes"] + cfg["receipt_reserve_bytes"] or statvfs.f_favail < cfg["min_free_inodes"]:
    raise RuntimeError("resident_recovery_capacity_floor_failed")
secret_path = os.path.join(cfg["workspace"], ".secrets", "megaplan-resident-discord.env")
secret_stat = os.lstat(secret_path)
if not stat.S_ISREG(secret_stat.st_mode) or stat.S_ISLNK(secret_stat.st_mode) or secret_stat.st_size <= 0:
    raise RuntimeError("resident_secret_file_invalid")

# Fence the preserved predecessor before any probe can race a daemon restart.
_, observed_policy = exact_source(require_fenced=False)
fence_intent = {
    "schema": "arnold.cloud.resident_only_source_fence_intent.v1",
    "outage_epoch": cfg["outage_epoch"], "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"], "source_image_id": cfg["expected_source_image_id"],
    "workspace": cfg["workspace"], "prior_restart_policy": observed_policy,
}
if os.path.exists(fence_intent_path):
    fence_intent = read_exact(fence_intent_path)
    if fence_intent.get("schema") != "arnold.cloud.resident_only_source_fence_intent.v1" or fence_intent.get("source_container_id") != cfg["expected_source_container_id"] or fence_intent.get("source_image_id") != cfg["expected_source_image_id"] or fence_intent.get("workspace") != cfg["workspace"]:
        raise RuntimeError("source_fence_intent_mismatch")
else:
    write_once(fence_intent_path, fence_intent)
prior_policy = fence_intent["prior_restart_policy"]
if observed_policy != {"Name": "no", "MaximumRetryCount": 0}:
    if observed_policy != prior_policy:
        raise RuntimeError("source_restart_policy_changed_before_fence")
    call(["docker", "update", "--restart", "no", cfg["expected_source_container_id"]])
# If the old restart policy revived the exact source during the inspect/update
# window, stop that immutable ID before admitting any resident launch.
post_fence = inspect(cfg["expected_source_container_id"])
post_host = post_fence.get("HostConfig") if isinstance(post_fence, dict) else None
post_state = post_fence.get("State") if isinstance(post_fence, dict) else None
if (
    post_fence is None
    or post_fence.get("Id") != cfg["expected_source_container_id"]
    or post_fence.get("Image") != cfg["expected_source_image_id"]
    or post_fence.get("Name") != "/" + cfg["source_container"]
    or workspace_mount(post_fence) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
    or not isinstance(post_host, dict)
    or post_host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
    or not isinstance(post_state, dict)
):
    raise RuntimeError("source_fence_post_update_mismatch")
if post_state.get("Running") is True:
    call(["docker", "stop", "--time", "15", cfg["expected_source_container_id"]])
exact_source(require_fenced=True)
fence_receipt = {
    "schema": "arnold.cloud.resident_only_source_fence.v1", "status": "fenced",
    "outage_epoch": cfg["outage_epoch"], "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"], "source_image_id": cfg["expected_source_image_id"],
    "workspace": cfg["workspace"], "prior_restart_policy": prior_policy,
    "applied_restart_policy": {"Name": "no", "MaximumRetryCount": 0},
    "rollback_required": prior_policy != {"Name": "no", "MaximumRetryCount": 0},
}
if os.path.exists(fence_path):
    if read_exact(fence_path) != fence_receipt:
        raise RuntimeError("source_fence_receipt_mismatch")
else:
    write_once(fence_path, fence_receipt)

probe = call([
    "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
    "--memory", "512m", "--memory-swap", "512m",
    "--mount", "type=bind,src=" + cfg["workspace"] + ",dst=/workspace,readonly",
    "--entrypoint", "/bin/bash", cfg["expected_source_image_id"], "-lc", listener_preflight,
], check=False)
if probe.returncode != 0 or "--listener-only" not in ((probe.stdout or "") + "\n" + (probe.stderr or "")):
    exact_source(require_fenced=True)
    if prior_policy != {"Name": "no", "MaximumRetryCount": 0}:
        rollback_arg = prior_policy["Name"]
        if rollback_arg == "on-failure" and prior_policy["MaximumRetryCount"]:
            rollback_arg += ":" + str(prior_policy["MaximumRetryCount"])
        call(["docker", "update", "--restart", rollback_arg, cfg["expected_source_container_id"]])
        _, restored_policy = exact_source(require_fenced=False)
        if restored_policy != prior_policy:
            raise RuntimeError("source_fence_probe_rollback_failed")
    rollback_path = prefix + ".fence.rollback.json"
    rollback_receipt = {
        "schema": "arnold.cloud.resident_only_source_fence_rollback.v1",
        "status": "restored" if prior_policy != {"Name": "no", "MaximumRetryCount": 0} else "not_required",
        "reason": "listener_preflight_failed",
        "outage_epoch": cfg["outage_epoch"],
        "source_container_id": cfg["expected_source_container_id"],
        "restored_restart_policy": prior_policy,
    }
    if os.path.exists(rollback_path):
        if read_exact(rollback_path) != rollback_receipt:
            raise RuntimeError("source_fence_probe_rollback_receipt_mismatch")
    else:
        write_once(rollback_path, rollback_receipt)
    raise RuntimeError("resident_listener_only_runtime_unavailable")
exact_source(require_fenced=True)

intent_core = {
    "schema": "arnold.cloud.resident_only_intent.v1", "outage_epoch": cfg["outage_epoch"],
    "source_container": cfg["source_container"], "source_container_id": cfg["expected_source_container_id"],
    "source_image_id": cfg["expected_source_image_id"], "workspace": cfg["workspace"],
    "resident_container": cfg["resident_container"], "resident_command_sha256": cfg["resident_command_sha256"],
    "source_fence_sha256": hashlib.sha256(json.dumps(fence_receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
}
new_attempt = not os.path.exists(intent_path)
if new_attempt:
    if inspect(cfg["resident_container"]) is not None:
        raise RuntimeError("resident_singleton_collision")
    write_once(intent_path, intent_core)
else:
    if read_exact(intent_path) != intent_core:
        raise RuntimeError("outage_epoch_intent_mismatch")

resident = inspect(cfg["resident_container"])
if new_attempt:
    if resident is not None:
        raise RuntimeError("resident_singleton_collision")
    exact_source(require_fenced=True)
    call([
        "docker", "run", "--detach", "--name", cfg["resident_container"],
        "--restart", "no", "--init", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "256",
        "--memory", "2g", "--memory-swap", "2g",
        "--mount", "type=bind,src=" + cfg["workspace"] + ",dst=/workspace",
        "--entrypoint", "/bin/bash", cfg["expected_source_image_id"], "-lc", command,
    ])
    resident = inspect(cfg["resident_container"])
if resident is None:
    raise RuntimeError("resident_attempt_exists_without_container")
identity = resident_identity(resident)
by_id = inspect(identity["container_id"])
if by_id is None or by_id.get("Id") != resident.get("Id"):
    raise RuntimeError("resident_name_identity_mismatch")

start_receipt = {
    "schema": "arnold.cloud.resident_only_start.v1", "status": "started",
    "outage_epoch": cfg["outage_epoch"], "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"], "source_image_id": cfg["expected_source_image_id"],
    "workspace": cfg["workspace"], "resident_container": cfg["resident_container"],
    "resident_container_id": identity["container_id"], "resident_command_sha256": cfg["resident_command_sha256"],
    "restart_policy": "no", "listener_only": True, "started_at": identity["started_at"],
}
if os.path.exists(start_path):
    if read_exact(start_path) != start_receipt:
        raise RuntimeError("start_receipt_mismatch")
else:
    write_once(start_path, start_receipt)

# A prior health receipt is historical evidence only. Re-inspect the exact ID
# and re-prove readiness from logs emitted since this process start every time.
if os.path.exists(health_path):
    historical_health = read_exact(health_path)
    if historical_health.get("schema") != "arnold.cloud.resident_only_health.v1" or historical_health.get("resident_container_id") != identity["container_id"]:
        raise RuntimeError("historical_health_receipt_mismatch")
ready, reason = False, "readiness_timeout"
deadline = time.monotonic() + cfg["health_timeout_seconds"] if new_attempt else time.monotonic()
while True:
    current = inspect(identity["container_id"])
    named = inspect(cfg["resident_container"])
    if current is None or named is None or current.get("Id") != named.get("Id"):
        reason = "resident_container_missing_or_rebound"
        break
    current_identity = resident_identity(current)
    logs = call(["docker", "logs", "--since", start_receipt["started_at"], "--tail", "200", identity["container_id"]], check=False)
    combined = (logs.stdout or "") + "\n" + (logs.stderr or "")
    if current_identity["running"] and "Resident Discord service ready user_id=" in combined and "listener_only=True" in combined:
        ready, reason = True, "discord_ready"
        break
    if not current_identity["running"]:
        reason = "resident_not_running"
        break
    if time.monotonic() >= deadline:
        break
    time.sleep(1)
if not ready:
    current = inspect(identity["container_id"])
    named = inspect(cfg["resident_container"])
    if current is not None:
        current_identity = resident_identity(current)
        if named is None or named.get("Id") != identity["container_id"]:
            raise RuntimeError("resident_health_stop_name_rebound")
        if current_identity["running"]:
            call(["docker", "stop", "--time", "15", identity["container_id"]])
        stopped = inspect(identity["container_id"])
        named = inspect(cfg["resident_container"])
        if stopped is None or named is None or stopped.get("Id") != named.get("Id") or resident_identity(stopped)["running"]:
            raise RuntimeError("resident_health_stop_failed")
health_receipt = {
    "schema": "arnold.cloud.resident_only_health.v1", "status": "healthy" if ready else "failed",
    "reason": reason, "outage_epoch": cfg["outage_epoch"], "resident_container": cfg["resident_container"],
    "resident_container_id": identity["container_id"], "listener_only": True,
    "resident_running": ready, "evidence_since": start_receipt["started_at"],
}
if not os.path.exists(health_path):
    write_once(health_path, health_receipt)

print(json.dumps({
    "schema": "arnold.cloud.resident_only_recovery.v1", "status": health_receipt["status"],
    "outage_epoch": cfg["outage_epoch"], "new_attempt": new_attempt,
    "source_fence_receipt": fence_receipt, "start_receipt": start_receipt,
    "health_receipt": health_receipt,
    "receipt_paths": {"fence_intent": fence_intent_path, "fence": fence_path, "intent": intent_path, "start": start_path, "health": health_path},
}, sort_keys=True, separators=(",", ":")))
'''.strip()


_DOWN_SCRIPT = r'''
import base64, json, os, stat, subprocess, sys

cfg = json.loads(base64.b64decode(sys.argv[1], validate=True))

def call(argv, *, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError("fixed_docker_operation_failed:" + argv[1])
    return result

def inspect(name):
    result = call(["docker", "inspect", "--type=container", name], check=False)
    if result.returncode != 0:
        diagnostic = (result.stderr or "").strip()
        if result.returncode == 1 and ("No such container" in diagnostic or "No such object" in diagnostic):
            return None
        raise RuntimeError("container_inspect_failed")
    value = json.loads(result.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise RuntimeError("container_inspect_invalid")
    return value[0]

def workspace_mount(item):
    mounts = item.get("Mounts")
    rows = [row for row in mounts if isinstance(row, dict) and row.get("Destination") == "/workspace"] if isinstance(mounts, list) else []
    if len(rows) != 1:
        raise RuntimeError("workspace_bind_missing_or_ambiguous")
    row = rows[0]
    return {"type": row.get("Type"), "source": row.get("Source"), "destination": "/workspace", "rw": row.get("RW")}

root = os.path.join(cfg["workspace"], ".megaplan", "resident-only-recovery")
root_stat = os.lstat(root)
if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
    raise RuntimeError("receipt_root_invalid")
prefix = os.path.join(root, cfg["outage_epoch"])
fence_path = prefix + ".fence.json"
start_path, down_intent_path, down_path = prefix + ".start.json", prefix + ".down.intent.json", prefix + ".down.json"
def read_exact(path):
    item_stat = os.lstat(path)
    if not stat.S_ISREG(item_stat.st_mode) or stat.S_ISLNK(item_stat.st_mode):
        raise RuntimeError("receipt_file_invalid")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
start = read_exact(start_path)
fence = read_exact(fence_path)
if (
    fence.get("schema") != "arnold.cloud.resident_only_source_fence.v1"
    or fence.get("status") != "fenced"
    or fence.get("source_container_id") != cfg["expected_source_container_id"]
    or fence.get("source_image_id") != cfg["expected_source_image_id"]
    or fence.get("workspace") != cfg["workspace"]
    or fence.get("applied_restart_policy") != {"Name": "no", "MaximumRetryCount": 0}
):
    raise RuntimeError("source_fence_receipt_invalid")
if not isinstance(start.get("started_at"), str) or not start.get("started_at"):
    raise RuntimeError("start_receipt_started_at_invalid")
expected_start = {
    "schema": "arnold.cloud.resident_only_start.v1", "status": "started",
    "outage_epoch": cfg["outage_epoch"], "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"], "source_image_id": cfg["expected_source_image_id"],
    "workspace": cfg["workspace"], "resident_container": cfg["resident_container"],
    "resident_container_id": cfg["expected_resident_container_id"], "resident_command_sha256": cfg["resident_command_sha256"],
    "restart_policy": "no", "listener_only": True, "started_at": start.get("started_at"),
}
if start != expected_start:
    raise RuntimeError("start_receipt_compare_and_swap_failed")

def write_once(path, payload):
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data); os.fsync(fd)
    finally:
        os.close(fd)
    parent_fd = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)

intent = {"schema": "arnold.cloud.resident_only_down_intent.v1", "outage_epoch": cfg["outage_epoch"], "resident_container": cfg["resident_container"], "resident_container_id": cfg["expected_resident_container_id"]}
if os.path.exists(down_intent_path):
    if read_exact(down_intent_path) != intent:
        raise RuntimeError("down_intent_mismatch")
else:
    write_once(down_intent_path, intent)

resident_by_id = inspect(cfg["expected_resident_container_id"])
resident_by_name = inspect(cfg["resident_container"])
if resident_by_id is not None:
    if resident_by_name is None or resident_by_name.get("Id") != resident_by_id.get("Id") or resident_by_id.get("Image") != cfg["expected_source_image_id"] or workspace_mount(resident_by_id) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}:
        raise RuntimeError("resident_down_compare_and_swap_failed")
    resident_state = resident_by_id.get("State")
    if isinstance(resident_state, dict) and resident_state.get("Running") is True:
        call(["docker", "stop", "--time", "15", cfg["expected_resident_container_id"]])
    resident_by_id = inspect(cfg["expected_resident_container_id"])
    if resident_by_id is None or resident_by_id.get("Id") != cfg["expected_resident_container_id"]:
        raise RuntimeError("resident_down_stop_reconciliation_failed")
    call(["docker", "rm", cfg["expected_resident_container_id"]])
elif resident_by_name is not None:
    raise RuntimeError("resident_name_rebound")
if inspect(cfg["expected_resident_container_id"]) is not None or inspect(cfg["resident_container"]) is not None:
    raise RuntimeError("resident_down_remove_failed")

# Restore only the exact predecessor ID to its fenced prior policy.
source = inspect(cfg["expected_source_container_id"])
source_by_name = inspect(cfg["source_container"])
if source is None or source_by_name is None or source.get("Id") != source_by_name.get("Id") or source.get("Image") != cfg["expected_source_image_id"] or workspace_mount(source) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}:
    raise RuntimeError("source_fence_rollback_compare_and_swap_failed")
prior = fence.get("prior_restart_policy")
if not isinstance(prior, dict) or set(prior) != {"Name", "MaximumRetryCount"}:
    raise RuntimeError("source_fence_receipt_invalid")
host = source.get("HostConfig")
current = host.get("RestartPolicy") if isinstance(host, dict) else None
if current not in ({"Name": "no", "MaximumRetryCount": 0}, prior):
    raise RuntimeError("source_restart_policy_changed_before_rollback")
if current != prior:
    policy_arg = prior["Name"]
    if policy_arg == "on-failure" and prior["MaximumRetryCount"]:
        policy_arg += ":" + str(prior["MaximumRetryCount"])
    call(["docker", "update", "--restart", policy_arg, cfg["expected_source_container_id"]])
source = inspect(cfg["expected_source_container_id"])
host = source.get("HostConfig") if isinstance(source, dict) else None
if not isinstance(host, dict) or host.get("RestartPolicy") != prior:
    raise RuntimeError("source_fence_rollback_failed")
rollback = {"status": "restored", "prior_restart_policy": prior, "current_restart_policy": prior, "source_container_id": cfg["expected_source_container_id"]}

receipt = {"schema": "arnold.cloud.resident_only_down.v1", "status": "down", "outage_epoch": cfg["outage_epoch"], "resident_container": cfg["resident_container"], "resident_container_id": cfg["expected_resident_container_id"], "removed": True, "source_fence_rollback": rollback}
if os.path.exists(down_path):
    if read_exact(down_path) != receipt:
        raise RuntimeError("down_receipt_mismatch")
else:
    write_once(down_path, receipt)
print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
'''.strip()


def resident_recover_command(
    *,
    source_container: str,
    expected_source_container_id: str,
    expected_source_image_id: str,
    workspace: str,
    outage_epoch: str,
    min_free_bytes: int,
    min_free_inodes: int,
    receipt_reserve_bytes: int,
    health_timeout_seconds: int,
) -> tuple[str, str]:
    source = validate_container_name(source_container)
    if type(health_timeout_seconds) is not int or not 5 <= health_timeout_seconds <= 120:
        raise CliError("resident_recovery_invalid", "health timeout must be an integer from 5 to 120 seconds")
    for label, value in {
        "min_free_bytes": min_free_bytes,
        "min_free_inodes": min_free_inodes,
        "receipt_reserve_bytes": receipt_reserve_bytes,
    }.items():
        if type(value) is not int or value < 0:
            raise CliError("resident_recovery_invalid", f"{label} must be a non-negative integer")
    payload = {
        "source_container": source,
        "expected_source_container_id": validate_container_id(expected_source_container_id, label="expected source container ID"),
        "expected_source_image_id": validate_image_id(expected_source_image_id),
        "workspace": validate_workspace_dir(workspace),
        "outage_epoch": validate_outage_epoch(outage_epoch),
        "resident_container": resident_only_container_name(source),
        "resident_command": RESIDENT_ONLY_COMMAND,
        "resident_command_sha256": hashlib.sha256(RESIDENT_ONLY_COMMAND.encode()).hexdigest(),
        "listener_preflight_command": _LISTENER_PREFLIGHT_COMMAND,
        "listener_preflight_command_sha256": hashlib.sha256(_LISTENER_PREFLIGHT_COMMAND.encode()).hexdigest(),
        "min_free_bytes": min_free_bytes,
        "min_free_inodes": min_free_inodes,
        "receipt_reserve_bytes": receipt_reserve_bytes,
        "health_timeout_seconds": health_timeout_seconds,
    }
    return shlex.join(["python3", "-", _encoded_config(payload)]), _RECOVER_SCRIPT


def resident_down_command(
    *,
    source_container: str,
    expected_source_container_id: str,
    expected_source_image_id: str,
    expected_resident_container_id: str,
    workspace: str,
    outage_epoch: str,
) -> tuple[str, str]:
    source = validate_container_name(source_container)
    payload = {
        "source_container": source,
        "expected_source_container_id": validate_container_id(expected_source_container_id, label="expected source container ID"),
        "expected_source_image_id": validate_image_id(expected_source_image_id),
        "expected_resident_container_id": validate_container_id(expected_resident_container_id, label="expected resident container ID"),
        "workspace": validate_workspace_dir(workspace),
        "outage_epoch": validate_outage_epoch(outage_epoch),
        "resident_container": resident_only_container_name(source),
        "resident_command_sha256": hashlib.sha256(RESIDENT_ONLY_COMMAND.encode()).hexdigest(),
    }
    return shlex.join(["python3", "-", _encoded_config(payload)]), _DOWN_SCRIPT


def parse_resident_recovery_receipt(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CliError("resident_recovery_unknown", "resident recovery returned invalid JSON") from exc
    start = value.get("start_receipt") if isinstance(value, Mapping) else None
    health = value.get("health_receipt") if isinstance(value, Mapping) else None
    fence = value.get("source_fence_receipt") if isinstance(value, Mapping) else None
    paths = value.get("receipt_paths") if isinstance(value, Mapping) else None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "status",
            "outage_epoch",
            "new_attempt",
            "source_fence_receipt",
            "start_receipt",
            "health_receipt",
            "receipt_paths",
        }
        or value.get("schema") != RECOVER_SCHEMA
        or value.get("status") not in {"healthy", "failed"}
        or not isinstance(value.get("outage_epoch"), str)
        or not isinstance(value.get("new_attempt"), bool)
        or not isinstance(fence, dict)
        or set(fence)
        != {
            "schema",
            "status",
            "outage_epoch",
            "source_container",
            "source_container_id",
            "source_image_id",
            "workspace",
            "prior_restart_policy",
            "applied_restart_policy",
            "rollback_required",
        }
        or fence.get("schema") != FENCE_SCHEMA
        or fence.get("status") != "fenced"
        or fence.get("applied_restart_policy")
        != {"Name": "no", "MaximumRetryCount": 0}
        or not isinstance(fence.get("prior_restart_policy"), dict)
        or type(fence.get("rollback_required")) is not bool
        or not isinstance(start, dict)
        or set(start)
        != {
            "schema",
            "status",
            "outage_epoch",
            "source_container",
            "source_container_id",
            "source_image_id",
            "workspace",
            "resident_container",
            "resident_container_id",
            "resident_command_sha256",
            "restart_policy",
            "listener_only",
            "started_at",
        }
        or start.get("schema") != START_SCHEMA
        or start.get("status") != "started"
        or not _CONTAINER_ID_RE.fullmatch(str(start.get("source_container_id") or ""))
        or not _IMAGE_ID_RE.fullmatch(str(start.get("source_image_id") or ""))
        or not _CONTAINER_ID_RE.fullmatch(str(start.get("resident_container_id") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("resident_command_sha256") or ""))
        or start.get("listener_only") is not True
        or start.get("restart_policy") != "no"
        or not isinstance(start.get("started_at"), str)
        or not start.get("started_at")
        or not isinstance(health, dict)
        or set(health)
        != {
            "schema",
            "status",
            "reason",
            "outage_epoch",
            "resident_container",
            "resident_container_id",
            "listener_only",
            "resident_running",
            "evidence_since",
        }
        or health.get("schema") != HEALTH_SCHEMA
        or health.get("status") != value.get("status")
        or not isinstance(health.get("reason"), str)
        or health.get("listener_only") is not True
        or health.get("resident_running") is not (value.get("status") == "healthy")
        or health.get("evidence_since") != start.get("started_at")
        or not isinstance(paths, dict)
        or set(paths) != {"fence_intent", "fence", "intent", "start", "health"}
        or any(not isinstance(item, str) or not item for item in paths.values())
    ):
        raise CliError("resident_recovery_unknown", "resident recovery receipt failed strict validation")
    return value


def parse_resident_down_receipt(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CliError("resident_down_unknown", "resident down returned invalid JSON") from exc
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "status",
            "outage_epoch",
            "resident_container",
            "resident_container_id",
            "removed",
            "source_fence_rollback",
        }
        or value.get("schema") != DOWN_SCHEMA
        or value.get("status") != "down"
        or value.get("removed") is not True
        or not isinstance(value.get("source_fence_rollback"), dict)
        or value["source_fence_rollback"].get("status") != "restored"
        or not _CONTAINER_ID_RE.fullmatch(str(value.get("resident_container_id") or ""))
    ):
        raise CliError("resident_down_unknown", "resident down receipt failed strict validation")
    return value


__all__ = [
    "DOWN_SCHEMA",
    "FENCE_SCHEMA",
    "HEALTH_SCHEMA",
    "RECOVER_SCHEMA",
    "RESIDENT_ONLY_COMMAND",
    "START_SCHEMA",
    "parse_resident_down_receipt",
    "parse_resident_recovery_receipt",
    "resident_down_command",
    "resident_only_container_name",
    "resident_recover_command",
]
