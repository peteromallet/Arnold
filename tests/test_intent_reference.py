"""Tests for slim downstream brief references."""

from __future__ import annotations

from pathlib import Path

from megaplan._core import intent_brief_reference
from megaplan.types import PlanState


def _state(idea: str, *, intent_summary: str | None = None) -> PlanState:
    state: PlanState = {
        "name": "test-plan",
        "idea": idea,
        "current_state": "planned",
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": "/tmp/project"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"notes": []},
        "last_gate": {},
    }
    if intent_summary is not None:
        state["clarification"] = {"intent_summary": intent_summary}
    return state


def test_intent_brief_reference_short() -> None:
    idea = "Refactor the worker process state. " + ("extra detail " * 500)

    output = intent_brief_reference(_state(idea))

    assert len(output) < 500
    assert "Brief summary:" in output
    assert "Full brief in state.idea" in output


def test_intent_brief_reference_uses_clarification() -> None:
    output = intent_brief_reference(
        _state("Verbose original idea that should not be used.", intent_summary="Use the slim summary.")
    )

    assert "Brief summary: Use the slim summary." in output
    assert "Verbose original idea" not in output


def test_intent_brief_reference_falls_back_to_first_sentence() -> None:
    output = intent_brief_reference(
        _state("First sentence drives the summary. Second sentence stays out.")
    )

    assert "Brief summary: First sentence drives the summary" in output
    assert "Second sentence stays out" not in output


def test_intent_brief_reference_truncates_at_200() -> None:
    output = intent_brief_reference(_state("x" * 250))

    summary = output.splitlines()[0].removeprefix("Brief summary: ")
    assert len(summary) == 203
    assert summary.endswith("...")


def test_downstream_prompt_modules_use_slim_reference() -> None:
    prompt_dir = Path("megaplan/prompts")
    downstream_modules = [
        "critique.py",
        "execute.py",
        "execute_creative.py",
        "execute_doc.py",
        "finalize.py",
        "gate.py",
        "review.py",
        "review_doc.py",
        "review_joke.py",
        "revise_creative.py",
        "tiebreaker_challenger.py",
        "tiebreaker_researcher.py",
    ]

    for module in downstream_modules:
        source = (prompt_dir / module).read_text(encoding="utf-8")
        assert "intent_brief_reference" in source, module
        assert "intent_and_notes_block" not in source, module


def test_verbose_intent_stays_scoped_to_plan_and_prep() -> None:
    callers = []
    for path in sorted(Path("megaplan/prompts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "intent_and_notes_block(state)" in source:
            callers.append(path.name)

    assert callers == ["planning.py"]


def test_prep_block_stays_scoped_to_plan_and_main_execute() -> None:
    callers = []
    for path in sorted(Path("megaplan/prompts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "_render_prep_block(plan_dir)" in source:
            callers.append(path.name)

    assert callers == ["execute.py", "planning.py"]


def test_plan_template_stays_scoped_to_plan() -> None:
    callers = []
    for path in sorted(Path("megaplan/prompts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "PLAN_TEMPLATE" in source and path.name != "__init__.py":
            callers.append(path.name)

    assert callers == ["planning.py"]
