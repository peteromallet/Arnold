from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.editorial.body import update_body
from arnold.pipelines.megaplan.store import (
    ControlMessageInput,
    CloudRunInput,
    FileStore,
    LocalDirBlobStore,
    ResidentConversationInput,
    ScheduledJobInput,
    SprintItemInput,
    deterministic_idempotency_key,
)
from arnold.pipelines.megaplan.store import ChecklistItemInput, RevisionConflict, StoreError
from arnold.pipelines.megaplan.store.snapshot import canonical_sha256
from arnold.pipelines.megaplan.tickets.files import read_ticket_file, slugify, ticket_file_path, write_ticket_file
from arnold.pipelines.megaplan.tickets.identity import repo_codebase_identity
from tests.contract._store_contract import run_arnold_adapter_contract, run_store_contract


def _init_git_repo(repo_root: Path) -> str:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Megaplan Tests"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
    (repo_root / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True)
    result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().splitlines()[0]


def test_file_store_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    run_store_contract(lambda: FileStore(tmp_path / "store", repo_root=repo_root))


def test_file_store_arnold_adapter_contract(tmp_path: Path) -> None:
    run_arnold_adapter_contract(lambda: FileStore(tmp_path / "store"))


def test_file_store_ticket_ops_refuse_without_repo_root_sha(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    store = FileStore(tmp_path / "store", repo_root=repo_root)

    with pytest.raises(StoreError, match="root commit"):
        store.create_ticket(
            codebase_id="any",
            title="No root",
            body="body",
            slug="no-root",
        )


def test_file_store_loads_legacy_null_ticket_with_normalized_codebase_without_writeback(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    store = FileStore(tmp_path / "store", repo_root=repo_root)
    legacy_path = ticket_file_path(repo_root, "LEGACY-1", slugify("Legacy ticket"))
    write_ticket_file(
        legacy_path,
        {
            "id": "LEGACY-1",
            "title": "Legacy ticket",
            "status": "open",
            "source": "human",
            "tags": ["legacy"],
            "codebase_id": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "last_edited_at": datetime(2026, 1, 1, tzinfo=UTC),
            "epics": [],
            "__body__": "legacy body",
        },
    )

    ticket = store.load_ticket("LEGACY-1")

    assert ticket is not None
    assert isinstance(ticket.codebase_id, str)
    assert store.resolve_codebase_by_root_sha(repo_codebase_identity(repo_root).root_commit_sha).id == ticket.codebase_id
    assert read_ticket_file(legacy_path)["codebase_id"] is None


def test_file_store_mutating_legacy_null_ticket_writes_back_normalized_codebase(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    store = FileStore(tmp_path / "store", repo_root=repo_root)
    legacy_path = ticket_file_path(repo_root, "LEGACY-2", slugify("Mutating legacy"))
    write_ticket_file(
        legacy_path,
        {
            "id": "LEGACY-2",
            "title": "Mutating legacy",
            "status": "open",
            "source": "human",
            "tags": [],
            "codebase_id": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "last_edited_at": datetime(2026, 1, 1, tzinfo=UTC),
            "epics": [],
            "__body__": "body",
        },
    )

    updated = store.update_ticket("LEGACY-2", status="dismissed")

    assert updated.status == "dismissed"
    assert read_ticket_file(legacy_path)["codebase_id"] == updated.codebase_id


def test_file_store_ticket_create_writes_repo_root_frontmatter_not_store_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    store = FileStore(tmp_path / "store", repo_root=repo_root)
    identity = repo_codebase_identity(repo_root)
    codebase = store.upsert_codebase(
        owner=identity.owner,
        name=identity.name,
        default_branch=identity.default_branch,
        root_commit_sha=identity.root_commit_sha,
    )

    ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Repo rooted",
        body="body",
        slug="repo-rooted",
    )

    assert (repo_root / ".megaplan" / "tickets" / f"{ticket.id}-repo-rooted.md").exists()
    assert not (tmp_path / "store" / ".megaplan" / "tickets").exists()


def test_file_store_ticket_links_use_repo_root_frontmatter_only(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    store = FileStore(tmp_path / "store", repo_root=repo_root)
    codebase = store._resolve_ticket_codebase()
    ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Linked ticket",
        body="body",
        slug="linked-ticket",
    )

    first = store.link_ticket_to_epic(
        ticket_id=ticket.id,
        epic_id="epic_1",
        resolves_on_complete=False,
    )
    relinked = store.link_ticket_to_epic(
        ticket_id=ticket.id,
        epic_id="epic_1",
        resolves_on_complete=True,
    )

    ticket_path = repo_root / ".megaplan" / "tickets" / f"{ticket.id}-linked-ticket.md"
    frontmatter = read_ticket_file(ticket_path)
    assert relinked.linked_at == first.linked_at
    assert frontmatter["epics"] == [
        {
            "epic_id": "epic_1",
            "resolves_on_complete": True,
            "linked_at": first.linked_at,
        }
    ]
    assert store.list_ticket_epic_links(ticket_id=ticket.id) == [relinked]
    assert not (tmp_path / "store" / "ticket_epics").exists()

    store.unlink_ticket_from_epic(ticket_id=ticket.id, epic_id="epic_1")

    assert read_ticket_file(ticket_path)["epics"] == []
    assert store.list_ticket_epic_links(ticket_id=ticket.id) == []
    assert not (tmp_path / "store" / "ticket_epics").exists()


def test_file_store_reads_facade_frontmatter_links_and_addresses_resolved(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    store = FileStore(tmp_path / "store", repo_root=repo_root)
    codebase = store._resolve_ticket_codebase()
    linked_at = datetime(2026, 1, 2, tzinfo=UTC)
    ticket_path = ticket_file_path(repo_root, "FRONT-1", slugify("Facade linked"))
    write_ticket_file(
        ticket_path,
        {
            "id": "FRONT-1",
            "title": "Facade linked",
            "status": "open",
            "source": "human",
            "tags": ["facade"],
            "codebase_id": codebase.id,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "last_edited_at": datetime(2026, 1, 1, tzinfo=UTC),
            "epics": [
                {
                    "epic_id": "epic_done",
                    "resolves_on_complete": True,
                    "linked_at": linked_at.isoformat(),
                }
            ],
            "__body__": "body",
        },
    )

    assert store.list_ticket_epic_links(epic_id="epic_done")[0].linked_at == linked_at
    assert store.address_tickets_resolved_by_epic("epic_done") == ["FRONT-1"]
    assert store.address_tickets_resolved_by_epic("epic_done") == []

    frontmatter = read_ticket_file(ticket_path)
    assert frontmatter["status"] == "addressed"
    assert frontmatter["epics"][0]["epic_id"] == "epic_done"
    assert not (tmp_path / "store" / "ticket_epics").exists()


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


def test_file_store_resident_rows_claiming_and_message_idempotency(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")

    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:g1:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
            metadata={"mode": "test"},
        )
    )
    same_conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:g1:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
            metadata={"mode": "updated"},
        )
    )
    assert same_conversation.id == conversation.id
    assert store.get_resident_conversation_by_key(transport="discord", conversation_key="discord:g1:c1").id == conversation.id

    first = store.create_message(
        epic_id=epic.id,
        conversation_id=conversation.id,
        direction="inbound",
        content="hello",
        idempotency_key="discord-message-1",
    )
    duplicate = store.create_message(
        epic_id=epic.id,
        conversation_id=conversation.id,
        direction="inbound",
        content="duplicate delivery",
        idempotency_key="discord-message-1",
    )
    assert duplicate.id == first.id
    assert duplicate.content == "hello"

    run = store.create_cloud_run(
        CloudRunInput(
            operation="status",
            conversation_id=conversation.id,
            epic_id=epic.id,
            provider="fake",
            idempotency_key="cloud-run-1",
        ),
        idempotency_key="cloud-run-1",
    )
    assert store.create_cloud_run(
        CloudRunInput(operation="status", conversation_id=conversation.id, epic_id=epic.id, idempotency_key="cloud-run-1"),
        idempotency_key="cloud-run-1",
    ).id == run.id

    due = store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation.id,
            cloud_run_id=run.id,
            epic_id=epic.id,
            scheduled_for=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    claimed = store.claim_due_scheduled_jobs(worker_id="worker-a", max=10)
    assert [job.id for job in claimed] == [due.id]
    assert claimed[0].claimed_by == "worker-a"
    assert claimed[0].attempt_count == 1

    stale = store.update_scheduled_job(
        due.id,
        status="claimed",
        claimed_by="worker-old",
        claimed_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    reclaimed = store.claim_due_scheduled_jobs(worker_id="worker-b", stale_after_seconds=60)
    assert [job.id for job in reclaimed] == [stale.id]
    assert reclaimed[0].claimed_by == "worker-b"


def test_file_store_plan_artifacts_are_recursive_and_path_safe(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=None,
        name="legacy-plan",
        idea="legacy",
        idempotency_key=deterministic_idempotency_key("file-test", "nested-artifact-plan"),
    )

    nested = store.write_plan_artifact(
        plan.id,
        "nested/state.bin",
        b"\x00\xffnested\n",
        idempotency_key=deterministic_idempotency_key("file-test", plan.id, "nested-artifact"),
    )
    root = store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"ok\": true}\n",
        idempotency_key=deterministic_idempotency_key("file-test", plan.id, "root-artifact"),
    )

    assert nested.name == "nested/state.bin"
    assert root.name == "state.json"
    assert [ref.name for ref in store.list_plan_artifacts(plan.id)] == ["nested/state.bin", "state.json"]
    assert store.read_plan_artifact(plan.id, "nested/state.bin") == b"\x00\xffnested\n"
    assert store.stat_plan_artifact(plan.id, "nested/state.bin").size_bytes == len(b"\x00\xffnested\n")

    for unsafe in ["/absolute.bin", "../escape.bin", "nested/../escape.bin", "nested//state.bin", "nested\\state.bin"]:
        with pytest.raises(ValueError, match="Unsafe|non-empty"):
            store.write_plan_artifact(plan.id, unsafe, b"bad")
        with pytest.raises(ValueError, match="Unsafe|non-empty"):
            store.read_plan_artifact(plan.id, unsafe)
        with pytest.raises(ValueError, match="Unsafe|non-empty"):
            store.stat_plan_artifact(plan.id, unsafe)


