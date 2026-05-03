from __future__ import annotations

import asyncio
import json

from tests.test_discord_transport import Attachment, FakeBlob, FakeGroq, Message, _store, _transport


def test_voice_pipeline_persists_first_then_transcribes_and_confirms_ledgers() -> None:
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

    asyncio.run(transport.on_message(Message(id=501, content="", attachments=[attachment])))

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 2,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["was_voice_message"] == 1
    assert message["content"] == "transcribed voice"
    assert message["audio_storage_url"] == "stored/1.ogg"
    assert json.loads(message["transcription_metadata"])["model"] == "whisper-large-v3"
    epic = conn.execute("SELECT * FROM epics WHERE id = ?", (message["epic_id"],)).fetchone()
    assert epic["title"] == "Discord DM 42"
    assert blob.puts == [
        {
            "epic_id": message["epic_id"],
            "content": b"attachment bytes",
            "mime_type": "audio/ogg",
        }
    ]
    assert groq.calls[0]["model"] == "whisper-large-v3"
    requests = conn.execute(
        "SELECT provider, status, request_body FROM external_requests ORDER BY provider"
    ).fetchall()
    assert [(row["provider"], row["status"]) for row in requests] == [
        ("groq", "confirmed"),
        ("supabase_storage", "confirmed"),
    ]
    storage_body = json.loads(
        next(row["request_body"] for row in requests if row["provider"] == "supabase_storage")
    )
    assert storage_body["discord_attachment_url"] == "https://cdn.example/voice.ogg"
    assert "deterministic_path" in storage_body
