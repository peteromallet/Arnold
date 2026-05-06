from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from megaplan.store import (
    ChecklistItemInput,
    CloudRunInput,
    LeaseConflict,
    MultiStore,
    ResidentConversationInput,
    ScheduledJobInput,
    SprintItemInput,
    StoreError,
    deterministic_idempotency_key,
)
from megaplan.store.file import FileStore
from megaplan.schemas import MigrationRun


def _multi(tmp_path: Path) -> tuple[MultiStore, FileStore, FileStore]:
    file_store = FileStore(tmp_path / "file")
    db_store = FileStore(tmp_path / "db")
    return MultiStore(file_store=file_store, db_store=db_store, actor_id="actor"), file_store, db_store


def test_multi_store_routes_by_epic_home_backend(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)

    file_epic = store.create_epic(title="File", goal="g", body="file body", home_backend="file")
    db_epic = store.create_epic(title="DB", goal="g", body="db body", home_backend="db")

    assert file_store.load_epic(file_epic.id) is not None
    assert db_store.load_epic(file_epic.id) is None
    assert db_store.load_epic(db_epic.id) is not None
    assert store.load_body(file_epic.id) == "file body"
    assert store.load_body(db_epic.id) == "db body"

    updated = store.update_body(
        db_epic.id,
        "db body updated",
        expected_revision=db_epic.revision,
        idempotency_key=deterministic_idempotency_key("multi", db_epic.id, "body"),
    )
    assert updated.home_backend == "db"
    assert db_store.load_body(db_epic.id) == "db body updated"
    assert file_store.load_epic(db_epic.id) is None


def test_multi_store_missing_epic_fails_clearly(tmp_path: Path) -> None:
    store, _, _ = _multi(tmp_path)

    with pytest.raises(KeyError, match="not found in file or db backends"):
        store.load_body("missing-epic")


def test_multi_store_merged_epic_lists_are_deterministic(tmp_path: Path) -> None:
    store, _, _ = _multi(tmp_path)

    file_epic = store.create_epic(title="Shared term file", goal="g", body="needle", home_backend="file")
    db_epic = store.create_epic(title="Shared term db", goal="g", body="needle needle", home_backend="db")

    listed = store.list_epics(limit=10)
    listed_ids = [epic.id for epic in listed]
    assert listed_ids == sorted(listed_ids, key=lambda epic_id: (store.load_epic(epic_id).last_edited_at, epic_id), reverse=True)

    searched = store.search_epics(query="needle", limit=10)
    assert {file_epic.id, db_epic.id}.issubset({epic.id for epic in searched})
    assert [epic.id for epic in searched] == [
        epic.id
        for epic in sorted(
            searched,
            key=lambda epic: (int(epic.match_tier or 0), epic.last_edited_at, epic.id),
            reverse=True,
        )
    ]


def test_multi_store_search_merge_ignores_raw_cross_backend_rank(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    file_epic = store.create_epic(title="Needle title", goal="g", body="needle", home_backend="file")
    db_epic = store.create_epic(title="Plain", goal="g", body="needle needle needle", home_backend="db")

    file_rows = file_store.search_epics(query="needle", limit=10)
    db_rows = db_store.search_epics(query="needle", limit=10)
    assert file_rows and db_rows
    # The body-heavy DB row can have a backend-specific raw rank, but MultiStore
    # merges by normalized tier first so title matches remain stable.
    merged = store.search_epics(query="needle", limit=10)

    assert merged[0].id == file_epic.id
    assert {file_epic.id, db_epic.id}.issubset({row.id for row in merged})


def test_multi_store_acquire_execution_lease_derives_epic_id(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="b", home_backend="db")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="plan",
        idea="idea",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "plan"),
    )

    lease = store.acquire_execution_lease(
        plan.id,
        "holder",
        "local_cli",
        60,
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "lease"),
    )

    assert lease.epic_id == epic.id
    assert db_store.get_active_lease(plan.id).epic_id == epic.id


def test_multi_store_exported_from_package() -> None:
    from megaplan.store import MultiStore as ExportedMultiStore

    assert ExportedMultiStore is MultiStore


