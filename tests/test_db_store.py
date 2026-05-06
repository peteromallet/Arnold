from __future__ import annotations

import hashlib
import inspect
import os
import uuid

import pytest

from megaplan.store import ChecklistItemInput
from megaplan.tests.store_contract import run_store_contract


def test_db_store_contract(db_store_factory) -> None:
    run_store_contract(db_store_factory)


def test_db_idempotency_key_required_before_connection() -> None:
    from megaplan.store import DBStore

    store = DBStore(actor_id="actor-without-dsn")

    with pytest.raises(ValueError, match="idempotency_key is required for DBStore.create_epic"):
        store.create_epic(title="T", goal="G", body="B")


def test_db_expected_revision_updates_still_require_idempotency_key() -> None:
    from megaplan.store import DBStore

    store = DBStore(actor_id="actor-without-dsn")

    with pytest.raises(ValueError, match="idempotency_key is required for DBStore.update_body"):
        store.update_body("epic-id", "new body", expected_revision=1)


def test_db_bootstrap_actor_contract_rejects_missing_key_and_reserved_ids() -> None:
    from megaplan.store import DBStore, deterministic_idempotency_key

    bootstrap = DBStore(actor_id=None)
    with pytest.raises(ValueError, match="idempotency_key is required for DBStore.create_automation_actor"):
        bootstrap.create_automation_actor(
            actor_id="actor",
            name="Actor",
            granted_epic_ids="*",
            actor_kind="cli",
        )
    with pytest.raises(ValueError, match="automation actor ID '__bootstrap__' is reserved"):
        bootstrap.create_automation_actor(
            actor_id="__bootstrap__",
            name="Bootstrap",
            granted_epic_ids="*",
            actor_kind="cli",
            idempotency_key=deterministic_idempotency_key("db-test", "reserved-bootstrap"),
        )
    with pytest.raises(ValueError, match="actor_id '__bootstrap__' is reserved"):
        DBStore(actor_id="__bootstrap__")


def test_db_idempotency_private_sets_include_sprint3_migration_mutators() -> None:
    import megaplan.store.db as db_module

    required = {
        "create_migration_run",
        "update_migration_run",
        "heartbeat_migration",
        "claim_expired_migration",
    }

    assert required.issubset(db_module._IDEMPOTENT_MUTATORS)


def test_db_sprint5_schema_plumbing_constants_are_registered() -> None:
    import megaplan.store.db as db_module

    assert {"revert", "attach_image"}.issubset(db_module._IDEMPOTENT_MUTATORS)
    assert {
        "pre_state",
        "post_state",
        "pre_state_canonical_json",
        "post_state_canonical_json",
        "pre_state_sha256",
        "post_state_sha256",
    }.issubset(db_module._COPY_TABLE_COLUMNS["epic_events"])
    assert {
        "blob_backend",
        "blob_id",
        "blob_sha256",
        "blob_size_bytes",
        "content_type",
    }.issubset(db_module._COPY_TABLE_COLUMNS["images"])
    assert {"pre_state", "post_state"}.issubset(db_module._COPY_JSONB_COLUMNS)


def test_db_resident_store_methods_use_idempotency_and_skip_locked_claims() -> None:
    from megaplan.store import DBStore

    source_create_message = inspect.getsource(DBStore.create_message)
    source_claim_jobs = inspect.getsource(DBStore.claim_due_scheduled_jobs)
    source_recover_control = inspect.getsource(DBStore.recover_stale_control_messages)

    assert "conversation_id" in source_create_message
    assert "idempotency_key" in source_create_message
    assert "SELECT * FROM messages WHERE discord_message_id" in source_create_message
    assert "ON CONFLICT (idempotency_key)" in source_create_message
    assert "FOR UPDATE SKIP LOCKED" in source_claim_jobs
    assert "status = 'pending'" in source_claim_jobs
    assert "status = 'claimed'" in source_claim_jobs
    assert "attempt_count = attempt_count + 1" in source_claim_jobs
    assert "FOR UPDATE SKIP LOCKED" in source_recover_control
    assert "processed_at IS NULL" in source_recover_control


