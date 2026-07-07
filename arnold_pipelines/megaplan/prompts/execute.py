"""Execute-phase prompt builders and helpers."""

from __future__ import annotations

import textwrap
import re
import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import (
    execute_batch_artifact_path,
    resolve_batch_artifact,
    compute_task_batches,
    configured_robustness,
    intent_brief_reference,
    json_dump,
    latest_plan_path,
    latest_plan_meta_path,
    read_json,
)
from arnold_pipelines.megaplan.resolution_contract import (
    FALLBACK_STATES,
    HARD_BLOCK_STATES,
    resolution_applies_to_task,
)
from arnold_pipelines.megaplan.resolutions import load_user_action_resolutions
from arnold_pipelines.megaplan.types import PlanState

from ._projection import (
    PromptProjectionCapabilities,
    project_execute_context,
    project_rework_context,
)
from ._shared import _gate_summary_or_skipped, _render_prep_block

_EXECUTE_OUTPUT_SHAPE_EXAMPLE = textwrap.dedent(
    """
    ```json
    {
      "output": "Implemented the approved plan and captured execution evidence.",
      "files_changed": ["megaplan/handlers.py", "megaplan/evaluation.py"],
      "commands_run": ["pytest tests/test_megaplan.py -k evidence"],
      "deviations": [],
      "task_updates": [
        {
          "task_id": "T6",
          "status": "done",
          "executor_notes": "Caught the empty-strings edge case while checking execution evidence: blank `commands_run` entries still leave the task uncovered, so the missing-evidence guard behaves correctly.",
          "files_changed": ["megaplan/handlers.py"],
          "commands_run": ["pytest tests/test_megaplan.py -k execute"]
        },
        {
          "task_id": "T7",
          "status": "done",
          "executor_notes": "Confirmed the happy path still records task evidence after the prompt updates by rerunning focused tests and checking the tracked task summary stayed intact.",
          "files_changed": ["megaplan/prompts.py"],
          "commands_run": ["pytest tests/test_prompts.py -k review"]
        },
        {
          "task_id": "T8",
          "status": "done",
          "executor_notes": "Kept the rubber-stamp thresholds centralized in evaluation so sense checks and reviewer verdicts share one policy entry point while still using different strictness levels.",
          "files_changed": ["megaplan/evaluation.py"],
          "commands_run": ["pytest tests/test_evaluation.py -k rubber_stamp"]
        },
        {
          "task_id": "T11",
          "status": "skipped",
          "executor_notes": "Skipped because upstream work is not ready yet; no repo changes were made for this task.",
          "files_changed": [],
          "commands_run": []
        }
      ],
      "sense_check_acknowledgments": [
        {
          "sense_check_id": "SC6",
          "executor_note": "Confirmed execute only blocks when both files_changed and commands_run are empty for a done task."
        }
      ]
    }
    ```
    """
).strip()


