"""Critique- and revise-phase prompt builders."""

from __future__ import annotations

import difflib
import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.forms.provocations import select_active_checks
from arnold_pipelines.megaplan.anchors import render_anchor_context
from arnold_pipelines.megaplan._core import (
    configured_robustness,
    intent_brief_reference,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
    robustness_critique_instruction,
    unresolved_significant_flags,
)
from arnold_pipelines.megaplan.north_star_actions import (
    NORTH_STAR_ACTION_TYPES,
    SEVERITY_BLOCKING,
    read_carried_north_star_actions,
)
from arnold_pipelines.megaplan.types import PlanState

_CRITIQUE_UNVERIFIABLE_ESCAPE_HATCH = """
Self-monitor for non-convergence before spending more tool calls. This is NOT about duration or difficulty: hard checks that are still making new progress should continue. But if you are spinning — re-reading the same file 3+ times, searching for a file the plan says to CREATE, needing a sibling/external repo or path outside the project root, or making many tool calls without getting closer to a verdict — STOP investigating. Not finding what you need is a finding; emit exactly one non-flagged finding whose detail starts `unverifiable: ` and explains what you could not resolve and exactly why. An unverifiable check is a complete, valid result for this worker; normal code ambiguity that you can inspect should still be flagged per the usual "when in doubt, flag it" rule.
""".strip()


def _with_anchor_block(prompt: str, state: PlanState, plan_dir: Path, *, audience: str) -> str:
    anchor_block = render_anchor_context(state, plan_dir, audience=audience)
    if not anchor_block:
        return prompt
    return f"{anchor_block}\n\n{prompt}"


