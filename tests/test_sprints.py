from __future__ import annotations

from agent_kit.gating import scan_lockdown_phrases
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from agent_kit.sprints import is_lock_in_confirmation
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.editorial  # noqa: F401
import agent_kit.tools.editorial_reads  # noqa: F401


def _body(extra: str = "") -> str:
    filler = " ".join(["handoff detail"] * 45)
    return f"""# Sprint Epic

## Goal

Ship sprint mode with deterministic lifecycle gates and clear PM handoff behavior.

## Key Decisions

State transitions are enforced server-side. {extra}

## Open Questions

None.

## Deliverable

A planned epic with queued or pending sprints, audit history, replay, and envelope deltas. {filler}
"""


def _context(tmp_path, *, state: str = "shaping", body_text: str | None = None):
    store = SQLiteStore(tmp_path / "sprints.db")
    epic = store.create_epic(
        title="Sprint Epic",
        goal="Ship sprint mode",
        body=body_text or _body(),
        state=state,
    )
    items = store.seed_checklist(epic["id"], ["Clarify", "Decide", "Sequence"])
    for item in items:
        store.update_checklist_item(item["id"], status="done")
    turn = store.create_turn(epic_id=epic["id"], triggered_by_message_ids=[])
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"epic_id": epic["id"]},
    )
    return store, epic, context


def _sprint_replace_payload():
    return {
        "replace": [
            {
                "sprint_number": 1,
                "name": "Lifecycle Gate",
                "goal": "Implement state gate enforcement.",
                "items": [
                    {
                        "content": "Wire edit_epic state advancement to deterministic gates.",
                        "estimated_complexity": "medium",
                        "source_section": "Deliverable",
                    }
                ],
            },
            {
                "sprint_number": 2,
                "name": "Visibility",
                "goal": "Expose sprint state in read paths.",
                "items": [
                    {
                        "content": "Return sprint rows from get_epic and time travel replay.",
                        "estimated_complexity": "small",
                        "source_section": "Deliverable",
                    }
                ],
            },
        ]
    }


def test_shaping_to_sprinting_gate_blocks_short_body_and_force_logs(tmp_path) -> None:
    store, epic, context = _context(
        tmp_path,
        body_text="# Short\n\n## Goal\n\nTiny\n\n## Deliverable\n\nTiny\n",
    )

    blocked = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"state": {"target": "sprinting"}},
            "change_summary": "advance",
        },
    ).result
    assert blocked["error"] == "state_transition_blocked"
    assert any(item["code"] == "body_too_short" for item in blocked["blockers"])
    assert store.load_epic(epic["id"])["state"] == "shaping"

    forced = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"state": {"target": "sprinting"}},
            "change_summary": "force advance",
            "force": True,
        },
    ).result
    assert forced["state_transition"]["forced"] is True
    assert store.load_epic(epic["id"])["state"] == "sprinting"
    assert [
        event["event_type"]
        for event in store.list_epic_events(epic["id"], kinds=["forced_handoff"])
    ] == ["forced_handoff"]


def test_state_gate_second_opinion_advisory_is_default_on_with_decline(tmp_path) -> None:
    store, epic, context = _context(tmp_path)

    advanced = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"state": {"target": "sprinting"}},
            "change_summary": "advance to sprinting",
        },
    ).result
    advisory = advanced["second_opinion_advisory"]
    assert advisory["status"] == "recommended"
    assert advisory["default_on"] is True
    assert advisory["tool"]["name"] == "request_second_opinion"
    assert advisory["tool"]["arguments"]["requested_by"] == "auto_state_gate"

    declined_dir = tmp_path / "declined"
    declined_dir.mkdir()
    declined_store, declined_epic, declined_context = _context(declined_dir)
    declined_context.metadata["user_message"] = "advance, skip second opinion until I ask"
    declined = registry.invoke(
        "edit_epic",
        declined_context,
        {
            "epic_id": declined_epic["id"],
            "changes": {"state": {"target": "sprinting"}},
            "change_summary": "advance to sprinting",
        },
    ).result
    assert declined_store.load_epic(declined_epic["id"])["state"] == "sprinting"
    assert declined["second_opinion_advisory"] == {
        "status": "declined",
        "reason": "user_declined",
        "decline_phrase": "skip second opinion until I ask",
    }


def test_sprint_lock_in_advances_to_planned_and_read_paths_include_sprints(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")

    shaped = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": _sprint_replace_payload()},
            "change_summary": "shape sprints",
        },
    ).result
    assert shaped["sprint_changes"] == [{"kind": "replace", "count": 2}]

    planned = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "sprints": {"lock_in": True},
                "state": {"target": "planned"},
            },
            "change_summary": "lock in",
        },
    ).result
    assert planned["state_transition"]["to"] == "planned"
    loaded = store.list_sprints_with_items(epic["id"])
    assert [(row["status"], row["queue_position"], row["pending_reason"]) for row in loaded] == [
        ("queued", 1, None),
        ("pending", None, "no reason given"),
    ]
    assert store.load_epic(epic["id"])["planned_at"] is not None

    current = registry.invoke("get_epic", context, {"epic_id": epic["id"]}).result
    assert len(current["sprints"]) == 2
    sprint_alias = registry.invoke("get_sprints", context, {"epic_id": epic["id"]}).result
    assert sprint_alias["epic_id"] == epic["id"]
    assert [row["name"] for row in sprint_alias["sprints"]] == [
        "Lifecycle Gate",
        "Visibility",
    ]
    assert registry.get("get_sprints").operation_kind == "read"
    historical = registry.invoke(
        "get_epic_at_time",
        context,
        {"epic_id": epic["id"], "timestamp": "1900-01-01T00:00:00Z"},
    ).result
    assert historical["sprints"] == []


