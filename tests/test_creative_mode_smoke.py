from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core import atomic_write_json, atomic_write_text, read_json
from arnold.pipelines.megaplan.execute.core import _build_aggregate_execution_payload
from arnold.pipelines.megaplan.handlers.review import _resolve_review_outcome
from arnold.pipelines.megaplan.planning.state import STATE_DONE


def _init_args(project_dir: Path, *, name: str) -> Namespace:
    return Namespace(
        plan=None,
        idea="Write a poem about a room that refuses to echo.",
        name=name,
        project_dir=str(project_dir),
        auto_approve=None,
        robustness="standard",
        agent=None,
        mode="creative",
        form="poem",
        output="poems/p.md",
        primary_criterion="tightest image",
        from_doc=None,
        hermes=None,
    )


def _initialized_creative_poem(
    bootstrap_fixture: tuple[Path, Path], *, name: str
) -> tuple[Path, dict]:
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(root, _init_args(project_dir, name=name))
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = read_json(plan_dir / "state.json")
    state["iteration"] = 1
    state["current_state"] = "finalized"
    state["plan_versions"] = [
        {
            "version": 1,
            "file": "plan_v1.md",
            "hash": "sha256:test",
            "timestamp": "2026-04-01T00:00:00Z",
        }
    ]
    atomic_write_text(
        plan_dir / "plan_v1.md",
        "# Poem Canvas\n"
        "## opening_image\n"
        "A room holds its breath.\n"
        "## turn\n"
        "The speaker names what the silence costs.\n"
        "## close\n"
        "The final image refuses explanation.\n",
    )
    atomic_write_json(plan_dir / "state.json", state)
    return plan_dir, state


def _poem_execute_payload(*, stop_requested: bool) -> dict:
    defense = "The next pass would sand the last image flat."
    return {
        "output": "Wrote the poem sections.",
        "sections_written": ["opening_image", "turn", "close"],
        "commands_run": [],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T-poem",
                "status": "done",
                "executor_notes": "Drafted the poem.",
                "sections_written": ["opening_image", "turn", "close"],
                "stance": {
                    "challenge_engaged": "I engaged poem-cut-explanation.",
                    "angle_taken": "I chose the image because it makes the room guilty.",
                    "what_changed": "I killed the summary line and kept the silence.",
                },
                "stop_signal": {"requested": stop_requested, "defense": defense},
            }
        ],
        "sense_check_acknowledgments": [],
    }


def test_creative_poem_execute_writes_directors_notes_once_per_run(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    plan_dir, state = _initialized_creative_poem(bootstrap_fixture, name="creative-poem-smoke")

    aggregate = _build_aggregate_execution_payload(
        [_poem_execute_payload(stop_requested=False)],
        completed_batches=1,
        total_batches=1,
        mode="creative",
        plan_dir=plan_dir,
        state=state,
    )

    notes = read_json(plan_dir / "directors_notes.json")
    assert aggregate["sections_written"] == ["opening_image", "turn", "close"]
    assert notes["form"] == "poem"
    assert notes["primary_criterion"] == "tightest image"
    assert len(notes["passes"]) == 1
    pass_entry = notes["passes"][0]
    assert pass_entry["iteration"] == 1
    assert pass_entry["stop_requested"] is False
    assert len(pass_entry["provocations_fired"]) == 3
    assert {item["vector"] for item in pass_entry["provocations_fired"]} == {
        "cut",
        "force",
        "spark",
    }
    assert pass_entry["stances"] == [
        {
            "task_id": "T-poem",
            "challenge_engaged": "I engaged poem-cut-explanation.",
            "angle_taken": "I chose the image because it makes the room guilty.",
            "what_changed": "I killed the summary line and kept the silence.",
            "stance_violations": [],
        }
    ]


def test_creative_poem_stop_signal_halts_needs_rework_review(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    plan_dir, state = _initialized_creative_poem(bootstrap_fixture, name="creative-poem-stop")

    _build_aggregate_execution_payload(
        [_poem_execute_payload(stop_requested=True)],
        completed_batches=1,
        total_batches=1,
        mode="creative",
        plan_dir=plan_dir,
        state=state,
    )
    atomic_write_json(
        plan_dir / "finalize.json",
        {"tasks": _poem_execute_payload(stop_requested=True)["task_updates"]},
    )

    result = _resolve_review_outcome(
        plan_dir,
        "needs_rework",
        1,
        1,
        0,
        0,
        [],
        "standard",
        state,
        [],
    )

    assert result == ("success", STATE_DONE, None)
    assert any("sand the last image flat" in note["note"] for note in state["meta"]["notes"])
    notes = read_json(plan_dir / "directors_notes.json")
    assert len(notes["passes"]) == 1
    assert notes["passes"][0]["stop_requested"] is True
    assert notes["passes"][0]["stop_defense"] == "The next pass would sand the last image flat."
