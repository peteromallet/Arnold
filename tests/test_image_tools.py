from __future__ import annotations

import base64
import sqlite3

import pytest

from agent_kit.ports import BlobRef
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.images  # noqa: F401


class FakeBlob:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.refs: list[BlobRef] = []

    def get(self, ref: BlobRef) -> bytes:
        self.refs.append(ref)
        return self.payload


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
    assert context.events == [invocation.event]
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
    )

    invocation = registry.invoke("send_image", context, {"image_id": image["id"]})

    message = store.load_message(invocation.result["message_row_id"])
    assert message["discord_message_id"] == "discord_image_1"
    assert transport.posts == [
        {
            "channel_id": "channel_1",
            "content": "from row",
            "files": [
                {
                    "image_id": image["id"],
                    "storage_url": "images/epic_1/upload.png",
                    "media_type": "image/png",
                    "reference_key": image["reference_key"],
                }
            ],
        }
    ]
    external = conn.execute("SELECT * FROM external_requests").fetchone()
    assert external["status"] == "confirmed"
    assert external["provider_request_id"] == "discord_image_1"
