from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json

import agent_kit.loop
from agent_kit.epic_routing import (
    conversation_gap_acknowledgment,
    detect_user_mode,
    resolve_reference,
    select_epic_for_message,
)
from agent_kit.ledger import Ledger, Reconciler
from agent_kit.model import FakeModel
from agent_kit.prompts import build_system_prompt
from agent_kit.resident import ResidentRunner
from agent_kit.tool_kit import ToolContext, registry
from tests.helpers import create_store, insert_epic
from tests.test_resident import FakePushTransport


def test_epic_selection_picks_single_recent_active_epic() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    epics = [
        _epic(f"epic_{index}", f"Epic {index}", now - timedelta(days=2))
        for index in range(4)
    ]
    epics.append(_epic("epic_5", "Hot Epic", now - timedelta(hours=3)))

    decision = select_epic_for_message("please tighten the scope", epics, now=now)

    assert decision.epic_id == "epic_5"
    assert decision.reason == "single_recent_default"


def test_epic_selection_asks_when_multiple_recent_defaults() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    epics = [
        _epic("epic_a", "Alpha", now - timedelta(hours=1)),
        _epic("epic_b", "Beta", now - timedelta(hours=2)),
    ]

    decision = select_epic_for_message("please tighten the scope", epics, now=now)

    assert decision.needs_clarification
    assert decision.epic_id is None


def test_reference_resolution_handles_ordinals_and_ambiguity() -> None:
    outbound = "1. Keep the CLI small\n2. Add message search\n3. Add mode reading"

    resolved = resolve_reference("the second one", outbound)
    ambiguous = resolve_reference("that point", outbound)

    assert resolved["resolved"] is True
    assert resolved["target"]["text"] == "Add message search"
    assert ambiguous["resolved"] is False
    assert ambiguous["reason"] == "ambiguous_deictic"


def test_mode_detection_and_gap_policy_feed_prompt() -> None:
    policy = {
        "mode": detect_user_mode("let's just do the direct version asap"),
        "conversation_gap_acknowledgment": conversation_gap_acknowledgment(
            "2026-04-28T10:00:00Z",
            now=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        ),
    }

    prompt = build_system_prompt({"response_policy": policy})

    assert policy["mode"] == "executing"
    assert policy["conversation_gap_acknowledgment"]["should_acknowledge"] is True
    assert "User mode: executing" in prompt
    assert "Briefly acknowledge the conversation gap" in prompt


def test_store_list_and_search_methods_return_stable_shapes(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn, "epic_alpha")
    conn.execute(
        "UPDATE epics SET title = ?, goal = ?, body = ? WHERE id = ?",
        ("Alpha Search", "Find the missing memory", "# Alpha\nUse lexical search.", "epic_alpha"),
    )
    inbound = store.create_message(
        epic_id="epic_alpha",
        direction="inbound",
        content="We need full text search over messages.",
        discord_message_id="discord_in_alpha",
    )

    listed = store.list_epics()
    epic_hits = store.search_epics(query="missing memory")
    message_hits = store.search_messages(query="full text search")

    assert listed[0]["id"] == "epic_alpha"
    assert epic_hits[0]["id"] == "epic_alpha"
    assert message_hits[0]["id"] == inbound["id"]
    assert {"id", "epic_id", "direction", "snippet", "sent_at", "rank"} <= set(message_hits[0])


def test_active_epic_reads_exclude_archived_epics(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn, "epic_active")
    insert_epic(conn, "epic_archived")
    conn.execute(
        "UPDATE epics SET title = ?, goal = ?, body = ?, state = ? WHERE id = ?",
        ("Visible Search", "shared target", "# Visible", "shaping", "epic_active"),
    )
    conn.execute(
        "UPDATE epics SET title = ?, goal = ?, body = ?, state = ? WHERE id = ?",
        ("Archived Search", "shared target", "# Archived", "archived", "epic_archived"),
    )
    conn.commit()

    listed_ids = {row["id"] for row in store.list_epics(active_only=True)}
    active_hit_ids = {row["id"] for row in store.search_epics(query="shared target", active_only=True)}
    all_hit_ids = {row["id"] for row in store.search_epics(query="shared target", active_only=False)}

    assert listed_ids == {"epic_active"}
    assert active_hit_ids == {"epic_active"}
    assert all_hit_ids == {"epic_active", "epic_archived"}


