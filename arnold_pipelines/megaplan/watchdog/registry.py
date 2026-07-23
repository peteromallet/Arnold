"""NDJSON registry of seen plans for the live watchdog.

Registry entries preserve diagnostics without refreshing liveness from
observer reads.  Tmux/session facts remain correlated evidence only —
they never escalate into bearer authority.  Typed uncertainty is fed
upstream so consumers can distinguish concrete observations from
inference.

Design rules (M9)
-----------------
* Observer reads do NOT refresh liveness — the registry records what was
  observed without inferring progress.
* Tmux/session facts are correlated evidence, never liveness authority.
* Every Observation carries explicit ``certainty`` and
  ``_non_authoritative`` markers.
* Transitions carry the evidence basis (process, tmux, heartbeat) so
  consumers know which evidence source triggered the transition.
* ``UNKNOWN`` is explicitly surfaced — never collapsed to optimistic state.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple


class PlanStatus(str, Enum):
    """Simplified lifecycle status derived from a single observation."""

    NEW = "new"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    STUCK = "stuck"
    IDLE = "idle"
    DISAPPEARED = "disappeared"
    UNCERTAIN = "uncertain"


# ── Observation certainty ──────────────────────────────────────────────────


class ObservationCertainty(str, Enum):
    """Typed certainty for a watchdog observation.

    * ``OBSERVED`` — evidence was directly read from a live source.
    * ``INFERRED`` — status derived from indirect evidence.
    * ``STALE`` — evidence is older than the freshness window.
    * ``UNKNOWN`` — could not determine state.
    """

    OBSERVED = "observed"
    INFERRED = "inferred"
    STALE = "stale"
    UNKNOWN = "unknown"


_TERMINAL_SUCCESS_STATES: frozenset[str] = frozenset({
    "completed",
    "done",
    "finalized",
    "executed",
    "resolved",
    "reviewed",
    "accepted",
})

_TERMINAL_FAILURE_STATES: frozenset[str] = frozenset({
    "failed",
    "aborted",
})

_CANCELLED_STATES: frozenset[str] = frozenset({
    "cancelled",
})

_REJECTED_STATES: frozenset[str] = frozenset({
    "rejected",
})


# ── Observation ────────────────────────────────────────────────────────────


@dataclass
class Observation:
    """A single watchdog observation of a plan.

    Carries explicit certainty and evidence source markers.  Observer reads
    do not refresh liveness — they record what was observed.
    """

    ts: float
    state: str | None
    triage: str | None
    health_category: str | None
    has_live_process: bool
    certainty: ObservationCertainty = ObservationCertainty.UNKNOWN
    """How certain this observation is."""

    evidence_source: str = ""
    """Which evidence source produced this observation (process, tmux, heartbeat, state_json)."""

    evidence_ids: Tuple[str, ...] = ()
    """Content-addressed evidence IDs backing this observation."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    _non_authoritative: bool = field(default=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "state": self.state,
            "triage": self.triage,
            "health_category": self.health_category,
            "has_live_process": self.has_live_process,
            "certainty": self.certainty.value,
            "evidence_source": self.evidence_source,
            "evidence_ids": list(self.evidence_ids),
            "detail": self.detail,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        certainty_raw = data.get("certainty", "unknown")
        try:
            certainty = ObservationCertainty(certainty_raw)
        except ValueError:
            certainty = ObservationCertainty.UNKNOWN

        return cls(
            ts=float(data["ts"]),
            state=data.get("state"),
            triage=data.get("triage"),
            health_category=data.get("health_category"),
            has_live_process=bool(data.get("has_live_process", False)),
            certainty=certainty,
            evidence_source=str(data.get("evidence_source", "")),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            detail=str(data.get("detail", "")),
            _non_authoritative=bool(data.get("_non_authoritative", True)),
        )

    @property
    def status(self) -> PlanStatus:
        """Derive a coarse lifecycle status from this observation.

        Tmux/session facts never escalate to RUNNING — only live process
        evidence can produce RUNNING status.
        """
        if self.certainty == ObservationCertainty.UNKNOWN:
            return PlanStatus.UNCERTAIN

        if self.has_live_process:
            return PlanStatus.RUNNING
        if self.state in _TERMINAL_SUCCESS_STATES:
            return PlanStatus.FINISHED
        if self.state in _TERMINAL_FAILURE_STATES:
            return PlanStatus.FAILED
        if self.state in _CANCELLED_STATES:
            return PlanStatus.CANCELLED
        if self.state in _REJECTED_STATES:
            return PlanStatus.REJECTED
        if self.state in {"blocked", "gated", "clarifying"} or self.health_category == "plan_issue":
            return PlanStatus.STUCK
        if self.triage == "disappeared":
            return PlanStatus.DISAPPEARED
        return PlanStatus.IDLE

    @property
    def is_authoritative_liveness(self) -> bool:
        """True only when this observation is directly observed live process evidence.

        Observer reads of tmux state, state.json, or indirect evidence
        are NOT authoritative liveness.
        """
        return (
            self.certainty == ObservationCertainty.OBSERVED
            and self.evidence_source == "process"
            and self.has_live_process
        )

    @classmethod
    def process_observation(
        cls,
        *,
        state: str | None = None,
        has_live_process: bool = False,
        triage: str | None = None,
        health_category: str | None = None,
        detail: str = "",
    ) -> "Observation":
        """Create an observation from process evidence."""
        return cls(
            ts=time.time(),
            state=state,
            triage=triage,
            health_category=health_category,
            has_live_process=has_live_process,
            certainty=ObservationCertainty.OBSERVED if has_live_process else ObservationCertainty.INFERRED,
            evidence_source="process",
            detail=detail,
        )

    @classmethod
    def tmux_observation(
        cls,
        *,
        state: str | None = None,
        session_names: Tuple[str, ...] = (),
        detail: str = "",
    ) -> "Observation":
        """Create an observation from tmux evidence.

        Tmux facts are correlated evidence ONLY — they never refresh liveness.
        ``has_live_process`` is always False for tmux observations.
        """
        return cls(
            ts=time.time(),
            state=state,
            triage=None,
            health_category=None,
            has_live_process=False,  # Tmux is never live process evidence
            certainty=ObservationCertainty.INFERRED,
            evidence_source="tmux",
            detail=detail or f"tmux sessions: {', '.join(session_names)}" if session_names else detail,
        )

    @classmethod
    def state_json_observation(
        cls,
        *,
        state: str | None = None,
        triage: str | None = None,
        health_category: str | None = None,
        detail: str = "",
    ) -> "Observation":
        """Create an observation from state.json evidence.

        state.json is a projection, not live evidence.
        """
        return cls(
            ts=time.time(),
            state=state,
            triage=triage,
            health_category=health_category,
            has_live_process=False,
            certainty=ObservationCertainty.INFERRED,
            evidence_source="state_json",
            detail=detail,
        )

    @classmethod
    def unknown_observation(cls, *, detail: str = "") -> "Observation":
        """Create an explicitly unknown observation."""
        return cls(
            ts=time.time(),
            state=None,
            triage=None,
            health_category=None,
            has_live_process=False,
            certainty=ObservationCertainty.UNKNOWN,
            evidence_source="",
            detail=detail or "could not determine plan state",
        )


