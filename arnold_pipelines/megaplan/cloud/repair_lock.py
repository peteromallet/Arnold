"""Repair lock helpers for serialized cloud repair mutation."""

from __future__ import annotations

import os
import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping

from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json, load_json

RepairLockStatus = Literal["missing", "acquired", "busy", "stale"]
PidLivenessProbe = Callable[[int], bool]


@dataclass(frozen=True)
class RepairLockResult:
    status: RepairLockStatus
    lock_dir: Path
    owner: dict[str, Any] | None = None
    stale_evidence: dict[str, Any] | None = None

    @property
    def acquired(self) -> bool:
        return self.status == "acquired"

    @property
    def busy(self) -> bool:
        return self.status == "busy"

    @property
    def stale(self) -> bool:
        return self.status == "stale"


def owner_metadata_path(lock_dir: str | Path) -> Path:
    """Return the canonical owner metadata path for *lock_dir*."""

    return Path(lock_dir) / "owner.json"


def build_owner_metadata(
    *,
    session: str,
    target_id: str = "",
    pid: int | None = None,
    command: str | None = None,
    started_at: str | None = None,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    hostname: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build normalized owner metadata for a repair lock holder."""

    metadata: dict[str, Any] = {
        "session": session,
        "target_id": target_id,
        "pid": os.getpid() if pid is None else int(pid),
        "command": _default_command() if command is None else command,
        "started_at": _utc_now() if started_at is None else started_at,
        "cwd": os.getcwd() if cwd is None else cwd,
        "timeout_seconds": timeout_seconds,
        "hostname": _default_hostname() if hostname is None else hostname,
    }
    if extra:
        metadata.update(dict(extra))
    return metadata


def inspect_repair_lock(
    lock_dir: str | Path,
    *,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> RepairLockResult:
    """Inspect an existing repair lock without mutating it."""

    lock_path = Path(lock_dir)
    pid_probe = is_pid_live or _default_is_pid_live
    if not lock_path.exists():
        return RepairLockResult(status="missing", lock_dir=lock_path)

    owner_path = owner_metadata_path(lock_path)
    owner_payload = load_json(owner_path, default="__missing__")
    evidence: dict[str, Any] = {
        "lock_dir": str(lock_path),
        "owner_path": str(owner_path),
        "reasons": [],
    }

    if not lock_path.is_dir():
        evidence["reasons"].append("lock_path_not_directory")

    owner: dict[str, Any] | None = owner_payload if isinstance(owner_payload, dict) else None
    if owner is None:
        if owner_path.exists():
            evidence["reasons"].append("owner_metadata_invalid")
        else:
            evidence["reasons"].append("owner_metadata_missing")
    else:
        evidence["owner"] = owner
        pid = owner.get("pid")
        if isinstance(pid, int):
            if not pid_probe(pid):
                evidence["reasons"].append("owner_pid_not_live")
        else:
            evidence["reasons"].append("owner_pid_missing")

        timeout_seconds = owner.get("timeout_seconds")
        started_at = _parse_datetime(owner.get("started_at"))
        if timeout_seconds is not None:
            if not isinstance(timeout_seconds, (int, float)) or timeout_seconds < 0:
                evidence["reasons"].append("timeout_invalid")
            elif started_at is None:
                evidence["reasons"].append("started_at_invalid")
            else:
                current_time = now or datetime.now(timezone.utc)
                age_seconds = (current_time - started_at).total_seconds()
                evidence["age_seconds"] = age_seconds
                if age_seconds > float(timeout_seconds):
                    evidence["reasons"].append("timeout_expired")

    if evidence["reasons"]:
        return RepairLockResult(
            status="stale",
            lock_dir=lock_path,
            owner=owner,
            stale_evidence=evidence,
        )

    return RepairLockResult(status="busy", lock_dir=lock_path, owner=owner)


def acquire_repair_lock(
    lock_dir: str | Path,
    *,
    session: str,
    target_id: str = "",
    pid: int | None = None,
    command: str | None = None,
    started_at: str | None = None,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    hostname: str | None = None,
    extra: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> RepairLockResult:
    """Attempt to acquire a repair lock using atomic ``mkdir`` semantics."""

    lock_path = Path(lock_dir)
    owner = build_owner_metadata(
        session=session,
        target_id=target_id,
        pid=pid,
        command=command,
        started_at=started_at,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        hostname=hostname,
        extra=extra,
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_path.mkdir(parents=False)
    except FileExistsError:
        return inspect_repair_lock(lock_path, now=now, is_pid_live=is_pid_live)

    try:
        atomic_write_json(owner_metadata_path(lock_path), owner)
    except Exception:
        try:
            lock_path.rmdir()
        except OSError:
            pass
        raise

    return RepairLockResult(status="acquired", lock_dir=lock_path, owner=owner)


def release_repair_lock(
    lock_dir: str | Path,
    *,
    owner: Mapping[str, Any] | None = None,
    expected_pid: int | None = None,
) -> bool:
    """Release a repair lock if the current owner matches the expectation."""

    lock_path = Path(lock_dir)
    if not lock_path.exists():
        return False

    owner_path = owner_metadata_path(lock_path)
    current_owner = load_json(owner_path, default="__missing__")
    if owner is not None and current_owner != dict(owner):
        return False
    if expected_pid is not None:
        if not isinstance(current_owner, dict) or current_owner.get("pid") != expected_pid:
            return False

    if owner_path.exists():
        owner_path.unlink()
    try:
        lock_path.rmdir()
    except OSError:
        return False
    return True


@contextmanager
def repair_lock(
    lock_dir: str | Path,
    *,
    session: str,
    target_id: str = "",
    pid: int | None = None,
    command: str | None = None,
    started_at: str | None = None,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    hostname: str | None = None,
    extra: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> Iterator[RepairLockResult]:
    """Context-manager wrapper around :func:`acquire_repair_lock`."""

    result = acquire_repair_lock(
        lock_dir,
        session=session,
        target_id=target_id,
        pid=pid,
        command=command,
        started_at=started_at,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        hostname=hostname,
        extra=extra,
        now=now,
        is_pid_live=is_pid_live,
    )
    try:
        yield result
    finally:
        if result.acquired:
            release_repair_lock(lock_dir, owner=result.owner)


def _default_command() -> str:
    return " ".join(sys.argv)


def _default_hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return ""


def _default_is_pid_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "RepairLockResult",
    "acquire_repair_lock",
    "build_owner_metadata",
    "inspect_repair_lock",
    "owner_metadata_path",
    "release_repair_lock",
    "repair_lock",
]
