"""Tiebreaker synthesis renderer — pure function, no LLM calls."""

from __future__ import annotations

from typing import Any


def render_synthesis(
    question: str,
    researcher: dict[str, Any],
    challenger: dict[str, Any],
) -> str:
    sections: list[str] = []

    sections.append(f"# Tiebreaker: Decision Brief\n\n## Decision\n\n{question}")

    # Options Considered (table)
    options = researcher.get("options", [])
    rows = ["| Option | Description | Assumptions | Costs |", "| --- | --- | --- | --- |"]
    for opt in options:
        assumptions = "; ".join(opt.get("assumptions", []))
        costs = "; ".join(opt.get("costs", []))
        rows.append(f"| {opt.get('name', '')} | {opt.get('description', '')} | {assumptions} | {costs} |")
    for missed in challenger.get("missing_options", []):
        rows.append(f"| {missed.get('name', '')} *(challenger)* | {missed.get('description', '')} | — | — |")
    sections.append(f"## Options Considered\n\n" + "\n".join(rows))

    # Evidence Summary
    evidence_lines = []
    for ev in researcher.get("evidence", []):
        paths = ", ".join(ev.get("file_paths", []))
        evidence_lines.append(f"- **{ev.get('claim', '')}** [{ev.get('evidence_type', '')}] ({paths})")
    if challenger.get("measurements_vs_assumptions"):
        evidence_lines.append(f"\n*Challenger assessment:* {challenger['measurements_vs_assumptions']}")
    sections.append(f"## Evidence Summary\n\n" + "\n".join(evidence_lines) if evidence_lines else "## Evidence Summary\n\nNo evidence collected.")

    # Researcher Pick
    pick = researcher.get("preliminary_pick", {})
    sections.append(
        f"## Researcher Pick\n\n"
        f"**{pick.get('option_name', 'N/A')}** — {pick.get('rationale', '')}\n\n"
        f"*Least sure about:* {pick.get('what_im_least_sure_about', 'N/A')}"
    )

    # Challenger Assessment
    counter = challenger.get("counter_recommendation", {})
    hard_cases_lines = []
    for hc in challenger.get("hard_cases", []):
        hard_cases_lines.append(f"- {hc.get('scenario', '')}: breaks **{hc.get('which_option_breaks', '')}** ({hc.get('severity', '')})")
    challenger_section = (
        f"## Challenger Assessment\n\n"
        f"**Pick:** {counter.get('option_name', 'N/A')} — {counter.get('rationale', '')}\n\n"
        f"**Agrees with researcher:** {'Yes' if counter.get('agrees_with_researcher') else 'No'}"
    )
    if hard_cases_lines:
        challenger_section += f"\n\n**Hard cases:**\n" + "\n".join(hard_cases_lines)
    if challenger.get("aging_analysis"):
        challenger_section += f"\n\n**Aging analysis:** {challenger['aging_analysis']}"
    sections.append(challenger_section)

    # Where They Agree
    agrees_with = counter.get("agrees_with_researcher", False)
    if agrees_with:
        agree_text = f"Both recommend **{pick.get('option_name', 'N/A')}**."
    else:
        agree_text = _find_agreements(researcher, challenger)
    sections.append(f"## Where They Agree\n\n{agree_text}")

    # Where They Disagree
    if agrees_with:
        disagree_text = "No fundamental disagreement on the pick."
        if challenger.get("measurements_vs_assumptions"):
            disagree_text += f" However, the challenger notes: {challenger['measurements_vs_assumptions']}"
    else:
        disagree_text = (
            f"Researcher picks **{pick.get('option_name', 'N/A')}**; "
            f"challenger picks **{counter.get('option_name', 'N/A')}**.\n\n"
            f"Researcher rationale: {pick.get('rationale', 'N/A')}\n\n"
            f"Challenger rationale: {counter.get('rationale', 'N/A')}"
        )
    sections.append(f"## Where They Disagree\n\n{disagree_text}")

    # Recommended Framing
    reframings = challenger.get("reframings", [])
    if reframings:
        framing_text = "\n".join(f"- {r}" for r in reframings)
    else:
        framing_text = "No alternative framings suggested."
    sections.append(f"## Recommended Framing\n\n{framing_text}")

    # Fallback Plan
    if agrees_with:
        fallback_text = f"If **{pick.get('option_name', 'N/A')}** fails, revisit the challenger's hard cases for pivot criteria."
    else:
        fallback_text = (
            f"If the chosen option fails:\n"
            f"- If **{pick.get('option_name', 'N/A')}** was chosen, consider pivoting to **{counter.get('option_name', 'N/A')}**.\n"
            f"- If **{counter.get('option_name', 'N/A')}** was chosen, consider pivoting to **{pick.get('option_name', 'N/A')}**."
        )
    sections.append(f"## Fallback Plan\n\n{fallback_text}")

    return "\n\n".join(sections) + "\n"


def _find_agreements(
    researcher: dict[str, Any],
    challenger: dict[str, Any],
) -> str:
    researcher_options = {o.get("name") for o in researcher.get("options", [])}
    challenger_missing = {o.get("name") for o in challenger.get("missing_options", [])}
    shared = researcher_options - challenger_missing
    if shared:
        return f"Both consider these options viable: {', '.join(sorted(shared))}."
    return "Limited agreement on the option space."
