"""Creative-work execute prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import (
    batch_artifact_path,
    compute_task_batches,
    configured_robustness,
    creative_form_id,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    read_json,
)
from megaplan.forms import Form, get_form
from megaplan.types import PlanState

from ._shared import _debt_watch_lines, _render_prep_block
from .execute import _execute_approval_note, _execute_nudges, _execute_rerun_guidance, _execute_review_block


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


def _requirements(form: Form, checkpoint_path: str) -> str:
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
        - Best-effort progress checkpointing: if `{checkpoint_path}` is writable, update task status, executor notes, sections_written, stance, and stop_signal there. Do NOT write to `finalize.json` directly.
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
    *,
    form: Form | None = None,
) -> str:
    active_form = _form(state, form)
    project_dir = Path(state["config"]["project_dir"])
    output_path = state["config"].get("output_path", "output.md")
    prep_block, prep_instruction = _render_prep_block(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    checkpoint_path = str(plan_dir / "execution_checkpoint.json")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = read_json(plan_dir / "gate.json")
    requirements_block = _requirements(active_form, checkpoint_path)
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

        Execution tracking source of truth (`finalize.json`):
        {json_dump(finalize_data).strip()}

        Absolute checkpoint path for best-effort progress checkpoints (NOT `finalize.json`):
        {checkpoint_path}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {_execute_review_block(plan_dir)}

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
    *,
    form: Form | None = None,
) -> str:
    active_form = _form(state, form)
    completed = set(completed_task_ids or set())
    finalize_data = read_json(plan_dir / "finalize.json")
    all_tasks = finalize_data.get("tasks", [])
    tasks_by_id = {task["id"]: task for task in all_tasks if isinstance(task, dict) and isinstance(task.get("id"), str)}
    batch_tasks = [tasks_by_id[task_id] for task_id in batch_task_ids if task_id in tasks_by_id]
    completed_tasks = [task for task_id, task in tasks_by_id.items() if task_id in completed and task_id not in set(batch_task_ids)]
    batch_sense_checks = [sc for sc in finalize_data.get("sense_checks", []) if sc.get("task_id") in set(batch_task_ids)]
    batch_sense_check_ids = [sc["id"] for sc in batch_sense_checks if isinstance(sc.get("id"), str)]
    global_batches = compute_task_batches(all_tasks)
    batch_number = next((index + 1 for index, batch in enumerate(global_batches) if batch == batch_task_ids), 1)
    checkpoint_path = str(batch_artifact_path(plan_dir, batch_number))
    debt_items = _debt_watch_lines(plan_dir, root)
    debt_block = "\n".join(["Debt watch items (do not make these worse):", *[f"- {item}" for item in debt_items]]) if debt_items else "Debt watch items (do not make these worse):\n- None."
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

        Full execution tracking source of truth (`finalize.json`):
        {json_dump(finalize_data).strip()}

        {debt_block}

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
        - Best-effort progress checkpointing: if `{checkpoint_path}` is writable, checkpoint task and sense-check updates there (not `finalize.json`).
        - Follow this JSON shape:
        {_output_shape(active_form)}
        """
    ).strip()


__all__ = ["_execute_creative_batch_prompt", "_execute_creative_prompt"]
