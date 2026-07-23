"""Orphan-process detection for the live watchdog.

M9: Orphan/retry occurrences are classified by exact identity tuples
(session, plan, revision, attempt, failure_signature, fence) and emit
drift + evidence IDs on mismatch.  A stale T7 occurrence cannot bind to
T12 or a same-basename run.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


_ORPHAN_AGE_SECONDS = 3600.0


@dataclass(frozen=True)
class OrphanIdentity:
    """Exact identity tuple for orphan classification.

    Each field narrows the binding so a stale occurrence cannot
    accidentally match a different session, plan, revision, or run.
    """

    session: str = ""
    """Canonical session name (e.g. ``cloud-session-1``)."""

    plan: str = ""
    """Plan name this worker was executing."""

    plan_dir: str = ""
    """Absolute path to the plan directory."""

    revision: str = ""
    """Plan revision hash (sha256 of finalize.json at admission time)."""

    attempt: int = 0
    """Execution attempt number (1-indexed)."""

    failure_signature: str = ""
    """Content hash of the failure that triggered orphan detection."""

    fence: str = ""
    """Run Authority fence token at the time the worker was admitted."""

    def identity_digest(self) -> str:
        """Content-addressed evidence ID for this identity tuple."""
        raw = (
            f"{self.session}\x00{self.plan}\x00{self.plan_dir}\x00"
            f"{self.revision}\x00{self.attempt}\x00"
            f"{self.failure_signature}\x00{self.fence}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_empty(self) -> bool:
        """True when no identity fields are populated (bare orphan)."""
        return not any([
            self.session, self.plan, self.plan_dir,
            self.revision, self.failure_signature, self.fence,
        ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "plan": self.plan,
            "plan_dir": self.plan_dir,
            "revision": self.revision,
            "attempt": self.attempt,
            "failure_signature": self.failure_signature,
            "fence": self.fence,
            "identity_digest": f"sha256:{self.identity_digest()}",
        }

    @classmethod
    def from_correlation(
        cls,
        *,
        session: str = "",
        plan: str = "",
        plan_dir: str = "",
        revision: str = "",
        attempt: int = 0,
        failure_signature: str = "",
        fence: str = "",
    ) -> "OrphanIdentity":
        return cls(
            session=session,
            plan=plan,
            plan_dir=plan_dir,
            revision=revision,
            attempt=attempt,
            failure_signature=failure_signature,
            fence=fence,
        )


@dataclass(frozen=True)
class OrphanDrift:
    """Drift evidence when an orphan identity does not match expectations.

    Emitted when the current binding target (session/plan/revision/attempt)
    differs from the orphan's recorded identity.  Drift is diagnostic
    evidence — it never authorizes repair or escalation.
    """

    field: str
    """Which identity field drifted (session, plan, revision, attempt, …)."""

    expected: str
    """Expected value from the current binding target."""

    observed: str
    """Observed value from the orphan's recorded identity."""

    evidence_id: str = ""
    """Content-addressed evidence ID for this drift observation."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raw = f"{self.field}\x00{self.expected}\x00{self.observed}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "evidence_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }


@dataclass(frozen=True)
class OrphanProcess:
    pid: int
    category: str
    elapsed_seconds: float | None
    reason: str

    # ── M9: exact identity classification ──
    identity: OrphanIdentity = field(default_factory=OrphanIdentity)
    """Exact identity tuple for this orphan occurrence."""

    drift: tuple[OrphanDrift, ...] = ()
    """Drift evidence when identity fields do not match expectations."""

    evidence_id: str = ""
    """Content-addressed evidence ID for this orphan occurrence."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raw = (
                f"{self.pid}\x00{self.category}\x00{self.identity.identity_digest()}"
            )
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "evidence_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "category": self.category,
            "elapsed_seconds": self.elapsed_seconds,
            "reason": self.reason,
            "identity": self.identity.to_dict() if not self.identity.is_empty() else None,
            "drift": [d.to_dict() for d in self.drift] if self.drift else [],
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }


