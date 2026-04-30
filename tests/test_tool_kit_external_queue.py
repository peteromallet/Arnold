from __future__ import annotations

import sqlite3

import pytest

from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ExternalSpec, ToolContext, ToolRegistry


def _store_with_turn():
    conn = sqlite3.connect(":memory:")
    store = SQLiteStore(conn)
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    return store, conn, turn


def test_external_queue_records_pending_in_transaction_and_runs_after_commit() -> None:
    store, conn, turn = _store_with_turn()
    registry = ToolRegistry()
    observations = {}

    def queued_tool(context):
        context.external_queue.append(
            (
                ExternalSpec(
                    provider="discord",
                    endpoint="POST /channels/channel_1/messages",
                    request_summary={"content_preview": "hello"},
                    request_body={"content": "hello"},
                ),
                external_call,
            )
        )
        return {"ok": True}

    def external_call():
        observations["transaction_depth"] = store._transaction_depth
        row = conn.execute(
            "SELECT status, request_body FROM external_requests"
        ).fetchone()
        observations["pending_status"] = row["status"]
        observations["request_body"] = row["request_body"]
        return "discord_1", {"ok": True}

    registry.register("queued_tool", queued_tool, {"type": "object"})
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    invocation = registry.invoke("queued_tool", context, {})

    assert invocation.result == {"ok": True}
    assert observations["transaction_depth"] == 0
    assert observations["pending_status"] == "pending"
    assert observations["request_body"] == '{"content":"hello"}'
    row = conn.execute("SELECT * FROM external_requests").fetchone()
    assert row["status"] == "confirmed"
    assert row["provider_request_id"] == "discord_1"
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1
    assert len(context.events) == 1


def test_external_queue_failure_marks_request_failed_and_reraises() -> None:
    store, conn, turn = _store_with_turn()
    registry = ToolRegistry()

    def queued_tool(context):
        context.external_queue.append(
            (
                ExternalSpec(
                    provider="discord",
                    endpoint="POST /channels/channel_1/messages",
                    request_summary={"content_preview": "hello"},
                ),
                external_call,
            )
        )
        return {"ok": True}

    def external_call():
        assert store._transaction_depth == 0
        raise RuntimeError("network down")

    registry.register("queued_tool", queued_tool, {"type": "object"})
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    with pytest.raises(RuntimeError, match="network down"):
        registry.invoke("queued_tool", context, {})

    row = conn.execute("SELECT * FROM external_requests").fetchone()
    assert row["status"] == "failed"
    assert '"network down"' in row["error_details"]
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1
    assert context.events == []


def test_tool_body_still_rolls_back_before_external_queue_runs() -> None:
    store, conn, turn = _store_with_turn()
    registry = ToolRegistry()
    calls = []

    def failing_tool(context):
        context.store.create_message(
            epic_id="epic_1",
            direction="outbound",
            content="bad",
            bot_turn_id=context.turn_id,
        )
        context.external_queue.append(
            (
                ExternalSpec(
                    provider="discord",
                    endpoint="POST /channels/channel_1/messages",
                    request_summary={"content_preview": "bad"},
                ),
                lambda: calls.append("called") or ("discord_1", {}),
            )
        )
        raise RuntimeError("fail")

    registry.register("failing_tool", failing_tool, {"type": "object"})
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    with pytest.raises(RuntimeError, match="fail"):
        registry.invoke("failing_tool", context, {})

    assert calls == []
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM external_requests").fetchone()[0] == 0
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM messages WHERE content = 'bad'"
        ).fetchone()[0]
        == 0
    )
