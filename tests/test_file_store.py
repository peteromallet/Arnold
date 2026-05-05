from __future__ import annotations

from pathlib import Path

import pytest

from megaplan.editorial.body import update_body
from megaplan.store import FileStore, LocalDirBlobStore, deterministic_idempotency_key
from megaplan.store import ChecklistItemInput, RevisionConflict, StoreError
from megaplan.store.snapshot import canonical_sha256
from megaplan.tests.store_contract import run_arnold_adapter_contract, run_store_contract


def test_file_store_contract(tmp_path: Path) -> None:
    run_store_contract(lambda: FileStore(tmp_path / "store"))


def test_file_store_arnold_adapter_contract(tmp_path: Path) -> None:
    run_arnold_adapter_contract(lambda: FileStore(tmp_path / "store"))


def test_file_store_places_orphan_plans_under_orphan_root(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=None,
        name="legacy-plan",
        idea="legacy",
        idempotency_key=deterministic_idempotency_key("file-test", "legacy-plan"),
    )
    turn = store.create_turn(
        epic_id=None,
        triggered_by_message_ids=[],
        idempotency_key=deterministic_idempotency_key("file-test", "turn"),
    )
    message = store.create_message(
        epic_id=None,
        direction="inbound",
        content="bootstrap",
        idempotency_key=deterministic_idempotency_key("file-test", "message"),
    )

    assert (tmp_path / "store" / "orphan_plans" / plan.id / "plan.json").exists()
    assert (tmp_path / "store" / "turns" / f"{turn.id}.json").exists()
    assert (tmp_path / "store" / "messages" / f"{message.id}.json").exists()


def test_local_dir_blob_store_round_trip(tmp_path: Path) -> None:
    store = LocalDirBlobStore(tmp_path / "blobs")

    ref = store.put("blob-1", b"hello", content_type="text/plain")

    assert ref.blob_id == "blob-1"
    assert store.get("blob-1") == b"hello"
    assert store.stat("blob-1").size_bytes == 5
    assert store.url("blob-1").endswith("data.txt")

    store.delete("blob-1")

    assert store.stat("blob-1") is None


