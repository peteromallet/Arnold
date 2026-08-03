"""Finite SSH resident-only recovery and exact rollback commands.

The public builders expose only two fixed host transactions.  They do not
accept an arbitrary shell command, expose secret contents, or start any of the
ordinary cloud entrypoint supervisors.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
from pathlib import PurePosixPath
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.providers.ssh_preflight import (
    validate_container_name,
    validate_workspace_dir,
)
from arnold_pipelines.megaplan.resident.listener_recovery import (
    LISTENER_RECOVERY_SEED_SCHEMA,
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
_GIT_ID_RE = re.compile(r"[0-9a-f]{40}\Z")
_CUSTODY_BASE = "/var/lib/arnold/megaplan-resident-recovery"

RESIDENT_ONLY_COMMAND = (
    "-P",
    "-m",
    "arnold_pipelines.megaplan",
    "resident",
    "discord",
    "--listener-only",
    "--recovery-seed",
    "__RECOVERY_SEED_PATH__",
    "--mode",
    "production",
    "--store-root",
    "/workspace/arnold/.megaplan/resident",
)

_LISTENER_CAPTURE_COMMAND = r"""set -euo pipefail
runtime_src=$1
expected_commit=$2
expected_tree=$3
runtime_python=$4
expected_python_sha256=$5
check_help=$6
runtime_src=$(cd "$runtime_src" && pwd -P)
[[ "$(git -C "$runtime_src" rev-parse HEAD)" == "$expected_commit" ]]
[[ "$(git -C "$runtime_src" rev-parse 'HEAD^{tree}')" == "$expected_tree" ]]
git -C "$runtime_src" diff --quiet --
git -C "$runtime_src" diff --cached --quiet --
[[ -z "$(git -C "$runtime_src" status --porcelain=v1 --untracked-files=all --ignored=matching)" ]]
while IFS= read -r -d '' link_path; do
  resolved=$(readlink -f "$link_path")
  [[ "$resolved" == "$runtime_src"/* ]]
done < <(find "$runtime_src" -type l -print0)
runtime_python=$(readlink -f "$runtime_python")
[[ "$(sha256sum "$runtime_python" | awk '{print $1}')" == "$expected_python_sha256" ]]
if [[ "$check_help" == 1 ]]; then
  help=$(cd "$runtime_src" && PYTHONPATH="$runtime_src" "$runtime_python" -P -m arnold_pipelines.megaplan resident discord --help)
  [[ "$help" == *"--listener-only"* && "$help" == *"--recovery-seed"* ]]
fi
workspace_dev=$(stat -c '%d' /workspace)
workspace_ino=$(stat -c '%i' /workspace)
printf '{"runtime_commit":"%s","runtime_path":"%s","runtime_python_path":"%s","runtime_python_sha256":"%s","runtime_tree":"%s","schema":"arnold.cloud.resident_only_runtime_capture.v1","workspace_identity":{"st_dev":%s,"st_ino":%s}}\n' \
  "$expected_commit" "$runtime_src" "$runtime_python" "$expected_python_sha256" "$expected_tree" "$workspace_dev" "$workspace_ino"
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


def validate_image_id(value: str, *, label: str = "expected source image") -> str:
    if not isinstance(value, str) or not _IMAGE_ID_RE.fullmatch(value):
        raise CliError("resident_recovery_invalid", f"{label} must be an exact sha256 image ID")
    return value


def validate_runtime_path(value: str) -> str:
    if not isinstance(value, str):
        raise CliError("resident_recovery_invalid", "expected runtime path must be absolute under /workspace")
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or path == PurePosixPath("/workspace") or PurePosixPath("/workspace") not in path.parents or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value):
        raise CliError("resident_recovery_invalid", "expected runtime path must be a normalized descendant of /workspace")
    return str(path)


def validate_git_id(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _GIT_ID_RE.fullmatch(value):
        raise CliError("resident_recovery_invalid", f"{label} must be an exact 40-character Git object ID")
    return value


def validate_absolute_path(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise CliError("resident_recovery_invalid", f"{label} must be an absolute normalized path")
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value):
        raise CliError("resident_recovery_invalid", f"{label} must be an absolute normalized path")
    return str(path)


def validate_sha256(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CliError("resident_recovery_invalid", f"{label} must be an exact lowercase SHA-256 digest")
    return value


def resident_only_container_name(source_container: str) -> str:
    source = validate_container_name(source_container)
    suffix = "-resident-only"
    if len(source) + len(suffix) <= 128:
        return source + suffix
    digest = hashlib.sha256(source.encode()).hexdigest()[:12]
    return source[: 128 - len(suffix) - len(digest) - 1] + "-" + digest + suffix


def resident_custody_host_root(source_container_id: str) -> str:
    exact_id = validate_container_id(
        source_container_id,
        label="expected source container ID",
    )
    return f"{_CUSTODY_BASE}/{exact_id}"


def _encoded_config(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


_RECOVER_SCRIPT = r'''
import base64, hashlib, json, os, re, secrets, shutil, stat, subprocess, sys, time

cfg = json.loads(base64.b64decode(sys.argv[1], validate=True))
if os.geteuid() != 0:
    raise RuntimeError("resident_recovery_requires_root_custody")
argv_template = cfg["resident_argv_template"]
listener_capture = cfg["listener_capture_command"]
if hashlib.sha256(json.dumps(argv_template, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != cfg["resident_argv_template_sha256"]:
    raise RuntimeError("resident_argv_template_digest_mismatch")
if hashlib.sha256(listener_capture.encode()).hexdigest() != cfg["listener_capture_command_sha256"]:
    raise RuntimeError("listener_capture_command_digest_mismatch")

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

def exact_mount(item, destination):
    mounts = item.get("Mounts")
    rows = [row for row in mounts if isinstance(row, dict) and row.get("Destination") == destination] if isinstance(mounts, list) else []
    if len(rows) != 1:
        raise RuntimeError("required_bind_missing_or_ambiguous")
    row = rows[0]
    return {"type": row.get("Type"), "source": row.get("Source"), "destination": destination, "rw": row.get("RW")}

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

def write_bytes_once(path, data):
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
    if not stat.S_ISREG(item_stat.st_mode) or stat.S_ISLNK(item_stat.st_mode) or item_stat.st_uid != 0 or stat.S_IMODE(item_stat.st_mode) != 0o600:
        raise RuntimeError("receipt_file_invalid")
    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RuntimeError("receipt_duplicate_field")
            value[key] = item
        return value
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicates)

def resident_identity(item):
    state, host, config = item.get("State"), item.get("HostConfig"), item.get("Config")
    configured_env = config.get("Env") if isinstance(config, dict) else None
    env_map = {}
    if isinstance(configured_env, list):
        for row in configured_env:
            if not isinstance(row, str) or "=" not in row:
                raise RuntimeError("resident_container_environment_invalid")
            key, value = row.split("=", 1)
            if key in env_map:
                raise RuntimeError("resident_container_environment_duplicate")
            env_map[key] = value
    expected_cmd = hashlib.sha256(json.dumps(resident_argv, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    actual_cmd = hashlib.sha256(json.dumps(config.get("Cmd") if isinstance(config, dict) else None, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (
        item.get("Image") != cfg["expected_resident_image_id"]
        or item.get("Name") != "/" + cfg["resident_container"]
        or not isinstance(config, dict) or config.get("Entrypoint") != [capture["runtime_python_path"]]
        or config.get("User") != "0:0"
        or config.get("WorkingDir") != cfg["resident_workdir"]
        or not isinstance(configured_env, list)
        or any(value.startswith("MEGAPLAN_RUNTIME_LAUNCH_SEED=") or value.startswith("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION=") for value in configured_env)
        or any(env_map.get(key) != value for key, value in secret_values.items())
        or env_map.get("PYTHONPATH") != capture["runtime_path"]
        or env_map.get("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED") != "0"
        or env_map.get("MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE") != "production"
        or any(key in env_map for key in ("BASH_ENV", "ENV", "SHELLOPTS", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "LD_PRELOAD", "LD_LIBRARY_PATH"))
        or actual_cmd != expected_cmd
        or not isinstance(host, dict)
        or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
        or host.get("CapDrop") != ["ALL"] or host.get("CapAdd") not in (None, [])
        or host.get("SecurityOpt") != ["no-new-privileges:true"]
        or host.get("PidsLimit") != 256 or host.get("Memory") != 2147483648
        or host.get("MemorySwap") != 2147483648
        or workspace_mount(item) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
        or exact_mount(item, cfg["expected_runtime_path"]) != {"type": "bind", "source": runtime_host_path, "destination": cfg["expected_runtime_path"], "rw": False}
        or exact_mount(item, "/run/megaplan-resident-recovery") != {"type": "bind", "source": seed_epoch_path, "destination": "/run/megaplan-resident-recovery", "rw": False}
        or not isinstance(state, dict) or not isinstance(state.get("StartedAt"), str)
    ):
        raise RuntimeError("resident_container_identity_mismatch")
    return {"container_id": item.get("Id"), "running": state.get("Running") is True, "exit_code": state.get("ExitCode"), "started_at": state.get("StartedAt")}

def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("recovery_custody_directory_invalid")

custody_root = cfg["custody_host_root"]
custody_epoch_path = os.path.join(custody_root, cfg["outage_epoch"])
seed_epoch_path = os.path.join(custody_epoch_path, "seed")
for private_path in (cfg["custody_host_parent"], custody_root, custody_epoch_path, seed_epoch_path):
    ensure_private_dir(private_path)
prefix = os.path.join(custody_epoch_path, "transaction")
fence_intent_path, fence_path = prefix + ".fence.intent.json", prefix + ".fence.json"
intent_path, start_path, health_path = prefix + ".intent.json", prefix + ".start.json", prefix + ".health.json"
down_path = prefix + ".down.json"
seed_path = os.path.join(seed_epoch_path, "launch-seed.json")
sanitized_env_path = os.path.join(custody_epoch_path, "resident.env")

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
if not stat.S_ISREG(secret_stat.st_mode) or stat.S_ISLNK(secret_stat.st_mode) or not 0 < secret_stat.st_size <= 65536:
    raise RuntimeError("resident_secret_file_invalid")
allowed_secret_names = {
    "DISCORD_BOT_TOKEN", "DISCORD_DM_USER_ID", "DISCORD_USER_WHITELIST",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "ZHIPU_API_KEY",
    "KIMI_API_KEY", "MOONSHOT_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "HERMES_API_KEY",
    "OPENAI_BASE_URL",
    "MEGAPLAN_RESIDENT_ADMIN_USERS", "MEGAPLAN_RESIDENT_ALLOWED_CHANNELS",
    "MEGAPLAN_RESIDENT_ALLOWED_GUILDS", "MEGAPLAN_RESIDENT_ALLOWED_USERS",
    "MEGAPLAN_RESIDENT_BURST_IDLE_S", "MEGAPLAN_RESIDENT_BURST_MAX_S",
    "MEGAPLAN_RESIDENT_CLOUD_YAML", "MEGAPLAN_RESIDENT_CODEX_REASONING_EFFORT",
    "MEGAPLAN_RESIDENT_CODEX_SANDBOX", "MEGAPLAN_RESIDENT_CONFIRMATION_EXPIRY_S",
    "MEGAPLAN_RESIDENT_DEFAULT_TIMEZONE", "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE",
    "MEGAPLAN_RESIDENT_EXPORT_ROOT", "MEGAPLAN_RESIDENT_GUILD_TIMEZONES",
    "MEGAPLAN_RESIDENT_HISTORY_WINDOW", "MEGAPLAN_RESIDENT_MAX_PROMPT_CHARS",
    "MEGAPLAN_RESIDENT_MAX_TOOL_CALLS", "MEGAPLAN_RESIDENT_MODE",
    "MEGAPLAN_RESIDENT_MODEL", "MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV",
    "MEGAPLAN_RESIDENT_MODEL_BASE_URL", "MEGAPLAN_RESIDENT_MODEL_MAX_TOKENS",
    "MEGAPLAN_RESIDENT_MODEL_PROVIDER", "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_RECOVERY_GRACE_S",
    "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S", "MEGAPLAN_RESIDENT_MODEL_TOOLSETS",
    "MEGAPLAN_RESIDENT_PROFILE", "MEGAPLAN_RESIDENT_REPAIR_DATA_DIR",
    "MEGAPLAN_RESIDENT_REPAIR_LOCK_DIR", "MEGAPLAN_RESIDENT_REQUIRE_CLOUD_CONFIRMATION",
    "MEGAPLAN_RESIDENT_SCHEDULER_BATCH_SIZE", "MEGAPLAN_RESIDENT_SCHEDULER_POLL_S",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_CONVERSATION_KEY",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_ENABLED", "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_INTERVAL_S",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_MAX_TOKENS",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TIMEOUT_S",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TOOLSETS",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBJECT_USER_ID",
    "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_TODO_PATH", "MEGAPLAN_RESIDENT_STALE_CLAIM_TIMEOUT_S",
    "MEGAPLAN_RESIDENT_STALE_CONTROL_CLAIM_TIMEOUT_S", "MEGAPLAN_RESIDENT_STALE_TURN_TIMEOUT_S",
    "MEGAPLAN_RESIDENT_STORE_ROOT",
    "MEGAPLAN_RESIDENT_SUBAGENT_MAX_TOOL_CALLS", "MEGAPLAN_RESIDENT_SUBAGENT_MODEL",
    "MEGAPLAN_RESIDENT_SUBAGENT_MODELS", "MEGAPLAN_RESIDENT_VOICE_DOWNLOAD_TIMEOUT_S",
    "MEGAPLAN_RESIDENT_VOICE_MAX_BYTES", "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_API_KEY_ENV",
    "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_BASE_URL",
    "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_ENABLED", "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_MODEL",
    "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_PROVIDER", "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_TIMEOUT_S",
    "MEGAPLAN_STATUS_SNAPSHOT",
}
try:
    secret_fd = os.open(secret_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened_secret_stat = os.fstat(secret_fd)
        if (opened_secret_stat.st_dev, opened_secret_stat.st_ino, opened_secret_stat.st_size) != (secret_stat.st_dev, secret_stat.st_ino, secret_stat.st_size):
            raise RuntimeError("resident_secret_compare_and_swap_failed")
        secret_bytes = os.read(secret_fd, 65537)
    finally:
        os.close(secret_fd)
    if len(secret_bytes) != secret_stat.st_size:
        raise RuntimeError("resident_secret_compare_and_swap_failed")
    secret_text = secret_bytes.decode("utf-8")
except (OSError, UnicodeDecodeError) as exc:
    raise RuntimeError("resident_secret_file_invalid") from exc
if "\r" in secret_text or "\0" in secret_text or not secret_text.endswith("\n"):
    raise RuntimeError("resident_secret_grammar_invalid")
secret_values = {}
for line in secret_text.splitlines():
    match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([A-Za-z0-9_./:@,+%=?-]+)", line)
    if not match:
        raise RuntimeError("resident_secret_grammar_invalid")
    key, value = match.groups()
    if key not in allowed_secret_names or key in secret_values or key.startswith(("BASH", "PYTHON", "LD_")):
        raise RuntimeError("resident_secret_name_invalid")
    secret_values[key] = value
if not secret_values.get("DISCORD_BOT_TOKEN"):
    raise RuntimeError("resident_discord_token_missing")
# This launch-owned value is emitted once through the explicit docker --env
# argument below.  Keeping the inherited copy in --env-file produces duplicate
# Config.Env keys, making immutable post-create identity ambiguous.
inherited_bot_role = secret_values.pop("MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE", None)
if inherited_bot_role not in (None, "production"):
    raise RuntimeError("resident_discord_bot_role_invalid")
sanitized_env_bytes = "".join(f"{key}={secret_values[key]}\n" for key in sorted(secret_values)).encode()
sanitized_env_sha256 = hashlib.sha256(sanitized_env_bytes).hexdigest()
if os.path.exists(sanitized_env_path):
    sanitized_env_stat = os.lstat(sanitized_env_path)
    if not stat.S_ISREG(sanitized_env_stat.st_mode) or stat.S_ISLNK(sanitized_env_stat.st_mode) or sanitized_env_stat.st_uid != 0 or stat.S_IMODE(sanitized_env_stat.st_mode) != 0o600:
        raise RuntimeError("resident_sanitized_env_custody_invalid")
    existing_env = open(sanitized_env_path, "rb").read()
    if existing_env != sanitized_env_bytes:
        raise RuntimeError("resident_sanitized_env_compare_and_swap_failed")
else:
    write_bytes_once(sanitized_env_path, sanitized_env_bytes)

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
fence_intent_sha256 = hashlib.sha256(json.dumps(fence_intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
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
    "fence_intent_sha256": fence_intent_sha256,
    "applied_restart_policy": {"Name": "no", "MaximumRetryCount": 0},
    "rollback_required": prior_policy != {"Name": "no", "MaximumRetryCount": 0},
}
if os.path.exists(fence_path):
    if read_exact(fence_path) != fence_receipt:
        raise RuntimeError("source_fence_receipt_mismatch")
else:
    write_once(fence_path, fence_receipt)

def rollback_probe_failure(reason):
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
        "reason": reason,
        "outage_epoch": cfg["outage_epoch"],
        "source_container_id": cfg["expected_source_container_id"],
        "restored_restart_policy": prior_policy,
    }
    if os.path.exists(rollback_path):
        if read_exact(rollback_path) != rollback_receipt:
            raise RuntimeError("source_fence_probe_rollback_receipt_mismatch")
    else:
        write_once(rollback_path, rollback_receipt)
    raise RuntimeError("resident_listener_only_runtime_unavailable:" + reason)

def capture_runtime(*, check_help, runtime_source=None):
    mounts = [
        "--mount", "type=bind,src=" + cfg["workspace"] + ",dst=/workspace,readonly",
    ]
    if runtime_source is not None:
        mounts.extend([
            "--mount", "type=bind,src=" + runtime_source + ",dst=" + cfg["expected_runtime_path"] + ",readonly",
        ])
    probe = call([
        "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
        "--memory", "512m", "--memory-swap", "512m",
        *mounts,
        "--entrypoint", "/bin/bash", cfg["expected_resident_image_id"], "-lc", listener_capture,
        "resident-runtime-capture", cfg["expected_runtime_path"], cfg["expected_runtime_commit"], cfg["expected_runtime_tree"],
        cfg["expected_runtime_python_path"], cfg["expected_runtime_python_sha256"], "1" if check_help else "0",
    ], check=False)
    if probe.returncode != 0:
        return None
    try:
        value = json.loads(probe.stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "runtime_path", "runtime_commit", "runtime_tree", "runtime_python_path", "runtime_python_sha256", "workspace_identity"}
        or value.get("schema") != "arnold.cloud.resident_only_runtime_capture.v1"
        or value.get("runtime_path") != cfg["expected_runtime_path"]
        or value.get("runtime_commit") != cfg["expected_runtime_commit"]
        or value.get("runtime_tree") != cfg["expected_runtime_tree"]
        or not isinstance(value.get("runtime_python_path"), str)
        or not value["runtime_python_path"].startswith("/")
        or not isinstance(value.get("runtime_python_sha256"), str)
        or len(value["runtime_python_sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in value["runtime_python_sha256"])
        or not isinstance(value.get("workspace_identity"), dict)
        or set(value["workspace_identity"]) != {"st_dev", "st_ino"}
        or any(type(value["workspace_identity"].get(key)) is not int or value["workspace_identity"][key] < 0 for key in ("st_dev", "st_ino"))
    ):
        return None
    return value

capture = capture_runtime(check_help=True)
if capture is None:
    rollback_probe_failure("listener_runtime_capture_failed")
exact_source(require_fenced=True)
# The selector files are mutable workspace state.  Capture again immediately
# before create and admit only byte-for-byte identical effective runtime state.
capture_recheck = capture_runtime(check_help=False)
if capture_recheck != capture:
    rollback_probe_failure("listener_runtime_selector_race")
exact_source(require_fenced=True)

runtime_suffix = capture["runtime_path"][len("/workspace"):].lstrip("/")
workspace_runtime_host_path = os.path.join(cfg["workspace"], runtime_suffix)
runtime_host_stat = os.lstat(workspace_runtime_host_path)
if (
    not stat.S_ISDIR(runtime_host_stat.st_mode)
    or stat.S_ISLNK(runtime_host_stat.st_mode)
    or os.path.realpath(workspace_runtime_host_path) != workspace_runtime_host_path
):
    rollback_probe_failure("listener_runtime_host_path_invalid")

# A read-only bind does not make a mutable shared-workspace source immutable:
# another host process or container can still change the bind source after our
# capture.  Copy the exact accepted runtime into this outage epoch's private,
# root-custodied directory, harden it, and re-run the same commit/tree/clean
# validation through the pinned image.  The resident mounts only this snapshot.
runtime_host_path = os.path.join(custody_epoch_path, "runtime")

def harden_runtime_snapshot(path):
    custody_uid = os.geteuid()
    custody_gid = os.getegid()
    for current, directories, files in os.walk(path, topdown=False, followlinks=False):
        for name in files + directories:
            item_path = os.path.join(current, name)
            info = os.lstat(item_path)
            if stat.S_ISLNK(info.st_mode):
                os.lchown(item_path, custody_uid, custody_gid)
                continue
            os.chown(item_path, custody_uid, custody_gid)
            os.chmod(item_path, stat.S_IMODE(info.st_mode) & ~0o022)
        current_info = os.lstat(current)
        os.chown(current, custody_uid, custody_gid)
        os.chmod(current, stat.S_IMODE(current_info.st_mode) & ~0o022)

if not os.path.exists(runtime_host_path):
    snapshot_staging = os.path.join(
        custody_epoch_path,
        ".runtime-staging-" + secrets.token_hex(16),
    )
    try:
        shutil.copytree(
            workspace_runtime_host_path,
            snapshot_staging,
            symlinks=True,
        )
        harden_runtime_snapshot(snapshot_staging)
        os.rename(snapshot_staging, runtime_host_path)
    finally:
        if os.path.lexists(snapshot_staging):
            shutil.rmtree(snapshot_staging)
snapshot_stat = os.lstat(runtime_host_path)
if (
    not stat.S_ISDIR(snapshot_stat.st_mode)
    or stat.S_ISLNK(snapshot_stat.st_mode)
    or snapshot_stat.st_uid != os.geteuid()
    or stat.S_IMODE(snapshot_stat.st_mode) & 0o022
    or os.path.realpath(runtime_host_path) != runtime_host_path
    or not os.path.commonpath([runtime_host_path, custody_epoch_path]) == custody_epoch_path
):
    rollback_probe_failure("listener_runtime_snapshot_custody_invalid")
snapshot_capture = capture_runtime(
    check_help=True,
    runtime_source=runtime_host_path,
)
if snapshot_capture != capture:
    rollback_probe_failure("listener_runtime_snapshot_verification_failed")

inside_seed_path = "/run/megaplan-resident-recovery/launch-seed.json"
resident_argv = [inside_seed_path if value == "__RECOVERY_SEED_PATH__" else value for value in argv_template]
if any(value.startswith("__") and value.endswith("__") for value in resident_argv):
    raise RuntimeError("resident_argv_render_failed")
command_sha256 = hashlib.sha256(json.dumps(resident_argv, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

intent_core = {
    "schema": "arnold.cloud.resident_only_intent.v1", "outage_epoch": cfg["outage_epoch"],
    "source_container": cfg["source_container"], "source_container_id": cfg["expected_source_container_id"],
    "source_image_id": cfg["expected_source_image_id"],
    "resident_image_id": cfg["expected_resident_image_id"], "workspace": cfg["workspace"],
    "resident_container": cfg["resident_container"], "resident_command_sha256": command_sha256,
    "resident_env_sha256": sanitized_env_sha256,
    "runtime_capture": capture,
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
intent_sha256 = hashlib.sha256(json.dumps(intent_core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

resident = inspect(cfg["resident_container"])
if resident is None:
    exact_source(require_fenced=True)
    created = call([
        "docker", "create", "--name", cfg["resident_container"], "--user", "0:0",
        "--restart", "no", "--init", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "256",
        "--memory", "2g", "--memory-swap", "2g",
        # Megaplan initializes state relative to cwd.  Keep the exact code
        # snapshot read-only and run from the resident's writable project root.
        "--workdir", cfg["resident_workdir"],
        "--env-file", sanitized_env_path,
        "--env", "PYTHONPATH=" + capture["runtime_path"],
        "--env", "MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED=0",
        "--env", "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE=production",
        "--mount", "type=bind,src=" + cfg["workspace"] + ",dst=/workspace",
        "--mount", "type=bind,src=" + runtime_host_path + ",dst=" + cfg["expected_runtime_path"] + ",readonly",
        "--mount", "type=bind,src=" + seed_epoch_path + ",dst=/run/megaplan-resident-recovery,readonly",
        "--entrypoint", capture["runtime_python_path"], cfg["expected_resident_image_id"], *resident_argv,
    ])
    created_id = (created.stdout or "").strip()
    if len(created_id) != 64 or any(ch not in "0123456789abcdef" for ch in created_id):
        raise RuntimeError("resident_create_id_invalid")
    resident = inspect(cfg["resident_container"])
if resident is None:
    raise RuntimeError("resident_attempt_exists_without_container")
identity = resident_identity(resident)
by_id = inspect(identity["container_id"])
if by_id is None or by_id.get("Id") != resident.get("Id"):
    raise RuntimeError("resident_name_identity_mismatch")
post_create_capture = capture_runtime(
    check_help=False,
    runtime_source=runtime_host_path,
)
if post_create_capture != capture:
    raise RuntimeError("listener_runtime_snapshot_changed_after_create")
exact_source(require_fenced=True)

seed_core = {
    "schema": cfg["listener_recovery_seed_schema"],
    "outage_epoch": cfg["outage_epoch"],
    "source_container_id": cfg["expected_source_container_id"],
    "source_image_id": cfg["expected_source_image_id"],
    "resident_image_id": cfg["expected_resident_image_id"],
    "workspace_host_path": cfg["workspace"],
    "workspace_identity": capture["workspace_identity"],
    "runtime_path": capture["runtime_path"],
    "runtime_commit": capture["runtime_commit"],
    "runtime_tree": capture["runtime_tree"],
    "runtime_python_path": capture["runtime_python_path"],
    "runtime_python_sha256": capture["runtime_python_sha256"],
    "command_sha256": command_sha256,
    "resident_env_sha256": sanitized_env_sha256,
    "container_id": identity["container_id"],
}
if os.path.exists(seed_path):
    seed_stat = os.lstat(seed_path)
    if seed_stat.st_uid != 0 or stat.S_IMODE(seed_stat.st_mode) != 0o600:
        raise RuntimeError("recovery_seed_custody_invalid")
    seed = read_exact(seed_path)
    if set(seed) != set(seed_core) | {"nonce"} or any(seed.get(key) != value for key, value in seed_core.items()) or not isinstance(seed.get("nonce"), str) or len(seed["nonce"]) != 64:
        raise RuntimeError("recovery_seed_compare_and_swap_failed")
else:
    seed = {**seed_core, "nonce": secrets.token_hex(32)}
    write_once(seed_path, seed)
seed_sha256 = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

# Creating the container is the single durable attempt.  A retry may finish
# the same not-yet-started ID after an interruption, but never mint a second ID.
started_now = False
if not os.path.exists(start_path):
    if not identity["running"]:
        if identity["started_at"] not in ("", "0001-01-01T00:00:00Z", "0001-01-01T00:00:00.000000000Z"):
            raise RuntimeError("resident_attempt_already_executed_without_receipt")
        final_capture = capture_runtime(
            check_help=False,
            runtime_source=runtime_host_path,
        )
        if final_capture != capture:
            raise RuntimeError("listener_runtime_snapshot_changed_before_start")
        if read_exact(seed_path) != seed:
            raise RuntimeError("recovery_seed_changed_before_start")
        exact_source(require_fenced=True)
        call(["docker", "start", identity["container_id"]])
        resident = inspect(identity["container_id"])
        if resident is None:
            raise RuntimeError("resident_start_missing")
        identity = resident_identity(resident)
        if not identity["running"]:
            raise RuntimeError("resident_start_failed")
    started_now = True

start_receipt = {
    "schema": "arnold.cloud.resident_only_start.v1", "status": "started",
    "outage_epoch": cfg["outage_epoch"], "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"], "source_image_id": cfg["expected_source_image_id"],
    "resident_image_id": cfg["expected_resident_image_id"],
    "workspace": cfg["workspace"], "resident_container": cfg["resident_container"],
    "resident_container_id": identity["container_id"], "resident_command_sha256": command_sha256,
    "resident_env_sha256": sanitized_env_sha256,
    "intent_sha256": intent_sha256,
    "recovery_seed_sha256": seed_sha256,
    "runtime_path": capture["runtime_path"], "runtime_commit": capture["runtime_commit"],
    "runtime_tree": capture["runtime_tree"], "runtime_python_path": capture["runtime_python_path"],
    "runtime_python_sha256": capture["runtime_python_sha256"],
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
deadline = time.monotonic() + cfg["health_timeout_seconds"] if started_now else time.monotonic()
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
    "receipt_paths": {"fence_intent": fence_intent_path, "fence": fence_path, "intent": intent_path, "seed": seed_path, "start": start_path, "health": health_path},
}, sort_keys=True, separators=(",", ":")))
'''.strip()


_DOWN_SCRIPT = r'''
import base64, hashlib, json, os, stat, subprocess, sys

cfg = json.loads(base64.b64decode(sys.argv[1], validate=True))
if os.geteuid() != 0:
    raise RuntimeError("resident_down_requires_root_custody")

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

root = cfg["custody_host_root"]
epoch_root = os.path.join(root, cfg["outage_epoch"])
for custody_dir in (root, epoch_root):
    root_stat = os.lstat(custody_dir)
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode) or root_stat.st_uid != 0 or stat.S_IMODE(root_stat.st_mode) != 0o700:
        raise RuntimeError("receipt_root_invalid")
prefix = os.path.join(epoch_root, "transaction")
fence_intent_path = prefix + ".fence.intent.json"
fence_path = prefix + ".fence.json"
attempt_intent_path = prefix + ".intent.json"
start_path, down_intent_path, down_path = prefix + ".start.json", prefix + ".down.intent.json", prefix + ".down.json"
def read_exact(path):
    item_stat = os.lstat(path)
    if not stat.S_ISREG(item_stat.st_mode) or stat.S_ISLNK(item_stat.st_mode) or item_stat.st_uid != 0 or stat.S_IMODE(item_stat.st_mode) != 0o600:
        raise RuntimeError("receipt_file_invalid")
    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RuntimeError("receipt_duplicate_field")
            value[key] = item
        return value
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicates)
fence_intent = read_exact(fence_intent_path)
fence = read_exact(fence_path)
attempt = read_exact(attempt_intent_path)
fence_intent_sha256 = hashlib.sha256(json.dumps(fence_intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
fence_sha256 = hashlib.sha256(json.dumps(fence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
attempt_sha256 = hashlib.sha256(json.dumps(attempt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if (
    set(fence_intent) != {"schema", "outage_epoch", "source_container", "source_container_id", "source_image_id", "workspace", "prior_restart_policy"}
    or fence_intent.get("schema") != "arnold.cloud.resident_only_source_fence_intent.v1"
    or fence_intent.get("outage_epoch") != cfg["outage_epoch"]
    or fence_intent.get("source_container") != cfg["source_container"]
    or fence_intent.get("source_container_id") != cfg["expected_source_container_id"]
    or fence_intent.get("source_image_id") != cfg["expected_source_image_id"]
    or fence_intent.get("workspace") != cfg["workspace"]
    or not isinstance(fence_intent.get("prior_restart_policy"), dict)
    or set(fence_intent["prior_restart_policy"]) != {"Name", "MaximumRetryCount"}
    or fence_intent["prior_restart_policy"].get("Name") not in {"no", "always", "unless-stopped", "on-failure"}
    or type(fence_intent["prior_restart_policy"].get("MaximumRetryCount")) is not int
    or fence_intent["prior_restart_policy"]["MaximumRetryCount"] < 0
    or (fence_intent["prior_restart_policy"]["Name"] != "on-failure" and fence_intent["prior_restart_policy"]["MaximumRetryCount"] != 0)
):
    raise RuntimeError("source_fence_intent_invalid")
if (
    set(fence) != {"schema", "status", "outage_epoch", "source_container", "source_container_id", "source_image_id", "workspace", "prior_restart_policy", "fence_intent_sha256", "applied_restart_policy", "rollback_required"}
    or fence.get("schema") != "arnold.cloud.resident_only_source_fence.v1"
    or fence.get("status") != "fenced"
    or fence.get("source_container_id") != cfg["expected_source_container_id"]
    or fence.get("source_image_id") != cfg["expected_source_image_id"]
    or fence.get("workspace") != cfg["workspace"]
    or fence.get("prior_restart_policy") != fence_intent["prior_restart_policy"]
    or fence.get("fence_intent_sha256") != fence_intent_sha256
    or fence.get("applied_restart_policy") != {"Name": "no", "MaximumRetryCount": 0}
):
    raise RuntimeError("source_fence_receipt_invalid")
if (
    set(attempt) != {"schema", "outage_epoch", "source_container", "source_container_id", "source_image_id", "resident_image_id", "workspace", "resident_container", "resident_command_sha256", "resident_env_sha256", "runtime_capture", "source_fence_sha256"}
    or attempt.get("schema") != "arnold.cloud.resident_only_intent.v1"
    or attempt.get("outage_epoch") != cfg["outage_epoch"]
    or attempt.get("source_container") != cfg["source_container"]
    or attempt.get("source_container_id") != cfg["expected_source_container_id"]
    or attempt.get("source_image_id") != cfg["expected_source_image_id"]
    or attempt.get("resident_image_id") != cfg["expected_resident_image_id"]
    or attempt.get("workspace") != cfg["workspace"]
    or attempt.get("resident_container") != cfg["resident_container"]
    or any(not isinstance(attempt.get(key), str) or len(attempt[key]) != 64 for key in ("resident_command_sha256", "resident_env_sha256", "source_fence_sha256"))
    or not isinstance(attempt.get("runtime_capture"), dict)
    or attempt.get("source_fence_sha256") != fence_sha256
):
    raise RuntimeError("attempt_intent_compare_and_swap_failed")
if os.path.exists(start_path):
    start = read_exact(start_path)
    if not isinstance(start.get("started_at"), str) or not start.get("started_at"):
        raise RuntimeError("start_receipt_started_at_invalid")
    if (
        set(start) != {"schema", "status", "outage_epoch", "source_container", "source_container_id", "source_image_id", "resident_image_id", "workspace", "resident_container", "resident_container_id", "resident_command_sha256", "resident_env_sha256", "intent_sha256", "recovery_seed_sha256", "runtime_path", "runtime_commit", "runtime_tree", "runtime_python_path", "runtime_python_sha256", "restart_policy", "listener_only", "started_at"}
        or start.get("schema") != "arnold.cloud.resident_only_start.v1"
        or start.get("status") != "started"
        or start.get("outage_epoch") != cfg["outage_epoch"]
        or start.get("source_container") != cfg["source_container"]
        or start.get("source_container_id") != cfg["expected_source_container_id"]
        or start.get("source_image_id") != cfg["expected_source_image_id"]
        or start.get("resident_image_id") != cfg["expected_resident_image_id"]
        or start.get("workspace") != cfg["workspace"]
        or start.get("resident_container") != cfg["resident_container"]
        or start.get("resident_container_id") != cfg["expected_resident_container_id"]
        or any(not isinstance(start.get(key), str) or len(start[key]) != 64 for key in ("resident_command_sha256", "resident_env_sha256", "intent_sha256", "recovery_seed_sha256", "runtime_python_sha256"))
        or any(not isinstance(start.get(key), str) or len(start[key]) != 40 for key in ("runtime_commit", "runtime_tree"))
        or not isinstance(start.get("runtime_path"), str)
        or not isinstance(start.get("runtime_python_path"), str)
        or start.get("restart_policy") != "no"
        or start.get("listener_only") is not True
        or start.get("intent_sha256") != attempt_sha256
    ):
        raise RuntimeError("start_receipt_compare_and_swap_failed")
else:
    pass

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
    if resident_by_name is None or resident_by_name.get("Id") != resident_by_id.get("Id") or resident_by_id.get("Image") != cfg["expected_resident_image_id"] or workspace_mount(resident_by_id) != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}:
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
    expected_resident_image_id: str,
    expected_runtime_path: str,
    expected_runtime_commit: str,
    expected_runtime_tree: str,
    expected_runtime_python_path: str,
    expected_runtime_python_sha256: str,
    workspace: str,
    outage_epoch: str,
    min_free_bytes: int,
    min_free_inodes: int,
    receipt_reserve_bytes: int,
    health_timeout_seconds: int,
) -> tuple[str, str]:
    source = validate_container_name(source_container)
    pinned_python = validate_absolute_path(expected_runtime_python_path, label="expected runtime Python path")
    if pinned_python == "/workspace" or pinned_python.startswith("/workspace/"):
        raise CliError(
            "resident_recovery_invalid",
            "expected runtime Python must come from the immutable accepted image, not the mutable workspace",
        )
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
        "expected_resident_image_id": validate_image_id(
            expected_resident_image_id,
            label="expected resident image",
        ),
        "custody_host_parent": _CUSTODY_BASE,
        "custody_host_root": resident_custody_host_root(expected_source_container_id),
        "expected_runtime_path": validate_runtime_path(expected_runtime_path),
        "expected_runtime_commit": validate_git_id(expected_runtime_commit, label="expected runtime commit"),
        "expected_runtime_tree": validate_git_id(expected_runtime_tree, label="expected runtime tree"),
        "expected_runtime_python_path": pinned_python,
        "expected_runtime_python_sha256": validate_sha256(expected_runtime_python_sha256, label="expected runtime Python SHA-256"),
        "workspace": validate_workspace_dir(workspace),
        "outage_epoch": validate_outage_epoch(outage_epoch),
        "resident_container": resident_only_container_name(source),
        "resident_workdir": "/workspace/arnold",
        "resident_argv_template": list(RESIDENT_ONLY_COMMAND),
        "resident_argv_template_sha256": hashlib.sha256(json.dumps(list(RESIDENT_ONLY_COMMAND), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "listener_recovery_seed_schema": LISTENER_RECOVERY_SEED_SCHEMA,
        "listener_capture_command": _LISTENER_CAPTURE_COMMAND,
        "listener_capture_command_sha256": hashlib.sha256(_LISTENER_CAPTURE_COMMAND.encode()).hexdigest(),
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
    expected_resident_image_id: str,
    expected_resident_container_id: str,
    workspace: str,
    outage_epoch: str,
) -> tuple[str, str]:
    source = validate_container_name(source_container)
    payload = {
        "source_container": source,
        "expected_source_container_id": validate_container_id(expected_source_container_id, label="expected source container ID"),
        "expected_source_image_id": validate_image_id(expected_source_image_id),
        "expected_resident_image_id": validate_image_id(
            expected_resident_image_id,
            label="expected resident image",
        ),
        "custody_host_root": resident_custody_host_root(expected_source_container_id),
        "expected_resident_container_id": validate_container_id(expected_resident_container_id, label="expected resident container ID"),
        "workspace": validate_workspace_dir(workspace),
        "outage_epoch": validate_outage_epoch(outage_epoch),
        "resident_container": resident_only_container_name(source),
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
            "fence_intent_sha256",
            "applied_restart_policy",
            "rollback_required",
        }
        or fence.get("schema") != FENCE_SCHEMA
        or fence.get("status") != "fenced"
        or fence.get("applied_restart_policy")
        != {"Name": "no", "MaximumRetryCount": 0}
        or not isinstance(fence.get("prior_restart_policy"), dict)
        or not re.fullmatch(r"[0-9a-f]{64}", str(fence.get("fence_intent_sha256") or ""))
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
            "resident_image_id",
            "workspace",
            "resident_container",
            "resident_container_id",
            "resident_command_sha256",
            "resident_env_sha256",
            "intent_sha256",
            "recovery_seed_sha256",
            "runtime_path",
            "runtime_commit",
            "runtime_tree",
            "runtime_python_path",
            "runtime_python_sha256",
            "restart_policy",
            "listener_only",
            "started_at",
        }
        or start.get("schema") != START_SCHEMA
        or start.get("status") != "started"
        or not _CONTAINER_ID_RE.fullmatch(str(start.get("source_container_id") or ""))
        or not _IMAGE_ID_RE.fullmatch(str(start.get("source_image_id") or ""))
        or not _IMAGE_ID_RE.fullmatch(str(start.get("resident_image_id") or ""))
        or not _CONTAINER_ID_RE.fullmatch(str(start.get("resident_container_id") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("resident_command_sha256") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("resident_env_sha256") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("intent_sha256") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("recovery_seed_sha256") or ""))
        or not re.fullmatch(r"[0-9a-f]{40}", str(start.get("runtime_commit") or ""))
        or not re.fullmatch(r"[0-9a-f]{40}", str(start.get("runtime_tree") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(start.get("runtime_python_sha256") or ""))
        or not isinstance(start.get("runtime_path"), str)
        or not isinstance(start.get("runtime_python_path"), str)
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
        or set(paths) != {"fence_intent", "fence", "intent", "seed", "start", "health"}
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
    "resident_custody_host_root",
    "resident_only_container_name",
    "resident_recover_command",
]
