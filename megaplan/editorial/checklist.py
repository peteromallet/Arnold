"""Store-backed editorial checklist operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from megaplan.schemas.base import utc_now
from megaplan.store import ChecklistItemInput, Store, deterministic_idempotency_key

from ._events import dump_record, get_field, record_event, require_epic, transaction_id
from .errors import EditorialNotFound, EditorialValidationError
from .lockdown import ensure_unlocked_for_edit

VALID_STATUSES = frozenset({"open", "done", "skipped", "superseded"})


def _ensure_unlocked(store: Store, epic_id: str, operation: str) -> Any:
    epic = require_epic(store, epic_id)
    ensure_unlocked_for_edit(epic_state=str(get_field(epic, "state")), operation=operation)
    return epic


def _validate_status_fields(
    *,
    status: str,
    completed_at: datetime | None = None,
    skip_reason: str | None = None,
    superseded_by_item_id: str | None = None,
) -> None:
    if status not in VALID_STATUSES:
        raise EditorialValidationError("Unsupported checklist status", details={"status": status})
    if status == "skipped" and not (skip_reason or "").strip():
        raise EditorialValidationError("Skipped checklist items require a skip reason")
    if status == "superseded" and not superseded_by_item_id:
        raise EditorialValidationError("Superseded checklist items require superseded_by_item_id")
    if status == "open" and (completed_at or skip_reason or superseded_by_item_id):
        raise EditorialValidationError("Open checklist items cannot include completion metadata")
    if status == "done" and (skip_reason or superseded_by_item_id):
        raise EditorialValidationError("Done checklist items cannot include skip/supersession metadata")


def _input_from_item(item: Any, *, position: int | None = None) -> ChecklistItemInput:
    return ChecklistItemInput(
        id=get_field(item, "id"),
        content=str(get_field(item, "content")),
        status=str(get_field(item, "status") or "open"),
        position=position or int(get_field(item, "position")),
        source=str(get_field(item, "source") or "bot_inferred"),
        skip_reason=get_field(item, "skip_reason"),
        superseded_by_item_id=get_field(item, "superseded_by_item_id"),
        created_at=get_field(item, "created_at"),
        completed_at=get_field(item, "completed_at"),
    )


def _record_checklist_event(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    tx: Any,
    idem: str,
    action: str,
    prior_items: list[Any],
    turn_id: str | None,
) -> None:
    record_event(
        store=store,
        epic_id=epic_id,
        transaction_id_value=transaction_id(store, epic_id, tx, idem),
        event_type="checklist_change",
        summary=f"{actor_id} {action} checklist",
        prior_state={"checklist": [dump_record(item) for item in prior_items]},
        turn_id=turn_id,
        idempotency_key=idem,
    )


def list_items(*, store: Store, epic_id: str, status: str | None = None) -> list[Any]:
    return store.list_checklist_items(epic_id, status=status)


def add_items(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    contents: Sequence[str],
    source: str = "user_requested",
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[Any]:
    epic = _ensure_unlocked(store, epic_id, "checklist_change")
    del epic
    if not contents or any(not content.strip() for content in contents):
        raise EditorialValidationError("Checklist item content cannot be empty")
    prior = store.list_checklist_items(epic_id)
    idem = idempotency_key or deterministic_idempotency_key("editorial-checklist-add", epic_id, actor_id, len(prior), *contents)
    inputs = [ChecklistItemInput(content=content.strip(), status="open", source=source) for content in contents]
    created = store.add_checklist_items(epic_id, inputs, idempotency_key=idem)
    _record_checklist_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="added",
        prior_items=prior,
        turn_id=turn_id,
    )
    return created


def update_item(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    item_id: str,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
    **changes: Any,
) -> Any:
    _ensure_unlocked(store, epic_id, "checklist_change")
    prior = store.list_checklist_items(epic_id)
    if item_id not in {get_field(item, "id") for item in prior}:
        raise EditorialNotFound(f"Checklist item not found: {item_id}", details={"item_id": item_id})
    if "content" in changes and not str(changes["content"]).strip():
        raise EditorialValidationError("Checklist item content cannot be empty")
    if "status" in changes:
        existing = next(item for item in prior if get_field(item, "id") == item_id)
        _validate_status_fields(
            status=str(changes["status"]),
            completed_at=changes.get("completed_at", get_field(existing, "completed_at")),
            skip_reason=changes.get("skip_reason", get_field(existing, "skip_reason")),
            superseded_by_item_id=changes.get("superseded_by_item_id", get_field(existing, "superseded_by_item_id")),
        )
    idem = idempotency_key or deterministic_idempotency_key("editorial-checklist-update", epic_id, actor_id, item_id, sorted(changes))
    updated = store.update_checklist_item(item_id, idempotency_key=idem, **changes)
    _record_checklist_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="updated",
        prior_items=prior,
        turn_id=turn_id,
    )
    return updated


def mark_done(**kwargs: Any) -> Any:
    return update_item(status="done", completed_at=utc_now(), skip_reason=None, superseded_by_item_id=None, **kwargs)


def mark_open(**kwargs: Any) -> Any:
    return update_item(status="open", completed_at=None, skip_reason=None, superseded_by_item_id=None, **kwargs)


def mark_skipped(*, skip_reason: str, **kwargs: Any) -> Any:
    return update_item(status="skipped", completed_at=None, skip_reason=skip_reason, superseded_by_item_id=None, **kwargs)


def mark_superseded(*, superseded_by_item_id: str, **kwargs: Any) -> Any:
    return update_item(
        status="superseded",
        completed_at=None,
        skip_reason=None,
        superseded_by_item_id=superseded_by_item_id,
        **kwargs,
    )


def move_item(*, position: int, **kwargs: Any) -> Any:
    if position <= 0:
        raise EditorialValidationError("Checklist position must be positive")
    return update_item(position=position, **kwargs)


def delete_items(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    item_ids: Sequence[str],
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    _ensure_unlocked(store, epic_id, "checklist_change")
    prior = store.list_checklist_items(epic_id)
    missing = sorted(set(item_ids) - {get_field(item, "id") for item in prior})
    if missing:
        raise EditorialNotFound("Checklist item not found", details={"item_ids": missing})
    idem = idempotency_key or deterministic_idempotency_key("editorial-checklist-delete", epic_id, actor_id, *item_ids)
    store.delete_checklist_items(item_ids, idempotency_key=idem)
    _record_checklist_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="deleted from",
        prior_items=prior,
        turn_id=turn_id,
    )


def replace_items(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    items: Sequence[ChecklistItemInput],
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[Any]:
    _ensure_unlocked(store, epic_id, "checklist_change")
    if not items:
        raise EditorialValidationError("Checklist replacement cannot be empty")
    for item in items:
        if not item.content.strip():
            raise EditorialValidationError("Checklist item content cannot be empty")
        _validate_status_fields(
            status=item.status,
            completed_at=item.completed_at,
            skip_reason=item.skip_reason,
            superseded_by_item_id=item.superseded_by_item_id,
        )
    prior = store.list_checklist_items(epic_id)
    idem = idempotency_key or deterministic_idempotency_key("editorial-checklist-replace", epic_id, actor_id, len(items))
    replaced = store.replace_checklist(epic_id, items, idempotency_key=idem)
    _record_checklist_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="replaced",
        prior_items=prior,
        turn_id=turn_id,
    )
    return replaced


def reorder_items(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    ordered_item_ids: Sequence[str],
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[Any]:
    prior = store.list_checklist_items(epic_id)
    by_id = {get_field(item, "id"): item for item in prior}
    if len(set(ordered_item_ids)) != len(ordered_item_ids):
        raise EditorialValidationError("Duplicate checklist item IDs are not allowed")
    missing = sorted(set(ordered_item_ids) - set(by_id))
    omitted = sorted(set(by_id) - set(ordered_item_ids))
    if missing or omitted:
        raise EditorialValidationError("Checklist reorder must include every current item", details={"missing": missing, "omitted": omitted})
    inputs = [_input_from_item(by_id[item_id], position=index) for index, item_id in enumerate(ordered_item_ids, start=1)]
    return replace_items(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        items=inputs,
        turn_id=turn_id,
        idempotency_key=idempotency_key,
    )
