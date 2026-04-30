from __future__ import annotations

import asyncio
import sqlite3

import pytest

from tests.test_discord_transport import Attachment, FakeBlob, FakeGroq, Message, _store, _transport


def test_duplicate_inbound_message_raises_and_does_not_double_upload_or_transcribe() -> None:
    store, conn = _store()
    blob = FakeBlob()
    groq = FakeGroq()
    transport = _transport(store, conn, blob=blob, groq=groq)
    attachment = Attachment(
        id="voice_1",
        url="https://cdn.example/voice.ogg",
        filename="voice.ogg",
        content_type="audio/ogg",
        voice=True,
    )
    message = Message(id=701, content="", attachments=[attachment])

    asyncio.run(transport.on_message(message))
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(transport.on_message(message))

    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM external_requests").fetchone()[0] == 2
    assert len(blob.puts) == 1
    assert len(groq.calls) == 1
