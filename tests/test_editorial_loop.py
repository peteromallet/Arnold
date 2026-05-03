from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from jsonschema import validate

from agent_kit import body
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
from tests.helpers import env_with_fake_model


DEFAULT_SECTIONS = [
    "Goal",
    "Principles",
    "Context",
    "Key Decisions",
    "Open Questions",
    "Deliverable",
]


def test_editorial_loop_acceptance_criteria(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "editorial.db")

    first = _run_scripted_turn(
        store,
        epic_id=None,
        input_text="Make me an auth flow design epic",
        script=[
            {
                "tool_requests": [
                    _tool(
                        "create_epic",
                        {
                            "title": "Auth flow design",
                            "goal": "Decide on auth provider and token storage",
                        },
                    )
                ],
                "provider_request_id": "req_1",
            },
            {"final_text": "Created the design epic.", "provider_request_id": "req_2"},
        ],
    )
    epic_id = first.epic_id
    assert first.outcome == "completed"
    assert epic_id is not None

    inbound = store._conn.execute(
        "SELECT * FROM messages WHERE direction = 'inbound'"
    ).fetchone()
    turn_one = store._conn.execute(
        "SELECT * FROM bot_turns WHERE id = ?",
        (first.turn_id,),
    ).fetchone()
    assert inbound["epic_id"] == epic_id
    assert turn_one["epic_id"] == epic_id

    created_epic = store.load_epic(epic_id)
    assert created_epic is not None
    created_body = str(created_epic["body"])
    created_checklist = store.list_checklist_items(epic_id)
    assert created_epic["title"] == "Auth flow design"
    assert created_epic["goal"] == "Decide on auth provider and token storage"
    assert _section_names(created_body) == DEFAULT_SECTIONS
    assert len(created_checklist) == 18
    assert {item["source"] for item in created_checklist} == {"default_seed"}
    assert {item["status"] for item in created_checklist} == {"open"}

    created_events = store.list_epic_events(epic_id, kinds=["created"])
    assert len(created_events) == 1
    assert created_events[0]["prior_state"]["body"] == created_body
    assert len(created_events[0]["prior_state"]["checklist"]) == 18

    body_before_turn_2 = created_body
    expected_title_body = body.serialize(
        body.replace_section(
            body.parse(body_before_turn_2),
            "_preamble",
            "# Auth flow architecture\n\n",
        )
    )
    _run_scripted_turn(
        store,
        epic_id=epic_id,
        input_text="Tighten the title.",
        script=[
            {
                "tool_requests": [
                    _tool(
                        "edit_epic",
                        {
                            "epic_id": epic_id,
                            "changes": {
                                "body": {
                                    "sections": {
                                        "Goal": "\nThis should be refused by expected_diff.\n",
                                    }
                                }
                            },
                            "change_summary": "Refused mismatched diff",
                            "expected_diff": "--- wrong\n+++ wrong\n",
                        },
                    ),
                    _tool(
                        "edit_epic",
                        {
                            "epic_id": epic_id,
                            "changes": {
                                "body": {
                                    "sections": {
                                        "_preamble": "# Auth flow architecture\n\n",
                                    }
                                }
                            },
                            "change_summary": "Retitle epic",
                        },
                    ),
                ],
                "provider_request_id": "req_3",
            },
            {"final_text": "Title updated.", "provider_request_id": "req_4"},
        ],
    )
    body_after_turn_2 = str(store.load_epic(epic_id)["body"])
    assert body_after_turn_2 == expected_title_body
    assert store.load_epic(epic_id)["title"] == "Auth flow architecture"
    assert _tool_result_errors(store, "edit_epic").count("expected_diff_mismatch") == 1

    title_event = _event_by_summary(store, epic_id, "Retitle epic")
    assert title_event["prior_state"]["title"] == "Auth flow design"

    section_updates = [
        ("Goal", "\nDecide on OAuth provider, session lifetime, and token storage.\n"),
        ("Principles", "\n- Prefer boring defaults.\n- Keep tokens out of localStorage.\n"),
        ("Context", "\nThe app needs a sign-in flow for web and API access.\n"),
        ("Key Decisions", "\n- Use hosted OAuth.\n- Store refresh tokens server-side.\n"),
        ("Open Questions", "\n- Confirm enterprise SSO timing.\n"),
        ("Deliverable", "\nA reviewed design document and implementation checklist.\n"),
    ]
    after_turn_5_timestamp = ""
    after_turn_5_body = ""
    after_turn_5_checklist: list[dict[str, Any]] = []
    goal_before = ""
    goal_after = ""

    for turn_index, (section_name, content) in enumerate(section_updates, start=3):
        before = str(store.load_epic(epic_id)["body"])
        arguments: dict[str, Any] = {
            "epic_id": epic_id,
            "changes": {"body": {"sections": {section_name: content}}},
            "change_summary": f"Update {section_name} section",
        }
        if section_name == "Goal":
            expected_body = body.serialize(
                body.replace_section(body.parse(before), section_name, content)
            )
            arguments["expected_diff"] = body.compute_diff(before, expected_body)
            goal_before = before

        _run_scripted_turn(
            store,
            epic_id=epic_id,
            input_text=f"Update {section_name}.",
            script=[
                {
                    "tool_requests": [_tool("edit_epic", arguments)],
                    "provider_request_id": f"req_{turn_index}_a",
                },
                {
                    "final_text": f"{section_name} updated.",
                    "provider_request_id": f"req_{turn_index}_b",
                },
            ],
        )
        if section_name == "Goal":
            goal_after = str(store.load_epic(epic_id)["body"])
        if turn_index == 5:
            after_turn_5_timestamp = store.list_epic_events(epic_id)[-1]["occurred_at"]
            after_turn_5_body = str(store.load_epic(epic_id)["body"])
            after_turn_5_checklist = store.list_checklist_items(epic_id)

    goal_event = _event_by_summary(store, epic_id, "Update Goal section")
    assert goal_event["prior_state"]["body"] == goal_before
    before_sections = _raw_sections(goal_before)
    after_sections = _raw_sections(goal_after)
    for section_name in DEFAULT_SECTIONS:
        if section_name != "Goal":
            assert after_sections[section_name] == before_sections[section_name]

    assert _section_names(str(store.load_epic(epic_id)["body"])) == DEFAULT_SECTIONS

    checklist_ids = [item["id"] for item in store.list_checklist_items(epic_id)[:3]]
    body_before_append = str(store.load_epic(epic_id)["body"])
    _run_scripted_turn(
        store,
        epic_id=epic_id,
        input_text="Add implementation context and mark checklist progress.",
        script=[
            {
                "tool_requests": [
                    _tool(
                        "edit_epic",
                        {
                            "epic_id": epic_id,
                            "changes": {
                                "body": {
                                    "append": {
                                        "Context": "\nImplementation note: align rollout with security review.\n",
                                    }
                                },
                                "checklist": {
                                    "update": [
                                        {
                                            "id": item_id,
                                            "status": "done",
                                            "completed_at": _now(),
                                        }
                                        for item_id in checklist_ids
                                    ]
                                },
                            },
                            "change_summary": "Append context and mark checklist",
                        },
                    )
                ],
                "provider_request_id": "req_9_a",
            },
            {"final_text": "Progress recorded.", "provider_request_id": "req_9_b"},
        ],
    )
    pre_revert_body = str(store.load_epic(epic_id)["body"])
    pre_revert_checklist = store.list_checklist_items(epic_id)
    assert pre_revert_body != body_before_append
    assert [item["status"] for item in pre_revert_checklist[:3]] == ["done"] * 3
    timestamp_before_revert = _now()
    _pause()

    tenth = _run_scripted_turn(
        store,
        epic_id=epic_id,
        input_text="Revert that.",
        script=[
            {
                "tool_requests": [
                    _tool("revert", {"epic_id": epic_id}),
                    _tool("send_message", {"content": "Reverted the last edit."}),
                ],
                "provider_request_id": "req_10_a",
            },
            {"final_text": "Done.", "provider_request_id": "req_10_b"},
        ],
    )
    assert tenth.reply == "Reverted the last edit."
    assert str(store.load_epic(epic_id)["body"]) == body_before_append
    assert [item["status"] for item in store.list_checklist_items(epic_id)[:3]] == [
        "open"
    ] * 3

    reverted = store.list_epic_events(epic_id, kinds=["reverted_to"])[-1]
    assert {"body", "title", "goal", "checklist"}.issubset(reverted["prior_state"])
    assert reverted["prior_state"]["body"] == pre_revert_body
    assert len(reverted["prior_state"]["checklist"]) == 18

    read_context = ToolContext(
        store=store,
        turn_id=tenth.turn_id,
        events=[],
        metadata={"epic_id": epic_id},
    )
    at_turn_5 = registry.invoke(
        "get_epic_at_time",
        read_context,
        {"epic_id": epic_id, "timestamp": after_turn_5_timestamp},
    ).result
    assert at_turn_5["body_full"] == after_turn_5_body
    assert at_turn_5["checklist"] == after_turn_5_checklist

    just_before_revert = registry.invoke(
        "get_epic_at_time",
        read_context,
        {"epic_id": epic_id, "timestamp": timestamp_before_revert},
    ).result
    assert just_before_revert["body_full"] == pre_revert_body
    assert [item["status"] for item in just_before_revert["checklist"][:3]] == [
        "done"
    ] * 3

    before_creation = registry.invoke(
        "get_epic_at_time",
        read_context,
        {"epic_id": epic_id, "timestamp": "1970-01-01T00:00:00Z"},
    ).result
    assert before_creation["body_full"] == created_body
    assert len(before_creation["checklist"]) == 18

    assert registry.invoke(
        "get_epic",
        read_context,
        {"epic_id": epic_id, "sections": ["Goal", "_preamble"]},
    ).result["section_names"] == DEFAULT_SECTIONS
    assert registry.invoke(
        "get_section_names",
        read_context,
        {"epic_id": epic_id},
    ).result["section_names"] == DEFAULT_SECTIONS
    assert registry.invoke(
        "get_history",
        read_context,
        {"epic_id": epic_id},
    ).result["events"][0]["event_type"] == "reverted_to"
    assert registry.invoke(
        "get_self_understanding",
        read_context,
        {"epic_id": epic_id},
    ).result["open_checklist_count"] == 18

    recent_turns = registry.invoke(
        "get_recent_turns",
        read_context,
        {"n": 5, "epic_id": epic_id},
    ).result["turns"]
    assert len(recent_turns) == 5
    assert [turn["started_at"] for turn in recent_turns] == sorted(
        [turn["started_at"] for turn in recent_turns],
        reverse=True,
    )
    assert any(turn["change_summary"] for turn in recent_turns)

    edit_calls = registry.invoke(
        "search_tool_calls",
        read_context,
        {"tool_name": "edit_epic", "epic_id": epic_id},
    ).result["tool_calls"]
    assert len(edit_calls) >= 3

    meta_result = registry.invoke(
        "edit_epic",
        read_context,
        {
            "epic_id": epic_id,
            "changes": {"meta": {"title": "X"}},
            "change_summary": "Unsupported meta edit",
        },
    ).result
    assert meta_result["error"] == "meta_not_supported"

    assert registry.invoke(
        "render_epic",
        read_context,
        {"epic_id": epic_id},
    ).result["body"] == str(store.load_epic(epic_id)["body"])

    _assert_tool_operation_kinds(store)
    _assert_epic_outline_logs(store, epic_id)

    whole_body_before = str(store.load_epic(epic_id)["body"])
    whole_body_after = whole_body_before + "\n## Extra Notes\n\nTemporary rewrite.\n"
    whole_edit = registry.invoke(
        "edit_epic",
        read_context,
        {
            "epic_id": epic_id,
            "changes": {"body": {"new_content": whole_body_after}},
            "change_summary": "Whole body rewrite",
        },
    ).result
    assert whole_edit["diff"]
    assert str(store.load_epic(epic_id)["body"]) == whole_body_after
    registry.invoke("revert", read_context, {"epic_id": epic_id})
    assert str(store.load_epic(epic_id)["body"]) == whole_body_before