def test_file_store_normalizes_checklist_positions_across_mutations(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    items = store.add_checklist_items(
        epic.id,
        [
            ChecklistItemInput(content="First", position=10),
            ChecklistItemInput(content="Second", position=10),
            ChecklistItemInput(content="Third"),
        ],
    )
    assert [item.position for item in store.list_checklist_items(epic.id)] == [1, 2, 3]

    done = store.update_checklist_item(items[2].id, status="done", position=1)
    ordered = store.list_checklist_items(epic.id)
    assert [item.id for item in ordered][0] == items[2].id
    assert [item.position for item in ordered] == [1, 2, 3]
    assert done.completed_at is not None
    assert {item.id: item for item in store.list_checklist_items(epic.id)}[items[2].id].completed_at == done.completed_at

    store.delete_checklist_items([items[0].id])
    assert [item.position for item in store.list_checklist_items(epic.id)] == [1, 2]

    replaced = store.replace_checklist(
        epic.id,
        [
            ChecklistItemInput(content="Done", status="done", position=3, completed_at=done.completed_at),
            ChecklistItemInput(content="Open", position=3),
        ],
    )
    assert [item.position for item in replaced] == [1, 2]
    assert replaced[0].status == "done"
    assert replaced[0].completed_at == done.completed_at


def test_file_store_set_sprint_queue_validates_and_cleans_stale_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    first = store.create_sprint(epic_id=epic.id, sprint_number=1, name="One", goal="One")
    second = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Two")
    third = store.create_sprint(epic_id=epic.id, sprint_number=3, name="Three", goal="Three")

    queued = store.set_sprint_queue(epic.id, [first.id, second.id], {third.id: "blocked"})
    assert [(row.id, row.status, row.queue_position, row.pending_reason) for row in queued] == [
        (first.id, "queued", 1, None),
        (second.id, "queued", 2, None),
        (third.id, "pending", None, "blocked"),
    ]

    cleaned = store.set_sprint_queue(epic.id, [second.id], {})
    by_id = {row.id: row for row in cleaned}
    assert by_id[second.id].status == "queued"
    assert by_id[second.id].queue_position == 1
    assert by_id[first.id].status == "proposed"
    assert by_id[first.id].queue_position is None
    assert by_id[third.id].status == "proposed"
    assert by_id[third.id].pending_reason is None

    for ordered, pending, match in [
        ([second.id, second.id], {}, "Duplicate queued"),
        ([second.id], {second.id: "also"}, "both queued and pending"),
        (["missing"], {}, "Unknown sprint"),
        ([], {first.id: ""}, "Pending sprints require"),
    ]:
        try:
            store.set_sprint_queue(epic.id, ordered, pending)
        except Exception as exc:
            assert match in str(exc)
        else:
            raise AssertionError(f"expected {match}")


def test_file_store_plan_lifecycle_fields_round_trip(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=None,
        name="plan",
        idea="idea",
        latest_failure={"kind": "blocked", "message": "needs input"},
        resume_cursor={"phase": "execute", "batch_index": 2},
    )
    loaded = store.load_plan(plan.id)
    assert loaded.latest_failure == {"kind": "blocked", "message": "needs input"}
    assert loaded.resume_cursor == {"phase": "execute", "batch_index": 2}

    updated = store.update_plan(
        plan.id,
        expected_revision=loaded.revision,
        current_state="blocked",
        latest_failure={"kind": "worker_blocked"},
        resume_cursor={"phase": "review"},
    )
    assert updated.current_state == "blocked"
    assert store.load_plan(plan.id).resume_cursor == {"phase": "review"}


def test_file_store_snapshot_reads_staged_transaction_writes(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Before")

    with store.transaction(epic.id):
        updated = store.update_body(epic.id, "After", expected_revision=epic.revision)
        snapshot = store.capture_epic_snapshot(epic.id)

    assert updated.revision == epic.revision + 1
    assert snapshot.body == "After"
    assert snapshot.epic["revision"] == updated.revision


def test_file_store_replay_events_are_ascending_while_public_list_is_descending(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")

    first = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="tx_1",
        event_type="body_edit",
        summary="first",
        prior_state={},
        turn_id=None,
    )
    second = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="tx_2",
        event_type="body_edit",
        summary="second",
        prior_state={},
        turn_id=None,
    )

    assert [event.id for event in store.list_epic_events(epic.id)] == [second.id, first.id]
    assert [event.id for event in store.list_epic_events_for_replay(epic.id)] == [first.id, second.id]
    assert store.latest_transaction_id(epic.id) == "tx_2"


def test_canonical_snapshot_hash_matches_for_semantically_identical_file_stores(tmp_path: Path) -> None:
    left = FileStore(tmp_path / "left")
    right = FileStore(tmp_path / "right")
    epic = left.create_epic(title="Epic", goal="Goal", body="Body")
    right._save_model(right._epic_path(epic.id), epic, journal_root=right._journal_root_for_epic(epic.id))
    right._commit_write(right._body_path(epic.id), b"Body", journal_root=right._journal_root_for_epic(epic.id))

    assert canonical_sha256(left.capture_epic_snapshot(epic.id)) == canonical_sha256(right.capture_epic_snapshot(epic.id))


def test_file_store_fts_search_top_results_stable_after_reindex(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epics = [
        store.create_epic(title="Alpha launch", goal="needle", body="body needle"),
        store.create_epic(title="Beta", goal="needle goal", body="body"),
        store.create_epic(title="Gamma", goal="other", body="needle body"),
        store.create_epic(title="Delta", goal="other", body="needle body"),
    ]

    first = [row.id for row in store.search_epics(query="needle", limit=3)]
    store.rebuild_search_index()
    second = [row.id for row in store.search_epics(query="needle", limit=3)]

    assert first == second
    assert first[:2] == [epics[0].id, epics[1].id]
    assert set(first[2:]).issubset({epics[2].id, epics[3].id})
    assert all(row.match_tier is not None for row in store.search_epics(query="needle", limit=3))


def test_file_store_revert_restores_target_pre_state_and_keeps_revision_monotonic(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Original")
    first = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        body="First",
        expected_revision=epic.revision,
    )
    first_event = store.list_epic_events(epic.id)[0]
    second = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        body="Second",
        expected_revision=first.revision,
    )

    reverted = store.revert(epic.id, first_event.transaction_id, expected_revision=second.revision)

    assert reverted.revision == second.revision + 1
    assert store.load_body(epic.id) == "Original"
    events = store.list_epic_events(epic.id)
    assert events[0].event_type == "reverted_to"
    assert events[0].prior_state["reverted_to_transaction_id"] == first_event.transaction_id
    assert events[0].pre_state["body"] == "Second"
    assert events[0].post_state["body"] == "Original"
    assert events[0].post_state["epic"]["revision"] == reverted.revision

    with pytest.raises(RevisionConflict):
        store.revert(epic.id, first_event.transaction_id, expected_revision=second.revision)
    assert store.load_body(epic.id) == "Original"


def test_file_store_revert_rejects_legacy_event_without_full_snapshot(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Original")
    event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="legacy-tx",
        event_type="body_edit",
        summary="legacy",
        prior_state={},
    )

    with pytest.raises(StoreError, match="lacks pre_state snapshot"):
        store.revert(epic.id, event.transaction_id, expected_revision=epic.revision)


def test_file_store_get_epic_at_time_uses_post_state_with_replay_ties(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Original")
    first = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        body="First",
        expected_revision=epic.revision,
    )
    second = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        body="Second",
        expected_revision=first.revision,
    )
    events = store.list_epic_events_for_replay(epic.id)

    at_first = store.get_epic_at_time(epic.id, events[0].occurred_at)
    at_second = store.get_epic_at_time(epic.id, events[1].occurred_at)

    assert at_first is not None
    assert at_first.body == "First"
    assert at_second is not None
    assert at_second.body == "Second"
    assert at_second.epic["revision"] == second.revision