def test_multi_store_preserves_backend_checklist_normalization(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")

    created = store.add_checklist_items(
        epic.id,
        [
            ChecklistItemInput(content="First", position=5),
            ChecklistItemInput(content="Second", position=5),
            ChecklistItemInput(content="Third"),
        ],
    )
    assert [item.position for item in created] == [1, 2, 3]

    store.update_checklist_item(created[2].id, position=1, status="done")
    assert [item.id for item in db_store.list_checklist_items(epic.id)][0] == created[2].id
    assert [item.position for item in db_store.list_checklist_items(epic.id)] == [1, 2, 3]

    store.delete_checklist_items([created[0].id])
    assert [item.position for item in db_store.list_checklist_items(epic.id)] == [1, 2]

    replaced = store.replace_checklist(
        epic.id,
        [ChecklistItemInput(content="A", position=7), ChecklistItemInput(content="B", position=7)],
    )
    assert [item.position for item in replaced] == [1, 2]


def test_multi_store_preserves_backend_sprint_queue_cleanup(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")
    first = store.create_sprint(epic_id=epic.id, sprint_number=1, name="One", goal="One")
    second = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Two")
    third = store.create_sprint(epic_id=epic.id, sprint_number=3, name="Three", goal="Three")

    store.set_sprint_queue(epic.id, [first.id, second.id], {third.id: "blocked"})
    cleaned = store.set_sprint_queue(epic.id, [second.id], {})
    by_id = {row.id: row for row in cleaned}
    assert by_id[second.id].status == "queued"
    assert by_id[second.id].queue_position == 1
    assert by_id[first.id].status == "proposed"
    assert by_id[third.id].status == "proposed"
    assert {row.id: row for row in db_store.list_sprints(epic.id)}[third.id].pending_reason is None


def test_multi_store_plan_lifecycle_fields_round_trip_on_routed_backend(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="db-plan",
        idea="idea",
        latest_failure={"kind": "blocked"},
        resume_cursor={"phase": "execute", "batch_index": 4},
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "plan-lifecycle"),
    )

    loaded = store.load_plan(plan.id)
    assert loaded.latest_failure == {"kind": "blocked"}
    assert loaded.resume_cursor == {"phase": "execute", "batch_index": 4}
    assert db_store.load_plan(plan.id).resume_cursor == {"phase": "execute", "batch_index": 4}

    updated = store.update_plan(
        plan.id,
        expected_revision=loaded.revision,
        latest_failure={"kind": "failed"},
        resume_cursor={"phase": "review"},
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "plan-lifecycle-update"),
    )
    assert updated.resume_cursor == {"phase": "review"}
    assert db_store.load_plan(plan.id).latest_failure == {"kind": "failed"}


def test_multi_store_resident_records_live_on_db_backend_and_reject_file_home_cloud_runs(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    file_epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    db_epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")

    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:channel",
            active_epic_id=db_epic.id,
            guild_id="guild",
            channel_id="channel",
        )
    )
    assert file_store.load_resident_conversation(conversation.id) is None
    assert db_store.load_resident_conversation(conversation.id).conversation_key == "discord:guild:channel"

    message = store.create_message(
        epic_id=db_epic.id,
        conversation_id=conversation.id,
        direction="inbound",
        content="hello",
        idempotency_key="multi-resident-message",
    )
    assert db_store.load_message(message.id).conversation_id == conversation.id
    assert store.create_message(
        epic_id=db_epic.id,
        conversation_id=conversation.id,
        direction="inbound",
        content="duplicate",
        idempotency_key="multi-resident-message",
    ).id == message.id

    run = store.create_cloud_run(
        CloudRunInput(
            operation="status",
            conversation_id=conversation.id,
            epic_id=db_epic.id,
            provider="fake",
            idempotency_key="multi-cloud-run",
        ),
        idempotency_key="multi-cloud-run",
    )
    assert db_store.load_cloud_run(run.id).epic_id == db_epic.id

    job = store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation.id,
            cloud_run_id=run.id,
            epic_id=db_epic.id,
            scheduled_for=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    assert db_store.load_scheduled_job(job.id).cloud_run_id == run.id
    assert store.claim_due_scheduled_jobs(worker_id="resident-worker")[0].id == job.id

    with pytest.raises(StoreError, match="DB-home epic"):
        store.create_cloud_run(
            CloudRunInput(operation="status", conversation_id=conversation.id, epic_id=file_epic.id),
            idempotency_key="file-home-cloud-run",
        )