def test_body_outline_and_search_read_tools_are_registered_and_stable() -> None:
    store = SQLiteStore(":memory:")
    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial goal",
        body=(
            "# Editorial Title\n"
            "\n"
            "## Goal\n"
            "\n"
            "Editorial goal.\n"
            "\n"
            "### Detail\n"
            "Needle appears here.\n"
        ),
    )
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    tool_names = {definition["name"] for definition in registry.definitions()}
    assert {"get_body_outline", "search_in_body"} <= tool_names

    outline = registry.invoke("get_body_outline", context, {"epic_id": epic["id"]}).result
    assert outline["epic_id"] == epic["id"]
    assert outline["outline"]["sections"][0]["name"] == "Goal"
    assert outline["outline"]["sections"][0]["line_count"] == 6
    assert outline["outline"]["sections"][0]["subheadings"][0]["name"] == "Detail"

    found = registry.invoke(
        "search_in_body",
        context,
        {"epic_id": epic["id"], "query": "needle", "context_lines": 1},
    ).result
    assert found["results"] == [
        {
            "line_number": 8,
            "line": "Needle appears here.",
            "section": "Goal",
            "subheading_path": ["Detail"],
            "context_before": [{"line_number": 7, "line": "### Detail"}],
            "context_after": [],
        }
    ]

    empty = registry.invoke(
        "search_in_body",
        context,
        {"epic_id": epic["id"], "query": "missing", "context_lines": 1},
    ).result
    assert empty == {"epic_id": epic["id"], "query": "missing", "results": []}

    missing_outline = registry.invoke(
        "get_body_outline",
        context,
        {"epic_id": "epic_missing"},
    ).result
    assert missing_outline == {"error": "epic_not_found", "epic_id": "epic_missing"}
    missing_search = registry.invoke(
        "search_in_body",
        context,
        {"epic_id": "epic_missing", "query": "needle"},
    ).result
    assert missing_search == {
        "error": "epic_not_found",
        "epic_id": "epic_missing",
        "query": "needle",
        "results": [],
    }


