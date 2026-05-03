from __future__ import annotations

import asyncio

from agent_kit.ledger import Ledger, Reconciler
from agent_kit.model import FakeModel, tool_request
from agent_kit.resident import ResidentRunner
from tests.helpers import create_store, insert_epic
from tests.test_resident import FakePushTransport


def test_status_lifecycle_posts_initial_edits_tools_and_final_done(tmp_path) -> None:
    async def scenario() -> None:
        store, conn = create_store(tmp_path / "arnold.db")
        insert_epic(conn)
        message = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="run tools",
            discord_message_id="discord_in_1",
        )
        transport = FakePushTransport()
        runner = _runner(
            store,
            transport,
            FakeModel(
                script=[
                    {
                        "tool_requests": [
                            tool_request("set_activity", {"description": "step one"}),
                            tool_request("set_activity", {"description": "step two"}),
                        ],
                    },
                    {"final_text": "done"},
                ]
            ),
            debounce=0,
        )

        await runner.dispatch_turn("epic_1", [message["id"]])

        assert len(transport.posts) == 2
        assert "Planning turn in progress" in transport.posts[0]["content"]
        assert transport.posts[1]["content"] == "done"
        assert 1 <= len(transport.edits) <= 4
        assert "✅ Done. 3 tool calls." in transport.edits[-1]["content"]
        assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 3
        message_rows = conn.execute(
            "SELECT direction, content, discord_message_id FROM messages ORDER BY rowid"
        ).fetchall()
        assert [(row["direction"], row["content"]) for row in message_rows] == [
            ("inbound", "run tools"),
            ("outbound", "done"),
        ]
        assert all(
            "Planning turn in progress" not in row["content"] for row in message_rows
        )
        assert message_rows[-1]["discord_message_id"] == "discord_2"

    asyncio.run(scenario())


def test_status_lifecycle_throttles_rapid_tool_edits(tmp_path) -> None:
    async def scenario() -> None:
        store, _conn = create_store(tmp_path / "arnold.db")
        insert_epic(_conn)
        message = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="many tools",
            discord_message_id="discord_in_1",
        )
        transport = FakePushTransport()
        runner = _runner(
            store,
            transport,
            FakeModel(
                script=[
                    {
                        "tool_requests": [
                            tool_request("set_activity", {"description": f"step {index}"})
                            for index in range(20)
                        ],
                    },
                    {"final_text": "done"},
                ]
            ),
            debounce=1,
        )

        await runner.dispatch_turn("epic_1", [message["id"]])

        assert len(transport.edits) <= 4
        assert "✅ Done." in transport.edits[-1]["content"]

    asyncio.run(scenario())


def _runner(store, transport, model, *, debounce: float) -> ResidentRunner:
    runner = ResidentRunner(
        store=store,
        model=model,
        model_id="fake",
        transport=transport,
        blob=None,
        ledger=Ledger(store),
        reconciler=Reconciler(store),
        status_debounce_seconds=debounce,
    )
    runner.channel_ids["epic_1"] = "channel_1"
    return runner
