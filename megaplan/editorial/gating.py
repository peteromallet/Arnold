"""Store-backed Arnold editorial gate checks and lifecycle transitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from megaplan.schemas.base import utc_now
from megaplan.store import Store, deterministic_idempotency_key

from .errors import EditorialNotFound, EditorialWorkflowError
from .lockdown import scan_lockdown_phrases

TERMINAL_CHECKLIST_STATUSES = frozenset({"done", "skipped", "superseded"})
SUPPORTED_TRANSITIONS = {
    "shaping": frozenset({"sprinting"}),
    "sprinting": frozenset({"planned"}),
}
REQUIRED_HANDOFF_SECTIONS = ("Goal", "Key Decisions", "Deliverable")
MIN_HANDOFF_BODY_CHARS = 500


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    blockers: list[str] = field(default_factory=list)


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(key, default)
    return getattr(record, key, default)


def _dump(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    if isinstance(record, Mapping):
        return dict(record)
    return dict(record)


def _section_titles(body: str) -> set[str]:
    titles: set[str] = set()
    for line in body.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            titles.add(match.group(1).strip().casefold())
    return titles


def _has_section(body: str, title: str) -> bool:
    return title.casefold() in _section_titles(body)


def _body_blockers(body: str) -> list[str]:
    blockers: list[str] = []
    if len(body.strip()) < MIN_HANDOFF_BODY_CHARS:
        blockers.append(f"Epic body must be at least {MIN_HANDOFF_BODY_CHARS} characters before handoff")
    for section in ("Goal", "Deliverable"):
        if not _has_section(body, section):
            blockers.append(f"Epic body is missing required section: {section}")
    return blockers


def _handoff_section_blockers(body: str) -> list[str]:
    return [
        f"Epic body is missing required handoff section: {section}"
        for section in REQUIRED_HANDOFF_SECTIONS
        if not _has_section(body, section)
    ]


def _checklist_blockers(checklist_items: list[Any], *, require_all_resolved: bool) -> list[str]:
    if not checklist_items:
        return []
    unresolved = [
        item
        for item in checklist_items
        if (_get(item, "status") or "open") not in TERMINAL_CHECKLIST_STATUSES
    ]
    if require_all_resolved:
        if unresolved:
            return [f"Checklist has {len(unresolved)} unresolved item(s)"]
        return []
    allowed_unresolved = max(1, len(checklist_items) // 3)
    if len(unresolved) > allowed_unresolved:
        return [
            f"Checklist has {len(unresolved)} unresolved item(s); at most {allowed_unresolved} allowed"
        ]
    return []


def _sprint_blockers(sprints: list[Any]) -> list[str]:
    if not sprints:
        return ["At least one sprint is required before planning"]
    blockers: list[str] = []
    for sprint in sprints:
        sprint_id = _get(sprint, "id")
        status = _get(sprint, "status")
        if status == "queued":
            if _get(sprint, "queue_position") is None:
                blockers.append(f"Sprint {sprint_id} is queued without a queue position")
        elif status == "pending":
            if not _get(sprint, "pending_reason"):
                blockers.append(f"Sprint {sprint_id} is pending without a reason")
        else:
            blockers.append(f"Sprint {sprint_id} must be queued or pending before planning")
        if not _get(sprint, "items", []):
            blockers.append(f"Sprint {sprint_id} must include at least one sprint item")
    return blockers


def evaluate_state_transition(
    *,
    epic: Any,
    target_state: str,
    checklist_items: list[Any] | None = None,
    sprints: list[Any] | None = None,
) -> GateResult:
    """Return Arnold-equivalent blockers for an epic lifecycle transition."""

    source_state = _get(epic, "state")
    body = str(_get(epic, "body", "") or "")
    checklist_items = list(checklist_items or [])
    sprints = list(sprints or [])
    blockers: list[str] = []

    if source_state == target_state:
        return GateResult(allowed=True)
    if source_state in {"paused", "archived"}:
        blockers.append(f"Epic state '{source_state}' cannot transition through editorial gates")
    elif target_state not in SUPPORTED_TRANSITIONS.get(str(source_state), frozenset()):
        blockers.append(f"Unsupported transition: {source_state} -> {target_state}")

    if target_state == "sprinting":
        blockers.extend(_body_blockers(body))
        blockers.extend(_checklist_blockers(checklist_items, require_all_resolved=False))
    elif target_state == "planned":
        blockers.extend(_body_blockers(body))
        blockers.extend(_handoff_section_blockers(body))
        blockers.extend(_checklist_blockers(checklist_items, require_all_resolved=True))
        blockers.extend(_sprint_blockers(sprints))
        for finding in scan_lockdown_phrases(body):
            blockers.append(f"Lockdown placeholder '{finding.phrase}' on line {finding.line}")

    return GateResult(allowed=not blockers, blockers=blockers)


def transition_epic_state(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    target_state: str,
    expected_revision: int,
    turn_id: str | None = None,
    force: bool = False,
    idempotency_key: str | None = None,
) -> Any:
    """Validate and persist an Arnold-style epic state transition through Store."""

    epic = store.load_epic(epic_id)
    if epic is None:
        raise EditorialNotFound(f"Epic not found: {epic_id}", details={"epic_id": epic_id})
    checklist_items = store.list_checklist_items(epic_id)
    sprints = store.list_sprints_with_items(epic_id)
    gate = evaluate_state_transition(
        epic=epic,
        target_state=target_state,
        checklist_items=checklist_items,
        sprints=sprints,
    )
    if not gate.allowed and not force:
        raise EditorialWorkflowError(
            f"Transition blocked: {_get(epic, 'state')} -> {target_state}",
            details={"blockers": gate.blockers, "source_state": _get(epic, "state"), "target_state": target_state},
        )

    idem = idempotency_key or deterministic_idempotency_key(
        "editorial-state",
        epic_id,
        actor_id,
        _get(epic, "state"),
        target_state,
        expected_revision,
    )
    prior_state = {
        "epic": _dump(epic),
        "checklist": [_dump(item) for item in checklist_items],
        "sprints": [_dump(sprint) for sprint in sprints],
        "forced": force,
        "blockers": gate.blockers,
    }
    changes: dict[str, Any] = {"state": target_state}
    if target_state == "planned":
        changes["planned_at"] = utc_now()

    with store.transaction(epic_id=epic_id) as tx:
        updated = store.update_epic(
            epic_id,
            expected_revision=expected_revision,
            idempotency_key=idem,
            **changes,
        )
        transaction_id = getattr(tx, "tx_id", None) or store.latest_transaction_id(epic_id) or idem
        store.record_epic_event(
            epic_id=epic_id,
            transaction_id=transaction_id,
            event_type="state_change",
            summary=f"{actor_id} changed epic state from {_get(epic, 'state')} to {target_state}",
            prior_state=prior_state,
            turn_id=turn_id,
            idempotency_key=deterministic_idempotency_key(idem, "event"),
        )
    return updated
