from __future__ import annotations

import asyncio

from agent_kit.resident import MessageCoalescer


def test_coalescer_collects_burst_until_window_expires() -> None:
    async def scenario():
        dispatched = []
        coalescer = MessageCoalescer(
            lambda epic_id, ids: dispatched.append((epic_id, ids)),
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


def test_coalescer_flushes_immediately_at_message_cap() -> None:
    async def scenario():
        dispatched = []
        coalescer = MessageCoalescer(
            lambda epic_id, ids: dispatched.append((epic_id, ids)),
            window_seconds=100,
            max_messages=2,
        )
        coalescer.add("epic_1", "msg_1")
        coalescer.add("epic_1", "msg_2")
        await asyncio.sleep(0)
        assert dispatched == [("epic_1", ["msg_1", "msg_2"])]

    asyncio.run(scenario())
