"""Repair lock helpers for serialized cloud repair mutation."""

from __future__ import annotations

import os
import shlex
import socket
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping

from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json, load_json
from arnold_pipelines.megaplan.custody.contracts import normalize_repair_occurrence_key

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
    repair_identity: Mapping[str, Any] | None = None,
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
    normalized_repair_identity = normalize_repair_occurrence_key(repair_identity)
    if normalized_repair_identity is not None:
        metadata["repair_identity"] = normalized_repair_identity.to_dict()
        metadata["repair_identity_key"] = normalized_repair_identity.key
    if extra:
        metadata.update(dict(extra))
    return metadata


def inspect_repair_lock(
    lock_dir: str | Path,
    *,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
    expected_repair_identity: Mapping[str, Any] | None = None,
) -> RepairLockResult:
    """Inspect an existing repair lock without mutating it."""

    lock_path = Path(lock_dir)
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
    pid_probe = is_pid_live or _default_is_pid_live
    normalized_expected_identity = normalize_repair_occurrence_key(expected_repair_identity)
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
            elif not _pid_matches_expected_repair_loop(owner, pid):
                evidence["reasons"].append("owner_process_mismatch")
                observed_command = _pid_command_text(pid)
                if observed_command:
                    evidence["observed_command"] = observed_command
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
        if normalized_expected_identity is not None:
            owner_identity = normalize_repair_occurrence_key(owner.get("repair_identity"))
            owner_identity_key = (
                owner_identity.key
                if owner_identity is not None
                else str(owner.get("repair_identity_key") or "")
            )
            if owner_identity_key != normalized_expected_identity.key:
                evidence["reasons"].append("repair_identity_mismatch")
                evidence["expected_repair_identity_key"] = normalized_expected_identity.key
                evidence["observed_repair_identity_key"] = owner_identity_key

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
    repair_identity: Mapping[str, Any] | None = None,
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
        repair_identity=repair_identity,
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
        return inspect_repair_lock(
            lock_path,
            now=now,
            is_pid_live=is_pid_live,
            expected_repair_identity=repair_identity,
        )

    try:
        # Owner equality is the release fence.  Additive provenance belongs on
        # the surrounding repair record, not inside this identity token.
        atomic_write_json(
            owner_metadata_path(lock_path),
            owner,
            include_resident_provenance=False,
        )
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
    repair_identity: Mapping[str, Any] | None = None,
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
        repair_identity=repair_identity,
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
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _pid_matches_expected_repair_loop(owner: Mapping[str, Any], pid: int) -> bool:
    session = str(owner.get("session") or "").strip()
    owner_command = str(owner.get("command") or "").strip()
    if not session or not owner_command:
        return True
    try:
        owner_args = shlex.split(owner_command)
    except ValueError:
        owner_args = owner_command.split()
    if not _args_match_repair_loop_session(owner_args, session):
        return True
    live_args = _pid_command_args(pid)
    if not live_args:
        return True
    return _args_match_repair_loop_session(live_args, session)


def _pid_command_args(pid: int) -> list[str]:
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except OSError:
        raw = b""
    if raw:
        return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
    proc = subprocess.run(
        ["ps", "-ww", "-o", "args=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _pid_command_text(pid: int) -> str:
    return " ".join(_pid_command_args(pid))


def _args_match_repair_loop_session(args: list[str], session: str) -> bool:
    def match_at(idx: int) -> bool:
        if idx >= len(args):
            return False
        if Path(args[idx]).name != "arnold-repair-loop":
            return False
        return idx + 1 < len(args) and args[idx + 1] == session

    for idx in range(len(args)):
        if match_at(idx):
            return True
        if Path(args[idx]).name in {"bash", "sh"} and match_at(idx + 1):
            return True
    return False


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
