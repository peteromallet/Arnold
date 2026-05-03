from __future__ import annotations

from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.feedback  # noqa: F401


def _store_and_context(tmp_path):
    store = SQLiteStore(tmp_path / "feedback_tools.db")
    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial goal",
        body="# Editorial Title\n\n## Goal\n\nEditorial goal\n",
    )
    inbound = store.create_message(
        epic_id=epic["id"],
        direction="inbound",
        content="save this: keep replies short",
        discord_message_id="msg_1",
    )
    turn = store.create_turn(
        epic_id=epic["id"],
        triggered_by_message_ids=[inbound["id"]],
    )
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={
            "epic_id": epic["id"],
            "inbound_message_id": inbound["id"],
            "user_message": inbound["content"],
        },
    )
    return store, epic, context


def test_feedback_tools_validate_and_update_feedback_lifecycle(tmp_path) -> None:
    store, _epic, context = _store_and_context(tmp_path)

    assert registry.get("list_feedback").operation_kind == "read"

    invalid_kind = registry.invoke(
        "save_feedback",
        context,
        {"kind": "friction", "content": "Bad mix."},
    ).result
    assert invalid_kind["error"] == "invalid_feedback_kind"

    invalid_source = registry.invoke(
        "save_feedback",
        context,
        {
            "kind": "style",
            "content": "Use short replies.",
            "source": "agent_observation",
        },
    ).result
    assert invalid_source["error"] == "invalid_feedback_source"

    saved = registry.invoke(
        "save_feedback",
        context,
        {
            "kind": "style",
            "content": "Use short replies.",
            "source": "explicit_save_request",
        },
    ).result["feedback"]
    assert saved["source"] == "explicit_save_request"
    assert saved["turn_id"] == context.turn_id
    assert saved["source_message_id"] == context.metadata["inbound_message_id"]
    assert saved["context_snapshot"]["user_message"] == context.metadata["user_message"]

    listed = registry.invoke(
        "list_feedback",
        context,
        {"kinds": ["style"], "active": True},
    ).result["feedback"]
    assert [row["id"] for row in listed] == [saved["id"]]
    assert store.load_feedback(saved["id"])["last_referenced_at"] is not None

    applied = registry.invoke(
        "apply_feedback",
        context,
        {"feedback_id": saved["id"]},
    ).result["feedback"]
    assert applied["last_applied_at"] is not None
    assert applied["last_referenced_at"] is not None

    deactivated = registry.invoke(
        "deactivate_feedback",
        context,
        {"feedback_id": saved["id"], "reason": "superseded"},
    ).result["feedback"]
    assert deactivated["active"] in (False, 0)
    assert deactivated["deactivation_reason"] == "superseded"
    assert store.load_hot_context(None)["active_feedback"] == []


def test_observation_tools_autofill_resolve_and_leave_hot_context(tmp_path) -> None:
    store, epic, context = _store_and_context(tmp_path)

    assert registry.get("list_observations").operation_kind == "read"

    invalid_kind = registry.invoke(
        "record_observation",
        context,
        {"kind": "style", "content": "Wrong group."},
    ).result
    assert invalid_kind["error"] == "invalid_observation_kind"

    observation = registry.invoke(
        "record_observation",
        context,
        {
            "kind": "friction",
            "content": "User had to repeat the target section.",
            "bot_action_being_critiqued": "missed the section",
        },
    ).result["observation"]
    assert observation["source"] == "agent_observation"
    assert observation["turn_id"] == context.turn_id
    assert observation["epic_id"] == epic["id"]
    assert observation["context_snapshot"] == {
        "user_message": context.metadata["user_message"],
        "bot_action_being_critiqued": "missed the section",
    }
    assert [
        row["id"]
        for row in store.load_hot_context(epic["id"])["unresolved_observations"]
    ] == [observation["id"]]

    feedback = registry.invoke(
        "save_feedback",
        context,
        {"kind": "style", "content": "Keep replies clipped."},
    ).result["feedback"]
    invalid_resolution = registry.invoke(
        "mark_observation_resolved",
        context,
        {"feedback_id": feedback["id"], "resolution_note": "wrong row"},
    ).result
    assert invalid_resolution["error"] == "invalid_observation_kind"

    listed = registry.invoke(
        "list_observations",
        context,
        {"resolved": False},
    ).result["observations"]
    assert [row["id"] for row in listed] == [observation["id"]]
    assert store.load_feedback(observation["id"])["last_referenced_at"] is not None

    resolved = registry.invoke(
        "mark_observation_resolved",
        context,
        {
            "feedback_id": observation["id"],
            "resolution_note": "user clarified",
        },
    ).result["observation"]
    assert resolved["resolved"] in (True, 1)
    assert resolved["resolution_note"] == "user clarified"
    assert resolved["resolved_at"] is not None
    assert store.load_hot_context(epic["id"])["unresolved_observations"] == []
