"""Custody-bound launch attestation for finite listener-only recovery."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

from arnold_pipelines.megaplan.types import CliError


LISTENER_RECOVERY_SEED_SCHEMA = "arnold.megaplan.resident_listener_recovery_seed.v1"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_EPOCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_SEED_FIELDS = {
    "schema",
    "outage_epoch",
    "nonce",
    "source_container_id",
    "source_image_id",
    "workspace_host_path",
    "workspace_identity",
    "runtime_path",
    "runtime_commit",
    "runtime_tree",
    "runtime_python_path",
    "runtime_python_sha256",
    "command_sha256",
    "resident_env_sha256",
    "container_id",
}


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate recovery seed field")
            value[key] = item
        return value

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed is unreadable or malformed",
        ) from exc
    if not isinstance(value, dict):
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed must be an object",
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(runtime_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(runtime_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery runtime Git identity is unavailable",
        )
    return result.stdout.strip()


def _git_tracked_tree_is_clean(runtime_path: Path) -> bool:
    return all(
        subprocess.run(
            ["git", "-C", str(runtime_path), *args],
            capture_output=True,
            check=False,
        ).returncode
        == 0
        for args in (("diff", "--quiet", "--"), ("diff", "--cached", "--quiet", "--"))
    )


def _consume_recovery_seed_once(
    seed: dict[str, Any],
    consumption_root: Path,
    *,
    required_uid: int = 0,
) -> None:
    try:
        consumption_root.mkdir(mode=0o700, parents=False, exist_ok=True)
        consumption_stat = os.lstat(consumption_root)
        if (
            not stat.S_ISDIR(consumption_stat.st_mode)
            or stat.S_ISLNK(consumption_stat.st_mode)
            or consumption_stat.st_uid != required_uid
            or stat.S_IMODE(consumption_stat.st_mode) != 0o700
        ):
            raise OSError("invalid consumption root custody")
        seed_digest = hashlib.sha256(
            json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        marker = consumption_root / f"{seed_digest}.consumed"
        fd = os.open(
            marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(fd, b"consumed\n")
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed was already consumed or cannot be consumed safely",
        ) from exc


def require_listener_recovery_seed(
    seed_path: str | None,
    *,
    hostname: str | None = None,
    workspace_mount: Path = Path("/workspace"),
    executable: Path | None = None,
    consumption_root: Path = Path("/run/megaplan-resident-recovery-consumed"),
) -> dict[str, Any]:
    """Validate a root-custodied seed against this exact running process."""
    if not seed_path:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener-only resident requires a recovery launch seed",
        )
    path = Path(seed_path)
    expected_parent = Path("/run/megaplan-resident-recovery")
    if (
        path != expected_parent / "launch-seed.json"
    ):
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed path is outside the fixed custody root",
        )
    try:
        parent_stat = os.lstat(expected_parent)
        seed_stat = os.lstat(path)
    except OSError as exc:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed custody is unavailable",
        ) from exc
    if (
        not stat.S_ISDIR(parent_stat.st_mode)
        or stat.S_ISLNK(parent_stat.st_mode)
        or parent_stat.st_uid != 0
        or stat.S_IMODE(parent_stat.st_mode) != 0o700
        or not stat.S_ISREG(seed_stat.st_mode)
        or stat.S_ISLNK(seed_stat.st_mode)
        or seed_stat.st_uid != 0
        or stat.S_IMODE(seed_stat.st_mode) != 0o600
    ):
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed failed root custody validation",
        )
    seed = _strict_json(path)
    workspace_identity = seed.get("workspace_identity")
    runtime_path = Path(str(seed.get("runtime_path") or ""))
    python_path = Path(str(seed.get("runtime_python_path") or ""))
    container_id = str(seed.get("container_id") or "")
    current_hostname = (hostname or os.uname().nodename).strip()
    try:
        mount_stat = os.stat(workspace_mount, follow_symlinks=False)
    except OSError as exc:
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery workspace identity is unavailable",
        ) from exc
    imported_root = Path(__file__).resolve().parents[3]
    actual_python = (executable or Path(sys.executable)).resolve()
    if (
        set(seed) != _SEED_FIELDS
        or seed.get("schema") != LISTENER_RECOVERY_SEED_SCHEMA
        or not _EPOCH.fullmatch(str(seed.get("outage_epoch") or ""))
        or not _HEX64.fullmatch(str(seed.get("nonce") or ""))
        or not _HEX64.fullmatch(str(seed.get("source_container_id") or ""))
        or not _IMAGE_ID.fullmatch(str(seed.get("source_image_id") or ""))
        or not isinstance(seed.get("workspace_host_path"), str)
        or not str(seed.get("workspace_host_path")).startswith("/")
        or not _HEX64.fullmatch(container_id)
        or not container_id.startswith(current_hostname)
        or not isinstance(workspace_identity, dict)
        or set(workspace_identity) != {"st_dev", "st_ino"}
        or workspace_identity
        != {"st_dev": mount_stat.st_dev, "st_ino": mount_stat.st_ino}
        or not runtime_path.is_absolute()
        or runtime_path != runtime_path.resolve()
        or workspace_mount not in runtime_path.parents
        or imported_root != runtime_path
        or not _GIT_ID.fullmatch(str(seed.get("runtime_commit") or ""))
        or not _GIT_ID.fullmatch(str(seed.get("runtime_tree") or ""))
        or _git_value(runtime_path, "rev-parse", "HEAD")
        != seed.get("runtime_commit")
        or _git_value(runtime_path, "rev-parse", "HEAD^{tree}")
        != seed.get("runtime_tree")
        or not _git_tracked_tree_is_clean(runtime_path)
        or actual_python != python_path
        or not python_path.is_absolute()
        or _sha256_file(actual_python) != seed.get("runtime_python_sha256")
        or not _HEX64.fullmatch(str(seed.get("command_sha256") or ""))
        or not _HEX64.fullmatch(str(seed.get("resident_env_sha256") or ""))
    ):
        raise CliError(
            "runtime_launch_attestation_mismatch",
            "listener recovery seed does not match the running process",
        )
    _consume_recovery_seed_once(seed, consumption_root)
    return seed


__all__ = ["LISTENER_RECOVERY_SEED_SCHEMA", "require_listener_recovery_seed"]
