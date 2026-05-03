from __future__ import annotations

import base64
import json
import sqlite3
from types import SimpleNamespace

import pytest

from agent_kit.attachments import UnsupportedMediaTypeError, normalize_image_attachment
from agent_kit.ports import BlobRef, FileUpload, OpenAIImageResult
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.images  # noqa: F401


class FakeBlob:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.refs: list[BlobRef] = []
        self.puts = []

    def get(self, ref: BlobRef) -> bytes:
        self.refs.append(ref)
        return self.payload

    def put(self, epic_id: str, content: bytes, mime_type: str, *, idempotency_key=None) -> BlobRef:
        self.puts.append(
            {
                "epic_id": epic_id,
                "content": content,
                "mime_type": mime_type,
                "idempotency_key": idempotency_key,
            }
        )
        return BlobRef(
            epic_id=epic_id,
            key=f"images/{epic_id}/{idempotency_key}.png",
            mime_type=mime_type,
            size_bytes=len(content),
        )

    def exists(self, ref: BlobRef) -> bool:
        return False


class FakeOpenAIOps:
    def __init__(self) -> None:
        self.image_calls = []

    def generate_image(self, *, prompt: str, quality: str, size: str, idempotency_key: str):
        self.image_calls.append(
            {
                "prompt": prompt,
                "quality": quality,
                "size": size,
                "idempotency_key": idempotency_key,
            }
        )
        return OpenAIImageResult(
            content=b"generated png",
            mime_type="image/png",
            provider_request_id="openai_img_1",
            response_summary={"ok": True},
        )


class FakePushTransport:
    def __init__(self) -> None:
        self.posts = []

    def post_message(self, channel_id, content, *, files=None):
        self.posts.append({"channel_id": channel_id, "content": content, "files": files})
        return {"id": "discord_image_1", "ok": True}


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


def test_list_view_and_update_image_tools() -> None:
    store, _conn, turn = _store_with_turn()
    image = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/source.png",
        caption="before",
        description="original",
    )
    caller_uploaded = store.create_image(
        epic_id="epic_1",
        source="caller_uploaded",
        storage_url="images/epic_1/caller.webp",
    )
    blob = FakeBlob(b"png bytes")
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=blob,
    )

    listed = registry.invoke(
        "list_images",
        context,
        {"epic_id": "epic_1", "source": "user_uploaded"},
    ).result
    listed_caller_uploaded = registry.invoke(
        "list_images",
        context,
        {"epic_id": "epic_1", "source": "caller_uploaded"},
    ).result
    viewed = registry.invoke(
        "view_image",
        context,
        {"image_id": image["id"], "mode": "visual"},
    ).result
    updated = registry.invoke(
        "update_image_metadata",
        context,
        {
            "image_id": image["id"],
            "caption": "after",
            "description": "annotated",
            "reference_key": "img_after",
        },
    ).result

    assert listed["images"][0]["id"] == image["id"]
    assert listed_caller_uploaded["images"][0]["id"] == caller_uploaded["id"]
    assert viewed["media_type"] == "image/png"
    assert viewed["image_bytes_b64"] == base64.b64encode(b"png bytes").decode("ascii")
    assert blob.refs == [
        BlobRef(
            epic_id="epic_1",
            key="images/epic_1/source.png",
            mime_type="image/png",
        )
    ]
    assert updated["image"]["caption"] == "after"
    assert updated["image"]["description"] == "annotated"
    assert updated["image"]["reference_key"] == "img_after"


def test_update_image_metadata_rejects_bad_reference_key() -> None:
    store, _conn, turn = _store_with_turn()
    image = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/generated.png",
    )
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    with pytest.raises(ValueError, match="reference_key"):
        registry.invoke(
            "update_image_metadata",
            context,
            {"image_id": image["id"], "reference_key": "Bad-Key"},
        )


def test_send_image_invocation_mode_records_event_and_synthetic_message() -> None:
    store, conn, turn = _store_with_turn()
    image = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/generated.png",
        caption="ship it",
    )
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    invocation = registry.invoke(
        "send_image",
        context,
        {"image_id": image["id"], "caption": "caption"},
    )

    assert invocation.result["discord_message_id"] == f"inv_{turn['id']}_1"
    assert invocation.result["caption"] == "caption"
    assert [event.kind for event in context.events] == ["tool_call", "attached_image"]
    assert context.events[0] == invocation.event
    assert context.events[1].details == {
        "image_id": image["id"],
        "caption": "caption",
        "storage_url": "images/epic_1/generated.png",
        "reference_key": image["reference_key"],
        "media_type": "image/png",
    }
    row = conn.execute(
        "SELECT content, has_image_attachment FROM messages WHERE id = ?",
        (invocation.result["message_row_id"],),
    ).fetchone()
    assert row["content"] == "caption"
    assert row["has_image_attachment"] == 1


