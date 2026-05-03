from __future__ import annotations

import asyncio
import json

from tests.test_discord_transport import Attachment, FakeBlob, Message, _store, _transport


def test_image_attachment_pipeline_persists_first_then_creates_image_row() -> None:
    store, conn = _store()
    blob = FakeBlob()
    transport = _transport(store, conn, blob=blob)
    attachment = Attachment(
        id="image_1",
        url="https://cdn.example/image.png",
        filename="image.png",
        content_type="image/png",
    )

    asyncio.run(
        transport.on_message(
            Message(id=601, content="image caption", attachments=[attachment])
        )
    )

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 1,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["has_image_attachment"] == 1
    assert message["content"] == "image caption"
    epic = conn.execute("SELECT * FROM epics WHERE id = ?", (message["epic_id"],)).fetchone()
    assert epic["title"] == "Discord DM 42"
    image = conn.execute("SELECT * FROM images").fetchone()
    assert image["source"] == "user_uploaded"
    assert image["reference_key"] == "img_user_upload_1"
    assert image["storage_url"] == "stored/1.png"
    assert image["discord_attachment_id"] == "image_1"
    assert blob.puts == [
        {
            "epic_id": message["epic_id"],
            "content": b"attachment bytes",
            "mime_type": "image/png",
        }
    ]
    request = conn.execute("SELECT status, request_body FROM external_requests").fetchone()
    assert request["status"] == "confirmed"
    request_body = json.loads(request["request_body"])
    assert request_body["discord_attachment_url"] == "https://cdn.example/image.png"
    assert "deterministic_path" in request_body
