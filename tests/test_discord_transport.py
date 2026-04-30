from __future__ import annotations

import asyncio
from dataclasses import dataclass
import sqlite3

from agent_kit.ledger import Ledger, derive_idempotency_key
from agent_kit.ports import BlobRef
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.transport.discord import DiscordTransport


@dataclass
class Author:
    id: int
    bot: bool = False


@dataclass
class Channel:
    id: int = 100


class Attachment:
    def __init__(
        self,
        *,
        id: str = "att_1",
        url: str = "https://cdn.example/file",
        filename: str = "file.png",
        content_type: str = "image/png",
        voice: bool = False,
    ) -> None:
        self.id = id
        self.url = url
        self.filename = filename
        self.content_type = content_type
        self._voice = voice

    def is_voice_message(self) -> bool:
        return self._voice


class Message:
    def __init__(
        self,
        *,
        id: int = 123,
        content: str = "hello",
        author_id: int = 42,
        guild=None,
        attachments=None,
        epic_id: str = "epic_1",
    ) -> None:
        self.id = id
        self.content = content
        self.author = Author(author_id)
        self.guild = guild
        self.attachments = list(attachments or [])
        self.channel = Channel()
        self.epic_id = epic_id


class FakeBlob:
    def __init__(self) -> None:
        self.puts = []

    def put(self, epic_id: str, content: bytes, mime_type: str) -> BlobRef:
        self.puts.append({"epic_id": epic_id, "content": content, "mime_type": mime_type})
        suffix = "ogg" if mime_type.startswith("audio/") else "png"
        return BlobRef(epic_id=epic_id, key=f"stored/{len(self.puts)}.{suffix}", mime_type=mime_type)

    def get(self, ref: BlobRef) -> bytes:
        return b""

    def exists(self, ref: BlobRef) -> bool:
        return True


class FakeGroq:
    def __init__(self) -> None:
        self.audio = self
        self.transcriptions = self
        self.calls = []

    def create(self, *, file, model):
        self.calls.append({"file": file, "model": model})
        return {"text": "transcribed voice"}


class InspectingDiscordTransport(DiscordTransport):
    def __init__(self, *args, conn: sqlite3.Connection, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.conn = conn
        self.downloads = []

    def download_attachment(self, url: str) -> bytes:
        self.downloads.append(url)
        self.rows_seen_before_download = {
            "messages": self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "pending": self.conn.execute(
                "SELECT COUNT(*) FROM external_requests WHERE status = 'pending'"
            ).fetchone()[0],
            "images": self.conn.execute("SELECT COUNT(*) FROM images").fetchone()[0],
        }
        return b"attachment bytes"


def _store():
    conn = sqlite3.connect(":memory:")
    store = SQLiteStore(conn)
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()
    return store, conn


def _transport(store, conn, blob=None, groq=None, whitelist=None):
    return InspectingDiscordTransport(
        store=store,
        blob=blob or FakeBlob(),
        ledger=Ledger(store),
        groq_client=groq or FakeGroq(),
        whitelist=whitelist or {"42"},
        token="token",
        conn=conn,
    )


def test_non_dm_is_ignored_and_non_whitelisted_dm_is_logged() -> None:
    store, conn = _store()
    transport = _transport(store, conn, whitelist={"7"})

    asyncio.run(transport.on_message(Message(guild=object())))
    asyncio.run(transport.on_message(Message(author_id=42)))

    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    log = conn.execute("SELECT * FROM system_logs").fetchone()
    assert log["level"] == "info"
    assert log["category"] == "application"
    assert log["event_type"] == "whitelist_rejected"


def test_text_dm_persists_message_and_invokes_handler() -> None:
    store, conn = _store()
    transport = _transport(store, conn)
    seen = []
    transport.start = lambda handler: setattr(transport, "_handler", handler)
    transport.start(seen.append)

    asyncio.run(transport.on_message(Message(id=200, content="hello text")))

    row = conn.execute("SELECT * FROM messages").fetchone()
    assert row["content"] == "hello text"
    assert row["discord_message_id"] == "200"
    assert seen[0]["message_id"] == row["id"]
    assert conn.execute("SELECT COUNT(*) FROM external_requests").fetchone()[0] == 0


def test_voice_message_persists_message_and_ledgers_before_external_io() -> None:
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

    asyncio.run(transport.on_message(Message(id=300, content="", attachments=[attachment])))

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 2,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["was_voice_message"] == 1
    assert message["content"] == "transcribed voice"
    assert message["audio_storage_url"] == "stored/1.ogg"
    requests = conn.execute(
        "SELECT provider, status, request_body FROM external_requests ORDER BY provider"
    ).fetchall()
    assert [(row["provider"], row["status"]) for row in requests] == [
        ("groq", "confirmed"),
        ("supabase_storage", "confirmed"),
    ]
    storage_body = next(row["request_body"] for row in requests if row["provider"] == "supabase_storage")
    assert "discord_attachment_url" in storage_body
    assert "deterministic_path" in storage_body
    assert groq.calls[0]["model"] == "whisper-large-v3"


def test_image_message_persists_message_and_ledger_before_upload_then_creates_image() -> None:
    store, conn = _store()
    blob = FakeBlob()
    transport = _transport(store, conn, blob=blob)
    attachment = Attachment(
        id="image_1",
        url="https://cdn.example/image.png",
        filename="image.png",
        content_type="image/png",
    )

    asyncio.run(transport.on_message(Message(id=400, content="caption", attachments=[attachment])))

    assert transport.rows_seen_before_download == {
        "messages": 1,
        "pending": 1,
        "images": 0,
    }
    message = conn.execute("SELECT * FROM messages").fetchone()
    assert message["has_image_attachment"] == 1
    assert message["content"] == "caption"
    image = conn.execute("SELECT * FROM images").fetchone()
    assert image["source"] == "user_uploaded"
    assert image["reference_key"] == "img_user_upload_1"
    assert image["discord_attachment_id"] == "image_1"
    request = conn.execute("SELECT * FROM external_requests").fetchone()
    assert request["status"] == "confirmed"
    assert "discord_attachment_url" in request["request_body"]
    assert "deterministic_path" in request["request_body"]


def test_ingest_idempotency_key_branch_is_stable() -> None:
    first = derive_idempotency_key(
        provider="supabase_storage",
        endpoint="PUT images/epic_1/123.png",
        request_summary={"ignored": True},
        turn_id=None,
        ingest_message_id="discord_123",
    )
    second = derive_idempotency_key(
        provider="supabase_storage",
        endpoint="PUT images/epic_1/123.png",
        request_summary={"ignored": False},
        turn_id=None,
        ingest_message_id="discord_123",
    )

    assert first == second
    assert len(first) == 16
