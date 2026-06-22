from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.schemas.arnold import ARNOLD_EPIC_STATES, ARNOLD_TO_MEGAPLAN_EPIC_STATE, Epic, map_arnold_epic_state


def test_arnold_epic_lifecycle_mapping_uses_existing_megaplan_states() -> None:
    assert ARNOLD_EPIC_STATES == ("shaping", "sprinting", "planned", "paused", "archived")
    assert ARNOLD_TO_MEGAPLAN_EPIC_STATE == {
        "shaping": "shaping",
        "sprinting": "sprinting",
        "planned": "planned",
        "paused": "paused",
        "archived": "archived",
    }
    for state in ARNOLD_EPIC_STATES:
        assert map_arnold_epic_state(state) == state


def test_arnold_epic_lifecycle_mapping_rejects_unknown_state() -> None:
    with pytest.raises(ValueError, match="Unsupported Arnold epic state"):
        map_arnold_epic_state("reviewing")


def test_epic_model_accepts_all_mapped_states() -> None:
    for state in ARNOLD_EPIC_STATES:
        epic = Epic(id=f"epic-{state}", title="Title", goal="Goal", body="Body", state=state)
        assert epic.state == state
