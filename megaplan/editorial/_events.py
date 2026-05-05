"""Small event helpers shared by editorial mutation modules."""

from __future__ import annotations

from typing import Any, Mapping

from megaplan.store import Store, deterministic_idempotency_key
from megaplan.store.snapshot import canonical_json_dumps, canonical_sha256

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


def capture_snapshot(store: Store, epic_id: str) -> Any:
    return store.capture_epic_snapshot(epic_id)


def snapshot_payload(snapshot: Any | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return dump_record(snapshot)


def record_event(
    *,
    store: Store,
    epic_id: str,
    transaction_id_value: str,
    event_type: str,
    summary: str,
    prior_state: dict[str, Any] | None,
    pre_snapshot: Any | None,
    turn_id: str | None,
    idempotency_key: str,
) -> Any:
    post_snapshot = capture_snapshot(store, epic_id)
    pre_state = snapshot_payload(pre_snapshot)
    post_state = snapshot_payload(post_snapshot)
    return store.record_epic_event(
        epic_id=epic_id,
        transaction_id=transaction_id_value,
        event_type=event_type,
        summary=summary,
        prior_state=prior_state,
        pre_state=pre_state,
        post_state=post_state,
        pre_state_canonical_json=canonical_json_dumps(pre_state) if pre_state is not None else None,
        post_state_canonical_json=canonical_json_dumps(post_state),
        pre_state_sha256=canonical_sha256(pre_state) if pre_state is not None else None,
        post_state_sha256=canonical_sha256(post_state),
        turn_id=turn_id,
        idempotency_key=deterministic_idempotency_key(idempotency_key, "event"),
    )