_EXECUTE_REQUIREMENTS_TEMPLATE = textwrap.dedent(
    """
    Requirements:
    - Implement the intent, not just the text.
    - Adapt if repository reality contradicts the plan.
    - Report deviations explicitly.
    - Do not over-engineer beyond what the plan prescribes — no str() wraps, .get() fallbacks, or try/except guards unless the plan called for them or you found a concrete reason.
    - Do NOT fix unrelated issues you encounter (e.g., dependency compatibility, Python version workarounds). Only change files directly needed for the task. If tests need updating, only update tests that are directly related to your fix.
    - If you cannot build the project from source (e.g., C extension compilation failures), report the build failure explicitly. Do NOT fall back to testing against an installed or cached package — that tests the wrong codebase and produces false positives.
    - If you cannot verify your changes (tests missing or unrunnable), treat this as high risk — re-examine your implementation with extra scrutiny instead of accepting it on faith.
    - If tests fail, read the traceback carefully. Diagnose WHY — don't just retry. Common causes: wrong function/method used, missing import, incorrect type, edge case not handled. Fix the root cause, then re-run.
    - When verifying changes, run the entire test file or module (e.g., `pytest tests/test_foo.py`), not individual test functions. Individual tests miss regressions in the same module.
    - Run tests ONCE, in the FOREGROUND, and wait for them to finish. You have a large time budget (~2h). Do NOT background a long test run and poll it in a loop.
    - Slowness is NOT a stall. A large suite legitimately takes many minutes; never relaunch a test command because it "seems stuck" — relaunching just creates CPU-contending duplicate runs that make everything slower. Never run more than one heavy test invocation at a time.
    - Prefer scoping tests to the changed files. Only run the full suite when the task explicitly requires it (e.g. a final-validation task), and then run it exactly once.
    - finalize.json includes baseline_test_failures — a list of test IDs that were already failing before your changes. If a test fails and its ID appears in baseline_test_failures, it is pre-existing — do not scope-creep into fixing it. If baseline_test_failures is null, the baseline could not be captured; use your judgment but err on the side of assuming failures are regressions. A mechanical post-execute suite run by the harness — not you — is the authoritative regression check. Run tests for your own fix loop if needed, then stop; do not loop the suite to make pre-existing failures pass.
    - Before declaring the work complete, write a short script (not a full test) that reproduces the exact bug or incorrect behavior described in the task. Run it to confirm the fix resolves the issue. Then delete the script so it does not appear in the final diff. If the task description is too vague to write a concrete reproduction, note this explicitly in executor_notes.
    - Output concrete files changed and commands run. `files_changed` means files you WROTE or MODIFIED — not files you read or verified. Only list files where you made actual edits.
    - Use the tasks in `finalize.json` as the execution boundary.
    {checkpoint_requirements}
    - Structured output remains the authoritative final summary for this step. Disk writes are progress checkpoints for timeout recovery only.
    - Return `task_updates` with one object per completed or skipped task.
    - `task_updates[].status` may be `done`, `skipped`, or `pending`. Return `pending` when the task has real progress but you need to hand back for another batch (for example, a multi-step change that requires a separate tool call after a long-running command). The orchestrator will call you again with the remaining work. Do not use `pending` to avoid producing evidence for a task you could complete now.
    - Multi-task batches: treat the batch as a checklist, not one undifferentiated problem. First write out the task list; then complete and evidence the tasks one at a time. Emit a SEPARATE `task_updates` entry per task carrying that task's own concrete evidence (its real `files_changed` and command output) — never summarize across tasks or reuse one task's evidence for another. If you find yourself about to report several tasks `done` without distinct per-task evidence, stop: produce the evidence, or mark the unfinished ones `skipped`/blocked with the reason.
    - If a task is blocked by environment limits, missing devices, or manual-only validation that cannot happen in this session, return `status: "skipped"` and explain the remaining manual follow-up in `executor_notes` and `deviations`.
    - Return `sense_check_acknowledgments` with one object per sense check.
    - Keep `executor_notes` verification-focused: explain why your changes are correct. The diff already shows what changed; notes should cover edge cases caught, expected behaviors confirmed, or design choices made.
    - Follow this JSON shape exactly:
    {output_shape}
    """
).strip()


