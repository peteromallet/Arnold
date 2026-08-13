"""Repair lock helpers for serialized cloud repair mutation.

The mkdir/PID lock provides **admission and projection evidence only** —
it serialises concurrent repair attempts and records who is attempting
the repair, but it does **not** confer authority to release, renew, or
perform any repair action.  Authoritative decisions require a current
Custody lease from the lease store (see
:mod:`arnold_pipelines.megaplan.custody.lease_store`).

Callers:
  - Use :func:`acquire_repair_lock` / :func:`inspect_repair_lock` for
    admission gating and projection evidence.
  - Use :func:`validate_lease_authority` to confirm lease-store ownership
    before performing any mutating repair action.
  - Use :func:`release_repair_lock` with ``lease_store`` + ``lease_id``
    for an authoritative release, or without them for a best-effort
    admission cleanup.
  - Use :func:`renew_repair_lock` (which always requires lease-store
    ownership) to extend a lock's expiry.

The **fenced durable job state machine** (Phase 3A fixer unification) lives
alongside the mkdir/PID lease and supersedes bare-lease coordination for
repair jobs: ``pending → running → committing → redriving → done`` with a
**dedupe key** (chain UUID + failure fingerprint), a **monotonically
increasing fencing epoch** (a holder with an older epoch cannot act),
acknowledge-only-after-redrive, per-attempt isolated edits, and
quarantine/reconcile of dirty attempts on crash rather than blind re-run.
A paused holder past TTL cannot resume into a newer epoch.  See
:func:`acquire_job_lock`, :func:`advance_job_state`,
:func:`acknowledge_job`, and :func:`reconcile_jobs`.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import socket
import subprocess
import sys
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms (see _job_record_flock)
    _fcntl = None  # type: ignore[assignment]
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping, cast

from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json, load_json

RepairLockStatus = Literal[
    "missing",
    "acquired",
    "busy",
    "stale",
    "unknown",
    "unauthorized",
]
PidLivenessProbe = Callable[[int], bool | None]


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

    @property
    def unknown(self) -> bool:
        return self.status == "unknown"

    @property
    def unauthorized(self) -> bool:
        return self.status == "unauthorized"


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
    boot_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build normalized owner metadata for a repair lock holder.

    *boot_id* carries the host/process-birth identity (machine boot time /
    kernel identifier) so that PID reuse across reboots cannot spoof a live
    lock holder (Step 13A).  When omitted it falls back to the current
    process-birth identity reported by :func:`process_birth_identity`.
    """

    owner_pid = os.getpid() if pid is None else int(pid)
    metadata: dict[str, Any] = {
        "session": session,
        "target_id": target_id,
        "pid": owner_pid,
        "command": _default_command() if command is None else command,
        "started_at": _utc_now() if started_at is None else started_at,
        "cwd": os.getcwd() if cwd is None else cwd,
        "timeout_seconds": timeout_seconds,
        "hostname": _default_hostname() if hostname is None else hostname,
    }
    if repair_identity is not None:
        from arnold_pipelines.megaplan.cloud import repair_requests

        normalized_identity = repair_requests.normalize_repair_identity(
            repair_identity
        )
        if normalized_identity is not None:
            metadata["repair_identity"] = normalized_identity
            metadata["repair_identity_key"] = (
                repair_requests.repair_identity_key(normalized_identity)
            )
    if boot_id is None:
        try:
            from arnold_pipelines.megaplan.custody.contracts import (
                process_birth_identity,
            )

            boot_id = str(process_birth_identity().get("boot_id") or "")
        except Exception:
            boot_id = ""
    metadata["boot_id"] = boot_id or ""
    if extra:
        metadata.update(dict(extra))
    # Reserved owner-incarnation fields are computed last so additive caller
    # metadata cannot spoof the release fence.
    metadata.update(process_owner_identity(owner_pid))
    return metadata


def process_owner_identity(pid: int) -> dict[str, Any]:
    """Return the namespace/process-birth fence for one locally visible PID."""

    return {
        "pid": int(pid),
        "pid_namespace": _pid_namespace(int(pid)) or _pid_namespace(os.getpid()),
        "process_start_ticks": _process_start_ticks(int(pid)),
    }


def inspect_repair_lock(
    lock_dir: str | Path,
    *,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
    expected_repair_identity: Mapping[str, Any] | None = None,
) -> RepairLockResult:
    """Inspect an existing repair lock without mutating it.

    The returned status (``stale``, ``busy``, etc.) is **advisory
    admission/projection evidence only**.  It does not confer authority
    to release, renew, or perform any repair action.  Callers must
    validate lease-store ownership separately via
    :func:`validate_lease_authority` before acting on inspection results.
    """

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
    pid_liveness_unknown = False
    owner_pid_liveness: bool | None = None
    expected_identity_key = ""
    if expected_repair_identity is not None:
        from arnold_pipelines.megaplan.cloud import repair_requests

        expected_identity_key = repair_requests.repair_identity_key(
            expected_repair_identity
        )
    if owner is None:
        pid_liveness_unknown = True
        if owner_path.exists():
            evidence["reasons"].append("owner_metadata_invalid")
        else:
            evidence["reasons"].append("owner_metadata_missing")
    else:
        evidence["owner"] = owner
        pid = owner.get("pid")
        if isinstance(pid, int):
            owner_pid_liveness = _owner_pid_liveness(owner, pid_probe)
            if owner_pid_liveness is None:
                pid_liveness_unknown = True
                evidence["reasons"].append("owner_pid_liveness_unknown")
            elif not owner_pid_liveness:
                evidence["reasons"].append("owner_pid_not_live")
            elif (
                Path(f"/proc/{pid}").exists()
                and not _pid_matches_expected_babysitter(owner, pid)
            ):
                evidence["reasons"].append("owner_process_mismatch")
                observed_command = _pid_command_text(pid)
                if observed_command:
                    evidence["observed_command"] = observed_command
        else:
            pid_liveness_unknown = True
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
        if expected_identity_key:
            observed_identity_key = str(
                owner.get("repair_identity_key") or ""
            )
            if observed_identity_key != expected_identity_key:
                evidence["reasons"].append("repair_identity_mismatch")
                evidence["expected_repair_identity_key"] = (
                    expected_identity_key
                )
                evidence["observed_repair_identity_key"] = (
                    observed_identity_key
                )

    # Projection-only hints such as age or identity mismatch cannot authorize a
    # stale reclaim when the owner's process cannot be observed in this PID
    # namespace.  UNKNOWN must fail closed and preserve the existing owner.
    if pid_liveness_unknown:
        return RepairLockResult(
            status="unknown",
            lock_dir=lock_path,
            owner=owner,
            stale_evidence=evidence,
        )

    # A live, incarnation-matched owner remains the owner.  Expired wall-clock
    # metadata and a caller's different expected identity are diagnostics, not
    # authority to create a concurrent repair.
    if owner_pid_liveness is True and evidence["reasons"]:
        return RepairLockResult(
            status="busy",
            lock_dir=lock_path,
            owner=owner,
            stale_evidence=evidence,
        )

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
    boot_id: str | None = None,
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
        boot_id=boot_id,
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
    lease_store: Any | None = None,
    lease_id: str = "",
) -> bool:
    """Release a repair lock if the current owner matches the expectation.

    When *lease_store* and *lease_id* are both provided the release is
    **authoritative**: the lease store must confirm current ownership by
    the same host and PID that appear in the lock's owner metadata.
    Without a lease store the release is a best-effort, same-PID-namespace
    admission cleanup only.  Foreign or legacy-unbound owners fail closed.

    Returns ``True`` if the lock was released, ``False`` otherwise.
    """

    lock_path = Path(lock_dir)
    if not lock_path.exists():
        return False

    owner_path = owner_metadata_path(lock_path)
    current_owner_raw = load_json(owner_path, default="__missing__")
    current_owner: dict[str, Any] | None = (
        current_owner_raw if isinstance(current_owner_raw, dict) else None
    )

    if owner is not None and current_owner != dict(owner):
        return False
    if expected_pid is not None:
        if current_owner is None or current_owner.get("pid") != expected_pid:
            return False

    owner_namespace = str((current_owner or {}).get("pid_namespace") or "")
    observer_namespace = _pid_namespace(os.getpid())
    same_pid_namespace = bool(
        owner_namespace and observer_namespace and owner_namespace == observer_namespace
    )

    # ── Lease-store authority check (M7) ──────────────────────────────
    if lease_store is not None and lease_id:
        if not _validate_lease_authority_inner(lease_store, lease_id, current_owner):
            return False
    elif not same_pid_namespace:
        # Exact owner JSON is a race fence, not an authority capability: every
        # observer of the shared filesystem can read and replay it.
        return False

    if owner_path.exists():
        owner_path.unlink()
    try:
        lock_path.rmdir()
    except OSError:
        return False
    return True


