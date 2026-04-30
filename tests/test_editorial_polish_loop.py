from __future__ import annotations

import json

from agent_kit import body
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from agent_kit.store.sqlite import SQLiteStore


def test_body_search_get_epic_edit_sequence_keeps_diff_and_scripted_show_changes(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "editorial_polish.db")
    original_body = (
        "# Searchable Epic\n"
        "\n"
        "## Goal\n"
        "\n"
        "Ship the editorial assistant.\n"
        "\n"
        "## Scope\n"
        "\n"
        "Old scope line.\n"
    )
    epic = store.create_epic(
        title="Searchable Epic",
        goal="Ship the editorial assistant.",
        body=original_body,
    )
    replacement = "\nNew scope line.\n"
    expected_body = body.serialize(
        body.replace_section(body.parse(original_body), "Scope", replacement)
    )
    expected_diff = body.compute_diff(original_body, expected_body)
    scripted_reply = (
        "Updated Scope.\n\n"
        "Show changes:\n"
        "- Old scope line.\n"
        "+ New scope line."
    )

    envelope = run_turn(
        epic_id=epic["id"],
        input="change the part about scope",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "search_in_body",
                            "arguments": {
                                "epic_id": epic["id"],
                                "query": "scope",
                                "context_lines": 1,
                            },
                        }
                    ],
                    "provider_request_id": "req_search",
                },
                {
                    "tool_requests": [
                        {
                            "name": "get_epic",
                            "arguments": {
                                "epic_id": epic["id"],
                                "sections": ["Scope"],
                            },
                        }
                    ],
                    "provider_request_id": "req_get",
                },
                {
                    "tool_requests": [
                        {
                            "name": "edit_epic",
                            "arguments": {
                                "epic_id": epic["id"],
                                "changes": {
                                    "body": {"sections": {"Scope": replacement}}
                                },
                                "change_summary": "Update Scope section",
                                "expected_diff": expected_diff,
                            },
                        }
                    ],
                    "provider_request_id": "req_edit",
                },
                {"final_text": scripted_reply, "provider_request_id": "req_final"},
            ]
        ),
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == scripted_reply
    assert str(store.load_epic(epic["id"])["body"]) == expected_body
    assert _tool_names(store) == [
        "search_in_body",
        "get_epic",
        "edit_epic",
        "send_message",
    ]

    edit_row = _tool_row(store, "edit_epic")
    edit_result = json.loads(edit_row["result"])
    assert edit_result["diff"] == expected_diff
    assert "-Old scope line." in edit_result["diff"]
    assert "+New scope line." in edit_result["diff"]

    event = store.list_epic_events(epic["id"], kinds=["body_edit"])[-1]
    assert event["summary"] == "Update Scope section"
    assert event["prior_state"]["body"] == original_body


def test_show_me_the_epic_uses_render_epic_and_scripted_reply(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "render.db")
    epic = store.create_epic(
        title="Rendered Epic",
        goal="Show the body.",
        body="# Rendered Epic\n\n## Goal\n\nShow the body.\n",
    )
    scripted_reply = "Here is the epic."

    envelope = run_turn(
        epic_id=epic["id"],
        input="Show me the epic",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "render_epic",
                            "arguments": {"epic_id": epic["id"]},
                        }
                    ],
                    "provider_request_id": "req_render",
                },
                {"final_text": scripted_reply, "provider_request_id": "req_final"},
            ]
        ),
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == scripted_reply
    assert _tool_names(store) == ["render_epic", "send_message"]
    assert json.loads(_tool_row(store, "render_epic")["result"])["body"] == epic["body"]