def _execute_review_block(
    plan_dir: Path,
    capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    review_path = plan_dir / "review.json"
    if not review_path.exists():
        return "No prior `review.json` exists. Treat this as the first execution pass."
    review_data = read_json(review_path)
    return textwrap.dedent(
        f"""
        Previous review findings to address on this execution pass (`review.json`, prompt projection only):
        {json_dump(project_rework_context(review_data, capabilities=capabilities)).strip()}
        """
    ).strip()


def _execute_nudges(
    finalize_data: dict[str, Any], plan_dir: Path | None = None, root: Path | None = None
) -> str:
    nudge_lines: list[str] = []
    sense_checks = finalize_data.get("sense_checks", [])
    if sense_checks:
        nudge_lines.append(
            "Sense checks to keep in mind during execution (reviewer will verify these):"
        )
        for sense_check in sense_checks:
            nudge_lines.append(
                f"- {sense_check['id']} ({sense_check['task_id']}): {sense_check['question']}"
            )
    watch_items = finalize_data.get("watch_items", [])
    if watch_items:
        nudge_lines.append("Watch items to keep visible during execution:")
        for item in watch_items:
            nudge_lines.append(f"- {item}")
    return "\n".join(nudge_lines)


def _execute_rerun_guidance(plan_dir: Path, finalize_data: dict[str, Any]) -> str:
    tasks = finalize_data.get("tasks", [])
    done_tasks = [task for task in tasks if task.get("status") in ("done", "skipped")]
    pending_tasks = [task for task in tasks if task.get("status") == "pending"]
    if done_tasks and pending_tasks:
        done_ids = ", ".join(task["id"] for task in done_tasks)
        pending_ids = ", ".join(task["id"] for task in pending_tasks)
        return (
            f"Re-execution: {len(done_tasks)} tasks already tracked ({done_ids}). "
            f"Focus on the {len(pending_tasks)} remaining tasks ({pending_ids}). "
            "You must still return task_updates for ALL tasks (including already-tracked ones) — "
            "for previously done tasks, preserve their existing status and notes."
        )
    if done_tasks and not pending_tasks:
        review_data = (
            read_json(plan_dir / "review.json")
            if (plan_dir / "review.json").exists()
            else {}
        )
        rework_items = review_data.get("rework_items", [])
        if rework_items:
            rework_lines = []
            for item in rework_items:
                if not isinstance(item, dict):
                    continue
                task_id = item.get("task_id", "?")
                issue = item.get("issue", "")
                expected = item.get("expected", "")
                actual = item.get("actual", "")
                evidence = item.get("evidence_file", "")
                entry = f"  - [{task_id}] {issue}"
                if expected:
                    entry += f"\n    expected: {expected}"
                if actual:
                    entry += f"\n    actual: {actual}"
                if evidence:
                    entry += f"\n    evidence: {evidence}"
                rework_lines.append(entry)
            issue_list = "\n".join(rework_lines)
        else:
            review_issues = review_data.get("issues", [])
            issue_list = (
                "\n".join(f"  - {issue}" for issue in review_issues)
                if review_issues
                else "  (see review.json above for details)"
            )
        return (
            "REWORK REQUIRED: all tasks are already tracked but the reviewer kicked this back.\n"
            f"Review issues to fix:\n{issue_list}\n\n"
            "You MUST make code changes to address each issue — do not return success without modifying files. "
            "For each issue, either fix it and list the file in files_changed, or explain in deviations why no change is needed with line-level evidence. "
            "Return task_updates for all tasks with updated evidence."
        )
    return ""


def _execute_rework_targeting_block(
    rework_context: dict[str, Any] | None,
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    if not isinstance(rework_context, dict):
        return ""
    projected_rework = project_rework_context(
        rework_context,
        capabilities=capabilities,
    )
    items = projected_rework.get("rework_items", [])
    if not isinstance(items, list) or not items:
        return ""
    milestone_files = rework_context.get("milestone_changed_files", [])
    if not isinstance(milestone_files, list):
        milestone_files = []
    scope_files = rework_context.get("scope_files", [])
    if not isinstance(scope_files, list):
        scope_files = []
    return textwrap.dedent(
        f"""
        Review rework targeting:
        The reviewer requested a focused rework pass. Fix the named issues below using read/grep tools and focused commands; do not broadly re-run unrelated execution work.

        Failing rework_items for this batch:
        {json_dump(items).strip()}

        Bounded search scope:
        {json_dump(scope_files).strip()}

        Milestone changed-file set:
        {json_dump(milestone_files).strip()}

        Rework requirements:
        - Start with each item's `evidence_file` when present.
        - If an item lacks `evidence_file`, search within the milestone changed-file set above.
        - Address each item's `issue`, `expected`, and `actual` directly in the named files or explain with line-level evidence why no code change is needed.
        """
    ).strip()


def _execute_approval_note(state: PlanState) -> str:
    if state["config"].get("auto_approve"):
        return (
            "Note: User chose auto-approve mode. This execution was not manually "
            "reviewed at the gate. Exercise extra caution on destructive operations."
        )
    if state["meta"].get("user_approved_gate"):
        return "Note: User explicitly approved this plan at the gate checkpoint."
    return "Note: Review mode is enabled. Execute should only be running after explicit gate approval."


def _brief_text(value: Any, *, limit: int) -> str:
    text = value if isinstance(value, str) else ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _checkpoint_requirements(
    checkpoint_path: str,
    capabilities: PromptProjectionCapabilities | None,
) -> str:
    caps = capabilities if capabilities is not None else PromptProjectionCapabilities.full()
    if not caps.checkpoint_write_access:
        return (
            f"- Do NOT attempt checkpoint writes for this run. This worker cannot write "
            f"`{checkpoint_path}`, so rely on the structured output below."
        )
    return "\n".join(
        [
            f"- Best-effort progress checkpointing: if `{checkpoint_path}` is writable, then after each completed task read the full file, update that task's `status`, `executor_notes`, `files_changed`, and `commands_run`, and write the full file back. Do NOT write to `finalize.json` directly — the harness owns that file.",
            f"- Best-effort sense-check checkpointing: if `{checkpoint_path}` is writable, then after each sense check acknowledgment read the full file again, update that sense check's `executor_note`, and write the full file back.",
            f"- Always use full read-modify-write updates for `{checkpoint_path}` instead of partial edits. If the sandbox blocks writes, continue execution and rely on the structured output below.",
        ]
    )


def _checkpoint_summary_requirement(
    checkpoint_path: str,
    capabilities: PromptProjectionCapabilities | None,
) -> str:
    caps = capabilities if capabilities is not None else PromptProjectionCapabilities.full()
    if not caps.checkpoint_write_access:
        return (
            f"Do not attempt checkpoint writes for this run. This worker cannot write "
            f"`{checkpoint_path}`; rely on structured output instead."
        )
    return (
        f"Best-effort progress checkpointing: if `{checkpoint_path}` is writable, "
        "checkpoint task and sense-check updates there (not `finalize.json`). "
        "The harness owns `finalize.json`."
    )


def _render_settled_decisions_brief(gate_carry: dict[str, Any]) -> str:
    decisions = gate_carry.get("settled_decisions", [])
    if not isinstance(decisions, list):
        return "- None provided."

    lines: list[str] = []
    for index, item in enumerate(decisions[:3], start=1):
        if isinstance(item, str):
            decision_id = f"SD{index}"
            decision = item
            rationale = ""
        elif isinstance(item, dict):
            raw_id = item.get("id")
            decision_id = raw_id if isinstance(raw_id, str) and raw_id else f"SD{index}"
            decision = item.get("decision", "")
            rationale = item.get("rationale", "")
        else:
            continue
        decision_text = _brief_text(decision, limit=180)
        if not decision_text:
            continue
        rationale_text = _brief_text(rationale, limit=220)
        if rationale_text:
            lines.append(f"- {decision_id}: {decision_text} - {rationale_text}")
        else:
            lines.append(f"- {decision_id}: {decision_text}")
    return "\n".join(lines) if lines else "- None provided."


def _extract_execution_order_summary(latest_plan_text: str) -> str:
    match = re.search(
        r"(?ms)^## Execution Order\s*\n(?P<body>.*?)(?=^##\s+|\Z)",
        latest_plan_text,
    )
    if not match:
        return "(none specified)"
    body = match.group("body").strip()
    if not body:
        return "(none specified)"
    return body[:800].rstrip()


def _format_user_action_guidance(
    finalize_data: dict[str, Any],
    resolutions: dict[str, dict[str, Any]],
    relevant_task_ids: list[str],
) -> tuple[str, str]:
    """Build resolution-aware prerequisite and guidance blocks for *relevant_task_ids*.

    Returns ``(prerequisite_block, resolution_guidance_block)`` — both are
    ready-to-embed strings (or empty strings when there is nothing to report).
    """
    # Build the blocking-task → user-actions mapping from finalize.json.
    user_actions_by_blocking_task: dict[str, list[dict[str, Any]]] = {}
    for action in finalize_data.get("user_actions", []):
        if not isinstance(action, dict):
            continue
        blocks_task_ids = action.get("blocks_task_ids", [])
        if not isinstance(blocks_task_ids, list):
            continue
        for task_id in blocks_task_ids:
            if isinstance(task_id, str):
                user_actions_by_blocking_task.setdefault(task_id, []).append(action)

    prerequisite_lines: list[str] = []
    resolution_guidance_lines: list[str] = []

    for task_id in relevant_task_ids:
        for action in user_actions_by_blocking_task.get(task_id, []):
            action_id = action.get("id", "unknown")
            description = action.get("description", "")
            resolution = resolutions.get(action_id)
            applies = resolution_applies_to_task(resolution, task_id, source="disk")

            if applies and isinstance(resolution, dict):
                state = resolution.get("state", "")
                if state == "rejected":
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: This task depends on user action {action_id}: "
                        f"{description}. Resolution state is rejected. "
                        f"This plan cannot continue. Mark this task blocked."
                    )
                elif state in FALLBACK_STATES:
                    fallback_mode = resolution.get("fallback_mode", "")
                    reason = resolution.get("reason", "")
                    instructions = resolution.get("instructions", "")
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: User action {action_id} ({description}) "
                        f"is resolved as {state}. FALLBACK MODE: {fallback_mode or 'proceed'}. "
                        f"Reason: {reason or 'no reason provided'}. "
                        f"{instructions or 'No specific fallback instructions provided.'}"
                    )
                    resolution_guidance_lines.append(
                        f"Resolution guidance for {action_id} ({state}): "
                        f"Supersedes the generic before_execute STOP — proceed with fallback."
                    )
                elif state == "satisfied":
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: User action {action_id} ({description}) "
                        f"is resolved as satisfied. Verify mechanically if possible, then proceed."
                    )
                    resolution_guidance_lines.append(
                        f"Resolution guidance for {action_id} (satisfied): "
                        f"Action marked as resolved. Confirm with a quick check and continue."
                    )
                elif state in HARD_BLOCK_STATES or state == "manual_required":
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: This task depends on user action {action_id}: "
                        f"{description}. Resolution state is {state}. "
                        f"If {action_id} is not complete, mark this task blocked with reason "
                        f"`awaiting {action_id}` rather than attempting it."
                    )
                else:
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: This task depends on user action {action_id}: "
                        f"{description}. If {action_id} is not complete (verify if possible — grep .env, "
                        f"curl, etc.), mark this task blocked with reason `awaiting {action_id}` rather "
                        "than attempting it."
                    )
            else:
                if isinstance(resolution, dict) and not applies:
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: This task depends on user action {action_id}: "
                        f"{description}. (Resolution for {action_id} is scoped to other tasks — "
                        f"this task still requires the action to be complete.) "
                        f"If {action_id} is not complete, mark this task blocked."
                    )
                else:
                    prerequisite_lines.append(
                        f"PREREQUISITE for {task_id}: This task depends on user action {action_id}: "
                        f"{description}. If {action_id} is not complete (verify if possible — grep .env, "
                        f"curl, etc.), mark this task blocked with reason `awaiting {action_id}` rather "
                        "than attempting it."
                    )

    prerequisite_block = (
        "\n".join(prerequisite_lines)
        if prerequisite_lines
        else "No user_action prerequisites for this batch."
    )
    resolution_guidance_block = (
        "\n".join(
            ["Resolution guidance (supersedes before_execute STOP for accepted/waived/satisfied):"]
            + resolution_guidance_lines
        )
        if resolution_guidance_lines
        else ""
    )

    return prerequisite_block, resolution_guidance_block


