from __future__ import annotations

from pathlib import Path

import pytest

from megaplan.editorial import sprints
from megaplan.editorial.errors import EditorialNotFound, EditorialValidationError, EditorialWorkflowError
from megaplan.store import FileStore, RevisionConflict, SprintItemInput


def _store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "store")


def test_sprint_crud_items_queue_and_events(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")

    first = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=1, name="One", goal="First")
    second = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=2, name="Two", goal="Second")
    updated = sprints.update_sprint(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        sprint_id=first.id,
        expected_revision=first.revision,
        goal="Updated first",
    )
    assert updated.goal == "Updated first"

    items = sprints.replace_sprint_items(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        sprint_id=first.id,
        items=[SprintItemInput(content="Build first")],
    )
    assert [item.position for item in items] == [1]
    assert [item.content for item in sprints.list_sprint_items(store=store, sprint_id=first.id)] == ["Build first"]
    sprints_with_items = sprints.list_sprints_with_items(store=store, epic_id=epic.id)
    assert {row.id for row in sprints_with_items} == {first.id, second.id}
    assert [item.content for item in next(row.items for row in sprints_with_items if row.id == first.id)] == ["Build first"]

    queued = sprints.set_sprint_queue(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        ordered_sprint_ids=[first.id],
        pending={second.id: "blocked externally"},
    )
    by_id = {row.id: row for row in queued}
    assert by_id[first.id].status == "queued"
    assert by_id[first.id].queue_position == 1
    assert by_id[second.id].status == "pending"

    sprints.delete_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_id=second.id)
    assert [row.id for row in sprints.list_sprints(store=store, epic_id=epic.id)] == [first.id]
    event_types = [event.event_type for event in store.list_epic_events(epic.id)]
    assert event_types.count("sprints_change") == 5
    assert event_types.count("sprint_status_change") == 1


def test_sprint_queue_validation_and_stale_cleanup(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    first = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=1, name="One", goal="First")
    second = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=2, name="Two", goal="Second")

    sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=[first.id, second.id], pending={})
    cleaned = sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=[second.id], pending={})
    by_id = {row.id: row for row in cleaned}
    assert by_id[first.id].status == "proposed"
    assert by_id[first.id].queue_position is None
    assert by_id[second.id].queue_position == 1

    with pytest.raises(EditorialValidationError, match="Duplicate"):
        sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=[second.id, second.id], pending={})
    with pytest.raises(EditorialValidationError, match="both queued and pending"):
        sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=[second.id], pending={second.id: "also"})
    with pytest.raises(EditorialNotFound):
        sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=["missing"], pending={})
    with pytest.raises(EditorialValidationError, match="require a reason"):
        sprints.set_sprint_queue(store=store, epic_id=epic.id, actor_id="actor", ordered_sprint_ids=[], pending={first.id: ""})


def test_sprint_editorial_validates_empty_text_and_missing_sprint_ids(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")

    with pytest.raises(EditorialValidationError, match="name cannot be empty"):
        sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=1, name=" ", goal="First")

    sprint = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=1, name="One", goal="First")
    with pytest.raises(EditorialValidationError, match="content cannot be empty"):
        sprints.replace_sprint_items(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            sprint_id=sprint.id,
            items=[SprintItemInput(content=" ")],
        )
    with pytest.raises(EditorialNotFound):
        sprints.delete_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_id="missing")


def test_sprint_revision_conflict_and_lockdown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    sprint = sprints.create_sprint(store=store, epic_id=epic.id, actor_id="actor", sprint_number=1, name="One", goal="First")
    store.update_sprint(sprint.id, expected_revision=sprint.revision, goal="External")

    with pytest.raises(RevisionConflict):
        sprints.update_sprint(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            sprint_id=sprint.id,
            expected_revision=sprint.revision,
            goal="Stale",
        )

    planned = store.create_epic(title="Locked", goal="Goal", body="Body", state="planned")
    with pytest.raises(EditorialWorkflowError, match="sprints_change is locked"):
        sprints.create_sprint(store=store, epic_id=planned.id, actor_id="actor", sprint_number=1, name="No", goal="No")
