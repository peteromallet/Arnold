"""VP to-do list state for the resident special-requests sweep.

A small JSON file the user edits directly (default
``.megaplan/resident/vp_todo_list.json``). The resident agent works through
pending items each sweep; completing an item clears it from the file instantly,
while failing an item retains it (status ``failed``) for retry or manual review.

Shared by the scheduled sweep handler (reads pending items) and the resident
tool surface (read / complete / fail / add).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import json
import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from .provenance import normalize_delegation_provenance

PENDING = "pending"
COMPLETED = "completed"
DONE = "done"
DELEGATED = "delegated_to_canonical_run"
SUPERSEDED = "superseded_by_existing_run"
# Compatibility token written by an unreleased reconciliation draft.  Keep it
# readable so the supported migration below can normalize it to SUPERSEDED;
# older resident processes only recognize SUPERSEDED.
SUPERSEDED_BY_RECORD = "superseded_by_canonical_record"
BLOCKED = "blocked"
FAILED = "failed"
CANCELLED = "cancelled"
_STATUSES = {
    PENDING,
    DONE,
    COMPLETED,
    DELEGATED,
    SUPERSEDED,
    SUPERSEDED_BY_RECORD,
    BLOCKED,
    FAILED,
    CANCELLED,
}
DEFAULT_UNCHANGED_CYCLE_ESCALATION_THRESHOLD = 3


class TodoItem(TypedDict):
    id: str
    task: str
    status: str
    result: str
    reason: str
    updated_at: str
    when: str
    launch_provenance: NotRequired[dict[str, Any]]
    canonical_run_id: NotRequired[str]
    canonical_run_evidence: NotRequired[str]
    canonical_record_id: NotRequired[str]
    canonical_record_evidence: NotRequired[str]
    resolution: NotRequired[str]
    transition_history: NotRequired[list[dict[str, Any]]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return secrets.token_hex(4)


def load_items(path: Path) -> list[TodoItem]:
    """Return the items list, tolerating a missing / empty / malformed file."""
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [_coerce_item(item) for item in items]


def _save_items_unlocked(path: Path, items: list[TodoItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"items": items}, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def _mutation_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_items(path: Path, items: list[TodoItem]) -> None:
    """Atomically replace the list while fencing concurrent state transitions."""

    with _mutation_lock(path):
        _save_items_unlocked(path, items)


def _coerce_item(item: Any) -> TodoItem:
    if not isinstance(item, dict):
        text = str(item).strip()
        return {
            "id": _new_id(),
            "task": text,
            "status": PENDING if text else DONE,
            "result": "",
            "reason": "",
            "updated_at": _now_iso(),
            "when": "",
        }
    task = str(item.get("task", "")).strip()
    status = str(item.get("status", PENDING)).strip() or PENDING
    if status not in _STATUSES:
        status = PENDING
    coerced: TodoItem = {
        "id": str(item.get("id") or _new_id()),
        "task": task,
        "status": status,
        "result": str(item.get("result", "") or ""),
        "reason": str(item.get("reason", "") or ""),
        "updated_at": str(item.get("updated_at", "") or _now_iso()),
        "when": str(item.get("when", "") or "").strip(),
    }
    provenance = item.get("launch_provenance")
    if isinstance(provenance, Mapping):
        try:
            coerced["launch_provenance"] = normalize_delegation_provenance(provenance)
        except ValueError:
            # A malformed legacy item stays visible but can never smuggle an
            # ambiguous reply target into a later scheduled launch.
            pass
    for key in (
        "canonical_run_id",
        "canonical_run_evidence",
        "canonical_record_id",
        "canonical_record_evidence",
        "resolution",
    ):
        if value := str(item.get(key, "") or "").strip():
            coerced[key] = value  # type: ignore[literal-required]
    history = item.get("transition_history")
    if isinstance(history, list):
        coerced["transition_history"] = [dict(row) for row in history if isinstance(row, Mapping)]
    return coerced


def public_item(item: TodoItem) -> dict[str, Any]:
    """Projection returned to the agent (stable, JSON-safe)."""
    return dict(item)


def pending_items(path: Path) -> list[TodoItem]:
    return [item for item in load_items(path) if item["status"] == PENDING and item["task"]]


def complete_item(path: Path, item_id: str, result: str) -> TodoItem | None:
    """Mark an item done and clear it from the active/retained file.

    Returns the completed item, or ``None`` if ``item_id`` was not found.
    """
    with _mutation_lock(path):
        items = load_items(path)
        for item in items:
            if item["id"] == item_id:
                _transition(item, DONE, result=result)
                _save_items_unlocked(
                    path, [candidate for candidate in items if candidate["id"] != item_id]
                )
                return item
    return None


def fail_item(path: Path, item_id: str, reason: str) -> TodoItem | None:
    """Mark the item failed but retain it for retry / manual review."""
    with _mutation_lock(path):
        items = load_items(path)
        for item in items:
            if item["id"] == item_id:
                _transition(item, FAILED, reason=reason)
                _save_items_unlocked(path, items)
                return item
    return None


def delegate_item(
    path: Path,
    item_id: str,
    *,
    canonical_run_id: str,
    evidence: str,
) -> TodoItem | None:
    """Transfer a pending item to one canonical durable run."""

    return _resolve_with_run(
        path,
        item_id,
        status=DELEGATED,
        canonical_run_id=canonical_run_id,
        evidence=evidence,
        resolution="durable managed run accepted custody",
    )


def supersede_item(
    path: Path,
    item_id: str,
    *,
    canonical_run_id: str,
    evidence: str,
    resolution: str,
) -> TodoItem | None:
    """Resolve a launch intent that an independently canonical run already satisfies."""

    return _resolve_with_run(
        path,
        item_id,
        status=SUPERSEDED,
        canonical_run_id=canonical_run_id,
        evidence=evidence,
        resolution=resolution,
    )


def supersede_by_record(
    path: Path,
    item_id: str,
    *,
    canonical_record_id: str,
    evidence: str,
    resolution: str,
) -> TodoItem | None:
    """Retire obsolete todo intent using a durable canonical replacement record.

    This transition is deliberately distinct from completion and from an
    already-running owner.  Initiative retirement/replacement evidence can
    prove that a retained request is no longer current without falsely proving
    that its requested work completed.
    """

    record_id = canonical_record_id.strip()
    evidence_ref = evidence.strip()
    why = resolution.strip()
    if not record_id or not evidence_ref or not why:
        raise ValueError("canonical record id, evidence, and resolution are required")
    with _mutation_lock(path):
        items = load_items(path)
        for item in items:
            if item["id"] != item_id:
                continue
            if item["status"] in {SUPERSEDED, SUPERSEDED_BY_RECORD}:
                if (
                    item.get("canonical_record_id") == record_id
                    and item.get("canonical_record_evidence") == evidence_ref
                ):
                    if item["status"] == SUPERSEDED_BY_RECORD:
                        previous = item["status"]
                        item["status"] = SUPERSEDED
                        item["updated_at"] = _now_iso()
                        history = list(item.get("transition_history") or [])
                        history.append(
                            {
                                "from": previous,
                                "to": SUPERSEDED,
                                "at": item["updated_at"],
                                "reason": "normalize to the established resident superseded token",
                            }
                        )
                        item["transition_history"] = history
                        _save_items_unlocked(path, items)
                    return item
                raise ValueError("todo item is already superseded by a different canonical record")
            if item["status"] != PENDING:
                raise ValueError(
                    f"todo item in {item['status']!r} cannot transition to "
                    f"{SUPERSEDED!r}"
                )
            _transition(
                item,
                SUPERSEDED,
                canonical_record_id=record_id,
                canonical_record_evidence=evidence_ref,
                resolution=why,
            )
            _save_items_unlocked(path, items)
            return item
    return None


def _resolve_with_run(
    path: Path,
    item_id: str,
    *,
    status: str,
    canonical_run_id: str,
    evidence: str,
    resolution: str,
) -> TodoItem | None:
    run_id = canonical_run_id.strip()
    evidence_ref = evidence.strip()
    why = resolution.strip()
    if not run_id or not evidence_ref or not why:
        raise ValueError("canonical run id, evidence, and resolution are required")
    with _mutation_lock(path):
        items = load_items(path)
        for item in items:
            if item["id"] != item_id:
                continue
            if item["status"] == status:
                if (
                    item.get("canonical_run_id") == run_id
                    and item.get("canonical_run_evidence") == evidence_ref
                ):
                    return item
                raise ValueError("todo item is already resolved by a different canonical run")
            if item["status"] != PENDING:
                raise ValueError(f"todo item in {item['status']!r} cannot transition to {status!r}")
            _transition(
                item,
                status,
                canonical_run_id=run_id,
                canonical_run_evidence=evidence_ref,
                resolution=why,
            )
            _save_items_unlocked(path, items)
            return item
    return None


def _transition(item: TodoItem, status: str, **changes: Any) -> None:
    previous = item["status"]
    if previous != PENDING and previous != status:
        raise ValueError(f"todo item in {previous!r} cannot transition to {status!r}")
    at = _now_iso()
    item["status"] = status
    item["updated_at"] = at
    for key, value in changes.items():
        item[key] = value
    history = list(item.get("transition_history") or [])
    if not history or history[-1].get("to") != status:
        history.append({"from": previous, "to": status, "at": at})
    item["transition_history"] = history


def add_item(
    path: Path,
    task: str,
    when: str = "",
    *,
    launch_provenance: Mapping[str, Any] | None = None,
) -> TodoItem:
    with _mutation_lock(path):
        items = load_items(path)
        item: TodoItem = {
            "id": _new_id(),
            "task": task.strip(),
            "status": PENDING,
            "result": "",
            "reason": "",
            "updated_at": _now_iso(),
            "when": (when or "").strip(),
        }
        if launch_provenance is not None:
            item["launch_provenance"] = normalize_delegation_provenance(launch_provenance)
        items.append(item)
        _save_items_unlocked(path, items)
        return item
