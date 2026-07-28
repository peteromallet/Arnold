"""Normalized process/tmux/heartbeat correlation identity.

Process/tmux/heartbeat data is correlated evidence only — it is never bearer
authority for dispatch, repair, or completion.  This module defines the exact
worker identity types that ensure recycled, unrelated, dead, and hung workers
produce typed ``stale`` or ``unknown`` liveness only, never false-positive
progress.

Design rules
------------
* Every worker identity is a (host, pid, boot_id) triple plus an optional
  heartbeat sequence number.  The triple is the minimum correlation key;
  without it, liveness is UNKNOWN.
* Recycled PIDs are detected via boot_id mismatch — a process with the same PID
  but a different boot_id is a different worker.
* Dead workers (pid not live) produce ``stale`` liveness, not ``running``.
* Hung workers (pid live but no recent heartbeat) produce ``stale`` liveness.
* Unrelated workers (cmdline/cwd not matching any known plan) produce
  ``unknown`` liveness for plan correlation.
* All liveness states carry exact evidence IDs (sha256 over identity tuple)
  so consumers can detect drift without re-scanning.
"""

from __future__ import annotations

import hashlib
import os
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Literal, Mapping, Optional, Tuple


# ── Liveness state literals ───────────────────────────────────────────────


class LivenessState(Enum):
    """Typed liveness state for a correlated worker.

    These map onto the source-cursor ``process_correlation`` dimension states:
    * LIVE = "fresh"  — worker is live and heartbeat is recent
    * STALE = "stale" — worker was live but heartbeat is stale
    * DEAD = "stale"  — worker pid is not live
    * HUNG = "stale"  — worker pid is live but no heartbeat evidence
    * RECYCLED = "stale" — pid matches but boot_id differs
    * UNRELATED = "unknown" — no plan correlation
    * UNKNOWN = "unknown" — cannot determine liveness
    """

    LIVE = "live"
    STALE = "stale"
    DEAD = "dead"
    HUNG = "hung"
    RECYCLED = "recycled"
    UNRELATED = "unrelated"
    UNKNOWN = "unknown"


LivenessCursorState = Literal["fresh", "stale", "unknown", "incoherent"]


def liveness_to_cursor_state(state: LivenessState) -> LivenessCursorState:
    """Map a liveness state to its source-cursor state."""
    mapping: Dict[LivenessState, LivenessCursorState] = {
        LivenessState.LIVE: "fresh",
        LivenessState.STALE: "stale",
        LivenessState.DEAD: "stale",
        LivenessState.HUNG: "stale",
        LivenessState.RECYCLED: "stale",
        LivenessState.UNRELATED: "unknown",
        LivenessState.UNKNOWN: "unknown",
    }
    return mapping.get(state, "unknown")


# ── Boot ID (cross-platform best-effort) ──────────────────────────────────


def _read_boot_id() -> Optional[str]:
    """Read the system boot ID if available.

    Linux: /proc/sys/kernel/random/boot_id
    macOS: sysctl kern.boottime (parsed)
    Others: None
    """
    # Linux
    try:
        boot_id_path = "/proc/sys/kernel/random/boot_id"
        if os.path.exists(boot_id_path):
            with open(boot_id_path, "r") as fh:
                return fh.read().strip()
    except Exception:
        pass

    # macOS
    if platform.system() == "Darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                # Format: { sec = 1234567890, usec = 123456 } ...
                return result.stdout.strip()
        except Exception:
            pass

    return None