def test_feedback_lifecycle_hot_reload_observation_resolution_and_default_ack(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "feedback_loop.db")

    explicit = run_turn(
        epic_id=None,
        input="save this: keep messages under 200 words",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "save_feedback",
                            "arguments": {
                                "kind": "style",
                                "content": "Keep messages under 200 words.",
                                "source": "explicit_save_request",
                            },
                        }
                    ],
                    "provider_request_id": "req_explicit_save",
                },
                {"final_text": "", "provider_request_id": "req_default_ack"},
            ]
        ),
        model_id="fake",
    )
    assert explicit.reply == "Done."
    explicit_feedback = store.list_feedback(kinds=["style"])[0]
    assert explicit_feedback["source"] == "explicit_save_request"

    proposed = run_turn(
        epic_id=None,
        input="stop apologizing",
        store=store,
        model=FakeModel(
            script=[
                {
                    "final_text": "I can save that as style feedback. Reply yes to confirm.",
                    "provider_request_id": "req_propose",
                }
            ]
        ),
        model_id="fake",
    )
    assert proposed.outcome == "completed"
    assert [
        row["content"]
        for row in store.list_feedback(kinds=["style"], active=True)
    ] == ["Keep messages under 200 words."]

    confirmed = run_turn(
        epic_id=None,
        input="yes",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "save_feedback",
                            "arguments": {
                                "kind": "style",
                                "content": "Stop apologizing.",
                                "source": "agent_proposed_user_confirmed",
                            },
                        }
                    ],
                    "provider_request_id": "req_confirmed_save",
                },
                {"final_text": "Saved.", "provider_request_id": "req_saved"},
            ]
        ),
        model_id="fake",
    )
    assert confirmed.outcome == "completed"
    confirmed_feedback = [
        row
        for row in store.list_feedback(kinds=["style"])
        if row["content"] == "Stop apologizing."
    ][0]
    assert confirmed_feedback["source"] == "agent_proposed_user_confirmed"

    apply_turn = run_turn(
        epic_id=None,
        input="apply the concise-message feedback",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "apply_feedback",
                            "arguments": {"feedback_id": explicit_feedback["id"]},
                        }
                    ],
                    "provider_request_id": "req_apply",
                },
                {"final_text": "Applied.", "provider_request_id": "req_applied"},
            ]
        ),
        model_id="fake",
    )
    assert apply_turn.outcome == "completed"
    assert store.load_feedback(explicit_feedback["id"])["last_applied_at"] is not None

    reload_model = FakeModel(
        script=[{"final_text": "Loaded.", "provider_request_id": "req_reload"}]
    )
    reload_turn = run_turn(
        epic_id=None,
        input="next turn",
        store=store,
        model=reload_model,
        model_id="fake",
    )
    assert reload_turn.outcome == "completed"
    active_contents = [
        row["content"] for row in reload_model.calls[0]["hot_context"]["active_feedback"]
    ]
    assert "Keep messages under 200 words." in active_contents
    assert "Stop apologizing." in active_contents
    assert any(
        row["id"] == explicit_feedback["id"] and row["last_applied_at"] is not None
        for row in reload_model.calls[0]["hot_context"]["active_feedback"]
    )

    observation_turn = run_turn(
        epic_id=None,
        input="the section target was confusing",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "record_observation",
                            "arguments": {
                                "kind": "friction",
                                "content": "User had to clarify the target section.",
                            },
                        }
                    ],
                    "provider_request_id": "req_observe",
                },
                {"final_text": "Noted.", "provider_request_id": "req_noted"},
            ]
        ),
        model_id="fake",
    )
    assert observation_turn.outcome == "completed"
    observation = store.list_observations(resolved=False)[0]
    assert observation["turn_id"] == observation_turn.turn_id
    assert observation["context_snapshot"]["user_message"] == (
        "the section target was confusing"
    )

    observed_reload_model = FakeModel(
        script=[{"final_text": "Loaded observation.", "provider_request_id": "req_obs_reload"}]
    )
    run_turn(
        epic_id=None,
        input="reload observations",
        store=store,
        model=observed_reload_model,
        model_id="fake",
    )
    assert [
        row["id"]
        for row in observed_reload_model.calls[0]["hot_context"][
            "unresolved_observations"
        ]
    ] == [observation["id"]]

    resolve_turn = run_turn(
        epic_id=None,
        input="user clarified",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "mark_observation_resolved",
                            "arguments": {
                                "feedback_id": observation["id"],
                                "resolution_note": "user clarified",
                            },
                        }
                    ],
                    "provider_request_id": "req_resolve",
                },
                {"final_text": "Resolved.", "provider_request_id": "req_resolved"},
            ]
        ),
        model_id="fake",
    )
    assert resolve_turn.outcome == "completed"
    assert store.load_feedback(observation["id"])["resolved_at"] is not None

    resolved_reload_model = FakeModel(
        script=[{"final_text": "Loaded resolved.", "provider_request_id": "req_resolved_reload"}]
    )
    run_turn(
        epic_id=None,
        input="reload after resolution",
        store=store,
        model=resolved_reload_model,
        model_id="fake",
    )
    assert resolved_reload_model.calls[0]["hot_context"][
        "unresolved_observations"
    ] == []


def _tool_names(store: SQLiteStore) -> list[str]:
    return [
        row["tool_name"]
        for row in store._conn.execute(
            "SELECT tool_name FROM tool_calls ORDER BY rowid"
        ).fetchall()
    ]


def _tool_row(store: SQLiteStore, tool_name: str):
    row = store._conn.execute(
        "SELECT * FROM tool_calls WHERE tool_name = ? ORDER BY rowid DESC LIMIT 1",
        (tool_name,),
    ).fetchone()
    assert row is not None
    return row
