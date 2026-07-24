"""Doc-mode execute prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import (
    execute_batch_artifact_path,
    resolve_batch_artifact,
    compute_task_batches,
    configured_robustness,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    read_json,
)
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
    _completed_task_receipts_for_prompt,
    _execute_approval_note,
    _execute_nudges,
    _execute_rerun_guidance,
    _execute_review_block,
    _extract_execution_order_summary,
    _render_settled_decisions_brief,
)

_EXECUTE_DOC_OUTPUT_SHAPE_EXAMPLE = textwrap.dedent(
    """
    ```json
    {
      "output": "Authored the planned document sections.",
      "files_changed": [],
      "commands_run": [],
      "deviations": [],
      "task_updates": [
        {
          "task_id": "T1",
          "status": "done",
          "executor_notes": "Wrote the introduction section covering project motivation and scope.",
          "sections_written": ["introduction"]
        },
        {
          "task_id": "T2",
          "status": "done",
          "executor_notes": "Drafted the problem statement with three concrete examples from the codebase.",
          "sections_written": ["problem-statement"]
        },
        {
          "task_id": "T3",
          "status": "skipped",
          "executor_notes": "Skipped because the milestones depend on unresolved scope questions.",
          "sections_written": []
        }
      ],
      "sense_check_acknowledgments": [
        {
          "sense_check_id": "SC1",
          "executor_note": "Confirmed the introduction names the target audience and links to prior art."
        }
      ]
    }
    ```
    """
).strip()

_EXECUTE_DOC_REQUIREMENTS_TEMPLATE = textwrap.dedent(
    """
    Requirements:
    - You are an author, not a coder. Your deliverable is document text, not code changes.
    - Write each assigned section to the configured output path. This is the only file you should create or modify.
    - The configured output path shown above under "Output path" is AUTHORITATIVE. If the plan's per-step instructions name a different filename (for example, a kebab-cased variant of the title), ignore that filename and write to the configured output path instead. Report the discrepancy in `executor_notes` so the plan can be corrected, but do not write to the alternate path.
    - Adapt if the document structure needs adjustment — report deviations explicitly.
    - Do not over-engineer beyond what the plan prescribes.
    - Output concrete sections written per task. `sections_written` means section IDs you authored — not sections you read or referenced.
    - Use the tasks in `finalize.json` as the execution boundary.
    {checkpoint_requirements}
    - Structured output remains the authoritative final summary for this step. Disk writes are progress checkpoints for timeout recovery only.
    - Return `task_updates` with one object per completed or skipped task.
    - `task_updates[].status` must be either `done` or `skipped`. Never return `pending` in execute output.
    - Return `sense_check_acknowledgments` with one object per sense check.
    - Keep `executor_notes` verification-focused: explain why the section content is correct and complete.
    - When the document contains design decisions, emit a top-level `## Settled Decisions` section. Either shape below is accepted; prefer the bold-dash inline form for short decisions:
      ```md
      ## Settled Decisions

      - **SD-001** \u2014 Keep the current storage model. _load_bearing: true_
        Rationale: External integrations depend on it.
      ```
      Or the YAML-ish shape:
      ```md
      ## Settled Decisions
      - id: SD-001
        load_bearing: true
        decision: Keep the current storage model
        rationale: External integrations depend on it.
      ```
    - Downstream plans can import these via `megaplan init --from-doc`.
    - Follow this JSON shape exactly:
    {output_shape}
    """
).strip()


def _prior_doc_context_block(state: PlanState) -> str:
    from_doc = state["config"].get("from_doc")
    if not from_doc:
        return ""
    imported_decisions = state["meta"].get("imported_decisions", [])
    lines = [
        "Prior doc context:",
        "Prior doc imported via --from-doc:",
        str(from_doc),
        f"Imported decisions (from the source doc's ## Settled Decisions section): {len(imported_decisions)}",
    ]
    if imported_decisions:
        lines.append("Imported decision details:")
        for decision in imported_decisions:
            lines.extend(
                [
                    f"- {decision.get('id', '')}: {decision.get('decision', '')}",
                    f"  rationale: {decision.get('rationale', '')}",
                    f"  load_bearing: {decision.get('load_bearing', False)}",
                ]
            )
    return "\n".join(lines)


def _execute_doc_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
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
    robustness = configured_robustness(state)
    prior_review_block = _execute_review_block(
        plan_dir,
        capabilities=projection_capabilities,
    )
    rerun_guidance = _execute_rerun_guidance(plan_dir, finalize_data)
    approval_note = _execute_approval_note(state)
    execution_nudges = _execute_nudges(finalize_data, plan_dir, root)
    prior_doc_block = _prior_doc_context_block(state)
    requirements_block = _EXECUTE_DOC_REQUIREMENTS_TEMPLATE.format(
        checkpoint_path=checkpoint_path,
        checkpoint_requirements=_checkpoint_requirements(
            checkpoint_path,
            projection_capabilities,
        ),
        output_shape=_EXECUTE_DOC_OUTPUT_SHAPE_EXAMPLE,
    )
    return textwrap.dedent(
        f"""
        Author the planned document sections.

        Project directory:
        {project_dir}

        Output path (write all sections here):
        {output_path}

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

        {prior_review_block}

        {rerun_guidance}

        {approval_note}
        Robustness level: {robustness}.

        {prior_doc_block}

        {requirements_block}

        {execution_nudges}
        """
    ).strip()


def _execute_doc_batch_prompt(
    state: PlanState,
    plan_dir: Path,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None = None,
    root: Path | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    completed = set(completed_task_ids or set())
    output_path = state["config"].get("output_path", "output.md")
    finalize_data = read_json(plan_dir / "finalize.json")
    projected_finalize = project_execute_context(
        finalize_data,
        capabilities=projection_capabilities,
    )
    all_tasks = finalize_data.get("tasks", [])
    projected_tasks = projected_finalize.get("tasks", [])
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
    completed_task_receipts = _completed_task_receipts_for_prompt(
        finalize_data,
        plan_dir=plan_dir,
        batch_task_ids=batch_task_ids,
        completed_task_ids=completed,
        projection_capabilities=projection_capabilities,
    )
    projected_sense_checks = projected_finalize.get("sense_checks", [])
    batch_sense_checks = [
        sense_check
        for sense_check in projected_sense_checks
        if sense_check.get("task_id") in set(batch_task_ids)
    ]
    batch_sense_check_ids = [
        sense_check["id"]
        for sense_check in batch_sense_checks
        if isinstance(sense_check.get("id"), str)
    ]
    global_batches = compute_task_batches(all_tasks)
    batch_number = next(
        (
            index + 1
            for index, batch in enumerate(global_batches)
            if batch == batch_task_ids
        ),
        1,
    )
    batch_total = len(global_batches) or 1
    checkpoint_path = str(
        execute_batch_artifact_path(plan_dir, batch_number, batch_task_ids)
    )
    prior_batch_deviations = "None"
    if batch_number > 1:
        prior_batch_artifact = resolve_batch_artifact(plan_dir, batch_number - 1)
        if prior_batch_artifact is not None:
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
    prior_doc_block = _prior_doc_context_block(state)
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
        Author the planned document sections.

        Project directory:
        {Path(state["config"]["project_dir"])}

        Output path (write all sections here):
        {output_path}

        {intent_and_notes_block(state)}

        Batch framing:
        - Execute batch {batch_number} of {batch_total}.
        - Actionable task IDs for this batch: {batch_task_ids}
        - Completed task records are represented only by bounded dependency receipts below.

        Actionable tasks for this batch:
        {json_dump(batch_tasks).strip()}

        Completed dependency receipts (already satisfied, do not re-execute):
        {json_dump(completed_task_receipts).strip()}

        Prior batch deviations (address if applicable):
        {prior_batch_deviations}

        Batch-scoped sense checks:
        {json_dump(batch_sense_checks).strip()}

        {execution_context}

        {approval_note}
        Robustness level: {configured_robustness(state)}.

        {prior_doc_block}

        Requirements:
        - You are an author. Write document sections to the configured output path.
        - Execute only the actionable tasks in this batch.
        - Treat completed tasks as dependency context, not new work.
        - If dependency receipts report omitted evidence, inspect their `source_artifact`; if it is unavailable, mark the affected task blocked instead of guessing.
        - Return structured JSON only.
        - Only produce `task_updates` for these tasks: [{", ".join(batch_task_ids)}]
        - Only produce `sense_check_acknowledgments` for these sense checks: [{", ".join(batch_sense_check_ids)}]
        - Do not include updates for tasks or sense checks outside this batch.
        - Keep `executor_notes` verification-focused.
        - {_checkpoint_summary_requirement(checkpoint_path, projection_capabilities)}
        - `sections_written` replaces `files_changed` in task_updates. List the section IDs you authored, not file paths.
        - When the document contains design decisions, emit a top-level `## Settled Decisions` section. Either shape below is accepted; prefer the bold-dash inline form for short decisions:
          ```md
          ## Settled Decisions

          - **SD-001** — Keep the current storage model. _load_bearing: true_
            Rationale: External integrations depend on it.
          ```
          Or the YAML-ish shape:
          ```md
          ## Settled Decisions
          - id: SD-001
            load_bearing: true
            decision: Keep the current storage model
            rationale: External integrations depend on it.
          ```
        - Downstream plans can import these via `megaplan init --from-doc`.
        - Follow this JSON shape:
        {_EXECUTE_DOC_OUTPUT_SHAPE_EXAMPLE}
        """
    ).strip()
