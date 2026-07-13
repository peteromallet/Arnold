"""VP to-do list state for the resident special-requests sweep.

A small JSON file the user edits directly (default
``.megaplan/resident/vp_todo_list.json``). The resident agent works through
pending items each sweep; completing an item clears it from the file instantly,
while failing an item retains it (status ``failed``) for retry or manual review.

Shared by the scheduled sweep handler (reads pending items) and the resident
tool surface (read / complete / fail / add).
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from .provenance import normalize_delegation_provenance

PENDING = "pending"
DONE = "done"
FAILED = "failed"
_STATUSES = {PENDING, DONE, FAILED}


class TodoItem(TypedDict):
    id: str
    task: str
    status: str
    result: str
    reason: str
    updated_at: str
    when: str
    launch_provenance: NotRequired[dict[str, Any]]


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


def save_items(path: Path, items: list[TodoItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"items": items}, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


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
    return coerced


def public_item(item: TodoItem) -> dict[str, Any]:
    """Projection returned to the agent (stable, JSON-safe)."""
    return dict(item)


def pending_items(path: Path) -> list[TodoItem]:
    return [item for item in load_items(path) if item["status"] == PENDING and item["task"]]


def complete_item(path: Path, item_id: str, result: str) -> TodoItem | None:
    """Mark the item done and remove it from the file (the 'clear on acted' step).

    Returns the completed item, or ``None`` if ``item_id`` was not found.
    """
    items = load_items(path)
    matched: TodoItem | None = None
    for item in items:
        if item["id"] == item_id:
            item["status"] = DONE
            item["result"] = result
            item["updated_at"] = _now_iso()
            matched = item
            break
    if matched is None:
        return None
    save_items(path, [item for item in items if item["id"] != item_id])
    return matched


def fail_item(path: Path, item_id: str, reason: str) -> TodoItem | None:
    """Mark the item failed but retain it for retry / manual review."""
    items = load_items(path)
    for item in items:
        if item["id"] == item_id:
            item["status"] = FAILED
            item["reason"] = reason
            item["updated_at"] = _now_iso()
            save_items(path, items)
            return item
    return None


def add_item(
    path: Path,
    task: str,
    when: str = "",
    *,
    launch_provenance: Mapping[str, Any] | None = None,
) -> TodoItem:
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
    save_items(path, items)
    return item
