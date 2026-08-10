from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.editorial.body import edit_section, read_body, update_body
from arnold_pipelines.megaplan.editorial.errors import EditorialValidationError, EditorialWorkflowError
from arnold_pipelines.megaplan.store import RevisionConflict
from arnold_pipelines.megaplan.store.snapshot import canonical_json_dumps


def _body() -> str:
    return "\n".join(
        [
            "# Goal",
            "Original goal.",
            "",
            "# Deliverable",
            "Original deliverable.",
        ]
    )


def test_body_update_uses_store_body_api_and_records_event(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Epic", goal="Goal", body=_body())

    updated = update_body(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        body="# Goal\nUpdated.\n\n# Deliverable\nDone.",
        expected_revision=epic.revision,
        turn_id="turn-1",
    )

    assert updated.revision == 1
    assert read_body(store=store, epic_id=epic.id).startswith("# Goal\nUpdated")
    events = store.list_epic_events(epic.id)
    assert [event.event_type for event in events] == ["body_edit"]
    assert events[0].prior_state["body"] == _body()
    assert events[0].turn_id == "turn-1"
    assert events[0].pre_state["body"] == _body()
    assert events[0].post_state["body"].startswith("# Goal\nUpdated")
    assert events[0].post_state["epic"]["revision"] == updated.revision
    assert events[0].post_state_canonical_json == canonical_json_dumps(events[0].post_state)
    assert events[0].post_state_sha256 is not None


def test_body_update_rejects_empty_body_and_lockdown_state(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Epic", goal="Goal", body=_body())

    with pytest.raises(EditorialValidationError, match="cannot be empty"):
        update_body(store=store, epic_id=epic.id, actor_id="actor", body=" ", expected_revision=epic.revision)

    planned = store.update_epic(epic.id, expected_revision=epic.revision, state="planned")
    with pytest.raises(EditorialWorkflowError, match="body_edit is locked"):
        update_body(store=store, epic_id=epic.id, actor_id="actor", body=_body(), expected_revision=planned.revision)


def test_section_edits_validate_missing_duplicate_and_malformed_sections(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Epic", goal="Goal", body=_body())

    with pytest.raises(EditorialValidationError, match="Unsupported section edit mode"):
        edit_section(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            heading="Goal",
            content="Text",
            mode="rewrite",
            expected_revision=epic.revision,
        )

    with pytest.raises(EditorialValidationError, match="not found"):
        edit_section(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            heading="Missing",
            content="Text",
            expected_revision=epic.revision,
        )

    with pytest.raises(EditorialValidationError, match="cannot be empty"):
        edit_section(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            heading="Goal",
            content="",
            expected_revision=epic.revision,
        )

    duplicate = "# Goal\nOne\n\n# Goal\nTwo\n"
    epic = store.update_body(epic.id, duplicate, expected_revision=epic.revision)
    with pytest.raises(EditorialValidationError, match="duplicated"):
        edit_section(
            store=store,
            epic_id=epic.id,
            actor_id="actor",
            heading="Goal",
            content="Three",
            expected_revision=epic.revision,
        )


def test_section_replace_append_prepend_and_delete(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Epic", goal="Goal", body=_body())

    epic = edit_section(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        heading="Goal",
        content="Replacement.",
        expected_revision=epic.revision,
    )
    assert "Replacement." in store.load_body(epic.id)

    epic = edit_section(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        heading="Goal",
        content="Prepended.",
        mode="prepend",
        expected_revision=epic.revision,
    )
    assert "# Goal\nPrepended.\nReplacement." in store.load_body(epic.id)

    epic = edit_section(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        heading="Goal",
        content="Appended.",
        mode="append",
        expected_revision=epic.revision,
    )
    assert "Replacement.\nAppended.\n# Deliverable" in store.load_body(epic.id)

    edit_section(
        store=store,
        epic_id=epic.id,
        actor_id="actor",
        heading="Deliverable",
        mode="delete",
        expected_revision=epic.revision,
    )
    assert store.load_body(epic.id).endswith("# Deliverable\n")


def test_body_update_surfaces_revision_conflicts(editorial_store) -> None:
    store = editorial_store
    epic = store.create_epic(title="Epic", goal="Goal", body=_body())
    store.update_body(epic.id, _body() + "\nextra", expected_revision=epic.revision)

    with pytest.raises(RevisionConflict):
        update_body(store=store, epic_id=epic.id, actor_id="actor", body=_body(), expected_revision=epic.revision)