def test_message_search_seeded_corpus_returns_expected_hit_ids(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn, "epic_search")
    corpus = {
        "lexical": "Lexical retrieval should find message content quickly.",
        "routing": "Routing corrections mention explicit epic switching.",
        "gap": "Conversation gap acknowledgments happen after a long pause.",
        "mode": "Executing mode keeps replies direct and concise.",
        "brainstorm": "Brainstorming mode explores options with more energy.",
        "deep": "Deep thinking mode is measured and substantive.",
        "reference": "Reference resolution handles the second one and that point.",
        "summary": "Understanding summaries include checklist decisions and images.",
        "sqlite": "SQLite full text search uses FTS triggers.",
        "supabase": "Supabase full text search uses a GIN index.",
    }
    expected_ids = {
        key: store.create_message(
            epic_id="epic_search",
            direction="inbound",
            content=content,
            discord_message_id=f"discord_{key}",
        )["id"]
        for key, content in corpus.items()
    }

    queries = {
        "lexical retrieval": "lexical",
        "epic switching": "routing",
        "long pause": "gap",
        "direct concise": "mode",
        "explores options": "brainstorm",
        "measured substantive": "deep",
        "second one": "reference",
        "checklist images": "summary",
        "FTS triggers": "sqlite",
        "GIN index": "supabase",
    }

    for query, key in queries.items():
        hits = store.search_messages(query=query, epic_id="epic_search", limit=3)
        assert hits, query
        assert hits[0]["id"] == expected_ids[key]


def test_epic_selection_eval_covers_thirty_canned_scenarios() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=2)
    recent = now - timedelta(hours=2)
    scenarios: list[tuple[str, list[dict[str, str]], str | None, str | None, bool]] = []

    for index in range(10):
        scenarios.append(
            (
                "tighten this up",
                [
                    _epic(f"old_{index}_{offset}", f"Old {index} {offset}", old)
                    for offset in range(4)
                ] + [_epic(f"hot_{index}", f"Hot {index}", recent - timedelta(minutes=index))],
                None,
                f"hot_{index}",
                False,
            )
        )
    for index in range(10):
        scenarios.append(
            (
                f"please switch to Focus {index}",
                [
                    _epic(f"focus_{index}", f"Focus {index}", old),
                    _epic(f"recent_{index}", f"Recent {index}", recent),
                ],
                None,
                f"focus_{index}",
                False,
            )
        )
    for index in range(5):
        scenarios.append(
            (
                "tighten this up",
                [
                    _epic(f"a_{index}", f"Alpha {index}", recent),
                    _epic(f"b_{index}", f"Beta {index}", recent - timedelta(minutes=5)),
                ],
                None,
                None,
                True,
            )
        )
    for index in range(5):
        scenarios.append(
            (
                "help",
                [_epic(f"meta_{index}", f"Meta {index}", recent)],
                f"meta_{index}",
                f"meta_{index}",
                False,
            )
        )

    correct = 0
    for message, epics, previous_epic_id, expected_epic_id, expected_clarify in scenarios:
        decision = select_epic_for_message(
            message,
            epics,
            previous_epic_id=previous_epic_id,
            now=now,
        )
        if decision.epic_id == expected_epic_id and decision.needs_clarification is expected_clarify:
            correct += 1

    assert len(scenarios) == 30
    assert correct >= 27


def test_ambiguity_eval_asks_instead_of_guessing_on_ten_scenarios() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    scenarios = [
        [_epic(f"multi_{index}_a", f"Multi {index} A", now - timedelta(hours=1)),
         _epic(f"multi_{index}_b", f"Multi {index} B", now - timedelta(hours=2))]
        for index in range(5)
    ] + [
        [_epic(f"stale_{index}_a", f"Stale {index} A", now - timedelta(days=3)),
         _epic(f"stale_{index}_b", f"Stale {index} B", now - timedelta(days=4))]
        for index in range(5)
    ]

    decisions = [
        select_epic_for_message("tighten this up", epics, now=now)
        for epics in scenarios
    ]

    assert len(decisions) == 10
    assert all(decision.epic_id is None and decision.needs_clarification for decision in decisions)


def test_read_tools_use_store_methods(tmp_path) -> None:
    store, _conn = create_store(tmp_path / "arnold.db")
    turn = store.create_turn(epic_id=None, triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])
    store.create_message(
        epic_id=None,
        direction="inbound",
        content="Find durable message search",
        discord_message_id="discord_search",
    )

    invocation = registry.invoke(
        "search_messages",
        context,
        {"query": "durable message", "limit": 5},
    )

    assert invocation.result["messages"][0]["id"].startswith("msg_")