def test_queue_and_reorder_keep_gapless_positions_and_revert_restores(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")
    registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "sprints": {**_sprint_replace_payload(), "lock_in": True},
                "state": {"target": "planned"},
            },
            "change_summary": "plan",
        },
    )

    queued = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": {"queue": {"sprint_number": 2}}},
            "change_summary": "queue sprint 2",
        },
    ).result
    assert queued["sprint_changes"][0]["kind"] == "queue"
    assert [
        (row["sprint_number"], row["queue_position"])
        for row in store.list_sprints(epic["id"])
        if row["status"] == "queued"
    ] == [(1, 1), (2, 2)]

    registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": {"reorder": [2, 1]}},
            "change_summary": "do sprint 2 first",
        },
    )
    assert [
        (row["sprint_number"], row["queue_position"])
        for row in store.list_sprints(epic["id"])
        if row["status"] == "queued"
    ] == [(1, 2), (2, 1)]
    assert store.list_epic_events(epic["id"], kinds=["sprint_status_change"])

    registry.invoke("revert", context, {"epic_id": epic["id"]})
    assert [
        (row["sprint_number"], row["queue_position"])
        for row in store.list_sprints(epic["id"])
        if row["status"] == "queued"
    ] == [(1, 1), (2, 2)]


def test_duplicate_sprint_numbers_are_rejected_before_writes(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")
    payload = _sprint_replace_payload()
    payload["replace"][1]["sprint_number"] = 1

    result = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": payload},
            "change_summary": "shape duplicate sprints",
        },
    ).result

    assert result["error"] == "invalid_sprints"
    assert result["blockers"][0]["field"] == "replace"
    assert store.list_sprints(epic["id"]) == []


def test_duplicate_reorder_numbers_are_rejected_without_mutation(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")
    registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "sprints": {**_sprint_replace_payload(), "lock_in": True},
                "state": {"target": "planned"},
            },
            "change_summary": "plan",
        },
    )

    result = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": {"reorder": [2, 2, 1]}},
            "change_summary": "bad reorder",
        },
    ).result

    assert result["error"] == "invalid_sprints"
    assert result["blockers"][0]["field"] == "reorder"
    assert [
        (row["sprint_number"], row["status"], row["queue_position"])
        for row in store.list_sprints(epic["id"])
    ] == [(1, "queued", 1), (2, "pending", None)]


def test_lock_in_rejects_unknown_and_conflicting_assignments_before_mutation(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")
    registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": _sprint_replace_payload()},
            "change_summary": "shape",
        },
    )

    unknown = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {"sprints": {"lock_in": {"queued": [99]}}},
            "change_summary": "bad lock in",
        },
    ).result
    assert unknown["error"] == "invalid_sprints"
    assert unknown["blockers"][0]["field"] == "lock_in"

    conflict = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": epic["id"],
            "changes": {
                "sprints": {
                    "lock_in": {
                        "queued": [1],
                        "pending": [{"sprint_number": 1, "pending_reason": "later"}],
                    }
                }
            },
            "change_summary": "conflicting lock in",
        },
    ).result
    assert conflict["error"] == "invalid_sprints"
    assert conflict["blockers"][0]["field"] == "lock_in"
    assert [
        (row["sprint_number"], row["status"], row["queue_position"], row["pending_reason"])
        for row in store.list_sprints(epic["id"])
    ] == [
        (1, "proposed", None, None),
        (2, "proposed", None, None),
    ]


def test_lock_in_confirmation_parser_is_deterministic() -> None:
    assert is_lock_in_confirmation("Yes.")
    assert is_lock_in_confirmation("lock it in")
    assert is_lock_in_confirmation("That works!")
    assert not is_lock_in_confirmation("maybe after one more pass")
    assert not is_lock_in_confirmation("yes, but queue sprint two first")


def test_lockdown_scan_blocks_outside_open_questions_and_ignores_fences() -> None:
    blockers = scan_lockdown_phrases(_body("Auth provider TBD."))
    assert blockers[0]["phrase"] == "TBD"
    assert blockers[0]["section"] == "Key Decisions"

    allowed = scan_lockdown_phrases(_body().replace("None.", "Auth provider TBD."))
    assert allowed == []

    fenced = scan_lockdown_phrases(_body("\n```text\nTBD\n```"))
    assert fenced == []


def test_invocation_envelope_reports_state_and_sprint_deltas(tmp_path) -> None:
    store, epic, context = _context(tmp_path, state="sprinting")
    envelope = run_turn(
        epic_id=epic["id"],
        input="shape and plan",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "edit_epic",
                            "arguments": {
                                "epic_id": epic["id"],
                                "changes": {
                                    "sprints": {**_sprint_replace_payload(), "lock_in": True},
                                    "state": {"target": "planned"},
                                },
                                "change_summary": "plan",
                            },
                        }
                    ],
                    "provider_request_id": "req_1",
                },
                {"final_text": "Planned.", "provider_request_id": "req_2"},
            ]
        ),
        model_id="fake",
    )

    assert envelope.epic_state_before == "sprinting"
    assert envelope.epic_state_after == "planned"
    assert envelope.state_delta.state_transition["to"] == "planned"
    assert {change["kind"] for change in envelope.state_delta.sprint_changes} == {
        "replace",
        "lock_in",
    }
