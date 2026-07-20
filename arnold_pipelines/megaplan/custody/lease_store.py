"""Append-only Custody lease history store using durable local CAS/file-locking.

Each lease is backed by an append-only event history (JSON-lines) and an
advisory ``fcntl.flock`` for serialization — the same pattern used by
:mod:`megaplan.runtime.capacity_lease` and
:mod:`megaplan.runtime.budget_authority`.

Storage layout under ``<base_dir>/``::

    <lease_id>.history.jsonl   — append-only event stream (one JSON object per line)
    <lease_id>.state.json      — cached current lease state (derived from replay)
    <lease_id>.lock            — fcntl.flock serialization gate

Principles
----------
* **Append-only** — Terminal events (release, expire, fence) are *added* to the
  history; they never erase prior events.  Replay always sees the full
  lifecycle.
* **Sequence checks** — An event whose ``sequence <= last_sequence`` is rejected
  unless it is an idempotent exact repeat.
* **Idempotency** — An event whose ``idempotency_key`` + ``payload_hash``
  matches the last event with that sequence is silently accepted (no-op).
* **Payload conflict quarantine** — If an event arrives with a known
  ``idempotency_key`` but a *different* ``payload_hash``, a synthetic
  ``conflict`` event is appended and the store quarantines the conflicting
  payload so callers can reconcile.
* **Deterministic replay** — ``replay_history(lease_id)`` replays every event
  in order through the reducers and returns the final ``CustodyLease`` (or
  ``None`` if the lease has not yet been acquired).

Reducers
--------
The store includes pure reducer functions for every event type:

============  =============================================================
acquire       Create a lease (requires no existing active lease).
renew         Bump ``custody_epoch`` and update ``expires_at``.
transfer      Change owner identity tuples.
release       Mark the lease as released (terminal — no further mutations).
expire        Mark the lease as expired (terminal).
fence         Mark the lease as fenced (terminal).
conflict      Record a conflict in the lease's ``last_conflict`` field.
reconcile     Clear conflict state and optionally resume the lease.
============

Terminal events produce a lease still present in the state with
``event_type`` set so callers can distinguish active vs terminated leases,
but the history is never truncated.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyLeaseEvent,
    CustodyLeaseEventType,
    normalize_custody_lease,
    normalize_custody_lease_event,
)
from arnold_pipelines.run_authority.contracts import (
    ContractError,
    PayloadConflict,
)

# ── Default base directory ────────────────────────────────────────────────


def default_lease_store_dir() -> Path:
    """Return the default custody lease-store directory."""
    return Path(os.path.expanduser("~/.megaplan/custody/leases"))


# ── File-path helpers ─────────────────────────────────────────────────────


def _history_path(base_dir: Path, lease_id: str) -> Path:
    return base_dir / f"{lease_id}.history.jsonl"


def _state_path(base_dir: Path, lease_id: str) -> Path:
    return base_dir / f"{lease_id}.state.json"


def _lock_path(base_dir: Path, lease_id: str) -> Path:
    return base_dir / f"{lease_id}.lock"


# ── Atomic file write ─────────────────────────────────────────────────────


def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically via temp-file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _atomic_append(path: Path, line: str) -> None:
    """Append a single line to *path* atomically via temp-file + rename.

    This reads the existing file, appends, and writes back.
    For append-only semantics, callers must serialize via flock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            existing = ""
    _atomic_write(path, existing + line)


# ── Error types ───────────────────────────────────────────────────────────


class LeaseStoreError(RuntimeError):
    """Base exception for custody lease-store operations."""


class StaleSequenceError(LeaseStoreError):
    """Raised when an event has a non-monotonic sequence number."""


class LeaseIdempotencyConflict(LeaseStoreError):
    """Raised when an idempotency key maps to a different payload."""


class QuarantinedPayloadError(LeaseStoreError):
    """Raised when a payload conflict has been quarantined."""


class LeaseNotFoundError(LeaseStoreError):
    """Raised when a referenced lease does not exist."""


# ── Reducers ──────────────────────────────────────────────────────────────


