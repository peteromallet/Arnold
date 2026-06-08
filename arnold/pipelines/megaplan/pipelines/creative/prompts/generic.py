"""Fresh-run-safe generic creative prompt renderers."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold.pipelines.megaplan._core import configured_robustness, creative_form_id
from arnold.pipelines.megaplan._pipeline.types import StepContext
from arnold.pipelines.megaplan.forms import Form, get_form
from arnold.pipelines.megaplan.forms.provocations import select_active_checks


def _state(ctx: StepContext) -> dict[str, Any]:
    return dict(ctx.state) if isinstance(ctx.state, Mapping) else {}


def _config(state: Mapping[str, Any]) -> dict[str, Any]:
    raw = state.get("config", {})
    return dict(raw) if isinstance(raw, Mapping) else {}


def _form(
    ctx: StepContext,
    params: Mapping[str, Any],
    state: Mapping[str, Any],
) -> Form:
    raw_form = params.get("form")
    if isinstance(raw_form, str) and raw_form:
        return get_form(raw_form)
    form_id = creative_form_id(state)
    return get_form(form_id or "joke")


def _primary_criterion(
    config: Mapping[str, Any],
    params: Mapping[str, Any],
) -> str:
    raw = params.get("primary_criterion")
    if not isinstance(raw, str) or not raw.strip():
        raw = config.get("primary_criterion")
    return raw.strip() if isinstance(raw, str) and raw.strip() else "[not declared]"


def _project_dir(config: Mapping[str, Any]) -> str:
    raw = config.get("project_dir")
    return str(raw) if raw else "."


def _output_path(config: Mapping[str, Any], form: Form) -> str:
    raw = config.get("output_path")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return f"creative-output{form.output_extension}"


def _idea(state: Mapping[str, Any]) -> str:
    raw = state.get("idea")
    return (
        raw.strip()
        if isinstance(raw, str) and raw.strip()
        else "[no idea text provided]"
    )


def _intent_block(state: Mapping[str, Any]) -> str:
    sections = [f"Idea:\n{_idea(state)}"]
    meta = state.get("meta", {})
    if isinstance(meta, Mapping):
        notes = meta.get("notes", [])
        if isinstance(notes, list) and notes:
            sections.append(
                "Operator notes:\n" + "\n".join(f"- {note}" for note in notes)
            )
    return "\n\n".join(sections)


def _previous_artifacts(
    ctx: StepContext,
    params: Mapping[str, Any],
) -> dict[str, Path]:
    raw = params.get("previous_artifacts")
    if not isinstance(raw, Mapping) and isinstance(ctx.state, Mapping):
        raw = ctx.state.get("_creative_artifacts", {})
    artifacts: dict[str, Path] = {}
    if isinstance(raw, Mapping):
        for label, value in raw.items():
            if isinstance(label, str) and value:
                artifacts[label] = Path(value)
    return artifacts


def _artifact_excerpt(path: Path, *, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return f"[artifact unavailable at {path}]"
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[truncated]"


def _artifact_block(ctx: StepContext, params: Mapping[str, Any]) -> str:
    artifacts = _previous_artifacts(ctx, params)
    if not artifacts:
        return "Prior creative artifacts: none yet."
    blocks = []
    for label, path in sorted(artifacts.items()):
        blocks.append(
            textwrap.dedent(
                f"""
                ## {label}
                Path: {path}

                {_artifact_excerpt(path)}
                """
            ).strip()
        )
    return "Prior creative artifacts:\n\n" + "\n\n".join(blocks)


def _beat_list(form: Form) -> str:
    return "\n".join(f"- {beat}" for beat in form.beat_ids)


def _prep_checklist(form: Form) -> str:
    return "\n".join(f"- {item}" for item in form.prep_checklist)


def _provocation_lines(form: Form) -> str:
    lines: list[str] = []
    for group in (
        form.provocations.cuts,
        form.provocations.forces,
        form.provocations.sparks,
    ):
        for provocation in group:
            lines.append(
                f"- {provocation.id} ({provocation.vector}/{provocation.subtype}): "
                f"{provocation.prompt_text}"
            )
    return "\n".join(lines) if lines else "- No registered provocations."


def creative_prep_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    state = _state(ctx)
    config = _config(state)
    form = _form(ctx, params, state)
    return textwrap.dedent(
        f"""
        Prepare a concise creative brief for a {form.display_name} run.

        Task:
        {_idea(state)}

        Project directory:
        {_project_dir(config)}

        Output path:
        {_output_path(config, form)}

        Primary criterion:
        {_primary_criterion(config, params)}

        {_intent_block(state)}

        Form beats:
        {_beat_list(form)}

        Preparation checklist:
        {_prep_checklist(form)}

        Requirements:
        - Decide whether repository investigation is needed before authoring.
        - Keep the brief specific to {form.display_name}; do not borrow another form's beats.
        - Name the working stance, pressure point, and likely failure mode.
        - Preserve the primary criterion unless the task text directly contradicts it.
        - Return JSON with: skip, task_summary, primary_criterion, key_evidence, relevant_code, test_expectations, constraints, suggested_approach.
        """
    ).strip()


def creative_execute_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    state = _state(ctx)
    config = _config(state)
    form = _form(ctx, params, state)
    return textwrap.dedent(
        f"""
        Author the current {form.display_name} creative artifact from fresh creative pipeline context.

        Task:
        {_idea(state)}

        Project directory:
        {_project_dir(config)}

        Output path:
        {_output_path(config, form)}

        Primary criterion:
        {_primary_criterion(config, params)}

        Form beats:
        {_beat_list(form)}

        {_artifact_block(ctx, params)}

        Requirements:
        - Write the artifact itself, not a task plan.
        - Use the prior prep artifact as guidance when present.
        - Cover the form beats that serve the work; do not invent planning artifacts.
        - Include a concise stance with challenge_engaged, angle_taken, and what_changed.
        - Include stop_signal with requested=false unless another pass would damage the work.
        - Return structured JSON with output, files_changed, commands_run, deviations, task_updates, and sense_check_acknowledgments.
        """
    ).strip()


def creative_critique_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    state = _state(ctx)
    config = _config(state)
    form = _form(ctx, params, state)
    robustness = configured_robustness(state)
    checks = select_active_checks(state, robustness, plan_dir=Path(ctx.plan_dir))
    selected = "\n".join(
        f"- {check.get('id')}: "
        f"{check.get('guidance') or check.get('provocation', {}).get('prompt_text')}"
        for check in checks
    )
    return textwrap.dedent(
        f"""
        Critique the current {form.display_name} artifact using fresh creative pipeline context.

        Primary criterion:
        {_primary_criterion(config, params)}

        Form beats:
        {_beat_list(form)}

        Available form provocations:
        {_provocation_lines(form)}

        Selected checks for robustness {robustness}:
        {selected or "- No selected checks."}

        {_artifact_block(ctx, params)}

        Requirements:
        - Use prior prep and execute artifacts as the source of truth.
        - Do not require planning metadata, gate summaries, or finalize task lists.
        - Flag concrete changes to the artifact: a cut, transformation, line, image, structure, or dare.
        - Return JSON with findings and flags that name exact provocation or beat pressure.
        """
    ).strip()


def creative_revise_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    state = _state(ctx)
    config = _config(state)
    form = _form(ctx, params, state)
    return textwrap.dedent(
        f"""
        Revise the {form.display_name} artifact using prior creative pipeline artifacts.

        Task:
        {_idea(state)}

        Primary criterion:
        {_primary_criterion(config, params)}

        Form beats:
        {_beat_list(form)}

        {_artifact_block(ctx, params)}

        Requirements:
        - Treat the critique artifact as pressure, not as an automatic checklist.
        - Keep changes that strengthen the artifact's stance and reject changes that soften it.
        - Do not read or depend on planning metadata, gate summaries, or finalize task lists.
        - Return JSON with plan, changes_summary, flags_addressed, assumptions, success_criteria, and questions.
        - Put the revised {form.display_name} artifact in the plan field.
        """
    ).strip()


def creative_joke_execute_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    return (
        creative_execute_prompt(ctx, {**dict(params), "form": "joke"})
        + "\n\nJoke-form emphasis:\n"
        "- Build a scene with a playable comic engine, not a list of gags.\n"
        "- Make the button or turn feel inevitable after the setup.\n"
        "- Keep the weirdest choice coherent enough that a reader can stage it."
    )


def creative_joke_critique_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    return (
        creative_critique_prompt(ctx, {**dict(params), "form": "joke"})
        + "\n\nJoke-form critique pressure:\n"
        "- Test whether the premise, escalation, and button are all present.\n"
        "- Flag cuts that make the scene funnier instead of merely shorter.\n"
        "- Do not ask for planning artifacts, gate reports, or finalize files."
    )


def creative_joke_revise_prompt(ctx: StepContext, params: Mapping[str, Any]) -> str:
    return (
        creative_revise_prompt(ctx, {**dict(params), "form": "joke"})
        + "\n\nJoke-form revision pressure:\n"
        "- Strengthen the comic engine before polishing language.\n"
        "- Preserve the best surprise and remove setup that does not pay it off.\n"
        "- Keep the revised scene in the returned plan field."
    )


__all__ = [
    "creative_critique_prompt",
    "creative_execute_prompt",
    "creative_joke_critique_prompt",
    "creative_joke_execute_prompt",
    "creative_joke_revise_prompt",
    "creative_prep_prompt",
    "creative_revise_prompt",
]