def validate_lease_authority(
    lease_store: Any,
    lease_id: str,
    lock_owner: Mapping[str, Any] | None,
) -> tuple[bool, dict[str, Any]]:
    """Confirm that *lease_store* records current ownership for *lease_id*
    matching the lock-owner identity from *lock_owner*.

    Returns ``(authorized, diagnostics)`` where *authorized* is ``True``
    only when the lease store contains a non-expired lease whose complete
    process incarnation (host, PID, boot, PID namespace, and process-start
    identity) matches the lock's owner metadata.

    This is the **authoritative** ownership check.  PID liveness alone
    (from :func:`inspect_repair_lock`) is admission evidence, not authority.
    """
    if lease_store is None or not lease_id:
        return False, {"reason": "missing_lease_store_or_lease_id"}
    if not isinstance(lock_owner, Mapping):
        return False, {"reason": "missing_lock_owner_metadata"}

    diagnostics: dict[str, Any] = {"lease_id": lease_id}

    try:
        lease = lease_store.current_lease(lease_id)
    except Exception as exc:
        diagnostics["reason"] = "lease_store_read_error"
        diagnostics["error"] = str(exc)
        return False, diagnostics

    if lease is None:
        diagnostics["reason"] = "no_lease_found"
        return False, diagnostics

    # Check expiry
    if lease.is_expired:
        diagnostics["reason"] = "lease_expired"
        diagnostics["lease_owner_host"] = lease.owner_host
        diagnostics["lease_owner_pid"] = lease.owner_pid
        return False, diagnostics

    lock_host = str(lock_owner.get("hostname") or "")
    lock_pid = str(lock_owner.get("pid") or "")
    lock_boot_id = str(lock_owner.get("boot_id") or "")
    lock_pid_namespace = str(lock_owner.get("pid_namespace") or "")
    lock_process_start = str(lock_owner.get("process_start_ticks") or "")

    diagnostics["lease_owner_host"] = lease.owner_host
    diagnostics["lease_owner_pid"] = lease.owner_pid
    diagnostics["lease_owner_boot_id"] = lease.owner_boot_id
    diagnostics["lock_host"] = lock_host
    diagnostics["lock_pid"] = lock_pid
    diagnostics["lock_boot_id"] = lock_boot_id
    diagnostics["lock_pid_namespace"] = lock_pid_namespace
    diagnostics["lock_process_start_ticks"] = lock_process_start

    if lease.owner_host != lock_host:
        diagnostics["reason"] = "owner_host_mismatch"
        return False, diagnostics

    if lease.owner_pid != lock_pid:
        diagnostics["reason"] = "owner_pid_mismatch"
        return False, diagnostics

    if not lease.owner_boot_id or not lock_boot_id:
        diagnostics["reason"] = "owner_boot_identity_missing"
        return False, diagnostics
    if lease.owner_boot_id != lock_boot_id:
        diagnostics["reason"] = "owner_boot_id_mismatch"
        return False, diagnostics
    if not lock_pid_namespace or not lock_process_start:
        diagnostics["reason"] = "lock_process_incarnation_missing"
        return False, diagnostics

    try:
        history = lease_store.load_history(lease_id)
    except Exception as exc:
        diagnostics["reason"] = "lease_process_incarnation_unavailable"
        diagnostics["error"] = str(exc)
        return False, diagnostics
    latest = history[-1] if history else None
    payload = getattr(latest, "payload", None)
    if not isinstance(payload, Mapping):
        diagnostics["reason"] = "lease_process_incarnation_missing"
        return False, diagnostics
    lease_pid_namespace = str(payload.get("owner_pid_namespace") or "")
    lease_process_start = str(payload.get("owner_process_start_ticks") or "")
    diagnostics["lease_pid_namespace"] = lease_pid_namespace
    diagnostics["lease_process_start_ticks"] = lease_process_start
    if not lease_pid_namespace or not lease_process_start:
        diagnostics["reason"] = "lease_process_incarnation_missing"
        return False, diagnostics
    if lease_pid_namespace != lock_pid_namespace:
        diagnostics["reason"] = "owner_pid_namespace_mismatch"
        return False, diagnostics
    if lease_process_start != lock_process_start:
        diagnostics["reason"] = "owner_process_start_mismatch"
        return False, diagnostics

    diagnostics["reason"] = "authorized"
    diagnostics["custody_epoch"] = lease.custody_epoch
    diagnostics["expires_at"] = lease.expires_at
    return True, diagnostics


def _validate_lease_authority_inner(
    lease_store: Any,
    lease_id: str,
    lock_owner: dict[str, Any] | None,
) -> bool:
    """Internal wrapper — returns a simple bool for release_repair_lock."""
    authorized, _diag = validate_lease_authority(lease_store, lease_id, lock_owner)
    return authorized


def renew_repair_lock(
    lock_dir: str | Path,
    lease_store: Any,
    lease_id: str,
    *,
    timeout_seconds: float | None = None,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> RepairLockResult:
    """Renew (extend the expiry of) a repair lock with lease-store authority.

    The lease store **must** confirm current ownership before the renewal
    is allowed.  The lock directory is not mutated — only the owner
    metadata's ``timeout_seconds`` and ``renewed_at`` fields are updated.

    Returns a :class:`RepairLockResult` with status ``"acquired"`` on
    success, ``"unauthorized"`` when the lease store does not confirm
    ownership, or ``"stale"`` / ``"busy"`` / ``"missing"`` as appropriate.
    """
    lock_path = Path(lock_dir)

    # First inspect the current lock state (admission evidence)
    inspection = inspect_repair_lock(lock_path, now=now, is_pid_live=is_pid_live)

    if inspection.status == "missing":
        return inspection

    if inspection.status not in {"busy", "stale", "unknown"}:
        return inspection

    if inspection.owner is None:
        return RepairLockResult(
            status="unauthorized",
            lock_dir=lock_path,
            owner=None,
            stale_evidence={
                "lock_dir": str(lock_path),
                "reasons": ["no_owner_metadata_for_renewal"],
            },
        )

    # ── Lease-store authority check ──────────────────────────────────
    authorized, diagnostics = validate_lease_authority(
        lease_store, lease_id, inspection.owner
    )
    if not authorized:
        return RepairLockResult(
            status="unauthorized",
            lock_dir=lock_path,
            owner=inspection.owner,
            stale_evidence={
                "lock_dir": str(lock_path),
                "reasons": [f"lease_authority_check_failed: {diagnostics.get('reason')}"],
                "lease_diagnostics": diagnostics,
            },
        )

    # ── Update owner metadata with new timeout ────────────────────────
    owner_path = owner_metadata_path(lock_path)
    updated_owner = dict(inspection.owner)
    updated_owner["timeout_seconds"] = timeout_seconds
    updated_owner["renewed_at"] = _utc_now()
    try:
        atomic_write_json(
            owner_path,
            updated_owner,
            include_resident_provenance=False,
        )
    except Exception:
        return RepairLockResult(
            status="unauthorized",
            lock_dir=lock_path,
            owner=inspection.owner,
            stale_evidence={
                "lock_dir": str(lock_path),
                "reasons": ["owner_metadata_write_failed"],
            },
        )

    return RepairLockResult(
        status="acquired",
        lock_dir=lock_path,
        owner=updated_owner,
    )


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


# ═══════════════════════════════════════════════════════════════════════════
# Fenced durable job state machine (Phase 3A fixer unification)
# ═══════════════════════════════════════════════════════════════════════════
#
# Coordination is a fenced, durable job state machine, not a bare lease.  A
# heartbeat lease alone permits split-brain: a paused holder can resume after
# a replacement starts, and re-enqueueing cannot make partially completed
# external effects exactly-once.  The machine is:
#
#     pending → running → committing → redriving → done
#
# with a **dedupe key** (chain UUID + failure fingerprint), a **monotonically
# increasing fencing epoch** (a holder with an older epoch cannot act),
# acknowledge-only-after-redrive, per-attempt isolated edits, and
# quarantine/reconcile of dirty attempts on crash rather than blind re-run.
# A paused holder past TTL cannot resume into the newer epoch.

JobState = Literal["pending", "running", "committing", "redriving", "done"]

#: All legal job states.
_JOB_STATES: frozenset[str] = frozenset(
    {"pending", "running", "committing", "redriving", "done"}
)

#: In-flight mutating states.  A crash leaves the record in one of these;
#: reconciliation quarantines it instead of blindly re-running it.
_JOB_DIRTY_STATES: frozenset[str] = frozenset(
    {"running", "committing", "redriving"}
)

#: Legal linear transitions.  ``pending`` is the conceptual pre-acquisition
#: state — :func:`acquire_job_lock` writes directly into ``running`` with a
#: fresh epoch; ``done`` is terminal.
_JOB_ADVANCE_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"running"}),
    "running": frozenset({"committing"}),
    "committing": frozenset({"redriving"}),
    "redriving": frozenset({"done"}),
    "done": frozenset(),
}

_JOB_RECORD_SCHEMA = "job-lock-record/v1"


