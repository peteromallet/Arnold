"""Planning-phase prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import (
    creative_form_id,
    intent_and_notes_block,
    is_creative_mode,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    read_json,
)
from arnold_pipelines.megaplan.forms import get_form
from arnold_pipelines.megaplan.types import PlanState

from ._shared import _render_contracts_block, _render_prep_block, _resolve_contract_context


def _render_open_tickets(state: PlanState, plan_dir: Path) -> str:
    """Return a prompt block listing open tickets for the current repo.

    Tickets are ranked by **tag overlap** with the idea / goal description
    (not the title), then by ``created_at`` descending.  At most 20 tickets
    are shown.  The planner may **propose** links with
    ``resolves_on_complete=true``, but actual linking happens via the
    explicit ``megaplan ticket link`` CLI — the planner never directly links.
    """
    try:
        from arnold_pipelines.megaplan.tickets import list_tickets as _tickets_list
        from arnold_pipelines.megaplan.tickets.core import _resolve_store, is_cloud_store

        store = _resolve_store()
        tickets_raw = _tickets_list(
            store=store,
            status="open",
        )
    except Exception:
        return ""

    if not tickets_raw:
        return ""

    goal_desc = (state.get("idea") or "").lower()
    goal_words: set[str] = set()
    if goal_desc:
        goal_words = set(goal_desc.split())

    def _tag_overlap(t: dict) -> int:
        ttags = [tag.lower() for tag in (t.get("tags") or [])]
        if not ttags or not goal_words:
            return 0
        scored = 0
        for tag in ttags:
            tag_parts = set(tag.replace("-", " ").replace("_", " ").split())
            scored += len(tag_parts & goal_words)
        return scored

    def _created_sort_key(t: dict) -> str:
        return t.get("created_at") or ""

    ranked = sorted(
        tickets_raw,
        key=lambda t: (-_tag_overlap(t), _created_sort_key(t)),
    )
    ranked = ranked[:20]

    lines: list[str] = [
        "Open tickets for this repo:",
        "",
    ]
    for t in ranked:
        tid = t.get("id", "?")
        title = t.get("title", "(untitled)")
        tags = ", ".join(t.get("tags") or [])
        lines.append(f"- {tid} — {title}  [{tags}]")

    lines.append("")
    lines.append(
        "The planner may PROPOSE linking tickets to this plan with "
        "`resolves_on_complete=true` in the plan output, but the actual "
        "linking is performed via the explicit `megaplan ticket link` CLI "
        "after planning — the planner never directly links tickets."
    )
    return "\n".join(lines)

PLAN_TEMPLATE = textwrap.dedent(
    """
    Plan template — simple format (adapt to the actual repo and scope):
    ````md
    # Implementation Plan: [Title]

    ## Overview
    Summarize the goal, current repository shape, and the constraints that matter.

    ## Main Phase

    ### Step 1: Audit the current behavior (`src/prompts.py`)
    **Scope:** Small
    1. **Inspect** the current implementation and call out the exact insertion points (`src/prompts.py:29`).

    ### Step 2: Add the first change (`src/evaluation.py`)
    **Scope:** Medium
    1. **Implement** the smallest viable change with exact file references (`src/evaluation.py:1`).
    2. **Capture** any tricky behavior with a short example.
       ```python
       issues = validate_plan_structure(plan_text)
       ```

    ### Step 3: Wire downstream behavior (`src/handlers.py`, `src/workers.py`)
    **Scope:** Medium
    1. **Update** the runtime flow in the touched files (`src/handlers.py:400`, `src/workers.py:199`).

    ### Step 4: Prove the change (`tests/test_validator.py`, `tests/test_integration.py`)
    **Scope:** Small
    1. **Run** the cheapest targeted checks first (`tests/test_validator.py:1`).
    2. **Finish** with broader verification once the wiring is in place (`tests/test_integration.py:1`).

    ## Execution Order
    1. Update prompts and mocks before enforcing stricter validation.
    2. Land higher-risk wiring after the validator and tests are ready.

    ## Validation Order
    1. Start with focused unit tests.
    2. Run the broader suite after the flow changes are in place.
    ````

    For complex plans, use multiple phases:
    ````md
    ## Phase 1: Foundation — Dependencies, DB, Types

    ### Step 1: Install dependencies (`package.json`)
    ...

    ### Step 2: Create database migration (`supabase/migrations/`)
    ...

    ## Phase 2: Core Integration

    ### Step 3: Port the main component (`src/components/`)
    ...
    ````

    Template guidance:
    - Simple plans: use `## Main Phase` with `### Step N:` sections underneath.
    - Complex plans: use multiple `## Phase N:` sections, each containing `### Step N:` steps. Step numbers are global (not per-phase).
    - The flat `## Step N:` format (without phases) also works for backwards compatibility.
    - Key invariants: one H1 title, one `## Overview`, numbered step sections (`### Step N:` or `## Step N:`), and at least one ordering section.
    """
).strip()


def _prep_context_sections(state: PlanState, plan_dir: Path) -> tuple[Path, Path, str, str]:
    project_dir = Path(state["config"]["project_dir"])
    prep_path = plan_dir / "prep.json"

    direction_raw = state.get("config", {}).get("prep_direction")
    direction = direction_raw.strip() if isinstance(direction_raw, str) else ""
    if direction:
        direction_block = textwrap.dedent(
            f"""
            User direction for prep (treat as steering for what to explore — not a substitute for the task):
            {direction}
            """
        ).strip()
    else:
        direction_block = ""

    extra_sections: list[str] = []
    clarification = state.get("clarification", {}) or {}
    intent_summary = clarification.get("intent_summary")
    if isinstance(intent_summary, str) and intent_summary.strip():
        extra_sections.append(f"User intent summary:\n{intent_summary.strip()}")
    notes = state.get("meta", {}).get("notes", []) or []
    note_lines = [
        f"- {n['note']}"
        for n in notes
        if isinstance(n, dict) and isinstance(n.get("note"), str) and n["note"].strip()
    ]
    if note_lines:
        extra_sections.append("User notes and answers:\n" + "\n".join(note_lines))
    notes_block = "\n\n".join(extra_sections)
    return project_dir, prep_path, direction_block, notes_block


def _plan_prompt(
    state: PlanState,
    plan_dir: Path,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    prep_block, prep_instruction = _render_prep_block(plan_dir)
    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="plan",
    )
    if prep_instruction:
        prep_instruction += (
            " Open questions in the brief are candidate concerns, not mandates —"
            " act on ones that materially affect the plan, dismiss immaterial or"
            " already-resolved ones with a brief reason, and treat question count as noise."
        )
    from_doc = state["config"].get("from_doc")
    imported_decisions = state["meta"].get("imported_decisions", [])
    clarification = state.get("clarification", {})
    mode = state["config"].get("mode", "code")
    output_path = state["config"].get("output_path")
    primary_criterion = state["config"].get("primary_criterion", "[missing primary criterion]")
    if mode == "doc" and output_path:
        output_path_block = textwrap.dedent(
            f"""
            Doc-mode output contract (LOAD-BEARING):
            The final document artifact will be written by the EXECUTE phase to exactly this path:
              {output_path}
            Your job in THIS plan phase is to produce the structured plan markdown as your text response — do NOT call the Write tool, the Edit tool, or any filesystem-writing tool right now. Do NOT attempt to author, save, or "queue" the deliverable file: a later execute phase reads your plan and writes the deliverable. Only the execute phase has write permission to the output path; any Write call in the plan phase will be rejected.
            Every plan step that authors, edits, or verifies document sections MUST reference this exact path. Do NOT invent an alternate filename based on the document title or a kebab-case normalization. The executor will only write to the path above; any step instructing it to write elsewhere will produce a file that review cannot verify.
            """
        ).strip()
    elif is_creative_mode(state) and output_path:
        form = get_form(creative_form_id(state) or "joke")
        beat_list = ", ".join(form.beat_ids)
        output_path_block = textwrap.dedent(
            f"""
            Creative-work output contract (LOAD-BEARING):
            Form: {form.display_name} (`{form.id}`)
            Beat canvas IDs: {beat_list}
            Produce a creative scene canvas keyed by those beat IDs, not a code task list.
            The final artifact written to `{output_path}` MUST be standalone creative prose for this form, including screenplay-style OR short story when the form is joke.
            The primary criterion is **{primary_criterion}** — every design choice must serve it.
            """
        ).strip()
    else:
        output_path_block = ""
    if clarification:
        clarification_block = textwrap.dedent(
            f"""
            Existing clarification context:
            {json_dump(clarification).strip()}
            """
        ).strip()
    else:
        clarification_block = "No prior clarification artifact exists. Identify ambiguities, ask clarifying questions, and state your assumptions inside the plan output."
    if from_doc:
        prior_doc_lines = [
            "Prior doc context:",
            "Prior doc imported via --from-doc:",
            str(from_doc),
        ]
        if imported_decisions:
            prior_doc_lines.extend(
                [
                    "Imported decisions:",
                    *[
                        "\n".join(
                            [
                                f"- {decision.get('id', '')}: {decision.get('decision', '')}",
                                f"  rationale: {decision.get('rationale', '')}",
                                f"  load_bearing: {decision.get('load_bearing', False)}",
                            ]
                        )
                        for decision in imported_decisions
                    ],
                    "Planning guidance for imported decisions:",
                    "- For each imported decision with load_bearing: true, include a machine-verifiable success criterion with priority: 'must', a non-empty container capability in `requires`, and the exact imported decision ID shown above in `criterion`.",
                    "- For each imported decision with load_bearing: false, include a success criterion with priority: 'info' and the exact imported decision ID shown above in `criterion`.",
                ]
            )
        else:
            prior_doc_lines.append(
                "No ## Settled Decisions section found — path stored for reference only."
            )
        prior_doc_block = "\n".join(prior_doc_lines)
    else:
        prior_doc_block = ""
    # --- Open tickets for this repo (planner discovery) ---
    tickets_block = _render_open_tickets(state, plan_dir)

    return textwrap.dedent(
        f"""
        You are creating an implementation plan for the following idea.

        {prep_block}

        {prep_instruction}

        {intent_and_notes_block(state)}

        {contracts_block}

        Project directory:
        {project_dir}

        {output_path_block}

        {prior_doc_block}

        {clarification_block}

        {tickets_block}

        Requirements:
        - If the engineering brief suggests an approach, use it as your starting hypothesis — but before committing, consider if there's a simpler or more fundamental fix. The brief is well-researched input, not a final answer.
        - If the brief is absent, incomplete, or says "skip", inspect the repository yourself before planning.
        - Stay focused on the requested idea. If repo exploration surfaces unrelated issues or docs, ignore them and return to the task.
        - Prefer source code, tests, and directly relevant config files. Avoid `.megaplan/`, prior plan artifacts, and unrelated `docs/` or ops/deployment material unless the task explicitly depends on them.
        - Stop exploring once you have enough evidence to name the concrete touch points and validation path. Do not keep browsing after you can write the plan.
        - Produce a concrete implementation plan in markdown.
        - Define observable success criteria as objects with `criterion` (string) and `priority` (`must`, `should`, or `info`):
          - `must` — hard gate. The reviewer will block on failure. Use for correctness, functional requirements, and verifiable outcomes (e.g., "all existing tests pass", "API returns 200 for valid input"). Every `must` criterion must have a clear yes/no answer.
          - `should` — quality target. The reviewer flags but does not block. Use for subjective goals, numeric guidelines, and best-effort improvements (e.g., "file under ~300 lines", "no deeply nested conditionals", "each function has a single responsibility").
          - `info` — documented for humans, reviewer skips. Use for criteria that cannot be verified in this pipeline (e.g., "13 manual smoke tests pass", "stakeholder sign-off obtained").
        - Each success criterion should include a `requires` field listing the capabilities needed for verification. Valid capability strings: `run_shell`, `read_files`, `run_tests`, `parse_diff`, `read_build_output`, `run_linter` (container), `drive_browser`, `inspect_runtime_ui`, `observe_runtime_logs`, `subjective_judgment`, `verify_physical_device` (human). `must` criteria MUST have non-empty `requires`. Example: `{{"criterion": "All tests pass", "priority": "must", "requires": ["run_tests"]}}`.
        - Use the `questions` field for ambiguities that would materially change implementation.
        - Use the `assumptions` field for defaults you are making so planning can proceed now.
        - Prefer cheap validation steps early.
        - Keep the plan proportional to the task. A 1-line fix needs a 2-step plan (apply fix + run tests), not a 5-step investigation.
        - Size each step so it can be implemented AND verified in a single worker turn (~15 min, one model conversation). A step that bundles "create the abstraction AND migrate every consumer AND write all the tests" is too large to finish in one turn and will fail (the worker runs out of time before it can implement, leaving the step blocked). For large mechanical refactors, split along the natural seam — one step to add the new abstraction + its unit tests, then one step per consumer to migrate (the last migration step also adds parity tests) — rather than one giant step. Higher complexity does not earn a step more time; it only routes to a stronger model for the same single turn.
        - If user notes answer earlier questions, incorporate them into the draft plan instead of re-asking them.
        - Fix the problem fully. Do not limit scope just to avoid breaking existing tests — update the tests too if needed.
        - Prefer the simplest, most direct fix. No fallbacks, type conversions, or defensive wrappers without concrete evidence they are needed.
        - If the task or issue hints suggest a specific approach, follow it. Only deviate with concrete counter-evidence.
        - Assign every plan step a complexity score 1–5 before finalize. Reason about complexity in the plan markdown (e.g. "Complexity: 2" per step), and surface it informally so the reviewer can audit:
          - 1 = trivial single-file mechanical change
          - 2 = simple change with tests to update
          - 3 = multi-file change with non-trivial logic
          - 4 = cross-cutting change with architecture implications
          - 5 = fundamental system change with high regression risk
        - Populate `changed_surfaces` with every concrete file path your plan will change or create. Include both source files and test files. Use repo-relative paths (e.g., `src/prompts.py`, `tests/test_prompts.py`). This list drives the deterministic test-selection blast radius; be complete. If your plan touches a file, list it.
        - (Optional) Populate `test_blast_radius` with your own scoped test-selection proposal. This complements the deterministic floor the system computes from `changed_surfaces`. Provide `strategy` ("scoped", "full", or "none"), `selectors` (array of `{{"kind": "path", "value": "<path>", "reason": "<why>"}}` objects), and a `rationale` string. The system merges your proposal with the deterministic floor; you cannot narrow below the floor, but you can widen with additional selectors or escalate to full. If you intend a scoped finalize baseline while keeping the full suite as a hard gate, set `strategy` to "scoped", include concrete `selectors`, and set `full_suite_fallback` to true; the floor's full-suite requirement will be honored by the fallback without forcing the baseline strategy to "full".

        {PLAN_TEMPLATE}
        """
    ).strip()


def _prep_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    del root
    project_dir, output_path, direction_block, notes_block = _prep_context_sections(
        state, plan_dir
    )
    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="prep",
    )

    return textwrap.dedent(
        f"""
        Prepare a concise engineering brief for the task below. This brief will be the primary context for all subsequent planning and execution.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Output file: {output_path}

        {direction_block}

        {notes_block}

        {contracts_block}

        First, assess: does this task need codebase investigation?

        Set "skip": true if ALL of these are true:
        - The task names the exact file(s) to change
        - The required change is clearly described
        - No ambiguity about the approach

        Set "skip": false if ANY of these are true:
        - The task doesn't say which files to change
        - Multiple approaches seem possible
        - The task references concepts, APIs, or patterns you'd need to look up in the codebase
        - The task involves more than 2-3 files
        - There are hints or references that need investigation

        If skipping, leave everything else empty. The original task description will be used directly.
        If not skipping, fill in the brief:
        1. Search the codebase (Glob, Grep, Read) for relevant files and functions.
        2. If tests exist for the affected code, read them — they reveal what the fix must actually do, which may differ from what the task description suggests.
        3. Extract evidence from the task description — hints, references, error messages.
        4. Challenge the obvious path: if the task or hints point to a specific location, verify it's actually the right place. Trace the call chain — where does data flow? Where does it go wrong? The obvious file may be a symptom, not the root cause.
        5. If the task describes a bug or incorrect behavior, seriously consider whether it is a symptom of a larger issue. Before proposing a fix, trace the root cause. Ask: why does this happen? Could the same root cause produce other failures? Is the fix a patch on one case, or does it need to address an underlying gap? If the codebase has related functionality that is also incomplete or broken, note it — a narrow fix may not be enough.
        6. If you find that a suggested fix already exists in the code, say so explicitly — this means the root cause is elsewhere.
        7. Once you identify the function, parameter, or pattern that needs fixing, grep for ALL other usages of it in the codebase. If the same parameter is passed in 3 places, all 3 may need the fix. List every call site in relevant_code — do not stop at the first one.
        8. If the code has a `NotImplementedError`, `raise`, `TODO`, or explicit skip for certain inputs, and the bug involves those inputs, the fix likely needs to implement the missing functionality — not just patch around it. Flag this in the brief so the plan knows a larger change is needed.
        9. Look for existing helper functions, utilities, or patterns in the codebase that handle similar cases. If there is existing machinery (e.g., a merge function, a validation helper, a base class method), the fix should use it rather than reinventing.
        10. Before finalizing, ask: if I change this function, are there other callers that rely on its current behavior? A function called from multiple code paths may need different fixes for different callers — or a new method instead of modifying the existing one.
        11. List all usages as a numbered list (1. file:line — description, 2. file:line — description, etc.) so none are missed.
        12. Distill into a brief that adds value beyond the raw task description.

        Brief fields:
        - skip: true if no investigation needed, false if brief has useful content.
        - task_summary: What needs to be done, in 2-3 sentences.
        - key_evidence: Facts from the task and codebase not obvious from reading the task alone.
        - relevant_code: File paths and key functions found by searching.
        - test_expectations: Tests that verify the affected behavior.
        - constraints: What must not break.
        - suggested_approach: A concrete approach grounded in what you found.

        """
    ).strip()


def _prep_triage_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    del root
    project_dir, _prep_path, direction_block, notes_block = _prep_context_sections(
        state, plan_dir
    )
    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="prep-triage",
    )
    output_path = plan_dir / "prep_triage.json"
    return textwrap.dedent(
        f"""
        Triage the prep task below into a bounded research plan. Route only; do not produce the final prep brief yet.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Output file: {output_path}

        {direction_block}

        {notes_block}

        {contracts_block}

        Goals:
        - Decide whether prep can skip research entirely.
        - When research is needed, break it into a small number of concrete investigation areas.
        - Keep the output operational: downstream fan-out should be able to investigate each area independently.

        Output contract:
        - `triage_framing`: short framing of the task and the likely root questions.
        - `areas`: ordered list of research areas, each with `id`, `area`, `brief`, and `suggested_files`.
        - Returning `areas: []` is the explicit skip path and means downstream prep should write a compatible `prep.json` with `skip: true`.

        Rules:
        - Cap the list to the smallest set of areas that would materially reduce uncertainty.
        - Do not emit final findings, final constraints, or a final suggested approach here.
        - Prefer relation-oriented areas such as caller coverage, root cause trace, contract compatibility, and validation impact.
        - If the existing prep evidence is already sufficient, return zero areas instead of inventing research.
        - **Production-of-artifact also counts as a research area, even when the question is well-defined.** If the task or user direction explicitly asks prep to *produce* an enumeration, inventory, categorized list, audit report, or similar deliverable artifact that the planner needs as input — treat each requested artifact as its own area, even if there's no uncertainty about what to enumerate or how. "Well-specified" is not the same as "already-done": producing the artifact IS the research. The skip path (`areas: []`) is for cases where the planner can proceed without that artifact, not for cases where it was asked for and the question happens to be clear. When in doubt between "skip because clear" and "include because requested" — include.

        Return JSON only.
        """
    ).strip()


def _prep_research_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    area: dict[str, object],
    output_path: Path | None = None,
    root: Path | None = None,
) -> str:
    del root
    project_dir, _prep_path, direction_block, notes_block = _prep_context_sections(
        state, plan_dir
    )
    target_path = output_path or (plan_dir / f"{area.get('id', 'area')}.research.json")
    return textwrap.dedent(
        f"""
        Investigate one prep research area and return only the findings for that area.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Research area:
        {json_dump(area).strip()}
        Output file: {target_path}

        {direction_block}

        {notes_block}

        Output contract:
        - `area`: stable area identifier or label.
        - `brief`: one-sentence reminder of the research question.
        - `status`: one of `complete`, `partial`, `timed_out`, `error`, `not_needed`.
        - `findings`: concrete evidence bullets for this area only.
        - `files`: file paths that materially informed the findings.
        - `code_refs`: exact functions, classes, or call sites that matter.
        - `confidence`: `high`, `medium`, or `low`.
        - `error`: optional short explanation when status is not `complete`.

        Rules:
        - Stay inside this area; do not try to solve the entire task.
        - Prefer direct repository evidence over speculation.
        - Call out contradictions or missing evidence explicitly instead of smoothing them over.
        - If the area produces no useful evidence, return `status: "not_needed"` with a short explanation.

        Return JSON only.
        """
    ).strip()


def _prep_distill_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    triage: dict[str, object],
    findings: list[dict[str, object]],
    output_path: Path | None = None,
    dossier_path: Path | None = None,
    metrics_path: Path | None = None,
    root: Path | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    del root
    project_dir, prep_path, direction_block, notes_block = _prep_context_sections(
        state, plan_dir
    )
    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="prep-distill",
    )
    target_path = output_path or prep_path
    dossier_target = dossier_path or (plan_dir / "prep_dossier.md")
    metrics_target = metrics_path or (plan_dir / "prep_metrics.json")
    return textwrap.dedent(
        f"""
        Distill the triage framing and per-area research findings into the final prep brief.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Compatible prep output: {target_path}
        Dossier sidecar: {dossier_target}
        Metrics sidecar: {metrics_target}

        {direction_block}

        {notes_block}

        {contracts_block}

        Triage framing:
        {json_dump(triage).strip()}

        Area findings:
        {json_dump(findings).strip()}

        Produce:
        - A `prep.json` payload that keeps the public compatibility contract unchanged:
          required: `skip`, `task_summary`, `key_evidence`, `relevant_code`, `test_expectations`, `constraints`, `suggested_approach`;
          optional: `open_questions`.
        - Distilled evidence only. Treat the area findings as evidence to adjudicate, not as text to copy blindly.
        - Resolve overlaps across areas into one coherent prep view instead of duplicating them.
        - Clear contradiction or gap notes when the findings disagree, time out, error, or leave concrete uncertainty.
        - For each gap or contradiction, classify it as an `open_questions[]` item:
          - `"blocking"` — genuine ambiguity that would materially change the plan and cannot be responsibly resolved alone.
          - `"assume_and_proceed"` — resolvable by a stated `assumption`; include the assumption text.
          Omit `open_questions` entirely when no genuine gaps or contradictions exist.

        Rules:
        - Do not add new required fields to the compatible `prep.json` payload.
        - Keep richer per-area detail in the dossier/metrics sidecars, not in the compatible payload.
        - You may do a small, bounded read-only cross-reference against the repository only when it helps close a concrete contradiction or gap raised by these findings.
        - If the evidence is still incomplete, make the gap explicit and keep any further repository lookup tightly targeted to that gap.
        - The final suggested approach is still a hypothesis; ground it in the strongest evidence you have.

        Return JSON only for the compatible `prep.json` payload.
        """
    ).strip()
