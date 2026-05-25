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
    read_json,
)
from megaplan.types import PlanState

from ._shared import _gate_summary_or_skipped


def _finalize_prompt(state: PlanState, plan_dir: Path, root: Path | None = None) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = _gate_summary_or_skipped(plan_dir)
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
        You are DECOMPOSING the approved plan below into an ordered task DAG. The plan has been
        critiqued, gated, and possibly revised. Do NOT re-evaluate strategy or re-litigate
        decisions - gate has settled those.

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan:
        {latest_plan}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        Requirements:
        - Produce structured JSON only.
        - For each `## Step N:` in the plan, emit 1-N tasks.
        - For each task, emit one sense_check.
        - Identify user_actions ONLY for human-only setup: env vars, manual UI tests, deploys, out-of-band approvals, or other work the executor cannot perform in the repo.
        - Do not invent tasks that don't trace to a plan step.
        - batch_1 (dependency-independent tasks executed together) MUST have at most 5 tasks. If you have more than 5 independent tasks, linearize some via depends_on to spread them across batches.
        - Do not include `validation` or `coverage_complete` fields - the harness computes those.
        - The FINAL task MUST run tests; harness validation will reject finalize output without it.
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
          - `complexity`: integer 1–5 complexity score. This score routes the task to a
            model at execution time, so adjudicate it deliberately — do not guess. Use the rubric:
            - 1 = trivial, mechanical, single-file change with no logic to reason about
                  (rename, constant bump, comment, import). A weak model cannot get it wrong.
            - 2 = simple, localized change plus the obvious test update; one file or two,
                  logic is linear and the failure mode is obvious.
            - 3 = multi-file change with non-trivial logic, control flow, or data shape the
                  executor must hold in its head; correctness is not self-evident from the diff.
            - 4 = cross-cutting change touching several modules or a shared interface/contract,
                  with architecture implications or non-local effects that need judgement.
            - 5 = fundamental system change with high regression risk: concurrency, schema or
                  state-machine changes, security-sensitive paths, or anything where a subtle
                  error would pass tests but be wrong.
            Score on the HARDEST aspect of the task, not the average. When genuinely torn
            between two tiers, choose the HIGHER one and say why in the justification.
            You are not the model that executes this task, and the score neither saves nor
            costs you anything — so do not lowball to seem efficient and do not highball to
            play safe. Both distort routing: a too-low score sends a hard task to a model
            that fails it; a too-high score burns a premium model on trivial work. Score
            what the task honestly requires, no higher and no lower.
            FLOOR: any task that touches concurrency, schema or state-machine changes,
            security- or auth-sensitive paths, or a public/shared interface contract is
            NEVER below tier 4, regardless of how few lines it changes — a subtle error
            in these areas passes tests but is wrong.
          - `complexity_justification`: REQUIRED. One or two sentences that argue, specifically,
            why this task sits at exactly that tier — cite the concrete files, interfaces, or
            risk that places it there (e.g. "touches the auth middleware contract used by 4
            call sites, so a mistake is non-local → tier 4"). A bare restatement of the rubric
            ("this is complex") is not acceptable; the justification must be defensible against
            a reviewer who disagrees.
        - `watch_items` must be an array of strings covering runtime risks, critique concerns, and assumptions to keep visible during execution.
        - `sense_checks` must be an array with one verification question per task. Every sense-check object must include:
          - `id`: short stable ID like `SC1`
          - `task_id`: the related task ID
          - `question`: reviewer verification question
          - `verdict`: always `""` at finalize time
        {user_actions_guidance}
        - `meta_commentary` must be a single string with execution guidance, gotchas, or judgment calls that help the executor succeed.
        - Preserve information that strong existing artifacts already capture well: execution ordering, watch-outs, reviewer checkpoints, and practical context.
        - The structured output should be self-contained: an executor reading only `finalize.json` should have everything needed to work.
        - Keep the task count proportional to the work. A simple 1-2 file fix should be 2 tasks: (1) apply the fix, (2) run tests. Do NOT create separate "inspect" or "read" tasks for simple changes — the executor can read and fix in one step. Only create more tasks when the work has genuinely independent stages.
        - {task_field_guidance}
        """
    ).strip()