@dataclass(frozen=True)
class JobLockRecord:
    """Durable fencing record for one repair job.

    One record exists per dedupe key (``chain_uuid:failure_fingerprint``).
    Each acquisition rewrites it with a monotonically increasing :attr:`epoch`
    and a fresh :attr:`attempt`; a caller whose in-memory record carries an
    epoch older than the on-disk record is fenced and may not mutate anything
    (an older epoch can never act).  ``state`` follows
    ``pending → running → committing → redriving → done``;
    :attr:`quarantine_reason` marks a dirty attempt whose holder died or went
    stale — it must be reconciled, never blindly re-run.
    """

    job_id: str
    chain_uuid: str
    failure_fingerprint: str
    state: JobState
    epoch: int
    holder_pid: int
    holder_boot_id: str
    attempt: int
    ttl_seconds: int
    created_at: str
    updated_at: str
    last_error: str = ""
    quarantine_reason: str | None = None
    acknowledged_at: str | None = None


def _job_dedupe_key(chain_uuid: str, failure_fingerprint: str) -> str:
    """Return the dedupe key binding one job to one failure occurrence."""

    return f"{chain_uuid}:{failure_fingerprint}"


def _job_record_path(
    lock_dir: str | Path,
    chain_uuid: str,
    failure_fingerprint: str,
) -> Path:
    """Return the atomic JSON record path for a dedupe key.

    The file name is a deterministic SHA-256 of the dedupe key, not the key
    itself: real failure fingerprints carry path-hostile characters (for
    example ``repair-blocker-fingerprint/v1:...``), so a literal
    ``<dedupe-key>.json`` name would nest directories and break the flat-file
    reconciliation scan.  One dedupe key always maps to exactly one flat file
    (the same pattern :func:`occurrence_scoped_lock_dir` uses for claim
    slots); the dedupe key itself is stored inside the record payload.
    """

    token = _job_dedupe_key(chain_uuid, failure_fingerprint)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return Path(lock_dir) / f"{digest}.json"


def _job_id_for_epoch(
    chain_uuid: str, failure_fingerprint: str, epoch: int
) -> str:
    """Return a deterministic job id for one (dedupe key, epoch) pair."""

    token = f"{_job_dedupe_key(chain_uuid, failure_fingerprint)}:e{epoch}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _record_to_payload(record: JobLockRecord) -> dict[str, Any]:
    """Serialize a :class:`JobLockRecord` to its canonical JSON payload."""

    return {
        "schema": _JOB_RECORD_SCHEMA,
        "job_id": record.job_id,
        "chain_uuid": record.chain_uuid,
        "failure_fingerprint": record.failure_fingerprint,
        "state": record.state,
        "epoch": record.epoch,
        "holder_pid": record.holder_pid,
        "holder_boot_id": record.holder_boot_id,
        "attempt": record.attempt,
        "ttl_seconds": record.ttl_seconds,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "last_error": record.last_error,
        "quarantine_reason": record.quarantine_reason,
        "acknowledged_at": record.acknowledged_at,
    }


def _record_from_payload(payload: Mapping[str, Any]) -> JobLockRecord | None:
    """Parse and strictly validate a record payload; ``None`` when corrupt."""

    job_id = payload.get("job_id")
    chain_uuid = payload.get("chain_uuid")
    failure_fingerprint = payload.get("failure_fingerprint")
    state = payload.get("state")
    epoch = payload.get("epoch")
    holder_pid = payload.get("holder_pid")
    holder_boot_id = payload.get("holder_boot_id")
    attempt = payload.get("attempt")
    ttl_seconds = payload.get("ttl_seconds")
    created_at = payload.get("created_at")
    updated_at = payload.get("updated_at")
    if not (
        isinstance(job_id, str)
        and job_id
        and isinstance(chain_uuid, str)
        and isinstance(failure_fingerprint, str)
        and state in _JOB_STATES
        and isinstance(epoch, int)
        and not isinstance(epoch, bool)
        and epoch > 0
        and isinstance(holder_pid, int)
        and not isinstance(holder_pid, bool)
        and holder_pid > 0
        and isinstance(holder_boot_id, str)
        and isinstance(attempt, int)
        and not isinstance(attempt, bool)
        and attempt > 0
        and isinstance(ttl_seconds, int)
        and not isinstance(ttl_seconds, bool)
        and ttl_seconds > 0
        and isinstance(created_at, str)
        and isinstance(updated_at, str)
    ):
        return None
    quarantine_reason = payload.get("quarantine_reason")
    if quarantine_reason is not None and not isinstance(quarantine_reason, str):
        return None
    acknowledged_at = payload.get("acknowledged_at")
    if acknowledged_at is not None and not isinstance(acknowledged_at, str):
        return None
    last_error = payload.get("last_error")
    if last_error is None:
        last_error = ""
    if not isinstance(last_error, str):
        return None
    return JobLockRecord(
        job_id=job_id,
        chain_uuid=chain_uuid,
        failure_fingerprint=failure_fingerprint,
        state=cast(JobState, state),
        epoch=epoch,
        holder_pid=holder_pid,
        holder_boot_id=holder_boot_id,
        attempt=attempt,
        ttl_seconds=ttl_seconds,
        created_at=created_at,
        updated_at=updated_at,
        last_error=last_error,
        quarantine_reason=quarantine_reason,
        acknowledged_at=acknowledged_at,
    )


def _load_job_record(
    lock_dir: str | Path,
    chain_uuid: str,
    failure_fingerprint: str,
) -> JobLockRecord | None:
    """Load the on-disk record for a dedupe key, or ``None`` when absent."""

    payload = load_json(
        _job_record_path(lock_dir, chain_uuid, failure_fingerprint),
        default="__missing__",
    )
    if not isinstance(payload, dict):
        return None
    return _record_from_payload(payload)


def _holder_stale_reason(
    record: JobLockRecord,
    *,
    now: datetime,
    boot_id: str,
) -> str | None:
    """Return the staleness reason for *record*, or ``None`` when it is live.

    A holder is live only while its attempt is dirty
    (``running``/``committing``/``redriving``), unquarantined, from the same
    boot generation (``holder_boot_id`` matches), its PID is live, and its
    TTL has not expired.  Anything else is stale: a paused holder past TTL, a
    dead process, or a rebooted host can never resume into a newer epoch.
    """

    if record.quarantine_reason is not None:
        return f"quarantined:{record.quarantine_reason}"
    if record.state not in _JOB_DIRTY_STATES:
        return f"state:{record.state}"
    if record.holder_boot_id != boot_id:
        return "boot_id_mismatch"
    if not _default_is_pid_live(record.holder_pid):
        return "holder_pid_not_live"
    updated_at = _parse_datetime(record.updated_at)
    if updated_at is None:
        return "updated_at_invalid"
    age_seconds = (now - updated_at).total_seconds()
    if age_seconds > float(record.ttl_seconds):
        return "ttl_expired"
    return None


@contextmanager
def _job_record_flock(path: Path) -> Iterator[None]:
    """Serialize one job-record read-modify-write with an advisory flock.

    The sidecar is ``<record>.json.lock`` (``*.json`` scans never match it).
    ``flock(LOCK_EX)`` blocks until the previous holder releases, so
    concurrent acquirers/advancers serialize their read → decide → write
    instead of racing; the payload still lands via the existing tmp+rename
    atomic write.  The sidecar is intentionally never removed — unlinking a
    lock file while another waiter blocks on the same inode lets a third
    opener create a fresh inode and split the fence.

    On hosts without ``fcntl`` (non-POSIX) this degrades to an O_EXCL
    create: contention raises immediately instead of blocking — fail-closed,
    but never silently skipped.
    """

    lock_path = Path(str(path) + ".lock")
    if _fcntl is None:  # pragma: no cover - non-POSIX fallback
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            yield
        finally:
            os.close(fd)
            try:
                os.unlink(lock_path)
            except OSError:
                pass
        return
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        try:
            yield
        finally:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
    finally:
        os.close(fd)


def decision_admission_lock_dir(queue_root: str | Path) -> Path:
    """Return the lock directory for request-scoped decision/admission flocks.

    The directory lives under the repair-queue root (beside the immutable
    ``requests/`` and ``decisions/`` record directories) so BOTH decision
    writers (:func:`arnold_pipelines.megaplan.cloud.repair_requests.write_decision`)
    and claim admission (``occurrence_join.join_exact_occurrence``) can
    derive the same per-request flock path from the queue root + request id
    alone.  Only ``*.lock`` sidecars live here; the ``*.json`` scans over
    ``requests/``/``decisions/`` never match them.
    """
    return Path(queue_root) / "decision-admission-locks"


