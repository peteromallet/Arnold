"""Core storage contracts, record shapes, and compatibility helpers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from pathlib import PurePosixPath
from types import TracebackType
from typing import Any, Iterator, Mapping, Protocol, Sequence, TypeAlias, runtime_checkable

from pydantic import Field

from arnold_pipelines.megaplan.schemas import (
    AutomationActor,
    BotTurn,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    CloudRun,
    Epic,
    EpicEvent,
    EpicLock,
    EpicSnapshot,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    Plan,
    ProgressEvent,
    ResidentConversation,
    ResidentUserPreference,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    StorageModel,
    SystemLog,
    Ticket,
    TicketEpicLink,
    ToolCall,
)
from arnold_pipelines.megaplan.schemas.arnold import (
    ChecklistSource,
    ChecklistStatus,
    EpicSummary,
    SprintItemComplexity,
    SprintItemStatus,
)
from arnold_pipelines.megaplan.schemas.base import Backend, NormalizedDict, utc_now
from arnold_pipelines.megaplan.schemas.sprint1 import ControlIntent
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


EPIC_UPDATE_FIELDS = frozenset({
    "title",
    "goal",
    "body",
    "state",
    "home_backend",
    "migrated_to",
    "last_active_at",
    "planned_at",
})


def validate_epic_update_fields(changes: Mapping[str, object]) -> None:
    unknown = sorted(set(changes) - EPIC_UPDATE_FIELDS)
    if unknown:
        allowed = ", ".join(sorted(EPIC_UPDATE_FIELDS))
        raise StoreError(f"Unknown epic update field(s): {', '.join(unknown)}. Allowed fields: {allowed}")


class RevisionConflict(StoreError):
    """Raised when an optimistic-concurrency write sees a stale revision."""


class LockConflict(StoreError):
    """Raised when an epic lock is held by another actor."""


class LeaseConflict(StoreError):
    """Raised when an execution lease is already held."""


class ChecklistItemInput(StorageModel):
    id: str | None = None
    content: str
    status: ChecklistStatus = "open"
    position: int | None = Field(default=None, gt=0)
    source: ChecklistSource = "bot_inferred"
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class SprintItemInput(StorageModel):
    id: str | None = None
    content: str
    estimated_complexity: SprintItemComplexity = "medium"
    status: SprintItemStatus = "open"
    source_section: str | None = None
    position: int | None = Field(default=None, gt=0)
    created_at: datetime | None = None


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


@dataclass(frozen=True)
class StoredEvent:
    """Store-neutral event record used by observability projections."""

    kind: str
    phase: str | None
    payload: Mapping[str, Any]
    occurred_at: datetime | str | None = None
    id: str | None = None
    seq: int | None = None
    run_id: str | None = None
    source: str | None = None


def validate_plan_artifact_name(name: str) -> str:
    """Return a normalized relative artifact path or reject unsafe names."""
    if not name:
        raise ValueError("Plan artifact name must be non-empty")
    if "\\" in name:
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name:
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    return name


class ControlMessageInput(StorageModel):
    epic_id: str
    actor_id: str
    intent: ControlIntent
    target_id: str
    payload: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str


class ResidentConversationInput(StorageModel):
    transport: str = "discord"
    conversation_key: str
    active_epic_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    dm_user_id: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)


class ScheduledJobInput(StorageModel):
    job_type: str
    conversation_id: str | None = None
    cloud_run_id: str | None = None
    epic_id: str | None = None
    payload: NormalizedDict = Field(default_factory=dict)
    scheduled_for: datetime
    max_attempts: int = Field(default=3, ge=1)


class CloudRunInput(StorageModel):
    operation: str
    conversation_id: str | None = None
    epic_id: str | None = None
    sprint_id: str | None = None
    plan_id: str | None = None
    provider: str | None = None
    provider_run_id: str | None = None
    target_id: str | None = None
    command_summary: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str | None = None
    started_by_actor_id: str | None = None


class ProgressEventInput(StorageModel):
    epic_id: str
    plan_id: str | None = None
    sprint_id: str | None = None
    idempotency_key: str | None = None
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

    def capture_epic_snapshot(self, epic_id: str) -> EpicSnapshot:
        ...

    def revert(
        self,
        epic_id: str,
        to_transaction_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
    ) -> Epic:
        ...

    def get_epic_at_time(self, epic_id: str, when: datetime | str) -> EpicSnapshot | None:
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
        pre_state: JSONDict | None = None,
        post_state: JSONDict | None = None,
        pre_state_canonical_json: str | None = None,
        post_state_canonical_json: str | None = None,
        pre_state_sha256: str | None = None,
        post_state_sha256: str | None = None,
        turn_id: str | None = None,
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

    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
        ...

    def latest_transaction_id(self, epic_id: str) -> str | None:
        ...

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        ...

    def append_telemetry_event(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        scope: str | None = None,
    ) -> JSONDict:
        ...

    def events_for_plan(self, plan_id: str) -> Iterator[StoredEvent]:
        ...

    # ---------- Messages / turns ----------
    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        discord_reply_provenance: JSONDict | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: JSONDict | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        ...

    def load_message(self, message_id: str) -> Message | None:
        ...

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        ...

    def find_conversation_message_by_discord_id(
        self,
        conversation_id: str,
        discord_message_id: str,
    ) -> Message | None:
        """Resolve one exact Discord identity inside one resident conversation."""
        ...

    def list_conversation_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        exclude_ids: Sequence[str] = (),
    ) -> list[Message]:
        """Return up to the last ``limit`` messages for a conversation, oldest first.

        Not epic-scoped: filters purely by ``conversation_id``. ``exclude_ids``
        drops the current burst (already persisted before a turn is handled) so
        it is not double-counted as history.
        """
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
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        ...

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        ...

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
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
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        root_commit_sha: str | None = None,
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
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        root_commit_sha: str | None = None,
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

    def load_codebase_by_associated_epic(self, epic_id: str) -> Codebase | None:
        ...

    def resolve_codebase_by_root_sha(self, root_commit_sha: str) -> Codebase | None:
        ...

    def create_ticket(
        self,
        *,
        codebase_id: str,
        title: str,
        body: str = "",
        source: str = "human",
        tags: list[str] | None = None,
        filed_by_actor_id: str | None = None,
        filed_in_turn_id: str | None = None,
        slug: str,
        ticket_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ticket:
        ...

    def load_ticket(self, ticket_id: str) -> Ticket | None:
        ...

    def list_tickets(
        self,
        *,
        codebase_id: str | None = None,
        codebase_ids: Sequence[str] | None = None,
        status: str | None = None,
        tags: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        keywords_all: bool = False,
        sort: str = "created",
        order: str = "desc",
        limit: int | None = None,
    ) -> list[Ticket]:
        ...

    def update_ticket(self, ticket_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Ticket:
        ...

    def link_ticket_to_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        resolves_on_complete: bool = False,
        idempotency_key: str | None = None,
    ) -> TicketEpicLink:
        ...

    def unlink_ticket_from_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        ...

    def list_ticket_epic_links(
        self,
        *,
        ticket_id: str | None = None,
        epic_id: str | None = None,
    ) -> list[TicketEpicLink]:
        ...

    def address_tickets_resolved_by_epic(self, epic_id: str) -> list[str]:
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

    def recover_stale_control_messages(
        self,
        *,
        processor_id: str,
        older_than_seconds: int,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        ...

    def list_stale_control_messages(
        self,
        *,
        older_than_seconds: int,
        limit: int = 10,
    ) -> list[ControlMessage]:
        ...

    # ---------- Resident orchestration ----------
    def upsert_resident_conversation(
        self,
        conversation: ResidentConversationInput,
        *,
        idempotency_key: str | None = None,
    ) -> ResidentConversation:
        ...

    def load_resident_conversation(self, conversation_id: str) -> ResidentConversation | None:
        ...

    def get_resident_conversation_by_key(
        self,
        *,
        transport: str,
        conversation_key: str,
    ) -> ResidentConversation | None:
        ...

    def list_resident_conversations(
        self,
        *,
        transport: str | None = None,
        active_epic_id: str | None = None,
        limit: int = 50,
    ) -> list[ResidentConversation]:
        ...

    def update_resident_conversation(
        self,
        conversation_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ResidentConversation:
        ...

    def load_resident_user_preference(
        self, *, transport: str, user_id: str
    ) -> ResidentUserPreference | None:
        ...

    def upsert_resident_user_preference(
        self,
        *,
        transport: str,
        user_id: str,
        timezone_name: str | None,
        metadata: JSONDict | None = None,
        idempotency_key: str | None = None,
    ) -> ResidentUserPreference:
        ...

    def create_scheduled_job(
        self,
        job: ScheduledJobInput,
        *,
        idempotency_key: str | None = None,
    ) -> ScheduledJob:
        ...

    def load_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        ...

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ScheduledJob:
        ...

    def claim_due_scheduled_jobs(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        stale_after_seconds: int | None = None,
        max: int = 10,
        job_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> list[ScheduledJob]:
        ...

    def list_scheduled_jobs(
        self,
        *,
        conversation_id: str | None = None,
        cloud_run_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[ScheduledJob]:
        ...

    def create_cloud_run(
        self,
        run: CloudRunInput,
        *,
        idempotency_key: str | None = None,
    ) -> CloudRun:
        ...

    def load_cloud_run(self, run_id: str) -> CloudRun | None:
        ...

    def update_cloud_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> CloudRun:
        ...

    def list_cloud_runs(
        self,
        *,
        conversation_id: str | None = None,
        epic_id: str | None = None,
        plan_id: str | None = None,
        sprint_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CloudRun]:
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
    "CloudRunInput",
    "EpicSummary",
    "HotContext",
    "JSONDict",
    "Lease",
    "LeaseConflict",
    "LockConflict",
    "MessageSearchHit",
    "ProgressEventInput",
    "ResidentConversationInput",
    "ScheduledJobInput",
    "RevisionConflict",
    "SprintItemInput",
    "SprintWithItems",
    "StoredEvent",
    "Store",
    "StoreError",
    "Transaction",
    "validate_plan_artifact_name",
]
