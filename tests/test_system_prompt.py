from __future__ import annotations

from agent_kit.prompts import (
    DEFAULT_PROMPT_VERSION,
    build_system_prompt,
    load_system_prompt,
    system_prompt_version,
)
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from agent_kit.templates import DEFAULT_CHECKLIST_SEED
from tests.helpers import create_store, insert_epic


def test_system_prompt_version_is_content_hash() -> None:
    prompt = load_system_prompt()
    assert DEFAULT_PROMPT_VERSION == system_prompt_version(prompt)
    assert len(DEFAULT_PROMPT_VERSION) == 8


def test_sprint_2b_system_prompt_contains_required_sections() -> None:
    prompt = load_system_prompt()
    required_phrases = [
        "# Persona",
        "# Communication Style",
        "# Feedback Discipline",
        "# Body Search And Editing",
        "`search_in_body`, then `get_epic`",
        "Show changes after edits.",
        "# End-Of-Turn Check",
        "# Agent Observations",
        "record_observation",
        "mark_observation_resolved",
        "apply_feedback(feedback_id)",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_sprint_2b_system_prompt_covers_all_checklist_items() -> None:
    prompt = load_system_prompt()
    for index, item in enumerate(DEFAULT_CHECKLIST_SEED, start=1):
        title = item.split(" \u2014 ", 1)[0]
        assert f"## {index}. " in prompt
        assert title.split(" (", 1)[0].split(" - ", 1)[0].lower()[:16] in prompt.lower()


def test_build_system_prompt_appends_hot_feedback_and_observations() -> None:
    rendered = build_system_prompt(
        {
            "active_feedback": [
                {
                    "id": "fb_style",
                    "kind": "style",
                    "content": "Keep replies under 200 words.",
                    "last_applied_at": None,
                }
            ],
            "unresolved_observations": [
                {
                    "id": "fb_obs",
                    "kind": "friction",
                    "content": "Scope took too long to clarify.",
                }
            ],
        }
    )

    assert "# Active Feedback" in rendered
    assert "Keep replies under 200 words." in rendered
    assert "# Recent Unresolved Observations" in rendered
    assert "Scope took too long to clarify." in rendered


def test_run_turn_records_derived_prompt_version(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)

    run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(script=[{"final_text": "done", "provider_request_id": "req_1"}]),
        model_id="fake",
    )

    row = conn.execute("SELECT prompt_version FROM bot_turns").fetchone()
    assert row["prompt_version"] == DEFAULT_PROMPT_VERSION
