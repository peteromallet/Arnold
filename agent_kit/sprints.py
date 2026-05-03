"""Deterministic sprint shaping and queue operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JSONDict = dict[str, Any]
PENDING_REASON_DEFAULT = "no reason given"
VALID_SPRINT_STATUSES = {"proposed", "queued", "pending", "done"}
VALID_ITEM_COMPLEXITIES = {"small", "medium", "large"}
VALID_ITEM_STATUSES = {"open", "in_progress", "done"}
CONFIRMATION_PHRASES = {
    "yes",
    "y",
    "yeah",
    "yep",
    "correct",
    "confirmed",
    "confirm",
    "approved",
    "approve",
    "looks good",
    "that works",
    "ship it",
    "lock it in",
    "lock in",
    "go ahead",
}


@dataclass(frozen=True)
class SprintValidationError(ValueError):
    errors: tuple[JSONDict, ...]


@dataclass
class SprintChangeSet:
    changes: list[JSONDict] = field(default_factory=list)

    def add(self, kind: str, **details: Any) -> None:
        self.changes.append({"kind": kind, **details})


def apply_sprint_changes(store: Any, epic_id: str, payload: JSONDict) -> list[JSONDict]:
    """Apply structured sprint operations and return a compact change summary."""

    changes = SprintChangeSet()
    if "replace" in payload:
        _replace_sprints(store, epic_id, _list_payload(payload["replace"]), changes)
    if "upsert" in payload:
        _upsert_sprints(store, epic_id, _list_payload(payload["upsert"]), changes)
    if payload.get("lock_in") is not None:
        _lock_in(store, epic_id, payload.get("lock_in"), changes)
    if "queue" in payload:
        _queue(store, epic_id, dict(payload["queue"]), changes)
    if "pend" in payload:
        _pend(store, epic_id, dict(payload["pend"]), changes)
    if "reorder" in payload:
        _reorder(store, epic_id, payload["reorder"], changes)
    _normalize_gapless_queue(store, epic_id)
    return changes.changes


def restore_sprints(store: Any, epic_id: str, snapshots: list[JSONDict]) -> None:
    for sprint in store.list_sprints(epic_id):
        store.delete_sprint(str(sprint["id"]))
    for snapshot in sorted(snapshots, key=lambda row: int(row.get("sprint_number") or 0)):
        restored = store.create_sprint(
            epic_id=epic_id,
            sprint_number=int(snapshot["sprint_number"]),
            name=str(snapshot["name"]),
            goal=str(snapshot["goal"]),
            status=str(snapshot.get("status") or "proposed"),
            queue_position=snapshot.get("queue_position"),
            pending_reason=snapshot.get("pending_reason"),
            target_weeks=int(snapshot.get("target_weeks") or 2),
        )
        store.replace_sprint_items(restored["id"], snapshot.get("items") or [])


def validate_sprint_payload(row: JSONDict) -> JSONDict:
    errors: list[JSONDict] = []
    sprint_number = _positive_int(row.get("sprint_number"), "sprint_number", errors)
    name = str(row.get("name") or "").strip()
    goal = str(row.get("goal") or "").strip()
    status = str(row.get("status") or "proposed")
    target_weeks = _positive_int(row.get("target_weeks", 2), "target_weeks", errors)
    if not name:
        errors.append({"field": "name", "message": "Sprint name is required."})
    if not goal:
        errors.append({"field": "goal", "message": "Sprint goal is required."})
    if status not in VALID_SPRINT_STATUSES:
        errors.append({"field": "status", "message": f"Unsupported sprint status: {status}"})
    queue_position = row.get("queue_position")
    if queue_position is not None:
        queue_position = _positive_int(queue_position, "queue_position", errors)
    pending_reason = row.get("pending_reason")
    if status == "queued" and queue_position is None:
        errors.append({"field": "queue_position", "message": "Queued sprints need a queue position."})
    if status == "pending" and not pending_reason:
        pending_reason = PENDING_REASON_DEFAULT
    if status != "queued":
        queue_position = None
    items = [_validate_item(item, index) for index, item in enumerate(row.get("items") or [], start=1)]
    if not items:
        errors.append({"field": "items", "message": "Each sprint needs at least one PM-level item."})
    if errors:
        raise SprintValidationError(tuple(errors))
    return {
        "sprint_number": sprint_number,
        "name": name,
        "goal": goal,
        "status": status,
        "queue_position": queue_position,
        "pending_reason": pending_reason,
        "target_weeks": target_weeks,
        "items": items,
    }


def is_lock_in_confirmation(text: str) -> bool:
    normalized = " ".join(str(text or "").strip().lower().rstrip(".!").split())
    return normalized in CONFIRMATION_PHRASES


def _replace_sprints(store: Any, epic_id: str, rows: list[JSONDict], changes: SprintChangeSet) -> None:
    normalized = [validate_sprint_payload(row) for row in rows]
    _reject_duplicate_numbers([int(row["sprint_number"]) for row in normalized], "replace")
    for sprint in store.list_sprints(epic_id):
        store.delete_sprint(str(sprint["id"]))
    for row in normalized:
        created = store.create_sprint(epic_id=epic_id, **_sprint_fields(row))
        store.replace_sprint_items(created["id"], row["items"])
    changes.add("replace", count=len(normalized))


def _upsert_sprints(store: Any, epic_id: str, rows: list[JSONDict], changes: SprintChangeSet) -> None:
    by_number = {int(sprint["sprint_number"]): sprint for sprint in store.list_sprints(epic_id)}
    normalized = [validate_sprint_payload(row) for row in rows]
    _reject_duplicate_numbers([int(row["sprint_number"]) for row in normalized], "upsert")
    for row in normalized:
        existing = by_number.get(int(row["sprint_number"]))
        if existing:
            store.update_sprint(existing["id"], **_sprint_fields(row))
            store.replace_sprint_items(existing["id"], row["items"])
            changes.add("upsert", action="updated", sprint_number=row["sprint_number"])
        else:
            created = store.create_sprint(epic_id=epic_id, **_sprint_fields(row))
            store.replace_sprint_items(created["id"], row["items"])
            changes.add("upsert", action="created", sprint_number=row["sprint_number"])


def _lock_in(store: Any, epic_id: str, spec: Any, changes: SprintChangeSet) -> None:
    sprints = store.list_sprints(epic_id)
    if not sprints:
        raise SprintValidationError(({"field": "sprints", "message": "At least one sprint is required."},))
    known_numbers = {int(sprint["sprint_number"]) for sprint in sprints}
    explicit = spec if isinstance(spec, dict) else {}
    queued_numbers = [int(value) for value in explicit.get("queued", [])]
    pending_specs = explicit.get("pending", [])
    pending_by_number: dict[int, str] = {}
    for item in pending_specs:
        if isinstance(item, dict):
            pending_by_number[int(item["sprint_number"])] = str(item.get("pending_reason") or PENDING_REASON_DEFAULT)
        else:
            pending_by_number[int(item)] = PENDING_REASON_DEFAULT
    if not queued_numbers and not pending_by_number:
        queued_numbers = [int(sprints[0]["sprint_number"])]
        pending_by_number = {
            int(sprint["sprint_number"]): PENDING_REASON_DEFAULT
            for sprint in sprints[1:]
        }
    _validate_lock_in_assignments(known_numbers, queued_numbers, pending_by_number)
    _clear_queue_fields(store, sprints)
    position = 1
    for sprint in sorted(sprints, key=lambda row: int(row["sprint_number"])):
        number = int(sprint["sprint_number"])
        if number in queued_numbers:
            store.update_sprint(
                sprint["id"],
                status="queued",
                queue_position=position,
                pending_reason=None,
            )
            position += 1
        else:
            store.update_sprint(
                sprint["id"],
                status="pending",
                queue_position=None,
                pending_reason=pending_by_number.get(number, PENDING_REASON_DEFAULT),
                queued_at=None,
            )
    changes.add("lock_in", queued=queued_numbers, pending=sorted(pending_by_number))


def _validate_lock_in_assignments(
    known_numbers: set[int],
    queued_numbers: list[int],
    pending_by_number: dict[int, str],
) -> None:
    _reject_duplicate_numbers(queued_numbers, "lock_in.queued")
    pending_numbers = list(pending_by_number)
    assigned_numbers = [*queued_numbers, *pending_numbers]
    unknown = sorted(number for number in assigned_numbers if number not in known_numbers)
    if unknown:
        raise SprintValidationError(
            (
                {
                    "field": "lock_in",
                    "message": f"Unknown sprint numbers: {unknown}",
                    "sprint_numbers": unknown,
                },
            )
        )
    conflicts = sorted(set(queued_numbers) & set(pending_numbers))
    if conflicts:
        raise SprintValidationError(
            (
                {
                    "field": "lock_in",
                    "message": f"Sprints cannot be both queued and pending: {conflicts}",
                    "sprint_numbers": conflicts,
                },
            )
        )


def _queue(store: Any, epic_id: str, spec: JSONDict, changes: SprintChangeSet) -> None:
    sprint = _sprint_by_number(store, epic_id, int(spec["sprint_number"]))
    queued = [row for row in store.list_sprints(epic_id) if row.get("status") == "queued" and row["id"] != sprint["id"]]
    position = int(spec.get("queue_position") or len(queued) + 1)
    _clear_queue_fields(store, [sprint, *queued])
    ordered = sorted(queued, key=lambda row: int(row.get("queue_position") or 9999))
    ordered.insert(max(position - 1, 0), sprint)
    for index, row in enumerate(ordered, start=1):
        store.update_sprint(row["id"], status="queued", queue_position=index, pending_reason=None)
    changes.add("queue", sprint_number=int(sprint["sprint_number"]), queue_position=position)


def _pend(store: Any, epic_id: str, spec: JSONDict, changes: SprintChangeSet) -> None:
    sprint = _sprint_by_number(store, epic_id, int(spec["sprint_number"]))
    store.update_sprint(
        sprint["id"],
        status="pending",
        queue_position=None,
        pending_reason=str(spec.get("pending_reason") or PENDING_REASON_DEFAULT),
        queued_at=None,
    )
    changes.add("pend", sprint_number=int(sprint["sprint_number"]))


def _reorder(store: Any, epic_id: str, spec: Any, changes: SprintChangeSet) -> None:
    numbers = spec.get("queued_sprint_numbers") if isinstance(spec, dict) else spec
    ordered_numbers = [int(number) for number in numbers]
    _reject_duplicate_numbers(ordered_numbers, "reorder")
    by_number = {int(sprint["sprint_number"]): sprint for sprint in store.list_sprints(epic_id)}
    missing = [number for number in ordered_numbers if number not in by_number]
    if missing:
        raise SprintValidationError(({"field": "reorder", "message": f"Unknown sprint numbers: {missing}"},))
    ordered = [by_number[number] for number in ordered_numbers]
    queued_tail = [
        sprint
        for sprint in store.list_sprints(epic_id)
        if sprint.get("status") == "queued" and int(sprint["sprint_number"]) not in ordered_numbers
    ]
    _clear_queue_fields(store, [*ordered, *queued_tail])
    for position, sprint in enumerate([*ordered, *queued_tail], start=1):
        store.update_sprint(sprint["id"], status="queued", queue_position=position, pending_reason=None)
    changes.add("reorder", queued_sprint_numbers=ordered_numbers)


def _normalize_gapless_queue(store: Any, epic_id: str) -> None:
    queued = [
        sprint
        for sprint in store.list_sprints(epic_id)
        if sprint.get("status") == "queued"
    ]
    _clear_queue_fields(store, queued)
    for position, sprint in enumerate(
        sorted(queued, key=lambda row: (int(row.get("queue_position") or 9999), int(row["sprint_number"]))),
        start=1,
    ):
        store.update_sprint(sprint["id"], status="queued", queue_position=position, pending_reason=None)


def _clear_queue_fields(store: Any, sprints: list[JSONDict]) -> None:
    for sprint in sprints:
        store.update_sprint(
            sprint["id"],
            status="proposed",
            queue_position=None,
            pending_reason=None,
            queued_at=None,
        )


def _sprint_by_number(store: Any, epic_id: str, sprint_number: int) -> JSONDict:
    for sprint in store.list_sprints(epic_id):
        if int(sprint["sprint_number"]) == sprint_number:
            return sprint
    raise SprintValidationError(({"field": "sprint_number", "message": f"Unknown sprint number: {sprint_number}"},))


def _validate_item(item: JSONDict, position: int) -> JSONDict:
    content = str(item.get("content") or "").strip()
    complexity = str(item.get("estimated_complexity") or "medium")
    status = str(item.get("status") or "open")
    errors = []
    if not content:
        errors.append({"field": "item.content", "message": "Sprint item content is required."})
    if complexity not in VALID_ITEM_COMPLEXITIES:
        errors.append({"field": "item.estimated_complexity", "message": f"Unsupported complexity: {complexity}"})
    if status not in VALID_ITEM_STATUSES:
        errors.append({"field": "item.status", "message": f"Unsupported item status: {status}"})
    if errors:
        raise SprintValidationError(tuple(errors))
    return {
        "content": content,
        "estimated_complexity": complexity,
        "status": status,
        "source_section": item.get("source_section"),
        "position": int(item.get("position") or position),
    }


def _positive_int(value: Any, field: str, errors: list[JSONDict]) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append({"field": field, "message": f"{field} must be a positive integer."})
        return 1
    if parsed <= 0:
        errors.append({"field": field, "message": f"{field} must be positive."})
        return 1
    return parsed


def _reject_duplicate_numbers(numbers: list[int], field: str) -> None:
    seen: set[int] = set()
    duplicates: list[int] = []
    for number in numbers:
        if number in seen and number not in duplicates:
            duplicates.append(number)
        seen.add(number)
    if duplicates:
        raise SprintValidationError(
            (
                {
                    "field": field,
                    "message": f"Duplicate sprint numbers are not allowed: {duplicates}",
                    "sprint_numbers": duplicates,
                },
            )
        )


def _sprint_fields(row: JSONDict) -> JSONDict:
    return {
        "sprint_number": row["sprint_number"],
        "name": row["name"],
        "goal": row["goal"],
        "status": row["status"],
        "queue_position": row["queue_position"],
        "pending_reason": row["pending_reason"],
        "target_weeks": row["target_weeks"],
    }


def _list_payload(value: Any) -> list[JSONDict]:
    if isinstance(value, list):
        return [dict(item) for item in value]
    return [dict(value)]


__all__ = [
    "PENDING_REASON_DEFAULT",
    "SprintValidationError",
    "apply_sprint_changes",
    "is_lock_in_confirmation",
    "restore_sprints",
    "validate_sprint_payload",
]
