"""Protocol boundaries for the Arnold agent substrate."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence


JSONDict = dict[str, Any]


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

    def create_turn(
        self,
        *,
        epic_id: str,
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

    def load_hot_context(self, epic_id: str) -> JSONDict:
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
        idempotency_key: str | None = None,
    ) -> ModelTurnResult:
        ...


class Blob(Protocol):
    """Blob storage port only; Sprint 1a intentionally ships no implementation."""

    def put(self, epic_id: str, content: bytes, mime_type: str) -> BlobRef:
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
        files: Sequence[JSONDict] | None = None,
    ) -> JSONDict:
        ...

    def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> JSONDict:
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
