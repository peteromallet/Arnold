from __future__ import annotations

import asyncio
import json

from tests.test_discord_transport import (
    Attachment,
    FakeBlob,
    FakeGroq,
    Message,
    _store,
    _transport,
)


class FailingBlob(FakeBlob):
    def put(self, epic_id, content, mime_type):
        raise RuntimeError("upload failed")


def test_voice_ingestion_confirms_storage_and_groq_rows() -> None:
    store, conn = _store()
    transport = _transport(store, conn, blob=FakeBlob(), groq=FakeGroq())
    attachment = Attachment(
        id="voice_1",
        url="https://cdn.example/voice.ogg",
        filename="voice.ogg",
        content_type="audio/ogg",
        voice=True,
    )

    asyncio.run(transport.on_message(Message(id=600, content="", attachments=[attachment])))

    rows = conn.execute(
        "SELECT provider, status FROM external_requests ORDER BY provider"
    ).fetchall()
    assert [(row["provider"], row["status"]) for row in rows] == [
        ("groq", "confirmed"),
        ("supabase_storage", "confirmed"),
    ]


def test_image_ingestion_confirms_storage_row() -> None:
    store, conn = _store()
    transport = _transport(store, conn, blob=FakeBlob())
    attachment = Attachment(
        id="image_1",
        url="https://cdn.example/image.png",
        filename="image.png",
        content_type="image/png",
    )

    asyncio.run(transport.on_message(Message(id=601, content="", attachments=[attachment])))

    row = conn.execute("SELECT provider, status FROM external_requests").fetchone()
    assert (row["provider"], row["status"]) == ("supabase_storage", "confirmed")


def test_ingestion_failure_marks_ledger_failed_but_keeps_message() -> None:
    store, conn = _store()
    transport = _transport(store, conn, blob=FailingBlob())
    attachment = Attachment(
        id="image_1",
        url="https://cdn.example/image.png",
        filename="image.png",
        content_type="image/png",
    )

    try:
        asyncio.run(transport.on_message(Message(id=602, content="", attachments=[attachment])))
    except RuntimeError:
        pass

    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    row = conn.execute("SELECT status, error_details FROM external_requests").fetchone()
    assert row["status"] == "failed"
    assert "upload failed" in json.loads(row["error_details"])["message"]