def _execute_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
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
    requirements_block = _EXECUTE_REQUIREMENTS_TEMPLATE.format(
        checkpoint_path=checkpoint_path,
        checkpoint_requirements=_checkpoint_requirements(
            checkpoint_path,
            projection_capabilities,
        ),
        output_shape=_EXECUTE_OUTPUT_SHAPE_EXAMPLE,
    )

    # Build resolution-aware guidance for ALL finalize tasks (not batch-dependent).
    all_tasks = finalize_data.get("tasks", [])
    all_task_ids = [
        task["id"]
        for task in all_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    ]
    resolutions = load_user_action_resolutions(plan_dir)
    prerequisite_block, resolution_guidance_block = _format_user_action_guidance(
        finalize_data, resolutions, all_task_ids
    )

    prompt = textwrap.dedent(
        f"""
        Execute the approved plan in the repository.

        Project directory:
        {project_dir}

        {prep_block}

        {prep_instruction}

        {intent_brief_reference(state)}

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

        User action prerequisites:
        {prerequisite_block}
        {resolution_guidance_block}

        {approval_note}
        Robustness level: {robustness}.

        {requirements_block}

        {execution_nudges}
        """
    ).strip()
    return prompt


def _execute_batch_prompt(
    state: PlanState,
    plan_dir: Path,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None = None,
    root: Path | None = None,
    rework_context: dict[str, Any] | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
    batch_template_path: Path | None = None,
) -> str:
    completed = set(completed_task_ids or set())
    finalize_data = read_json(plan_dir / "finalize.json")
    projected_finalize = project_execute_context(
        finalize_data,
        capabilities=projection_capabilities,
    )
    all_tasks = finalize_data.get("tasks", [])
    projected_tasks = projected_finalize.get("tasks", [])
    tasks_by_id = {
        task["id"]: task
        for task in all_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
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
    if batch_template_path is None:
        batch_template_path = plan_dir / f"execute_batch_{batch_number}_output.json"
        if not batch_template_path.exists():
            _write_execute_batch_template(
                plan_dir,
                batch_number,
                batch_task_ids,
                batch_sense_check_ids,
            )
    try:
        batch_template = batch_template_path.read_text(encoding="utf-8")
    except OSError:
        batch_template = json_dump(
            _execute_batch_template_payload(
                batch_task_ids,
                batch_sense_check_ids,
            )
        ).strip()
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
    # Load resolutions and build resolution-aware prerequisite text.
    resolutions = load_user_action_resolutions(plan_dir)
    prerequisite_block, resolution_guidance_block = _format_user_action_guidance(
        finalize_data, resolutions, batch_task_ids
    )
    approval_note = _execute_approval_note(state)
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
    rework_targeting_block = _execute_rework_targeting_block(
        rework_context,
        capabilities=projection_capabilities,
    )
    if rework_targeting_block:
        rework_targeting_block = f"\n\n{rework_targeting_block}"
    template_reference = (
        f"Template file already written for reference: {batch_template_path}"
        if projection_capabilities is None or projection_capabilities.can_read_plan_dir
        else "Template contents are embedded below for workers without plan-directory file access."
    )
    prompt = textwrap.dedent(
        f"""
        Execute the approved plan in the repository.

        Project directory:
        {Path(state["config"]["project_dir"])}

        {intent_brief_reference(state)}

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

        User action prerequisites:
        {prerequisite_block}
        {resolution_guidance_block}

        Batch-scoped sense checks:
        {json_dump(batch_sense_checks).strip()}
        {rework_targeting_block}

        {execution_context}

        {approval_note}
        Robustness level: {configured_robustness(state)}.

        Requirements:
        - Execute only the actionable tasks in this batch.
        - Treat completed tasks as dependency context, not new work.
        - Return structured JSON only.
        - Fill in the following template and return it as your JSON response. Only update the entries for this batch's tasks/sense checks.
        - {template_reference}
        - Only produce `task_updates` for these tasks: [{", ".join(batch_task_ids)}]
        - `task_updates[].status` must be one of `done`, `skipped`, `completed`, or `blocked`; never `pending` or `in_progress`.
        - Only produce `sense_check_acknowledgments` for these sense checks: [{", ".join(batch_sense_check_ids)}]
        - Do not include updates for tasks or sense checks outside this batch.
        - Some prior file lists may be capped prompt projections with `items`, `omitted_count`, and `full_set_artifact_ref`; use the artifact reference when you need the full set.
        - Keep `executor_notes` verification-focused.
        - {_checkpoint_summary_requirement(checkpoint_path, projection_capabilities)}
        - When verifying changes, run the entire test file or module, not individual test functions. Individual tests miss regressions.
        - Run tests ONCE, in the FOREGROUND, and wait for them to finish (you have a large time budget). Do NOT background a long test run and poll it in a loop. Slowness is NOT a stall — never relaunch a test command because it "seems stuck"; duplicate concurrent runs contend for CPU and make everything slower. Never run more than one heavy test invocation at a time. Prefer scoping to the changed files; run the full suite only when the task explicitly requires it, and then exactly once.
        - finalize.json includes baseline_test_failures — a list of test IDs that were already failing before your changes. If a test fails and its ID appears in baseline_test_failures, it is pre-existing — do not scope-creep into fixing it. If baseline_test_failures is null, the baseline could not be captured; use your judgment but err on the side of assuming failures are regressions. A mechanical post-execute suite run by the harness — not you — is the authoritative regression check. Run tests for your own fix loop if needed, then stop; do not loop the suite to make pre-existing failures pass.
        - If this batch includes the final verification task, write a short script that reproduces the exact bug described in the task, run it to confirm the fix resolves it, then delete the script.

        Batch JSON response template:
        ```json
        {batch_template.strip()}
        ```
        """
    ).strip()
    return prompt


def _execute_batch_template_payload(
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
) -> dict[str, object]:
    return {
        "output": "",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [
            {
                "task_id": task_id,
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "auto_attributed_files": False,
            }
            for task_id in batch_task_ids
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": sense_check_id,
                "executor_note": "",
            }
            for sense_check_id in batch_sense_check_ids
        ],
    }