def test_editorial_read_aliases_return_expected_payloads(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "read-aliases.db")
    epic = _create_minimal_epic(store)
    checklist_items = store.seed_checklist(epic["id"], ["Clarify scope", "Confirm risks"])
    store.update_checklist_item(checklist_items[1]["id"], status="done")
    for index in range(12):
        store.create_message(
            epic_id=epic["id"],
            direction="inbound",
            content=f"Message {index}",
            discord_message_id=f"discord_{index}",
        )
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    for tool_name in {"get_checklist", "get_sprints", "recent_messages"}:
        assert registry.get(tool_name).operation_kind == "read"

    open_checklist = registry.invoke(
        "get_checklist",
        context,
        {"epic_id": epic["id"], "status": "open"},
    ).result
    assert open_checklist["epic_id"] == epic["id"]
    assert open_checklist["status"] == "open"
    assert [item["content"] for item in open_checklist["checklist"]] == ["Clarify scope"]

    recent = registry.invoke(
        "recent_messages",
        context,
        {"epic_id": epic["id"], "n": 11},
    ).result
    assert recent["epic_id"] == epic["id"]
    assert recent["requested_n"] == 11
    assert recent["max_available"] == 10
    assert recent["returned_n"] == 10
    assert len(recent["recent_messages"]) == 10


