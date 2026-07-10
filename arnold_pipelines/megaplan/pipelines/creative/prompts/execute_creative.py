"""Creative-work execute prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    execute_batch_artifact_path,
    compute_task_batches,
    configured_robustness,
    creative_form_id,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    read_json,
)
from arnold_pipelines.megaplan.forms import Form, get_form
from arnold_pipelines.megaplan.types import PlanState

from arnold_pipelines.megaplan.prompts._projection import (
    PromptProjectionCapabilities,
    project_execute_context,
)
from arnold_pipelines.megaplan.prompts._shared import (
    _gate_summary_or_skipped,
    _render_prep_block,
)
from arnold_pipelines.megaplan.prompts.execute import (
    _checkpoint_requirements,
    _checkpoint_summary_requirement,
    _execute_approval_note,
    _execute_nudges,
    _execute_rerun_guidance,
    _execute_review_block,
    _extract_execution_order_summary,
    _render_settled_decisions_brief,
)


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    return criterion.strip() if isinstance(criterion, str) and criterion.strip() else "[missing primary criterion]"


def _form(state: PlanState, form: Form | None) -> Form:
    return form or get_form(creative_form_id(state) or "joke")


def _output_shape(form: Form) -> str:
    beats = list(form.beat_ids[:2] or form.beat_ids)
    return textwrap.dedent(
        f"""
        ```json
        {{
          "output": "Authored the planned {form.display_name} artifact.",
          "files_changed": [],
          "commands_run": [],
          "deviations": [],
          "task_updates": [
            {{
              "task_id": "T1",
              "status": "done",
              "executor_notes": "Wrote the assigned beats and preserved the primary criterion.",
              "sections_written": {json_dump(beats).strip()},
              "stance": {{
                "challenge_engaged": "I engaged <provocation id>",
                "angle_taken": "I chose the harder angle because ...",
                "what_changed": "I cut or changed ..."
              }},
              "stop_signal": {{"requested": false, "defense": ""}}
            }}
          ],
          "sense_check_acknowledgments": [
            {{"sense_check_id": "SC1", "executor_note": "Confirmed the artifact serves the declared stance."}}
          ]
        }}
        ```
        """
    ).strip()


def _requirements(
    form: Form,
    checkpoint_path: str,
    capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    return textwrap.dedent(
        f"""
        Requirements:
        - You are a maker authoring {form.display_name}, not a coder shipping source edits.
        - Write the final artifact to the configured output path. This is the only file you should create or modify.
        - The primary criterion is load-bearing.
        - `sections_written` must use this form's beat IDs: {", ".join(form.beat_ids)}.
        - Every `task_updates[]` object MUST include structured `stance` and `stop_signal`.
        - Stance voice: {form.stance_voice_hint}
        - `stance` must be <=50 words total, first person, name the specific provocation engaged, avoid hedging verbs, and take a position someone could disagree with.
        - `stance` fields are `challenge_engaged`, `angle_taken`, and `what_changed`.
        - Stop affordance: if the next pass would damage the work, you MAY set `stop_signal.requested=true` with a concise `defense`; otherwise set `requested=false` and `defense=""`.
        - Use the tasks in `finalize.json` as the execution boundary.
        {_checkpoint_requirements(checkpoint_path, capabilities)}
        - Return `task_updates` with one object per completed or skipped task.
        - `task_updates[].status` must be either `done` or `skipped`.
        - Keep `executor_notes` verification-focused; keep stance separate from the artifact body.
        - Follow this JSON shape exactly:
        {_output_shape(form)}
        """
    ).strip()


def _execute_creative_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
    *,
    form: Form | None = None,
) -> str:
    active_form = _form(state, form)
    project_dir = Path(state["config"]["project_dir"])
    output_path = state["config"].get("output_path", "output.md")
    prep_block, prep_instruction = _render_prep_block(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    projected_finalize = project_execute_context(
        finalize_data,
        capabilities=projection_capabilities,
    )
    checkpoint_path = str(plan_dir / "execution_checkpoint.json")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = _gate_summary_or_skipped(plan_dir)
    requirements_block = _requirements(
        active_form,
        checkpoint_path,
        capabilities=projection_capabilities,
    )
    return textwrap.dedent(
        f"""
        Author the planned {active_form.display_name} creative artifact.

        Project directory:
        {project_dir}

        Output path:
        {output_path}

        Primary criterion:
        {_primary_criterion(state)}

        {prep_block}
        {prep_instruction}

        {intent_and_notes_block(state)}

        Execution tracking source of truth (`finalize.json`, prompt projection only):
        {json_dump(projected_finalize).strip()}

        Absolute checkpoint path for best-effort progress checkpoints (NOT `finalize.json`):
        {checkpoint_path}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {_execute_review_block(plan_dir, capabilities=projection_capabilities)}

        {_execute_rerun_guidance(plan_dir, finalize_data)}

        {_execute_approval_note(state)}
        Robustness level: {configured_robustness(state)}.

        {requirements_block}

        {_execute_nudges(finalize_data, plan_dir, root)}
        """
    ).strip()


def _execute_creative_batch_prompt(
    state: PlanState,
    plan_dir: Path,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None = None,
    root: Path | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
    *,
    form: Form | None = None,
) -> str:
    active_form = _form(state, form)
    completed = set(completed_task_ids or set())
    finalize_data = read_json(plan_dir / "finalize.json")
    projected_finalize = project_execute_context(
        finalize_data,
        capabilities=projection_capabilities,
    )
    all_tasks = finalize_data.get("tasks", [])
    projected_tasks = projected_finalize.get("tasks", [])
    tasks_by_id = {task["id"]: task for task in all_tasks if isinstance(task, dict) and isinstance(task.get("id"), str)}
    projected_tasks_by_id = {
        task["id"]: task
        for task in projected_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    batch_tasks = [
        projected_tasks_by_id[task_id]
        for task_id in batch_task_ids
        if task_id in projected_tasks_by_id
    ]
    completed_tasks = [
        projected_tasks_by_id[task_id]
        for task_id in completed
        if task_id not in set(batch_task_ids) and task_id in projected_tasks_by_id
    ]
    projected_sense_checks = projected_finalize.get("sense_checks", [])
    batch_sense_checks = [sc for sc in projected_sense_checks if sc.get("task_id") in set(batch_task_ids)]
    batch_sense_check_ids = [sc["id"] for sc in batch_sense_checks if isinstance(sc.get("id"), str)]
    global_batches = compute_task_batches(all_tasks)
    batch_number = next((index + 1 for index, batch in enumerate(global_batches) if batch == batch_task_ids), 1)
    checkpoint_path = str(
        execute_batch_artifact_path(plan_dir, batch_number, batch_task_ids)
    )
    gate_carry = _gate_summary_or_skipped(plan_dir)
    try:
        latest_plan_text = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    except (KeyError, OSError):
        latest_plan_text = ""
    meta_commentary = projected_finalize.get("meta_commentary", "")
    if not isinstance(meta_commentary, str):
        meta_commentary = ""
    execution_context = textwrap.dedent(
        f"""
        ## Execution context (settled - DO NOT re-litigate)

        {_render_settled_decisions_brief(gate_carry)}

        ## Plan execution order rationale

        {_extract_execution_order_summary(latest_plan_text)}

        ## Inter-task guidance from finalize

        {meta_commentary[:1500]}
        """
    ).strip()
    return textwrap.dedent(
        f"""
        Author the planned {active_form.display_name} creative artifact.

        Project directory:
        {Path(state["config"]["project_dir"])}

        Output path:
        {state["config"].get("output_path", "output.md")}

        Primary criterion:
        {_primary_criterion(state)}

        {intent_and_notes_block(state)}

        Batch framing:
        - Execute batch {batch_number} of {len(global_batches) or 1}.
        - Actionable task IDs for this batch: {batch_task_ids}
        - Already completed task IDs available as dependency context: {sorted(completed)}

        Actionable tasks for this batch:
        {json_dump(batch_tasks).strip()}

        Completed task context:
        {json_dump(completed_tasks).strip()}

        Batch-scoped sense checks:
        {json_dump(batch_sense_checks).strip()}

        {execution_context}

        {_execute_approval_note(state)}
        Robustness level: {configured_robustness(state)}.

        Requirements:
        - Execute only the actionable tasks in this batch.
        - Treat completed tasks as dependency context, not new work.
        - Return structured JSON only.
        - Only produce `task_updates` for these tasks: [{", ".join(batch_task_ids)}]
        - Only produce `sense_check_acknowledgments` for these sense checks: [{", ".join(batch_sense_check_ids)}]
        - Do not include updates outside this batch.
        - `sections_written` must use this form's beat IDs: {", ".join(active_form.beat_ids)}.
        - Every task update MUST include `stance` and `stop_signal`.
        - Stance voice: {active_form.stance_voice_hint}
        - Stance must be <=50 words, first person, name the specific provocation, avoid hedging verbs, and take a disagreeable position.
        - Stop affordance: set `stop_signal.requested=true` only if another pass would damage the work; include the defense.
        - {_checkpoint_summary_requirement(checkpoint_path, projection_capabilities)}
        - Follow this JSON shape:
        {_output_shape(active_form)}
        """
    ).strip()


__all__ = ["_execute_creative_batch_prompt", "_execute_creative_prompt"]
