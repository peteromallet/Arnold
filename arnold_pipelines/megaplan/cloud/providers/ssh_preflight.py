"""Fixed, read-only host observations used before SSH cloud launch.

The public builders accept only the configured container/workspace and numeric
reserve floors.  They intentionally do not expose an arbitrary host command.
"""

from __future__ import annotations

import json
import posixpath
import re
import shlex
from pathlib import PurePosixPath
from typing import Any, Mapping

from arnold_pipelines.megaplan.types import CliError


_CONTAINER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_MISSING_CONTAINER_MARKERS = (
    "no such container",
    "no such object",
    "container not found",
)


def validate_container_name(value: str) -> str:
    if not isinstance(value, str) or not _CONTAINER_NAME_RE.fullmatch(value):
        raise CliError(
            "invalid_provider_observation_target",
            "configured SSH container name is not a safe Docker identifier",
        )
    return value


def validate_workspace_dir(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\n" in value
        or "\r" in value
    ):
        raise CliError(
            "invalid_provider_observation_target",
            "configured SSH workspace directory is not a safe absolute path",
        )
    path = PurePosixPath(value)
    normalized = posixpath.normpath(value)
    if (
        not path.is_absolute()
        or normalized != value
        or value == "/"
        or ".." in path.parts
    ):
        raise CliError(
            "invalid_provider_observation_target",
            "configured SSH workspace directory must be normalized, absolute, and non-root",
        )
    return value


def container_inspect_command(container: str) -> str:
    name = validate_container_name(container)
    return shlex.join(
        [
            "docker",
            "inspect",
            "--type",
            "container",
            "--format",
            "{{json .State}}\n{{json .Id}}\n{{json .Image}}\n{{json .Config.Image}}\n{{json .Mounts}}",
            name,
        ]
    )


def classify_container_inspect(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    expected_container: str,
) -> dict[str, Any]:
    """Classify fixed ``docker inspect`` output without guessing transport errors."""
    name = validate_container_name(expected_container)
    diagnostic = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part)
    lowered = diagnostic.lower()
    if returncode != 0:
        lifecycle = (
            "missing"
            if any(marker in lowered for marker in _MISSING_CONTAINER_MARKERS)
            else "unknown"
        )
        return {
            "schema": "arnold.cloud.ssh_container_observation.v1",
            "status": "available" if lifecycle == "missing" else "unknown",
            "lifecycle": lifecycle,
            "container": name,
            "returncode": returncode,
            "diagnostic": diagnostic,
            "collector": {
                "status": "unavailable",
                "reason": "container_missing"
                if lifecycle == "missing"
                else "container_state_unknown",
            },
        }

    try:
        lines = stdout.splitlines()
        if len(lines) != 5:
            raise ValueError("expected five docker inspect fields")
        state, container_id, image_id, image_ref, mounts = (
            json.loads(line) for line in lines
        )
        payload = {
            "State": state,
            "Id": container_id,
            "Image": image_id,
            "Config": {"Image": image_ref},
            "Mounts": mounts,
        }
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema": "arnold.cloud.ssh_container_observation.v1",
            "status": "unknown",
            "lifecycle": "unknown",
            "container": name,
            "returncode": returncode,
            "diagnostic": f"docker inspect output was not JSON: {exc}",
            "collector": {"status": "unavailable", "reason": "container_state_unknown"},
        }
    if not isinstance(payload, Mapping):
        return {
            "schema": "arnold.cloud.ssh_container_observation.v1",
            "status": "unknown",
            "lifecycle": "unknown",
            "container": name,
            "returncode": returncode,
            "diagnostic": "docker inspect output was not an object",
            "collector": {"status": "unavailable", "reason": "container_state_unknown"},
        }

    state = payload.get("State") if isinstance(payload.get("State"), Mapping) else {}
    raw_status = str(state.get("Status") or "").lower()
    if bool(state.get("Paused")):
        lifecycle = "paused"
    elif bool(state.get("Restarting")) or raw_status == "restarting":
        lifecycle = "restarting"
    elif bool(state.get("Running")) and raw_status in {"", "running"}:
        lifecycle = "running"
    elif (
        raw_status in {"created", "exited", "dead", "removing"}
        and state.get("Running") is False
    ):
        lifecycle = "stopped"
    else:
        lifecycle = "unknown"

    mounts = payload.get("Mounts") if isinstance(payload.get("Mounts"), list) else []
    workspace_mounts = [
        item
        for item in mounts
        if isinstance(item, Mapping) and item.get("Destination") == "/workspace"
    ]
    if len(workspace_mounts) == 1:
        mount = workspace_mounts[0]
        workspace_bind = {
            "status": "present",
            "type": mount.get("Type"),
            "source": mount.get("Source"),
            "destination": "/workspace",
            "rw": bool(mount.get("RW")),
        }
    else:
        workspace_bind = {
            "status": "missing" if not workspace_mounts else "invalid",
            "count": len(workspace_mounts),
            "destination": "/workspace",
        }

    config = payload.get("Config") if isinstance(payload.get("Config"), Mapping) else {}
    observation = {
        "schema": "arnold.cloud.ssh_container_observation.v1",
        "status": "available" if lifecycle != "unknown" else "unknown",
        "lifecycle": lifecycle,
        "container": name,
        "container_id": payload.get("Id"),
        "returncode": returncode,
        "exit_code": state.get("ExitCode"),
        "oom_killed": bool(state.get("OOMKilled")),
        "error": str(state.get("Error") or ""),
        "image_id": payload.get("Image"),
        "image_ref": config.get("Image"),
        "workspace_bind": workspace_bind,
        "collector": {
            "status": "available" if lifecycle == "running" else "unavailable",
            "reason": None if lifecycle == "running" else f"container_{lifecycle}",
        },
    }
    return observation


