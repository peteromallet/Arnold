from __future__ import annotations

import json

from agent_kit.loop import run_turn
from agent_kit.model import FakeModel, tool_request
from tests.helpers import create_store, insert_epic


def test_resident_trigger_ids_recovered_messages_and_on_turn_start(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    second = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="second",
        discord_message_id="discord_2",
    )
    first = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="first",
        discord_message_id="discord_1",
    )
    conn.execute(
        "UPDATE messages SET sent_at = ? WHERE id = ?",
        ("2026-04-30T10:00:00.000Z", first["id"]),
    )
    conn.execute(
        "UPDATE messages SET sent_at = ? WHERE id = ?",
        ("2026-04-30T10:00:01.000Z", second["id"]),
    )
    conn.commit()
    first = store.load_message(first["id"])
    second = store.load_message(second["id"])
    starts = []
    model = FakeModel(script=[{"final_text": "done"}])

    envelope = run_turn(
        epic_id="epic_1",
        input="ignored invocation input",
        store=store,
        model=model,
        model_id="fake",
        triggered_by_message_ids=[first["id"], second["id"]],
        recovered_input_messages=[second, first],
        on_turn_start=starts.append,
    )

    assert envelope.outcome == "completed"
    assert starts and starts[0]["id"] == envelope.turn_id
    assert starts[0]["triggered_by_message_ids"] == [first["id"], second["id"]]
    assert model.calls[0]["messages"][0]["content"] == "first\n\nsecond"
    assert conn.execute(
        "SELECT COUNT(*) FROM messages WHERE direction = 'inbound'"
    ).fetchone()[0] == 2


def test_mid_turn_check_before_final_text_auto_send_reprompts(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    mid_rows = []

    def on_start(turn):
        mid_rows.append(
            store.create_message(
                epic_id="epic_1",
                direction="inbound",
                content="also consider this",
                discord_message_id="discord_mid",
            )
        )

    seen_mid_turn = False

    def mid_turn_check(_turn):
        nonlocal seen_mid_turn
        if seen_mid_turn:
            return None
        seen_mid_turn = True
        return list(mid_rows)

    model = FakeModel(
        script=[
            {"final_text": "premature"},
            {"final_text": "done"},
        ]
    )

    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=model,
        model_id="fake",
        on_turn_start=on_start,
        mid_turn_message_check=mid_turn_check,
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == "done"
    assert model.call_count == 2
    assert "Mid-turn messages" in model.calls[1]["messages"][-1]["content"]
    assert "also consider this" in model.calls[1]["messages"][-1]["content"]
    turn = conn.execute("SELECT triggered_by_message_ids FROM bot_turns").fetchone()
    assert mid_rows[0]["id"] in json.loads(turn["triggered_by_message_ids"])


def test_mid_turn_check_before_explicit_send_message_reprompts(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    mid_rows = []

    def on_start(_turn):
        mid_rows.append(
            store.create_message(
                epic_id="epic_1",
                direction="inbound",
                content="wait, one more thing",
                discord_message_id="discord_mid",
            )
        )

    seen_mid_turn = False

    def mid_turn_check(_turn):
        nonlocal seen_mid_turn
        if seen_mid_turn:
            return None
        seen_mid_turn = True
        return list(mid_rows)

    model = FakeModel(
        script=[
            {
                "tool_requests": [
                    tool_request("send_message", {"content": "premature"})
                ]
            },
            {"final_text": "done"},
        ]
    )

    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=model,
        model_id="fake",
        on_turn_start=on_start,
        mid_turn_message_check=mid_turn_check,
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == "done"
    assert model.call_count == 2
    assert "wait, one more thing" in model.calls[1]["messages"][-1]["content"]
    outbound = conn.execute(
        "SELECT content FROM messages WHERE direction = 'outbound'"
    ).fetchall()
    assert [row["content"] for row in outbound] == ["done"]
