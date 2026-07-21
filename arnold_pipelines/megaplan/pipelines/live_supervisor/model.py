"""Typed models for the live-supervisor pipeline and watchdog daemon."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Mapping


class HealthCategory(str, Enum):
    ALL_GOOD = "all_good"
    FALSE_STALL = "false_stall"
    HARNESS_ISSUE = "harness_issue"
    PLAN_ISSUE = "plan_issue"
    ENVIRONMENT_ISSUE = "environment_issue"
    DEAD_OR_DISAPPEARED = "dead_or_disappeared"
    UNKNOWN = "unknown"


class Triage(str, Enum):
    LIVE = "live"
    RECENT = "recent"
    MAYBE_LIVE = "maybe_live"
    STALE = "stale"


@dataclass(frozen=True)
class CheckFinding:
    scope: Literal["plan", "repo"]
    check: str
    status: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"scope": self.scope, "check": self.check, "status": self.status, "message": self.message}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CheckFinding":
        return cls(
            scope=data["scope"],
            check=data["check"],
            status=data["status"],
            message=data["message"],
        )


@dataclass(frozen=True)
class PlanEntry:
    plan_id: str
    plan_name: str
    plan_dir: str
    repo_path: str
    state: dict[str, Any]
    chain_spec_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_name": self.plan_name,
            "plan_dir": self.plan_dir,
            "repo_path": self.repo_path,
            "state": self.state,
            "chain_spec_path": self.chain_spec_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlanEntry":
        return cls(
            plan_id=data["plan_id"],
            plan_name=data["plan_name"],
            plan_dir=data["plan_dir"],
            repo_path=data["repo_path"],
            state=dict(data.get("state") or {}),
            chain_spec_path=data.get("chain_spec_path"),
        )


@dataclass(frozen=True)
class SignalBundle:
    liveness: str
    liveness_reason: str
    block_details: dict[str, Any]
    doctor_findings: tuple[CheckFinding, ...]
    has_in_flight_llm: bool = False
    last_event_age_seconds: float | None = None
    degraded: bool = False
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "liveness": self.liveness,
            "liveness_reason": self.liveness_reason,
            "block_details": self.block_details,
            "doctor_findings": [f.to_dict() for f in self.doctor_findings],
            "has_in_flight_llm": self.has_in_flight_llm,
            "last_event_age_seconds": self.last_event_age_seconds,
            "degraded": self.degraded,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SignalBundle":
        findings = data.get("doctor_findings") or []
        return cls(
            liveness=data["liveness"],
            liveness_reason=data["liveness_reason"],
            block_details=dict(data.get("block_details") or {}),
            doctor_findings=tuple(CheckFinding.from_dict(f) for f in findings),
            has_in_flight_llm=bool(data.get("has_in_flight_llm", False)),
            last_event_age_seconds=data.get("last_event_age_seconds"),
            degraded=bool(data.get("degraded", False)),
            failure_reason=data.get("failure_reason"),
        )


@dataclass(frozen=True)
class Incident:
    plan_entry: PlanEntry
    signals: SignalBundle
    triage: Triage
    # M9 — display-only liveness correlation summary. Never authority: a live
    # process or fresh heartbeat is *evidence* of an in-flight attempt, never a
    # success/repair verdict. Populated by the watchdog snapshot builder when
    # canonical WBC attempt identity is supplied; defaults to empty so legacy
    # snapshots round-trip unchanged.
    liveness_authority: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "plan_entry": self.plan_entry.to_dict(),
            "signals": self.signals.to_dict(),
            "triage": self.triage.value,
        }
        if self.liveness_authority:
            result["liveness_authority"] = dict(self.liveness_authority)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Incident":
        return cls(
            plan_entry=PlanEntry.from_dict(data["plan_entry"]),
            signals=SignalBundle.from_dict(data["signals"]),
            triage=Triage(data["triage"]),
            liveness_authority=dict(data.get("liveness_authority") or {}),
        )


@dataclass(frozen=True)
class Diagnosis:
    health_category: HealthCategory
    findings: tuple[CheckFinding, ...]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_category": self.health_category.value,
            "findings": [f.to_dict() for f in self.findings],
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Diagnosis":
        findings = data.get("findings") or []
        return cls(
            health_category=HealthCategory(data["health_category"]),
            findings=tuple(CheckFinding.from_dict(f) for f in findings),
            reasoning=data["reasoning"],
        )


@dataclass(frozen=True)
class RepairRecommendation:
    command: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "context": self.context}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RepairRecommendation":
        return cls(command=data["command"], context=dict(data.get("context") or {}))


@dataclass(frozen=True)
class RepairAction:
    command: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "context": self.context}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RepairAction":
        return cls(command=data["command"], context=dict(data.get("context") or {}))


@dataclass(frozen=True)
class AllowlistVerdict:
    allowed: bool
    reason: str
    action: RepairAction | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"allowed": self.allowed, "reason": self.reason}
        if self.action is not None:
            result["action"] = self.action.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AllowlistVerdict":
        action = data.get("action")
        return cls(
            allowed=bool(data["allowed"]),
            reason=data["reason"],
            action=RepairAction.from_dict(action) if action else None,
        )


@dataclass(frozen=True)
class Snapshot:
    scan_ts_utc: str
    plans: tuple[PlanEntry, ...]
    incidents: tuple[Incident, ...]
    # M9 — display-only annotations. ``source_cursor_vector`` records the
    # canonical source cursors (ledger / projection history) the snapshot was
    # built against; ``liveness_authority`` summarizes the per-plan liveness
    # correlation. Both are *evidence only* — they never feed dispatch,
    # completion, cancellation, publication, or delivery. Default to empty so
    # legacy snapshots round-trip unchanged.
    source_cursor_vector: dict[str, Any] = field(default_factory=dict)
    liveness_authority: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "scan_ts_utc": self.scan_ts_utc,
            "plans": [p.to_dict() for p in self.plans],
            "incidents": [i.to_dict() for i in self.incidents],
        }
        if self.source_cursor_vector:
            result["source_cursor_vector"] = dict(self.source_cursor_vector)
        if self.liveness_authority:
            result["liveness_authority"] = dict(self.liveness_authority)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Snapshot":
        return cls(
            scan_ts_utc=data["scan_ts_utc"],
            plans=tuple(PlanEntry.from_dict(p) for p in data.get("plans", [])),
            incidents=tuple(Incident.from_dict(i) for i in data.get("incidents", [])),
            source_cursor_vector=dict(data.get("source_cursor_vector") or {}),
            liveness_authority=dict(data.get("liveness_authority") or {}),
        )

    @classmethod
    def now(cls, plans: tuple[PlanEntry, ...], incidents: tuple[Incident, ...]) -> "Snapshot":
        return cls(
            scan_ts_utc=datetime.now(timezone.utc).isoformat(),
            plans=plans,
            incidents=incidents,
        )


__all__ = [
    "HealthCategory",
    "Triage",
    "CheckFinding",
    "PlanEntry",
    "SignalBundle",
    "Incident",
    "Diagnosis",
    "RepairRecommendation",
    "RepairAction",
    "AllowlistVerdict",
    "Snapshot",
]