# ── Transition ─────────────────────────────────────────────────────────────


@dataclass
class Transition:
    """A lifecycle change between two consecutive observations.

    Carries evidence basis so consumers know what triggered the transition.
    """

    plan_id: str
    previous_status: PlanStatus
    current_status: PlanStatus
    previous_state: str | None
    current_state: str | None
    ts: float
    evidence_source: str = ""
    """Evidence source that triggered this transition."""

    transition_certainty: ObservationCertainty = ObservationCertainty.UNKNOWN

    detail: str = ""

    _non_authoritative: bool = field(default=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "previous_status": self.previous_status.value,
            "current_status": self.current_status.value,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "ts": self.ts,
            "evidence_source": self.evidence_source,
            "transition_certainty": self.transition_certainty.value,
            "detail": self.detail,
            "_non_authoritative": self._non_authoritative,
        }

    @property
    def is_authoritative(self) -> bool:
        """True only when the transition is backed by directly observed process evidence."""
        return (
            self.transition_certainty == ObservationCertainty.OBSERVED
            and self.evidence_source == "process"
        )


# ── Registry entry ─────────────────────────────────────────────────────────


@dataclass
class RegistryEntry:
    plan_id: str
    first_seen: float
    last_seen: float
    last_state: str | None
    incident_count: int
    retry_count: int
    observations: list[Observation] = field(default_factory=list)

    # M9 additions
    last_certainty: ObservationCertainty = ObservationCertainty.UNKNOWN
    """Certainty of the most recent observation."""

    entry_digest: str = ""
    """Content-addressed entry identifier (computed on save)."""

    _non_authoritative: bool = field(default=True)

    @property
    def status(self) -> PlanStatus:
        """Derived status from the most recent observation."""
        last = self.last_observation()
        if last is None:
            return PlanStatus.UNCERTAIN
        return last.status

    @property
    def has_authoritative_liveness(self) -> bool:
        """True when the most recent observation is authoritative live process evidence."""
        last = self.last_observation()
        if last is None:
            return False
        return last.is_authoritative_liveness

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "last_state": self.last_state,
            "incident_count": self.incident_count,
            "retry_count": self.retry_count,
            "observations": [o.to_dict() for o in self.observations],
            "last_certainty": self.last_certainty.value,
            "entry_digest": self.entry_digest,
            "status": self.status.value,
            "has_authoritative_liveness": self.has_authoritative_liveness,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegistryEntry":
        observations = [Observation.from_dict(o) for o in data.get("observations", [])]
        last_certainty_raw = data.get("last_certainty", "unknown")
        try:
            last_certainty = ObservationCertainty(last_certainty_raw)
        except ValueError:
            last_certainty = ObservationCertainty.UNKNOWN

        return cls(
            plan_id=data["plan_id"],
            first_seen=float(data["first_seen"]),
            last_seen=float(data["last_seen"]),
            last_state=data.get("last_state"),
            incident_count=int(data.get("incident_count", 0)),
            retry_count=int(data.get("retry_count", 0)),
            observations=observations,
            last_certainty=last_certainty,
            entry_digest=str(data.get("entry_digest", "")),
            _non_authoritative=bool(data.get("_non_authoritative", True)),
        )

    def last_observation(self) -> Observation | None:
        return self.observations[-1] if self.observations else None

    def _compute_entry_digest(self) -> None:
        """Compute content-addressed entry digest from observations."""
        parts = "\x00".join(
            f"{o.ts}:{o.state}:{o.certainty.value}:{o.evidence_source}"
            for o in self.observations[-20:]  # Last 20 for stability
        )
        self.entry_digest = f"sha256:{hashlib.sha256(parts.encode('utf-8')).hexdigest()}"


