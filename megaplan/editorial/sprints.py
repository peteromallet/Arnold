"""Store-backed editorial sprint operations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from megaplan.store import SprintItemInput, Store, deterministic_idempotency_key

from ._events import dump_record, get_field, record_event, require_epic, transaction_id
from .errors import EditorialNotFound, EditorialValidationError
from .lockdown import ensure_unlocked_for_edit


def _ensure_unlocked(store: Store, epic_id: str, operation: str) -> Any:
    epic = require_epic(store, epic_id)
    ensure_unlocked_for_edit(epic_state=str(get_field(epic, "state")), operation=operation)
    return epic


def _record_sprint_event(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    tx: Any,
    idem: str,
    action: str,
    prior_sprints: list[Any],
    event_type: str = "sprints_change",
    turn_id: str | None,
) -> None:
    record_event(
        store=store,
        epic_id=epic_id,
        transaction_id_value=transaction_id(store, epic_id, tx, idem),
        event_type=event_type,
        summary=f"{actor_id} {action} sprints",
        prior_state={"sprints": [dump_record(sprint) for sprint in prior_sprints]},
        turn_id=turn_id,
        idempotency_key=idem,
    )


def _validate_text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise EditorialValidationError(f"Sprint {field} cannot be empty")
    return stripped


def create_sprint(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    sprint_number: int,
    name: str,
    goal: str,
    target_weeks: int = 2,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    _ensure_unlocked(store, epic_id, "sprints_change")
    if sprint_number <= 0 or target_weeks <= 0:
        raise EditorialValidationError("Sprint number and target weeks must be positive")
    prior = store.list_sprints_with_items(epic_id)
    idem = idempotency_key or deterministic_idempotency_key("editorial-sprint-create", epic_id, actor_id, sprint_number, name)
    sprint = store.create_sprint(
        epic_id=epic_id,
        sprint_number=sprint_number,
        name=_validate_text(name, "name"),
        goal=_validate_text(goal, "goal"),
        target_weeks=target_weeks,
        idempotency_key=idem,
    )
    _record_sprint_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="created",
        prior_sprints=prior,
        turn_id=turn_id,
    )
    return sprint


def list_sprints(*, store: Store, epic_id: str, status: str | None = None) -> list[Any]:
    return store.list_sprints(epic_id, status=status)


def list_sprints_with_items(*, store: Store, epic_id: str) -> list[Any]:
    return store.list_sprints_with_items(epic_id)


def update_sprint(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    sprint_id: str,
    expected_revision: int,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
    **changes: Any,
) -> Any:
    _ensure_unlocked(store, epic_id, "sprints_change")
    prior = store.list_sprints_with_items(epic_id)
    if sprint_id not in {get_field(sprint, "id") for sprint in prior}:
        raise EditorialNotFound(f"Sprint not found: {sprint_id}", details={"sprint_id": sprint_id})
    if "name" in changes:
        changes["name"] = _validate_text(str(changes["name"]), "name")
    if "goal" in changes:
        changes["goal"] = _validate_text(str(changes["goal"]), "goal")
    idem = idempotency_key or deterministic_idempotency_key("editorial-sprint-update", epic_id, actor_id, sprint_id, sorted(changes))
    sprint = store.update_sprint(sprint_id, expected_revision=expected_revision, idempotency_key=idem, **changes)
    _record_sprint_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="updated",
        prior_sprints=prior,
        turn_id=turn_id,
    )
    return sprint


def delete_sprint(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    sprint_id: str,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    _ensure_unlocked(store, epic_id, "sprints_change")
    prior = store.list_sprints_with_items(epic_id)
    if sprint_id not in {get_field(sprint, "id") for sprint in prior}:
        raise EditorialNotFound(f"Sprint not found: {sprint_id}", details={"sprint_id": sprint_id})
    idem = idempotency_key or deterministic_idempotency_key("editorial-sprint-delete", epic_id, actor_id, sprint_id)
    store.delete_sprint(sprint_id, idempotency_key=idem)
    _record_sprint_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="deleted from",
        prior_sprints=prior,
        turn_id=turn_id,
    )


def replace_sprint_items(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    sprint_id: str,
    items: Sequence[SprintItemInput],
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[Any]:
    _ensure_unlocked(store, epic_id, "sprints_change")
    prior = store.list_sprints_with_items(epic_id)
    if sprint_id not in {get_field(sprint, "id") for sprint in prior}:
        raise EditorialNotFound(f"Sprint not found: {sprint_id}", details={"sprint_id": sprint_id})
    if any(not item.content.strip() for item in items):
        raise EditorialValidationError("Sprint item content cannot be empty")
    idem = idempotency_key or deterministic_idempotency_key("editorial-sprint-items", epic_id, actor_id, sprint_id, len(items))
    created = store.replace_sprint_items(sprint_id, items, idempotency_key=idem)
    _record_sprint_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="replaced items for",
        prior_sprints=prior,
        turn_id=turn_id,
    )
    return created


def list_sprint_items(*, store: Store, sprint_id: str) -> list[Any]:
    return store.list_sprint_items(sprint_id)


def set_sprint_queue(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    ordered_sprint_ids: Sequence[str],
    pending: Mapping[str, str],
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[Any]:
    _ensure_unlocked(store, epic_id, "sprint_status_change")
    ordered = [str(sprint_id) for sprint_id in ordered_sprint_ids]
    pending_map = {str(sprint_id): str(reason) for sprint_id, reason in pending.items()}
    if len(set(ordered)) != len(ordered):
        raise EditorialValidationError("Duplicate queued sprint IDs are not allowed")
    overlap = sorted(set(ordered) & set(pending_map))
    if overlap:
        raise EditorialValidationError("Sprints cannot be both queued and pending", details={"sprint_ids": overlap})
    prior = store.list_sprints_with_items(epic_id)
    known_ids = {get_field(sprint, "id") for sprint in prior}
    unknown = sorted((set(ordered) | set(pending_map)) - known_ids)
    if unknown:
        raise EditorialNotFound("Unknown sprint IDs", details={"sprint_ids": unknown})
    missing_reasons = sorted(sprint_id for sprint_id, reason in pending_map.items() if not reason.strip())
    if missing_reasons:
        raise EditorialValidationError("Pending sprints require a reason", details={"sprint_ids": missing_reasons})
    idem = idempotency_key or deterministic_idempotency_key("editorial-sprint-queue", epic_id, actor_id, *ordered, *pending_map)
    queued = store.set_sprint_queue(epic_id, ordered, pending_map, idempotency_key=idem)
    _record_sprint_event(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        tx=None,
        idem=idem,
        action="queued",
        prior_sprints=prior,
        event_type="sprint_status_change",
        turn_id=turn_id,
    )
    return queued