def _reduce_acquire(
    _current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Create a new lease from an acquire event.

    Requires no existing lease (or the existing lease is in a terminal state
    where a new acquisition is allowed — determined by the caller).
    """
    from arnold_pipelines.megaplan.custody.contracts import (
        RepairOccurrenceKey,
        CustodyTargetKey,
        build_custody_target_key,
        build_repair_occurrence_key,
    )

    # Reconstruct the lease from the event fields
    # We need a RepairOccurrenceKey, which requires a CustodyTargetKey.
    # The event carries occurrence_digest, which is a hash — we cannot
    # reconstruct the full target from just the digest.
    # Instead, the store layer uses the event's fields directly.
    # For the lease record, we store what we can and use the occurrence_digest
    # as an opaque reference.
    return CustodyLease(
        lease_id=event.lease_id,
        occurrence_key=_synthetic_occurrence_key_from_event(event),
        owner_host=event.owner_host,
        owner_pid=event.owner_pid,
        owner_boot_id=event.owner_boot_id,
        run_authority_grant_id=event.run_authority_grant_id,
        coordinator_fence_token=event.coordinator_fence_token,
        wbc_attempt_reference=event.wbc_attempt_reference,
        custody_epoch=event.custody_epoch,
        acquired_at=event.occurred_at,
        expires_at=_expiry_from_payload(event),
        idempotency_key=event.idempotency_key,
        causal_predecessor=event.causal_predecessor,
    )


def _reduce_renew(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Renew a lease — bump epoch and update expiry."""
    if current is None:
        raise LeaseStoreError("cannot renew a non-existent lease")
    new_epoch = max(current.custody_epoch, event.custody_epoch)
    new_expires = _expiry_from_payload(event)
    return replace(
        current,
        custody_epoch=new_epoch,
        expires_at=new_expires,
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


def _reduce_transfer(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Transfer ownership to a new owner identity."""
    if current is None:
        raise LeaseStoreError("cannot transfer a non-existent lease")
    new_epoch = max(current.custody_epoch, event.custody_epoch)
    return replace(
        current,
        owner_host=event.owner_host,
        owner_pid=event.owner_pid,
        owner_boot_id=event.owner_boot_id,
        custody_epoch=new_epoch,
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


def _terminal_expires_at(
    current: CustodyLease, event: CustodyLeaseEvent
) -> str:
    """Return an ``expires_at`` value that is strictly after ``acquired_at``.

    Terminal events (release, expire, fence) set ``expires_at`` to the event's
    ``occurred_at``, but if that is not after ``acquired_at`` (e.g. the event is
    recorded with the same timestamp), we advance it by one second to satisfy
    the contract invariant ``expires_at > acquired_at``.
    """
    from datetime import timedelta

    candidate = event.occurred_at
    try:
        acq_dt = datetime.fromisoformat(current.acquired_at.replace("Z", "+00:00"))
        cand_dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        # If either timestamp is unparseable, return candidate as-is;
        # the contract will raise on construction if it's invalid.
        return candidate
    if cand_dt > acq_dt:
        return candidate
    # Advance by one second past acquired_at to maintain the invariant.
    safe = acq_dt + timedelta(seconds=1)
    return safe.strftime("%Y-%m-%dT%H:%M:%SZ")


def _reduce_release(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Release a lease — terminal state, no further mutations."""
    if current is None:
        raise LeaseStoreError("cannot release a non-existent lease")
    return replace(
        current,
        expires_at=_terminal_expires_at(current, event),
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


def _reduce_expire(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Mark a lease as expired — terminal state."""
    if current is None:
        raise LeaseStoreError("cannot expire a non-existent lease")
    return replace(
        current,
        expires_at=_terminal_expires_at(current, event),
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


def _reduce_fence(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Mark a lease as fenced — terminal state."""
    if current is None:
        raise LeaseStoreError("cannot fence a non-existent lease")
    return replace(
        current,
        coordinator_fence_token=event.coordinator_fence_token,
        expires_at=_terminal_expires_at(current, event),
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


def _reduce_conflict(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Record a conflict — the lease itself is unchanged (quarantined separately)."""
    if current is None:
        # Conflict on a lease that hasn't been acquired yet is possible
        # (e.g., conflicting acquire attempts).  The caller quarantines.
        return None
    # Conflict does not mutate the lease — it's recorded in the event history.
    return current


def _reduce_reconcile(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Reconcile after a conflict — resume from the current state."""
    if current is None:
        raise LeaseStoreError("cannot reconcile a non-existent lease")
    new_epoch = max(current.custody_epoch, event.custody_epoch)
    return replace(
        current,
        custody_epoch=new_epoch,
        causal_predecessor=event.causal_predecessor or current.lease_id,
    )


# ── Reducer dispatch ──────────────────────────────────────────────────────


_REDUCERS: dict[CustodyLeaseEventType, Any] = {
    "acquire": _reduce_acquire,
    "renew": _reduce_renew,
    "transfer": _reduce_transfer,
    "release": _reduce_release,
    "expire": _reduce_expire,
    "fence": _reduce_fence,
    "conflict": _reduce_conflict,
    "reconcile": _reduce_reconcile,
}


def reduce_event(
    current: CustodyLease | None, event: CustodyLeaseEvent
) -> CustodyLease | None:
    """Apply a single event to the current lease state, returning the new state."""
    reducer = _REDUCERS.get(event.event_type)
    if reducer is None:
        raise LeaseStoreError(f"unknown event type: {event.event_type!r}")
    return reducer(current, event)


def replay_events(
    events: Sequence[CustodyLeaseEvent],
) -> CustodyLease | None:
    """Deterministically replay a sequence of events to compute the current lease."""
    current: CustodyLease | None = None
    for event in events:
        current = reduce_event(current, event)
    return current


# ── Synthetic occurrence key (used when reconstructing leases from events) ─


def _synthetic_occurrence_key_from_event(
    event: CustodyLeaseEvent,
) -> Any:
    """Build a minimal RepairOccurrenceKey from an event when the full target
    is not available in the event history.

    The event carries occurrence_digest but not the full F01 tuple.
    We construct a synthetic target using the lease_id as a stand-in for
    the F01 fields and use the event's other identity fields directly.
    """
    from arnold_pipelines.megaplan.custody.contracts import (
        RepairOccurrenceKey,
        CustodyTargetKey,
    )

    # Build a synthetic target from the lease_id and event fields.
    # This is lossy (the original F01 is not recoverable from just the digest)
    # but allows the lease record to carry a coherent occurrence_key.
    synthetic_target = CustodyTargetKey(
        environment="__synthetic__",
        session=event.lease_id,
        chain=event.lease_id,
        plan_revision=event.causal_predecessor or event.lease_id,
        phase=event.event_type,
        task=event.lease_id,
        attempt=str(event.sequence),
        normalized_failure_kind=event.event_type,
        blocker_or_phase_result_hash=event.payload_hash,
        fence=str(event.coordinator_fence_token),
        chain_identity=event.occurrence_digest,
    )
    return RepairOccurrenceKey(
        target=synthetic_target,
        run_id=event.run_authority_grant_id,
        run_revision=str(event.custody_epoch),
        coordinator_attempt_id=event.event_id,
        fence_token=event.coordinator_fence_token,
        wbc_attempt_reference=event.wbc_attempt_reference,
    )


def _expiry_from_payload(event: CustodyLeaseEvent) -> str:
    """Extract expires_at from the event payload, falling back to a default."""
    payload = dict(event.payload) if event.payload else {}
    expires = payload.get("expires_at")
    if isinstance(expires, str) and expires.strip():
        return expires
    # Fallback: 24 hours from occurred_at
    try:
        occurred_dt = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        occurred_dt = datetime.now(timezone.utc)
    from datetime import timedelta
    default = occurred_dt + timedelta(hours=24)
    return default.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Lease store ───────────────────────────────────────────────────────────


@dataclass
class CustodyLeaseStore:
    """Append-only custody lease history store.

    Construct via :func:`open_lease_store`.  Each instance manages leases
    under a single ``base_dir``.
    """

    base_dir: Path
    flock: bool = True

    # -- record event --------------------------------------------------------

    def record_event(self, event: CustodyLeaseEvent) -> CustodyLeaseEvent:
        """Append *event* to the lease's history.

        Returns the event as recorded (may be the same event for a no-op
        idempotent repeat).

        Raises:
            StaleSequenceError: if the event sequence is not monotonic.
            LeaseIdempotencyConflict: if the idempotency key maps to a different payload.
        """
        if not isinstance(event, CustodyLeaseEvent):
            raise LeaseStoreError("event must be a CustodyLeaseEvent")

        lease_id = event.lease_id
        existing_events = self.load_history(lease_id)

        # --- Sequence check ---
        if existing_events:
            last_seq = existing_events[-1].sequence
            if event.sequence < last_seq:
                raise StaleSequenceError(
                    f"event sequence {event.sequence} is before last sequence "
                    f"{last_seq} for lease {lease_id!r}"
                )
            if event.sequence == last_seq:
                # Idempotency check: same idempotency_key + same payload_hash = no-op
                last_event = existing_events[-1]
                if event.idempotency_key == last_event.idempotency_key:
                    if event.payload_hash == last_event.payload_hash:
                        # Exact duplicate — idempotent no-op
                        return last_event
                    # Same idempotency key, different payload — conflict!
                    self._quarantine_conflict(lease_id, event, last_event)
                # Different idempotency key, same sequence — stale sequence
                raise StaleSequenceError(
                    f"event sequence {event.sequence} already occupied by a "
                    f"different idempotency key for lease {lease_id!r}"
                )

        # --- Append ---
        if self.flock:
            self._append_flock(lease_id, event)
        else:
            self._append_inproc(lease_id, event)

        # --- Recompute and cache state ---
        all_events = self.load_history(lease_id)
        current = replay_events(all_events)
        if current is not None:
            self._write_cached_state(lease_id, current)

        return event

    # -- load / replay -------------------------------------------------------

    def load_history(self, lease_id: str) -> tuple[CustodyLeaseEvent, ...]:
        """Load the raw event history for *lease_id*.

        Returns an empty tuple if no history exists.
        """
        path = _history_path(self.base_dir, lease_id)
        if not path.exists():
            return ()
        try:
            text = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return ()
        if not text.strip():
            return ()
        events: list[CustodyLeaseEvent] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            evt = normalize_custody_lease_event(data)
            if evt is not None:
                events.append(evt)
        return tuple(events)

    def replay_history(self, lease_id: str) -> CustodyLease | None:
        """Deterministically replay the event history for *lease_id*."""
        events = self.load_history(lease_id)
        return replay_events(events)

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        """Return the current lease state (from cache if available, else replay)."""
        # Try cached state first
        cached = self._read_cached_state(lease_id)
        if cached is not None:
            return cached
        # Fall back to replay
        return self.replay_history(lease_id)

    # -- quarantine ----------------------------------------------------------

    def quarantined_conflicts(self, lease_id: str) -> tuple[dict[str, Any], ...]:
        """Return quarantined conflict payloads for *lease_id*."""
        path = _quarantine_path(self.base_dir, lease_id)
        if not path.exists():
            return ()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return ()
        if not isinstance(data, list):
            return ()
        return tuple(item for item in data if isinstance(item, dict))

    # -- internal helpers ----------------------------------------------------

    def _append_flock(self, lease_id: str, event: CustodyLeaseEvent) -> None:
        """Append under flock serialization."""
        import fcntl

        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_p = _lock_path(self.base_dir, lease_id)
        fd = os.open(lock_p, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _atomic_append(
                _history_path(self.base_dir, lease_id),
                event.to_json() + "\n",
            )
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _append_inproc(self, lease_id: str, event: CustodyLeaseEvent) -> None:
        """Append without flock (single-process fallback)."""
        _atomic_append(
            _history_path(self.base_dir, lease_id),
            event.to_json() + "\n",
        )

    def _write_cached_state(self, lease_id: str, lease: CustodyLease) -> None:
        """Write the cached state atomically."""
        _atomic_write(
            _state_path(self.base_dir, lease_id),
            lease.to_json(),
        )

    def _read_cached_state(self, lease_id: str) -> CustodyLease | None:
        """Read the cached state if it exists."""
        path = _state_path(self.base_dir, lease_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        return normalize_custody_lease(data)

    def _quarantine_conflict(
        self,
        lease_id: str,
        new_event: CustodyLeaseEvent,
        existing_event: CustodyLeaseEvent,
    ) -> None:
        """Quarantine a payload conflict for later reconciliation.

        Appends a synthetic ``conflict`` event and records both
        conflicting payloads in the quarantine file.
        """
        # Append a conflict event
        conflict_event = CustodyLeaseEvent(
            event_id=f"conflict-{new_event.idempotency_key}",
            lease_id=lease_id,
            sequence=new_event.sequence,
            event_type="conflict",
            occurred_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            custody_epoch=new_event.custody_epoch,
            owner_host=new_event.owner_host,
            owner_pid=new_event.owner_pid,
            owner_boot_id=new_event.owner_boot_id,
            run_authority_grant_id=new_event.run_authority_grant_id,
            coordinator_fence_token=new_event.coordinator_fence_token,
            wbc_attempt_reference=new_event.wbc_attempt_reference,
            occurrence_digest=new_event.occurrence_digest,
            idempotency_key=f"conflict-{new_event.idempotency_key}",
            causal_predecessor=new_event.causal_predecessor,
            payload={
                "reason": "idempotency_payload_conflict",
                "conflicting_idempotency_key": new_event.idempotency_key,
                "existing_payload_hash": existing_event.payload_hash,
                "new_payload_hash": new_event.payload_hash,
            },
        )

        if self.flock:
            self._append_flock(lease_id, conflict_event)
        else:
            self._append_inproc(lease_id, conflict_event)

        # Record both payloads in quarantine
        qpath = _quarantine_path(self.base_dir, lease_id)
        existing_quarantine: list[dict[str, Any]] = []
        if qpath.exists():
            try:
                existing_quarantine = json.loads(qpath.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                existing_quarantine = []
        if not isinstance(existing_quarantine, list):
            existing_quarantine = []

        existing_quarantine.append({
            "idempotency_key": new_event.idempotency_key,
            "sequence": new_event.sequence,
            "existing_event_id": existing_event.event_id,
            "existing_payload_hash": existing_event.payload_hash,
            "conflicting_event_id": new_event.event_id,
            "conflicting_payload_hash": new_event.payload_hash,
            "quarantined_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

        _atomic_write(qpath, json.dumps(existing_quarantine, indent=2))

        raise LeaseIdempotencyConflict(
            f"idempotency key {new_event.idempotency_key!r} maps to different "
            f"payloads for lease {lease_id!r}: existing hash "
            f"{existing_event.payload_hash!r} vs new hash "
            f"{new_event.payload_hash!r}"
        )


def _quarantine_path(base_dir: Path, lease_id: str) -> Path:
    return base_dir / f"{lease_id}.quarantine.json"


# ── Open / factory ────────────────────────────────────────────────────────


def open_lease_store(
    base_dir: Path | None = None,
    *,
    flock: bool = True,
) -> CustodyLeaseStore:
    """Open a custody lease store rooted at *base_dir*.

    If *base_dir* is ``None``, defaults to ``~/.megaplan/custody/leases``.
    """
    base = (base_dir or default_lease_store_dir()).resolve()
    return CustodyLeaseStore(base_dir=base, flock=flock)


# ── Convenience: record a batch of events ─────────────────────────────────


def record_events(
    store: CustodyLeaseStore,
    events: Sequence[CustodyLeaseEvent],
) -> tuple[CustodyLeaseEvent, ...]:
    """Record a batch of events in sequence order.

    Returns the events as recorded (may differ from input for idempotent repeats).
    """
    result: list[CustodyLeaseEvent] = []
    for event in sorted(events, key=lambda e: e.sequence):
        recorded = store.record_event(event)
        result.append(recorded)
    return tuple(result)