_CAPACITY_PROBE_SCRIPT = r"""
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile

workspace = sys.argv[1]
min_free_bytes = int(sys.argv[2])
min_free_inodes = int(sys.argv[3])
reserve_bytes = int(sys.argv[4])
result = {
    "schema": "arnold.cloud.ssh_workspace_prelaunch.v1",
    "workspace": workspace,
    "thresholds": {
        "min_free_bytes": min_free_bytes,
        "min_free_inodes": min_free_inodes,
        "receipt_reserve_bytes": reserve_bytes,
    },
    "checks": {},
    "errors": [],
}
probe_dir = None

def mount_identity(path):
    st = os.stat(path, follow_symlinks=False)
    identity = {
        "st_dev": st.st_dev,
        "device_major": os.major(st.st_dev),
        "device_minor": os.minor(st.st_dev),
        "inode": st.st_ino,
    }
    best = None
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as handle:
            for line in handle:
                fields = line.rstrip("\n").split()
                if "-" not in fields or len(fields) < 10:
                    continue
                dash = fields.index("-")
                mount_point = fields[4].replace("\\040", " ")
                if path == mount_point or path.startswith(mount_point.rstrip("/") + "/"):
                    if best is None or len(mount_point) > len(best[0]):
                        best = (mount_point, fields[dash + 1], fields[dash + 2])
    except OSError:
        pass
    if best is not None:
        identity.update({"mount_point": best[0], "filesystem": best[1], "mount_source": best[2]})
    return identity

try:
    lst = os.lstat(workspace)
    if not stat.S_ISDIR(lst.st_mode) or stat.S_ISLNK(lst.st_mode):
        raise RuntimeError("configured workspace is not a real directory")
    if os.path.realpath(workspace) != workspace:
        raise RuntimeError("configured workspace path resolves elsewhere")
    result["mount"] = mount_identity(workspace)
    before = os.statvfs(workspace)
    free_bytes = before.f_bavail * before.f_frsize
    free_inodes = before.f_favail
    result["capacity"] = {"free_bytes": free_bytes, "free_inodes": free_inodes}
    required_bytes = min_free_bytes + reserve_bytes
    result["checks"]["byte_floor"] = free_bytes >= required_bytes
    result["checks"]["inode_floor"] = free_inodes >= min_free_inodes
    if not result["checks"]["byte_floor"]:
        result["errors"].append("prelaunch_free_bytes_below_reserve")
    if not result["checks"]["inode_floor"]:
        result["errors"].append("prelaunch_free_inodes_below_reserve")
    if result["errors"]:
        raise RuntimeError("capacity floor failed")

    probe_dir = tempfile.mkdtemp(prefix=".arnold-prelaunch-", dir=workspace)
    reserve_path = os.path.join(probe_dir, "receipt.reserve")
    fd = os.open(reserve_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        if reserve_bytes:
            if hasattr(os, "posix_fallocate"):
                os.posix_fallocate(fd, 0, reserve_bytes)
            else:
                remaining = reserve_bytes
                block = b"\0" * min(1024 * 1024, reserve_bytes)
                while remaining:
                    written = os.write(fd, block[:remaining])
                    if written <= 0:
                        raise RuntimeError("receipt reserve write made no progress")
                    remaining -= written
                os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, b"arnold-prelaunch\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    result["checks"]["reserve_fsync"] = True

    db_path = os.path.join(probe_dir, "probe.sqlite3")
    connection = sqlite3.connect(db_path)
    try:
        journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TABLE receipt (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        connection.execute("INSERT INTO receipt(payload) VALUES (?)", ("prelaunch",))
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        checkpoint = connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
    finally:
        connection.close()
    if str(journal).lower() != "wal" or integrity != "ok" or not checkpoint or checkpoint[0] != 0:
        raise RuntimeError("sqlite WAL durability probe failed")
    db_fd = os.open(db_path, os.O_RDONLY)
    try:
        os.fsync(db_fd)
    finally:
        os.close(db_fd)
    result["checks"]["sqlite_wal"] = True

    receipt_tmp = os.path.join(probe_dir, "receipt.json.tmp")
    receipt_path = os.path.join(probe_dir, "receipt.json")
    receipt_fd = os.open(receipt_tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(receipt_fd, b'{"status":"durable"}\n')
        os.fsync(receipt_fd)
    finally:
        os.close(receipt_fd)
    os.replace(receipt_tmp, receipt_path)
    dir_fd = os.open(probe_dir, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    result["checks"]["receipt_atomic_fsync"] = True
except Exception as exc:
    message = str(exc)
    if message and message not in result["errors"] and message != "capacity floor failed":
        result["errors"].append(message)
finally:
    if probe_dir is not None:
        try:
            shutil.rmtree(probe_dir)
            workspace_fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(workspace_fd)
            finally:
                os.close(workspace_fd)
            result["checks"]["cleanup"] = True
        except Exception as exc:
            result["checks"]["cleanup"] = False
            result["errors"].append("probe_cleanup_failed: " + str(exc))

required_checks = ("byte_floor", "inode_floor", "reserve_fsync", "sqlite_wal", "receipt_atomic_fsync", "cleanup")
result["status"] = "go" if not result["errors"] and all(result["checks"].get(key) is True for key in required_checks) else "no-go"
result["verdict"] = "GO" if result["status"] == "go" else "NO-GO"
print(json.dumps(result, sort_keys=True))
raise SystemExit(0 if result["status"] == "go" else 3)
""".strip()


