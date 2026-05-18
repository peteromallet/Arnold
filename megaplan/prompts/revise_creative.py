"""Creative-work revise prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from megaplan._core import (
    configured_robustness,
    creative_form_id,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
    unresolved_significant_flags,
)
from megaplan.forms import Form, get_form
from megaplan.types import PlanState

from ._shared import _render_prep_block
from .critique import _settled_decisions_block


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    return criterion.strip() if isinstance(criterion, str) and criterion.strip() else "[missing primary criterion]"


def _canvas_template(form: Form) -> str:
    beat_sections = "\n".join(f"## {beat}\n[...]" for beat in form.beat_ids)
    return f"# {form.display_name} Canvas: [Title]\n## Overview\n[One short paragraph naming the engine and refusal.]\n{beat_sections}"


def _prior_stance_block(plan_dir: Path) -> str:
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return "Prior stance: none recorded."
    try:
        data = read_json(notes_path)
    except (OSError, ValueError):
        return "Prior stance: unreadable."
    for pass_entry in reversed(data.get("passes", [])):
        stances = pass_entry.get("stances", [])
        if stances:
            return "Prior stance records:\n" + json_dump(stances).strip()
    return "Prior stance: none recorded."


def _revise_creative_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    form: Form | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    active_form = form or get_form(creative_form_id(state) or "joke")
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
        settled_decisions = decisions_data if isinstance(decisions_data, list) else decisions_data.get("decisions", [])

    contrast_instruction = ""
    if configured_robustness(state) == "full" and int(state.get("iteration") or 1) > 1:
        contrast_instruction = "- The revised stance must explicitly contrast the prior stance: say what you now refuse or keep differently.\n"

    return textwrap.dedent(
        f"""
        You are revising a {active_form.display_name} creative-work canvas after critique and gate feedback.

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

        {_prior_stance_block(plan_dir)}

        {_settled_decisions_block(settled_decisions)}

        Requirements:
        - Treat open flags as a menu of provocations, not a coverage checklist.
        - The primary criterion is **{_primary_criterion(state)}**. This is the through-line.
        - Keep only the provocations that strengthen the artifact's stance. Reject flags that would sand down risk, specificity, or form.
        {contrast_instruction}- Your output is a revised **{active_form.display_name} canvas**, not a task list.
        - Return `flags_addressed` with exact flag IDs or rejection records you handled.
        - Include `changes_summary` naming what changed and what you intentionally refused.
        - Preserve success criteria quality; each criterion priority must be `must`, `should`, or `info`.
        - CRITICAL: Put the entire revised canvas markdown in the `plan` field only.
        - CRITICAL: Return only the structured JSON object for `plan`, `changes_summary`, `flags_addressed`, `assumptions`, `success_criteria`, and `questions`.

        Use this canvas shape inside the `plan` field:

        {_canvas_template(active_form)}
        """
    ).strip()


__all__ = ["_revise_creative_prompt"]