# ── Worker identity ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerIdentity:
    """Exact worker identity for process/tmux/heartbeat correlation.

    The triple (host, pid, boot_id) is the minimum correlation key.
    Without it, liveness is UNKNOWN.

    The heartbeat_seq disambiguates multiple heartbeats from the same
    process — a stalled heartbeat sequence (same seq for too long)
    indicates a hung worker.
    """

    host: str
    """Hostname where the worker is running."""

    pid: int
    """Process ID."""

    boot_id: str
    """System boot ID at worker start.  Empty string if unavailable."""

    heartbeat_seq: int = 0
    """Monotonic heartbeat sequence number.  0 means no heartbeat evidence."""

    worker_type: str = ""
    """Worker category: megaplan, arnold, shannon, codex, claude, tmux_session."""

    cmdline: str = ""
    """Full command line of the worker process (for audit)."""

    cwd: str = ""
    """Working directory of the worker process."""

    started_at_epoch_ms: Optional[float] = None
    """When the worker was first observed (epoch ms)."""

    last_heartbeat_epoch_ms: Optional[float] = None
    """When the last heartbeat was received (epoch ms)."""

    @property
    def correlation_key(self) -> str:
        """Deterministic correlation key: host:pid:boot_id."""
        return f"{self.host}:{self.pid}:{self.boot_id}"

    @property
    def identity_digest(self) -> str:
        """Content-addressed evidence ID for this worker identity.

        Computed as sha256 over (host, pid, boot_id, heartbeat_seq, worker_type).
        """
        raw = f"{self.host}\x00{self.pid}\x00{self.boot_id}\x00{self.heartbeat_seq}\x00{self.worker_type}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def has_boot_id(self) -> bool:
        """True when boot_id is available (minimum correlation requirement)."""
        return bool(self.boot_id)

    def is_same_worker(self, other: "WorkerIdentity") -> bool:
        """True when two identities refer to the same worker (same triple)."""
        return (
            self.host == other.host
            and self.pid == other.pid
            and self.boot_id == other.boot_id
        )

    def is_recycled_pid(self, other: "WorkerIdentity") -> bool:
        """True when same pid but different boot_id → recycled PID."""
        return (
            self.host == other.host
            and self.pid == other.pid
            and self.boot_id != other.boot_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "pid": self.pid,
            "boot_id": self.boot_id,
            "heartbeat_seq": self.heartbeat_seq,
            "worker_type": self.worker_type,
            "cmdline": self.cmdline,
            "cwd": self.cwd,
            "started_at_epoch_ms": self.started_at_epoch_ms,
            "last_heartbeat_epoch_ms": self.last_heartbeat_epoch_ms,
            "correlation_key": self.correlation_key,
            "identity_digest": f"sha256:{self.identity_digest}",
        }

    @classmethod
    def from_process_record(
        cls,
        pid: int,
        *,
        host: str = "",
        boot_id: str = "",
        worker_type: str = "",
        cmdline: str = "",
        cwd: str = "",
        started_at_epoch_ms: Optional[float] = None,
    ) -> "WorkerIdentity":
        """Build a worker identity from a process record.

        Args:
            pid: Process ID.
            host: Hostname (defaults to platform.node()).
            boot_id: Boot ID (auto-detected if empty).
            worker_type: Category from process scanner.
            cmdline: Full command line.
            cwd: Working directory.
            started_at_epoch_ms: When first observed.
        """
        return cls(
            host=host or platform.node(),
            pid=pid,
            boot_id=boot_id or _read_boot_id() or "",
            heartbeat_seq=0,
            worker_type=worker_type,
            cmdline=cmdline,
            cwd=cwd,
            started_at_epoch_ms=started_at_epoch_ms or (time.time() * 1000),
            last_heartbeat_epoch_ms=None,
        )

    @classmethod
    def from_tmux_session(
        cls,
        session_name: str,
        *,
        host: str = "",
        boot_id: str = "",
        pid: int = 0,
        started_at_epoch_ms: Optional[float] = None,
    ) -> "WorkerIdentity":
        """Build a worker identity from a tmux session.

        Tmux sessions do not carry PID guarantees across hosts, so the
        identity is (host, session_name, boot_id) mapped into the triple.
        """
        return cls(
            host=host or platform.node(),
            pid=pid or hash(session_name) & 0x7FFFFFFF,  # synthetic PID for correlation
            boot_id=boot_id or _read_boot_id() or "",
            heartbeat_seq=0,
            worker_type="tmux_session",
            cmdline=f"tmux:{session_name}",
            cwd="",
            started_at_epoch_ms=started_at_epoch_ms or (time.time() * 1000),
            last_heartbeat_epoch_ms=None,
        )

    def with_heartbeat(self, seq: int, *, epoch_ms: Optional[float] = None) -> "WorkerIdentity":
        """Return a new identity with updated heartbeat sequence.

        Args:
            seq: Monotonic heartbeat sequence number.
            epoch_ms: Epoch milliseconds of the heartbeat.  None defaults to now.
        """
        return WorkerIdentity(
            host=self.host,
            pid=self.pid,
            boot_id=self.boot_id,
            heartbeat_seq=seq,
            worker_type=self.worker_type,
            cmdline=self.cmdline,
            cwd=self.cwd,
            started_at_epoch_ms=self.started_at_epoch_ms,
            last_heartbeat_epoch_ms=epoch_ms if epoch_ms is not None else (time.time() * 1000),
        )


