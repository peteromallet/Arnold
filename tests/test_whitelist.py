from __future__ import annotations

import asyncio

from tests.test_discord_transport import Message, _store, _transport


def test_non_whitelisted_dm_is_logged_without_persisting_message() -> None:
    store, conn = _store()
    transport = _transport(store, conn, whitelist={"7"})

    asyncio.run(transport.on_message(Message(author_id=42, content="blocked")))

    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM bot_turns").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM external_requests").fetchone()[0] == 0
    log = conn.execute("SELECT level, category, event_type FROM system_logs").fetchone()
    assert dict(log) == {
        "level": "info",
        "category": "application",
        "event_type": "whitelist_rejected",
    }
