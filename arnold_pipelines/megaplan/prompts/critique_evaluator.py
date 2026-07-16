"""Critique evaluator prompt — selects which lenses to fire and rates their difficulty.

The evaluator reads the finished plan, the task graph, and the 9-lens
catalog, then decides which lenses to fire / skip and rates each selected
lens's complexity 1–10.  The profile maps complexity scores to models;
the evaluator never names a vendor or model.  Every lens fires by default;
a skip requires a concrete reason.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import (
    intent_and_notes_block,
    intent_brief_reference,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    read_json,
)
from arnold_pipelines.megaplan.audits.robustness import CRITIQUE_CHECKS
from arnold_pipelines.megaplan.audits.critique_evaluator import MAX_OTHER_AREAS
from arnold_pipelines.megaplan.types import PlanState


def _render_differential_section(
    flag_lifecycle: dict,
    iteration_pressure: list,
    gate_signals: dict,
    iteration: int,
) -> str:
    """Render the revise-loop differential context block for iteration N >= 2."""
    from arnold_pipelines.megaplan.audits.iteration import render_pressure_table

    flags = flag_lifecycle.get("flags", [])
    verified = [f for f in flags if f.get("status") == "verified"]
    signals = gate_signals.get("signals", {})
    unresolved = signals.get("unresolved_flags", [])
    recurring = signals.get("recurring_critiques", [])
    trajectory = signals.get("loop_summary", "")
    plan_delta = signals.get("plan_delta_from_previous")
    delta_str = f"{plan_delta:.1f}%" if plan_delta is not None else "n/a"

    reopened_entries = [e for e in iteration_pressure if e.get("addressed_then_reopened_count", 0) > 0]
    recurring_group_entries = [e for e in iteration_pressure if e.get("iterations_open", 0) >= 2 and e.get("addressed_then_reopened_count", 0) == 0]

    lines: list[str] = [
        f"## Revise-Loop Differential Context (Iteration {iteration})",
        "",
        "This is a revise iteration. Use the signals below to assign lenses",
        "differentially. Do NOT produce a per-section plan diff — use only",
        f"flag-centric signals. Scalar plan delta from previous: **{delta_str}**.",
        "",
    ]

    if verified:
        lines.append("### Verified Flags — Do Not Re-Litigate")
        lines.append("")
        lines.append("These flags are already `verified`. Skip lenses whose **sole**")
        lines.append("purpose would be to re-examine a concern already resolved here.")
        lines.append("")
        for f in verified:
            lines.append(f"- `{f['id']}`: {f.get('concern', '')}")
        lines.append("")

    if reopened_entries:
        lines.append("### Addressed-Then-Reopened Flags — Escalate")
        lines.append("")
        lines.append("These concerns were marked addressed but reopened. Rate the")
        lines.append("complexity **higher** for any lens that touches these concerns.")
        lines.append("")
        for e in reopened_entries:
            concern = e.get("representative_concern", "")[:80]
            count = e.get("addressed_then_reopened_count", 0)
            lines.append(
                f"- Group `{e['fuzzy_group_id']}` (reopened {count}x): "
                f"{concern} [flags: {', '.join(e.get('member_flag_ids', []))}]"
            )
        lines.append("")

    if recurring_group_entries:
        lines.append("### Recurring Flag Groups — Escalate")
        lines.append("")
        lines.append("These concerns have appeared across multiple iterations without being")
        lines.append("addressed. Rate complexity higher for lenses touching these concerns.")
        lines.append("")
        for e in recurring_group_entries:
            concern = e.get("representative_concern", "")[:80]
            lines.append(
                f"- Group `{e['fuzzy_group_id']}` ({e.get('iterations_open', 0)} iters): "
                f"{concern} [flags: {', '.join(e.get('member_flag_ids', []))}]"
            )
        lines.append("")

    pressure_table = render_pressure_table(iteration_pressure)
    if pressure_table:
        lines.append("### Iteration Pressure Summary")
        lines.append("")
        lines.append("```")
        lines.append(pressure_table)
        lines.append("```")
        lines.append("")

    if unresolved:
        lines.append("### Unresolved Significant Flags (from prior gate)")
        lines.append("")
        for f in unresolved:
            lines.append(
                f"- `{f['id']}` [{f.get('category', '')} / {f.get('severity', '')}]: "
                f"{f.get('concern', '')}"
            )
        lines.append("")

    if recurring:
        lines.append("### Recurring Critiques (from prior gate)")
        lines.append("")
        for r in recurring[:5]:
            lines.append(f"- {r}")
        lines.append("")

    if trajectory:
        lines.append("### Loop Trajectory")
        lines.append("")
        lines.append(trajectory)
        lines.append("")

    lines += [
        "### Differential Assignment Rules",
        "",
        "1. **Escalate for recurring/reopened**: For any lens touching a concern",
        "   resembling an addressed-then-reopened or recurring flag group above,",
        "   rate the complexity **higher**.",
        "2. **Verify just-addressed flags**: Fire lenses that can confirm whether",
        "   flags from the prior critique were genuinely resolved in this revision.",
        "3. **Skip verified flags**: Lenses whose sole purpose is to re-examine an",
        "   already-`verified` flag should be skipped (cite the flag id in `why`).",
        "4. **Flag-centric only**: No per-section plan diff. Reason only from the",
        "   flag lifecycle and pressure signals above.",
        "5. **Keep distinct from gate**: This differential assignment is NOT the",
        "   gate's loop/no-loop decision. Assign lenses based on what needs fresh",
        "   scrutiny, independent of whether the loop will continue.",
        "",
    ]
    return "\n".join(lines)


def _format_lens_catalog() -> str:
    """Render the 9-lens CRITIQUE_CHECKS as a structured catalog."""
    lines = []
    for check in CRITIQUE_CHECKS:
        lines.append(
            f"### Lens: `{check['id']}` (tier: {check['tier']}, "
            f"category: {check['category']})"
        )
        lines.append(f"**Question:** {check['question']}")
        guidance = check.get("guidance", "")
        if guidance:
            lines.append(f"**Guidance:** {guidance}")
        lines.append("")
    return "\n".join(lines)


def _render_prep_section(
    prep_dossier_text: str | None, prep_metrics: dict | None
) -> str:
    """Render the "Prep that preceded this plan" section.

    Surfaces the prep dossier plus the decision-relevant coverage signals from
    ``prep_metrics.json`` (counts, gaps, contradictions) so the evaluator can
    fire lenses with knowledge of where prep was thorough vs. where it left
    holes. Returns ``""`` when no prep artifacts are available.
    """
    if not prep_dossier_text and not prep_metrics:
        return ""
    lines = [
        "## Prep that preceded this plan",
        "",
        "This plan was produced after a multi-step prep phase (triage -> research",
        "fan-out -> distill). Use the prep record below when deciding which lenses",
        "to fire: areas prep researched thoroughly may need less scrutiny, while",
        "areas prep flagged as gaps, contradictions, or timed-out research warrant",
        "extra attention from the critics.",
        "",
    ]
    if prep_metrics:
        coverage_bits = [
            f"{key}={prep_metrics[key]}"
            for key in (
                "area_count",
                "fanout_count",
                "completed_count",
                "partial_count",
                "timed_out_count",
                "error_count",
            )
            if key in prep_metrics
        ]
        if coverage_bits:
            lines.append("**Prep coverage:** " + ", ".join(coverage_bits))
            lines.append("")
        gap_notes = prep_metrics.get("gap_notes") or []
        if gap_notes:
            lines.append("**Gaps prep could not close:**")
            lines += [f"- {note}" for note in gap_notes]
            lines.append("")
        contradiction_notes = prep_metrics.get("contradiction_notes") or []
        if contradiction_notes:
            lines.append("**Contradictions surfaced in research:**")
            lines += [f"- {note}" for note in contradiction_notes]
            lines.append("")
    if prep_dossier_text:
        lines += ["**Prep dossier:**", "", prep_dossier_text.strip(), ""]
    return "\n".join(lines) + "\n\n"


def _critique_evaluator_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    flag_lifecycle: dict | None = None,
    iteration_pressure: list | None = None,
    gate_signals: dict | None = None,
    revise_resolutions: list[dict[str, Any]] | None = None,
    plan_diff: str | None = None,
    prep_dossier_text: str | None = None,
    prep_metrics: dict | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    """Assemble the critique evaluator prompt.

    Renders the finished plan + task graph, the intent/issue-hints/notes
    block, the 9-lens catalog, a 1–10 complexity rubric with FLOOR rules,
    and the fire-by-default / justify-to-skip contract.  The evaluator
    never names models or vendors — the profile maps complexity to models.

    When prep_dossier_text / prep_metrics are supplied, a "Prep that preceded
    this plan" section is rendered so the evaluator selects lenses with the
    prep research record in view (gaps and contradictions warrant scrutiny).

    When iteration >= 2 and flag_lifecycle / iteration_pressure / gate_signals
    are supplied, a differential context section is prepended that guides
    escalation for recurring flags and verification of just-addressed ones.

    When iteration >= 2 and revise_resolutions / plan_diff are supplied, a
    verify block is rendered that asks the evaluator to adjudicate each
    resolution claim against the plan diff.
    """
    from ._shared import _render_contracts_block, _resolve_contract_context

    contracts_block = _render_contracts_block(
        _resolve_contract_context(state, contract_context),
        audience="critique_evaluator",
    )
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    intent_block = intent_and_notes_block(state)

    lens_catalog = _format_lens_catalog()

    # Collect all known check ids for the contract
    all_check_ids = [check["id"] for check in CRITIQUE_CHECKS]

    prep_section = _render_prep_section(prep_dossier_text, prep_metrics)

    iteration = state.get("iteration", 1)
    differential_section = ""
    if (
        iteration >= 2
        and flag_lifecycle is not None
        and iteration_pressure is not None
        and gate_signals is not None
    ):
        differential_section = _render_differential_section(
            flag_lifecycle, iteration_pressure, gate_signals, iteration
        ) + "\n\n"

    # ── Verify block (iteration >= 2 with resolutions + diff) ──────────
    verify_section = ""
    if iteration >= 2 and revise_resolutions and plan_diff:
        verify_lines: list[str] = [
            "## Flag Resolution Verification",
            "",
            "The plan was revised in this iteration.  Below are every flag that",
            "carried a resolution (addressed or rejected) from the reviser.",
            "Compare each resolution claim against the unified plan diff and",
            "emit a `flag_verifications` entry.",
            "",
        ]
        for res in revise_resolutions:
            fid = res.get("id", "?")
            concern = res.get("concern", "")
            evidence = res.get("evidence", "")
            resolution = res.get("resolution", {})
            kind = resolution.get("kind", "?") if isinstance(resolution, dict) else "?"
            claim = resolution.get("claim", "") if isinstance(resolution, dict) else ""
            where = resolution.get("where", "") if isinstance(resolution, dict) else ""
            verify_lines.append(f"### Flag `{fid}` (revise action: {kind})")
            verify_lines.append(f"- **Original concern:** {concern}")
            verify_lines.append(f"- **Original evidence:** {evidence}")
            verify_lines.append(f"- **Revise claim:** {claim}")
            verify_lines.append(f"- **Revise where:** {where}")
            verify_lines.append("")
            if kind == "rejected":
                verify_lines.append(
                    "**Rejected flag rule:** This flag was rejected by the author "
                    "as invalid or out of scope.  Only re-raise it if you have "
                    "**NEW evidence the author missed**.  If the rejection stands, "
                    "the outcome must be `accepted_tradeoff`."
                )
                verify_lines.append("")
        verify_lines += [
            "### Unified plan diff",
            "",
            "```diff",
            plan_diff,
            "```",
            "",
            "### Verification instructions",
            "",
            "For **each flag listed above**, pick the single most relevant lens",
            f"(from {', '.join('`' + cid + '`' for cid in all_check_ids)}) and emit",
            "one `flag_verifications` entry:",
            "",
            "- **`verified`** — the diff supports the resolution claim (the change",
            "  described in the claim is visible in the diff).",
            "- **`open`** — cosmetic or no-op change, or the diff does not support",
            "  the claim.  The concern remains unresolved.",
            "- **`accepted_tradeoff`** — the flag was soundly rejected AND the",
            "  rejection stands (no new evidence).  Also use this for any flag",
            "  where the revision intentionally chose not to address a real",
            "  concern and the reasoning is defensible.",
            "",
            "Each entry needs: `flag_id`, `lens` (one of the lens ids above),",
            "`outcome` (verified / open / accepted_tradeoff), and `rationale`",
            "(cite specific lines from the diff or plan text).",
            "Use exactly one catalog lens id for `lens`; do not combine ids",
            "with slashes, commas, plus signs, or prose such as",
            "`correctness/all_locations`.",
            "",
            "Always include the `flag_verifications` field. Use an empty list",
            "`[]` when there are no flag resolutions to verify.",
            "",
        ]
        verify_section = "\n".join(verify_lines) + "\n\n"

    output_path = _write_critique_evaluator_template(plan_dir, state)

    return textwrap.dedent(
        f"""\
        You are the Critique Evaluator. Your job is to decide which critique
        lenses to fire and to rate each selected lens's difficulty on a 1–10
        complexity scale. The profile will map your complexity scores to
        models — you do NOT name models or vendors.

        {contracts_block}
        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Finished plan:
        {latest_plan}

        Task graph (plan metadata):
        {json_dump(latest_meta).strip()}

        {intent_block}

        Your output template is at: {output_path}
        Read this file first by calling `read_file` with `path` exactly `{output_path}` — it contains the expected JSON structure with all known check IDs pre-populated in `skipped`.
        If you cannot supply that exact non-empty path, do not call `read_file`.
        Move checks you are firing to `selections`, fill `why` for the rest, and write the file back.
        If you cannot use file tools, return the populated JSON structure inline as your response instead.

        {prep_section}{differential_section}{verify_section}## Critique Lens Catalog ({len(CRITIQUE_CHECKS)} lenses)

        {lens_catalog}

        ## Complexity Rubric (1–10)

        Rate each selected lens on its **hardest realistic** aspect (composite of difficulty + scale + blast radius/consequence). When genuinely torn between two tiers, choose the LOWER one UNLESS you can name the specific cascading, test-evading failure that earns the higher tier.

        - **1 = MICRO:** tightly scoped, obvious check (one small location or grep). Low difficulty, negligible scale.
        - **2 = LIGHT:** small, well-understood check (localized, linear answer). Limited reasoning, very small surface.
        - **3 = ROUTINE:** normal check with clear path (small feature area). Low-moderate difficulty, contained scale.
        - **4 = STANDARD:** bounded check needing some judgment (small module or feature). Touches several files but risks understandable.
        - **5 = MEANINGFUL:** moderately sized with genuine complexity (multiple components, non-obvious edges). Scale or difficulty requires deliberate planning.
        - **6 = HEAVY:** large or difficult check crossing boundaries (several interacting requirements, meaningful risk of missing issues).
        - **7 = DEMANDING:** high-complexity check (uncertain causes, non-trivial architecture, broad surface, delicate constraints). Both dimensions elevated.
        - **8 = MAJOR:** major subsystem or broad repair check (many dependencies, substantial validation needs). Large and cognitively demanding.
        - **9 = CRITICAL:** high-risk check affecting core paths, data integrity, security or many consumers. Scale broad or difficulty exceptionally subtle.
        - **10 = EXCEPTIONAL:** system-defining check with maximum scale/uncertainty/consequence (core engine, wire format, consistency model). Requires expert reasoning and comprehensive validation.

        **FLOOR rules (hard minimum) — these two lenses ONLY:**
        - `correctness` — NEVER below tier 4. A correctness defect that
          slips through is the most expensive failure mode.
        - `prerequisite_ordering` — NEVER below tier 4. Partial-precondition
          contradictions are subtle and cascade into runtime failures; a
          weak model will miss them.
        Every OTHER lens must EARN tier 4-10 under the rubric above; the
        expected home for an ordinary, locally-verifiable check is tier 2-3.
        Do not let "this plan is large" inflate a lens whose own question is
        answerable by a focused read.

        ## Assignment Contract

        Select the FEWEST lenses that cover the real risk; keep the set lean
        rather than firing broad, overlapping checks. If a check's verification
        would likely depend on things outside this project root (external or
        sibling repos), files the plan only creates later, or runtime-only
        behavior, either scope the lens to what is statically checkable in this
        repo or name that dependency in its justification so the worker and gate
        expect a partial or `unverifiable` result.

        - **Select deliberately**: a lens fires only when it covers a concrete
          risk in this plan.
        - **Justify to skip**: every skipped lens must include a concrete, specific
          `why` — a reason grounded in the plan's content, not a generic dismissal.
        - **Every lens is assigned exactly once**: the union of `selections` and
          `skipped` must cover all {len(all_check_ids)} lens ids with no overlap
          and no omission.
        - **At least one lens must be selected** — an all-skip verdict is rejected.
        - **Every selected catalog lens** must emit a `complexity` (int 1–10) and
          a `complexity_justification` (one or two sentences citing why this
          lens sits at exactly that tier — reference the lens's question, the
          plan's concrete files/interfaces/risks). The justification must be
          defensible against a reviewer who disagrees. A bare restatement of the
          rubric ("this is complex") is not acceptable.
        - **`other` custom areas**: an `other` selection is additive (does not
          replace a catalog lens). It requires `area` (a non-empty name for the
          custom critique area), `why` (the probe question for the critic),
          `complexity`, and `complexity_justification`. At most {MAX_OTHER_AREAS}
          `other` areas.
        - **Do not invent check IDs**: North Star, anchor, product, or project-
          specific concerns must either use one of the catalog lens IDs above
          or `check_id: "other"` with the specific concern named in `area`.
          Values such as `north_star_alignment`, `compatibility_shim_risk`, or
          `behavior_preservation` are invalid as `check_id`s.

        Your output must be a JSON object with these keys:
        - `selections`: list of objects. For catalog lenses:
          {{check_id, complexity (int 1–10), complexity_justification, why?}}
          For `other` custom areas:
          {{check_id: "other", area, why, complexity (int 1–10), complexity_justification}}
        - `skipped`: list of {{check_id, why}} objects
        - `evaluator_model`: your own model identifier string
        - `flag_verifications`: list of
          {{flag_id, lens, outcome, rationale}} objects where outcome is
          one of "verified" / "open" / "accepted_tradeoff"; use [] when the
          Flag Resolution Verification section is absent. `lens` must be
          exactly one catalog lens id; combined lens strings such as
          `correctness/all_locations` are invalid.

        Remember: prefer the smallest selected set that still covers the real
        risk.  Skipping requires a justification.  When you skip, explain *why
        this specific lens is unnecessary for this specific plan* — do not
        write generic cop-outs.
        """
    ).strip()


def _write_critique_evaluator_template(
    plan_dir: Path,
    state: PlanState,
) -> Path:
    """Write the critique evaluator output template file and return its path.

    Pre-populates ``skipped`` with every known check id from
    :data:`CRITIQUE_CHECKS` so the model moves selections to
    ``selections`` and fills ``why`` for the rest.  This is the
    same ID-prepopulation pattern used by review and critique
    templates.
    """
    import json

    all_check_ids = [check["id"] for check in CRITIQUE_CHECKS]
    skipped: list[dict[str, str]] = [
        {"check_id": cid, "why": ""} for cid in all_check_ids
    ]

    template: dict[str, object] = {
        "selections": [],
        "skipped": skipped,
        "evaluator_model": "",
        "flag_verifications": [],
    }

    output_path = plan_dir / "critique_evaluator_output.json"
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return output_path
