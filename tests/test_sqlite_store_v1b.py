from __future__ import annotations

import sqlite3

from agent_kit.store.sqlite import SQLiteStore


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


def test_message_v1b_methods_and_synthesize_flag() -> None:
    store, conn = _store()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
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

    updated = store.update_message(
        first["id"],
        content="transcribed",
        audio_storage_url="audio/path.ogg",
        transcription_metadata={"model": "whisper-large-v3"},
        has_image_attachment=True,
    )
    assert updated["content"] == "transcribed"
    assert updated["transcription_metadata"] == {"model": "whisper-large-v3"}
    assert updated["has_image_attachment"] == 1

    unprocessed = store.find_unprocessed_messages(
        "epic_1",
        first["sent_at"],
        exclude_ids=[first["id"]],
    )
    assert [row["id"] for row in unprocessed] == [second["id"]]
    assert conn.execute(
        "SELECT discord_message_id FROM messages WHERE id = ?",
        (outbound["id"],),
    ).fetchone()["discord_message_id"] is None


def test_recovery_external_request_methods() -> None:
    store, conn = _store()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    stale_started_at = "2000-01-01T00:00:00.000Z"
    conn.execute(
        "UPDATE bot_turns SET started_at = ? WHERE id = ?",
        (stale_started_at, turn["id"]),
    )
    request = store.insert_pending(
        idempotency_key="idem_1",
        provider="discord",
        endpoint="POST /channels/channel_1/messages",
        request_summary={"content_preview": "hello"},
        request_body={"content": "hello"},
        turn_id=turn["id"],
    )
    conn.execute(
        "UPDATE external_requests SET last_attempted_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00.000Z", request["id"]),
    )
    conn.commit()

    assert [row["id"] for row in store.find_abandoned_turns(300)] == [turn["id"]]
    pending = store.find_pending_external_requests(60)
    assert [row["id"] for row in pending] == [request["id"]]
    assert pending[0]["request_body"] == {"content": "hello"}

    orphaned = store.mark_orphaned(request["id"], error_details={"reason": "expired"})
    assert orphaned["status"] == "orphaned"
    assert orphaned["error_details"] == {"reason": "expired"}
    assert orphaned["completed_at"] is not None


def test_image_crud_methods_and_reference_key_generation() -> None:
    store, _conn = _store()

    first = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/a.png",
        discord_attachment_id="attachment_1",
    )
    second = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/b.png",
        caption="before",
    )
    generated = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/c.png",
        reference_key="hero",
        active=False,
    )
    caller_uploaded = store.create_image(
        epic_id="epic_1",
        source="caller_uploaded",
        storage_url="images/epic_1/caller.png",
    )

    assert first["reference_key"] == "img_user_upload_1"
    assert second["reference_key"] == "img_user_upload_2"
    assert generated["reference_key"] == "hero"
    assert caller_uploaded["reference_key"] == "img_caller_upload_1"
    assert store.load_image(first["id"])["discord_attachment_id"] == "attachment_1"

    active_user_images = store.list_images(epic_id="epic_1", source="user_uploaded")
    assert {row["id"] for row in active_user_images} == {first["id"], second["id"]}
    active_caller_images = store.list_images(epic_id="epic_1", source="caller_uploaded")
    assert [row["id"] for row in active_caller_images] == [caller_uploaded["id"]]
    all_images = store.list_images(epic_id="epic_1", active=None)
    assert {row["id"] for row in all_images} == {
        first["id"],
        second["id"],
        generated["id"],
        caller_uploaded["id"],
    }

    updated = store.update_image(
        second["id"],
        caption="after",
        description="diagram",
        in_body=True,
        active=False,
    )
    assert updated["caption"] == "after"
    assert updated["description"] == "diagram"
    assert updated["in_body"] == 1
    assert updated["active"] == 0


def test_active_image_helpers_and_second_opinions_hot_context() -> None:
    store, _conn = _store()

    older = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/older.png",
        reference_key="img_flow",
        description="older flow",
    )
    assert store.active_image_reference_exists("epic_1", "img_flow") is True
    assert store.load_active_image_by_reference("epic_1", "img_flow")["id"] == older["id"]

    deactivated = store.deactivate_active_image_reference("epic_1", "img_flow")
    newer = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/newer.png",
        reference_key="img_flow",
        description="newer flow",
    )

    assert [row["id"] for row in deactivated] == [older["id"]]
    assert store.load_image(older["id"])["active"] == 0
    assert store.load_active_image_by_reference("epic_1", "img_flow")["id"] == newer["id"]
    assert [row["id"] for row in store.list_active_images("epic_1")] == [newer["id"]]

    first_opinion = store.create_second_opinion(
        epic_id="epic_1",
        requested_by="user",
        focus_areas=["handoff", "ambiguity"],
        raw_response="Score: 6/10\n\nVerdict: needs work",
        score=6,
        summary="Material gaps remain.",
        verdict="needs work",
        model_used="gpt-5.5",
    )
    _conn.execute(
        "UPDATE second_opinions SET requested_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00.000Z", first_opinion["id"]),
    )
    _conn.commit()
    second_opinion = store.create_second_opinion(
        epic_id="epic_1",
        requested_by="auto_state_gate",
        focus_areas=["sprint realism"],
        raw_response="Score: 8/10\n\nVerdict: mostly ready",
        score=8,
        summary="Mostly ready.",
        verdict="mostly ready",
        model_used="gpt-5.5",
        resulting_checklist_item_ids=["item_1"],
    )
    updated_opinion = store.set_second_opinion_checklist_items(
        first_opinion["id"],
        ["item_2", "item_3"],
    )

    assert updated_opinion["resulting_checklist_item_ids"] == ["item_2", "item_3"]
    assert [row["id"] for row in store.list_second_opinions("epic_1")] == [
        second_opinion["id"],
        first_opinion["id"],
    ]

    hot_context = store.load_hot_context("epic_1")
    assert hot_context["active_images"] == [
        {
            "id": newer["id"],
            "reference_key": "img_flow",
            "source": "agent_generated",
            "description": "newer flow",
            "caption": None,
            "storage_url": "images/epic_1/newer.png",
            "quality": None,
            "size": None,
            "created_at": newer["created_at"],
        }
    ]
    assert [row["id"] for row in hot_context["recent_second_opinions"]] == [
        second_opinion["id"],
        first_opinion["id"],
    ]
    assert "raw_response" not in hot_context["recent_second_opinions"][0]
