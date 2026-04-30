from __future__ import annotations

import sqlite3

from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, ToolRegistry


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


def test_audit_wrapper_rolls_back_mutation_and_audit_on_failure() -> None:
    store, conn, turn = _store_with_turn()
    registry = ToolRegistry()

    def failing_tool(context):
        context.store.create_message(
            epic_id="epic_1",
            direction="outbound",
            content="bad",
            bot_turn_id=context.turn_id,
        )
        raise RuntimeError("fail")

    registry.register("failing_tool", failing_tool, {"type": "object"})
    context = ToolContext(store=store, turn_id=turn["id"], events=[])
    try:
        registry.invoke("failing_tool", context, {})
    except RuntimeError:
        pass
    else:
        raise AssertionError("tool did not fail")

    assert context.events == []
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 0
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM messages WHERE content = 'bad'"
        ).fetchone()[0]
        == 0
    )


def test_event_kind_dispatch_and_tool_call_id_present() -> None:
    store, conn, turn = _store_with_turn()
    registry = ToolRegistry()
    seen = []

    def activity_tool(context, description):
        return {"description": description}

    registry.register(
        "activity_tool",
        activity_tool,
        {"type": "object"},
        event_kind="activity",
    )
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        on_event=seen.append,
    )
    invocation = registry.invoke(
        "activity_tool",
        context,
        {"description": "drafting"},
    )

    assert len(context.events) == 1
    assert context.events[0] is seen[0] is invocation.event
    assert invocation.event.kind == "activity"
    assert invocation.event.text == "drafting"
    assert invocation.event.tool_call_id
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1