def test_migrate_epic_runs_seven_phases_and_tombstones_source(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    checklist = store.add_checklist_items(
        epic.id,
        [ChecklistItemInput(content="First", position=1)],
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "checklist"),
    )
    sprint = store.create_sprint(
        epic_id=epic.id,
        sprint_number=1,
        name="Sprint 1",
        goal="Goal",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "sprint"),
    )
    store.replace_sprint_items(
        sprint.id,
        [SprintItemInput(content="Ship", estimated_complexity="small", position=1)],
        idempotency_key=deterministic_idempotency_key("multi", sprint.id, "items"),
    )
    store.create_image(
        epic_id=epic.id,
        source="user_uploaded",
        storage_url="images/source.png",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "image"),
    )
    store.create_second_opinion(
        epic_id=epic.id,
        requested_by="user",
        focus_areas=["scope"],
        raw_response="raw",
        score=7,
        summary="summary",
        verdict="ok",
        model_used="mock",
        resulting_checklist_item_ids=[checklist[0].id],
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "opinion"),
    )
    store.create_feedback(
        kind="epic_specific",
        content="watch",
        source="user_volunteered",
        epic_id=epic.id,
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "feedback"),
    )
    codebase = store.create_codebase(
        owner="openai",
        name="megaplan",
        default_branch="main",
        repo_url="https://github.com/openai/megaplan.git",
        repo_workspace="/workspace/megaplan",
        scope="epic_specific",
        associated_epic_id=epic.id,
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "codebase"),
    )
    plan = store.create_plan(
        sprint_id=sprint.id,
        epic_id=epic.id,
        name="migration-plan",
        idea="move",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "plan"),
    )
    store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"ok\": true}\n",
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "artifact"),
    )

    run = store.migrate_epic(epic.id, to="db", ttl_seconds=60)

    assert run.phase == "complete"
    assert run.completed_at is not None
    assert run.manifest["entities"]["plan_artifacts_by_plan"] == {plan.id: ["state.json"]}
    assert run.manifest["entities"]["codebases"] == [codebase.id]
    assert run.copied_ids["plan_artifacts_by_plan"] == {plan.id: ["state.json"]}
    assert run.copied_ids["codebases"] == [codebase.id]
    assert run.blob_copy_progress[plan.id]["state.json"]
    assert file_store.load_epic(epic.id).migrated_to == run.id
    assert [row.id for row in file_store.list_epics()] == []
    target_epic = db_store.load_epic(epic.id)
    assert target_epic is not None
    assert target_epic.home_backend == "db"
    assert db_store.read_plan_artifact(plan.id, "state.json") == b"{\"ok\": true}\n"
    assert len(db_store.list_checklist_items(epic.id)) == 1
    assert len(db_store.list_sprints(epic.id)) == 1
    assert len(db_store.list_second_opinions(epic.id)) == 1
    assert len(db_store.list_images(epic_id=epic.id, active=None)) == 1
    copied_codebase = db_store.load_codebase(codebase.id)
    assert copied_codebase.repo_url == "https://github.com/openai/megaplan.git"
    assert copied_codebase.repo_workspace == "/workspace/megaplan"


def test_migrate_epic_copies_blob_backed_image_bytes_and_hashes(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="![alt](mp://image/diagram)", home_backend="file")
    image = store.attach_image(
        epic_id=epic.id,
        content=b"image-bytes",
        content_type="image/png",
        reference_key="diagram",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "blob-image"),
    )

    run = store.migrate_epic(epic.id, to="db", ttl_seconds=60)

    copied = db_store.load_active_image_by_reference(epic.id, "diagram")
    assert copied is not None
    assert copied.id == image.id
    assert db_store.blobs.get(copied.blob_id) == file_store.blobs.get(image.blob_id)
    assert run.blob_copy_progress["images"]["diagram"]["source_sha256"] == image.blob_sha256
    assert db_store.resolve_image_reference(epic.id, "mp://image/diagram") == db_store.resolve_image_reference(epic.id, "image:diagram")
    assert db_store.load_body(epic.id) == "![alt](mp://image/diagram)"


def test_migrate_epic_preflight_rejects_active_execution_lease(tmp_path: Path) -> None:
    store, _, _ = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="leased-plan",
        idea="move",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "leased-plan"),
    )
    store.acquire_execution_lease(
        plan.id,
        "holder",
        "local_cli",
        60,
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "lease"),
    )

    with pytest.raises(LeaseConflict, match="active execution leases"):
        store.migrate_epic(epic.id, to="db", ttl_seconds=60)


