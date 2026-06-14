"""Creative-work critique prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping
from typing import Any

from arnold.pipelines.megaplan._core import configured_robustness, creative_form_id, read_json
from arnold.pipelines.megaplan.forms import Form, get_form
from arnold.pipelines.megaplan.forms.provocations import select_active_checks
from arnold.pipelines.megaplan.types import PlanState

from arnold.pipelines.megaplan.prompts.critique import (
    _build_critique_prompt,
    _critique_context,
    _write_critique_template,
)

_STANCE_AUTHENTICITY_SUBPROVOCATION = (
    "Read it aloud. If it's safe, the work is too. Rewrite the part that would embarrass you to say to a stranger."
)


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    return criterion.strip() if isinstance(criterion, str) and criterion.strip() else "[missing primary criterion]"


def _prior_provocation_ids(plan_dir: Path) -> list[str]:
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return []
    try:
        data = read_json(notes_path)
    except (OSError, ValueError):
        return []
    ids: list[str] = []
    for pass_entry in data.get("passes", []):
        for provocation in pass_entry.get("provocations_fired", []):
            if isinstance(provocation, dict) and isinstance(provocation.get("id"), str):
                ids.append(provocation["id"])
    return ids


def _stance_subprovocation_block(plan_dir: Path) -> str:
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return ""
    try:
        data = read_json(notes_path)
    except (OSError, ValueError):
        return ""
    for pass_entry in reversed(data.get("passes", [])):
        for stance in pass_entry.get("stances", []):
            if isinstance(stance, dict) and stance.get("stance_violations"):
                return (
                    "Stance-authenticity sub-provocation:\n"
                    f"{_STANCE_AUTHENTICITY_SUBPROVOCATION}\n"
                    "Prior stance violations:\n"
                    f"{stance.get('stance_violations')}"
                )
    return ""


def _voice_text(form: Form, checks: tuple[dict[str, Any], ...]) -> str:
    voice_id = next((check.get("provocateur_voice") for check in checks if check.get("provocateur_voice")), None)
    if not isinstance(voice_id, str):
        return "Provocateur voice: maker's own pressure."
    voice = next((candidate for candidate in form.provocateur_voices if candidate.id == voice_id), None)
    return f"Provocateur voice: {voice.id} — {voice.persona_text}" if voice else f"Provocateur voice: {voice_id}"


def _provocation_instruction(check: dict[str, Any]) -> str:
    provocation = check.get("provocation", {})
    pid = str(provocation.get("id", check.get("id", "")))
    vector = str(provocation.get("vector", "provocation"))
    subtype = str(provocation.get("subtype", ""))
    prompt_text = str(provocation.get("prompt_text", check.get("guidance", "")))
    return textwrap.dedent(
        f"""
        {pid} ({vector}/{subtype})
        {prompt_text}
        Output exactly one `FLAG-{pid}`. The flag must name one concrete proposal for the work: a cut, transformation, line, image, structure, or dare. Do not offer alternatives.
        """
    ).strip()


def _creative_findings_requirements() -> str:
    return textwrap.dedent(
        """
        For each active provocation:
        - Add at least one finding to that check's `findings` array.
        - Keep the existing findings schema unchanged: each finding needs `detail` and `flagged`.
        - Use `detail` to name the concrete act demanded by the provocation and why it strengthens the work.
        - Set `flagged` to true for the committed proposal.
        - Emit exactly one `FLAG-<provocation-id>` entry in the `flags` array.
        """
    ).strip()


def _critique_creative_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    *,
    form: Form | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    del contract_context
    context = _critique_context(state, plan_dir, root)
    active_form = form or get_form(creative_form_id(state) or "joke")
    robustness = configured_robustness(state)
    active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
    output_path = _write_critique_template(plan_dir, state, active_checks)
    prior_ids = _prior_provocation_ids(plan_dir)
    stance_subprovocation = _stance_subprovocation_block(plan_dir)
    iteration = int(state.get("iteration") or 1)
    prior_block = ""
    if robustness == "full" and iteration > 1 and prior_ids:
        prior_block = (
            "\nPreviously fired provocations from directors_notes.json are off-limits for this pass. "
            "The selector has excluded them; do not relitigate addressed material."
        )
    provocation_block = "\n\n".join(_provocation_instruction(check) for check in active_checks)
    critique_review_block = textwrap.dedent(
        f"""
        Your output template is at: {output_path}
        Read this file first. It contains the active creative-work provocations for {active_form.display_name}.

        The primary criterion is: {_primary_criterion(state)}
        {_voice_text(active_form, active_checks)}
        Form beats: {", ".join(active_form.beat_ids)}
        {prior_block}

        {_creative_findings_requirements()}

        Active provocations:
        {stance_subprovocation}

        {provocation_block or "No provocations are active at this robustness level."}

        Commit to one concrete proposal per provocation. Avoid introspection, throat-clearing, and hedging.
        Workflow: read the file -> investigate the plan and artifact context -> write committed findings and `FLAG-<provocation-id>` flags -> write the file back.
        """
    ).strip()
    return _build_critique_prompt(state, context, critique_review_block)


__all__ = ["_critique_creative_prompt"]
