"""Compatibility adapters for live Arnold callers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import uuid4

from arnold_pipelines.megaplan.schemas import StorageModel

from .base import ChecklistItemInput, ControlMessageInput, JSONDict, LockConflict, SprintItemInput, Store, deterministic_idempotency_key
from .blob import BlobRef as StoreBlobRef
from .blob import BlobStore


def _dump(value: Any) -> Any:
    if isinstance(value, StorageModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    return value


class ArnoldStoreAdapter:
    """Expose the live Arnold dict-based store API on top of the new Store seam."""

    _IDEMPOTENT_METHODS = frozenset(
        {
            "create_epic",
            "update_epic",
            "update_body",
            "seed_checklist",
            "add_checklist_items",
            "update_checklist_item",
            "delete_checklist_items",
            "replace_checklist",
            "create_sprint",
            "update_sprint",
            "delete_sprint",
            "replace_sprint_items",
            "set_sprint_queue",
            "record_epic_event",
            "create_message",
            "update_message",
            "create_turn",
            "update_turn",
            "record_tool_call",
            "log_system_event",
            "insert_pending",
            "mark_confirmed",
            "mark_failed",
            "mark_orphaned",
            "create_image",
            "update_image",
            "deactivate_active_image_reference",
            "create_second_opinion",
            "set_second_opinion_checklist_items",
            "create_codebase",
            "upsert_codebase",
            "update_codebase",
            "remove_codebase",
            "touch_codebase_accessed",
            "mark_codebase_verified",
            "create_code_artifact",
            "update_code_artifact",
            "delete_code_artifact",
            "touch_code_artifact_used",
            "upsert_api_cache",
            "cleanup_expired_api_cache",
            "create_feedback",
            "update_feedback",
            "create_plan",
            "update_plan",
            "write_plan_artifact",
            "acquire_execution_lease",
            "heartbeat_lease",
            "release_lease",
            "acquire_lock",
            "release_lock",
            "create_control_message",
            "put_control_message",
            "claim_pending_control_messages",
            "mark_control_message_processed",
            "append_progress_event",
            "create_automation_actor",
            "update_automation_actor",
        }
    )

    def __init__(self, store: Store) -> None:
        self._store = store

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def _call(self, method_name: str, /, *args: Any, **kwargs: Any) -> Any:
        if method_name in self._IDEMPOTENT_METHODS and kwargs.get("idempotency_key") is None:
            kwargs["idempotency_key"] = deterministic_idempotency_key("arnold-adapter", method_name, *args, kwargs)
        method = getattr(self._store, method_name)
        return _dump(method(*args, **kwargs))

    def transaction(self) -> Any:
        return self._store.transaction(epic_id=None)

    def create_message(self, **fields: Any) -> JSONDict:
        return self._call("create_message", **fields)

    def load_message(self, message_id: str) -> JSONDict | None:
        return self._call("load_message", message_id)

    def load_messages(self, message_ids: Sequence[str]) -> list[JSONDict]:
        return self._call("load_messages", message_ids)

    def update_message(self, message_id: str, **changes: Any) -> JSONDict:
        return self._call("update_message", message_id, **changes)

    def latest_outbound_message(self, *, epic_id: str | None = None) -> JSONDict | None:
        return self._call("latest_outbound_message", epic_id=epic_id)

    def create_turn(self, **fields: Any) -> JSONDict:
        return self._call("create_turn", **fields)

    def update_turn(self, turn_id: str, **changes: Any) -> JSONDict:
        return self._call("update_turn", turn_id, **changes)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[JSONDict]:
        return self._call("find_abandoned_turns", older_than_seconds)

    def record_tool_call(self, **fields: Any) -> JSONDict:
        return self._call("record_tool_call", **fields)

    def log_system_event(self, **fields: Any) -> JSONDict:
        return self._call("log_system_event", **fields)

    def acquire_epic_lock(
        self,
        epic_id: str,
        *,
        holder_id: str,
        timeout_seconds: int = 60,
    ) -> bool:
        try:
            acquired = self._store.acquire_lock(
                epic_id=epic_id,
                holder_id=holder_id,
                ttl_seconds=timeout_seconds,
                idempotency_key=deterministic_idempotency_key("arnold-adapter", "acquire_lock", epic_id, holder_id),
            )
        except LockConflict:
            return False
        return bool(acquired)

    def release_epic_lock(self, epic_id: str, *, holder_id: str) -> None:
        self._store.release_lock(
            epic_id,
            holder_id,
            idempotency_key=deterministic_idempotency_key("arnold-adapter", "release_lock", epic_id, holder_id),
        )

    def load_hot_context(self, epic_id: str | None) -> JSONDict:
        return self._call("load_hot_context", epic_id)

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[JSONDict]:
        return self._call(
            "find_unprocessed_messages",
            epic_id,
            started_at,
            exclude_ids,
        )

    def insert_pending(self, **fields: Any) -> JSONDict:
        return self._call("insert_pending", **fields)

    def mark_confirmed(self, request_id: str, **changes: Any) -> JSONDict:
        return self._call("mark_confirmed", request_id, **changes)

    def mark_failed(self, request_id: str, **changes: Any) -> JSONDict:
        return self._call("mark_failed", request_id, **changes)

    def find_pending_external_requests(self, older_than_seconds: int) -> list[JSONDict]:
        return self._call("find_pending_external_requests", older_than_seconds)

    def mark_orphaned(self, request_id: str, **changes: Any) -> JSONDict:
        return self._call("mark_orphaned", request_id, **changes)

    def create_image(self, **fields: Any) -> JSONDict:
        return self._call("create_image", **fields)

    def load_image(self, image_id: str) -> JSONDict | None:
        return self._call("load_image", image_id)

    def list_images(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_images", **filters)

    def update_image(self, image_id: str, **changes: Any) -> JSONDict:
        return self._call("update_image", image_id, **changes)

    def list_active_images(self, epic_id: str) -> list[JSONDict]:
        return self._call("list_active_images", epic_id)

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> JSONDict | None:
        return self._call("load_active_image_by_reference", epic_id, reference_key)

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        return self._call("active_image_reference_exists", epic_id, reference_key)

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str) -> list[JSONDict]:
        return self._call("deactivate_active_image_reference", epic_id, reference_key)

    def create_second_opinion(self, **fields: Any) -> JSONDict:
        return self._call("create_second_opinion", **fields)

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[JSONDict]:
        return self._call("list_second_opinions", epic_id, limit=limit)

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
    ) -> JSONDict:
        return self._call(
            "set_second_opinion_checklist_items",
            second_opinion_id,
            checklist_item_ids,
        )

    def create_codebase(self, **fields: Any) -> JSONDict:
        return self._call("create_codebase", **fields)

    def upsert_codebase(self, **fields: Any) -> JSONDict:
        return self._call("upsert_codebase", **fields)

    def load_codebase(self, codebase_id: str) -> JSONDict | None:
        return self._call("load_codebase", codebase_id)

    def find_codebase(self, owner: str, name: str) -> JSONDict | None:
        return self._call("find_codebase", owner, name)

    def list_codebases(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_codebases", **filters)

    def update_codebase(self, codebase_id: str, **changes: Any) -> JSONDict:
        return self._call("update_codebase", codebase_id, **changes)

    def remove_codebase(self, codebase_id: str) -> None:
        self._call("remove_codebase", codebase_id)

    def touch_codebase_accessed(self, codebase_id: str, **changes: Any) -> JSONDict:
        return self._call("touch_codebase_accessed", codebase_id, **changes)

    def mark_codebase_verified(self, codebase_id: str, **changes: Any) -> JSONDict:
        return self._call("mark_codebase_verified", codebase_id, **changes)

    def create_code_artifact(self, **fields: Any) -> JSONDict:
        return self._call("create_code_artifact", **fields)

    def load_code_artifact(self, artifact_id: str) -> JSONDict | None:
        return self._call("load_code_artifact", artifact_id)

    def list_code_artifacts(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_code_artifacts", **filters)

    def update_code_artifact(self, artifact_id: str, **changes: Any) -> JSONDict:
        return self._call("update_code_artifact", artifact_id, **changes)

    def delete_code_artifact(self, artifact_id: str) -> None:
        self._call("delete_code_artifact", artifact_id)

    def touch_code_artifact_used(self, artifact_id: str, **changes: Any) -> JSONDict:
        return self._call("touch_code_artifact_used", artifact_id, **changes)

    def get_api_cache(self, cache_key: str, **filters: Any) -> JSONDict | None:
        return self._call("get_api_cache", cache_key, **filters)

    def upsert_api_cache(self, **fields: Any) -> JSONDict:
        return self._call("upsert_api_cache", **fields)

    def cleanup_expired_api_cache(self, **filters: Any) -> int:
        return self._call("cleanup_expired_api_cache", **filters)

    def create_epic(self, **fields: Any) -> JSONDict:
        return self._call("create_epic", **fields)

    def load_epic(self, epic_id: str) -> JSONDict | None:
        return self._call("load_epic", epic_id)

    def list_epics(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_epics", **filters)

    def search_epics(self, **filters: Any) -> list[JSONDict]:
        return self._call("search_epics", **filters)

    def search_messages(self, **filters: Any) -> list[JSONDict]:
        return self._call("search_messages", **filters)

    def list_conversation_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        exclude_ids: Sequence[str] = (),
    ) -> list[JSONDict]:
        return self._call(
            "list_conversation_messages",
            conversation_id,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    def update_epic(self, epic_id: str, **changes: Any) -> JSONDict:
        return self._call("update_epic", epic_id, **changes)

    def seed_checklist(self, epic_id: str, items: Sequence[str], *, idempotency_key: str | None = None) -> list[JSONDict]:
        seeded = [
            ChecklistItemInput(
                content=content,
                status="open",
                position=position,
                source="default_seed",
            )
            for position, content in enumerate(items, start=1)
        ]
        return self._call("add_checklist_items", epic_id, seeded, idempotency_key=idempotency_key)

    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[JSONDict]:
        return self._call("list_checklist_items", epic_id, status=status)

    def update_checklist_item(self, item_id: str, **changes: Any) -> JSONDict:
        return self._call("update_checklist_item", item_id, **changes)

    def add_checklist_items(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        return self._call(
            "add_checklist_items",
            epic_id,
            [ChecklistItemInput.model_validate(item) for item in items],
        )

    def delete_checklist_items(self, item_ids: Sequence[str]) -> None:
        self._call("delete_checklist_items", item_ids)

    def replace_checklist(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        return self._call(
            "replace_checklist",
            epic_id,
            [ChecklistItemInput.model_validate(item) for item in items],
        )

    def record_epic_event(self, **fields: Any) -> JSONDict:
        return self._call("record_epic_event", **fields)

    def list_epic_events(self, epic_id: str, **filters: Any) -> list[JSONDict]:
        return self._call("list_epic_events", epic_id, **filters)

    def latest_transaction_id(self, epic_id: str) -> str | None:
        return self._store.latest_transaction_id(epic_id)

    def events_by_transaction(self, transaction_id: str) -> list[JSONDict]:
        return self._call("events_by_transaction", transaction_id)

    def list_recent_turns(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_recent_turns", **filters)

    def search_tool_calls_by(self, **filters: Any) -> list[JSONDict]:
        return self._call("search_tool_calls_by", **filters)

    def create_feedback(self, **fields: Any) -> JSONDict:
        return self._call("create_feedback", **fields)

    def load_feedback(self, feedback_id: str) -> JSONDict | None:
        return self._call("load_feedback", feedback_id)

    def update_feedback(self, feedback_id: str, **changes: Any) -> JSONDict:
        return self._call("update_feedback", feedback_id, **changes)

    def list_feedback(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_feedback", **filters)

    def list_observations(self, **filters: Any) -> list[JSONDict]:
        return self._call("list_observations", **filters)

    def create_sprint(self, **fields: Any) -> JSONDict:
        return self._call("create_sprint", **fields)

    def load_sprint(self, sprint_id: str) -> JSONDict | None:
        return self._call("load_sprint", sprint_id)

    def list_sprints(self, epic_id: str) -> list[JSONDict]:
        return self._call("list_sprints", epic_id)

    def update_sprint(self, sprint_id: str, **changes: Any) -> JSONDict:
        return self._call("update_sprint", sprint_id, **changes)

    def delete_sprint(self, sprint_id: str) -> None:
        self._call("delete_sprint", sprint_id)

    def replace_sprint_items(self, sprint_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        return self._call(
            "replace_sprint_items",
            sprint_id,
            [SprintItemInput.model_validate(item) for item in items],
        )

    def list_sprint_items(self, sprint_id: str) -> list[JSONDict]:
        return self._call("list_sprint_items", sprint_id)

    def list_sprints_with_items(self, epic_id: str) -> list[JSONDict]:
        return self._call("list_sprints_with_items", epic_id)

    def create_control_message(
        self,
        *,
        epic_id: str,
        actor_id: str,
        intent: str,
        target_id: str,
        payload: JSONDict | None = None,
        idempotency_key: str | None = None,
    ) -> JSONDict:
        effective_key = idempotency_key or deterministic_idempotency_key(
            "arnold-adapter",
            "create_control_message",
            epic_id,
            actor_id,
            intent,
            target_id,
            payload or {},
        )
        return _dump(
            self._store.put_control_message(
                ControlMessageInput(
                    epic_id=epic_id,
                    actor_id=actor_id,
                    intent=intent,
                    target_id=target_id,
                    payload=payload or {},
                    idempotency_key=effective_key,
                ),
                idempotency_key=effective_key,
            )
        )

    def list_progress_events(
        self,
        *,
        epic_id: str | None = None,
        plan_id: str | None = None,
        after_id: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[JSONDict]:
        since_value: Any = since
        if isinstance(since, str):
            since_value = datetime.fromisoformat(since.replace("Z", "+00:00"))
        events = self._call(
            "list_progress_events",
            epic_id=epic_id,
            plan_id=plan_id,
            since=since_value,
        )
        events.sort(key=lambda event: (str(event.get("occurred_at") or ""), str(event.get("id") or "")))
        if after_id is not None:
            cursor = next((event for event in events if event.get("id") == after_id), None)
            if cursor is not None:
                cursor_key = (str(cursor.get("occurred_at") or ""), str(cursor.get("id") or ""))
                events = [
                    event
                    for event in events
                    if (str(event.get("occurred_at") or ""), str(event.get("id") or "")) > cursor_key
                ]
        return events[:limit]


class ArnoldBlobAdapter:
    """Adapt the new blob seam to Arnold's legacy epic/key-oriented port."""

    def __init__(self, blob_store: BlobStore) -> None:
        self._blob_store = blob_store

    @staticmethod
    def _blob_id(epic_id: str, idempotency_key: str | None) -> str:
        suffix = idempotency_key or uuid4().hex
        return f"{epic_id}/{suffix}"

    @staticmethod
    def _ref(epic_id: str, store_ref: StoreBlobRef) -> JSONDict:
        key = store_ref.blob_id.partition("/")[2] or store_ref.blob_id
        return {
            "epic_id": epic_id,
            "key": key,
            "mime_type": store_ref.content_type,
            "size_bytes": store_ref.size_bytes,
        }

    def put(
        self,
        epic_id: str,
        content: bytes,
        mime_type: str,
        *,
        idempotency_key: str | None = None,
    ) -> JSONDict:
        blob_id = self._blob_id(epic_id, idempotency_key)
        return self._ref(
            epic_id,
            self._blob_store.put(blob_id, content, content_type=mime_type),
        )

    def get(self, ref: JSONDict) -> bytes:
        blob_id = self._blob_id(str(ref["epic_id"]), str(ref["key"]))
        return self._blob_store.get(blob_id)

    def exists(self, ref: JSONDict) -> bool:
        blob_id = self._blob_id(str(ref["epic_id"]), str(ref["key"]))
        return self._blob_store.stat(blob_id) is not None


__all__ = ["ArnoldBlobAdapter", "ArnoldStoreAdapter"]
