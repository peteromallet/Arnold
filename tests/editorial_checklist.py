from __future__ import annotations

from pathlib import Path

import pytest

from megaplan.editorial import checklist
from megaplan.editorial.errors import EditorialNotFound, EditorialValidationError, EditorialWorkflowError
from megaplan.store import ChecklistItemInput, FileStore


def _store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "store")


def test_checklist_crud_status_helpers_and_events(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")

    items = checklist.add_items(store=store, epic_id=epic.id, actor_id="actor", contents=["One", "Two"])
    assert [item.position for item in items] == [1, 2]

    done = checklist.mark_done(store=store, epic_id=epic.id, actor_id="actor", item_id=items[0].id)
    assert done.status == "done"
    assert done.completed_at is not None

    skipped = checklist.mark_skipped(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        item_id=items[1].id,
        skip_reason="Not needed",
    )
    assert skipped.status == "skipped"
    assert skipped.skip_reason == "Not needed"

    reopened = checklist.mark_open(store=store, epic_id=epic.id, actor_id="actor", item_id=items[1].id)
    assert reopened.status == "open"
    assert reopened.skip_reason is None

    checklist.delete_items(store=store, epic_id=epic.id, actor_id="actor", item_ids=[items[0].id])
    remaining = checklist.list_items(store=store, epic_id=epic.id)
    assert [item.id for item in remaining] == [items[1].id]
    assert [item.position for item in remaining] == [1]
    assert [event.event_type for event in store.list_epic_events(epic.id)] == [
        "checklist_change",
        "checklist_change",
        "checklist_change",
        "checklist_change",
        "checklist_change",
    ]


def test_checklist_update_and_supersession_preserve_status_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    first, second = checklist.add_items(store=store, epic_id=epic.id, actor_id="actor", contents=["One", "Two"])

    updated = checklist.update_item(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        item_id=first.id,
        content="One revised",
    )
    assert updated.content == "One revised"

    superseded = checklist.mark_superseded(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        item_id=first.id,
        superseded_by_item_id=second.id,
    )
    assert superseded.status == "superseded"
    assert superseded.superseded_by_item_id == second.id

    reopened = checklist.mark_open(store=store, epic_id=epic.id, actor_id="actor", item_id=first.id)
    assert reopened.status == "open"
    assert reopened.superseded_by_item_id is None


def test_checklist_reorder_and_single_move_rely_on_store_normalization(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    items = checklist.add_items(store=store, epic_id=epic.id, actor_id="actor", contents=["One", "Two", "Three"])

    moved = checklist.move_item(store=store, epic_id=epic.id, actor_id="actor", item_id=items[2].id, position=1)
    assert moved.id == items[2].id
    assert [item.position for item in checklist.list_items(store=store, epic_id=epic.id)] == [1, 2, 3]

    reordered = checklist.reorder_items(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        ordered_item_ids=[items[1].id, items[2].id, items[0].id],
    )
    assert [item.id for item in reordered] == [items[1].id, items[2].id, items[0].id]
    assert [item.position for item in reordered] == [1, 2, 3]


def test_checklist_replace_preserves_status_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    replacement = [
        ChecklistItemInput(content="Done", status="done"),
        ChecklistItemInput(content="Skipped", status="skipped", skip_reason="No longer needed"),
    ]

    items = checklist.replace_items(store=store, epic_id=epic.id, actor_id="actor", items=replacement)

    assert [item.position for item in items] == [1, 2]
    assert items[0].status == "done"
    assert items[1].skip_reason == "No longer needed"


def test_checklist_validates_status_specific_fields_and_ids(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    item = checklist.add_items(store=store, epic_id=epic.id, actor_id="actor", contents=["One"])[0]

    with pytest.raises(EditorialValidationError, match="skip reason"):
        checklist.mark_skipped(store=store, epic_id=epic.id, actor_id="actor", item_id=item.id, skip_reason="")
    with pytest.raises(EditorialValidationError, match="superseded_by_item_id"):
        checklist.mark_superseded(store=store, epic_id=epic.id, actor_id="actor", item_id=item.id, superseded_by_item_id="")
    with pytest.raises(EditorialNotFound):
        checklist.delete_items(store=store, epic_id=epic.id, actor_id="actor", item_ids=["missing"])
    with pytest.raises(EditorialValidationError, match="Duplicate"):
        checklist.reorder_items(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            ordered_item_ids=[item.id, item.id],
        )
    with pytest.raises(EditorialValidationError, match="include every current item"):
        checklist.reorder_items(store=store, epic_id=epic.id, actor_id="actor", ordered_item_ids=[])


def test_checklist_rejects_review_lockdown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="Goal", body="Body", state="planned")

    with pytest.raises(EditorialWorkflowError, match="checklist_change is locked"):
        checklist.add_items(store=store, epic_id=epic.id, actor_id="actor", contents=["Nope"])