@contextmanager
def decision_admission_lock(
    queue_root: str | Path, request_id: str
) -> Iterator[None]:
    """Serialize decision writes and claim admission for ONE repair request.

    T-0101h blocker 1: ``write_decision`` and occurrence-join claim
    admission share ONE request-scoped advisory flock, held by the join from
    its AUTHORITATIVE latest-decision check through the atomic WBC STARTED
    commit and by ``write_decision`` across its record write, so a
    superseding decision can never land between the check and the admission.

    Mirrors the per-record flock pattern of :func:`_job_record_flock`: the
    sidecar ``<sha256(request_id)>.lock`` is intentionally never removed
    (unlinking a lock file while another waiter blocks on the same inode
    lets a third opener create a fresh inode and split the fence), and on
    hosts without ``fcntl`` (non-POSIX) the O_EXCL fallback fails closed
    instead of silently skipping.  Under the occurrence-join zero-mutation
    refusal contract (T-0101h) this lock file is ALLOWED provisioning: a
    refusal may leave it behind, exactly like the occurrence flock file.
    """
    request_id = str(request_id or "").strip()
    if not request_id:
        raise ValueError("request_id is required")
    lock_dir = decision_admission_lock_dir(queue_root)
    lock_dir.mkdir(parents=True, exist_ok=True)
    token = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    lock_path = lock_dir / f"{token}.lock"
    if _fcntl is None:  # pragma: no cover - non-POSIX fallback
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            yield
        finally:
            os.close(fd)
            try:
                os.unlink(lock_path)
            except OSError:
                pass
        return
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        try:
            yield
        finally:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _record_past_ttl(record: JobLockRecord, *, now: datetime) -> bool:
    """Return ``True`` when *record* is past its TTL at *now*.

    A paused holder past TTL can never advance or acknowledge — expiry is
    the reconciler's job (quarantine + epoch bump), never a resume.  An
    unparseable ``updated_at`` is treated as expired (fail closed: a record
    whose liveness cannot be verified must not be mutated).
    """

    updated_at = _parse_datetime(record.updated_at)
    if updated_at is None:
        return True
    return (now - updated_at).total_seconds() > float(record.ttl_seconds)


