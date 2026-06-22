"""Joke-mode prep prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Mapping

from arnold_pipelines.megaplan.types import PlanState


def _declared_primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    if isinstance(criterion, str) and criterion.strip():
        return criterion.strip()
    return ""


def _prep_joke_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    contract_context: Mapping[str, object] | None = None,
) -> str:
    del contract_context
    del root
    project_dir = Path(state["config"]["project_dir"])
    output_path = plan_dir / "prep.json"
    declared_primary_criterion = _declared_primary_criterion(state)
    declared_primary_criterion_block = ""
    if declared_primary_criterion:
        declared_primary_criterion_block = textwrap.dedent(
            f"""
            Declared primary criterion:
            {declared_primary_criterion}

            Preserve this unless the task text clearly contradicts it.
            """
        ).strip()
    return textwrap.dedent(
        f"""
        Prepare a concise scene-writing brief for the joke-mode task below. This brief will be the primary context for all subsequent planning and execution.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Output file: {output_path}

        {declared_primary_criterion_block}

        First, assess: does this task need investigation?

        Set "skip": true if ALL of these are true:
        - The scene premise, tone, and comic target are already explicit.
        - The primary criterion is already obvious from the task.
        - No repository context, prior examples, or tonal references need review.

        Set "skip": false if ANY of these are true:
        - The brief needs film, genre, or tonal anchor references.
        - The scene premise is underspecified or could go in multiple directions.
        - The primary criterion is not explicit and must be inferred from context.
        - Characters, location, constraints, or format expectations are still fuzzy.

        If skipping, leave everything else empty. The original task description will be used directly.
        If not skipping, fill in the brief:
        1. Summarize the scene premise and the comic engine.
        2. Declare the primary criterion for the scene. This field is REQUIRED when skip is false.
        3. Identify useful reference films, tonal anchors, or comparable scenes.
        4. Name the likely characters, location, and core dramatic situation.
        5. Capture constraints such as length, rating, tone, and format.

        Brief fields:
        - skip: true if no investigation is needed, false if the brief has useful content.
        - task_summary: What the scene should accomplish, in 2-3 sentences.
        - primary_criterion: REQUIRED when skip is false. Examples: "weirdest coherent", "most bathetic", "darkest that plays funny".
        - key_evidence: Facts from the task description or repository context that shape the scene.
        - relevant_code: File paths or existing artifacts worth referencing for continuity or house style. Use this for source material, not code to change.
        - test_expectations: For joke mode, list the scene beats or constraints reviewers should verify. Each entry's test_id is a beat or requirement name, status is "expected", and what_it_checks describes what the scene must deliver.
        - constraints: Length, rating, tone, location, format, or content constraints that must be preserved.
        - suggested_approach: A concrete scene-writing approach grounded in what you found.

        Return JSON only.
        """
    ).strip()


__all__ = ["_prep_joke_prompt"]
