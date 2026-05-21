"""Finalize-phase prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import (
    configured_robustness,
    intent_brief_reference,
    is_prose_mode,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
)
from megaplan.types import PlanState

from ._shared import _finalize_debt_block, _gate_summary_or_skipped
from .gate import _collect_critique_summaries, _flag_summary


def _finalize_prompt(state: PlanState, plan_dir: Path, root: Path | None = None) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = _gate_summary_or_skipped(plan_dir)
    flag_registry = load_flag_registry(plan_dir)
    critique_history = _collect_critique_summaries(plan_dir, state["iteration"])
    debt_block = _finalize_debt_block(plan_dir, root)
    plan_mode = state.get("config", {}).get("mode", "code")
    robustness = configured_robustness(state)
    if is_prose_mode(state):
        task_field_guidance = textwrap.dedent(
            f"""
            - Each task represents a document section or group of sections to author.
            - Task objects use `sections_written` (array of section IDs) instead of `files_changed`/`commands_run`.
            - Do NOT include `files_changed` or `commands_run` in task descriptions — the executor writes to a single output file.
            - Do NOT include `baseline_test_failures` or `baseline_test_command` — there are no tests for doc mode.
            - The FINAL task should be a review/polish pass over the assembled document, not a test run.
            {"- Bare robustness doc-mode exception: emit exactly one task that both authors and verifies the document, so execution stays single-batch." if robustness == "bare" else ""}
            """
        ).strip()
    else:
        task_field_guidance = textwrap.dedent(
            """
            - The FINAL task MUST always be to run tests and verify the changes work. If specific test IDs or commands are mentioned in the original task, include them. Otherwise, the executor should find and run the tests most relevant to the files changed. If any test fails, read the error, fix the code, and re-run until they pass. Do NOT create new test files — run the project's existing test suite. Additionally, the executor should write a short throwaway script that reproduces the specific bug described in the task, run it to confirm the fix works, then delete the script.
            """
        ).strip()
    if plan_mode == "code":
        user_actions_guidance = textwrap.dedent(
            """
            - `user_actions` must be an array of human-only setup or operational actions. Use IDs `U1`, `U2`, ... and include `description` plus `phase` (`before_execute` or `after_execute`). Use optional `blocks_task_ids` when an action blocks specific tasks, optional `rationale` when useful, and `requires_human_only_reason` ONLY when the user_action is the sole coverage for a plan step.
            - Include ONLY actions that require a human outside the executor's repo-editing work: env vars or secrets, infra access such as cloud accounts or VPN, DB migrations the human must trigger, manual UI/UX smoke tests, deploys, and out-of-band approvals.
            - Anything that touches code in the repo MUST be a task, not a user_action. Reading docs, editing files, running tests, and writing migration SQL are tasks. Negative example: writing the migration SQL is a task, not a user_action.
            - Positive examples: `U1: Set ANTHROPIC_API_KEY in .env (before_execute)`; `U2: Manually smoke test the production deploy in the browser (after_execute)`.
            """
        ).strip()
    else:
        user_actions_guidance = textwrap.dedent(
            """
            - `user_actions` must be `[]` in doc, joke, and creative modes. These modes must not emit human-only user_actions.
            """
        ).strip()
    return textwrap.dedent(
        f"""
        You are preparing an execution-ready briefing document from the approved plan.

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan:
        {latest_plan}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        Flag registry:
        {json_dump(_flag_summary(flag_registry)).strip()}

        Critique history:
        {json_dump(critique_history).strip()}

        {debt_block}

        Requirements:
        - Produce structured JSON only.
        - `tasks` must be an ordered array of task objects. Every task object must include:
          - `id`: short stable task ID like `T1`
          - `description`: concrete work item
          - `depends_on`: array of earlier task IDs or `[]`
          - `status`: always `"pending"` at finalize time
          - `executor_notes`: always `""` at finalize time
          - `reviewer_verdict`: always `""` at finalize time
          - `kind`: indicating the type of work. One of:
            - `code`: writes or modifies source files (executor must produce `files_changed`).
            - `test`: writes or modifies test files, or runs the test suite (executor must produce `files_changed` in tests/ OR `commands_run` containing pytest/test invocations).
            - `audit`: read-only investigation — grep, code review, schema inspection (executor evidence is `executor_notes` describing findings; no `files_changed` expected).
            - `research`: external research or non-code investigation (executor evidence is `executor_notes`).
            - `docs`: writes documentation files (executor must produce `files_changed`).
            If unsure, default to `code`.
        - `watch_items` must be an array of strings covering runtime risks, critique concerns, and assumptions to keep visible during execution.
        - `sense_checks` must be an array with one verification question per task. Every sense-check object must include:
          - `id`: short stable ID like `SC1`
          - `task_id`: the related task ID
          - `question`: reviewer verification question
          - `verdict`: always `""` at finalize time
        {user_actions_guidance}
        - `meta_commentary` must be a single string with execution guidance, gotchas, or judgment calls that help the executor succeed.
        - `validation` must be an object that self-checks plan coverage:
          - `plan_steps_covered`: enumerate EVERY step from the approved plan. For each step, provide a short `plan_step_summary` (the step's intent in one phrase) and `finalize_item_ids` (array of task IDs `T*` or user_action IDs `U*` that implement or cover it — a single plan step may map to multiple tasks and/or user_actions).
          - `orphan_tasks`: task IDs that do not correspond to any plan step. Normally empty. If non-empty, explain in `completeness_notes`.
          - `completeness_notes`: free-text explanation of any gaps, deviations, or deliberate omissions.
          - `coverage_complete`: set to `true` only if every plan step has at least one finalize task or user_action AND you have verified the mapping by reviewing each entry. Set to `false` if any plan step is missing coverage.
          - Example:
          ```json
          "validation": {{
            "plan_steps_covered": [
              {{"plan_step_summary": "Add retry logic to API client", "finalize_item_ids": ["T1", "T2"]}},
              {{"plan_step_summary": "Set required production secret", "finalize_item_ids": ["U1"]}}
            ],
            "orphan_tasks": [],
            "completeness_notes": "All plan steps mapped to tasks.",
            "coverage_complete": true
          }}
          ```
        - Preserve information that strong existing artifacts already capture well: execution ordering, watch-outs, reviewer checkpoints, and practical context.
        - The structured output should be self-contained: an executor reading only `finalize.json` should have everything needed to work.
        - Keep the task count proportional to the work. A simple 1-2 file fix should be 2 tasks: (1) apply the fix, (2) run tests. Do NOT create separate "inspect" or "read" tasks for simple changes — the executor can read and fix in one step. Only create more tasks when the work has genuinely independent stages.
        - {task_field_guidance}
        """
    ).strip()
