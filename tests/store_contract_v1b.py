from __future__ import annotations

from typing import Callable

import pytest


# Additive Sprint 1b contract coverage; the Sprint 1a contract stays unchanged.
def run_store_contract_v1b(store_factory: Callable) -> None:
    store, conn = store_factory()
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()

    first = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="first",
        discord_message_id="discord_1",
    )
    second = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="second",
        discord_message_id="discord_2",
    )
    turn = store.create_turn(
        epic_id="epic_1",
        triggered_by_message_ids=[first["id"]],
    )
    outbound = store.create_message(
        epic_id="epic_1",
        direction="outbound",
        content="queued",
        bot_turn_id=turn["id"],
        synthesize_outbound_id=False,
    )
    assert outbound["discord_message_id"] is None

    assert [row["id"] for row in store.load_messages([second["id"], first["id"]])] == [
        second["id"],
        first["id"],
    ]
    updated_message = store.update_message(
        first["id"],
        content="transcribed",
        discord_message_id="discord_1_updated",
        audio_storage_url="audio/epic_1/a.ogg",
        transcription_metadata={"model": "whisper-large-v3"},
        has_image_attachment=True,
    )
    assert updated_message["content"] == "transcribed"
    assert updated_message["transcription_metadata"] == {"model": "whisper-large-v3"}
    assert updated_message["has_image_attachment"] in {1, True}

    unprocessed = store.find_unprocessed_messages(
        "epic_1",
        first["sent_at"],
        exclude_ids=[first["id"]],
    )
    assert [row["id"] for row in unprocessed] == [second["id"]]

    request = store.insert_pending(
        idempotency_key="idem_v1b",
        provider="discord",
        endpoint="POST /channels/channel_1/messages",
        request_summary={"content_preview": "hello"},
        request_body={"content": "hello"},
        turn_id=turn["id"],
    )
    _set_stale_timestamps(conn, turn["id"], request["id"])
    assert [row["id"] for row in store.find_abandoned_turns(300)] == [turn["id"]]
    pending = store.find_pending_external_requests(60)
    assert [row["id"] for row in pending] == [request["id"]]
    assert pending[0]["request_body"] == {"content": "hello"}
    orphaned = store.mark_orphaned(
        request["id"],
        error_details={"reason": "expired"},
    )
    assert orphaned["status"] == "orphaned"
    assert orphaned["error_details"] == {"reason": "expired"}

    with pytest.raises(Exception):
        store.insert_pending(
            idempotency_key="idem_v1b",
            provider="discord",
            endpoint="POST /channels/channel_1/messages",
            request_summary={},
        )

    first_image = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/a.png",
        discord_attachment_id="attachment_1",
    )
    second_image = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/b.png",
        reference_key="hero",
        active=False,
    )
    assert first_image["reference_key"] == "img_user_upload_1"
    assert store.load_image(first_image["id"])["discord_attachment_id"] == "attachment_1"
    assert [row["id"] for row in store.list_images(epic_id="epic_1")] == [
        first_image["id"]
    ]
    assert {
        row["id"] for row in store.list_images(epic_id="epic_1", active=None)
    } == {first_image["id"], second_image["id"]}
    updated_image = store.update_image(
        first_image["id"],
        caption="caption",
        description="description",
        in_body=True,
    )
    assert updated_image["caption"] == "caption"
    assert updated_image["description"] == "description"
    assert updated_image["in_body"] in {1, True}


def _set_stale_timestamps(conn, turn_id: str, request_id: str) -> None:
    conn.execute(
        "UPDATE bot_turns SET started_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00.000Z", turn_id),
    )
    conn.execute(
        "UPDATE external_requests SET last_attempted_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00.000Z", request_id),
    )
    conn.commit()
