from __future__ import annotations

from tests.helpers import create_store, insert_epic


def test_outbound_create_message_synthesize_flag_controls_discord_id(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])

    synthesized = store.create_message(
        epic_id="epic_1",
        direction="outbound",
        content="invocation",
        bot_turn_id=turn["id"],
    )
    unsynthesized = store.create_message(
        epic_id="epic_1",
        direction="outbound",
        content="resident",
        bot_turn_id=turn["id"],
        synthesize_outbound_id=False,
    )

    assert synthesized["discord_message_id"] == f"inv_{turn['id']}_1"
    assert unsynthesized["discord_message_id"] is None