def test_db_resident_schema_plumbing_constants_are_registered() -> None:
    import megaplan.store.db as db_module

    assert {
        "upsert_resident_conversation",
        "update_resident_conversation",
        "create_scheduled_job",
        "update_scheduled_job",
        "claim_due_scheduled_jobs",
        "create_cloud_run",
        "update_cloud_run",
    }.issubset(db_module._IDEMPOTENT_MUTATORS)
    assert {"resident_conversations", "scheduled_jobs", "cloud_runs"}.issubset(db_module._COPY_TABLE_COLUMNS)
    assert {"conversation_id", "idempotency_key"}.issubset(db_module._COPY_TABLE_COLUMNS["messages"])
    assert {"repo_url", "repo_workspace"}.issubset(db_module._COPY_TABLE_COLUMNS["codebases"])
    assert {"payload", "metadata", "last_status"}.issubset(db_module._COPY_JSONB_COLUMNS)


def test_sprint5_supabase_migration_declares_snapshot_image_and_search_indexes() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "202605050002_sprint5_editorial_schema.sql"
    ).read_text(encoding="utf-8")

    for expected in [
        "pre_state_canonical_json",
        "post_state_canonical_json",
        "blob_sha256",
        "images_one_active_reference",
        "epics_search_tsv_gin",
        "to_tsvector",
    ]:
        assert expected in migration


def test_codebase_supabase_migration_declares_repo_url_column_and_index() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "202604300009_009_codebase_research.sql"
    ).read_text(encoding="utf-8")

    for expected in [
        "repo_url TEXT",
        "repo_workspace TEXT",
        "ADD COLUMN IF NOT EXISTS repo_url",
        "ADD COLUMN IF NOT EXISTS repo_workspace",
        "idx_codebases_repo_url",
    ]:
        assert expected in migration


def test_resident_supabase_migration_declares_runtime_tables_and_indexes() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "202605060001_resident_orchestration.sql"
    ).read_text(encoding="utf-8")

    for expected in [
        "CREATE TABLE IF NOT EXISTS resident_conversations",
        "CREATE TABLE IF NOT EXISTS scheduled_jobs",
        "CREATE TABLE IF NOT EXISTS cloud_runs",
        "ADD COLUMN IF NOT EXISTS conversation_id",
        "ADD COLUMN IF NOT EXISTS idempotency_key",
        "UNIQUE (transport, conversation_key)",
        "idx_messages_idempotency_key_unique",
        "idx_messages_conversation_idempotency_unique",
        "idx_resident_conversations_transport_key",
        "idx_scheduled_jobs_due_claim",
        "idx_scheduled_jobs_stale_claim",
        "idx_cloud_runs_idempotency_key_unique",
        "idx_cloud_runs_conversation_created",
        "idx_cloud_runs_status_checked",
        "idx_control_messages_stale_claim",
        "idx_control_messages_processor_claimed",
        "Megaplan Resident Discord Agent",
        "status = 'pending' AND claimed_at IS NULL",
        "status = 'claimed' AND claimed_at IS NOT NULL",
        "processed_at IS NULL AND claimed_at IS NOT NULL",
    ]:
        assert expected in migration


def test_db_plan_columns_include_resume_cursor() -> None:
    import megaplan.store.db as db_module

    assert "resume_cursor" in db_module._PLAN_COLUMNS
    assert "resume_cursor" in db_module._PLAN_JSONB
    assert "resume_cursor" in db_module._COPY_TABLE_COLUMNS["plans"]


def test_db_store_normalizes_checklist_positions_across_mutations(db_store_factory) -> None:
    store = db_store_factory()
    try:
        epic = store.create_epic(title="Epic", goal="Goal", body="Body", idempotency_key="db-checklist-epic")
        items = store.add_checklist_items(
            epic.id,
            [
                ChecklistItemInput(content="First", position=10),
                ChecklistItemInput(content="Second", position=10),
                ChecklistItemInput(content="Third"),
            ],
            idempotency_key="db-checklist-add",
        )
        assert [item.position for item in store.list_checklist_items(epic.id)] == [1, 2, 3]

        done = store.update_checklist_item(items[2].id, status="done", position=1, idempotency_key="db-checklist-update")
        ordered = store.list_checklist_items(epic.id)
        assert [item.id for item in ordered][0] == items[2].id
        assert [item.position for item in ordered] == [1, 2, 3]
        assert done.completed_at is not None

        store.delete_checklist_items([items[0].id], idempotency_key="db-checklist-delete")
        assert [item.position for item in store.list_checklist_items(epic.id)] == [1, 2]

        replaced = store.replace_checklist(
            epic.id,
            [
                ChecklistItemInput(content="Done", status="done", position=3, completed_at=done.completed_at),
                ChecklistItemInput(content="Open", position=3),
            ],
            idempotency_key="db-checklist-replace",
        )
        assert [item.position for item in replaced] == [1, 2]
        assert replaced[0].completed_at == done.completed_at
    finally:
        store.close()