def acquire_job_lock(
    chain_uuid: str,
    failure_fingerprint: str,
    *,
    lock_dir: Path,
    holder_pid: int,
    boot_id: str,
    ttl_seconds: int = 3600,
    now: datetime | None = None,
) -> JobLockRecord | None:
    """Acquire the fenced job lock for one dedupe key.

    The dedupe key is ``chain_uuid:failure_fingerprint``; only one mutator may
    hold the job at a time.  A successful acquisition returns a record in
    state ``running`` whose :attr:`epoch` is exactly the previous epoch + 1
    (monotonic fencing) and whose :attr:`attempt` is the previous attempt + 1
    (per-attempt isolated edits).

    Returns ``None`` when a live holder owns the current (newer) epoch — an
    older-epoch caller cannot act, so exactly one mutator exists per dedupe
    key.  When the existing holder is stale (past TTL, dead PID, or a
    different boot generation), the stale record is first **quarantined** in
    place (``quarantine_reason`` recorded, state preserved) and then the lock
    is re-acquired with ``epoch + 1``; a crash between the two writes leaves
    the quarantined evidence on disk for the next reconciler.
    """

    if not isinstance(chain_uuid, str) or not chain_uuid.strip():
        raise ValueError("chain_uuid is required")
    if not isinstance(failure_fingerprint, str) or not failure_fingerprint.strip():
        raise ValueError("failure_fingerprint is required")
    if (
        not isinstance(holder_pid, int)
        or isinstance(holder_pid, bool)
        or holder_pid <= 0
    ):
        raise ValueError("holder_pid must be a positive integer")
    if not isinstance(boot_id, str) or not boot_id.strip():
        raise ValueError("boot_id is required")
    if (
        not isinstance(ttl_seconds, int)
        or isinstance(ttl_seconds, bool)
        or ttl_seconds <= 0
    ):
        raise ValueError("ttl_seconds must be a positive integer")
    if now is not None and not isinstance(now, datetime):
        raise ValueError("now must be a datetime")

    current_time = now if now is not None else datetime.now(timezone.utc)
    path = _job_record_path(lock_dir, chain_uuid, failure_fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _job_record_flock(path):
        # Re-read under the exclusive flock: concurrent acquirers serialize
        # here, so exactly one sees previous=None and writes epoch 1; every
        # later acquirer observes the winner's record and is fenced.
        payload = load_json(path, default="__missing__")
        previous = _record_from_payload(payload) if isinstance(payload, dict) else None
        if previous is not None:
            stale_reason = _holder_stale_reason(
                previous, now=current_time, boot_id=boot_id
            )
            if stale_reason is None:
                # A live holder owns the current (newer) epoch.  An older-epoch
                # caller cannot act — exactly one mutator per dedupe key.
                return None
            if previous.state in _JOB_DIRTY_STATES:
                quarantined = replace(
                    previous,
                    quarantine_reason=stale_reason,
                    updated_at=current_time.isoformat(),
                    last_error=(
                        f"quarantined before re-acquire (epoch {previous.epoch} stale: "
                        f"{stale_reason})"
                    ),
                )
                atomic_write_json(
                    path,
                    _record_to_payload(quarantined),
                    include_resident_provenance=False,
                )
            previous_epoch = previous.epoch
            previous_attempt = previous.attempt
        else:
            previous_epoch = 0
            previous_attempt = 0

        epoch = previous_epoch + 1
        attempt = previous_attempt + 1
        timestamp = current_time.isoformat()
        record = JobLockRecord(
            job_id=_job_id_for_epoch(chain_uuid, failure_fingerprint, epoch),
            chain_uuid=chain_uuid,
            failure_fingerprint=failure_fingerprint,
            state="running",
            epoch=epoch,
            holder_pid=holder_pid,
            holder_boot_id=boot_id,
            attempt=attempt,
            ttl_seconds=ttl_seconds,
            created_at=timestamp,
            updated_at=timestamp,
            last_error="",
            quarantine_reason=None,
            acknowledged_at=None,
        )
        atomic_write_json(
            path,
            _record_to_payload(record),
            include_resident_provenance=False,
        )
        return record


def advance_job_state(
    record: JobLockRecord,
    target: JobState,
    *,
    lock_dir: Path,
    now: datetime | None = None,
) -> JobLockRecord | None:
    """Advance *record* one legal step through the job state machine.

    Legal linear transitions: ``running → committing → redriving → done``
    (plus ``pending → running`` for a pre-acquisition record).  Jumping
    states — for example ``running → done`` without committing and redriving
    — is rejected and returns ``None``.

    The transition is **fenced**: when the on-disk record carries an epoch
    newer than *record* (or the record was quarantined or removed), the
    caller is stale and ``None`` is returned — an older epoch can never
    mutate state.  The fence also binds **holder identity**: the on-disk
    ``holder_pid``/``holder_boot_id`` must equal *record*'s, and the record
    must not be past its TTL — a paused holder past TTL cannot advance; the
    reconciler owns expiry.
    """

    if now is not None and not isinstance(now, datetime):
        raise ValueError("now must be a datetime")
    current_time = now if now is not None else datetime.now(timezone.utc)
    path = _job_record_path(lock_dir, record.chain_uuid, record.failure_fingerprint)
    with _job_record_flock(path):
        # Re-read under the exclusive flock: the read → decide → write is
        # atomic, so two concurrent advancers of the same epoch cannot both
        # win — the loser observes the winner's state change and is rejected.
        on_disk = _load_job_record(
            lock_dir, record.chain_uuid, record.failure_fingerprint
        )
        if on_disk is None or on_disk.epoch != record.epoch:
            return None
        if on_disk.quarantine_reason is not None:
            return None
        if (
            on_disk.holder_pid != record.holder_pid
            or on_disk.holder_boot_id != record.holder_boot_id
        ):
            # Holder-identity fence: a same-epoch record held by a different
            # holder identity is not the caller's to advance.
            return None
        if _record_past_ttl(on_disk, now=current_time):
            # A paused holder past TTL cannot resume — the reconciler owns
            # expiry (quarantine + epoch bump), never a transition here.
            return None
        if target not in _JOB_ADVANCE_TRANSITIONS.get(on_disk.state, frozenset()):
            return None
        updated = replace(
            on_disk,
            state=target,
            updated_at=current_time.isoformat(),
        )
        atomic_write_json(
            path,
            _record_to_payload(updated),
            include_resident_provenance=False,
        )
        return updated


def acknowledge_job(
    record: JobLockRecord,
    *,
    lock_dir: Path,
    now: datetime | None = None,
) -> JobLockRecord:
    """Acknowledge a completed redrive, moving the job to ``done``.

    Acknowledge-after-redrive: the only legal source state is ``redriving``;
    the record moves to ``done`` and :attr:`acknowledged_at` is stamped with
    the acknowledgment timestamp.  Acknowledgment is rejected — the current
    on-disk record is returned unchanged so the caller can observe why — when
    the caller is fenced (newer epoch on disk), the job is quarantined, the
    on-disk holder identity differs from *record*'s, the record is past its
    TTL, or it is not in ``redriving``.
    """

    if now is not None and not isinstance(now, datetime):
        raise ValueError("now must be a datetime")
    current_time = now if now is not None else datetime.now(timezone.utc)
    path = _job_record_path(lock_dir, record.chain_uuid, record.failure_fingerprint)
    with _job_record_flock(path):
        # Serialized read → decide → write; see _job_record_flock.
        on_disk = _load_job_record(
            lock_dir, record.chain_uuid, record.failure_fingerprint
        )
        if on_disk is None:
            return record
        if (
            on_disk.epoch != record.epoch
            or on_disk.quarantine_reason is not None
            or on_disk.holder_pid != record.holder_pid
            or on_disk.holder_boot_id != record.holder_boot_id
            or _record_past_ttl(on_disk, now=current_time)
        ):
            # Fenced: newer epoch, quarantined, foreign holder identity, or
            # past TTL — the caller cannot acknowledge; return the current
            # record unchanged so the caller can observe why.
            return on_disk
        if on_disk.state != "redriving":
            return on_disk
        updated = replace(
            on_disk,
            state="done",
            acknowledged_at=current_time.isoformat(),
            updated_at=current_time.isoformat(),
        )
        atomic_write_json(
            path,
            _record_to_payload(updated),
            include_resident_provenance=False,
        )
        return updated


def reconcile_jobs(
    lock_dir: Path,
    *,
    boot_id: str,
    now: datetime,
) -> list[JobLockRecord]:
    """Quarantine dirty attempts after a crash instead of blindly re-running.

    Every record whose attempt is in flight (``running``/``committing``/
    ``redriving``) and whose holder is dead (PID gone), from another boot
    generation (``holder_boot_id`` mismatch), or past its TTL is marked
    **quarantined**: the state is preserved and ``quarantine_reason`` records
    why the attempt must not be resumed.  The caller decides what to do next;
    this function never re-runs a quarantined attempt.

    Returns every record present (quarantined and live) so the caller can
    reconcile the full picture.  Unreadable records are left untouched for
    the operator.
    """

    lock_path = Path(lock_dir)
    records: list[JobLockRecord] = []
    if not lock_path.is_dir():
        return records
    for path in sorted(lock_path.glob("*.json")):
        with _job_record_flock(path):
            # Per-record exclusive flock: read → decide → write is atomic, so
            # a concurrent acquirer/advancer cannot interleave between the
            # load and the quarantine write on the same record.
            payload = load_json(path, default="__missing__")
            record = (
                _record_from_payload(payload) if isinstance(payload, dict) else None
            )
            if record is None:
                # Corrupt/unreadable record — preserved for the operator, never
                # re-run or blindly overwritten by reconciliation.
                continue
            if record.quarantine_reason is not None:
                records.append(record)
                continue
            stale_reason = _holder_stale_reason(record, now=now, boot_id=boot_id)
            if stale_reason is not None and record.state in _JOB_DIRTY_STATES:
                quarantined = replace(
                    record,
                    quarantine_reason=stale_reason,
                    updated_at=now.isoformat(),
                )
                atomic_write_json(
                    path,
                    _record_to_payload(quarantined),
                    include_resident_provenance=False,
                )
                records.append(quarantined)
            else:
                records.append(record)
    return records


def job_is_quarantined(record: JobLockRecord) -> bool:
    """Return ``True`` when *record* is quarantined (its holder went stale)."""

    return record.quarantine_reason is not None


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


def _pid_namespace(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        return os.readlink(f"/proc/{pid}/ns/pid")
    except OSError:
        # Non-Linux development/test hosts have one host PID namespace.  This
        # fallback is intentionally unavailable for arbitrary target PIDs; the
        # caller may bind an unobservable target to its own current namespace.
        if pid == os.getpid():
            return f"host:{_default_hostname()}"
        return ""


def _process_start_ticks(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        suffix = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[1]
        # proc(5): field 22 is process start time; suffix starts at field 3.
        return suffix.split()[19]
    except (OSError, IndexError):
        try:
            started = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
            return f"ps-lstart:{started}" if started else ""
        except Exception:
            return ""


def _owner_pid_liveness(
    owner: Mapping[str, Any],
    probe: PidLivenessProbe,
) -> bool | None:
    pid = owner.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    owner_namespace = str(owner.get("pid_namespace") or "")
    observer_namespace = _pid_namespace(os.getpid())
    if not owner_namespace or not observer_namespace or owner_namespace != observer_namespace:
        return None
    observed = probe(pid)
    if observed is not True:
        return observed
    expected_start = str(owner.get("process_start_ticks") or "")
    if expected_start:
        observed_start = _process_start_ticks(pid)
        if not observed_start:
            return None
        if observed_start != expected_start:
            return False
    return True


def _pid_matches_expected_babysitter(owner: Mapping[str, Any], pid: int) -> bool:
    session = str(owner.get("session") or "").strip()
    owner_command = str(owner.get("command") or "").strip()
    if not session or not owner_command:
        return True
    try:
        owner_args = shlex.split(owner_command)
    except ValueError:
        owner_args = owner_command.split()
    if not _args_match_babysitter_session(owner_args, session):
        return True
    live_args = _pid_command_args(pid)
    if not live_args:
        return True
    return _args_match_babysitter_session(live_args, session)


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


def _args_match_babysitter_session(args: list[str], session: str) -> bool:
    def match_at(idx: int) -> bool:
        if idx >= len(args):
            return False
        if Path(args[idx]).name != "arnold-babysitter":
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


def occurrence_scoped_lock_dir(
    claims_dir: str | Path,
    occurrence_fingerprint: str,
) -> Path:
    """Return the lock directory for an exact-occurrence claim.

    The directory is keyed by the deterministic occurrence fingerprint so
    that two distinct occurrences of the same logical blocker cannot share
    a claim slot — only one exact occurrence may be actively claimed at a
    time.  The fingerprint MUST come from the canonical occurrence tuple
    (the F01 repair-occurrence fields); it MUST NOT be derived from a
    label, liveness signal, WBC receipt, or rebuildable projection, since
    none of those uniquely and exactly identify a repair occurrence.
    """

    if not isinstance(occurrence_fingerprint, str) or not occurrence_fingerprint.strip():
        raise ValueError("occurrence_fingerprint is required")
    token = hashlib.sha256(occurrence_fingerprint.encode("utf-8")).hexdigest()
    return Path(claims_dir) / f"{token}.lock"


# ═══════════════════════════════════════════════════════════════════════════
# Canonical claim alias index + cross-namespace fence (T-0204)
# ═══════════════════════════════════════════════════════════════════════════
#
# Two claim namespaces live under one repair queue root:
#
#   * **active claims** — blocker-keyed (``active-claims/<sha256(blocker)>.lock``,
#     :func:`arnold_pipelines.megaplan.cloud.repair_requests.active_repair_claim_lock_dir`);
#   * **occurrence claims** — occurrence-fingerprint-keyed
#     (``occurrence-claims/<sha256(fingerprint)>.lock``,
#     :func:`arnold_pipelines.megaplan.cloud.simple_fixer.claim_singleton_occurrence`).
#
# They must converge on ONE owner for one repair, so each namespace consults
# the OTHER **before** acquiring its own lock, through ONE canonical alias
# index (:func:`claim_alias_index_dir`) plus the current fencing fence
# (``(custody_epoch, fence_token)`` from the normalized repair identity).
# The index deterministically maps ``blocker_id <-> occurrence_fingerprint``
# and records the newest fence seen; liveness is always re-derived from the
# live lock directories, never trusted from the index alone.  A live foreign
# owner in the other namespace is ``busy`` (never displaced); a STALE foreign
# claim may be reclaimed ONLY with a newer fence, and the reclaim re-acquires
# the other namespace's lock under the caller's own owner so both namespaces
# converge on one owner (no double launch).  The alias files are advisory and
# intentionally never removed: a lingering mapping is harmless because every
# decision re-inspects the live lock directories, and removing it while the
# other namespace still holds a live claim would hide that claim.

CLAIM_ALIAS_SCHEMA = "claim-alias/v1"
ClaimNamespace = Literal["active", "occurrence"]
CLAIM_NAMESPACES: frozenset[str] = frozenset({"active", "occurrence"})


@dataclass(frozen=True)
class ClaimAliasRecord:
    """One canonical alias record binding blocker and occurrence namespaces.

    The SAME record is written under both deterministic keys (blocker id and
    occurrence fingerprint) inside :func:`claim_alias_index_dir`.  It is the
    canonical mapping through which one namespace finds the other: the
    occurrence side resolves its blocker, the active side resolves the
    occurrence claims mapped to its blocker.  ``fence_epoch`` /
    ``fence_token`` carry the newest fencing fence observed, so a stale
    reclaim requires a strictly newer fence than any record claims.
    """

    occurrence_fingerprint: str
    request_id: str
    repair_identity_key: str
    fence_epoch: int
    fence_token: int
    blocker_id: str = ""
    holder_namespaces: tuple[str, ...] = ()
    updated_at: str = ""


def _alias_to_payload(record: ClaimAliasRecord) -> dict[str, Any]:
    """Serialize a :class:`ClaimAliasRecord` to its canonical JSON payload."""

    return {
        "schema": CLAIM_ALIAS_SCHEMA,
        "blocker_id": record.blocker_id,
        "occurrence_fingerprint": record.occurrence_fingerprint,
        "request_id": record.request_id,
        "repair_identity_key": record.repair_identity_key,
        "fence_epoch": record.fence_epoch,
        "fence_token": record.fence_token,
        "holder_namespaces": list(record.holder_namespaces),
        "updated_at": record.updated_at,
    }


def _alias_from_payload(payload: Mapping[str, Any]) -> ClaimAliasRecord | None:
    """Strictly validate an alias payload; ``None`` when corrupt."""

    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("schema") or "") != CLAIM_ALIAS_SCHEMA:
        return None
    occurrence_fingerprint = str(payload.get("occurrence_fingerprint") or "").strip()
    request_id = str(payload.get("request_id") or "").strip()
    repair_identity_key = str(payload.get("repair_identity_key") or "").strip()
    if not occurrence_fingerprint or not request_id or not repair_identity_key:
        return None
    fence_epoch = payload.get("fence_epoch")
    fence_token = payload.get("fence_token")
    if (
        not isinstance(fence_epoch, int)
        or isinstance(fence_epoch, bool)
        or fence_epoch < 0
    ):
        return None
    if (
        not isinstance(fence_token, int)
        or isinstance(fence_token, bool)
        or fence_token < 0
    ):
        return None
    holders = payload.get("holder_namespaces")
    holder_namespaces: tuple[str, ...] = ()
    if isinstance(holders, list):
        if not all(isinstance(item, str) and item in CLAIM_NAMESPACES for item in holders):
            return None
        holder_namespaces = tuple(holders)
    elif holders is not None:
        return None
    return ClaimAliasRecord(
        occurrence_fingerprint=occurrence_fingerprint,
        request_id=request_id,
        repair_identity_key=repair_identity_key,
        fence_epoch=fence_epoch,
        fence_token=fence_token,
        blocker_id=str(payload.get("blocker_id") or "").strip(),
        holder_namespaces=holder_namespaces,
        updated_at=str(payload.get("updated_at") or "").strip(),
    )


def claim_alias_index_dir(queue_root: str | Path) -> Path:
    """Return the canonical claim alias index directory for *queue_root*."""

    return Path(queue_root) / "claims-index"


def _claim_alias_path(queue_root: str | Path, key: str) -> Path:
    """Return the deterministic alias file path for one canonical key."""

    token = hashlib.sha256(str(key).strip().encode("utf-8")).hexdigest()
    return claim_alias_index_dir(queue_root) / f"{token}.json"


def claim_alias_record(
    queue_root: str | Path,
    *,
    blocker_id: str = "",
    occurrence_fingerprint: str = "",
) -> ClaimAliasRecord | None:
    """Read the canonical alias record for one namespace key, or ``None``.

    ``None`` means the index has no record for that key.  A present-but-
    corrupt record also yields ``None``; callers that must fail closed can
    distinguish by checking whether the alias file exists
    (:func:`claim_alias_file_exists`).
    """

    key = occurrence_fingerprint or blocker_id
    if not key:
        return None
    payload = load_json(_claim_alias_path(queue_root, key), default="__missing__")
    if not isinstance(payload, dict):
        return None
    return _alias_from_payload(payload)


def claim_alias_file_exists(
    queue_root: str | Path,
    *,
    blocker_id: str = "",
    occurrence_fingerprint: str = "",
) -> bool:
    """Return whether an alias file exists for the given key (corrupt or not)."""

    key = occurrence_fingerprint or blocker_id
    if not key:
        return False
    return _claim_alias_path(queue_root, key).exists()


def write_claim_alias(
    queue_root: str | Path,
    record: ClaimAliasRecord,
    *,
    updated_at: str | None = None,
) -> ClaimAliasRecord:
    """Write the canonical alias record under BOTH deterministic keys.

    The pair is written under one directory-level flock so concurrent
    claimers serialize their blocker/fingerprint alias pair instead of
    interleaving two half-pairs.  Each file is individually atomic
    (tmp+rename).  The blocker-keyed file is written only when
    ``blocker_id`` is known — an occurrence-side claim that has not yet
    resolved its blocker writes only the fingerprint key, which the
    active side completes on its next claim.
    """

    queue_root_path = Path(queue_root)
    index_dir = claim_alias_index_dir(queue_root_path)
    index_dir.mkdir(parents=True, exist_ok=True)
    stamp = updated_at or _utc_now()
    record = ClaimAliasRecord(
        occurrence_fingerprint=record.occurrence_fingerprint,
        request_id=record.request_id,
        repair_identity_key=record.repair_identity_key,
        fence_epoch=record.fence_epoch,
        fence_token=record.fence_token,
        blocker_id=record.blocker_id,
        holder_namespaces=tuple(
            ns for ns in record.holder_namespaces if ns in CLAIM_NAMESPACES
        ),
        updated_at=stamp,
    )
    payload = _alias_to_payload(record)
    paths = [_claim_alias_path(queue_root_path, record.occurrence_fingerprint)]
    if record.blocker_id:
        paths.append(_claim_alias_path(queue_root_path, record.blocker_id))
    with _job_record_flock(index_dir / "index.lock"):
        for path in sorted(paths):
            atomic_write_json(
                path,
                payload,
                include_resident_provenance=False,
            )
    return record


def _aliases_for_blocker(
    queue_root: str | Path,
    blocker_id: str,
) -> list[ClaimAliasRecord]:
    """Return every valid alias record mapped to *blocker_id*.

    The blocker-keyed alias file holds only the most recent record; a scan
    of the whole index catches OLDER occurrence claims for the same blocker
    that are still live, so the active side can refuse foreign owners that
    the single blocker-keyed file would miss.
    """

    index_dir = claim_alias_index_dir(queue_root)
    records: list[ClaimAliasRecord] = []
    seen: set[str] = set()
    if not index_dir.is_dir():
        return records
    for path in sorted(index_dir.glob("*.json")):
        payload = load_json(path, default="__missing__")
        if not isinstance(payload, dict):
            continue
        record = _alias_from_payload(payload)
        if record is None:
            continue
        if record.blocker_id != blocker_id:
            continue
        if record.occurrence_fingerprint in seen:
            continue
        seen.add(record.occurrence_fingerprint)
        records.append(record)
    return records


def blocker_id_for_occurrence(
    queue_root: str | Path,
    occurrence_fingerprint: str,
) -> str:
    """Resolve the canonical blocker id for one occurrence fingerprint.

    The alias index is the fast path; the immutable request records are the
    authoritative source (every claimable occurrence has an enqueued request
    carrying the same ``repair_identity_key`` and its ``blocker_id``), so a
    missing/stale alias can never hide an active claim behind an unresolvable
    blocker.  Returns ``""`` when nothing binds the occurrence to a blocker.
    """

    record = claim_alias_record(
        queue_root, occurrence_fingerprint=occurrence_fingerprint
    )
    if record is not None and record.blocker_id:
        return record.blocker_id
    from arnold_pipelines.megaplan.cloud.repair_requests import iter_repair_requests

    for request in iter_repair_requests(queue_root):
        if str(request.get("repair_identity_key") or "") != occurrence_fingerprint:
            continue
        blocker_id = str(request.get("blocker_id") or "").strip()
        if blocker_id:
            return blocker_id
    return ""


def claim_fence(repair_identity: Mapping[str, Any] | None) -> tuple[int, int]:
    """Return the ``(custody_epoch, fence_token)`` fence for an identity.

    The fence is the monotonic custody epoch from the normalized repair
    identity, seconded by the coordinator fence token.  ``(0, 0)`` is the
    lowest fence: an identity-less caller can never reclaim a stale claim,
    and any recorded claim fences it out.
    """

    if not isinstance(repair_identity, Mapping):
        return (0, 0)
    custody_epoch = repair_identity.get("custody_epoch")
    if (
        not isinstance(custody_epoch, int)
        or isinstance(custody_epoch, bool)
        or custody_epoch < 0
    ):
        custody_epoch = 0
    fence_token = 0
    occurrence = repair_identity.get("occurrence")
    if isinstance(occurrence, Mapping):
        try:
            token = int(occurrence.get("fence_token") or 0)
        except (TypeError, ValueError):
            token = 0
        fence_token = max(0, token)
    return (int(custody_epoch), int(fence_token))


def _fence_newer(candidate: tuple[int, int], current: tuple[int, int]) -> bool:
    """Return whether *candidate* is strictly newer than *current*."""

    return (candidate[0], candidate[1]) > (current[0], current[1])


def _owner_identity_key(owner: Mapping[str, Any] | None) -> str:
    """Return the canonical owner identity key from lock owner metadata."""

    if not isinstance(owner, Mapping):
        return ""
    return str(
        owner.get("repair_identity_key")
        or owner.get("occurrence_fingerprint")
        or ""
    ).strip()


@dataclass(frozen=True)
class CrossNamespaceConsultation:
    """Typed result of consulting the OTHER claim namespace before claiming.

    :attr:`may_proceed` is ``True`` only when acquiring the caller's own
    namespace lock cannot create a second owner for the same repair.  When
    ``False``, ``outcome`` names the reason (``busy_other_owner`` or
    ``fenced_stale_refused``) and :attr:`evidence` carries the observed
    foreign claim.  When ``True`` with ``stale_reclaim_allowed``,
    :attr:`reclaim_targets` lists the stale other-namespace claims the
    caller may reclaim (release + re-acquire under its own owner) AFTER
    acquiring its own lock.
    """

    may_proceed: bool
    outcome: str
    other_namespace: str = ""
    blocker_id: str = ""
    other_lock_dirs: tuple[Path, ...] = ()
    reclaim_targets: tuple[dict[str, Any], ...] = ()
    alias: ClaimAliasRecord | None = None
    evidence: dict[str, Any] | None = None


def consult_claim_namespace(
    queue_root: str | Path,
    *,
    own_namespace: str,
    occurrence_fingerprint: str,
    repair_identity_key: str,
    request_id: str,
    fence: tuple[int, int],
    blocker_id: str = "",
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> CrossNamespaceConsultation:
    """Consult the other claim namespace BEFORE acquiring our own lock.

    This is the ONE canonical cross-namespace check.  Rules:

    * other namespace has no live claim -> proceed (``no_other_claim``);
    * other namespace has a LIVE owner with the SAME repair identity key
      (or the same request id) -> same-owner join, proceed;
    * other namespace has a LIVE foreign owner -> ``busy_other_owner``,
      never displaced regardless of fence;
    * other namespace has a STALE claim -> reclaimable ONLY when our fence
      is strictly newer than the recorded fence
      (``stale_reclaim_allowed``); otherwise ``fenced_stale_refused``.

    A present-but-corrupt alias file fails closed (``alias_invalid``): a
    mapping we cannot read must never be silently bypassed.
    """

    if own_namespace not in CLAIM_NAMESPACES:
        raise ValueError(f"own_namespace must be one of {sorted(CLAIM_NAMESPACES)}")
    if not occurrence_fingerprint or not repair_identity_key or not request_id:
        raise ValueError(
            "cross-namespace consultation requires occurrence_fingerprint, "
            "repair_identity_key, and request_id"
        )
    queue_root_path = Path(queue_root)

    # ── Resolve the other namespace's lock directories ────────────────────
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        active_repair_claim_lock_dir,
        singleton_occurrence_claim_lock_dir,
    )

    alias = claim_alias_record(
        queue_root_path, occurrence_fingerprint=occurrence_fingerprint
    )
    # Fail closed on a present-but-corrupt mapping: an alias we cannot read
    # must never be silently bypassed (it could hide a live foreign claim).
    if (
        alias is None
        and claim_alias_file_exists(
            queue_root_path, occurrence_fingerprint=occurrence_fingerprint
        )
    ):
        return CrossNamespaceConsultation(
            may_proceed=False,
            outcome="alias_invalid",
            other_namespace="",
            blocker_id=blocker_id,
            other_lock_dirs=(),
            alias=None,
            evidence={
                "kind": "cross_namespace_claim_consultation",
                "own_namespace": own_namespace,
                "outcome": "alias_invalid",
                "reason": "fingerprint-keyed alias present but unreadable",
                "occurrence_fingerprint": occurrence_fingerprint,
                "request_id": request_id,
            },
        )
    other_namespace = "active" if own_namespace == "occurrence" else "occurrence"
    #: (occurrence_fingerprint, lock_dir) pairs — the fingerprint lets the
    #: reclaimed claim's alias be refreshed under the new owner+fence.
    other_dirs: list[tuple[str, Path]] = []
    seen_dirs: set[str] = set()
    resolved_blocker_id = blocker_id
    if own_namespace == "occurrence":
        if not resolved_blocker_id and alias is not None:
            resolved_blocker_id = alias.blocker_id
        if not resolved_blocker_id:
            resolved_blocker_id = blocker_id_for_occurrence(
                queue_root_path, occurrence_fingerprint
            )
        if alias is None and resolved_blocker_id:
            # Fall back to the blocker-keyed alias: it carries the newest
            # fence observed for this blocker even when the caller's own
            # fingerprint has never claimed.
            alias = claim_alias_record(
                queue_root_path, blocker_id=resolved_blocker_id
            )
            if (
                alias is None
                and claim_alias_file_exists(
                    queue_root_path, blocker_id=resolved_blocker_id
                )
            ):
                return CrossNamespaceConsultation(
                    may_proceed=False,
                    outcome="alias_invalid",
                    other_namespace=other_namespace,
                    blocker_id=resolved_blocker_id,
                    other_lock_dirs=(),
                    alias=None,
                    evidence={
                        "kind": "cross_namespace_claim_consultation",
                        "own_namespace": own_namespace,
                        "outcome": "alias_invalid",
                        "reason": "blocker-keyed alias present but unreadable",
                        "blocker_id": resolved_blocker_id,
                        "occurrence_fingerprint": occurrence_fingerprint,
                        "request_id": request_id,
                    },
                )
        if not resolved_blocker_id:
            # No mapping to the active namespace at all — nothing to consult.
            return CrossNamespaceConsultation(
                may_proceed=True,
                outcome="no_other_claim",
                other_namespace=other_namespace,
                blocker_id="",
                other_lock_dirs=(),
                alias=alias,
                evidence={
                    "kind": "cross_namespace_claim_consultation",
                    "own_namespace": own_namespace,
                    "outcome": "no_other_claim",
                    "reason": "no blocker mapping for occurrence",
                    "occurrence_fingerprint": occurrence_fingerprint,
                    "request_id": request_id,
                },
            )
        other_dirs = [
            (
                alias.occurrence_fingerprint if alias is not None else "",
                active_repair_claim_lock_dir(queue_root_path, resolved_blocker_id),
            )
        ]
    else:
        blocker_alias = claim_alias_record(
            queue_root_path, blocker_id=blocker_id
        )
        if (
            blocker_alias is None
            and claim_alias_file_exists(queue_root_path, blocker_id=blocker_id)
        ):
            return CrossNamespaceConsultation(
                may_proceed=False,
                outcome="alias_invalid",
                other_namespace=other_namespace,
                blocker_id=blocker_id,
                other_lock_dirs=(),
                alias=None,
                evidence={
                    "kind": "cross_namespace_claim_consultation",
                    "own_namespace": own_namespace,
                    "outcome": "alias_invalid",
                    "reason": "blocker-keyed alias present but unreadable",
                    "blocker_id": blocker_id,
                    "occurrence_fingerprint": occurrence_fingerprint,
                    "request_id": request_id,
                },
            )
        candidates = {occurrence_fingerprint}
        if blocker_alias is not None and blocker_alias.occurrence_fingerprint:
            candidates.add(blocker_alias.occurrence_fingerprint)
        for record in _aliases_for_blocker(queue_root_path, blocker_id):
            candidates.add(record.occurrence_fingerprint)
        for fingerprint in sorted(candidates):
            other_dirs.append(
                (
                    fingerprint,
                    singleton_occurrence_claim_lock_dir(queue_root_path, fingerprint),
                )
            )

    inspections: list[dict[str, Any]] = []
    busy: list[dict[str, Any]] = []
    fenced: list[dict[str, Any]] = []
    reclaim_targets: list[dict[str, Any]] = []
    same_owner_seen = False
    for fingerprint, lock_dir in other_dirs:
        if str(lock_dir) in seen_dirs:
            continue
        seen_dirs.add(str(lock_dir))
        inspection = inspect_repair_lock(
            lock_dir,
            now=now,
            is_pid_live=is_pid_live,
        )
        # The fence floor comes from the candidate's own alias record when
        # available, else the caller's fingerprint-keyed alias; the live
        # owner metadata (which carries the full normalized identity) is the
        # authoritative newest fence and always takes the maximum.
        candidate_alias = (
            alias
            if fingerprint == occurrence_fingerprint
            else claim_alias_record(
                queue_root_path, occurrence_fingerprint=fingerprint
            )
        )
        record_fence = (0, 0)
        if candidate_alias is not None:
            record_fence = (candidate_alias.fence_epoch, candidate_alias.fence_token)
        elif alias is not None:
            record_fence = (alias.fence_epoch, alias.fence_token)
        owner = inspection.owner
        if isinstance(owner, Mapping):
            owner_fence = claim_fence(owner.get("repair_identity"))
            record_fence = max(record_fence, owner_fence)
        owner_key = _owner_identity_key(owner)
        entry: dict[str, Any] = {
            "lock_dir": str(lock_dir),
            "status": inspection.status,
            "owner_identity_key": owner_key,
            "owner_request_id": str(
                (owner or {}).get("request_id") or ""
            ),
            "record_fence": list(record_fence),
        }
        if inspection.status == "missing":
            inspections.append(entry)
            continue
        if inspection.status in {"busy", "unknown"}:
            same_owner = bool(
                owner_key
                and owner_key == repair_identity_key
            ) or str((owner or {}).get("request_id") or "") == request_id
            entry["same_owner"] = same_owner
            inspections.append(entry)
            if same_owner:
                same_owner_seen = True
            else:
                busy.append(entry)
            continue
        if inspection.status == "stale":
            entry["stale_evidence"] = inspection.stale_evidence
            inspections.append(entry)
            if _fence_newer(fence, record_fence):
                reclaim_targets.append(
                    {
                        "lock_dir": lock_dir,
                        "owner": dict(owner) if isinstance(owner, Mapping) else None,
                        "occurrence_fingerprint": fingerprint,
                    }
                )
            else:
                fenced.append(entry)
            continue
        inspections.append(entry)

    evidence: dict[str, Any] = {
        "kind": "cross_namespace_claim_consultation",
        "own_namespace": own_namespace,
        "other_namespace": other_namespace,
        "outcome": "",
        "blocker_id": resolved_blocker_id,
        "occurrence_fingerprint": occurrence_fingerprint,
        "request_id": request_id,
        "repair_identity_key": repair_identity_key,
        "fence": list(fence),
        "other_lock_dirs": [str(path) for _fp, path in other_dirs],
        "inspections": inspections,
    }

    if busy:
        evidence["outcome"] = "busy_other_owner"
        evidence["busy_claims"] = busy
        return CrossNamespaceConsultation(
            may_proceed=False,
            outcome="busy_other_owner",
            other_namespace=other_namespace,
            blocker_id=resolved_blocker_id,
            other_lock_dirs=tuple(path for _fp, path in other_dirs),
            alias=alias,
            evidence=evidence,
        )
    if fenced:
        evidence["outcome"] = "fenced_stale_refused"
        evidence["fenced_claims"] = fenced
        return CrossNamespaceConsultation(
            may_proceed=False,
            outcome="fenced_stale_refused",
            other_namespace=other_namespace,
            blocker_id=resolved_blocker_id,
            other_lock_dirs=tuple(path for _fp, path in other_dirs),
            alias=alias,
            evidence=evidence,
        )
    if reclaim_targets:
        evidence["outcome"] = "stale_reclaim_allowed"
        evidence["reclaim_targets"] = [
            {"lock_dir": str(item["lock_dir"])} for item in reclaim_targets
        ]
        return CrossNamespaceConsultation(
            may_proceed=True,
            outcome="stale_reclaim_allowed",
            other_namespace=other_namespace,
            blocker_id=resolved_blocker_id,
            other_lock_dirs=tuple(path for _fp, path in other_dirs),
            reclaim_targets=tuple(reclaim_targets),
            alias=alias,
            evidence=evidence,
        )
    evidence["outcome"] = (
        "same_owner_join" if same_owner_seen else "no_other_claim"
    )
    return CrossNamespaceConsultation(
        may_proceed=True,
        outcome=evidence["outcome"],
        other_namespace=other_namespace,
        blocker_id=resolved_blocker_id,
        other_lock_dirs=tuple(path for _fp, path in other_dirs),
        alias=alias,
        evidence=evidence,
    )


def finalize_cross_namespace_claim(
    queue_root: str | Path,
    *,
    own_namespace: str,
    occurrence_fingerprint: str,
    repair_identity_key: str,
    request_id: str,
    fence: tuple[int, int],
    blocker_id: str = "",
    claim_lock_dir: Path,
    claim_owner: Mapping[str, Any],
    claim_metadata: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    is_pid_live: PidLivenessProbe | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Post-acquisition cross-namespace backstop + fenced stale reclaim.

    Called AFTER the caller acquired its own namespace lock.  Re-consults
    the other namespace to close the consult -> acquire race window: if a
    live foreign owner appeared meanwhile, returns ``(False, ...)`` and the
    caller MUST release its own claim (fail closed — no double launch).
    Stale foreign claims are reclaimed (release + re-acquire under the
    caller's own owner) so both namespaces converge on one owner; a failed
    or out-fenced reclaim also returns ``(False, ...)``.

    Returns ``(True, evidence)`` when the caller's claim may stand.
    """

    consultation = consult_claim_namespace(
        queue_root,
        own_namespace=own_namespace,
        occurrence_fingerprint=occurrence_fingerprint,
        repair_identity_key=repair_identity_key,
        request_id=request_id,
        fence=fence,
        blocker_id=blocker_id,
        now=now,
        is_pid_live=is_pid_live,
    )
    evidence: dict[str, Any] = {
        "kind": "cross_namespace_claim_backstop",
        "own_namespace": own_namespace,
        "consultation": consultation.evidence,
    }
    if not consultation.may_proceed:
        evidence["reason"] = consultation.outcome
        return False, evidence
    for target in consultation.reclaim_targets:
        lock_dir = target["lock_dir"]
        stale_owner = target.get("owner")
        stale_pid = (
            stale_owner.get("pid")
            if isinstance(stale_owner, Mapping)
            and isinstance(stale_owner.get("pid"), int)
            else None
        )
        if not release_repair_lock(
            lock_dir,
            owner=stale_owner,
            expected_pid=stale_pid,
        ):
            evidence["reason"] = "stale_reclaim_release_failed"
            evidence["lock_dir"] = str(lock_dir)
            return False, evidence
        # The reclaimed claim must carry the OTHER namespace's canonical
        # shape (kind + blocker_id / occurrence_fingerprint) so dispatcher
        # bind paths and later inspectors read it correctly, with OUR
        # request/identity/fence stamped in.
        reclaim_extra = dict(claim_metadata or {})
        if own_namespace == "occurrence":
            reclaim_extra["kind"] = "active_repair_request_claim"
            if blocker_id:
                reclaim_extra["blocker_id"] = blocker_id
        else:
            reclaim_extra["kind"] = "singleton_occurrence_claim"
            reclaim_extra["occurrence_fingerprint"] = occurrence_fingerprint
        reacquired = acquire_repair_lock(
            lock_dir,
            session=str(claim_owner.get("session") or ""),
            target_id=str(claim_owner.get("target_id") or ""),
            repair_identity=claim_owner.get("repair_identity"),
            pid=(
                claim_owner.get("pid")
                if isinstance(claim_owner.get("pid"), int)
                else None
            ),
            command=claim_owner.get("command"),
            started_at=claim_owner.get("started_at"),
            cwd=claim_owner.get("cwd"),
            timeout_seconds=claim_owner.get("timeout_seconds"),
            hostname=claim_owner.get("hostname"),
            extra=reclaim_extra,
            now=now,
            is_pid_live=is_pid_live,
        )
        if not reacquired.acquired:
            evidence["reason"] = "stale_reclaim_reacquire_failed"
            evidence["lock_dir"] = str(lock_dir)
            evidence["reacquire_status"] = reacquired.status
            return False, evidence
        evidence.setdefault("reclaimed", []).append(str(lock_dir))
        # Refresh the alias for the reclaimed claim under OUR owner and fence
        # so the canonical index records the newest fence immediately.
        reclaimed_fingerprint = str(
            target.get("occurrence_fingerprint") or ""
        ).strip()
        if reclaimed_fingerprint:
            write_claim_alias(
                queue_root,
                ClaimAliasRecord(
                    blocker_id=blocker_id,
                    occurrence_fingerprint=reclaimed_fingerprint,
                    request_id=request_id,
                    repair_identity_key=repair_identity_key,
                    fence_epoch=fence[0],
                    fence_token=fence[1],
                    holder_namespaces=(consultation.other_namespace,),
                ),
            )
    evidence["reason"] = "ok"
    return True, evidence


__all__ = [
    "CLAIM_ALIAS_SCHEMA",
    "ClaimAliasRecord",
    "ClaimNamespace",
    "CrossNamespaceConsultation",
    "JobLockRecord",
    "JobState",
    "RepairLockResult",
    "acknowledge_job",
    "acquire_job_lock",
    "acquire_repair_lock",
    "advance_job_state",
    "blocker_id_for_occurrence",
    "build_owner_metadata",
    "claim_alias_file_exists",
    "claim_alias_index_dir",
    "claim_alias_record",
    "claim_fence",
    "consult_claim_namespace",
    "decision_admission_lock",
    "decision_admission_lock_dir",
    "finalize_cross_namespace_claim",
    "inspect_repair_lock",
    "job_is_quarantined",
    "occurrence_scoped_lock_dir",
    "owner_metadata_path",
    "process_owner_identity",
    "reconcile_jobs",
    "release_repair_lock",
    "renew_repair_lock",
    "repair_lock",
    "validate_lease_authority",
    "write_claim_alias",
]
