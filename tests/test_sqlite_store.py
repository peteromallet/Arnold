from __future__ import annotations

import sqlite3

import pytest

from agent_kit.store.sqlite import SQLiteStore
from tests.store_contract import run_store_contract
from tests.store_contract_v1b import run_store_contract_v1b


@pytest.fixture
def store_factory(tmp_path):
    def factory():
        path = tmp_path / "arnold.db"
        store = SQLiteStore(path)
        return store, store._conn

    return factory


def test_sqlite_store_contract(store_factory) -> None:
    run_store_contract(store_factory)


def test_sqlite_store_contract_v1b(store_factory) -> None:
    run_store_contract_v1b(store_factory)


def test_external_requests_lifecycle_and_unique_idempotency(store_factory) -> None:
    store, conn = store_factory()
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    request = store.insert_pending(
        idempotency_key="idem_1",
        provider="anthropic",
        endpoint="POST /v1/messages",
        request_summary={"shape": "small"},
        turn_id=turn["id"],
    )
    assert request["status"] == "pending"
    confirmed = store.mark_confirmed(
        request["id"],
        provider_request_id="req_1",
        provider_response_summary={"ok": True},
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["completed_at"] is not None

    tool_call = store.record_tool_call(
        turn_id=turn["id"],
        tool_name="send_message",
        operation_kind="write",
        arguments={},
        result={},
        duration_ms=1,
    )
    failed_request = store.insert_pending(
        idempotency_key="idem_2",
        provider="discord",
        endpoint="POST /chat.send",
        request_summary={"content": "hi"},
        turn_id=turn["id"],
        tool_call_id=tool_call["id"],
    )
    failed = store.mark_failed(failed_request["id"], error_details={"code": "bad"})
    assert failed["status"] == "failed"
    assert failed["error_details"]["code"] == "bad"
    assert failed["completed_at"] is not None

    with pytest.raises(sqlite3.IntegrityError):
        store.insert_pending(
            idempotency_key="idem_2",
            provider="discord",
            endpoint="POST /chat.send",
            request_summary={},
        )


def test_sqlite_schema_columns_and_indexes(store_factory) -> None:
    _store, conn = store_factory()
    external_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(external_requests)")
    }
    assert {
        "id",
        "idempotency_key",
        "provider",
        "endpoint",
        "tool_call_id",
        "turn_id",
        "request_summary",
        "status",
        "provider_request_id",
        "provider_response_summary",
        "attempt_count",
        "first_attempted_at",
        "last_attempted_at",
        "completed_at",
        "error_details",
    } <= external_cols

    message_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    assert {
        "has_code_attachment",
        "has_image_attachment",
        "bot_turn_id",
        "discord_message_id",
    } <= message_cols
    turn_cols = {row[1] for row in conn.execute("PRAGMA table_info(bot_turns)")}
    assert {"status_message_id", "current_activity"} <= turn_cols

    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    assert {
        "idx_external_requests_idempotency_key",
        "idx_external_requests_provider_status_last_attempted",
        "idx_external_requests_status_last_attempted",
        "idx_external_requests_turn_id",
        "idx_external_requests_tool_call_id",
        "idx_messages_epic_sent_at",
        "idx_tool_calls_turn_id",
    } <= indexes
