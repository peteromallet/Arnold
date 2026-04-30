from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from agent_kit.ledger import Ledger, Reconciler
from agent_kit.model import FakeModel
from agent_kit.resident import ResidentRunner
from tests.helpers import create_store, insert_epic
from tests.test_resident import FakePushTransport


def test_recovery_abandons_stale_turn_and_dispatches_fresh_turn(tmp_path) -> None:
    async def scenario() -> None:
        store, conn = create_store(tmp_path / "arnold.db")
        insert_epic(conn)
        inbound = store.create_message(
            epic_id="epic_1",
            direction="inbound",
            content="recover this",
            discord_message_id="discord_in_1",
        )
        stale = store.create_turn(
            epic_id="epic_1",
            triggered_by_message_ids=[inbound["id"]],
        )
        conn.execute(
            "UPDATE bot_turns SET started_at = ? WHERE id = ?",
            (_old_timestamp(600), stale["id"]),
        )
        conn.commit()

        transport = FakePushTransport()
        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "recovered reply"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=Ledger(store),
            reconciler=Reconciler(store),
            status_debounce_seconds=0,
        )
        runner.channel_ids["epic_1"] = "channel_1"

        result = runner.reconciler.run_once()
        assert result["requeued_message_ids"] == [inbound["id"]]
        assert (
            conn.execute(
                "SELECT status FROM bot_turns WHERE id = ?",
                (stale["id"],),
            ).fetchone()["status"]
            == "abandoned"
        )

        envelope = await runner.dispatch_turn("epic_1", result["requeued_message_ids"])

        assert envelope.outcome == "completed"
        rows = conn.execute(
            "SELECT id, status, triggered_by_message_ids FROM bot_turns ORDER BY started_at"
        ).fetchall()
        assert [row["status"] for row in rows] == ["abandoned", "completed"]
        assert json.loads(rows[-1]["triggered_by_message_ids"]) == [inbound["id"]]
        assert transport.posts[-1]["content"] == "recovered reply"

    asyncio.run(scenario())


def _old_timestamp(seconds: int) -> str:
    value = datetime.now(UTC) - timedelta(seconds=seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
