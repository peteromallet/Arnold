"""Gate-phase prompt builders and summaries."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold.pipelines.megaplan._core import (
    configured_robustness,
    current_iteration_artifact,
    intent_brief_reference,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
    unresolved_significant_flags,
)
from arnold.pipelines.megaplan.flags import flag_resolution_summary
from arnold.pipelines.megaplan.audits.iteration import compute_iteration_pressure, render_pressure_table
from arnold.pipelines.megaplan.types import FlagRegistry, PlanState

from ._shared import _gate_debt_block


def _iteration_pressure_block(state: PlanState, plan_dir: Path) -> str:
    entries = compute_iteration_pressure(plan_dir, state)
    if not entries:
        return ""
    return render_pressure_table(entries)


def _gate_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    from ._shared import _render_contracts_block, _resolve_contract_context

    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="gate",
    )
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    gate_signals = read_json(
        current_iteration_artifact(plan_dir, "gate_signals", state["iteration"])
    )
    flag_registry = load_flag_registry(plan_dir)
    unresolved = unresolved_significant_flags(flag_registry)
    open_flags = [
        {
            "id": flag["id"],
            "concern": flag["concern"],
            "evidence": flag.get("evidence", ""),
            "revise_summary": flag_resolution_summary(flag),
            "category": flag["category"],
            "severity": flag.get("severity", "unknown"),
            "status": flag["status"],
            "weight": flag.get("weight"),
        }
        for flag in unresolved
    ]
    robustness = configured_robustness(state)
    debt_block = _gate_debt_block(plan_dir, root)
    # Critique check summary — flagged counts only (unflagged findings are in the
    # artifact JSON for audit but not injected into the gate prompt).
    critique_checks_block = ""
    critique_path = current_iteration_artifact(plan_dir, "critique", state["iteration"])
    if Path(critique_path).exists():
        critique_data = read_json(critique_path)
        checks = critique_data.get("checks", [])
        if checks:
            check_lines = []
            for check in checks:
                findings = check.get("findings", [])
                flagged_count = sum(1 for f in findings if f.get("flagged"))
                status = f"{flagged_count} flagged" if flagged_count else "clear"
                check_lines.append(f"- {check.get('id', '?')}: {status}")
            critique_checks_block = (
                "Critique check summary:\n        "
                + "\n        ".join(check_lines)
            )
    return textwrap.dedent(
        f"""
        You are the gatekeeper for the megaplan workflow. Make the continuation decision directly.

        {contracts_block}
        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Plan:
        {latest_plan}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate signals:
        {json_dump(gate_signals).strip()}

        {critique_checks_block}

        Unresolved significant flags:
        {json_dump(open_flags).strip()}

        Addressed but unverified flags:
        {json_dump(gate_signals.get("signals", {}).get("addressed_flags", [])).strip()}

        {debt_block}

        {_iteration_pressure_block(state, plan_dir)}

        Robustness level:
        {robustness}

        Requirements:
        - Decide exactly one of: PROCEED, ITERATE, ESCALATE, TIEBREAKER.
        - Use the weighted score, flag details (including `evidence`), plan delta, recurring critiques, and preflight results as judgment context.
        - PROCEED when execution should move forward now.
        - ITERATE when revising the plan is the best next move.
        - ESCALATE when the loop is stuck, churn is recurring, or user intervention is needed.
        - TIEBREAKER when a flag group reflects an *unresolvable constraint tension* (architectural or philosophical — requires a human call) rather than a plan-quality issue. Use TIEBREAKER only when the Iteration Pressure Analysis shows `addressed_then_reopened_count >= 2` for a fuzzy group OR the group has >=2 member flags across >=2 iterations. If the concern is simply that the plan writer hasn't tried hard enough, use ITERATE instead. When recommending TIEBREAKER you MUST provide `tiebreaker_question` (the decision question for human resolution), `tiebreaker_flag_ids` (which flags this resolves), and `tiebreaker_fuzzy_group_id` (which group this resolves). Cite specific flag IDs and iterations in your rationale.
        - `signals_assessment`: one paragraph summarizing score trajectory, flag status, and preflight posture.

        Flags come in three gate states:
        - **Blocking** (severity = significant/likely-significant): These are serious concerns. If you recommend PROCEED, you MUST provide a `flag_resolutions` entry for every blocking flag. There is no implicit acceptance.
        - **Addressed but unverified**: The revision claims these were fixed. Treat significant/likely-significant addressed flags as verification obligations. If you recommend PROCEED, provide a `flag_resolutions` entry with `action: "verify_fixed"` and concrete evidence for every addressed blocking flag. If the evidence is insufficient, choose ITERATE.
        - **Noted** (everything else): Acknowledge in your rationale but they don't block PROCEED.

        If there are blocking or addressed-blocking flags and you want to PROCEED, provide `flag_resolutions` with one entry per flag. If you cannot resolve every required flag, choose ITERATE (send back for revision) or ESCALATE (human intervention needed).
        Structurally unresolvable flags (for example, infrastructure outside the repo or product decisions that require a human) are ESCALATE, not PROCEED with a non-answer.

        For each required flag:
        - **verify_fixed**: The concern was real and the revised plan now fixes it. Evidence must cite the concrete changed plan section, file path, command, or contract that proves the fix.
        - **dispute**: The critique is factually wrong. Evidence must cite something specific (file path, line, API doc, etc.). Generic statements like "handled correctly" are invalid.
        - **accept_tradeoff**: The concern is real but intentionally accepted as a known limitation. Rationale must be specific to this flag. Boilerplate like "acceptable within scope" is invalid.
        - Schema requirement: every `flag_resolutions` entry must include both `evidence` and `rationale`. Use `""` for the field that does not apply to that action.

        If there are no blocking flags, return `flag_resolutions: []`.
        Always return `accepted_tradeoffs`; use `[]` when none apply.

        Populate `settled_decisions` with design choices that should carry into review without re-litigation. Return typed objects, never bare strings: `[{{"id": "SD1", "decision": "...", "rationale": "..."}}]`. Return `[]` when there are none.

        Example:
        ```json
        {{
          "recommendation": "PROCEED",
          "rationale": "Core fix is correct. Convention concern accepted.",
          "signals_assessment": "Score stable at 2.5, preflight passed, no recurring critiques.",
          "warnings": ["Verify edge case with composite moduli during execution."],
          "flag_resolutions": [
            {{"flag_id": "addressed-1", "action": "verify_fixed", "evidence": "plan_v3.md Phase 1 Step 2 requires an exact __all__ assertion and tests/characterization/test_import_surface.py coverage.", "rationale": ""}},
            {{"flag_id": "correctness-1", "action": "dispute", "evidence": "allow_migrate and allow_migrate_model produce identical behavior for this use case (verified at django/db/utils.py:286).", "rationale": ""}},
            {{"flag_id": "performance-1", "action": "accept_tradeoff", "evidence": "", "rationale": "Cold-start latency remains 40ms above target because the cache warmup job is owned by platform and outside this repo; rollout is still approved for the limited internal beta."}},
            {{"flag_id": "conventions-1", "action": "accept_tradeoff", "evidence": "", "rationale": "Minor naming inconsistency is confined to this helper and would create churn across generated fixtures; track it as follow-up cleanup instead of blocking this fix."}}
          ],
          "accepted_tradeoffs": [],
          "settled_decisions": [
            {{"id": "SD1", "decision": "Keep the migration as a data-only migration", "rationale": "The schema change belongs to the already-approved follow-up and should not be re-litigated during review."}}
          ]
        }}
        ```
        """
    ).strip()


def _collect_critique_summaries(
    plan_dir: Path, iteration: int
) -> list[dict[str, object]]:
    """Gather a compact list of all critique rounds for the finalize prompt."""
    summaries: list[dict[str, object]] = []
    for i in range(1, iteration + 1):
        path = plan_dir / f"critique_v{i}.json"
        if path.exists():
            data = read_json(path)
            summaries.append(
                {
                    "iteration": i,
                    "flag_count": len(data.get("flags", [])),
                    "verified": data.get("verified_flag_ids", []),
                }
            )
    return summaries


def _flag_summary(registry: FlagRegistry) -> list[dict[str, object]]:
    """Compact flag list for the finalize prompt."""
    return [
        {
            "id": f["id"],
            "concern": f["concern"],
            "evidence": f.get("evidence", ""),
            "revise_summary": flag_resolution_summary(f),
            "status": f["status"],
            "severity": f.get("severity", "unknown"),
        }
        for f in registry["flags"]
    ]