# ── Liveness evaluation ──────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerLiveness:
    """Evaluated liveness for a correlated worker identity.

    Produces a typed liveness state based on process liveness, heartbeat
    freshness, and boot_id matching.  Recycled, unrelated, dead, and hung
    workers produce explicit stale or unknown liveness — never
    false-positive progress.
    """

    identity: WorkerIdentity
    """The exact worker identity."""

    state: LivenessState
    """Evaluated liveness state."""

    is_pid_live: bool = False
    """True when the PID is currently alive."""

    has_recent_heartbeat: bool = False
    """True when a heartbeat was received within the freshness window."""

    heartbeat_age_ms: Optional[float] = None
    """Age of the last heartbeat in milliseconds."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def cursor_state(self) -> LivenessCursorState:
        """Source-cursor state derived from this liveness evaluation."""
        return liveness_to_cursor_state(self.state)

    @property
    def is_positive_progress(self) -> bool:
        """False for stale, dead, hung, recycled, unrelated, unknown.

        Only LIVE workers are positive progress.
        """
        return self.state == LivenessState.LIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "state": self.state.value,
            "cursor_state": self.cursor_state,
            "is_pid_live": self.is_pid_live,
            "has_recent_heartbeat": self.has_recent_heartbeat,
            "heartbeat_age_ms": self.heartbeat_age_ms,
            "is_positive_progress": self.is_positive_progress,
            "detail": self.detail,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def evaluate(
        cls,
        identity: WorkerIdentity,
        *,
        is_pid_live: Optional[bool] = None,
        current_boot_id: str = "",
        heartbeat_freshness_window_ms: int = 30_000,
        now_epoch_ms: Optional[float] = None,
    ) -> "WorkerLiveness":
        """Evaluate liveness for a worker identity.

        Args:
            identity: The worker identity to evaluate.
            is_pid_live: Whether the PID is currently alive (auto-detected if None).
            current_boot_id: Current system boot ID for recycled PID detection.
            heartbeat_freshness_window_ms: Max heartbeat age for "recent".
            now_epoch_ms: Current time for age calculations.

        Returns:
            WorkerLiveness with a typed state.
        """
        now = now_epoch_ms or (time.time() * 1000)

        # No boot_id → cannot correlate → UNKNOWN
        if not identity.has_boot_id and not current_boot_id:
            return cls(
                identity=identity,
                state=LivenessState.UNKNOWN,
                is_pid_live=False,
                detail="no boot_id available; cannot correlate process identity",
            )

        # Recycled PID detection
        current_bid = current_boot_id or _read_boot_id() or ""
        if current_bid and identity.boot_id and current_bid != identity.boot_id:
            return cls(
                identity=identity,
                state=LivenessState.RECYCLED,
                is_pid_live=False,
                detail=f"PID {identity.pid} belongs to boot {identity.boot_id}, current boot is {current_bid}",
            )

        # Check PID liveness
        pid_live = is_pid_live
        if pid_live is None:
            pid_live = _check_pid_live(identity.pid)

        if not pid_live:
            return cls(
                identity=identity,
                state=LivenessState.DEAD,
                is_pid_live=False,
                detail=f"PID {identity.pid} is not live",
            )

        # PID is live — check heartbeat
        if identity.last_heartbeat_epoch_ms is None:
            # Live PID but no heartbeat evidence → HUNG
            return cls(
                identity=identity,
                state=LivenessState.HUNG,
                is_pid_live=True,
                has_recent_heartbeat=False,
                detail=f"PID {identity.pid} is live but has no heartbeat evidence",
            )

        heartbeat_age = now - identity.last_heartbeat_epoch_ms
        has_recent = heartbeat_age <= heartbeat_freshness_window_ms

        if has_recent:
            return cls(
                identity=identity,
                state=LivenessState.LIVE,
                is_pid_live=True,
                has_recent_heartbeat=True,
                heartbeat_age_ms=heartbeat_age,
                detail=f"PID {identity.pid} is live with recent heartbeat ({heartbeat_age:.0f}ms ago)",
            )
        else:
            return cls(
                identity=identity,
                state=LivenessState.STALE,
                is_pid_live=True,
                has_recent_heartbeat=False,
                heartbeat_age_ms=heartbeat_age,
                detail=f"PID {identity.pid} is live but heartbeat is stale ({heartbeat_age:.0f}ms ago)",
            )


# ── PID liveness check (cross-platform best-effort) ──────────────────────


def _check_pid_live(pid: int) -> bool:
    """Best-effort check whether a PID is alive.

    Uses os.kill(pid, 0) which is portable across Unix systems.
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# ── Correlation result ───────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerCorrelation:
    """Result of correlating a worker identity to a plan.

    A worker may be correlated to zero, one, or multiple plans.
    Uncorrelated workers are surfaced as ``UNRELATED`` — they are
    evidence of activity but not of specific plan progress.
    """

    identity: WorkerIdentity
    """The exact worker identity."""

    liveness: WorkerLiveness
    """Evaluated liveness for this worker."""

    plan_dirs: Tuple[str, ...] = ()
    """Plan directories correlated to this worker (empty if unrelated)."""

    correlation_method: str = ""
    """How the correlation was established (exact_name, exact_dir, cwd_match, etc.)."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_correlated(self) -> bool:
        """True when the worker is correlated to at least one plan."""
        return len(self.plan_dirs) > 0

    @property
    def cursor_state(self) -> LivenessCursorState:
        """Source-cursor state for process_correlation dimension."""
        if not self.is_correlated:
            return "unknown"
        return self.liveness.cursor_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "liveness": self.liveness.to_dict(),
            "plan_dirs": list(self.plan_dirs),
            "correlation_method": self.correlation_method,
            "is_correlated": self.is_correlated,
            "cursor_state": self.cursor_state,
            "_non_authoritative": self._non_authoritative,
        }


# ── Bulk correlation aggregation ─────────────────────────────────────────


@dataclass(frozen=True)
class ProcessCorrelationSnapshot:
    """Aggregate process-correlation state across all workers.

    Consumed by the source-cursor vector's ``process_correlation`` dimension.
    Every worker that is dead, hung, recycled, or unrelated produces
    ``stale`` or ``unknown`` cursor state — never ``fresh``.
    """

    correlations: Tuple[WorkerCorrelation, ...]
    """All worker correlations, sorted by identity."""

    snapshot_epoch_ms: float = field(default_factory=lambda: time.time() * 1000)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_corrs = tuple(
            sorted(self.correlations, key=lambda c: c.identity.correlation_key)
        )
        object.__setattr__(self, "correlations", sorted_corrs)
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def live_workers(self) -> Tuple[WorkerCorrelation, ...]:
        """Workers with LIVE liveness state."""
        return tuple(c for c in self.correlations if c.liveness.state == LivenessState.LIVE)

    @property
    def stale_or_worse(self) -> Tuple[WorkerCorrelation, ...]:
        """Workers with non-LIVE liveness state."""
        return tuple(c for c in self.correlations if c.liveness.state != LivenessState.LIVE)

    @property
    def aggregate_cursor_state(self) -> LivenessCursorState:
        """Aggregate cursor state for process_correlation dimension.

        * ``fresh`` when at least one correlated worker is LIVE and none are STALE/DEAD/HUNG.
        * ``stale`` when any correlated worker is STALE/DEAD/HUNG/RECYCLED.
        * ``unknown`` when no workers are correlated or all are UNRELATED/UNKNOWN.
        """
        if not self.correlations:
            return "unknown"

        has_live = any(c.liveness.state == LivenessState.LIVE for c in self.correlations)
        has_stale = any(
            c.liveness.state in (LivenessState.STALE, LivenessState.DEAD, LivenessState.HUNG, LivenessState.RECYCLED)
            for c in self.correlations
        )
        all_uncorrelated = all(not c.is_correlated for c in self.correlations)

        if all_uncorrelated:
            return "unknown"
        if has_stale:
            return "stale"
        if has_live:
            return "fresh"
        return "unknown"

    @property
    def cursor_version(self) -> str:
        """Version identifier for the process_correlation dimension.

        Format: ``<host>:<live_count>:<total_count>:<snapshot_hash>``
        """
        live_count = len(self.live_workers)
        total = len(self.correlations)
        # Digest of all correlation keys for version stability
        keys = "\x00".join(c.identity.correlation_key for c in self.correlations)
        hash_part = hashlib.sha256(keys.encode("utf-8")).hexdigest()[:12]
        host = platform.node()
        return f"{host}:{live_count}:{total}:{hash_part}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlations": [c.to_dict() for c in self.correlations],
            "live_worker_count": len(self.live_workers),
            "stale_worker_count": len(self.stale_or_worse),
            "aggregate_cursor_state": self.aggregate_cursor_state,
            "cursor_version": self.cursor_version,
            "snapshot_epoch_ms": self.snapshot_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }


__all__ = [
    # ── Types ──
    "LivenessState",
    "LivenessCursorState",
    "liveness_to_cursor_state",
    # ── Identity ──
    "WorkerIdentity",
    # ── Liveness ──
    "WorkerLiveness",
    # ── Correlation ──
    "WorkerCorrelation",
    "ProcessCorrelationSnapshot",
    # ── Helpers ──
    "_read_boot_id",
]
