from __future__ import annotations

from typing import Any

from arnold.pipelines.megaplan.editorial import checklist, sprints
from arnold.pipelines.megaplan.editorial.body import edit_section, read_body, update_body
from arnold.pipelines.megaplan.editorial.gating import transition_epic_state
from arnold.pipelines.megaplan.store import SprintItemInput


MANUAL_PARITY_NOTES = (
    "Generated IDs, transaction IDs, revisions, and timestamps are intentionally excluded from "
    "the automated Arnold parity comparison. Stable semantic fields are compared directly."
)


def _handoff_body() -> str:
    filler = (
        "This editorial transplant keeps all mutations behind Store APIs, preserves Arnold gate "
        "semantics, and gives reviewers deterministic snapshots for lifecycle, checklist, sprint, "
        "and body behavior. "
    )
    return "\n".join(
        [
            "# Goal",
            "Port Arnold editorial logic into Megaplan without direct database or filesystem writes.",
            "",
            "# Key Decisions",
            filler * 4,
            "",
            "# Deliverable",
            "A pure Python editorial API with transition gates, body editing, checklist tracking, and sprint queueing.",
        ]
    )


def _normalize_checklist(items: list[Any]) -> list[dict[str, Any]]:
    by_id = {item.id: item for item in items}
    normalized: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: row.position):
        superseded_target = by_id.get(item.superseded_by_item_id)
        normalized.append(
            {
                "content": item.content,
                "status": item.status,
                "position": item.position,
                "skip_reason": item.skip_reason,
                "superseded_by": superseded_target.content if superseded_target else None,
            }
        )
    return normalized


def _normalize_sprints(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for sprint in sorted(rows, key=lambda row: row.sprint_number):
        normalized.append(
            {
                "number": sprint.sprint_number,
                "name": sprint.name,
                "goal": sprint.goal,
                "status": sprint.status,
                "queue_position": sprint.queue_position,
                "pending_reason": sprint.pending_reason,
                "items": [item.content for item in sorted(sprint.items, key=lambda row: row.position)],
            }
        )
    return normalized


def test_arnold_editorial_flow_parity_compares_stable_semantics(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Editorial transplant", goal="Port Arnold", body="# Draft\nRough notes")

    epic = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        body=_handoff_body(),
        expected_revision=epic.revision,
    )
    epic = edit_section(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        heading="Deliverable",
        content="Acceptance includes gates, Store-backed CRUD, queue normalization, hot context reads, and persisted lifecycle records.",
        expected_revision=epic.revision,
    )

    items = checklist.add_items(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        contents=[
            "Confirm Store-only editorial writes",
            "Defer image management to Sprint 5",
            "Supersede direct runtime import audit",
        ],
    )
    checklist.mark_done(store=store, epic_id=epic.id, actor_id="pm", item_id=items[0].id)
    checklist.mark_skipped(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        item_id=items[1].id,
        skip_reason="Out of scope for Sprint 4",
    )
    checklist.mark_superseded(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        item_id=items[2].id,
        superseded_by_item_id=items[0].id,
    )
    checklist.reorder_items(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        ordered_item_ids=[items[1].id, items[0].id, items[2].id],
    )

    epic = transition_epic_state(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        target_state="sprinting",
        expected_revision=epic.revision,
    )

    first = sprints.create_sprint(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        sprint_number=1,
        name="Editorial API",
        goal="Port pure editorial operations",
    )
    second = sprints.create_sprint(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        sprint_number=2,
        name="Deferred Review",
        goal="Hold review-runner work for Sprint 5",
    )
    sprints.replace_sprint_items(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        sprint_id=first.id,
        items=[SprintItemInput(content="Implement Store-backed gates, body, checklist, and sprint queue APIs")],
    )
    sprints.replace_sprint_items(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        sprint_id=second.id,
        items=[SprintItemInput(content="Leave second opinions runner out of Sprint 4")],
    )
    sprints.set_sprint_queue(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        ordered_sprint_ids=[first.id],
        pending={second.id: "Requires Sprint 5 scope"},
    )

    epic = transition_epic_state(
        store=store,
        epic_id=epic.id,
        actor_id="pm",
        target_state="planned",
        expected_revision=epic.revision,
    )

    assert MANUAL_PARITY_NOTES.startswith("Generated IDs")
    assert {
        "state": epic.state,
        "body": read_body(store=store, epic_id=epic.id),
        "checklist": _normalize_checklist(checklist.list_items(store=store, epic_id=epic.id)),
        "sprints": _normalize_sprints(sprints.list_sprints_with_items(store=store, epic_id=epic.id)),
        "event_kinds": [event.event_type for event in store.list_epic_events_for_replay(epic.id)],
    } == {
        "state": "planned",
        "body": "\n".join(
            [
                "# Goal",
                "Port Arnold editorial logic into Megaplan without direct database or filesystem writes.",
                "",
                "# Key Decisions",
                (
                    "This editorial transplant keeps all mutations behind Store APIs, preserves Arnold gate "
                    "semantics, and gives reviewers deterministic snapshots for lifecycle, checklist, sprint, "
                    "and body behavior. "
                )
                * 4,
                "",
                "# Deliverable",
                "Acceptance includes gates, Store-backed CRUD, queue normalization, hot context reads, and persisted lifecycle records.",
                "",
            ]
        ),
        "checklist": [
            {
                "content": "Defer image management to Sprint 5",
                "status": "skipped",
                "position": 1,
                "skip_reason": "Out of scope for Sprint 4",
                "superseded_by": None,
            },
            {
                "content": "Confirm Store-only editorial writes",
                "status": "done",
                "position": 2,
                "skip_reason": None,
                "superseded_by": None,
            },
            {
                "content": "Supersede direct runtime import audit",
                "status": "superseded",
                "position": 3,
                "skip_reason": None,
                "superseded_by": "Confirm Store-only editorial writes",
            },
        ],
        "sprints": [
            {
                "number": 1,
                "name": "Editorial API",
                "goal": "Port pure editorial operations",
                "status": "queued",
                "queue_position": 1,
                "pending_reason": None,
                "items": ["Implement Store-backed gates, body, checklist, and sprint queue APIs"],
            },
            {
                "number": 2,
                "name": "Deferred Review",
                "goal": "Hold review-runner work for Sprint 5",
                "status": "pending",
                "queue_position": None,
                "pending_reason": "Requires Sprint 5 scope",
                "items": ["Leave second opinions runner out of Sprint 4"],
            },
        ],
        "event_kinds": [
            "body_edit",
            "body_edit",
            "checklist_change",
            "checklist_change",
            "checklist_change",
            "checklist_change",
            "checklist_change",
            "state_change",
            "sprints_change",
            "sprints_change",
            "sprints_change",
            "sprints_change",
            "sprint_status_change",
            "state_change",
        ],
    }
