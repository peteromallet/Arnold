from __future__ import annotations

from typing import Callable


def run_store_contract(store_factory: Callable):
    store, conn = store_factory()
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()

    inbound = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="hello",
        discord_message_id="discord_1",
        has_code_attachment=True,
    )
    assert store.load_message(inbound["id"])["content"] == "hello"
    assert store.load_hot_context("epic_1")["epic"]["title"] == "Title"

    turn = store.create_turn(
        epic_id="epic_1",
        triggered_by_message_ids=[inbound["id"]],
        prompt_snapshot={"input": "hello"},
        state_at_turn={"state": "shaping"},
        model_version="fake",
    )
    updated = store.update_turn(turn["id"], status="completed", reasoning="done")
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None

    outbound = store.create_message(
        epic_id="epic_1",
        direction="outbound",
        content="hi",
        bot_turn_id=turn["id"],
    )
    assert outbound["discord_message_id"] == f"inv_{turn['id']}_1"

    tool_call = store.record_tool_call(
        turn_id=turn["id"],
        tool_name="send_message",
        operation_kind="write",
        arguments={"content": "hi"},
        result={"discord_message_id": outbound["discord_message_id"]},
        duration_ms=1,
    )
    assert tool_call["arguments"]["content"] == "hi"

    log = store.log_system_event(
        level="info",
        category="system",
        event_type="contract",
        message="ok",
        details={"ok": True},
        turn_id=turn["id"],
        epic_id="epic_1",
    )
    assert log["details"]["ok"] is True

    assert store.acquire_epic_lock("epic_1", holder_id="holder_a") is True
    assert store.acquire_epic_lock("epic_1", holder_id="holder_b") is False
    store.release_epic_lock("epic_1", holder_id="holder_a")
    assert store.acquire_epic_lock("epic_1", holder_id="holder_b") is True

