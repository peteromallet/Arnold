"""Steps 14 and 15A: Event-driven recovery and SLO measurement.

Step 14: Join durable blocker/process-exit events to one exact-identity
repair request.  Record event, request, claim, terminal/escalation
timestamps and denominator membership.  Test SLO p95 target of 300s.

Step 15A: Persist parser loss, classification incompatibility, launcher
failure, and missing-child failures as durable failed occurrences so
they are visible to recovery joins and the six-hour reconciliation
backstop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

# ── Recovery event kinds ─────────────────────────────────────────────────────


class RecoveryEventKind(str, Enum):
    """Kinds of durable recovery events."""

    BLOCKER_DETECTED = "blocker_detected"
    """A blocker was detected (e.g. process exit, stuck task)."""

    PROCESS_EXIT = "process_exit"
    """A monitored process exited."""

    REPAIR_REQUEST_ENQUEUED = "repair_request_enqueued"
    """A repair request was enqueued for this recovery event."""

    REPAIR_CLAIMED = "repair_claimed"
    """A repair request was claimed by a worker."""

    REPAIR_TERMINAL = "repair_terminal"
    """A repair reached a terminal state (fixed, escalated, etc.)."""

    REPAIR_ESCALATED = "repair_escalated"
    """A repair was escalated to human review."""

    SLO_EXCEEDED = "slo_exceeded"
    """The p95 SLO target (300s) was exceeded."""

    PARSER_LOSS = "parser_loss"
    """A parser failed to produce output (Step 15A)."""

    CLASSIFICATION_INCOMPATIBLE = "classification_incompatible"
    """Classification was incompatible with expected schema (Step 15A)."""

    LAUNCHER_FAILURE = "launcher_failure"
    """A launcher failed to start (Step 15A)."""

    MISSING_CHILD = "missing_child"
    """A required child process/artifact is missing (Step 15A)."""


# ── Recovery event record ────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecoveryEvent:
    """A single durable recovery event recorded for join and SLO measurement."""

    event_id: str
    """Stable event identity."""

    kind: RecoveryEventKind
    """What kind of recovery event this is."""

    occurred_at: str
    """ISO-8601 timestamp when the event was first observed."""

    recorded_at: str
    """ISO-8601 timestamp when the event was recorded."""

    request_id: str = ""
    """Linked repair request id, if any."""

    claim_time: str = ""
    """ISO-8601 timestamp when the repair was claimed, if any."""

    terminal_time: str = ""
    """ISO-8601 timestamp when the repair reached terminal state, if any."""

    escalation_time: str = ""
    """ISO-8601 timestamp when the repair was escalated, if any."""

    slo_target_seconds: float = 300.0
    """SLO target in seconds for this event (default 300s for p95)."""

    denominator_group: str = ""
    """SLO denominator membership group (e.g. parser, launcher, classification)."""

    slo_exceeded: bool = False
    """True if the event-to-terminal duration exceeded the SLO target."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional event metadata."""

    @property
    def event_to_request_seconds(self) -> float | None:
        """Seconds from event occurrence to request enqueue."""
        if not self.request_id:
            return None
        return _duration_seconds(self.occurred_at, self.recorded_at)

    @property
    def event_to_claim_seconds(self) -> float | None:
        """Seconds from event occurrence to claim."""
        if not self.claim_time:
            return None
        return _duration_seconds(self.occurred_at, self.claim_time)

    @property
    def event_to_terminal_seconds(self) -> float | None:
        """Seconds from event occurrence to terminal resolution."""
        if not self.terminal_time:
            return None
        return _duration_seconds(self.occurred_at, self.terminal_time)

    @property
    def total_latency_seconds(self) -> float | None:
        """Total latency: event → terminal or escalation."""
        end = self.terminal_time or self.escalation_time
        if not end:
            return None
        return _duration_seconds(self.occurred_at, end)


# ── Recovery event store ─────────────────────────────────────────────────────