def test_db_store_set_sprint_queue_validates_and_cleans_stale_state(db_store_factory) -> None:
    store = db_store_factory()
    try:
        epic = store.create_epic(title="Epic", goal="Goal", body="Body", idempotency_key="db-queue-epic")
        first = store.create_sprint(epic_id=epic.id, sprint_number=1, name="One", goal="One", idempotency_key="db-queue-one")
        second = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Two", idempotency_key="db-queue-two")
        third = store.create_sprint(epic_id=epic.id, sprint_number=3, name="Three", goal="Three", idempotency_key="db-queue-three")

        store.set_sprint_queue(epic.id, [first.id, second.id], {third.id: "blocked"}, idempotency_key="db-queue-set")
        cleaned = store.set_sprint_queue(epic.id, [second.id], {}, idempotency_key="db-queue-clean")
        by_id = {row.id: row for row in cleaned}
        assert by_id[second.id].status == "queued"
        assert by_id[second.id].queue_position == 1
        assert by_id[first.id].status == "proposed"
        assert by_id[first.id].queue_position is None
        assert by_id[third.id].status == "proposed"
        assert by_id[third.id].pending_reason is None

        with pytest.raises(ValueError, match="Duplicate queued"):
            store.set_sprint_queue(epic.id, [second.id, second.id], {}, idempotency_key="db-queue-dupe")
        with pytest.raises(ValueError, match="both queued and pending"):
            store.set_sprint_queue(epic.id, [second.id], {second.id: "also"}, idempotency_key="db-queue-overlap")
        with pytest.raises(FileNotFoundError, match="Unknown sprint"):
            store.set_sprint_queue(epic.id, ["missing"], {}, idempotency_key="db-queue-missing")
        with pytest.raises(ValueError, match="Pending sprints require"):
            store.set_sprint_queue(epic.id, [], {first.id: ""}, idempotency_key="db-queue-reason")
    finally:
        store.close()


def test_db_store_plan_lifecycle_fields_round_trip(db_store_factory) -> None:
    store = db_store_factory()
    try:
        plan = store.create_plan(
            sprint_id=None,
            epic_id=None,
            name="db-plan-lifecycle",
            idea="idea",
            latest_failure={"kind": "blocked", "message": "needs input"},
            resume_cursor={"phase": "execute", "batch_index": 2},
            idempotency_key="db-plan-life-create",
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
            idempotency_key="db-plan-life-update",
        )
        assert updated.current_state == "blocked"
        assert store.load_plan(plan.id).resume_cursor == {"phase": "review"}
    finally:
        store.close()


def test_db_copy_helpers_keep_plan_artifacts_off_generic_path() -> None:
    import inspect

    from megaplan.store import DBStore

    store = DBStore(actor_id="actor-without-dsn")
    with pytest.raises(ValueError, match="copy_plan_artifacts_idempotent"):
        store.copy_rows_idempotent("plan_artifacts", [])

    source = inspect.getsource(DBStore.copy_plan_artifacts_idempotent)
    assert "ON CONFLICT (plan_id, name) DO NOTHING" in source
    assert '"plan_id": plan_id' in source


def test_db_plan_artifact_binary_helpers_preserve_bytes_and_legacy_text() -> None:
    from megaplan.store import DBStore
    from megaplan.store.base import ArtifactRef
    from megaplan.store.multi import MultiStore

    binary = b"\x00\xffbinary\x80\n"
    text = "{\"ok\": true}\n"
    store = DBStore(actor_id="actor-without-dsn")

    assert store._plan_artifact_bytes({"content_bytes": memoryview(binary), "content_text": None}) == binary
    assert store._plan_artifact_bytes({"content_bytes": None, "content_text": text}) == text.encode("utf-8")

    ref = ArtifactRef(
        plan_id="plan_1",
        name="state.bin",
        kind="raw_text",
        role="execution",
        sha256=hashlib.sha256(binary).hexdigest(),
        size_bytes=len(binary),
        updated_at=None,
    )
    artifact = MultiStore.__new__(MultiStore)._artifact_model(ref, binary)
    assert artifact.content_text is None
    assert artifact.content_base64 is not None
    assert artifact.sha256 == hashlib.sha256(binary).hexdigest()

    copy_source = inspect.getsource(DBStore.copy_plan_artifacts_idempotent)
    write_source = inspect.getsource(DBStore.write_plan_artifact)
    assert "content_bytes" in copy_source
    assert "base64.b64decode" in copy_source
    assert "content_bytes" in write_source
    assert "UnicodeDecodeError" in write_source


