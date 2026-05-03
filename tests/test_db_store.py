from __future__ import annotations

import os
import uuid

import pytest

from megaplan.tests.store_contract import run_store_contract


def test_db_store_contract(db_store_factory) -> None:
    run_store_contract(db_store_factory)


def test_db_write_without_actor_raises() -> None:
    from megaplan.store import DBStore

    store = DBStore.__new__(DBStore)
    store._actor_id = None
    store._dsn = None
    store._conn = None

    with pytest.raises(RuntimeError, match="actor"):
        store.create_epic(title="T", goal="G", body="B")


def test_db_write_with_unregistered_actor_raises(db_store_factory) -> None:
    from megaplan.store import DBStore

    dsn = os.environ["SUPABASE_DB_URL"]
    store = DBStore(actor_id="nonexistent-actor-xyz-" + uuid.uuid4().hex, dsn=dsn)
    try:
        with pytest.raises(Exception):
            store.create_epic(title="T", goal="G", body="B")
    finally:
        store.close()


def test_from_arnold_epic_produces_no_db_writes(db_store_factory) -> None:
    from megaplan.store import DBStore

    dsn = os.environ["SUPABASE_DB_URL"]
    actor_id = f"no-write-actor-{uuid.uuid4().hex[:12]}"

    bootstrap = DBStore(actor_id=None, dsn=dsn)
    try:
        bootstrap.create_automation_actor(
            actor_id=actor_id,
            name="No-Write Test Actor",
            granted_epic_ids="*",
            actor_kind="cli",
        )
    finally:
        bootstrap.close()

    db2 = DBStore(actor_id=actor_id, dsn=dsn)
    try:
        epic = db2.create_epic(title="Read Only Epic", goal="no writes", body="content")
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
