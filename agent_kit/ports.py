"""Protocol boundaries for the Arnold agent substrate."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence


JSONDict = dict[str, Any]

_EPIC_COLUMNS = {"title", "goal", "body", "state", "last_edited_at", "last_active_at", "planned_at"}
_CHECKLIST_COLUMNS = {
    "content",
    "status",
    "position",
    "skip_reason",
    "superseded_by_item_id",
    "completed_at",
}


@dataclass(frozen=True)
class ProviderError(Exception):
    """A parseable provider error response.

    Model adapters raise this when the provider returns a structured error
    response. Transport failures, SDK bugs, and other non-provider exceptions
    are intentionally propagated unchanged so the loop can leave the external
    request ledger row pending for later reconciliation.
    """

    error_details: JSONDict
    provider_request_id: str | None = None


@dataclass(frozen=True)
class BlobRef:
    epic_id: str
    key: str
    mime_type: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class FileUpload:
    filename: str
    content: bytes
    mime_type: str
    metadata: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: JSONDict


@dataclass(frozen=True)
class ModelTurnResult:
    final_text: str | None = None
    tool_requests: list[ToolRequest] = field(default_factory=list)
    reasoning: str | None = None
    provider_request_id: str | None = None
    response_summary: JSONDict | None = None


class Transport(Protocol):
    """Transport adapter boundary for resident and invocation modes."""

    def receive(self) -> JSONDict:
        ...

    def send(self, payload: JSONDict) -> None:
        ...

    def stream_event(self, event: JSONDict) -> None:
        ...


class Store(Protocol):
    """Persistent store boundary used by the loop, tools, and logger."""

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
    ) -> JSONDict:
        ...

    def load_message(self, message_id: str) -> JSONDict | None:
        ...

    def load_messages(self, message_ids: Sequence[str]) -> list[JSONDict]:
        ...

    def update_message(self, message_id: str, **changes: Any) -> JSONDict:
        ...

    def latest_outbound_message(
        self,
        *,
        epic_id: str | None = None,
    ) -> JSONDict | None:
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
    ) -> JSONDict:
        ...

    def update_turn(self, turn_id: str, **changes: Any) -> JSONDict:
        ...

    def find_abandoned_turns(self, older_than_seconds: int) -> list[JSONDict]:
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
    ) -> JSONDict:
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
    ) -> JSONDict:
        ...

    def acquire_epic_lock(
        self,
        epic_id: str,
        *,
        holder_id: str,
        timeout_seconds: int = 60,
    ) -> bool:
        ...

    def release_epic_lock(self, epic_id: str, *, holder_id: str) -> None:
        ...

    def load_hot_context(self, epic_id: str | None) -> JSONDict:
        ...

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[JSONDict]:
        ...

    def transaction(self) -> AbstractContextManager[None]:
        ...

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
    ) -> JSONDict:
        ...

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: JSONDict | None = None,
    ) -> JSONDict:
        ...

    def mark_failed(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
    ) -> JSONDict:
        ...

    def find_pending_external_requests(
        self,
        older_than_seconds: int,
    ) -> list[JSONDict]:
        ...

    def mark_orphaned(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
    ) -> JSONDict:
        ...

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
    ) -> JSONDict:
        ...

    def load_image(self, image_id: str) -> JSONDict | None:
        ...

    def list_images(
        self,
        *,
        epic_id: str,
        source: str | None = None,
        active: bool | None = True,
    ) -> list[JSONDict]:
        ...

    def update_image(self, image_id: str, **changes: Any) -> JSONDict:
        ...

    def list_active_images(self, epic_id: str) -> list[JSONDict]:
        ...

    def load_active_image_by_reference(
        self,
        epic_id: str,
        reference_key: str,
    ) -> JSONDict | None:
        ...

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        ...

    def deactivate_active_image_reference(
        self,
        epic_id: str,
        reference_key: str,
    ) -> list[JSONDict]:
        ...

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
    ) -> JSONDict:
        ...

    def list_second_opinions(
        self,
        epic_id: str,
        *,
        limit: int | None = None,
    ) -> list[JSONDict]:
        ...

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
    ) -> JSONDict:
        ...

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
    ) -> JSONDict:
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
    ) -> JSONDict:
        ...

    def load_codebase(self, codebase_id: str) -> JSONDict | None:
        ...

    def find_codebase(self, owner: str, name: str) -> JSONDict | None:
        ...

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[JSONDict]:
        ...

    def update_codebase(self, codebase_id: str, **changes: Any) -> JSONDict:
        ...

    def remove_codebase(self, codebase_id: str) -> None:
        ...

    def touch_codebase_accessed(
        self,
        codebase_id: str,
        *,
        accessed_at: str | None = None,
    ) -> JSONDict:
        ...

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
    ) -> JSONDict:
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
    ) -> JSONDict:
        ...

    def load_code_artifact(self, artifact_id: str) -> JSONDict | None:
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
    ) -> list[JSONDict]:
        ...

    def update_code_artifact(self, artifact_id: str, **changes: Any) -> JSONDict:
        ...

    def delete_code_artifact(self, artifact_id: str) -> None:
        ...

    def touch_code_artifact_used(
        self,
        artifact_id: str,
        *,
        used_at: str | None = None,
    ) -> JSONDict:
        ...

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> JSONDict | None:
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
    ) -> JSONDict:
        ...

    def cleanup_expired_api_cache(self, *, now: str | None = None) -> int:
        ...

    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
    ) -> JSONDict:
        ...

    def load_epic(self, epic_id: str) -> JSONDict | None:
        ...

    def list_epics(
        self,
        *,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[JSONDict]:
        ...

    def search_epics(
        self,
        *,
        query: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[JSONDict]:
        ...

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[JSONDict]:
        ...

    def update_epic(self, epic_id: str, **changes: Any) -> JSONDict:
        ...

    def seed_checklist(self, epic_id: str, items: Sequence[str]) -> list[JSONDict]:
        ...

    def list_checklist_items(
        self,
        epic_id: str,
        *,
        status: str | None = None,
    ) -> list[JSONDict]:
        ...

    def update_checklist_item(self, item_id: str, **changes: Any) -> JSONDict:
        ...

    def add_checklist_items(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        ...

    def delete_checklist_items(self, item_ids: Sequence[str]) -> None:
        ...

    def replace_checklist(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        ...

    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: JSONDict | None,
        turn_id: str | None,
    ) -> JSONDict:
        ...

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        ...

    def latest_transaction_id(self, epic_id: str) -> str | None:
        ...

    def events_by_transaction(self, transaction_id: str) -> list[JSONDict]:
        ...

    def list_recent_turns(
        self,
        *,
        n: int = 10,
        epic_id: str | None = None,
    ) -> list[JSONDict]:
        ...

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[JSONDict]:
        ...

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
    ) -> JSONDict:
        ...

    def load_feedback(self, feedback_id: str) -> JSONDict | None:
        ...

    def update_feedback(self, feedback_id: str, **changes: Any) -> JSONDict:
        ...

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        ...

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        ...

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
    ) -> JSONDict:
        ...

    def load_sprint(self, sprint_id: str) -> JSONDict | None:
        ...

    def list_sprints(self, epic_id: str) -> list[JSONDict]:
        ...

    def update_sprint(self, sprint_id: str, **changes: Any) -> JSONDict:
        ...

    def delete_sprint(self, sprint_id: str) -> None:
        ...

    def replace_sprint_items(self, sprint_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        ...

    def list_sprint_items(self, sprint_id: str) -> list[JSONDict]:
        ...

    def list_sprints_with_items(self, epic_id: str) -> list[JSONDict]:
        ...


class Model(Protocol):
    """Model adapter boundary.

    ``model_id`` is supplied by the caller or CLI. Adapters should raise
    ``ProviderError`` for structured provider errors and propagate transport
    or SDK exceptions unchanged.
    """

    def complete_turn(
        self,
        *,
        model_id: str,
        messages: Sequence[JSONDict],
        tools: Sequence[JSONDict],
        hot_context: JSONDict,
        system: str | None = None,
        idempotency_key: str | None = None,
    ) -> ModelTurnResult:
        ...


@dataclass(frozen=True)
class OpenAIImageResult:
    content: bytes
    mime_type: str = "image/png"
    provider_request_id: str | None = None
    response_summary: JSONDict | None = None


@dataclass(frozen=True)
class OpenAISecondOpinionResult:
    raw_response: str
    provider_request_id: str | None = None
    response_summary: JSONDict | None = None


class OpenAIOps(Protocol):
    """Narrow OpenAI operations boundary used by tools."""

    def generate_image(
        self,
        *,
        prompt: str,
        quality: str,
        size: str,
        idempotency_key: str,
    ) -> OpenAIImageResult:
        ...

    def request_second_opinion(
        self,
        *,
        payload: JSONDict,
        idempotency_key: str,
    ) -> OpenAISecondOpinionResult:
        ...


class Blob(Protocol):
    """Blob storage port."""

    def put(
        self,
        epic_id: str,
        content: bytes,
        mime_type: str,
        *,
        idempotency_key: str | None = None,
    ) -> BlobRef:
        ...

    def get(self, ref: BlobRef) -> bytes:
        ...

    def exists(self, ref: BlobRef) -> bool:
        ...


class PushTransport(Protocol):
    """Push transport boundary for resident mode; pull Transport stays separate."""

    def start(self, handler: Callable[[JSONDict], Any]) -> None:
        ...

    def stop(self) -> None:
        ...

    def post_message(
        self,
        channel_id: str,
        content: str,
        *,
        files: Sequence[FileUpload] | None = None,
    ) -> JSONDict:
        ...

    def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> JSONDict:
        ...

    def set_typing(self, channel_id: str, on: bool) -> JSONDict:
        ...

    def download_attachment(self, url: str) -> bytes:
        ...

    def fetch_recent_messages(
        self,
        channel_id: str,
        since: str,
        until: str,
    ) -> list[JSONDict]:
        ...
