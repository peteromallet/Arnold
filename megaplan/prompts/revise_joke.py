"""Joke-mode revise prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from megaplan._core import (
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
    unresolved_significant_flags,
)
from megaplan.types import PlanState

from ._shared import _render_prep_block
from .critique import _settled_decisions_block


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    if isinstance(criterion, str) and criterion.strip():
        return criterion.strip()
    return "[missing primary criterion]"


def _revise_joke_prompt(state: PlanState, plan_dir: Path) -> str:
    project_dir = Path(state["config"]["project_dir"])
    prep_block, prep_instruction = _render_prep_block(plan_dir)
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = read_json(plan_dir / "gate.json")
    unresolved = unresolved_significant_flags(load_flag_registry(plan_dir))
    open_flags = [
        {
            "id": flag["id"],
            "severity": flag.get("severity"),
            "status": flag["status"],
            "concern": flag["concern"],
            "evidence": flag.get("evidence"),
        }
        for flag in unresolved
    ]
    settled_decisions: list[dict[str, Any]] = []
    decisions_path = plan_dir / "tiebreaker_decisions.json"
    if decisions_path.exists():
        decisions_data = read_json(decisions_path)
        if isinstance(decisions_data, list):
            settled_decisions = decisions_data
        elif isinstance(decisions_data, dict):
            settled_decisions = decisions_data.get("decisions", [])
    settled_block = _settled_decisions_block(settled_decisions)
    primary_criterion = _primary_criterion(state)

    return textwrap.dedent(
        f"""
        You are revising a joke-mode scene plan after critique and gate feedback.

        Project directory:
        {project_dir}

        {prep_block}
        {prep_instruction}

        {intent_and_notes_block(state)}

        Current plan (markdown):
        {latest_plan}

        Current plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        Open significant flags:
        {json_dump(open_flags).strip()}

        {settled_block}

        Requirements:
        - Each open flag is a committed generative proposal from a lens persona. Treat them as *menu*, not *checklist*.
        - The primary criterion for this scene is **{primary_criterion}**. This is your through-line.
        - You MAY and SHOULD reject a flag when: (a) it fights the primary criterion, (b) it fights another stronger flag you are keeping, (c) integrating it would require neutering the scene's existing weirdness. Record rejections in `flags_addressed` as `{{"id": "FLAG-X", "resolution": "rejected", "reason": "..."}}`.
        - Select and integrate only the flags that strengthen the scene's coherence under the primary criterion. If a stronger kept flag makes a weaker one redundant, reject the weaker one explicitly instead of sanding both down.
        - Your output is a revised **scene canvas** (premise, tone anchor, characters, objective, obstacle, turn, button), not a task list.
        - Do NOT address every flag. The harness will not measure you against flag-coverage; it will measure the final scene against the primary criterion.
        - Return `flags_addressed` with the exact flag IDs or rejection records you handled. Addressed flags may remain bare IDs; rejected flags must use the object form with `id`, `resolution`, and `reason`.
        - Include `changes_summary` as a short plain-English summary of what changed in the revision and what you intentionally rejected.
        - Preserve or improve success criteria quality. Each criterion must have a `priority` of `must`, `should`, or `info`.
        - Verify that the revised scene canvas remains aligned with the user's original intent, not just internal weirdness.
        - CRITICAL: Your entire revised scene canvas markdown must be output as the `plan` field in the structured output. The prose response must not contain the plan text.
        - CRITICAL: Return only the structured JSON object for the schema fields `plan`, `changes_summary`, `flags_addressed`, `assumptions`, `success_criteria`, and `questions`. Do not add commentary before or after the JSON object.

        Use this canvas shape inside the `plan` field:

        # Scene Canvas: [Title]
        ## Overview
        [One short paragraph describing the comic engine and why it serves the primary criterion.]
        ## Premise
        [...]
        ## Tone Anchor
        [...]
        ## Characters
        [...]
        ## Objective
        [...]
        ## Obstacle
        [...]
        ## Turn
        [...]
        ## Button
        [...]
        """
    ).strip()


__all__ = ["_revise_joke_prompt"]