def test_send_image_resident_mode_posts_and_updates_message_after_commit() -> None:
    store, conn, turn = _store_with_turn()
    image = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/upload.png",
        caption="from row",
    )
    transport = FakePushTransport()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"channel_id": "channel_1"},
        transport=transport,
        blob=FakeBlob(b"stored png bytes"),
    )

    invocation = registry.invoke("send_image", context, {"image_id": image["id"]})

    message = store.load_message(invocation.result["message_row_id"])
    assert [event.kind for event in context.events] == ["tool_call"]
    assert message["discord_message_id"] == "discord_image_1"
    assert len(transport.posts) == 1
    assert transport.posts[0]["channel_id"] == "channel_1"
    assert transport.posts[0]["content"] == "from row"
    assert transport.posts[0]["files"] == [
        FileUpload(
            filename="upload.png",
            content=b"stored png bytes",
            mime_type="image/png",
            metadata={
                "image_id": image["id"],
                "storage_url": "images/epic_1/upload.png",
                "media_type": "image/png",
                "reference_key": image["reference_key"],
                "filename": "upload.png",
            },
        )
    ]
    external = conn.execute("SELECT * FROM external_requests").fetchone()
    assert external["status"] == "confirmed"
    assert external["provider_request_id"] == "discord_image_1"
    request_summary = json.loads(external["request_summary"])
    assert request_summary["files"] == [
        {
            "image_id": image["id"],
            "storage_url": "images/epic_1/upload.png",
            "media_type": "image/png",
            "reference_key": image["reference_key"],
            "filename": "upload.png",
        }
    ]
    assert json.dumps(request_summary)
    assert json.loads(external["request_body"]) == {
        "content": "from row",
        "files": [
            {
                "image_id": image["id"],
                "storage_url": "images/epic_1/upload.png",
                "media_type": "image/png",
                "reference_key": image["reference_key"],
                "filename": "upload.png",
            }
        ],
    }
    assert "stored png bytes" not in external["request_body"]
    assert "stored png bytes" not in external["request_summary"]


def test_send_image_resident_mode_requires_blob_adapter() -> None:
    store, _conn, turn = _store_with_turn()
    image = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/upload.png",
    )
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"channel_id": "channel_1"},
        transport=FakePushTransport(),
    )

    with pytest.raises(ValueError, match="requires a blob adapter"):
        registry.invoke("send_image", context, {"image_id": image["id"]})


def test_invocation_image_attachment_normalization_accepts_supported_inputs(tmp_path) -> None:
    png = b"\x89PNG\r\n\x1a\npayload"
    jpeg = b"\xff\xd8\xff\xe0payload"
    webp = b"RIFF\x10\x00\x00\x00WEBPpayload"
    path = tmp_path / "upload.png"
    path.write_bytes(png)

    from_path = normalize_image_attachment(path)
    from_bytes = normalize_image_attachment(jpeg)
    from_tuple = normalize_image_attachment((webp, "image/webp"))

    assert (from_path.mime_type, from_path.filename, from_path.content) == (
        "image/png",
        "upload.png",
        png,
    )
    assert from_bytes.mime_type == "image/jpeg"
    assert from_tuple.mime_type == "image/webp"


