"""Core storage contracts, record shapes, and compatibility helpers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
import hashlib
import re
from types import TracebackType
from typing import Any, Literal, Mapping, Protocol, Sequence, TypeAlias, runtime_checkable

from pydantic import Field

from megaplan.schemas import (
    AutomationActor,
    BotTurn,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    Epic,
    EpicEvent,
    EpicLock,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    Plan,
    ProgressEvent,
    SecondOpinion,
    Sprint,
    SprintItem,
    StorageModel,
    SystemLog,
    ToolCall,
)
from megaplan.schemas.base import NormalizedDict, utc_now

Backend = Literal["file", "db"]
JSONDict: TypeAlias = dict[str, Any]
_IDEMPOTENCY_PART_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def deterministic_idempotency_key(*parts: object) -> str:
    """Build a stable, readable idempotency key from caller-owned values."""
    raw = ":".join(str(part) for part in parts if part is not None)
    slug = _IDEMPOTENCY_PART_RE.sub("-", raw).strip("-") or "operation"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{slug}:{digest}"


class StoreError(RuntimeError):
    """Base exception for store-contract failures."""


class RevisionConflict(StoreError):
    """Raised when an optimistic-concurrency write sees a stale revision."""


class LockConflict(StoreError):
    """Raised when an epic lock is held by another actor."""


class LeaseConflict(StoreError):
    """Raised when an execution lease is already held."""


class ChecklistItemInput(StorageModel):
    id: str | None = None
    content: str
    status: str = "open"
    position: int | None = Field(default=None, gt=0)
    source: str = "bot_inferred"
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class SprintItemInput(StorageModel):
    id: str | None = None
    content: str
    estimated_complexity: str = "medium"
    status: str = "open"
    source_section: str | None = None
    position: int | None = Field(default=None, gt=0)
    created_at: datetime | None = None


class EpicSummary(Epic):
    snippet: str | None = None
    rank: float | int | None = None


class MessageSearchHit(Message):
    snippet: str | None = None
    rank: float | int | None = None


class SprintWithItems(Sprint):
    items: list[SprintItem] = Field(default_factory=list)


class HotContext(StorageModel):
    epic: Epic | None = None
    recent_messages: list[Message] = Field(default_factory=list)
    recent_tool_calls: list[ToolCall] = Field(default_factory=list)
    active_feedback: list[Feedback] = Field(default_factory=list)
    unresolved_observations: list[Feedback] = Field(default_factory=list)
    sprints: list[SprintWithItems] = Field(default_factory=list)
    codebases: list[Codebase] = Field(default_factory=list)
    recent_code_artifacts: list[CodeArtifact] = Field(default_factory=list)
    active_images: list[Image] = Field(default_factory=list)
    recent_second_opinions: list[SecondOpinion] = Field(default_factory=list)
    all_sprints_pending_no_queued: bool = False


class ArtifactRef(StorageModel):
    plan_id: str
    name: str
    kind: str | None = None
    role: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    updated_at: datetime | None = None


class ArtifactStat(StorageModel):
    plan_id: str
    name: str
    size_bytes: int
    sha256: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ControlMessageInput(StorageModel):
    epic_id: str
    actor_id: str
    intent: str
    target_id: str
    payload: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str


class ProgressEventInput(StorageModel):
    epic_id: str
    plan_id: str | None = None
    sprint_id: str | None = None
    kind: str
    summary: str
    details: NormalizedDict = Field(default_factory=dict)


Lease = ExecutionLease


@runtime_checkable
class Transaction(Protocol):
    """Context-manager shape used by Store.transaction()."""

    def __enter__(self) -> Transaction:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        ...


@runtime_checkable
class Store(Protocol):
    """Canonical Sprint 1 storage contract.

    The interface follows the refined design-doc surface while preserving the
    live Arnold caller API that still drives editorial operations today.
    """

    # ---------- Transaction ----------
    def transaction(self, epic_id: str | None = None) -> AbstractContextManager[Transaction]:
        ...

    # ---------- Epic ----------
    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: Backend = "file",
        idempotency_key: str | None = None,
    ) -> Epic:
        ...

    def load_epic(self, epic_id: str) -> Epic | None:
        ...

    def update_epic(
        self,
        epic_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Epic:
        ...

    def list_epics(
        self,
        *,
        active_only: bool = True,
        limit: int = 50,
        home_backend: Backend | None = None,
    ) -> list[EpicSummary]:
        ...

    def search_epics(
        self,
        *,
        query: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[EpicSummary]:
        ...

    # ---------- Body ----------
    def load_body(self, epic_id: str) -> str:
        ...

    def update_body(self, epic_id: str, body: str, *, expected_revision: int, idempotency_key: str | None = None) -> Epic:
        ...

    # ---------- Checklist ----------
    def seed_checklist(self, epic_id: str, items: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        ...

    def list_checklist_items(
        self,
        epic_id: str,
        *,
        status: str | None = None,
    ) -> list[ChecklistItem]:
        ...

    def add_checklist_items(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        ...

    def update_checklist_item(self, item_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> ChecklistItem:
        ...

    def delete_checklist_items(self, item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def replace_checklist(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        ...

    # ---------- Sprints ----------
    def create_sprint(
        self,
        *,
        epic_id: str,
        sprint_number: int,
        name: str,
        goal: str,
        status: str = "proposed",
        queue_position: int | None = None,
        pending_reason: str | None = None,
        target_weeks: int = 2,
        idempotency_key: str | None = None,
    ) -> Sprint:
        ...

    def load_sprint(self, sprint_id: str) -> Sprint | None:
        ...

    def list_sprints(
        self,
        epic_id: str,
        *,
        status: str | None = None,
    ) -> list[Sprint]:
        ...

    def list_sprints_with_items(self, epic_id: str) -> list[SprintWithItems]:
        ...

    def update_sprint(
        self,
        sprint_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Sprint:
        ...

    def delete_sprint(self, sprint_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def replace_sprint_items(
        self,
        sprint_id: str,
        items: Sequence[SprintItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[SprintItem]:
        ...

    def list_sprint_items(self, sprint_id: str) -> list[SprintItem]:
        ...

    def set_sprint_queue(
        self,
        epic_id: str,
        ordered_sprint_ids: Sequence[str],
        pending: Mapping[str, str],
        *,
        idempotency_key: str | None = None,
    ) -> list[Sprint]:
        ...

    # ---------- Events ----------
    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: JSONDict | None,
        turn_id: str | None,
        idempotency_key: str | None = None,
    ) -> EpicEvent:
        ...

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[EpicEvent]:
        ...

    def latest_transaction_id(self, epic_id: str) -> str | None:
        ...

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        ...

    # ---------- Messages / turns ----------
    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: JSONDict | None = None,
        synthesize_outbound_id: bool = True,
        idempotency_key: str | None = None,
    ) -> Message:
        ...

    def load_message(self, message_id: str) -> Message | None:
        ...

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        ...

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        ...

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        ...

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: JSONDict | None = None,
        prompt_version: str | None = None,
        state_at_turn: JSONDict | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        ...

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        ...

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        ...

    def list_recent_turns(
        self,
        *,
        n: int = 10,
        epic_id: str | None = None,
    ) -> list[BotTurn]:
        ...

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchHit]:
        ...

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: JSONDict,
        result: JSONDict,
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        ...

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[ToolCall]:
        ...

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: JSONDict | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        ...

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        ...

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[Message]:
        ...

    # ---------- External request ledger ----------
    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: JSONDict,
        request_body: JSONDict | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ExternalRequest:
        ...

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: JSONDict | None = None,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    def mark_failed(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    def find_pending_external_requests(self, older_than_seconds: int) -> list[ExternalRequest]:
        ...

    def mark_orphaned(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    # ---------- Images ----------
    def create_image(
        self,
        *,
        epic_id: str,
        source: str,
        storage_url: str,
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        reference_key: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = False,
        active: bool = True,
        discord_attachment_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        ...

    def load_image(self, image_id: str) -> Image | None:
        ...

    def list_images(
        self,
        *,
        epic_id: str,
        source: str | None = None,
        active: bool | None = True,
    ) -> list[Image]:
        ...

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
        ...

    def list_active_images(self, epic_id: str) -> list[Image]:
        ...

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> Image | None:
        ...

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        ...

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
    ) -> list[Image]:
        ...

    # ---------- Second opinions ----------
    def create_second_opinion(
        self,
        *,
        epic_id: str,
        requested_by: str,
        focus_areas: Sequence[str],
        raw_response: str,
        score: int,
        summary: str,
        verdict: str,
        model_used: str,
        resulting_checklist_item_ids: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        ...

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[SecondOpinion]:
        ...

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        ...

    # ---------- Codebases / artifacts ----------
    def create_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        codebase_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        ...

    def upsert_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        ...

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        ...

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        ...

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[Codebase]:
        ...

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Codebase:
        ...

    def remove_codebase(self, codebase_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def touch_codebase_accessed(
        self,
        codebase_id: str,
        *,
        accessed_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        ...

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        ...

    def create_code_artifact(
        self,
        *,
        kind: str,
        source: str,
        content: str,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        line_range: Any = None,
        scope: str | None = None,
        content_summary: str | None = None,
        metadata: JSONDict | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        ...

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        ...

    def list_code_artifacts(
        self,
        *,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        include_expired: bool = True,
        limit: int | None = 50,
    ) -> list[CodeArtifact]:
        ...

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> CodeArtifact:
        ...

    def delete_code_artifact(self, artifact_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def touch_code_artifact_used(
        self,
        artifact_id: str,
        *,
        used_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        ...

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> CodeArtifact | None:
        ...

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: JSONDict | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        ...

    def cleanup_expired_api_cache(self, *, now: str | None = None,
        idempotency_key: str | None = None,
    ) -> int:
        ...

    # ---------- Feedback ----------
    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: JSONDict | None = None,
        idempotency_key: str | None = None,
    ) -> Feedback:
        ...

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        ...

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Feedback:
        ...

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        ...

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        ...

    # ---------- Plan + PlanArtifact ----------
    def create_plan(
        self,
        *,
        sprint_id: str | None,
        epic_id: str | None,
        name: str,
        idea: str,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> Plan:
        ...

    def load_plan(self, plan_id: str) -> Plan | None:
        ...

    def update_plan(
        self,
        plan_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Plan:
        ...

    def list_plans(
        self,
        *,
        sprint_id: str | None = None,
        epic_id: str | None = None,
        include_orphans: bool = False,
    ) -> list[Plan]:
        ...

    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None:
        ...

    def write_plan_artifact(
        self,
        plan_id: str,
        name: str,
        data: bytes,
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactRef:
        ...

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        ...

    def stat_plan_artifact(self, plan_id: str, name: str) -> ArtifactStat | None:
        ...

    # ---------- Execution leases ----------
    def acquire_execution_lease(
        self,
        plan_id: str,
        holder_id: str,
        worker_kind: str,
        ttl_seconds: int,
        *,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Lease:
        ...

    def heartbeat_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> Lease:
        ...

    def release_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def get_active_lease(self, plan_id: str) -> Lease | None:
        ...

    def find_active_leases_for_epic(self, epic_id: str) -> list[Lease]:
        ...

    # ---------- Locks ----------
    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> EpicLock:
        ...

    def release_lock(self, epic_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    # ---------- Control plane ----------
    def put_control_message(self, msg: ControlMessageInput,
        *,
        idempotency_key: str | None = None,
    ) -> ControlMessage:
        ...

    def claim_pending_control_messages(
        self,
        *,
        processor_id: str,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        ...

    def mark_control_message_processed(self, msg_id: str, result: JSONDict,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def append_progress_event(self, event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        ...

    def list_progress_events(
        self,
        *,
        plan_id: str | None = None,
        epic_id: str | None = None,
        since: datetime | None = None,
    ) -> list[ProgressEvent]:
        ...

    # ---------- Automation actors ----------
    def create_automation_actor(
        self,
        *,
        actor_id: str,
        name: str,
        granted_epic_ids: str | Sequence[str],
        actor_kind: str,
        idempotency_key: str | None = None,
    ) -> AutomationActor:
        ...

    def load_automation_actor(self, actor_id: str) -> AutomationActor | None:
        ...

    def update_automation_actor(self, actor_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> AutomationActor:
        ...


__all__ = [
    "ArtifactRef",
    "ArtifactStat",
    "Backend",
    "ChecklistItemInput",
    "ControlMessageInput",
    "EpicSummary",
    "HotContext",
    "JSONDict",
    "Lease",
    "LeaseConflict",
    "LockConflict",
    "MessageSearchHit",
    "ProgressEventInput",
    "RevisionConflict",
    "SprintItemInput",
    "SprintWithItems",
    "Store",
    "StoreError",
    "Transaction",
]
