from __future__ import annotations

import asyncio
import threading

from agent_kit.envelope import Envelope
from agent_kit.ledger import Ledger, Reconciler
from agent_kit.model import FakeModel
from agent_kit.resident import MessageCoalescer, ResidentRunner, format_status
from tests.helpers import create_store, insert_epic


class FakePushTransport:
    def __init__(self) -> None:
        self.posts = []
        self.edits = []
        self.typing = []
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

    def set_typing(self, channel_id, on):
        self.typing.append({"channel_id": channel_id, "on": on})
        return {"channel_id": channel_id, "typing": on}

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


def test_resident_runner_uses_worker_thread_when_transport_owns_loop(tmp_path, monkeypatch) -> None:
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
        transport._loop = asyncio.get_running_loop()
        loop_thread_id = threading.get_ident()
        run_turn_thread_ids = []
        turn = store.create_turn(
            epic_id="epic_1",
            triggered_by_message_ids=[message["id"]],
        )

        def fake_run_turn(**kwargs):
            run_turn_thread_ids.append(threading.get_ident())
            return Envelope(
                turn_id=turn["id"],
                epic_id=kwargs["epic_id"],
                epic_state_before="shaping",
                epic_state_after="shaping",
                reply="",
            )

        monkeypatch.setattr("agent_kit.resident.run_turn", fake_run_turn)
        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "unused"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=Ledger(store),
            reconciler=Reconciler(store),
            status_debounce_seconds=0,
        )
        runner.channel_ids["epic_1"] = "channel_1"

        await runner.dispatch_turn("epic_1", [message["id"]])

        assert run_turn_thread_ids
        assert run_turn_thread_ids[0] != loop_thread_id

    asyncio.run(scenario())


def test_resident_runner_quiet_discord_mode_uses_typing_without_status_post(tmp_path, monkeypatch) -> None:
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
        transport._loop = asyncio.get_running_loop()
        turn = store.create_turn(
            epic_id="epic_1",
            triggered_by_message_ids=[message["id"]],
        )

        def fake_run_turn(**kwargs):
            kwargs["on_turn_start"](turn)
            return Envelope(
                turn_id=turn["id"],
                epic_id=kwargs["epic_id"],
                epic_state_before="shaping",
                epic_state_after="shaping",
                reply="",
            )

        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "resident reply"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=Ledger(store),
            reconciler=Reconciler(store),
            status_debounce_seconds=0,
        )
        runner.channel_ids["epic_1"] = "channel_1"

        monkeypatch.setattr("agent_kit.resident.run_turn", fake_run_turn)
        await runner.dispatch_turn("epic_1", [message["id"]])

        assert transport.typing == [{"channel_id": "channel_1", "on": True}]
        assert all("Planning turn in progress" not in post["content"] for post in transport.posts)
        assert transport.posts == []
        assert transport.edits == []

    asyncio.run(scenario())


def test_resident_runner_quiet_status_flag_uses_typing_without_status_post(tmp_path, monkeypatch) -> None:
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
        transport.quiet_status_updates = True
        turn = store.create_turn(
            epic_id="epic_1",
            triggered_by_message_ids=[message["id"]],
        )

        def fake_run_turn(**kwargs):
            kwargs["on_turn_start"](turn)
            return Envelope(
                turn_id=turn["id"],
                epic_id=kwargs["epic_id"],
                epic_state_before="shaping",
                epic_state_after="shaping",
                reply="",
            )

        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "resident reply"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=Ledger(store),
            reconciler=Reconciler(store),
            status_debounce_seconds=0,
        )
        runner.channel_ids["epic_1"] = "channel_1"

        monkeypatch.setattr("agent_kit.resident.run_turn", fake_run_turn)
        await runner.dispatch_turn("epic_1", [message["id"]])

        assert transport.typing == [{"channel_id": "channel_1", "on": True}]
        assert transport.posts == []
        assert transport.edits == []

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
