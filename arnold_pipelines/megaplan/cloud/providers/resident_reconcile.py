"""Exact finite adoption proof for an unreceipted resident listener."""

from __future__ import annotations


RECONCILE_ADOPTION_SCRIPT = r'''
import base64, fcntl, hashlib, json, os, stat, subprocess, sys, tempfile

cfg = json.loads(base64.b64decode(sys.argv[1], validate=True))
if os.geteuid() != 0:
    raise RuntimeError("resident_reconcile_requires_root_custody")

def call(argv, *, check=True):
    result = subprocess.run(argv, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError("fixed_operation_failed:" + argv[0])
    return result

def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

def canonical_sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def strict_object(raw, *, label):
    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RuntimeError(label + "_duplicate_field")
            value[key] = item
        return value
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(label + "_invalid_json") from error
    if not isinstance(value, dict):
        raise RuntimeError(label + "_not_object")
    return value

def inspect(identifier):
    result = call(["docker", "inspect", "--type=container", identifier], check=False)
    if result.returncode != 0:
        diagnostic = result.stderr.decode(errors="replace")
        if result.returncode == 1 and ("No such container" in diagnostic or "No such object" in diagnostic):
            return None
        raise RuntimeError("container_inspect_failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("container_inspect_invalid") from error
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise RuntimeError("container_inspect_invalid")
    return value[0]

def exact_mount(item, destination):
    mounts = item.get("Mounts")
    rows = [row for row in mounts if isinstance(row, dict) and row.get("Destination") == destination] if isinstance(mounts, list) else []
    if len(rows) != 1:
        raise RuntimeError("required_bind_missing_or_ambiguous")
    row = rows[0]
    return {"type": row.get("Type"), "source": row.get("Source"), "destination": destination, "rw": row.get("RW")}

def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("reconcile_custody_directory_invalid")

def read_receipt(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError("receipt_file_invalid")
    with open(path, "rb") as handle:
        return strict_object(handle.read(), label="receipt")

def publish_once(path, payload):
    data = canonical_bytes(payload) + b"\n"
    if os.path.exists(path):
        if read_receipt(path) != payload:
            raise RuntimeError("immutable_receipt_mismatch")
        return
    parent = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix=".reconcile.", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if read_receipt(path) != payload:
                raise RuntimeError("immutable_receipt_mismatch")
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass

def read_evidence(path, *, label):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError(label + "_custody_invalid")
    with open(path, "rb") as handle:
        return handle.read()

def exact_source():
    by_id = inspect(cfg["expected_source_container_id"])
    by_name = inspect(cfg["source_container"])
    if by_id is None or by_name is None or by_id.get("Id") != by_name.get("Id"):
        raise RuntimeError("source_name_identity_mismatch")
    state = by_id.get("State")
    host = by_id.get("HostConfig")
    policy = host.get("RestartPolicy") if isinstance(host, dict) else None
    if (
        by_id.get("Id") != cfg["expected_source_container_id"]
        or by_id.get("Image") != cfg["expected_source_image_id"]
        or by_id.get("Name") != "/" + cfg["source_container"]
        or not isinstance(state, dict)
        or state.get("Running") is not False
        or state.get("Paused") is not False
        or state.get("Restarting") is not False
        or not isinstance(policy, dict)
        or set(policy) != {"Name", "MaximumRetryCount"}
        or policy.get("Name") not in {"no", "always", "unless-stopped", "on-failure"}
        or type(policy.get("MaximumRetryCount")) is not int
        or policy["MaximumRetryCount"] < 0
        or (policy["Name"] != "on-failure" and policy["MaximumRetryCount"] != 0)
        or exact_mount(by_id, "/workspace") != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
    ):
        raise RuntimeError("source_compare_and_swap_failed")

root = cfg["custody_host_root"]
epoch_root = os.path.join(root, cfg["outage_epoch"])
for path in (cfg["custody_host_parent"], root, epoch_root):
    ensure_private_dir(path)
lock_fd = os.open(os.path.join(root, ".resident-reconcile.lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
fcntl.flock(lock_fd, fcntl.LOCK_EX)
prefix = os.path.join(epoch_root, "transaction")
intent_path = prefix + ".reconcile.intent.json"
adoption_path = prefix + ".reconcile.adopted.json"
down_intent_path = prefix + ".reconcile.down.intent.json"
down_path = prefix + ".reconcile.down.json"
canonical_paths = [prefix + suffix for suffix in (
    ".fence.intent.json", ".fence.json", ".intent.json", ".start.json",
    ".health.json", ".down.intent.json", ".down.json",
)]
if any(os.path.exists(path) for path in canonical_paths):
    raise RuntimeError("reconcile_conflicting_canonical_receipt")

expected_command = cfg["expected_resident_command"]
expected_workspace = {"st_dev": cfg["expected_workspace_device"], "st_ino": cfg["expected_workspace_inode"]}
intent = {
    "schema": "arnold.cloud.resident_only_reconcile_intent.v1",
    "outage_epoch": cfg["outage_epoch"],
    "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"],
    "source_image_id": cfg["expected_source_image_id"],
    "resident_container": cfg["resident_container"],
    "resident_container_id": cfg["expected_resident_container_id"],
    "resident_image_id": cfg["expected_resident_image_id"],
    "resident_command_sha256": cfg["expected_resident_command_sha256"],
    "resident_env_sha256": cfg["expected_resident_env_sha256"],
    "recovery_seed_host_dir": cfg["expected_recovery_seed_host_dir"],
    "recovery_seed_sha256": cfg["expected_recovery_seed_sha256"],
    "runtime_path": cfg["expected_runtime_path"],
    "runtime_commit": cfg["expected_runtime_commit"],
    "runtime_tree": cfg["expected_runtime_tree"],
    "runtime_content_sha256": cfg["expected_runtime_content_sha256"],
    "runtime_python_path": cfg["expected_runtime_python_path"],
    "runtime_python_sha256": cfg["expected_runtime_python_sha256"],
    "workspace": cfg["workspace"],
    "workspace_identity": expected_workspace,
}
if os.path.exists(intent_path):
    if read_receipt(intent_path) != intent:
        raise RuntimeError("reconcile_intent_mismatch")
else:
    if any(os.path.exists(path) for path in (adoption_path, down_intent_path, down_path)):
        raise RuntimeError("reconcile_receipt_without_intent")
    publish_once(intent_path, intent)
intent_sha = canonical_sha(intent)
if os.path.exists(adoption_path):
    adoption = read_receipt(adoption_path)
    if adoption.get("schema") != "arnold.cloud.resident_only_reconcile_adoption.v1" or adoption.get("status") != "adopted" or adoption.get("reconcile_intent_sha256") != intent_sha or adoption.get("resident_container_id") != cfg["expected_resident_container_id"]:
        raise RuntimeError("reconcile_adoption_mismatch")
    print(json.dumps(adoption, sort_keys=True, separators=(",", ":")))
    raise SystemExit(0)
if os.path.exists(down_intent_path) or os.path.exists(down_path):
    raise RuntimeError("reconcile_down_receipt_without_adoption")

exact_source()
resident_by_id = inspect(cfg["expected_resident_container_id"])
resident_by_name = inspect(cfg["resident_container"])
if resident_by_id is None or resident_by_name is None or resident_by_id.get("Id") != resident_by_name.get("Id"):
    raise RuntimeError("resident_name_identity_mismatch")
state = resident_by_id.get("State")
host = resident_by_id.get("HostConfig")
config = resident_by_id.get("Config")
runtime_host_path = os.path.join(cfg["workspace"], cfg["expected_runtime_path"].removeprefix("/workspace/"))
if (
    resident_by_id.get("Id") != cfg["expected_resident_container_id"]
    or resident_by_id.get("Image") != cfg["expected_resident_image_id"]
    or resident_by_id.get("Name") != "/" + cfg["resident_container"]
    or not isinstance(state, dict)
    or state.get("Running") is not True
    or not isinstance(state.get("StartedAt"), str)
    or not state.get("StartedAt")
    or not isinstance(host, dict)
    or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
    or host.get("CapDrop") != ["ALL"]
    or host.get("CapAdd") not in (None, [])
    or host.get("SecurityOpt") != ["no-new-privileges:true"]
    or host.get("PidsLimit") != 256
    or host.get("Memory") != 2147483648
    or host.get("MemorySwap") != 2147483648
    or exact_mount(resident_by_id, "/workspace") != {"type": "bind", "source": cfg["workspace"], "destination": "/workspace", "rw": True}
    or exact_mount(resident_by_id, cfg["expected_runtime_path"]) != {"type": "bind", "source": runtime_host_path, "destination": cfg["expected_runtime_path"], "rw": False}
    or exact_mount(resident_by_id, "/run/megaplan-resident-recovery") != {"type": "bind", "source": cfg["expected_recovery_seed_host_dir"], "destination": "/run/megaplan-resident-recovery", "rw": False}
    or not isinstance(config, dict)
    or config.get("Entrypoint") != [cfg["expected_runtime_python_path"]]
    or config.get("Cmd") != expected_command
    or config.get("User") != "0:0"
    or config.get("WorkingDir") != "/workspace/arnold"
):
    raise RuntimeError("resident_adoption_identity_mismatch")
if canonical_sha(config["Cmd"]) != cfg["expected_resident_command_sha256"]:
    raise RuntimeError("resident_command_digest_mismatch")

seed_path = os.path.join(cfg["expected_recovery_seed_host_dir"], "launch-seed.json")
env_path = os.path.join(os.path.dirname(cfg["expected_recovery_seed_host_dir"]), "resident.env")
seed_raw = read_evidence(seed_path, label="recovery_seed")
env_raw = read_evidence(env_path, label="resident_env")
seed = strict_object(seed_raw, label="recovery_seed")
if canonical_sha(seed) != cfg["expected_recovery_seed_sha256"]:
    raise RuntimeError("recovery_seed_digest_mismatch")
if hashlib.sha256(env_raw).hexdigest() != cfg["expected_resident_env_sha256"]:
    raise RuntimeError("resident_env_digest_mismatch")
if (
    set(seed) != set(cfg["recovery_seed_fields"])
    or seed.get("schema") != cfg["recovery_seed_schema"]
    or seed.get("outage_epoch") != cfg["outage_epoch"]
    or seed.get("source_container_id") != cfg["expected_source_container_id"]
    or seed.get("source_image_id") != cfg["expected_source_image_id"]
    or seed.get("resident_image_id") != cfg["expected_resident_image_id"]
    or seed.get("workspace_host_path") != cfg["workspace"]
    or seed.get("workspace_identity") != expected_workspace
    or seed.get("runtime_path") != cfg["expected_runtime_path"]
    or seed.get("runtime_commit") != cfg["expected_runtime_commit"]
    or seed.get("runtime_tree") != cfg["expected_runtime_tree"]
    or seed.get("runtime_python_path") != cfg["expected_runtime_python_path"]
    or seed.get("runtime_python_sha256") != cfg["expected_runtime_python_sha256"]
    or seed.get("command_sha256") != cfg["expected_resident_command_sha256"]
    or seed.get("resident_env_sha256") != cfg["expected_resident_env_sha256"]
    or seed.get("container_id") != cfg["expected_resident_container_id"]
):
    raise RuntimeError("recovery_seed_identity_mismatch")

configured_env = config.get("Env")
if not isinstance(configured_env, list) or any(not isinstance(row, str) or "=" not in row for row in configured_env):
    raise RuntimeError("resident_container_environment_invalid")
env_map = {}
for row in configured_env:
    key, value = row.split("=", 1)
    if key in env_map:
        raise RuntimeError("resident_container_environment_duplicate")
    env_map[key] = value
file_env = {}
for line in env_raw.decode("utf-8").splitlines():
    if not line or line.startswith("#"):
        continue
    if "=" not in line:
        raise RuntimeError("resident_env_file_invalid")
    key, value = line.split("=", 1)
    if key in file_env:
        raise RuntimeError("resident_env_file_duplicate")
    file_env[key] = value
hazardous = {"BASH_ENV", "ENV", "SHELLOPTS", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "LD_PRELOAD", "LD_LIBRARY_PATH"}
allowed_injected = {
    "PYTHONPATH": cfg["expected_runtime_path"],
    "MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE": "production",
}
# Deny-by-default: the resident must run with runtime attestation REQUIRED
# (absent => default ON).  A live container that explicitly disabled
# attestation (``=0``) must never be adopted.
attestation_required = env_map.get("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED")
if any(key in env_map for key in hazardous) or any(env_map.get(key) != value for key, value in file_env.items()) or any(env_map.get(key) != value for key, value in allowed_injected.items()) or attestation_required not in (None, "1") or set(env_map) - set(file_env) - set(allowed_injected) - {"MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED"}:
    raise RuntimeError("resident_environment_compare_and_swap_failed")

workspace_stat = os.stat(cfg["workspace"], follow_symlinks=False)
if {"st_dev": workspace_stat.st_dev, "st_ino": workspace_stat.st_ino} != expected_workspace:
    raise RuntimeError("workspace_identity_mismatch")
if call(["git", "-C", runtime_host_path, "rev-parse", "HEAD"]).stdout.decode().strip() != cfg["expected_runtime_commit"]:
    raise RuntimeError("runtime_commit_mismatch")
if call(["git", "-C", runtime_host_path, "rev-parse", "HEAD^{tree}"]).stdout.decode().strip() != cfg["expected_runtime_tree"]:
    raise RuntimeError("runtime_tree_mismatch")
if call(["git", "-C", runtime_host_path, "diff", "--quiet", "--"], check=False).returncode != 0 or call(["git", "-C", runtime_host_path, "diff", "--cached", "--quiet", "--"], check=False).returncode != 0:
    raise RuntimeError("runtime_tracked_content_dirty")
archive = call(["git", "-C", runtime_host_path, "archive", "--format=tar", cfg["expected_runtime_commit"]]).stdout
if hashlib.sha256(archive).hexdigest() != cfg["expected_runtime_content_sha256"]:
    raise RuntimeError("runtime_content_digest_mismatch")
python_digest = call(["docker", "exec", cfg["expected_resident_container_id"], "sha256sum", cfg["expected_runtime_python_path"]]).stdout.decode().split()
if not python_digest or python_digest[0] != cfg["expected_runtime_python_sha256"]:
    raise RuntimeError("runtime_python_digest_mismatch")

all_ids = call(["docker", "ps", "--no-trunc", "-aq"]).stdout.decode().split()
listener_ids = []
for container_id in all_ids:
    item = inspect(container_id)
    item_state = item.get("State") if isinstance(item, dict) else None
    item_config = item.get("Config") if isinstance(item, dict) else None
    item_command = item_config.get("Cmd") if isinstance(item_config, dict) else None
    if isinstance(item_state, dict) and item_state.get("Running") is True and isinstance(item_command, list) and item_command[:5] == ["-P", "-m", "arnold_pipelines.megaplan", "resident", "discord"] and "--listener-only" in item_command:
        listener_ids.append(item.get("Id"))
if listener_ids != [cfg["expected_resident_container_id"]]:
    raise RuntimeError("resident_listener_singleton_mismatch")

probe_code = (
    "import json,os,stat;"
    "wanted=json.loads(os.environ['RECONCILE_WANTED']);rows=[];"
    "\nfor name in os.listdir('/proc'):\n"
    " if name.isdigit():\n"
    "  try:\n"
    "   raw=open('/proc/'+name+'/cmdline','rb').read().split(b'\\0');argv=[part.decode() for part in raw if part]\n"
    "  except (OSError,UnicodeDecodeError): continue\n"
    "  if argv==wanted: rows.append(name)\n"
    "marker='/run/megaplan-resident-recovery-consumed/'+os.environ['RECONCILE_SEED']+'.consumed';"
    "info=os.lstat(marker);"
    "ok=stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o600 and open(marker,'rb').read()==b'consumed\\n';"
    "print(json.dumps({'process_count':len(rows),'marker':ok},sort_keys=True))"
)
probe = call([
    "docker", "exec",
    "--env", "RECONCILE_WANTED=" + json.dumps([cfg["expected_runtime_python_path"], *expected_command], separators=(",", ":")),
    "--env", "RECONCILE_SEED=" + canonical_sha(seed),
    cfg["expected_resident_container_id"], cfg["expected_runtime_python_path"], "-c", probe_code,
])
try:
    live = json.loads(probe.stdout)
except json.JSONDecodeError as error:
    raise RuntimeError("resident_live_probe_invalid") from error
if live != {"marker": True, "process_count": 1}:
    raise RuntimeError("resident_live_probe_mismatch")
logs = call(["docker", "logs", cfg["expected_resident_container_id"]]).stdout.decode(errors="replace")
if "Resident Discord service ready " not in logs or " listener_only=True " not in logs:
    raise RuntimeError("resident_readiness_evidence_missing")

adoption = {
    "schema": "arnold.cloud.resident_only_reconcile_adoption.v1",
    "status": "adopted",
    "outage_epoch": cfg["outage_epoch"],
    "source_container": cfg["source_container"],
    "source_container_id": cfg["expected_source_container_id"],
    "source_image_id": cfg["expected_source_image_id"],
    "resident_container": cfg["resident_container"],
    "resident_container_id": cfg["expected_resident_container_id"],
    "resident_image_id": cfg["expected_resident_image_id"],
    "resident_command_sha256": cfg["expected_resident_command_sha256"],
    "resident_env_sha256": cfg["expected_resident_env_sha256"],
    "recovery_seed_host_dir": cfg["expected_recovery_seed_host_dir"],
    "recovery_seed_sha256": cfg["expected_recovery_seed_sha256"],
    "runtime_path": cfg["expected_runtime_path"],
    "runtime_commit": cfg["expected_runtime_commit"],
    "runtime_tree": cfg["expected_runtime_tree"],
    "runtime_content_sha256": cfg["expected_runtime_content_sha256"],
    "runtime_python_path": cfg["expected_runtime_python_path"],
    "runtime_python_sha256": cfg["expected_runtime_python_sha256"],
    "workspace": cfg["workspace"],
    "workspace_identity": expected_workspace,
    "reconcile_intent_sha256": intent_sha,
    "started_at": state["StartedAt"],
    "source_fence_rollback": {"status": "not_applicable"},
}
publish_once(adoption_path, adoption)
print(json.dumps(adoption, sort_keys=True, separators=(",", ":")))
'''.strip()


__all__ = ["RECONCILE_ADOPTION_SCRIPT"]
