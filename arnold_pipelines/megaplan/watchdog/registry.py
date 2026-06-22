"""NDJSON registry of seen plans for the live watchdog."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


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


@dataclass
class Observation:
    """A single watchdog observation of a plan."""

    ts: float
    state: str | None
    triage: str | None
    health_category: str | None
    has_live_process: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "state": self.state,
            "triage": self.triage,
            "health_category": self.health_category,
            "has_live_process": self.has_live_process,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        return cls(
            ts=float(data["ts"]),
            state=data.get("state"),
            triage=data.get("triage"),
            health_category=data.get("health_category"),
            has_live_process=bool(data.get("has_live_process", False)),
        )

    @property
    def status(self) -> PlanStatus:
        """Derive a coarse lifecycle status from this observation."""
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


@dataclass
class Transition:
    """A lifecycle change between two consecutive observations."""

    plan_id: str
    previous_status: PlanStatus
    current_status: PlanStatus
    previous_state: str | None
    current_state: str | None
    ts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "previous_status": self.previous_status.value,
            "current_status": self.current_status.value,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "ts": self.ts,
        }


@dataclass
class RegistryEntry:
    plan_id: str
    first_seen: float
    last_seen: float
    last_state: str | None
    incident_count: int
    retry_count: int
    observations: list[Observation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "last_state": self.last_state,
            "incident_count": self.incident_count,
            "retry_count": self.retry_count,
            "observations": [o.to_dict() for o in self.observations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegistryEntry":
        return cls(
            plan_id=data["plan_id"],
            first_seen=float(data["first_seen"]),
            last_seen=float(data["last_seen"]),
            last_state=data.get("last_state"),
            incident_count=int(data.get("incident_count", 0)),
            retry_count=int(data.get("retry_count", 0)),
            observations=[Observation.from_dict(o) for o in data.get("observations", [])],
        )

    def last_observation(self) -> Observation | None:
        return self.observations[-1] if self.observations else None


class WatchdogRegistry:
    """Simple NDJSON registry persisting seen-plan history and observations."""

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
        """Append an observation to a plan's history, creating the entry if needed."""
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
            )
            self._entries[plan_id] = entry
        entry.observations.append(observation)
        if len(entry.observations) > self.MAX_OBSERVATIONS_PER_PLAN:
            entry.observations = entry.observations[-self.MAX_OBSERVATIONS_PER_PLAN :]
        entry.last_seen = now
        entry.last_state = observation.state

    def compute_transitions(
        self,
        current_observations: dict[str, Observation],
        now: float | None = None,
    ) -> list[Transition]:
        """Compare current observations to the last recorded ones and emit transitions."""
        now = now if now is not None else time.time()
        transitions: list[Transition] = []

        for plan_id, observation in current_observations.items():
            entry = self._entries.get(plan_id)
            previous = entry.last_observation() if entry is not None else None
            if previous is None:
                # First observation: transition from implicit "new" status.
                transitions.append(
                    Transition(
                        plan_id=plan_id,
                        previous_status=PlanStatus.NEW,
                        current_status=observation.status,
                        previous_state=None,
                        current_state=observation.state,
                        ts=now,
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

    def __iter__(self):
        return iter(self._entries.values())


__all__ = [
    "Observation",
    "PlanStatus",
    "RegistryEntry",
    "Transition",
    "WatchdogRegistry",
]