def _settled_decisions_block(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return ""
    lines = ["Settled tiebreaker decisions (DO NOT re-raise these concerns under a new surface):"]
    for d in decisions:
        gid = d.get("fuzzy_group_id", "?")
        question = d.get("question", "")
        pick = d.get("human_pick", d.get("action", ""))
        rationale = d.get("rationale", "")
        lines.append(f"- {gid}: {question} -> Decision: {pick}. Rationale: {rationale}")
    lines.append(
        "\nOnly raise a new concern about these topics if new evidence *materially* "
        "changes the settled premise — and if so, explicitly cite which settled "
        "decision you are challenging and why."
    )
    return "\n".join(lines)


def _build_north_star_actions_block(actions: list[dict[str, Any]]) -> str:
    """Render carried North Star actions with explicit instruction per action_type.

    The revise worker must resolve each action by mapping its type to a
    concrete plan change, gate/scenario/checker addition, dead-delete, or
    human halt when the action cannot be mapped to the plan.
    """
    if not actions:
        return ""

    # Action-type to concrete revise instruction
    _action_instructions: dict[str, str] = {
        "change_plan": (
            "Change the plan to address this concern directly. The revised plan "
            "must show a concrete, traceable change — not just a note or TODO."
        ),
        "add_gate": (
            "Add an explicit gate requirement to the plan that blocks completion "
            "until this concern is resolved. The gate must name a concrete check, "
            "owner, or blocking condition."
        ),
        "add_scenario": (
            "Add a new scenario / test case to the plan that exercises this concern. "
            "The scenario must be concrete enough to execute, not just a prose "
            "placeholder."
        ),
        "add_checker": (
            "Add an automated checker (lint rule, static analysis, CI guard, etc.) "
            "to the plan that detects or prevents this category of issue."
        ),
        "dead_delete": (
            "Identify and remove plan steps, files, or assumptions that are "
            "dead weight given this concern. The removal must be explicit in the "
            "revised plan, not implied."
        ),
        "add_human_halt": (
            "If this concern CANNOT be addressed by any of the above actions, "
            "do NOT try to work around it — emit a `north_star_actions_addressed` "
            "entry with `resolution: \"halted\"` and a clear `reason` explaining "
            "why the action cannot be mapped to a plan change."
        ),
    }

    lines: list[str] = [
        "Carried North Star actions (must be resolved in this revision):",
        "",
        "These actions were identified by the gate as plan-level execution-safety "
        "concerns. Each action has an `action_type` that tells you what concrete "
        "change is expected. You MUST address every action by mapping its type to "
        "the corresponding revise behavior below, then record the result in "
        "`north_star_actions_addressed[]`.",
        "",
        "Action type -> expected revise behavior:",
    ]
    for at in NORTH_STAR_ACTION_TYPES:
        instr = _action_instructions.get(at, "Address this action in the revised plan.")
        lines.append(f"  - `{at}`: {instr}")
    lines.append("")  # blank line before listing actions
    lines.append("Carried actions:")

    for action in actions:
        aid = action.get("id", "?")
        category = action.get("category", "?")
        action_type = action.get("action_type", "?")
        severity = action.get("severity", "?")
        concern = action.get("concern", "")
        evidence = action.get("evidence", "")

        line = f"  - {aid} | category={category} | type={action_type} | severity={severity}"
        lines.append(line)
        if concern:
            lines.append(f"    concern: {concern}")
        if evidence:
            # Truncate very long evidence strings to keep the prompt readable
            ev = evidence[:300] + ("..." if len(evidence) > 300 else "")
            lines.append(f"    evidence: {ev}")
        # Include required_change / plan_refs as optional guidance
        required_change = action.get("required_change", "")
        if required_change:
            lines.append(f"    required_change: {required_change}")
        plan_refs = action.get("plan_refs")
        if isinstance(plan_refs, list) and plan_refs:
            lines.append(f"    plan_refs: {', '.join(str(r) for r in plan_refs)}")

    lines.append("")
    lines.append(
        "For EACH action above, record an entry in `north_star_actions_addressed[]`:"
    )
    lines.append(
        "  - `action_id`: the action `id` from the carried list above"
    )
    lines.append(
        "  - `resolution`: `\"addressed\"` (mapped to a plan change), "
        "`\"rejected\"` (action is invalid/out-of-scope), or "
        "`\"halted\"` (cannot be mapped — see `add_human_halt` above)"
    )
    lines.append("  - `reason`: what you did or why you rejected/halted")
    lines.append(
        "  - `where`: pointer to the plan section where the change lives "
        '(e.g. "Phase 2 — Step 3", "gate.json section preflight")'
    )
    lines.append(
        "  - `plan_refs` (optional): concrete file paths this resolution touches"
    )

    return "\n".join(lines)


def _plan_version_unified_diff(plan_dir: Path, iteration: int) -> str:
    """Return a unified diff between plan_v{N-1}.md and plan_v{N}.md.

    Returns an empty string when iteration < 2 or either file is missing.
    """
    if iteration < 2:
        return ""
    prev_path = plan_dir / f"plan_v{iteration - 1}.md"
    curr_path = plan_dir / f"plan_v{iteration}.md"
    if not prev_path.exists() or not curr_path.exists():
        return ""
    prev_lines = prev_path.read_text(encoding="utf-8").splitlines(keepends=True)
    curr_lines = curr_path.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(
        prev_lines,
        curr_lines,
        fromfile=f"plan_v{iteration - 1}.md",
        tofile=f"plan_v{iteration}.md",
    )
    return "".join(diff)


def _build_verification_delta_block(
    delta: dict[str, Any] | None,
    raw_log_path: str | None,
) -> str:
    """Build a bounded ~5000-char mechanical verification block for the revise prompt.

    *newly_failing* tests get error-type + message (and a traceback snippet when
    the raw log is parseable).  *still_red* is rendered name-only (comma-separated
    nodeids).  The raw log path is NEVER exposed to the LLM.  When *delta* is
    absent or non-computable, returns an empty string.
    """
    if not isinstance(delta, dict):
        return ""
    if not delta.get("computable", True):
        return ""

    newly_failing: list[str] = delta.get("newly_failing") or []
    still_red: list[str] = delta.get("still_red") or []

    if not newly_failing and not still_red:
        return ""

    # Extract failure details for newly_failing tests from the raw log
    failure_details: dict[str, dict[str, str]] = {}
    if newly_failing and raw_log_path:
        try:
            from arnold_pipelines.megaplan.orchestration.suite_runner import extract_failure_details
            details = extract_failure_details(Path(raw_log_path), newly_failing)
            failure_details = {d["nodeid"]: d for d in details}
        except Exception:
            pass

    lines: list[str] = []
    lines.append(
        "Mechanical post-execute verification \u2014 fix these new regressions; "
        "do NOT scope-creep into still_red."
    )
    lines.append("")

    CHAR_BUDGET = 5000

    def _current_len() -> int:
        return len("\n".join(lines))

    # --- newly_failing section -------------------------------------------
    if newly_failing:
        header = f"Newly failing tests ({len(newly_failing)}):"
        if _current_len() + len(header) + 2 <= CHAR_BUDGET:
            lines.append(header)
        else:
            return "\n".join(lines)

        for i, nid in enumerate(newly_failing):
            fd = failure_details.get(nid, {})
            err_type = fd.get("error_type", "<unknown>")
            msg = fd.get("message", "<unparsed>")
            tb_head = fd.get("traceback_head", "")

            entry_lines = [f"  {nid} \u2014 {err_type}: {msg}"]
            if tb_head and tb_head != "<could not extract>":
                tb_first = tb_head.split("\n")[0][:200]
                entry_lines.append(f"    Traceback: {tb_first}")

            candidate = "\n".join(lines + entry_lines)
            if len(candidate) > CHAR_BUDGET - 50:
                remaining = len(newly_failing) - i
                lines.append(f"  \u2026[{remaining} more]")
                break
            lines.extend(entry_lines)

    # --- still_red section (name-only) -----------------------------------
    if still_red:
        max_names = 20
        names = ", ".join(still_red[:max_names])
        if len(still_red) > max_names:
            names += f" \u2026[{len(still_red) - max_names} more]"
        sr_line = (
            f"\nPre-existing failures (still red \u2014 do NOT fix): {names}"
        )
        if _current_len() + len(sr_line) <= CHAR_BUDGET:
            lines.append(sr_line.strip())

    return "\n".join(lines)


def _revise_prompt(state: PlanState, plan_dir: Path) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate = read_json(plan_dir / "gate.json")
    unresolved = unresolved_significant_flags(load_flag_registry(plan_dir))
    open_flags = [
        {
            "id": flag["id"],
            "severity": flag.get("severity"),
            "status": flag["status"],
            "concern": flag["concern"],
            "evidence": flag.get("evidence"),
        }
        for flag in unresolved
    ]
    settled_decisions: list[dict[str, Any]] = []
    decisions_path = plan_dir / "tiebreaker_decisions.json"
    if decisions_path.exists():
        decisions_data = read_json(decisions_path)
        if isinstance(decisions_data, list):
            settled_decisions = decisions_data
        elif isinstance(decisions_data, dict):
            settled_decisions = decisions_data.get("decisions", [])
    settled_block = _settled_decisions_block(settled_decisions)

    # Build the mechanical verification delta block from the completion
    # verdict (if present).  The raw log path is used internally for
    # failure-detail parsing but NEVER surfaced to the LLM.
    ctx = _critique_context(state, plan_dir)
    delta_block = _build_verification_delta_block(
        ctx.get("verification_delta"),
        ctx.get("verification_raw_log_path"),
    )

    # Read carried North Star actions from gate_carry.json (normalized,
    # carried form). Fall back to gate.json when no carry file exists.
    north_star_actions = read_carried_north_star_actions(plan_dir)
    north_star_block = _build_north_star_actions_block(north_star_actions)

    return textwrap.dedent(
        f"""
        You are revising an implementation plan after critique and gate feedback.

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Current plan (markdown):
        {latest_plan}

        Current plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        Open significant flags:
        {json_dump(open_flags).strip()}

        {settled_block}

        {delta_block}

        {north_star_block}

        Requirements:
        - Before addressing individual flags, check: does any flag suggest the plan is targeting the wrong code or the wrong root cause? If so, consider whether the plan needs a new approach rather than adjustments. Explain your reasoning.
        - Update the plan to address the significant issues.
        - Keep the plan readable and executable.
        - Return flags_addressed with the exact flag IDs you addressed or rejected. For each flag, include:
          - `id`: the flag ID
          - `resolution`: `"addressed"` (you incorporated the fix) or `"rejected"` (the flag is invalid or out of scope)
          - `reason`: a concise explanation of what was changed or why the flag was rejected
          - `where`: a pointer to the plan section / files the change or claim points at (e.g., "Phase 2 — Step 3", "README.md §API")
        - Include `changes_summary` as a short plain-English summary of what changed in the revision. If there were no concrete flags, say that explicitly (for example: `No critique flags were raised; refined wording and kept the plan aligned for execution.`).
        - Preserve or improve success criteria quality. Each criterion must have a `priority` of `must`, `should`, or `info`. Promote or demote priorities if critique feedback reveals a criterion was over- or under-weighted.
        - Each success criterion should include a `requires` field listing the capabilities needed for verification. Valid capability strings: `run_shell`, `read_files`, `run_tests`, `parse_diff`, `read_build_output`, `run_linter` (container), `drive_browser`, `inspect_runtime_ui`, `observe_runtime_logs`, `subjective_judgment`, `verify_physical_device` (human). `must` criteria MUST have non-empty `requires`. Example: `{{"criterion": "All tests pass", "priority": "must", "requires": ["run_tests"]}}`.
        - For code-mode plans with any `run_tests` success criterion, include or preserve a machine-readable `test_blast_radius` object in the structured output. Use this shape: `{{"strategy":"scoped","confidence":"high","selectors":[{{"kind":"path","value":"tests/test_relevant.py","reason":"covers the changed surface"}}],"changed_surfaces":["src/relevant.py"],"always_run":[],"full_suite_fallback":true,"rationale":"Why these tests cover the planned changes."}}`. If finalize feedback says scoped baseline metadata was missing, the revision must add this object rather than only adding prose validation commands.
        - Verify that the plan remains aligned with the user's original intent, not just internal plan quality.
        - Remove unjustified scope growth. If critique raised scope creep, narrow the plan back to the original idea unless the broader work is strictly required.
        - Maintain the structural template: H1 title, ## Overview, phase sections with numbered step sections, ## Execution Order or ## Validation Order.
        - CRITICAL: Your entire revised plan markdown (all sections) must be output as the `plan` field in the structured output. The prose response must not contain the plan text.
        - CRITICAL: Return only the structured JSON object for the schema fields `plan`, `changes_summary`, `flags_addressed`, `north_star_actions_addressed`, `assumptions`, `success_criteria`, `questions`, and optional `changed_surfaces` / `test_blast_radius`. Do not add commentary before or after the JSON object.
        - Populate `changed_surfaces` with every concrete file path your revised plan will change or create. Include both source files and test files. Use repo-relative paths. This list drives the deterministic test-selection blast radius; be complete. If your revised plan touches a file, list it.
        - (Optional) Populate `test_blast_radius` with your own scoped test-selection proposal. This complements the deterministic floor the system computes from `changed_surfaces`. Provide `strategy` ("scoped", "full", or "none"), `selectors` (array of `{{"kind": "path", "value": "<path>", "reason": "<why>"}}` objects), and a `rationale` string. The system merges your proposal with the deterministic floor and the prior plan's blast radius; you cannot narrow below the floor, but you can widen with additional selectors or escalate to full. If you intend a scoped finalize baseline while keeping the full suite as a hard gate, set `strategy` to "scoped", include concrete `selectors`, and set `full_suite_fallback` to true; the floor's full-suite requirement will be honored by the fallback without forcing the baseline strategy to "full".

        """
    ).strip()


def _critique_context(state: PlanState, plan_dir: Path, root: Path | None = None) -> dict[str, Any]:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    structure_warnings = latest_meta.get("structure_warnings", [])
    flag_registry = load_flag_registry(plan_dir)
    unresolved = [
        {
            "id": flag["id"],
            "concern": flag["concern"],
            "status": flag["status"],
            "severity": flag.get("severity"),
        }
        for flag in flag_registry["flags"]
        if flag["status"] in {"addressed", "open", "disputed"}
    ]
    settled_decisions: list[dict[str, Any]] = []
    decisions_path = plan_dir / "tiebreaker_decisions.json"
    if decisions_path.exists():
        decisions_data = read_json(decisions_path)
        if isinstance(decisions_data, list):
            settled_decisions = decisions_data
        elif isinstance(decisions_data, dict):
            settled_decisions = decisions_data.get("decisions", [])

    # ----- Read the mechanical post-execute verification verdict ----------
    # We surface the delta so the revise LLM knows exactly which tests
    # regressed and must be fixed.  The raw log path is extracted for
    # internal use (failure-detail parsing) but NEVER surfaced to the LLM.
    verification_delta: dict[str, Any] | None = None
    verification_raw_log_path: str | None = None
    try:
        from arnold_pipelines.megaplan.orchestration.completion_io import read_completion_verdict
        verdict = read_completion_verdict(plan_dir)
        if isinstance(verdict, dict):
            gs = verdict.get("green_suite")
            if isinstance(gs, dict):
                verification_delta = gs.get("delta")
            # Also extract the raw_log_path from the green_suite evidence ref
            # for failure-detail parsing (never surfaced to the LLM).
            for ref in verdict.get("evidence") or []:
                if isinstance(ref, dict) and ref.get("kind") == "green_suite":
                    details = ref.get("details")
                    if isinstance(details, dict):
                        rlp = details.get("raw_log_path")
                        if isinstance(rlp, str):
                            verification_raw_log_path = rlp
                    break
    except Exception:
        pass

    # ----- prompt-size guard: keep the assembled context under ~150K tokens -----
    # Estimate tokens ≈ chars / 4.  The full plan text is the dominant contributor;
    # a 1.6M-token prompt silently overflows the model context and produces an
    # empty response (see hermes retry-on-empty guard).
    _TOKEN_BUDGET = 150_000
    _CHAR_BUDGET = _TOKEN_BUDGET * 4  # ~600K chars

    # Rough size check on the fields that end up in the assembled prompt.
    # The prompt template adds ~5K chars of fixed text, so leave headroom.
    _plan_len = len(latest_plan)
    _flags_len = len(json_dump(unresolved).strip())
    _meta_len = len(json_dump(latest_meta).strip())
    _warn_len = len(json_dump(structure_warnings).strip())
    _total_est = _plan_len + _flags_len + _meta_len + _warn_len

    if _total_est > _CHAR_BUDGET:
        overage = _total_est - _CHAR_BUDGET
        if overage > 0:
            keep_head = max(1, (_plan_len - overage) // 2)
            keep_tail = max(1, _plan_len - overage - keep_head)
            if keep_head + keep_tail < _plan_len:
                truncated_middle = _plan_len - keep_head - keep_tail
                latest_plan = (
                    latest_plan[:keep_head]
                    + "\n\n[... TRUNCATED " + str(truncated_middle)
                    + " chars of plan body to stay within model context budget ...]\n\n"
                    + latest_plan[-keep_tail:]
                )
                overage = 0

    return {
        "project_dir": project_dir,
        "latest_plan": latest_plan,
        "latest_meta": latest_meta,
        "structure_warnings": structure_warnings,
        "unresolved": unresolved,
        "robustness": configured_robustness(state),
        "settled_tiebreaker_decisions": settled_decisions,
        "verification_delta": verification_delta,
        "verification_raw_log_path": verification_raw_log_path,
    }


def _build_checks_template(
    plan_dir: Path,
    state: PlanState,
    checks: tuple[dict[str, Any], ...],
) -> list[dict[str, object]]:
    checks_template = []
    for check in checks:
        entry: dict[str, object] = {
            "id": check["id"],
            "question": check["question"],
            "guidance": check.get("guidance", ""),
            "findings": [],
        }
        checks_template.append(entry)

    iteration = state.get("iteration", 1)
    if iteration > 1:
        prior_path = plan_dir / f"critique_v{iteration - 1}.json"
        if prior_path.exists():
            prior = read_json(prior_path)
            active_check_ids = {check["id"] for check in checks}
            prior_checks = {
                c.get("id"): c for c in prior.get("checks", [])
                if isinstance(c, dict) and c.get("id") in active_check_ids
            }
            registry = load_flag_registry(plan_dir)
            flag_status = {f["id"]: f.get("status", "open") for f in registry.get("flags", [])}
            for entry in checks_template:
                cid = entry["id"]
                if cid in prior_checks:
                    pc = prior_checks[cid]
                    prior_findings = []
                    flagged_count = sum(1 for f in pc.get("findings", []) if f.get("flagged"))
                    flagged_idx = 0
                    for f in pc.get("findings", []):
                        pf: dict[str, object] = {
                            "detail": f.get("detail", ""),
                            "flagged": f.get("flagged", False),
                        }
                        if f.get("flagged"):
                            flagged_idx += 1
                            fid = cid if flagged_count == 1 else f"{cid}-{flagged_idx}"
                            pf["status"] = flag_status.get(fid, flag_status.get(cid, "open"))
                        else:
                            pf["status"] = "n/a"
                        prior_findings.append(pf)
                    entry["prior_findings"] = prior_findings
    return checks_template


def _build_critique_prompt(
    state: PlanState,
    context: dict[str, Any],
    critique_review_block: str,
    revise_context: str = "",
    selection_why: dict[str, str] | None = None,
    contracts_block: str = "",
) -> str:
    revise_block = ""
    if revise_context:
        revise_block = (
            "Revise context (what changed since the last plan version):\n"
            f"{revise_context}\n\n"
        )
    why_block = ""
    if selection_why:
        why_lines = ["Evaluator targeting notes (why each lens was selected for this iteration):"]
        for check_id, why in selection_why.items():
            if why:
                why_lines.append(f"- {check_id}: {why}")
        if len(why_lines) > 1:
            why_block = "\n".join(why_lines) + "\n\n"
    return textwrap.dedent(
        f"""
        You are an independent reviewer. Critique the plan against the actual repository.

        {contracts_block}
        Project directory:
        {context["project_dir"]}

        {intent_brief_reference(state)}

        Plan:
        {context["latest_plan"]}

        Plan metadata:
        {json_dump(context["latest_meta"]).strip()}

        Plan structure warnings from validator:
        {json_dump(context["structure_warnings"]).strip()}

        Existing flags:
        {json_dump(context["unresolved"]).strip()}

        {_settled_decisions_block(context.get("settled_tiebreaker_decisions", []))}

        {why_block}{revise_block}{critique_review_block}

        Additional guidelines:
        - Robustness level: {context["robustness"]}. {robustness_critique_instruction(context["robustness"])}
        - Over-engineering: prefer the simplest approach that fully solves the problem.
        - Reuse existing flag IDs when the same concern is still open.
        - `verified_flag_ids`: list flag IDs from prior iterations that the revised plan actually resolves (e.g., if the plan was revised to fix FLAG-001, and you confirm the fix is correct, include "FLAG-001"). Only include flags you've verified — don't guess.
        - Verify that the plan follows the expected structure when validator warnings or the outline suggest drift.
        - Additional flags may use these categories: correctness, security, completeness, performance, maintainability, other.
        - Focus on concrete issues, not structural formatting.
        - Complexity audit: flag (a) missing complexity scores on plan steps, (b) inflated scores that would waste premium models on trivial work, and (c) under-rated work that should not run on cheap models. Use category `completeness`.
        """
    ).strip()


def _write_critique_template(
    plan_dir: Path,
    state: PlanState,
    checks: tuple[dict[str, Any], ...],
) -> Path:
    """Write the critique output template file and return its path.

    The file serves as both guide (check questions + guidance) and output
    (findings arrays to fill in). This is the model's sole output channel.
    """
    import json

    template: dict[str, object] = {
        "checks": _build_checks_template(plan_dir, state, checks),
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    output_path = plan_dir / "critique_output.json"
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path


def write_single_check_template(
    plan_dir: Path,
    state: PlanState,
    check: dict[str, Any],
    output_name: str,
) -> Path:
    import json

    template: dict[str, object] = {
        "checks": _build_checks_template(plan_dir, state, (check,)),
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    output_path = plan_dir / output_name
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path


def _critique_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    active_checks: list[dict[str, Any]] | None = None,
    expected_ids: list[str] | None = None,
    revise_context: str = "",
    selection_why: dict[str, str] | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    from ._shared import _render_contracts_block, _resolve_contract_context

    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="critique",
    )
    context = _critique_context(state, plan_dir, root)
    if active_checks is None:
        active_checks = select_active_checks(state, context["robustness"], plan_dir=plan_dir)
    else:
        active_checks = tuple(active_checks)
    # Write the template file — this is both the guide and the output
    output_path = _write_critique_template(plan_dir, state, active_checks)
    iteration = state.get("iteration", 1)

    if active_checks:
        iteration_context = ""
        if iteration > 1:
            iteration_context = (
                "\n\n            This is critique iteration {iteration}. "
                "The template file includes prior findings with their status. "
                "Verify addressed flags were actually fixed, re-flag if inadequate, "
                "and check for new issues introduced by the revision."
            ).format(iteration=iteration)
        critique_review_block = textwrap.dedent(
            f"""
            Your output template is at: {output_path}
            Read this file first — it contains {len(active_checks)} checks, each with a question and guidance.
            For each check, investigate the codebase, then add your findings to the `findings` array for that check.

            {_CRITIQUE_UNVERIFIABLE_ESCAPE_HATCH}

            Each finding needs:
            - "detail": what you specifically checked and what you found (at least a full sentence)
            - "flagged": true if this describes a difference, risk, or tension — even if you think it's justified. false only if purely informational with no possible downside.
            - Every check must end with at least one finding. Never leave a `findings` array empty. If you found no issue, add one detailed `flagged: false` finding explaining what you checked and why it appears clear.

            When in doubt, flag it — the gate can accept tradeoffs, but it can't act on findings it never sees.

            Good: {{"detail": "Checked callers of nthroot_mod in solveset.py line 1205 — passes prime moduli only, consistent with the fix.", "flagged": false}}
            Good: {{"detail": "The fix handles empty tuples but not single-element tuples which need a trailing comma.", "flagged": true}}
            Bad: {{"detail": "No issue found", "flagged": false}}  ← too brief, will be rejected
            Bad: {{"detail": "The hints suggest approach X but the plan uses Y. However Y is consistent with X's intent.", "flagged": false}}  ← a different approach than the hints IS a flag. You found a divergence — flag it. The gate decides if it's acceptable.

            After filling in checks, add any additional concerns to the `flags` array (e.g., security, performance, dependencies).
            Use the standard format (id, concern, category, severity_hint, evidence). This array can be empty.

            Workflow: read the file → investigate → read file again → add finding → write file back. Repeat for each check.{iteration_context}
        """
        ).strip()
    else:
        critique_review_block = textwrap.dedent(
            f"""
            Your output template is at: {output_path}
            Review the plan with a broad scope. Consider whether the approach is correct, whether it covers
            all the places it needs to, whether it would break callers or violate codebase conventions,
            and whether its verification strategy is adequate.

            Place any concrete concerns in the `flags` array in the template file using the standard format
            (id, concern, category, severity_hint, evidence). Leave `checks` as an empty array.

            Workflow: read the file → investigate → read file again → add findings → write file back.
        """
        ).strip()
    return _build_critique_prompt(
        state, context, critique_review_block,
        revise_context=revise_context, selection_why=selection_why,
        contracts_block=contracts_block,
    )


def single_check_critique_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    check: dict[str, Any],
    template_path: Path,
) -> str:
    context = _critique_context(state, plan_dir, root)
    iteration = state.get("iteration", 1)
    iteration_context = ""
    if iteration > 1:
        iteration_context = (
            "\n\n            This is critique iteration {iteration}. "
            "The template file includes prior findings with their status. "
            "Verify addressed flags were actually fixed, re-flag if inadequate, "
            "and check for new issues introduced by the revision."
        ).format(iteration=iteration)
    critique_review_block = textwrap.dedent(
        f"""
        Your output template is at: {template_path}
        Read this file first — it contains 1 check with a question and guidance.
        Investigate only this check, then add your findings to the `findings` array for that check.

        {_CRITIQUE_UNVERIFIABLE_ESCAPE_HATCH}

        Check ID: {check["id"]}
        Question: {check["question"]}
        Guidance: {check.get("guidance", "")}

        Each finding needs:
        - "detail": what you specifically checked and what you found (at least a full sentence)
        - "flagged": true if this describes a difference, risk, or tension — even if you think it's justified. false only if purely informational with no possible downside.
        - This check must end with at least one finding. Never leave its `findings` array empty. If you found no issue, add one detailed `flagged: false` finding explaining what you checked and why it appears clear.

        When in doubt, flag it — the gate can accept tradeoffs, but it can't act on findings it never sees.

        Good: {{"detail": "Checked callers of nthroot_mod in solveset.py line 1205 — passes prime moduli only, consistent with the fix.", "flagged": false}}
        Good: {{"detail": "The fix handles empty tuples but not single-element tuples which need a trailing comma.", "flagged": true}}
        Bad: {{"detail": "No issue found", "flagged": false}}  ← too brief, will be rejected
        Bad: {{"detail": "The hints suggest approach X but the plan uses Y. However Y is consistent with X's intent.", "flagged": false}}  ← a different approach than the hints IS a flag. You found a divergence — flag it. The gate decides if it's acceptable.

        After filling in checks, add any additional concerns to the `flags` array (e.g., security, performance, dependencies).
        Use the standard format (id, concern, category, severity_hint, evidence). This array can be empty.

        Workflow: read the file → investigate → read file again → add finding → write file back. Repeat for this check.{iteration_context}
    """
    ).strip()
    return _with_anchor_block(
        _build_critique_prompt(state, context, critique_review_block),
        state,
        plan_dir,
        audience="parallel_critique",
    )