def test_invocation_image_attachment_normalization_rejects_unsupported_inputs(tmp_path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    mismatched = tmp_path / "bad.jpg"
    mismatched.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    with pytest.raises(UnsupportedMediaTypeError, match="unknown image bytes"):
        normalize_image_attachment(b"not an image")
    with pytest.raises(UnsupportedMediaTypeError, match="audio/ogg"):
        normalize_image_attachment((b"OggS\x00payload", "audio/ogg"))
    with pytest.raises(UnsupportedMediaTypeError, match="exceeds 25MB"):
        normalize_image_attachment(b"\x89PNG\r\n\x1a\n" + (b"x" * (25 * 1024 * 1024)))
    with pytest.raises(UnsupportedMediaTypeError, match="does not match"):
        normalize_image_attachment(mismatched)
    with pytest.raises(UnsupportedMediaTypeError, match="does not match"):
        normalize_image_attachment((b"\x89PNG\r\n\x1a\npayload", "image/webp"))
    with pytest.raises(UnsupportedMediaTypeError, match="unknown image bytes"):
        normalize_image_attachment(bad)


def test_generate_image_creates_agent_image_without_sending_to_discord() -> None:
    store, conn, turn = _store_with_turn()
    openai_ops = FakeOpenAIOps()
    blob = FakeBlob(b"")
    transport = FakePushTransport()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=blob,
        openai_ops=openai_ops,
        transport=transport,
    )

    invocation = registry.invoke(
        "generate_image",
        context,
        {
            "epic_id": "epic_1",
            "prompt": "draw the data flow diagram",
            "reference_key": "img_data_flow",
            "caption": "Data flow",
        },
    )

    image = store.load_image(invocation.result["image_id"])
    assert image["source"] == "agent_generated"
    assert image["active"] == 1
    assert image["reference_key"] == "img_data_flow"
    assert image["quality"] == "medium"
    assert image["size"] == "1536x1024"
    assert image["caption"] == "Data flow"
    assert "draw the data flow diagram" in image["prompt"]
    assert invocation.result["openai_external_request_id"]
    assert invocation.result["storage_external_request_id"]
    assert transport.posts == []
    assert openai_ops.image_calls[0]["quality"] == "medium"
    assert blob.puts[0]["content"] == b"generated png"
    external = conn.execute("SELECT provider, status FROM external_requests ORDER BY id").fetchall()
    assert sorted((row["provider"], row["status"]) for row in external) == [
        ("openai", "confirmed"),
        ("supabase_storage", "confirmed"),
    ]


def test_generate_image_honors_explicit_quality_override() -> None:
    store, _conn, turn = _store_with_turn()
    openai_ops = FakeOpenAIOps()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=FakeBlob(b""),
        openai_ops=openai_ops,
    )

    result = registry.invoke(
        "generate_image",
        context,
        {
            "epic_id": "epic_1",
            "prompt": "rough sketch of a production handoff",
            "quality": "high",
        },
    ).result

    assert result["image"]["quality"] == "high"
    assert openai_ops.image_calls[0]["quality"] == "high"


def test_generated_reference_key_skips_active_collision(monkeypatch) -> None:
    store, _conn, turn = _store_with_turn()
    store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/existing.png",
        reference_key="img_aaaaaaaa",
        active=True,
    )
    uuids = iter(
        [
            SimpleNamespace(hex="aaaaaaaa000000000000000000000000"),
            SimpleNamespace(hex="bbbbbbbb000000000000000000000000"),
        ]
    )
    monkeypatch.setattr(agent_kit.tools.images, "uuid4", lambda: next(uuids))
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=FakeBlob(b""),
        openai_ops=FakeOpenAIOps(),
    )

    result = registry.invoke(
        "generate_image",
        context,
        {"epic_id": "epic_1", "prompt": "draw the flow"},
    ).result

    assert result["reference_key"] == "img_bbbbbbbb"
    assert store.load_active_image_by_reference("epic_1", "img_aaaaaaaa")


def test_generate_image_reuses_reference_key_by_deactivating_prior_active_image() -> None:
    store, _conn, turn = _store_with_turn()
    old = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/old.png",
        reference_key="img_data_flow",
        active=True,
    )
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=FakeBlob(b""),
        openai_ops=FakeOpenAIOps(),
    )

    invocation = registry.invoke(
        "generate_image",
        context,
        {
            "epic_id": "epic_1",
            "prompt": "redo that image but cleaner",
            "reference_key": "img_data_flow",
        },
    )

    assert invocation.result["deactivated_image_ids"] == [old["id"]]
    assert store.load_image(old["id"])["active"] == 0
    active = store.load_active_image_by_reference("epic_1", "img_data_flow")
    assert active["id"] == invocation.result["image_id"]


def test_generate_image_rejects_bad_reference_key_and_selects_low_quality() -> None:
    store, _conn, turn = _store_with_turn()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=FakeBlob(b""),
        openai_ops=FakeOpenAIOps(),
    )

    with pytest.raises(ValueError, match="reference_key"):
        registry.invoke(
            "generate_image",
            context,
            {"epic_id": "epic_1", "prompt": "rough sketch", "reference_key": "Bad-Key"},
        )

    result = registry.invoke(
        "generate_image",
        context,
        {"epic_id": "epic_1", "prompt": "rough sketch of the layout"},
    ).result
    assert result["image"]["quality"] == "low"
    assert result["reference_key"].startswith("img_")