def test_local_dir_blob_store_round_trip(tmp_path: Path) -> None:
    store = LocalDirBlobStore(tmp_path / "blobs")

    ref = store.put("blob-1", b"hello", content_type="text/plain")

    assert ref.blob_id == "blob-1"
    assert store.get("blob-1") == b"hello"
    assert store.stat("blob-1").size_bytes == 5
    assert store.url("blob-1").endswith("data.txt")

    store.delete("blob-1")

    assert store.stat("blob-1") is None


def test_file_store_attach_image_replaces_active_reference_and_resolves_without_body_mutation(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="![alt](mp://image/diagram)")

    first = store.attach_image(
        epic_id=epic.id,
        content=b"first-image",
        content_type="image/png",
        reference_key="diagram",
    )
    second = store.attach_image(
        epic_id=epic.id,
        content=b"second-image",
        content_type="image/png",
        reference_key="diagram",
    )

    assert store.load_image(first.id).active is False
    assert second.active is True
    assert [row.id for row in store.list_active_images(epic.id)] == [second.id]
    assert store.blobs.get(second.blob_id) == b"second-image"
    assert store.resolve_image_reference(epic.id, "mp://image/diagram") == store.resolve_image_reference(epic.id, "image:diagram")
    assert store.load_body(epic.id) == "![alt](mp://image/diagram)"


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


