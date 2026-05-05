from __future__ import annotations

import os
import uuid

import pytest

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


def test_db_copy_helpers_keep_plan_artifacts_off_generic_path() -> None:
    import inspect

    from megaplan.store import DBStore

    store = DBStore(actor_id="actor-without-dsn")
    with pytest.raises(ValueError, match="copy_plan_artifacts_idempotent"):
        store.copy_rows_idempotent("plan_artifacts", [])

    source = inspect.getsource(DBStore.copy_plan_artifacts_idempotent)
    assert "ON CONFLICT (plan_id, name) DO NOTHING" in source
    assert '"plan_id": plan_id' in source


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
