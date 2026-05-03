from __future__ import annotations

import sqlite3

from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.editorial  # noqa: F401


def _store_with_turn(body: str):
    conn = sqlite3.connect(":memory:")
    store = SQLiteStore(conn)
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', ?, 'shaping')
        """,
        (body,),
    )
    conn.commit()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    return store, conn, turn


def test_render_epic_resolves_uploaded_and_generated_image_references() -> None:
    body = (
        "# Title\n\n"
        "![flow](image:img_flow)\n\n"
        "![generated](image:img_generated)\n\n"
        "![missing](image:img_missing)"
    )
    store, conn, turn = _store_with_turn(body)
    uploaded = store.create_image(
        epic_id="epic_1",
        source="user_uploaded",
        storage_url="images/epic_1/uploaded.png",
        reference_key="img_flow",
        active=True,
    )
    generated = store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/generated.png",
        reference_key="img_generated",
        active=True,
    )
    store.create_image(
        epic_id="epic_1",
        source="agent_generated",
        storage_url="images/epic_1/inactive.png",
        reference_key="img_missing",
        active=False,
    )
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    result = registry.invoke("render_epic", context, {"epic_id": "epic_1"}).result

    assert "![flow](images/epic_1/uploaded.png)" in result["body"]
    assert "![generated](images/epic_1/generated.png)" in result["body"]
    assert "![missing](missing-image:img_missing)" in result["body"]
    assert result["raw_body"] == body
    assert conn.execute("SELECT body FROM epics WHERE id = 'epic_1'").fetchone()["body"] == body
    assert result["resolved_image_references"] == [
        {
            "reference_key": "img_flow",
            "caption": "flow",
            "image_id": uploaded["id"],
            "source": "user_uploaded",
            "storage_url": "images/epic_1/uploaded.png",
        },
        {
            "reference_key": "img_generated",
            "caption": "generated",
            "image_id": generated["id"],
            "source": "agent_generated",
            "storage_url": "images/epic_1/generated.png",
        },
    ]
    assert result["missing_image_references"] == [
        {
            "reference_key": "img_missing",
            "caption": "missing",
            "placeholder": "missing-image:img_missing",
        }
    ]
