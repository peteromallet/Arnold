from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

from agent_kit.ledger import Ledger, Reconciler
from agent_kit.ports import JSONDict, ModelTurnResult, ToolRequest
from agent_kit.resident import ResidentRunner
from tests.helpers import create_store, insert_epic
from tests.test_resident import FakePushTransport


class MidTurnModel:
    def __init__(self, store, *, first_result: ModelTurnResult) -> None:
        self.store = store
        self.first_result = first_result
        self.calls: list[list[JSONDict]] = []
        self.created_mid_message_id: str | None = None

    def complete_turn(
        self,
        *,
        model_id: str,
        messages: Sequence[JSONDict],
        tools: Sequence[JSONDict],
        hot_context: JSONDict,
        idempotency_key: str | None = None,
    ) -> ModelTurnResult:
        del model_id, tools, hot_context, idempotency_key
        self.calls.append(list(messages))
        if self.created_mid_message_id is None:
            row = self.store.create_message(
                epic_id="epic_1",
                direction="inbound",
                content="second message arrived",
                discord_message_id="discord_mid_1",
            )
            self.created_mid_message_id = row["id"]
            return self.first_result
        return ModelTurnResult(final_text="final after mid-turn")


def test_mid_turn_message_reprompts_before_final_text_send(tmp_path) -> None:
    async def scenario() -> None:
        store, conn = create_store(tmp_path / "arnold.db")
        insert_epic(conn)
        first = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="first message",
            discord_message_id="discord_first",
        )
        model = MidTurnModel(
            store,
            first_result=ModelTurnResult(final_text="premature final"),
        )
        transport = FakePushTransport()
        runner = _runner(store, transport, model)

        await runner.dispatch_turn("epic_1", [first["id"]])

        turn = conn.execute("SELECT * FROM bot_turns").fetchone()
        assert json.loads(turn["triggered_by_message_ids"]) == [
            first["id"],
            model.created_mid_message_id,
        ]
        assert len(model.calls) == 2
        assert "[Mid-turn messages" in str(model.calls[1])
        assert "second message arrived" in str(model.calls[1])
        assert any("📥 Received" in edit["content"] for edit in transport.edits)
        assert "premature final" not in [post["content"] for post in transport.posts]

    asyncio.run(scenario())


def test_mid_turn_message_reprompts_before_explicit_send_message(tmp_path) -> None:
    async def scenario() -> None:
        store, conn = create_store(tmp_path / "arnold.db")
        insert_epic(conn)
        first = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="first message",
            discord_message_id="discord_first",
        )
        model = MidTurnModel(
            store,
            first_result=ModelTurnResult(
                tool_requests=[
                    ToolRequest(
                        name="send_message",
                        arguments={"content": "should not send before re-prompt"},
                    )
                ]
            ),
        )
        transport = FakePushTransport()
        runner = _runner(store, transport, model)

        await runner.dispatch_turn("epic_1", [first["id"]])

        turn = conn.execute("SELECT * FROM bot_turns").fetchone()
        assert json.loads(turn["triggered_by_message_ids"]) == [
            first["id"],
            model.created_mid_message_id,
        ]
        assert len(model.calls) == 2
        assert "[Mid-turn messages" in str(model.calls[1])
        assert all(
            post["content"] != "should not send before re-prompt"
            for post in transport.posts
        )

    asyncio.run(scenario())


def _runner(store, transport, model) -> ResidentRunner:
    runner = ResidentRunner(
        store=store,
        model=model,
        model_id="fake",
        transport=transport,
        blob=None,
        ledger=Ledger(store),
        reconciler=Reconciler(store),
        status_debounce_seconds=0,
    )
    runner.channel_ids["epic_1"] = "channel_1"
    return runner
