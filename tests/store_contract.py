from __future__ import annotations

import time
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

    no_epic_turn = store.create_turn(
        epic_id=None,
        triggered_by_message_ids=[],
        prompt_snapshot={"input": "bootstrap"},
    )
    assert no_epic_turn["epic_id"] is None
    row = conn.execute(
        f"SELECT epic_id FROM bot_turns WHERE id = '{no_epic_turn['id']}'"
    ).fetchone()
    assert (row["epic_id"] if isinstance(row, dict) else row[0]) is None

    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial goal",
        body="# Editorial Title\n\n## Goal\n\nEditorial goal\n",
    )
    assert epic["id"].startswith("epic_")
    assert epic["title"] == "Editorial Title"
    assert epic["goal"] == "Editorial goal"

    checklist = store.seed_checklist(epic["id"], ["First item", "Second item"])
    assert [item["position"] for item in checklist] == [1, 2]
    assert [item["source"] for item in checklist] == ["default_seed", "default_seed"]
    assert [item["content"] for item in store.list_checklist_items(epic["id"])] == [
        "First item",
        "Second item",
    ]

    event_turn = store.create_turn(
        epic_id=epic["id"],
        triggered_by_message_ids=[],
    )
    first = store.record_epic_event(
        epic_id=epic["id"],
        transaction_id="txn_shared",
        event_type="body_edit",
        summary="Body updated",
        prior_state={"body": "before"},
        turn_id=event_turn["id"],
    )
    second = store.record_epic_event(
        epic_id=epic["id"],
        transaction_id="txn_shared",
        event_type="checklist_change",
        summary="Checklist updated",
        prior_state={"items": checklist},
        turn_id=event_turn["id"],
    )
    time.sleep(0.002)
    third = store.record_epic_event(
        epic_id=epic["id"],
        transaction_id="txn_latest",
        event_type="state_change",
        summary="State updated",
        prior_state={"state": "shaping"},
        turn_id=event_turn["id"],
    )
    shared_events = store.events_by_transaction("txn_shared")
    assert {event["id"] for event in shared_events} == {first["id"], second["id"]}
    assert shared_events == sorted(
        shared_events,
        key=lambda event: (event["occurred_at"], event["id"]),
    )
    listed_events = store.list_epic_events(epic["id"])
    assert {event["id"] for event in listed_events} == {
        first["id"],
        second["id"],
        third["id"],
    }
    assert listed_events == sorted(
        listed_events,
        key=lambda event: (event["occurred_at"], event["id"]),
    )
    assert [event["id"] for event in store.list_epic_events(epic["id"], kinds=["body_edit"])] == [
        first["id"],
    ]
    assert store.latest_transaction_id(epic["id"]) == "txn_latest"