def test_file_store_rejects_invalid_store_inputs_before_writes(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    existing = store.add_checklist_items(epic.id, [ChecklistItemInput(content="Existing")])
    invalid_checklist = ChecklistItemInput.model_construct(content="Bad", status="bogus", source="bot_inferred")

    with pytest.raises(ValueError):
        store.add_checklist_items(epic.id, [ChecklistItemInput(content="Valid"), invalid_checklist])
    assert [item.id for item in store.list_checklist_items(epic.id)] == [existing[0].id]

    with pytest.raises(ValueError):
        store.replace_checklist(epic.id, [invalid_checklist])
    assert [item.id for item in store.list_checklist_items(epic.id)] == [existing[0].id]

    sprint = store.create_sprint(epic_id=epic.id, sprint_number=1, name="One", goal="One")
    invalid_sprint_item = SprintItemInput.model_construct(content="Bad", estimated_complexity="enormous", status="open")
    with pytest.raises(ValueError):
        store.replace_sprint_items(sprint.id, [SprintItemInput(content="Valid"), invalid_sprint_item])
    assert store.list_sprint_items(sprint.id) == []

    invalid_control = ControlMessageInput.model_construct(
        epic_id=epic.id,
        actor_id="actor",
        intent="bogus",
        target_id="target",
        payload={},
        idempotency_key="invalid-control",
    )
    with pytest.raises(ValueError):
        store.put_control_message(invalid_control)
    assert store.claim_pending_control_messages(processor_id="proc") == []


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
