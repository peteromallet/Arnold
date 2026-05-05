from __future__ import annotations

from pathlib import Path

from megaplan.store import FileStore, LocalDirBlobStore, deterministic_idempotency_key
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
