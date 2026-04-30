from __future__ import annotations

import sqlite3

from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext
from agent_kit.tools.communication import send_message, set_activity


class FakePushTransport:
    def __init__(self) -> None:
        self.posts = []

    def post_message(self, channel_id, content, *, files=None):
        self.posts.append({"channel_id": channel_id, "content": content, "files": files})
        return {"id": "discord_123", "ok": True}


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


def test_send_message_invocation_mode_uses_synthetic_discord_id() -> None:
    store, _conn, turn = _store_with_turn()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"epic_id": "epic_1"},
    )

    value = send_message(context, "hello")

    assert value == f"inv_{turn['id']}_1"
    assert context.external_queue is None
    assert store.load_message(
        next(
            row["id"]
            for row in store._conn.execute("SELECT id FROM messages")
        )
    )["discord_message_id"] == value


def test_send_message_resident_mode_queues_post_and_updates_message() -> None:
    store, conn, turn = _store_with_turn()
    transport = FakePushTransport()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"epic_id": "epic_1", "channel_id": "channel_1"},
        transport=transport,
    )

    message_id = send_message(context, "hello resident")

    row = store.load_message(message_id)
    assert row["discord_message_id"] is None
    assert context.external_queue is not None
    assert len(context.external_queue) == 1
    spec, callback = context.external_queue[0]
    assert spec.provider == "discord"
    assert spec.endpoint == "POST /channels/channel_1/messages"
    assert spec.request_summary == {
        "content_preview": "hello resident",
        "channel_id": "channel_1",
        "message_row_id": message_id,
    }

    provider_id, response_summary = callback()

    assert provider_id == "discord_123"
    assert response_summary["ok"] is True
    assert transport.posts == [
        {"channel_id": "channel_1", "content": "hello resident", "files": None}
    ]
    assert store.load_message(message_id)["discord_message_id"] == "discord_123"
    assert conn.execute(
        "SELECT discord_message_id FROM messages WHERE id = ?",
        (message_id,),
    ).fetchone()["discord_message_id"] == "discord_123"


def test_set_activity_updates_current_activity() -> None:
    store, conn, turn = _store_with_turn()
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    assert set_activity(context, "drafting") == {"description": "drafting"}

    assert conn.execute(
        "SELECT current_activity FROM bot_turns WHERE id = ?",
        (turn["id"],),
    ).fetchone()["current_activity"] == "drafting"
