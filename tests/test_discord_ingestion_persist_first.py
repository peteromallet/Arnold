from __future__ import annotations

import asyncio

from tests.test_discord_transport import (
    Attachment,
    FakeBlob,
    FakeGroq,
    Message,
    _store,
    _transport,
)


def test_voice_ingestion_persists_message_and_ledgers_before_storage_io() -> None:
    store, conn = _store()
    groq = FakeGroq()
    transport = _transport(store, conn, blob=FakeBlob(), groq=groq)
    attachment = Attachment(
        id="voice_1",
        url="https://cdn.example/voice.ogg",
        filename="voice.ogg",
        content_type="audio/ogg",
        voice=True,
    )

    asyncio.run(transport.on_message(Message(id=500, content="", attachments=[attachment])))

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 2,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["was_voice_message"] == 1
    assert message["content"] == "transcribed voice"
    assert message["audio_storage_url"] == "stored/1.ogg"


def test_image_ingestion_persists_message_and_ledger_before_image_row_io() -> None:
    store, conn = _store()
    transport = _transport(store, conn, blob=FakeBlob())
    attachment = Attachment(
        id="image_1",
        url="https://cdn.example/image.png",
        filename="image.png",
        content_type="image/png",
    )

    asyncio.run(
        transport.on_message(Message(id=501, content="caption", attachments=[attachment]))
    )

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 1,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["has_image_attachment"] == 1
    image = conn.execute("SELECT * FROM images").fetchone()
    assert image["source"] == "user_uploaded"
    assert image["reference_key"] == "img_user_upload_1"