def test_db_plan_artifact_paths_are_sorted_relative_and_path_safe() -> None:
    from megaplan.store import DBStore
    from megaplan.store.base import validate_plan_artifact_name

    store = DBStore(actor_id="actor-without-dsn")
    for unsafe in ["/absolute.bin", "../escape.bin", "nested/../escape.bin", "nested//state.bin", "nested\\state.bin", ""]:
        with pytest.raises(ValueError, match="Unsafe|non-empty"):
            validate_plan_artifact_name(unsafe)

    assert validate_plan_artifact_name("nested/state.bin") == "nested/state.bin"
    assert validate_plan_artifact_name("state.json") == "state.json"

    write_source = inspect.getsource(DBStore.write_plan_artifact)
    read_source = inspect.getsource(DBStore.read_plan_artifact)
    stat_source = inspect.getsource(DBStore.stat_plan_artifact)
    list_source = inspect.getsource(DBStore.list_plan_artifacts)
    copy_source = inspect.getsource(DBStore.copy_plan_artifacts_idempotent)

    assert "validate_plan_artifact_name(name)" in write_source
    assert "validate_plan_artifact_name(name)" in read_source
    assert "validate_plan_artifact_name(name)" in stat_source
    assert "ORDER BY name" in list_source
    assert "validate_plan_artifact_name(data[\"name\"])" in copy_source
    assert store._plan_artifact_bytes({"content_text": "legacy"}) == b"legacy"


def test_sprint7_supabase_migration_declares_plan_artifact_binary_column() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "202605050003_plan_artifact_binary_content.sql"
    ).read_text(encoding="utf-8")

    assert "content_bytes bytea" in migration
    assert "IF NOT EXISTS" in migration


def test_db_write_without_actor_raises() -> None:
    from megaplan.store import DBStore, deterministic_idempotency_key

    store = DBStore.__new__(DBStore)
    store._actor_id = None
    store._dsn = None
    store._conn = None

    with pytest.raises(RuntimeError, match="actor"):
        store.create_epic(title="T", goal="G", body="B", idempotency_key=deterministic_idempotency_key("db-test", "no-actor"))


def test_db_write_with_unregistered_actor_raises(db_store_factory) -> None:
    from megaplan.store import DBStore, deterministic_idempotency_key

    dsn = os.environ["SUPABASE_DB_URL"]
    store = DBStore(actor_id="nonexistent-actor-xyz-" + uuid.uuid4().hex, dsn=dsn)
    try:
        with pytest.raises(Exception):
            store.create_epic(
                title="T",
                goal="G",
                body="B",
                idempotency_key=deterministic_idempotency_key("db-test", "unregistered", store._actor_id),
            )
    finally:
        store.close()


def test_from_arnold_epic_produces_no_db_writes(db_store_factory) -> None:
    from megaplan.store import DBStore, deterministic_idempotency_key

    dsn = os.environ["SUPABASE_DB_URL"]
    actor_id = f"no-write-actor-{uuid.uuid4().hex[:12]}"

    bootstrap = DBStore(actor_id=None, dsn=dsn)
    try:
        bootstrap.create_automation_actor(
            actor_id=actor_id,
            name="No-Write Test Actor",
            granted_epic_ids="*",
            actor_kind="cli",
            idempotency_key=deterministic_idempotency_key("db-test", actor_id, "create_actor"),
        )
    finally:
        bootstrap.close()

    db2 = DBStore(actor_id=actor_id, dsn=dsn)
    try:
        epic = db2.create_epic(
            title="Read Only Epic",
            goal="no writes",
            body="content",
            idempotency_key=deterministic_idempotency_key("db-test", actor_id, "create_epic"),
        )
        revision_before = epic.revision
    finally:
        db2.close()

    db_read = DBStore(actor_id=None, dsn=dsn)
    try:
        loaded = db_read.load_epic(epic.id)
    finally:
        db_read.close()

    assert loaded.id == epic.id
    assert loaded.revision == revision_before