def test_migrate_epic_preflight_rejects_active_migration_collision(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    db_store.create_migration_run(
        MigrationRun(
            id="migration-live",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="copying_meta",
            holder_id="other",
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
    )

    with pytest.raises(LeaseConflict, match="already has active migration"):
        store.migrate_epic(epic.id, to="db", ttl_seconds=60)


def test_migrate_epic_rejects_target_collision_before_source_lock(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    existing = db_store.create_epic(title="Existing", goal="g", body="already there", home_backend="db")
    db_store._save_model(
        db_store._epic_path(epic.id),
        existing.model_copy(update={"id": epic.id}),
        journal_root=db_store._journal_root_for_epic(epic.id),
    )

    with pytest.raises(StoreError, match="Target backend already has active epic"):
        store.migrate_epic(epic.id, to="db", ttl_seconds=60)

    assert not file_store._lock_path(epic.id).exists()


def test_concurrent_migrate_attempt_fails_with_lease_busy_error(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    db_store.create_migration_run(
        MigrationRun(
            id="migration-concurrent",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="planning",
            holder_id="first-holder",
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
    )

    with pytest.raises(LeaseConflict, match="already has active migration"):
        store.migrate_epic(epic.id, to="db", ttl_seconds=60)


def test_migration_heartbeat_extends_active_run_without_resuming(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    old_expiry = datetime.now(UTC) + timedelta(seconds=1)
    db_store.create_migration_run(
        MigrationRun(
            id="migration-heartbeat",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="copying_meta",
            holder_id="actor",
            expires_at=old_expiry,
        )
    )

    heartbeated = db_store.heartbeat_migration("migration-heartbeat", ttl_seconds=120)

    assert heartbeated.phase == "copying_meta"
    assert heartbeated.holder_id == "actor"
    assert heartbeated.expires_at > old_expiry
    assert store.load_epic(epic.id).home_backend == "file"


def test_migrate_epic_db_to_file_tombstones_db_source(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")

    run = store.migrate_epic(epic.id, to="file", ttl_seconds=60)

    assert run.phase == "complete"
    source_epic = db_store.load_epic(epic.id)
    assert source_epic.migrated_to == run.id
    assert [row.id for row in db_store.list_epics()] == []
    target_epic = file_store.load_epic(epic.id)
    assert target_epic is not None
    assert target_epic.home_backend == "file"
    assert store.load_epic(epic.id).home_backend == "file"


def test_multi_store_fuzz_routes_mixed_backend_mutations(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    rng = random.Random(20260505)
    epics = [
        store.create_epic(
            title=f"Fuzz {index}",
            goal="g",
            body=f"body-{index}",
            home_backend="file" if index % 2 == 0 else "db",
        )
        for index in range(8)
    ]

    for step in range(40):
        epic = rng.choice(epics)
        op = rng.choice(["body", "plan", "list", "search"])
        if op == "body":
            current = store.load_epic(epic.id)
            updated = store.update_body(
                epic.id,
                f"body-{epic.id}-{step}",
                expected_revision=current.revision,
                idempotency_key=deterministic_idempotency_key("multi-fuzz", epic.id, step, "body"),
            )
            epics = [updated if row.id == epic.id else row for row in epics]
        elif op == "plan":
            store.create_plan(
                sprint_id=None,
                epic_id=epic.id,
                name=f"plan-{step}",
                idea="fuzz",
                idempotency_key=deterministic_idempotency_key("multi-fuzz", epic.id, step, "plan"),
            )
        elif op == "list":
            assert {row.id for row in epics}.issubset({row.id for row in store.list_epics(limit=20)})
        else:
            assert {row.id for row in store.search_epics(query="Fuzz", limit=20)} == {row.id for row in epics}

    for epic in epics:
        loaded = store.load_epic(epic.id)
        if loaded.home_backend == "file":
            assert file_store.load_epic(epic.id) is not None
            assert db_store.load_epic(epic.id) is None
        else:
            assert db_store.load_epic(epic.id) is not None
            assert file_store.load_epic(epic.id) is None


def test_resume_migration_terminal_noop(tmp_path: Path) -> None:
    store, _, _ = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")

    run = store.migrate_epic(epic.id, to="db", ttl_seconds=60)
    resumed = store.resume_migration(run.id, ttl_seconds=60)

    assert resumed.id == run.id
    assert resumed.phase == "complete"
    assert resumed.completed_at == run.completed_at


def test_resume_migration_refuses_live_holder_conflict(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    db_store.create_migration_run(
        MigrationRun(
            id="migration-live-resume",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="copying_meta",
            holder_id="other",
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
    )

    with pytest.raises(LeaseConflict, match="still held"):
        store.resume_migration("migration-live-resume", ttl_seconds=60)


def test_resume_migration_claims_expired_run_and_retries_copying_meta(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="resume-plan",
        idea="resume",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "resume-plan"),
    )
    store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"resume\": true}\n",
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "resume-artifact"),
    )
    run = MigrationRun(
        id="migration-expired-copying-meta",
        epic_id=epic.id,
        source_backend="file",
        target_backend="db",
        phase="copying_meta",
        manifest={"entities": {"plans": [plan.id]}},
        copied_ids={"epics": [epic.id]},
        holder_id="dead-holder",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_store.create_migration_run(run)

    resumed = store.resume_migration(run.id, ttl_seconds=60)

    assert resumed.phase == "complete"
    assert resumed.holder_id == "actor"
    assert file_store.load_epic(epic.id).migrated_to == run.id
    assert db_store.load_epic(epic.id).home_backend == "db"
    assert db_store.read_plan_artifact(plan.id, "state.json") == b"{\"resume\": true}\n"


def test_file_target_plan_artifact_copy_is_absent_only(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="DB", goal="g", body="body", home_backend="db")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="db-plan",
        idea="move",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "db-plan"),
    )
    store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"source\": true}\n",
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "source-artifact"),
    )
    entities = store._migration_entities(db_store, epic.id)
    file_store = store.file
    file_store.copy_entity_if_absent(
        file_store._plan_path(plan.id, epic_id=epic.id, sprint_id=None),
        plan,
        journal_root=file_store._journal_root_for_epic(epic.id),
    )
    artifact_path = file_store._plan_artifacts_dir(plan.id) / "state.json"
    file_store._commit_write(
        artifact_path,
        b"{\"target\": true}\n",
        journal_root=file_store._journal_root_for_epic(epic.id),
    )

    store._copy_plan_artifacts_to_file(file_store, plan.id, entities["plan_artifacts"][plan.id], "migration-test")

    assert artifact_path.read_bytes() == b"{\"target\": true}\n"


def test_resume_migration_reenters_copying_blobs_with_copied_ids(tmp_path: Path) -> None:
    store, file_store, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="resume-copying-blobs",
        idea="resume",
        idempotency_key=deterministic_idempotency_key("multi", epic.id, "resume-copying-blobs"),
    )
    store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"copied\": true}\n",
        idempotency_key=deterministic_idempotency_key("multi", plan.id, "copied-artifact"),
    )
    entities = store._migration_entities(file_store, epic.id)
    copied_ids = store._copy_metadata(db_store, entities, "db", "migration-copying-blobs")
    db_store.create_migration_run(
        MigrationRun(
            id="migration-copying-blobs",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="copying_blobs",
            manifest={"entities": {"plan_artifacts_by_plan": {plan.id: ["state.json"]}}},
            copied_ids=copied_ids,
            holder_id="dead-holder",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    resumed = store.resume_migration("migration-copying-blobs", ttl_seconds=60)

    assert resumed.phase == "complete"
    assert resumed.copied_ids["plan_artifacts_by_plan"] == {plan.id: ["state.json"]}
    assert db_store.read_plan_artifact(plan.id, "state.json") == b"{\"copied\": true}\n"


def test_incomplete_migration_warning_does_not_auto_resume(tmp_path: Path) -> None:
    store, _, db_store = _multi(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    db_store.create_migration_run(
        MigrationRun(
            id="migration-warning",
            epic_id=epic.id,
            source_backend="file",
            target_backend="db",
            phase="verifying",
            holder_id="other",
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
    )

    messages = store.incomplete_migration_warnings()

    assert messages == [
        f"Migration migration-warning for epic {epic.id} is incomplete at phase verifying; resume explicitly with migrate --resume migration-warning."
    ]
    assert db_store.load_migration_run("migration-warning").phase == "verifying"
    with pytest.warns(RuntimeWarning, match="migrate --resume migration-warning"):
        assert store.warn_incomplete_migrations() == messages