def test_search_messages_tool_is_store_portable() -> None:
    class StoreSpy:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def transaction(self) -> object:
            return self

        def __enter__(self) -> "StoreSpy":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def search_messages(
            self,
            *,
            query: str,
            epic_id: str | None = None,
            limit: int = 20,
        ) -> list[dict[str, object]]:
            self.calls.append({"query": query, "epic_id": epic_id, "limit": limit})
            return [
                {
                    "id": "msg_spy",
                    "epic_id": epic_id,
                    "direction": "inbound",
                    "snippet": "portable search",
                    "rank": 1,
                }
            ]

        def record_tool_call(self, **_kwargs: object) -> dict[str, object]:
            return {"id": "tc_spy", "tool_name": "search_messages"}

    store = StoreSpy()
    context = ToolContext(store=store, turn_id="turn_spy", events=[])  # type: ignore[arg-type]

    invocation = registry.invoke(
        "search_messages",
        context,
        {"query": "portable", "epic_id": "epic_spy", "limit": 3},
    )

    assert store.calls == [{"query": "portable", "epic_id": "epic_spy", "limit": 3}]
    assert invocation.result["messages"][0]["id"] == "msg_spy"


def test_get_self_understanding_returns_all_seven_sections(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    store.seed_checklist("epic_1", ["Keep search scoped"])

    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])
    result = registry.invoke("get_self_understanding", context, {"epic_id": "epic_1"}).result

    assert {
        "goal_and_current_state",
        "active_checklist_items",
        "principles_captured",
        "recent_decisions",
        "code_references",
        "recent_images",
        "recent_second_opinion_findings",
    } <= set(result)


def test_run_turn_passes_policy_and_resolved_reference(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    store.create_message(
        epic_id="epic_1",
        direction="outbound",
        content="1. Alpha\n2. Beta",
        discord_message_id="discord_out_1",
    )
    envelope = agent_kit.loop.run_turn(
        epic_id="epic_1",
        input="the second one",
        store=store,
        model=FakeModel(script=[{"final_text": "ok", "provider_request_id": "req_1"}]),
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    prompt_snapshot = json.loads(
        conn.execute("SELECT request_summary FROM external_requests WHERE provider = 'anthropic'").fetchone()[0]
    )
    assert prompt_snapshot["hot_context"]["recent_message_count"] >= 1


def test_resident_reassigns_inbound_before_dispatch_and_announces_switch(tmp_path) -> None:
    async def scenario() -> None:
        store, conn = create_store(tmp_path / "arnold.db")
        now = datetime.now(UTC)
        insert_epic(conn, "epic_old")
        insert_epic(conn, "epic_new")
        conn.execute(
            "UPDATE epics SET title = ?, last_edited_at = ? WHERE id = ?",
            ("Old", (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"), "epic_old"),
        )
        conn.execute(
            "UPDATE epics SET title = ?, last_edited_at = ? WHERE id = ?",
            ("New", (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "epic_new"),
        )
        conn.commit()
        message = store.create_message(
            epic_id="epic_old",
            direction="inbound",
            content="tighten this",
            discord_message_id="discord_in_1",
        )
        followup = store.create_message(
            epic_id="epic_old",
            direction="inbound",
            content="and keep the search notes",
            discord_message_id="discord_in_2",
        )
        transport = FakePushTransport()
        runner = ResidentRunner(
            store=store,
            model=FakeModel(script=[{"final_text": "done", "provider_request_id": "req_1"}]),
            model_id="fake",
            transport=transport,
            blob=None,
            ledger=Ledger(store),
            reconciler=Reconciler(store),
        )
        runner.previous_epic_by_channel["channel_1"] = "epic_old"

        runner.handle_transport_message(
            {
                "epic_id": "epic_old",
                "message_id": message["id"],
                "message_ids": [message["id"], followup["id"]],
                "channel_id": "channel_1",
            }
        )
        await asyncio.sleep(0)

        row = store.load_message(message["id"])
        assert row and row["epic_id"] == "epic_new"
        followup_row = store.load_message(followup["id"])
        assert followup_row and followup_row["epic_id"] == "epic_new"
        assert runner.coalescer._bursts["epic_new"].message_ids == [message["id"], followup["id"]]
        assert any("Switching to New." == post["content"] for post in transport.posts)

    asyncio.run(scenario())


def _epic(epic_id: str, title: str, edited: datetime) -> dict[str, str]:
    return {
        "id": epic_id,
        "title": title,
        "state": "shaping",
        "last_edited_at": edited.isoformat().replace("+00:00", "Z"),
    }