def _is_parent_alive(ppid: int | None, scanned_pids: set[int]) -> bool:
    """A parent is considered alive if it is in our scanned process set.

    ``ppid`` of 0 or 1 means the process is directly owned by the kernel/
    launchd and has no interactive supervisor.
    """
    if ppid is None:
        return False
    if ppid <= 1:
        return False
    return ppid in scanned_pids


def _is_orphaned_tmux_server(proc: Any, min_age_seconds: float) -> bool:
    """True if *proc* looks like an old detached tmux server."""
    cmdline = ""
    if isinstance(proc, dict):
        cmdline = proc.get("cmdline", "")
        ppid = proc.get("ppid")
        elapsed = proc.get("elapsed_seconds")
    else:
        cmdline = getattr(proc, "cmdline", "")
        ppid = getattr(proc, "ppid", None)
        elapsed = getattr(proc, "elapsed_seconds", None)
    lowered = str(cmdline).lower().lstrip()
    if not lowered.startswith("tmux"):
        return False
    try:
        ppid = int(ppid) if ppid is not None else None
    except Exception:
        return False
    if ppid is not None and ppid > 1:
        return False
    try:
        elapsed = float(elapsed) if elapsed is not None else 0.0
    except Exception:
        return False
    return elapsed >= min_age_seconds


def _has_orphaned_tmux_ancestor(
    pid: int,
    proc_by_pid: dict[int, Any],
    min_age_seconds: float,
    visited: set[int] | None = None,
) -> tuple[bool, int | None]:
    """Walk the parent chain looking for an old detached tmux server.

    Returns ``(orphaned, orphan_pid)``.
    """
    if visited is None:
        visited = set()
    if pid in visited or pid <= 1:
        return False, None
    visited.add(pid)
    proc = proc_by_pid.get(pid)
    if proc is None:
        return False, None
    if _is_orphaned_tmux_server(proc, min_age_seconds):
        return True, pid
    if isinstance(proc, dict):
        ppid = proc.get("ppid")
    else:
        ppid = getattr(proc, "ppid", None)
    try:
        ppid = int(ppid) if ppid is not None else 1
    except Exception:
        ppid = 1
    return _has_orphaned_tmux_ancestor(ppid, proc_by_pid, min_age_seconds, visited)


def _extract_identity_from_correlation(
    corr: Any,
    proc: Any,
    *,
    plan_dirs: dict[str, str] | None = None,
) -> OrphanIdentity:
    """Extract an OrphanIdentity from a correlation record and process info.

    Best-effort: missing fields are left empty rather than defaulted.
    """
    session = ""
    plan = ""
    plan_dir = ""
    revision = ""
    attempt = 0
    failure_signature = ""
    fence = ""

    if isinstance(corr, dict):
        session = str(corr.get("session", ""))
        plan = str(corr.get("plan_name", ""))
        plan_dir = str(corr.get("plan_dir", ""))
        revision = str(corr.get("revision", ""))
        attempt = int(corr.get("attempt", 0) or 0)
        failure_signature = str(corr.get("failure_signature", ""))
        fence = str(corr.get("fence", ""))
    else:
        session = str(getattr(corr, "session", ""))
        plan = str(getattr(corr, "plan_name", ""))
        plan_dir = str(getattr(corr, "plan_dir", ""))
        revision = str(getattr(corr, "revision", ""))
        try:
            attempt = int(getattr(corr, "attempt", 0) or 0)
        except (TypeError, ValueError):
            attempt = 0
        failure_signature = str(getattr(corr, "failure_signature", ""))
        fence = str(getattr(corr, "fence", ""))

    return OrphanIdentity(
        session=session,
        plan=plan,
        plan_dir=plan_dir,
        revision=revision,
        attempt=attempt,
        failure_signature=failure_signature,
        fence=fence,
    )