def workspace_prelaunch_command(
    workspace_dir: str,
    *,
    min_free_bytes: int,
    min_free_inodes: int,
    receipt_reserve_bytes: int,
) -> str:
    workspace = validate_workspace_dir(workspace_dir)
    values = (min_free_bytes, min_free_inodes, receipt_reserve_bytes)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in values
    ):
        raise CliError(
            "invalid_provider_observation_target",
            "prelaunch capacity thresholds must be non-negative integers",
        )
    return shlex.join(
        [
            "python3",
            "-c",
            _CAPACITY_PROBE_SCRIPT,
            workspace,
            str(min_free_bytes),
            str(min_free_inodes),
            str(receipt_reserve_bytes),
        ]
    )


def parse_workspace_prelaunch_result(
    *, returncode: int, stdout: str, stderr: str
) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        diagnostic = "\n".join(
            part for part in (stderr.strip(), stdout.strip()) if part
        )
        return {
            "schema": "arnold.cloud.ssh_workspace_prelaunch.v1",
            "status": "unknown",
            "verdict": "NO-GO",
            "returncode": returncode,
            "errors": ["workspace prelaunch output was not valid JSON"],
            "diagnostic": diagnostic,
        }
    payload["returncode"] = returncode
    if (
        returncode == 0
        and payload.get("status") == "go"
        and payload.get("verdict") == "GO"
    ):
        return payload
    payload["status"] = "no-go" if payload.get("status") == "no-go" else "unknown"
    payload["verdict"] = "NO-GO"
    if stderr.strip():
        payload.setdefault("diagnostic", stderr.strip())
    return payload


__all__ = [
    "classify_container_inspect",
    "container_inspect_command",
    "parse_workspace_prelaunch_result",
    "validate_container_name",
    "validate_workspace_dir",
    "workspace_prelaunch_command",
]
