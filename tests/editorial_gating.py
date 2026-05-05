from __future__ import annotations

import pytest

from megaplan.editorial.gating import evaluate_state_transition, transition_epic_state
from megaplan.editorial.lockdown import ensure_unlocked_for_edit, scan_lockdown_phrases
from megaplan.editorial.errors import EditorialWorkflowError
from megaplan.store import ChecklistItemInput, RevisionConflict, SprintItemInput


def _body(*, lockdown_phrase: str | None = None) -> str:
    filler = "This paragraph fixes scope, tradeoffs, implementation notes, and review expectations. " * 8
    phrase = f"\n{lockdown_phrase}\n" if lockdown_phrase else ""
    return "\n".join(
        [
            "# Goal",
            "Ship the editorial transplant with Store-backed behavior.",
            "",
            "# Key Decisions",
            filler,
            phrase,
            "# Deliverable",
            "A deterministic Python API with persisted events and gates.",
        ]
    )


def test_transition_shaping_to_sprinting_records_state_change_event(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Editorial", goal="Port Arnold", body=_body())
    store.add_checklist_items(
        epic.id,
        [
            ChecklistItemInput(content="Done", status="done"),
            ChecklistItemInput(content="Open"),
            ChecklistItemInput(content="Skipped", status="skipped", skip_reason="not needed"),
        ],
    )

    updated = transition_epic_state(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        target_state="sprinting",
        expected_revision=epic.revision,
        turn_id="turn-1",
    )

    assert updated.state == "sprinting"
    events = store.list_epic_events(epic.id)
    assert [event.event_type for event in events] == ["state_change"]
    assert events[0].prior_state is not None
    assert events[0].prior_state["epic"]["state"] == "shaping"
    assert events[0].pre_state["epic"]["state"] == "shaping"
    assert events[0].post_state["epic"]["state"] == "sprinting"
    assert events[0].post_state_canonical_json is not None
    assert events[0].post_state_sha256 is not None
    assert events[0].turn_id == "turn-1"


def test_transition_blocks_missing_prerequisites_and_invalid_transitions(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Editorial", goal="Port Arnold", body="# Goal\nToo short")

    with pytest.raises(EditorialWorkflowError, match="Transition blocked") as exc_info:
        transition_epic_state(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            target_state="sprinting",
            expected_revision=epic.revision,
        )
    assert "Deliverable" in str(exc_info.value.details["blockers"])

    epic = store.update_epic(epic.id, expected_revision=epic.revision, body=_body())
    with pytest.raises(EditorialWorkflowError, match="Transition blocked") as invalid:
        transition_epic_state(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            target_state="planned",
            expected_revision=epic.revision,
        )
    assert "Unsupported transition: shaping -> planned" in invalid.value.details["blockers"]


def test_transition_rejects_stale_revisions(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Editorial", goal="Port Arnold", body=_body())
    store.update_epic(epic.id, expected_revision=epic.revision, title="Updated")

    with pytest.raises(RevisionConflict):
        transition_epic_state(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            target_state="sprinting",
            expected_revision=epic.revision,
        )


def test_transition_blocks_paused_and_archived_sources(editorial_store) -> None:
    store = editorial_store
    for state in ("paused", "archived"):
        epic = store.create_epic(title=f"Editorial {state}", goal="Port Arnold", body=_body(), state=state)
        result = evaluate_state_transition(epic=epic, target_state="sprinting")
        assert not result.allowed
        assert any(state in blocker for blocker in result.blockers)


def test_planned_transition_enforces_lockdown_and_sprint_prerequisites(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(
        title="Editorial",
        goal="Port Arnold",
        body=_body(lockdown_phrase="TBD"),
        state="sprinting",
    )
    item = store.add_checklist_items(epic.id, [ChecklistItemInput(content="Ready")])[0]
    store.update_checklist_item(item.id, status="done")
    sprint = store.create_sprint(epic_id=epic.id, sprint_number=1, name="Sprint 1", goal="Port gates")
    store.replace_sprint_items(
        sprint.id,
        [SprintItemInput(content="Implement gates")],
    )
    store.set_sprint_queue(epic.id, [sprint.id], {})

    with pytest.raises(EditorialWorkflowError) as exc_info:
        transition_epic_state(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            target_state="planned",
            expected_revision=epic.revision,
        )
    assert "Lockdown placeholder" in str(exc_info.value.details["blockers"])

    epic = store.update_epic(epic.id, expected_revision=epic.revision, body=_body())
    planned = transition_epic_state(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        target_state="planned",
        expected_revision=epic.revision,
    )
    assert planned.state == "planned"
    assert planned.planned_at is not None


def test_lockdown_phrase_scan_ignores_code_and_open_questions() -> None:
    body = "\n".join(
        [
            "# Goal",
            "Ready text",
            "```",
            "TBD",
            "```",
            "# Open Questions",
            "to be decided",
            "# Deliverable",
            "figure out later",
        ]
    )

    findings = scan_lockdown_phrases(body)

    assert [(finding.phrase.lower(), finding.line) for finding in findings] == [("figure out later", 9)]


def test_lockdown_rejects_review_phase_mutations() -> None:
    with pytest.raises(EditorialWorkflowError, match="body_edit is locked"):
        ensure_unlocked_for_edit(epic_state="planned", operation="body_edit")