def detect_identity_drift(
    observed: OrphanIdentity,
    expected: OrphanIdentity,
) -> tuple[OrphanDrift, ...]:
    """Compare observed vs expected identity and emit drift on mismatch.

    Only populated fields are compared — empty fields skip comparison.
    Returns a tuple of OrphanDrift entries, one per mismatched field.
    """
    drift: list[OrphanDrift] = []
    fields = [
        ("session", observed.session, expected.session),
        ("plan", observed.plan, expected.plan),
        ("plan_dir", observed.plan_dir, expected.plan_dir),
        ("revision", observed.revision, expected.revision),
        ("attempt", str(observed.attempt) if observed.attempt else "",
         str(expected.attempt) if expected.attempt else ""),
        ("failure_signature", observed.failure_signature, expected.failure_signature),
        ("fence", observed.fence, expected.fence),
    ]
    for field, obs_val, exp_val in fields:
        if not obs_val and not exp_val:
            continue
        if obs_val != exp_val:
            drift.append(OrphanDrift(
                field=field,
                expected=exp_val or "",
                observed=obs_val or "",
            ))
    return tuple(drift)


def find_orphan_processes(
    processes: tuple[Any, ...],
    correlations: tuple[Any, ...],
    *,
    min_age_seconds: float = _ORPHAN_AGE_SECONDS,
    expected_identities: dict[int, OrphanIdentity] | None = None,
) -> dict[Path, list[OrphanProcess]]:
    """Return suspected orphan processes grouped by plan directory.

    A process is considered an orphan when it is correlated to a plan, has
    been running longer than ``min_age_seconds``, and its parent is either
    the init process, no longer present, or an old detached tmux server.

    M9: Each orphan carries exact identity classification (session, plan,
    revision, attempt, failure_signature, fence) and drift evidence when
    the observed identity does not match expectations.
    """
    def _get_int(obj: Any, name: str) -> int | None:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    def _get_float(obj: Any, name: str) -> float | None:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        try:
            return float(value) if value is not None else None
        except Exception:
            return None

    def _get_str(obj: Any, name: str) -> str | None:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    expected_identities = expected_identities or {}

    scanned_pids: set[int] = {_get_int(p, "pid") for p in processes if _get_int(p, "pid") is not None}
    proc_by_pid: dict[int, Any] = {_get_int(p, "pid"): p for p in processes if _get_int(p, "pid") is not None}

    by_plan: dict[Path, list[OrphanProcess]] = {}
    for corr in correlations:
        plan_dir = Path(corr.plan_dir)
        pid = int(corr.process_pid)
        proc = proc_by_pid.get(pid)
        if proc is None:
            continue

        elapsed = _get_float(proc, "elapsed_seconds")
        if elapsed is None or elapsed < min_age_seconds:
            continue

        ppid = _get_int(proc, "ppid")
        has_orphan_ancestor, orphan_ancestor_pid = _has_orphaned_tmux_ancestor(
            pid, proc_by_pid, min_age_seconds
        )

        if _is_parent_alive(ppid, scanned_pids) and not has_orphan_ancestor:
            continue

        if has_orphan_ancestor:
            reason = f"ancestor tmux server {orphan_ancestor_pid} is detached/orphaned"
        else:
            reason = f"parent {ppid} missing or init"

        # ── M9: extract exact identity and detect drift ──
        identity = _extract_identity_from_correlation(corr, proc)
        expected = expected_identities.get(pid)
        drift: tuple[OrphanDrift, ...] = ()
        if expected is not None and not identity.is_empty():
            drift = detect_identity_drift(identity, expected)

        by_plan.setdefault(plan_dir, []).append(
            OrphanProcess(
                pid=pid,
                category=_get_str(proc, "category") or "unknown",
                elapsed_seconds=elapsed,
                reason=reason,
                identity=identity,
                drift=drift,
            )
        )

    return by_plan


__all__ = [
    "OrphanIdentity",
    "OrphanDrift",
    "OrphanProcess",
    "detect_identity_drift",
    "find_orphan_processes",
]