def test_editorial_cli_no_epic_bootstrap(tmp_path) -> None:
    script = [
        {
            "tool_requests": [
                _tool(
                    "create_epic",
                    {
                        "title": "Auth flow design",
                        "goal": "Decide on auth provider and token storage",
                    },
                )
            ],
            "provider_request_id": "cli_req_1",
        },
        {"final_text": "Created.", "provider_request_id": "cli_req_2"},
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold",
            "turn",
            "--input",
            "Make me an auth flow design epic",
            "--db",
            str(tmp_path / "cli.db"),
            "--model-id",
            "fake",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_with_fake_model(script),
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["outcome"] == "completed"
    assert envelope["epic_id"].startswith("epic_")


def test_errored_no_epic_envelope_is_schema_valid(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "error.db")
    envelope = run_turn(
        epic_id=None,
        input="Make this fail before an epic exists.",
        store=store,
        model=FakeModel(script=[{"runtime_error": "transport failed"}]),
        model_id="fake",
    )
    assert envelope.outcome == "errored"
    assert envelope.epic_id is None
    schema = json.loads(
        (Path(__file__).parents[1] / "agent_kit" / "envelope.schema.json").read_text()
    )
    validate(envelope.to_dict(), schema)


def test_edit_epic_links_confirmed_checklist_items_to_second_opinion(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "second-opinion-links.db")
    epic = _create_minimal_epic(store)
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])
    opinion = store.create_second_opinion(
        epic_id=epic["id"],
        requested_by="user",
        focus_areas=["handoff"],
        raw_response='{"score": 6}',
        score=6,
        summary="Three holes remain.",
        verdict="needs work",
        model_used="gpt-5.5",
        resulting_checklist_item_ids=["existing_item"],
    )

    result = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "checklist": {
                    "add": [
                        {
                            "content": "Define rollout guardrails",
                            "source": "second_opinion",
                            "source_second_opinion_id": opinion["id"],
                        },
                        {
                            "content": "Add owner handoff",
                            "source": "second_opinion",
                            "source_second_opinion_id": opinion["id"],
                        },
                        {
                            "content": "Unlinked follow-up",
                            "source": "bot_inferred",
                        },
                    ]
                }
            },
            "change_summary": "Confirm second opinion checklist items",
        },
    ).result

    created_ids = result["created_checklist_item_ids"]
    assert len(created_ids) == 3
    assert [item["id"] for item in result["created_checklist_items"]] == created_ids
    linked = store.list_second_opinions(epic["id"])[0]
    assert linked["id"] == opinion["id"]
    assert linked["resulting_checklist_item_ids"] == [
        "existing_item",
        created_ids[0],
        created_ids[1],
    ]


