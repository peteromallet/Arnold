"""Finalize-phase prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    configured_robustness,
    intent_brief_reference,
    is_prose_mode,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    read_json,
)
from arnold_pipelines.megaplan.types import PlanState

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
            - Return the task DAG JSON only. Do NOT include a top-level `plan`, `final_plan`, `document`, or prose draft field.
            - Do NOT include `files_changed` or `commands_run` in task descriptions — the executor writes to a single output file.
            - Do NOT include `baseline_test_failures` or `baseline_test_command` — there are no tests for doc mode.
            - The FINAL task should be a review/polish pass over the assembled document, not a test run.
            {"- Bare robustness doc-mode exception: emit exactly one task that both authors and verifies the document, so execution stays single-batch." if robustness == "bare" else ""}
            """
        ).strip()
    else:
        task_field_guidance = textwrap.dedent(
            """
            - The harness owns integration and full-suite verification — do NOT author a model task whose objective is to run either one. Implementation and test-authoring tasks may run narrow selectors for immediate feedback, but keep those selectors to the changed behavior, run them once, and allow at most one diagnostic rerun after a failure. The harness will run the authoritative post-execute suite.
            - For code-mode plans, preserve a scoped test contract. Prefer the plan's machine-readable `test_blast_radius`; when it is missing, ensure at least one finalized task carries a concrete scoped pytest command in `commands_run` (for example `pytest tests/test_relevant.py -q`) or mappable `files_changed` paths. Do not rely on an unscoped `pytest` command unless the plan explicitly opts into `test_selection=full`.
            """
        ).strip()
    if plan_mode == "code":
        user_actions_guidance = textwrap.dedent(
            """
            - `user_actions` should default to `[]`. Emitting a user_action stalls execution on a human gate — it is a load-bearing escape hatch, not a convenience. Prefer to design every step to be fully mechanical: the executor can read files, run commands, query APIs, fetch URLs, parse JSON, edit code, and run tests. If a check is mechanical, write it as a task — not a user_action.
            - Emit a user_action ONLY when the work is *genuinely non-mechanical* and the executor has no path to do it itself: secrets the human alone holds (a real API key the executor cannot mint), infrastructure access bound to the human's identity (cloud console, VPN), legal/license/security-policy judgments that require a human signatory, or out-of-band manual UI smoke tests on production. If you cannot name a specific reason the executor cannot do it, the task is mechanical — make it a task.
            - Anything that touches code, configuration, fixtures, or local files MUST be a task. Reading docs, grepping, editing, running tests, writing SQL, and producing JSON resolution files are tasks. Negative example: writing the migration SQL is a task, not a user_action; verifying a license URL is reachable is a task, not a user_action.
            - When you do emit a user_action, set `requires_human_only_reason` to a specific sentence naming why the executor literally cannot perform it (not just "it's important").
            - If `user_actions` is non-empty, expect that execution will block until the human resolves each one — only emit them when that block is unavoidable.
            - Positive examples (rare, last-resort): `U1: Set ANTHROPIC_API_KEY in .env (before_execute, requires_human_only_reason: "secret the executor cannot mint")`; `U2: Confirm legal sign-off to commit the third-party JSON corpus (before_execute, requires_human_only_reason: "license judgment with legal liability")`.
            """
        ).strip()
    else:
        user_actions_guidance = textwrap.dedent(
            """
            - `user_actions` must be `[]` in doc, joke, and creative modes. These modes must not emit human-only user_actions.
            """
        ).strip()
    if is_prose_mode(state):
        final_task_guidance = (
            "- The FINAL task MUST review/polish the assembled prose artifact; it must not run tests."
        )
    else:
        final_task_guidance = (
            "- Do NOT add a final integration/full-suite test task. The final implementation or "
            "test-authoring task should run only its narrow selectors; the harness owns the "
            "authoritative post-execute validation."
        )
    output_path = _write_finalize_template(plan_dir, state)

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

        Your output template is at: {output_path}
        Read this file first — it contains the expected JSON structure (tasks, user_actions, sense_checks, watch_items, meta_commentary).
        Fill the JSON structure with your results and write the file back.
        If you cannot use file tools, return the populated JSON structure inline as your response instead.

        Requirements:
        - Produce structured JSON only.
        - For each `## Step N:` in the plan, emit 1-N tasks.
        - For each task, emit one sense_check.
        - Default `user_actions` to `[]`. Identify a user_action ONLY when the work is genuinely non-mechanical and the executor literally cannot do it (secrets the human alone holds, identity-bound infra access, legal/license signatories, manual UI smoke tests on production). If a check is mechanical, make it a task — not a user_action. See the detailed guidance below.
        - Do not invent tasks that don't trace to a plan step.
        - How batching works at runtime — shape `depends_on` with this in mind, not just literal sequencing. Tasks that share the same `depends_on` set form one batch (capped at 5). Each batch dispatches as a SINGLE LLM conversation to a SINGLE model, picked by the max(complexity) in that batch. So a c=8 audit plus three c=2 tweaks sharing a batch all run in one turn on the c=8 model. Two consequences you control via DAG shape:
          - Routing: every task in a batch runs on the highest-tier task's model — bundle a c=2 task beside a c=8 sibling and it runs on the pricier model.
          - Cognitive load: one conversation holds all of the batch's tasks in working context. The more disparate the tasks, the higher the risk the model loses the thread or claims completion without doing the work. Wide, mixed batches are the dominant quality failure mode.
        - `depends_on` is correctness authority, not a routing hint. Add an edge only when the downstream task cannot be implemented correctly from the original baseline plus its other declared prerequisites. Never add an edge merely to isolate a model tier, reduce a ready frontier, preserve authoring order, or keep a heavyweight in its own batch.
        - Three principles for shaping batches — judgment, not arithmetic (there is no mechanical split rule):
          1. Isolate heavyweights without inventing dependencies. Keep semantically independent c=7/c=8+ tasks as siblings; the runtime batch cap can place ready siblings in separate batches.
          2. Bundle context-related light work. Several c=2/c=3 tasks touching the same files or contracts batch well together.
          3. A ready frontier wider than 5 is valid when the work is genuinely independent. Preserve that independence; the runtime batcher caps each dispatched batch at 5.
        - Do not include `validation` or `coverage_complete` fields - the harness computes those.
        {final_task_guidance}
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
          - `complexity`: integer 1–10 "weight" score. This is a composite of **difficulty**
            (cognitive load, novelty, risk of subtle bugs, reasoning required) **and scale**
            (size/volume of change: files/modules touched, surface area, amount of work).
            The third dimension is **blast radius / consequence** (how costly a mistake would be).
            Adjudicate deliberately — do not guess. Use the rubric:
            - 1 = MICRO: tightly scoped, obvious change (one small location, few lines). Low difficulty, negligible scale.
            - 2 = LIGHT: small, well-understood task (localized fix or test update). Limited reasoning, very small surface.
            - 3 = ROUTINE: normal maintenance with clear path (small feature or refactor across a few locations). Low-moderate difficulty, contained scale.
            - 4 = STANDARD: bounded task needing some design judgment (across a small module). Touches several files but risks are understandable.
            - 5 = MEANINGFUL: moderately sized with genuine complexity (multiple components, non-obvious edges). Scale or difficulty requires deliberate planning.
            - 6 = HEAVY: large or difficult task crossing module boundaries (several interacting requirements, meaningful regression risk). Requires sustained reasoning.
            - 7 = DEMANDING: high-complexity work (uncertain root causes, non-trivial architecture, broad surface, delicate constraints). Both difficulty and scale elevated.
            - 8 = MAJOR: major subsystem change or broad repair (many dependencies, substantial validation). Large and cognitively demanding.
            - 9 = CRITICAL: high-risk work affecting core paths, data integrity, security, or many consumers. Scale may be broad or difficulty exceptionally subtle.
            - 10 = EXCEPTIONAL: system-defining work with maximum scale, uncertainty, or consequence (major redesign, multi-system migration). Requires expert reasoning and comprehensive validation.
            Score on the hardest REALISTIC aspect of the task, not a worst-case imagining. When
            genuinely torn between two tiers, choose the LOWER one UNLESS you can name the specific
            cascading, test-evading failure that earns the higher tier in the justification.
            You are not the model that executes this task, and the score neither saves nor
            costs you anything — so do not lowball to seem efficient and do not highball to
            play safe. Both distort routing: a too-low score sends a hard task to a model
            that fails it; a too-high score burns a premium model on trivial work. Score
            what the task honestly requires, no higher and no lower.
            FLOOR: a task is NEVER below tier 4 only when it GENUINELY changes the semantics of
            concurrency, a schema/state-machine, a security/auth boundary, or a contract other
            code actually depends on — because a subtle error there passes tests but is wrong.
            This floor does NOT apply to mechanical edits that merely sit near such code, or that
            add a new interface nothing relies on yet; score those on the rubric (usually 2-3).
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
        - Keep the task count proportional to the work. A simple 1-2 file fix should normally be one task that applies the fix and runs its narrow selectors; post-execute integration/full-suite validation is not another model task. Do NOT create separate "inspect", "read", or validation-only tasks for simple changes. Only create more tasks when the work has genuinely independent implementation stages.
        - One task is the unit of ONE worker turn: the executor must IMPLEMENT it, run bounded narrow verification, and emit its result envelope inside a single ~15-minute conversation. A task that cannot realistically finish in one turn is mis-sized and WILL fail — the worker reports `blocked: "turn ended before implementation"` or runs out the clock mid-edit. Size every task to fit one turn; raising `complexity` does NOT buy more turns, it only routes to a stronger model for the SAME single turn. Narrow verification should consume at most 2 minutes of the turn under normal conditions; a slower integration or full-suite command belongs to the harness. When a step is a large mechanical refactor, SPLIT it across tasks instead of bundling: "add the new abstraction + its unit tests" (T1) → "migrate consumer A" (T2, depends_on T1) and "migrate consumer B + parity tests" (T3, depends_on T1) when the consumers are independent. A single task that says "extract this 2000-line file into modules and write tests" or "consolidate the roots AND migrate three registries AND add parity tests" is a god-task — decompose it into one task per consumer/module, each independently completable and verifiable.
        - {task_field_guidance}
        """
    ).strip()


def _write_finalize_template(
    plan_dir: Path,
    state: PlanState,
) -> Path:
    """Write the finalize output template file and return its path.

    The template provides the expected top-level keys with empty
    collections so the model only has to populate them.  No ID
    prepopulation is needed — the model generates task and
    sense-check IDs from the approved plan.
    """
    import json

    template: dict[str, object] = {
        "tasks": [],
        "user_actions": [],
        "sense_checks": [],
        "watch_items": [],
        "meta_commentary": "",
    }

    output_path = plan_dir / "finalize_output.json"
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path