# ── Watchdog registry ──────────────────────────────────────────────────────


class WatchdogRegistry:
    """Simple NDJSON registry persisting seen-plan history and observations.

    In M9, the registry:
    * Preserves diagnostics without refreshing liveness from observer reads.
    * Tracks observation certainty per entry.
    * Feeds typed uncertainty upstream so consumers distinguish concrete
      observations from inference.
    * Never escalates tmux/session facts into liveness authority.
    """

    MAX_OBSERVATIONS_PER_PLAN: int = 50

    def __init__(self, ndjson_path: str | Path) -> None:
        self._path = Path(ndjson_path)
        self._entries: dict[str, RegistryEntry] = {}
        self.load()

    def load(self) -> None:
        self._entries = {}
        if not self._path.exists():
            return
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entry = RegistryEntry.from_dict(data)
                self._entries[entry.plan_id] = entry
        except Exception:
            self._entries = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Compute digests before saving
        for entry in self._entries.values():
            entry._compute_entry_digest()
        lines = [json.dumps(e.to_dict()) + "\n" for e in self._entries.values()]
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(self._path)

    def update_seen(
        self,
        plans: Iterable[Any],
        now: float | None = None,
    ) -> None:
        now = now if now is not None else time.time()
        for plan in plans:
            plan_id = getattr(plan, "plan_id", str(plan))
            state = getattr(plan, "state", None)
            last_state = state.get("current_state") if isinstance(state, dict) else None
            existing = self._entries.get(plan_id)
            if existing is None:
                self._entries[plan_id] = RegistryEntry(
                    plan_id=plan_id,
                    first_seen=now,
                    last_seen=now,
                    last_state=last_state,
                    incident_count=0,
                    retry_count=0,
                    observations=[],
                )
            else:
                existing.last_seen = now
                existing.last_state = last_state

    def record_observation(
        self,
        plan_id: str,
        observation: Observation,
        now: float | None = None,
    ) -> None:
        """Append an observation to a plan's history, creating the entry if needed.

        Updates ``last_certainty`` from the observation's certainty field.
        Observer reads do NOT refresh liveness — they record what was observed.
        """
        now = now if now is not None else time.time()
        entry = self._entries.get(plan_id)
        if entry is None:
            entry = RegistryEntry(
                plan_id=plan_id,
                first_seen=now,
                last_seen=now,
                last_state=observation.state,
                incident_count=0,
                retry_count=0,
                observations=[],
                last_certainty=observation.certainty,
            )
            self._entries[plan_id] = entry
        entry.observations.append(observation)
        if len(entry.observations) > self.MAX_OBSERVATIONS_PER_PLAN:
            entry.observations = entry.observations[-self.MAX_OBSERVATIONS_PER_PLAN :]
        entry.last_seen = now
        entry.last_state = observation.state
        entry.last_certainty = observation.certainty

    def record_process_observation(
        self,
        plan_id: str,
        *,
        state: str | None = None,
        has_live_process: bool = False,
        triage: str | None = None,
        health_category: str | None = None,
        detail: str = "",
    ) -> None:
        """Record a process-derived observation.

        This is the ONLY observation kind that sets ``has_live_process=True``
        and produces authoritative liveness.
        """
        obs = Observation.process_observation(
            state=state,
            has_live_process=has_live_process,
            triage=triage,
            health_category=health_category,
            detail=detail,
        )
        self.record_observation(plan_id, obs)

    def record_tmux_observation(
        self,
        plan_id: str,
        *,
        state: str | None = None,
        session_names: Tuple[str, ...] = (),
        detail: str = "",
    ) -> None:
        """Record a tmux-derived observation.

        Tmux facts are correlated evidence only — they never refresh liveness.
        ``has_live_process`` is always False.
        """
        obs = Observation.tmux_observation(
            state=state,
            session_names=session_names,
            detail=detail,
        )
        self.record_observation(plan_id, obs)

    def record_unknown_observation(
        self,
        plan_id: str,
        *,
        detail: str = "",
    ) -> None:
        """Record an explicitly unknown observation."""
        obs = Observation.unknown_observation(detail=detail)
        self.record_observation(plan_id, obs)

    def compute_transitions(
        self,
        current_observations: dict[str, Observation],
        now: float | None = None,
    ) -> list[Transition]:
        """Compare current observations to the last recorded ones and emit transitions.

        Each transition carries the evidence source and certainty so consumers
        know whether it was triggered by process, tmux, or state_json evidence.
        """
        now = now if now is not None else time.time()
        transitions: list[Transition] = []

        for plan_id, observation in current_observations.items():
            entry = self._entries.get(plan_id)
            previous = entry.last_observation() if entry is not None else None
            if previous is None:
                transitions.append(
                    Transition(
                        plan_id=plan_id,
                        previous_status=PlanStatus.NEW,
                        current_status=observation.status,
                        previous_state=None,
                        current_state=observation.state,
                        ts=now,
                        evidence_source=observation.evidence_source,
                        transition_certainty=observation.certainty,
                        detail=f"first observation via {observation.evidence_source}",
                    )
                )
            elif previous.status != observation.status or previous.state != observation.state:
                transitions.append(
                    Transition(
                        plan_id=plan_id,
                        previous_status=previous.status,
                        current_status=observation.status,
                        previous_state=previous.state,
                        current_state=observation.state,
                        ts=now,
                        evidence_source=observation.evidence_source,
                        transition_certainty=observation.certainty,
                        detail=f"transition via {observation.evidence_source}",
                    )
                )

        # Plans that were observed before but are missing now.
        for plan_id, entry in self._entries.items():
            if plan_id in current_observations:
                continue
            previous = entry.last_observation()
            if previous is None:
                continue
            if previous.status != PlanStatus.DISAPPEARED:
                transitions.append(
                    Transition(
                        plan_id=plan_id,
                        previous_status=previous.status,
                        current_status=PlanStatus.DISAPPEARED,
                        previous_state=previous.state,
                        current_state=None,
                        ts=now,
                        evidence_source="",
                        transition_certainty=ObservationCertainty.INFERRED,
                        detail="plan disappeared from current observations",
                    )
                )

        return transitions

    def mark_disappeared(self, seen_before: Iterable[str], current: Iterable[str]) -> None:
        """Bump incident_count for plans that were seen before but are gone now."""
        before_set = set(seen_before)
        current_set = set(current)
        disappeared = before_set - current_set
        for plan_id in disappeared:
            entry = self._entries.get(plan_id)
            if entry is not None:
                entry.incident_count += 1

    def bump_retry(self, plan_id: str) -> None:
        entry = self._entries.get(plan_id)
        if entry is not None:
            entry.retry_count += 1

    def get(self, plan_id: str) -> RegistryEntry | None:
        return self._entries.get(plan_id)

    def get_status(self, plan_id: str) -> PlanStatus:
        """Return the derived status for a plan, or UNCERTAIN."""
        entry = self._entries.get(plan_id)
        if entry is None:
            return PlanStatus.UNCERTAIN
        return entry.status

    def get_certainty(self, plan_id: str) -> ObservationCertainty:
        """Return the certainty of the last observation, or UNKNOWN."""
        entry = self._entries.get(plan_id)
        if entry is None:
            return ObservationCertainty.UNKNOWN
        last = entry.last_observation()
        if last is None:
            return ObservationCertainty.UNKNOWN
        return last.certainty

    def liveness_is_authoritative(self, plan_id: str) -> bool:
        """True when the plan has authoritative process-based liveness evidence."""
        entry = self._entries.get(plan_id)
        if entry is None:
            return False
        return entry.has_authoritative_liveness

    def entries_with_certainty(
        self,
        certainty: ObservationCertainty,
    ) -> Tuple[RegistryEntry, ...]:
        """Return entries whose last observation has the given certainty."""
        return tuple(
            e for e in self._entries.values()
            if e.last_certainty == certainty
        )

    def __iter__(self):
        return iter(self._entries.values())


__all__ = [
    # ── Types ──
    "ObservationCertainty",
    "Observation",
    "PlanStatus",
    "RegistryEntry",
    "Transition",
    "WatchdogRegistry",
]