def test_edit_epic_rolls_back_checklist_add_for_unknown_second_opinion(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "second-opinion-link-rollback.db")
    epic = _create_minimal_epic(store)
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])
    context = ToolContext(store=store, turn_id=turn["id"], events=[])

    result = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "checklist": {
                    "add": [
                        {
                            "content": "Should roll back",
                            "source_second_opinion_id": "opinion_missing",
                        }
                    ]
                }
            },
            "change_summary": "Attempt invalid second opinion link",
        },
    ).result

    assert result["error"] == "source_second_opinion_not_found"
    assert store.list_checklist_items(epic["id"]) == []


def _run_scripted_turn(
    store: SQLiteStore,
    *,
    epic_id: str | None,
    input_text: str,
    script: list[dict[str, Any]],
):
    envelope = run_turn(
        epic_id=epic_id,
        input=input_text,
        store=store,
        model=FakeModel(script=script),
        model_id="fake",
    )
    assert envelope.outcome == "completed"
    _pause()
    return envelope


def _tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "arguments": arguments}


def _pause() -> None:
    time.sleep(0.01)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _create_minimal_epic(store: SQLiteStore) -> dict[str, Any]:
    return store.create_epic(
        title="Second opinion link test",
        goal="Track confirmed findings.",
        body=(
            "# Second opinion link test\n\n"
            "## Goal\n\n"
            "Track confirmed findings.\n"
        ),
    )


def _section_names(markdown: str) -> list[str]:
    return [section.name for section in body.parse(markdown).sections]


def _raw_sections(markdown: str) -> dict[str, str]:
    return {section.name: section.raw for section in body.parse(markdown).sections}


def _tool_result_errors(store: SQLiteStore, tool_name: str) -> list[str]:
    rows = store._conn.execute(
        "SELECT result FROM tool_calls WHERE tool_name = ? ORDER BY called_at, id",
        (tool_name,),
    ).fetchall()
    return [
        json.loads(row["result"]).get("error")
        for row in rows
        if json.loads(row["result"]).get("error")
    ]


def _event_by_summary(store: SQLiteStore, epic_id: str, summary: str) -> dict[str, Any]:
    matches = [
        event
        for event in store.list_epic_events(epic_id)
        if event.get("summary") == summary
    ]
    assert matches
    return matches[-1]


def _assert_tool_operation_kinds(store: SQLiteStore) -> None:
    rows = store._conn.execute(
        "SELECT tool_name, operation_kind FROM tool_calls"
    ).fetchall()
    by_tool: dict[str, set[str]] = {}
    for row in rows:
        by_tool.setdefault(row["tool_name"], set()).add(row["operation_kind"])

    for tool_name in {
        "get_epic",
        "get_section_names",
        "get_history",
        "get_self_understanding",
        "get_epic_at_time",
        "get_recent_turns",
        "search_tool_calls",
    }:
        assert by_tool[tool_name] == {"read"}

    for tool_name in {"create_epic", "edit_epic", "revert", "render_epic"}:
        assert by_tool[tool_name] == {"write"}


def _assert_epic_outline_logs(store: SQLiteStore, epic_id: str) -> None:
    rows = store._conn.execute(
        """
        SELECT * FROM system_logs
        WHERE event_type = 'epic_outline' AND epic_id = ?
        ORDER BY occurred_at, id
        """,
        (epic_id,),
    ).fetchall()
    assert len(rows) == 10
    for row in rows:
        assert row["category"] == "application"
        details = json.loads(row["details"])
        section_names = {section["name"] for section in details["sections"]}
        assert set(DEFAULT_SECTIONS).issubset(section_names)
