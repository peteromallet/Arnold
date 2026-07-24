"""Tmux session / orphan enrichment for the live watchdog.

Tmux facts are not bearer authority.  This module keeps tmux/session facts
as correlated evidence only, preserves diagnostics, avoids liveness refresh
from observer reads, and feeds typed uncertainty upstream.

Design rules
------------
* Tmux session data is **correlated evidence only** — it never refreshes
  liveness or authorizes positive action.
* Observer reads of tmux state do not modify evidence.
* Missing/unavailable tmux data produces typed ``UNKNOWN``, never optimistic
  defaults.
* Diagnostics are preserved for human operators but gated behind explicit
  non-authoritative markers.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

from arnold_pipelines.megaplan.runtime.process import TmuxSession, detect_orphans


# ── Tmux evidence types ────────────────────────────────────────────────────


class TmuxEvidenceCertainty(Enum):
    """Typed certainty for tmux-derived evidence.

    * ``OBSERVED`` — tmux session was observed and data is current.
    * ``STALE`` — tmux session data is older than the freshness window.
    * ``UNAVAILABLE`` — tmux is not installed or session not found.
    * ``UNKNOWN`` — could not determine tmux state.
    """

    OBSERVED = "observed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TmuxEvidence:
    """Correlated tmux session evidence (non-authoritative).

    Carries session facts as evidence — never as liveness authority.
    Observer reads do not refresh liveness or modify evidence.
    """

    session_name: str
    """Tmux session name."""

    exists: bool = False
    """Whether the tmux session currently exists."""

    is_orphan: bool = False
    """Whether the session is orphaned (no active tmux server)."""

    certainty: TmuxEvidenceCertainty = TmuxEvidenceCertainty.UNKNOWN
    """Certainty of this tmux observation."""

    observed_at_epoch_ms: float = 0.0
    """When this session was last observed (epoch ms)."""

    plan_dir: str = ""
    """Associated plan directory (empty if uncorrelated)."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    evidence_id: str = field(init=False)
    """Content-addressed evidence identifier."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = (
            f"{self.session_name}\x00{self.exists}\x00{self.is_orphan}\x00"
            f"{self.certainty.value}\x00{self.observed_at_epoch_ms}\x00{self.plan_dir}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "evidence_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_fresh(self) -> bool:
        """True when the observation is fresh (within 60s)."""
        if self.observed_at_epoch_ms <= 0:
            return False
        return (time.time() * 1000 - self.observed_at_epoch_ms) < 60_000

    @property
    def cursor_state(self) -> str:
        """Source-cursor state derived from this evidence."""
        if self.certainty == TmuxEvidenceCertainty.UNAVAILABLE:
            return "unknown"
        if self.certainty == TmuxEvidenceCertainty.UNKNOWN:
            return "unknown"
        if self.certainty == TmuxEvidenceCertainty.STALE:
            return "stale"
        return "fresh" if self.is_fresh else "stale"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_name": self.session_name,
            "exists": self.exists,
            "is_orphan": self.is_orphan,
            "certainty": self.certainty.value,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "plan_dir": self.plan_dir,
            "detail": self.detail,
            "evidence_id": self.evidence_id,
            "is_fresh": self.is_fresh,
            "cursor_state": self.cursor_state,
            "_non_authoritative": self._non_authoritative,
        }


@dataclass(frozen=True)
class TmuxInfo:
    """Tmux session and orphan information for a plan directory.

    Legacy-compatible with the original TmuxInfo but carries typed certainty.
    """

    session_names: tuple[str, ...]
    orphans: tuple[str, ...]

    session_evidence: Tuple[TmuxEvidence, ...] = ()
    """Typed evidence for each session (new in M9)."""

    plan_dir: str = ""
    """Associated plan directory."""

    certainty: TmuxEvidenceCertainty = TmuxEvidenceCertainty.UNKNOWN

    observed_at_epoch_ms: float = field(default_factory=lambda: time.time() * 1000)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> dict[str, Any]:
        result: Dict[str, Any] = {
            "session_names": list(self.session_names),
            "orphans": list(self.orphans),
            "certainty": self.certainty.value,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }
        if self.plan_dir:
            result["plan_dir"] = self.plan_dir
        if self.session_evidence:
            result["session_evidence"] = [e.to_dict() for e in self.session_evidence]
        return result

    @property
    def total_sessions(self) -> int:
        """Total sessions (alive + orphan)."""
        return len(self.session_names) + len(self.orphans)

    @property
    def has_any_session(self) -> bool:
        """True when any tmux session is associated."""
        return self.total_sessions > 0


@dataclass(frozen=True)
class TmuxScanResult:
    """Complete tmux scan result for all plan directories.

    Carries evidence per plan directory with typed certainty.  Every
    piece of evidence is explicitly non-authoritative.
    """

    results: Tuple[TmuxInfo, ...]
    """One TmuxInfo per scanned plan directory."""

    scan_epoch_ms: float = field(default_factory=lambda: time.time() * 1000)

    tmux_available: bool = True
    """Whether tmux was available during the scan."""

    error_detail: str = ""
    """Error detail if tmux was unavailable."""

    scan_digest: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_results = tuple(sorted(self.results, key=lambda r: r.plan_dir or ""))
        object.__setattr__(self, "results", sorted_results)
        parts = "\x00".join(
            ",".join(r.session_names) + "|" + ",".join(r.orphans)
            for r in sorted_results
        )
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "scan_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def total_sessions(self) -> int:
        return sum(r.total_sessions for r in self.results)

    @property
    def all_session_names(self) -> Tuple[str, ...]:
        all_names: list[str] = []
        for r in self.results:
            all_names.extend(r.session_names)
            all_names.extend(r.orphans)
        return tuple(sorted(set(all_names)))

    def by_plan_dir(self, plan_dir: str) -> Optional[TmuxInfo]:
        """Return TmuxInfo for a specific plan directory."""
        for r in self.results:
            if r.plan_dir == plan_dir:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "scan_epoch_ms": self.scan_epoch_ms,
            "tmux_available": self.tmux_available,
            "error_detail": self.error_detail,
            "total_sessions": self.total_sessions,
            "all_session_names": list(self.all_session_names),
            "scan_digest": self.scan_digest,
            "_non_authoritative": self._non_authoritative,
        }


# ── Plan session patterns ──────────────────────────────────────────────────


def _plan_session_patterns(plan_dir: Path) -> list[str]:
    """Generate likely tmux session patterns for a plan directory."""
    name = plan_dir.name
    return [name, f"{name}*", f"*{name}*"]


# ── Tmux enrichment (with typed uncertainty) ───────────────────────────────


def enrich_with_tmux(
    processes: tuple[Any, ...],
    plan_dirs: tuple[Path, ...],
) -> dict[Path, TmuxInfo]:
    """Discover tmux sessions and orphans associated with each plan directory.

    Returns a mapping from plan directory to ``TmuxInfo``.  Tmux session data
    is correlated evidence only — it never refreshes liveness or authorizes
    positive action.

    The implementation gracefully degrades when tmux is not installed,
    producing typed ``UNAVAILABLE`` certainty.
    """
    now_ms = time.time() * 1000
    result: dict[Path, TmuxInfo] = {}
    for plan_dir in plan_dirs:
        sessions: list[str] = []
        orphans: list[str] = []
        evidence_list: list[TmuxEvidence] = []
        for pattern in _plan_session_patterns(plan_dir):
            try:
                orphan_matches = detect_orphans(pattern)
            except Exception:
                orphan_matches = []
            for session_name in orphan_matches:
                if session_name not in sessions and session_name not in orphans:
                    try:
                        session_exists = TmuxSession(session_name).exists()
                        if session_exists:
                            sessions.append(session_name)
                            evidence_list.append(TmuxEvidence(
                                session_name=session_name,
                                exists=True,
                                is_orphan=False,
                                certainty=TmuxEvidenceCertainty.OBSERVED,
                                observed_at_epoch_ms=now_ms,
                                plan_dir=str(plan_dir),
                                detail=f"tmux session observed: {session_name}",
                            ))
                        else:
                            orphans.append(session_name)
                            evidence_list.append(TmuxEvidence(
                                session_name=session_name,
                                exists=False,
                                is_orphan=True,
                                certainty=TmuxEvidenceCertainty.OBSERVED,
                                observed_at_epoch_ms=now_ms,
                                plan_dir=str(plan_dir),
                                detail=f"orphan tmux session: {session_name}",
                            ))
                    except Exception:
                        orphans.append(session_name)
                        evidence_list.append(TmuxEvidence(
                            session_name=session_name,
                            exists=False,
                            is_orphan=True,
                            certainty=TmuxEvidenceCertainty.UNKNOWN,
                            observed_at_epoch_ms=now_ms,
                            plan_dir=str(plan_dir),
                            detail=f"could not determine tmux session state: {session_name}",
                        ))

        result[plan_dir] = TmuxInfo(
            session_names=tuple(sessions),
            orphans=tuple(orphans),
            session_evidence=tuple(evidence_list),
            plan_dir=str(plan_dir),
            certainty=TmuxEvidenceCertainty.OBSERVED if evidence_list else TmuxEvidenceCertainty.UNAVAILABLE,
            observed_at_epoch_ms=now_ms,
        )
    return result


def enrich_with_tmux_typed(
    processes: tuple[Any, ...],
    plan_dirs: tuple[Path, ...],
) -> TmuxScanResult:
    """Discover tmux sessions with typed uncertainty (new M9 API).

    Returns a TmuxScanResult with typed evidence per plan directory.
    Prefer this over ``enrich_with_tmux`` for consumers that need
    explicit certainty and non-authoritative markers.
    """
    mapping = enrich_with_tmux(processes, plan_dirs)
    results = tuple(
        info
        for plan_dir in plan_dirs
        for info in (mapping.get(plan_dir),)
        if info is not None
    )
    # Check if tmux itself is available
    tmux_available = True
    error_detail = ""
    try:
        import subprocess
        subprocess.run(["tmux", "list-sessions"], capture_output=True, timeout=5)
    except FileNotFoundError:
        tmux_available = False
        error_detail = "tmux binary not found"
    except Exception as e:
        tmux_available = False
        error_detail = str(e)

    return TmuxScanResult(
        results=results,
        tmux_available=tmux_available,
        error_detail=error_detail,
    )


# ── Observer purity: tmux reads do not refresh liveness ────────────────────


def tmux_observer_read_is_pure(
    before_evidence: TmuxScanResult,
    after_evidence: TmuxScanResult,
) -> bool:
    """Prove that an observer read of tmux state did not refresh liveness.

    Returns True when the scan digests are identical (no evidence mutation).
    """
    return before_evidence.scan_digest == after_evidence.scan_digest


__all__ = [
    # ── Types ──
    "TmuxEvidenceCertainty",
    "TmuxEvidence",
    "TmuxInfo",
    "TmuxScanResult",
    # ── Enrichment ──
    "enrich_with_tmux",
    "enrich_with_tmux_typed",
    # ── Observer purity ──
    "tmux_observer_read_is_pure",
]
