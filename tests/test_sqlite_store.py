from __future__ import annotations

import sqlite3

import pytest

from agent_kit.store.sqlite import SQLiteStore
from tests.store_contract import run_store_contract
from tests.store_contract_v1b import run_store_contract_v1b


@pytest.fixture
def store_factory(tmp_path):
    def factory():
        path = tmp_path / "arnold.db"
        store = SQLiteStore(path)
        return store, store._conn

    return factory


def test_sqlite_store_contract(store_factory) -> None:
    run_store_contract(store_factory)


def test_sqlite_store_contract_v1b(store_factory) -> None:
    run_store_contract_v1b(store_factory)


def test_external_requests_lifecycle_and_unique_idempotency(store_factory) -> None:
    store, conn = store_factory()
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES ('epic_1', 'Title', 'Goal', '# Title', 'shaping')
        """
    )
    conn.commit()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    request = store.insert_pending(
        idempotency_key="idem_1",
        provider="anthropic",
        endpoint="POST /v1/messages",
        request_summary={"shape": "small"},
        turn_id=turn["id"],
    )
    assert request["status"] == "pending"
    confirmed = store.mark_confirmed(
        request["id"],
        provider_request_id="req_1",
        provider_response_summary={"ok": True},
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["completed_at"] is not None

    tool_call = store.record_tool_call(
        turn_id=turn["id"],
        tool_name="send_message",
        operation_kind="write",
        arguments={},
        result={},
        duration_ms=1,
    )
    failed_request = store.insert_pending(
        idempotency_key="idem_2",
        provider="discord",
        endpoint="POST /chat.send",
        request_summary={"content": "hi"},
        turn_id=turn["id"],
        tool_call_id=tool_call["id"],
    )
    failed = store.mark_failed(failed_request["id"], error_details={"code": "bad"})
    assert failed["status"] == "failed"
    assert failed["error_details"]["code"] == "bad"
    assert failed["completed_at"] is not None

    with pytest.raises(sqlite3.IntegrityError):
        store.insert_pending(
            idempotency_key="idem_2",
            provider="discord",
            endpoint="POST /chat.send",
            request_summary={},
        )


def test_sqlite_schema_columns_and_indexes(store_factory) -> None:
    _store, conn = store_factory()
    external_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(external_requests)")
    }
    assert {
        "id",
        "idempotency_key",
        "provider",
        "endpoint",
        "tool_call_id",
        "turn_id",
        "request_summary",
        "status",
        "provider_request_id",
        "provider_response_summary",
        "attempt_count",
        "first_attempted_at",
        "last_attempted_at",
        "completed_at",
        "error_details",
    } <= external_cols

    message_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    assert {
        "has_code_attachment",
        "has_image_attachment",
        "bot_turn_id",
        "discord_message_id",
    } <= message_cols
    turn_cols = {row[1] for row in conn.execute("PRAGMA table_info(bot_turns)")}
    assert {"status_message_id", "current_activity"} <= turn_cols

    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    assert {
        "idx_external_requests_idempotency_key",
        "idx_external_requests_provider_status_last_attempted",
        "idx_external_requests_status_last_attempted",
        "idx_external_requests_turn_id",
        "idx_external_requests_tool_call_id",
        "idx_messages_epic_sent_at",
        "idx_tool_calls_turn_id",
    } <= indexes


def test_sqlite_feedback_schema_columns_constraints_and_indexes(store_factory) -> None:
    _store, conn = store_factory()

    feedback_cols = {
        row[1]: {
            "type": row[2],
            "not_null": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in conn.execute("PRAGMA table_info(feedback)")
    }
    assert {
        "id",
        "kind",
        "content",
        "source",
        "source_message_id",
        "epic_id",
        "turn_id",
        "context_snapshot",
        "active",
        "deactivation_reason",
        "resolved",
        "resolution_note",
        "resolved_at",
        "created_at",
        "last_referenced_at",
        "last_applied_at",
    } <= set(feedback_cols)
    assert feedback_cols["id"]["pk"] is True
    assert feedback_cols["kind"]["not_null"] is True
    assert feedback_cols["source"]["not_null"] is True
    assert feedback_cols["active"]["default"] == "1"
    assert feedback_cols["resolved"]["default"] == "0"

    conn.execute(
        """
        INSERT INTO feedback (id, kind, content, source, context_snapshot)
        VALUES ('fb_style', 'style', 'Use short replies.', 'explicit_save_request', '{"ok": true}')
        """
    )
    conn.execute(
        """
        INSERT INTO feedback (id, kind, content, source)
        VALUES ('fb_observation', 'friction', 'Repeated failed search.', 'agent_observation')
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO feedback (id, kind, content, source)
            VALUES ('fb_bad', 'friction', 'Bad mix.', 'explicit_save_request')
            """
        )

    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    assert {
        "idx_feedback_active_global_kind_created",
        "idx_feedback_epic_active_kind_created",
        "idx_feedback_unresolved_observations_created",
    } <= indexes


def test_sqlite_feedback_observation_persistence_and_hot_context(store_factory) -> None:
    store, _conn = store_factory()
    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial goal",
        body="# Editorial Title\n\n## Goal\n\nEditorial goal\n",
    )
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])

    style = store.create_feedback(
        kind="style",
        content="Keep responses clipped.",
        source="explicit_save_request",
        context_snapshot={"user_message": "save this", "bot_action_being_critiqued": None},
    )
    process = store.create_feedback(
        kind="process",
        content="Search before editing.",
        source="user_volunteered",
    )
    epic_specific = store.create_feedback(
        kind="epic_specific",
        content="Use the launch terminology.",
        source="user_volunteered",
        epic_id=epic["id"],
    )
    inactive = store.create_feedback(
        kind="style",
        content="Inactive style.",
        source="explicit_save_request",
    )
    store.update_feedback(inactive["id"], active=False, deactivation_reason="superseded")
    observation = store.create_feedback(
        kind="friction",
        content="User had to repeat target section.",
        source="agent_observation",
        turn_id=turn["id"],
        epic_id=epic["id"],
        context_snapshot={"user_message": "change X", "bot_action_being_critiqued": "missed"},
    )

    loaded = store.load_feedback(style["id"])
    assert loaded["context_snapshot"]["user_message"] == "save this"
    applied = store.update_feedback(style["id"], last_applied_at="2026-04-30T12:00:00.000Z")
    assert applied["last_applied_at"] == "2026-04-30T12:00:00.000Z"

    assert [row["id"] for row in store.list_feedback(active=True, kinds=["style"])] == [
        style["id"]
    ]
    hot_global = store.load_hot_context(None)
    assert hot_global["epic"] is None
    assert hot_global["recent_messages"] == []
    assert hot_global["recent_tool_calls"] == []
    assert {row["id"] for row in hot_global["active_feedback"]} == {
        style["id"],
        process["id"],
    }
    assert [row["id"] for row in hot_global["unresolved_observations"]] == [
        observation["id"]
    ]

    hot_epic = store.load_hot_context(epic["id"])
    assert hot_epic["epic"]["id"] == epic["id"]
    assert {row["id"] for row in hot_epic["active_feedback"]} == {
        style["id"],
        process["id"],
        epic_specific["id"],
    }
    assert hot_epic["unresolved_observations"][0]["context_snapshot"]["bot_action_being_critiqued"] == "missed"

    store.update_feedback(observation["id"], resolved=True, resolution_note="user clarified")
    assert store.list_observations(resolved=False) == []


def test_sqlite_hot_context_limits_recent_unresolved_observations(store_factory) -> None:
    store, conn = store_factory()
    for index in range(7):
        conn.execute(
            """
            INSERT INTO feedback (
                id, kind, content, source, resolved, active, created_at
            )
            VALUES (?, 'friction', ?, 'agent_observation', 0, 1, ?)
            """,
            (
                f"fb_obs_{index}",
                f"Observation {index}",
                f"2026-04-30T12:0{index}:00.000Z",
            ),
        )
    conn.execute(
        """
        INSERT INTO feedback (
            id, kind, content, source, resolved, active, created_at
        )
        VALUES (
            'fb_resolved',
            'friction',
            'Already resolved',
            'agent_observation',
            1,
            1,
            '2026-04-30T12:09:00.000Z'
        )
        """
    )
    conn.commit()

    hot_context = store.load_hot_context(None)

    assert [
        row["id"] for row in hot_context["unresolved_observations"]
    ] == [
        "fb_obs_6",
        "fb_obs_5",
        "fb_obs_4",
        "fb_obs_3",
        "fb_obs_2",
    ]
    assert "fb_resolved" not in {
        row["id"] for row in hot_context["unresolved_observations"]
    }