def _write_execute_batch_template(
    plan_dir: Path,
    batch_number: int,
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
) -> Path:
    """Write the batch-scoped execute output template and return its path."""
    output_path = plan_dir / f"execute_batch_{batch_number}_output.json"
    output_path.write_text(
        json.dumps(
            _execute_batch_template_payload(batch_task_ids, batch_sense_check_ids),
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def _write_execute_template(
    plan_dir: Path,
    state: PlanState,
) -> Path:
    """Write the execute output template file and return its path.

    Execute output is assembled from multiple batch outputs
    (``batch_assembly`` mode).  This builder exists for parity and
    documentation: it pre-populates ``task_updates`` and
    ``sense_check_acknowledgments`` with the actual task IDs and
    sense-check IDs from ``finalize.json`` so that downstream
    assembly code can merge batch outputs by ID.  Handlers do NOT
    route through single-file scratch promotion for execute.
    """
    task_updates: list[dict[str, object]] = []
    sense_check_acknowledgments: list[dict[str, object]] = []

    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        try:
            finalize_data = read_json(finalize_path)
            if isinstance(finalize_data, dict):
                for task in finalize_data.get("tasks", []):
                    task_id = task.get("id", "")
                    if task_id:
                        task_updates.append({
                            "task_id": task_id,
                            "status": "pending",
                            "executor_notes": "",
                            "files_changed": [],
                            "commands_run": [],
                        })
                for sc in finalize_data.get("sense_checks", []):
                    sc_id = sc.get("id", "")
                    if sc_id:
                        sense_check_acknowledgments.append({
                            "sense_check_id": sc_id,
                            "executor_note": "",
                        })
        except Exception:
            pass

    template: dict[str, object] = {
        "output": "",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": task_updates,
        "sense_check_acknowledgments": sense_check_acknowledgments,
    }

    output_path = plan_dir / "execute_output.json"
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path
