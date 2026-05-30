"""Sprint 1 storage extensions and Plan compatibility models."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import ConfigDict, Field, field_validator

from megaplan.types import (
    ActivePhase,
    ClarificationRecord,
    HistoryEntry,
    LastGateRecord,
    PlanConfig,
    PlanMeta,
    PlanState,
    PlanVersionRecord,
    SessionInfo,
    validate_plan_current_state,
)

from .base import HomeBackend, NormalizedDict, NormalizedStringList, StorageModel, utc_now

MigrationPhase = Literal[
    "planning",
    "copying_meta",
    "copying_blobs",
    "verifying",
    "cutting_over",
    "tombstoning",
    "complete",
    "aborted",
]
PlanArtifactKind = Literal["markdown", "json", "jsonl", "raw_text", "lock", "derived"]
PlanArtifactRole = Literal[
    "plan_version",
    "plan_meta",
    "critique",
    "gate",
    "gate_signals",
    "finalize",
    "finalize_snapshot",
    "execution_batch",
    "execution",
    "execution_audit",
    "execution_checkpoint",
    "execution_trace",
    "faults",
    "receipt",
    "review",
    "raw_worker_output",
    "template",
    "derived_final",
    "prep",
    "research",
    "directors_notes",
    "human_verifications",
    "tiebreaker_decisions",
    "tiebreaker_payload",
    "feedback",
]
WorkerKind = Literal["local_cli", "cloud_worker", "auto_driver"]
ScheduledJobStatus = Literal["pending", "claimed", "fired", "cancelled", "failed"]
ScheduledJobType = Literal["cloud_check", "deferred_turn", "heartbeat", "confirmation_expiry"]
CloudRunStatus = Literal["queued", "starting", "running", "blocked", "failed", "gate-needed", "completed", "cancelled", "unknown"]
CloudRunOperation = Literal["chain", "bootstrap", "resume", "sprint", "status"]
ControlIntent = Literal[
    "run_sprint",
    "pause_plan",
    "resume_plan",
    "approve_gate",
    "reject_gate",
    "cancel_run",
    "manual_fix",
    "request_inspect",
]
ProgressEventKind = Literal[
    "phase_start",
    "phase_end",
    "batch_complete",
    "gate_pending",
    "gate_resolved",
    "plan_done",
    "plan_failed",
    "execution_blocked",
    "manual_fix_attached",
]
AutomationActorKind = Literal["cli", "cloud_worker", "ci", "admin"]


class MigrationRun(StorageModel):
    id: str
    epic_id: str
    source_backend: HomeBackend
    target_backend: HomeBackend
    phase: MigrationPhase
    manifest: NormalizedDict = Field(default_factory=dict)
    copied_ids: NormalizedDict = Field(default_factory=dict)
    blob_copy_progress: NormalizedDict = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    holder_id: str
    expires_at: datetime


class ExecutionLease(StorageModel):
    plan_id: str
    epic_id: str | None = None
    holder_id: str
    phase: str
    worker_kind: WorkerKind
    acquired_at: datetime = Field(default_factory=utc_now)
    heartbeat_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class PlanArtifact(StorageModel):
    name: str
    kind: PlanArtifactKind
    role: PlanArtifactRole
    version: int | None = None
    batch: int | None = None
    phase: str | None = None
    content_text: str | None = None
    content_json: dict[str, Any] | list[Any] | None = None
    content_base64: str | None = None
    sha256: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ControlMessage(StorageModel):
    id: str
    epic_id: str
    actor_id: str
    intent: ControlIntent
    target_id: str
    payload: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str
    created_at: datetime = Field(default_factory=utc_now)
    processor_id: str | None = None
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    result: NormalizedDict | None = None


class ProgressEvent(StorageModel):
    id: str
    epic_id: str
    plan_id: str | None = None
    sprint_id: str | None = None
    idempotency_key: str | None = None
    kind: ProgressEventKind
    summary: str
    details: NormalizedDict = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)


class ScheduledJob(StorageModel):
    id: str
    job_type: ScheduledJobType
    status: ScheduledJobStatus = "pending"
    conversation_id: str | None = None
    cloud_run_id: str | None = None
    epic_id: str | None = None
    payload: NormalizedDict = Field(default_factory=dict)
    scheduled_for: datetime
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    fired_at: datetime | None = None
    cancelled_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CloudRun(StorageModel):
    id: str
    operation: CloudRunOperation
    status: CloudRunStatus = "queued"
    conversation_id: str | None = None
    epic_id: str | None = None
    sprint_id: str | None = None
    plan_id: str | None = None
    provider: str | None = None
    provider_run_id: str | None = None
    target_id: str | None = None
    command_summary: str | None = None
    progress_summary: str | None = None
    last_status: NormalizedDict = Field(default_factory=dict)
    metadata: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str | None = None
    started_by_actor_id: str | None = None
    started_at: datetime | None = None
    last_checked_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AutomationActor(StorageModel):
    id: str
    name: str
    granted_epic_ids: Literal["*"] | NormalizedStringList
    actor_kind: AutomationActorKind
    created_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime | None = None


class Plan(StorageModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=True)

    id: str
    name: str
    epic_id: str | None = None
    sprint_id: str | None = None
    revision: int
    schema_version: int = 0
    idea: str
    current_state: str
    iteration: int
    config: dict[str, Any]
    sessions: dict[str, dict[str, Any]]
    plan_versions: list[dict[str, Any]]
    history: list[dict[str, Any]]
    meta: dict[str, Any]
    last_gate: dict[str, Any]
    active_step: dict[str, Any] | None = None
    clarification: dict[str, Any] | None = None
    latest_finalize: dict[str, Any] | None = None
    latest_review: dict[str, Any] | None = None
    latest_execution: dict[str, Any] | None = None
    latest_failure: dict[str, Any] | None = None
    resume_cursor: dict[str, Any] | None = None
    artifacts: list[PlanArtifact] = Field(default_factory=list)
    feedback: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("current_state")
    @classmethod
    def _validate_current_state(cls, value: str) -> str:
        return validate_plan_current_state(value)

    @classmethod
    def from_plan_state(
        cls,
        state: PlanState | dict[str, Any],
        *,
        plan_id: str | None = None,
        epic_id: str | None = None,
        sprint_id: str | None = None,
        revision: int = 0,
        artifacts: list[PlanArtifact] | None = None,
        latest_finalize: dict[str, Any] | None = None,
        latest_review: dict[str, Any] | None = None,
        latest_execution: dict[str, Any] | None = None,
        latest_failure: dict[str, Any] | None = None,
        resume_cursor: dict[str, Any] | None = None,
        feedback: dict[str, Any] | None = None,
        updated_at: datetime | None = None,
    ) -> Plan:
        raw = deepcopy(dict(state))
        created_at = raw["created_at"]
        plan = cls(
            id=plan_id or raw["name"],
            name=raw["name"],
            epic_id=epic_id,
            sprint_id=sprint_id,
            revision=revision,
            idea=raw["idea"],
            current_state=raw["current_state"],
            iteration=raw["iteration"],
            config=raw["config"],
            sessions=raw["sessions"],
            plan_versions=raw["plan_versions"],
            history=raw["history"],
            meta=raw["meta"],
            last_gate=raw["last_gate"],
            active_step=raw.get("active_step"),
            clarification=raw.get("clarification"),
            latest_finalize=latest_finalize,
            latest_review=latest_review,
            latest_execution=latest_execution,
            latest_failure=latest_failure if latest_failure is not None else raw.get("latest_failure"),
            resume_cursor=resume_cursor if resume_cursor is not None else raw.get("resume_cursor"),
            artifacts=artifacts or [],
            feedback=feedback,
            created_at=created_at,
            updated_at=updated_at or created_at,
        )
        return plan

    @classmethod
    def from_state(cls, state: PlanState | dict[str, Any], **kwargs: Any) -> Plan:
        return cls.from_plan_state(state, **kwargs)

    def to_plan_state(self) -> PlanState:
        state: PlanState = {
            "name": self.name,
            "idea": self.idea,
            "current_state": self.current_state,
            "iteration": self.iteration,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "config": cast(PlanConfig, deepcopy(self.config)),
            "sessions": cast(dict[str, SessionInfo], deepcopy(self.sessions)),
            "plan_versions": cast(list[PlanVersionRecord], deepcopy(self.plan_versions)),
            "history": cast(list[HistoryEntry], deepcopy(self.history)),
            "meta": cast(PlanMeta, deepcopy(self.meta)),
            "last_gate": cast(LastGateRecord, deepcopy(self.last_gate)),
            "schema_version": self.schema_version,
        }
        if self.active_step is not None:
            state["active_step"] = cast(ActivePhase, deepcopy(self.active_step))
        if self.clarification is not None:
            state["clarification"] = cast(ClarificationRecord, deepcopy(self.clarification))
        if self.latest_failure is not None:
            state["latest_failure"] = deepcopy(self.latest_failure)
        if self.resume_cursor is not None:
            state["resume_cursor"] = deepcopy(self.resume_cursor)
        return state
