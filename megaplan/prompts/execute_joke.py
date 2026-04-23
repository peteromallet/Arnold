"""Joke-mode execute prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import (
    batch_artifact_path,
    compute_task_batches,
    configured_robustness,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    read_json,
)
from megaplan.types import PlanState

from ._shared import _debt_watch_lines, _render_prep_block
from .execute import (
    _execute_approval_note,
    _execute_nudges,
    _execute_rerun_guidance,
    _execute_review_block,
)

_EXECUTE_JOKE_OUTPUT_SHAPE_EXAMPLE = textwrap.dedent(
    """
    ```json
    {
      "output": "Authored the planned scene prose.",
      "files_changed": [],
      "commands_run": [],
      "deviations": [],
      "task_updates": [
        {
          "task_id": "T1",
          "status": "done",
          "executor_notes": "Wrote the opening and inciting movement while preserving the primary criterion.",
          "sections_written": ["opening", "inciting"]
        },
        {
          "task_id": "T2",
          "status": "done",
          "executor_notes": "Integrated the obstacle, turn, and button into one coherent comedic escalation.",
          "sections_written": ["obstacle", "turn", "button"]
        }
      ],
      "sense_check_acknowledgments": [
        {
          "sense_check_id": "SC1",
          "executor_note": "Confirmed the final scene prose still serves the declared primary criterion."
        }
      ]
    }
    ```
    """
).strip()


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    if isinstance(criterion, str) and criterion.strip():
        return criterion.strip()
    return "[missing primary criterion]"


def _execute_joke_requirements(checkpoint_path: str) -> str:
    return textwrap.dedent(
        f"""
        Requirements:
        - You are a screenwriter authoring a single scene, not a coder shipping source edits.
        - Write the final scene prose to the configured output path. This is the only file you should create or modify.
        - The primary criterion is load-bearing. Keep the scene weird/coherent/bathetic according to that declared target.
        - `sections_written` should use scene-beat IDs such as `opening`, `inciting`, `obstacle`, `turn`, and `button`.
        - Use the tasks in `finalize.json` as the execution boundary.
        - Best-effort progress checkpointing: if `{checkpoint_path}` is writable, then after each completed task read the full file, update that task's `status`, `executor_notes`, and `sections_written`, and write the full file back. Do NOT write to `finalize.json` directly.
        - Best-effort sense-check checkpointing: if `{checkpoint_path}` is writable, then after each sense check acknowledgment read the full file again, update that sense check's `executor_note`, and write the full file back.
        - Return `task_updates` with one object per completed or skipped task.
        - `task_updates[].status` must be either `done` or `skipped`. Never return `pending` in execute output.
        - Return `sense_check_acknowledgments` with one object per sense check.
        - Keep `executor_notes` verification-focused: explain why the scene beats and final prose satisfy the brief and primary criterion.
        - Follow this JSON shape exactly:
        {_EXECUTE_JOKE_OUTPUT_SHAPE_EXAMPLE}
        """
    ).strip()


def _execute_joke_prompt(state: PlanState, plan_dir: Path, root: Path | None = None) -> str:
    project_dir = Path(state["config"]["project_dir"])
    output_path = state["config"].get("output_path", "output.md")
    primary_criterion = _primary_criterion(state)
    prep_block, prep_instruction = _render_prep_block(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    checkpoint_path = str(plan_dir / "execution_checkpoint.json")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = read_json(plan_dir / "gate.json")
    robustness = configured_robustness(state)
    prior_review_block = _execute_review_block(plan_dir)
    rerun_guidance = _execute_rerun_guidance(plan_dir, finalize_data)
    approval_note = _execute_approval_note(state)
    execution_nudges = _execute_nudges(finalize_data, plan_dir, root)
    requirements_block = _execute_joke_requirements(checkpoint_path)
    return textwrap.dedent(
        f"""
        Author the planned joke-mode scene prose.

        Project directory:
        {project_dir}

        Output path (write the scene here):
        {output_path}

        Primary criterion:
        {primary_criterion}

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

        {prior_review_block}

        {rerun_guidance}

        {approval_note}
        Robustness level: {robustness}.

        {requirements_block}

        {execution_nudges}
        """
    ).strip()


def _execute_joke_batch_prompt(
    state: PlanState,
    plan_dir: Path,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None = None,
    root: Path | None = None,
) -> str:
    completed = set(completed_task_ids or set())
    output_path = state["config"].get("output_path", "output.md")
    primary_criterion = _primary_criterion(state)
    finalize_data = read_json(plan_dir / "finalize.json")
    all_tasks = finalize_data.get("tasks", [])
    tasks_by_id = {
        task["id"]: task
        for task in all_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    batch_tasks = [tasks_by_id[task_id] for task_id in batch_task_ids if task_id in tasks_by_id]
    completed_tasks = [
        task for task_id, task in tasks_by_id.items() if task_id in completed and task_id not in set(batch_task_ids)
    ]
    batch_sense_checks = [
        sense_check
        for sense_check in finalize_data.get("sense_checks", [])
        if sense_check.get("task_id") in set(batch_task_ids)
    ]
    batch_sense_check_ids = [
        sense_check["id"] for sense_check in batch_sense_checks if isinstance(sense_check.get("id"), str)
    ]
    global_batches = compute_task_batches(all_tasks)
    batch_number = next((index + 1 for index, batch in enumerate(global_batches) if batch == batch_task_ids), 1)
    batch_total = len(global_batches) or 1
    checkpoint_path = str(batch_artifact_path(plan_dir, batch_number))
    prior_batch_deviations = "None"
    if batch_number > 1:
        prior_batch_artifact = batch_artifact_path(plan_dir, batch_number - 1)
        if prior_batch_artifact.exists():
            try:
                prior_batch_payload = read_json(prior_batch_artifact)
            except (OSError, ValueError):
                prior_batch_payload = {}
            raw_deviations = prior_batch_payload.get("deviations", [])
            if isinstance(raw_deviations, list):
                deviations = [item for item in raw_deviations if isinstance(item, str)]
                if deviations:
                    prior_batch_deviations = json_dump(deviations).strip()
    approval_note = _execute_approval_note(state)
    debt_watch_items = _debt_watch_lines(plan_dir, root)
    debt_watch_block = (
        "\n".join(["Debt watch items (do not make these worse):", *[f"- {item}" for item in debt_watch_items]])
        if debt_watch_items
        else "Debt watch items (do not make these worse):\n- None."
    )
    return textwrap.dedent(
        f"""
        Author the planned joke-mode scene prose.

        Project directory:
        {Path(state["config"]["project_dir"])}

        Output path (write the scene here):
        {output_path}

        Primary criterion:
        {primary_criterion}

        {intent_and_notes_block(state)}

        Batch framing:
        - Execute batch {batch_number} of {batch_total}.
        - Actionable task IDs for this batch: {batch_task_ids}
        - Already completed task IDs available as dependency context: {sorted(completed)}

        Actionable tasks for this batch:
        {json_dump(batch_tasks).strip()}

        Completed task context (already satisfied, do not re-execute unless directly required by current edits):
        {json_dump(completed_tasks).strip()}

        Prior batch deviations (address if applicable):
        {prior_batch_deviations}

        Batch-scoped sense checks:
        {json_dump(batch_sense_checks).strip()}

        Full execution tracking source of truth (`finalize.json`):
        {json_dump(finalize_data).strip()}

        {debt_watch_block}

        {approval_note}
        Robustness level: {configured_robustness(state)}.

        Requirements:
        - You are a screenwriter authoring a single scene.
        - Execute only the actionable tasks in this batch.
        - Treat completed tasks as dependency context, not new work.
        - Return structured JSON only.
        - Only produce `task_updates` for these tasks: [{", ".join(batch_task_ids)}]
        - Only produce `sense_check_acknowledgments` for these sense checks: [{", ".join(batch_sense_check_ids)}]
        - Do not include updates for tasks or sense checks outside this batch.
        - Keep `executor_notes` verification-focused.
        - Best-effort progress checkpointing: if `{checkpoint_path}` is writable, checkpoint task and sense-check updates there (not `finalize.json`). The harness owns `finalize.json`.
        - `sections_written` means scene-beat IDs such as `opening`, `inciting`, `obstacle`, `turn`, and `button`.
        - The final artifact written to `{output_path}` must be scene prose, not an outline or task list.
        - Follow this JSON shape:
        {_EXECUTE_JOKE_OUTPUT_SHAPE_EXAMPLE}
        """
    ).strip()


__all__ = ["_execute_joke_prompt", "_execute_joke_batch_prompt"]
