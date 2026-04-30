from __future__ import annotations

import asyncio

from agent_kit.ledger import Ledger, Reconciler
from agent_kit.model import FakeModel
from agent_kit.resident import MessageCoalescer, ResidentRunner, format_status
from tests.helpers import create_store, insert_epic


class FakePushTransport:
    def __init__(self) -> None:
        self.posts = []
        self.edits = []
        self.handler = None

    def start(self, handler):
        self.handler = handler

    def stop(self) -> None:
        pass

    def post_message(self, channel_id, content, *, files=None):
        message_id = f"discord_{len(self.posts) + 1}"
        self.posts.append({"channel_id": channel_id, "content": content, "files": files})
        return {"discord_message_id": message_id, "content": content}

    def edit_message(self, channel_id, message_id, content):
        self.edits.append(
            {"channel_id": channel_id, "message_id": message_id, "content": content}
        )
        return {"discord_message_id": message_id, "content": content}

    def download_attachment(self, url):
        return b""

    def fetch_recent_messages(self, channel_id, since, until):
        return []


def test_format_status_dynamic_and_terminal_states() -> None:
    in_progress = format_status(
        {"status": "in_progress"},
        [{"tool_name": "list_images"}, {"tool_name": "send_message"}],
        "drafting",
        1_777_777_777,
    )
    assert "Activity: drafting" in in_progress
    assert "Recent: list_images, send_message" in in_progress
    assert "<t:1777777777:R>" in in_progress

    done = format_status(
        {"status": "completed"},
        [{"tool_name": "a"}, {"tool_name": "b"}],
        None,
        1_777_777_777,
    )
    assert done == "✅ Done. 2 tool calls. <t:1777777777:R>"

    failed = format_status({"status": "failed", "reasoning": "boom"}, [], None, 1)
    assert failed == "❌ Failed. boom"


def test_message_coalescer_flushes_burst_after_reset_window() -> None:
    async def scenario():
        dispatched = []
        coalescer = MessageCoalescer(
            lambda epic_id, message_ids: dispatched.append((epic_id, message_ids)),
            window_seconds=0.01,
            hard_cap_seconds=1.0,
            max_messages=10,
        )
        coalescer.add("epic_1", "msg_1")
        await asyncio.sleep(0.005)
        coalescer.add("epic_1", "msg_2")
        await asyncio.sleep(0.03)
        assert dispatched == [("epic_1", ["msg_1", "msg_2"])]

    asyncio.run(scenario())


def test_message_coalescer_skips_dispatch_when_turn_in_flight() -> None:
    async def scenario():
        dispatched = []
        coalescer = MessageCoalescer(
            lambda epic_id, message_ids: dispatched.append((epic_id, message_ids)),
            window_seconds=0.01,
        )
        coalescer.in_flight.add("epic_1")
        coalescer.add("epic_1", "msg_1")
        await asyncio.sleep(0.03)
        assert dispatched == []

    asyncio.run(scenario())


def test_resident_runner_posts_initial_status_and_final_edit(tmp_path) -> None:
    async def scenario():
        store, conn = create_store(tmp_path / "arnold.db")
        insert_epic(conn)
        message = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="hello",
            discord_message_id="discord_in_1",
        )
        transport = FakePushTransport()
        ledger = Ledger(store)
        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "resident reply"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=ledger,
            reconciler=Reconciler(store),
            status_debounce_seconds=0,
        )
        runner.channel_ids["epic_1"] = "channel_1"

        envelope = await runner.dispatch_turn("epic_1", [message["id"]])

        assert envelope.outcome == "completed"
        assert transport.posts[0]["channel_id"] == "channel_1"
        assert "Planning turn in progress" in transport.posts[0]["content"]
        assert transport.posts[1]["content"] == "resident reply"
        assert transport.edits[-1]["message_id"] == "discord_1"
        assert "Done." in transport.edits[-1]["content"]
        row = conn.execute("SELECT status_message_id FROM bot_turns").fetchone()
        assert row["status_message_id"] == "discord_1"

    asyncio.run(scenario())
