from __future__ import annotations

import sqlite3

from agent_kit.tool_kit import ToolContext, registry
from tests.test_tool_kit_external_queue import _store_with_turn


class InspectingTransport:
    def __init__(self, store, conn: sqlite3.Connection) -> None:
        self.store = store
        self.conn = conn
        self.depths: list[int] = []
        self.message_ids_before_update: list[str | None] = []

    def post_message(self, channel_id, content, *, files=None):
        del channel_id, files
        self.depths.append(self.store._transaction_depth)
        row = self.conn.execute(
            "SELECT discord_message_id FROM messages WHERE content = ?",
            (content,),
        ).fetchone()
        self.message_ids_before_update.append(row["discord_message_id"])
        return {"discord_message_id": "discord_after_commit", "content": content}


def test_resident_send_message_posts_after_commit_updates_message_and_ledger() -> None:
    store, conn, turn = _store_with_turn()
    transport = InspectingTransport(store, conn)
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"epic_id": "epic_1", "channel_id": "channel_1"},
        transport=transport,
    )

    invocation = registry.invoke("send_message", context, {"content": "hello resident"})

    assert invocation.result["value"].startswith("msg_")
    assert transport.depths == [0]
    assert transport.message_ids_before_update == [None]
    message = conn.execute("SELECT * FROM messages WHERE content = 'hello resident'").fetchone()
    assert message["discord_message_id"] == "discord_after_commit"
    request = conn.execute("SELECT * FROM external_requests").fetchone()
    assert request["provider"] == "discord"
    assert request["status"] == "confirmed"
    assert request["provider_request_id"] == "discord_after_commit"
