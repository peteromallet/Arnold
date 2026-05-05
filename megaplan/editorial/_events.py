"""Small event helpers shared by editorial mutation modules."""

from __future__ import annotations

from typing import Any, Mapping

from megaplan.store import Store, deterministic_idempotency_key

from .errors import EditorialNotFound


def get_field(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(key, default)
    return getattr(record, key, default)


def dump_record(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    if isinstance(record, Mapping):
        return dict(record)
    return dict(record)


def require_epic(store: Store, epic_id: str) -> Any:
    epic = store.load_epic(epic_id)
    if epic is None:
        raise EditorialNotFound(f"Epic not found: {epic_id}", details={"epic_id": epic_id})
    return epic


def transaction_id(store: Store, epic_id: str, tx: Any, fallback: str) -> str:
    return getattr(tx, "tx_id", None) or store.latest_transaction_id(epic_id) or fallback


def record_event(
    *,
    store: Store,
    epic_id: str,
    transaction_id_value: str,
    event_type: str,
    summary: str,
    prior_state: dict[str, Any] | None,
    turn_id: str | None,
    idempotency_key: str,
) -> Any:
    return store.record_epic_event(
        epic_id=epic_id,
        transaction_id=transaction_id_value,
        event_type=event_type,
        summary=summary,
        prior_state=prior_state,
        turn_id=turn_id,
        idempotency_key=deterministic_idempotency_key(idempotency_key, "event"),
    )