class RecoveryEventStore:
    """In-memory store for recovery events used in joins and SLO measurement.

    In production this would be backed by durable storage.  For M10
    it is in-memory with a persistence interface that the six-hour
    reconciliation backstop can query.
    """

    def __init__(self) -> None:
        self._events: dict[str, RecoveryEvent] = {}
        self._by_request: dict[str, list[str]] = {}  # request_id → event_ids
        self._by_kind: dict[RecoveryEventKind, list[str]] = {}

    # ── record ──────────────────────────────────────────────────────────

    def record(self, event: RecoveryEvent) -> None:
        """Record a recovery event."""
        self._events[event.event_id] = event

        if event.request_id:
            joined_ids = self._by_request.setdefault(event.request_id, [])
            source_event_id = event.metadata.get("source_event_id")
            if (
                isinstance(source_event_id, str)
                and source_event_id in self._events
                and source_event_id not in joined_ids
            ):
                joined_ids.append(source_event_id)
            if event.event_id not in joined_ids:
                joined_ids.append(event.event_id)

        self._by_kind.setdefault(event.kind, []).append(event.event_id)

    # ── join ─────────────────────────────────────────────────────────────

    def join_events_to_request(
        self, request_id: str
    ) -> list[RecoveryEvent]:
        """Return all recovery events joined to *request_id*."""
        event_ids = self._by_request.get(request_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def join_blocker_to_request(
        self, request_id: str
    ) -> Optional[RecoveryEvent]:
        """Return the blocker_detected or process_exit event for a request."""
        event_ids = self._by_request.get(request_id, [])
        for eid in event_ids:
            ev = self._events.get(eid)
            if ev is not None and ev.kind in (
                RecoveryEventKind.BLOCKER_DETECTED,
                RecoveryEventKind.PROCESS_EXIT,
            ):
                return ev
        return None

    # ── query ────────────────────────────────────────────────────────────

    def events_by_kind(
        self, kind: RecoveryEventKind
    ) -> list[RecoveryEvent]:
        """Return all events of a given kind."""
        event_ids = self._by_kind.get(kind, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def count_by_kind(self, kind: RecoveryEventKind) -> int:
        """Count events of a given kind."""
        return len(self._by_kind.get(kind, []))

    # ── SLO ──────────────────────────────────────────────────────────────

    def slo_denominator(self, group: str | None = None) -> int:
        """Return the SLO denominator for a group (or all events)."""
        if group is None:
            return len(self._events)
        return sum(
            1
            for ev in self._events.values()
            if ev.denominator_group == group
        )

    def slo_violations(
        self, group: str | None = None, target_seconds: float | None = None
    ) -> list[RecoveryEvent]:
        """Return events that exceeded their SLO target."""
        target = target_seconds or 300.0
        result: list[RecoveryEvent] = []
        for ev in self._events.values():
            if group is not None and ev.denominator_group != group:
                continue
            lat = ev.total_latency_seconds
            if lat is not None and lat > target:
                result.append(ev)
        return result

    def p95_latency(
        self, group: str | None = None
    ) -> float | None:
        """Return the p95 latency in seconds for a group."""
        latencies = sorted(
            lat
            for ev in self._events.values()
            if (group is None or ev.denominator_group == group)
            and (lat := ev.total_latency_seconds) is not None
        )
        if not latencies:
            return None
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    def all_events(self) -> list[RecoveryEvent]:
        """Return all recorded events."""
        return list(self._events.values())


# ── Step 14: recovery event builder ──────────────────────────────────────────


class RecoveryEventBuilder:
    """Builds recovery events with exact identity joins and SLO timestamps.

    Step 14: Joins durable blocker/process-exit events to one exact-identity
    request.  Records event, request, claim, terminal/escalation timestamps
    and denominator membership.
    """

    @staticmethod
    def blocker_detected(
        *,
        blocker_id: str,
        session: str,
        failure_kind: str,
        phase_or_step: str = "",
        denominator_group: str = "",
    ) -> RecoveryEvent:
        """Record a blocker_detected event."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"blocker-{blocker_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.BLOCKER_DETECTED,
            occurred_at=now,
            recorded_at=now,
            denominator_group=denominator_group or f"blocker:{failure_kind}",
            metadata={
                "blocker_id": blocker_id,
                "session": session,
                "failure_kind": failure_kind,
                "phase_or_step": phase_or_step,
            },
        )

    @staticmethod
    def process_exit(
        *,
        process_id: str,
        exit_code: int,
        session: str = "",
        denominator_group: str = "",
    ) -> RecoveryEvent:
        """Record a process_exit event."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"exit-{process_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.PROCESS_EXIT,
            occurred_at=now,
            recorded_at=now,
            denominator_group=denominator_group or f"process:{process_id}",
            metadata={
                "process_id": process_id,
                "exit_code": exit_code,
                "session": session,
            },
        )

    @staticmethod
    def request_enqueued(
        *,
        event: RecoveryEvent,
        request_id: str,
    ) -> RecoveryEvent:
        """Record that a repair request was enqueued for *event*."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"enqueued-{request_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.REPAIR_REQUEST_ENQUEUED,
            occurred_at=event.occurred_at,
            recorded_at=now,
            request_id=request_id,
            denominator_group=event.denominator_group,
            metadata={"source_event_id": event.event_id},
        )

    @staticmethod
    def repair_claimed(
        *,
        event: RecoveryEvent,
        request_id: str,
        claimant: str = "",
    ) -> RecoveryEvent:
        """Record that a repair was claimed."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"claimed-{request_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.REPAIR_CLAIMED,
            occurred_at=event.occurred_at,
            recorded_at=now,
            request_id=request_id,
            claim_time=now,
            denominator_group=event.denominator_group,
            metadata={"claimant": claimant},
        )

    @staticmethod
    def repair_terminal(
        *,
        event: RecoveryEvent,
        request_id: str,
        outcome: str,
    ) -> RecoveryEvent:
        """Record that a repair reached a terminal state."""
        now = _utc_now_iso()
        total_lat = _duration_seconds(event.occurred_at, now)
        slo_exceeded = total_lat is not None and total_lat > 300.0
        return RecoveryEvent(
            event_id=f"terminal-{request_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.REPAIR_TERMINAL,
            occurred_at=event.occurred_at,
            recorded_at=now,
            request_id=request_id,
            terminal_time=now,
            slo_exceeded=slo_exceeded,
            denominator_group=event.denominator_group,
            metadata={"outcome": outcome, "total_latency_seconds": total_lat},
        )

    @staticmethod
    def repair_escalated(
        *,
        event: RecoveryEvent,
        request_id: str,
        reason: str,
    ) -> RecoveryEvent:
        """Record that a repair was escalated to human review."""
        now = _utc_now_iso()
        total_lat = _duration_seconds(event.occurred_at, now)
        slo_exceeded = total_lat is not None and total_lat > 300.0
        return RecoveryEvent(
            event_id=f"escalated-{request_id}-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.REPAIR_ESCALATED,
            occurred_at=event.occurred_at,
            recorded_at=now,
            request_id=request_id,
            escalation_time=now,
            slo_exceeded=slo_exceeded,
            denominator_group=event.denominator_group,
            metadata={"reason": reason, "total_latency_seconds": total_lat},
        )

    # ── Step 15A: failure persistence builders ───────────────────────────

    @staticmethod
    def parser_loss(
        *,
        session: str,
        phase_or_step: str = "",
        detail: str = "",
    ) -> RecoveryEvent:
        """Step 15A: persist a parser-loss failed occurrence."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"parser-loss-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.PARSER_LOSS,
            occurred_at=now,
            recorded_at=now,
            denominator_group="parser",
            metadata={
                "session": session,
                "phase_or_step": phase_or_step,
                "detail": detail,
            },
        )

    @staticmethod
    def classification_incompatible(
        *,
        session: str,
        phase_or_step: str = "",
        expected_schema: str = "",
        observed: str = "",
    ) -> RecoveryEvent:
        """Step 15A: persist a classification incompatibility failed occurrence."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"class-incompat-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.CLASSIFICATION_INCOMPATIBLE,
            occurred_at=now,
            recorded_at=now,
            denominator_group="classification",
            metadata={
                "session": session,
                "phase_or_step": phase_or_step,
                "expected_schema": expected_schema,
                "observed": observed,
            },
        )

    @staticmethod
    def launcher_failure(
        *,
        session: str,
        launcher_name: str = "",
        exit_code: int | None = None,
        detail: str = "",
    ) -> RecoveryEvent:
        """Step 15A: persist a launcher failure failed occurrence."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"launcher-fail-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.LAUNCHER_FAILURE,
            occurred_at=now,
            recorded_at=now,
            denominator_group="launcher",
            metadata={
                "session": session,
                "launcher_name": launcher_name,
                "exit_code": exit_code,
                "detail": detail,
            },
        )

    @staticmethod
    def missing_child(
        *,
        session: str,
        child_id: str = "",
        expected_path: str = "",
        detail: str = "",
    ) -> RecoveryEvent:
        """Step 15A: persist a missing-child failed occurrence."""
        now = _utc_now_iso()
        return RecoveryEvent(
            event_id=f"missing-child-{int(time.time() * 1_000_000)}",
            kind=RecoveryEventKind.MISSING_CHILD,
            occurred_at=now,
            recorded_at=now,
            denominator_group="child",
            metadata={
                "session": session,
                "child_id": child_id,
                "expected_path": expected_path,
                "detail": detail,
            },
        )


# ── Helper functions ─────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    """RFC 3339 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _duration_seconds(start: str, end: str) -> float | None:
    """Compute duration in seconds between two ISO-8601 timestamps."""
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return (e - s).total_seconds()
    except (ValueError, TypeError):
        return None


__all__ = [
    "RecoveryEventKind",
    "RecoveryEvent",
    "RecoveryEventStore",
    "RecoveryEventBuilder",
]
