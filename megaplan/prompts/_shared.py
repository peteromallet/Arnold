"""Shared prompt helpers used across megaplan phases."""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import (
    debt_by_subsystem,
    escalated_subsystems,
    json_dump,
    load_debt_registry,
    read_json,
)


def _resolve_prompt_root(plan_dir: Path, root: Path | None) -> Path:
    if root is not None:
        return root
    if len(plan_dir.parents) >= 3:
        return plan_dir.parents[2]
    return plan_dir


def _gate_summary_or_skipped(plan_dir: Path) -> dict[str, object]:
    carry_path = plan_dir / "gate_carry.json"
    if carry_path.exists():
        carry = read_json(carry_path)
        if isinstance(carry, dict):
            normalized = dict(carry)
            recommendation = normalized.get("recommendation") or normalized.get("verdict")
            if recommendation is not None:
                normalized["recommendation"] = recommendation
            return normalized
        return carry

    gate_path = plan_dir / "gate.json"
    if gate_path.exists():
        gate = read_json(gate_path)
        settled_decisions = gate.get("settled_decisions", [])
        if isinstance(settled_decisions, list):
            settled_decisions = [
                {"id": f"SD{index}", "decision": item, "rationale": ""}
                if isinstance(item, str)
                else item
                for index, item in enumerate(settled_decisions, start=1)
                if isinstance(item, (str, dict))
            ]
        else:
            settled_decisions = []
        return {
            "version": 1,
            "recommendation": gate.get("recommendation", "PROCEED"),
            "passed": gate.get("passed", True),
            "rationale_brief": gate.get("rationale", ""),
            "settled_decisions": settled_decisions,
            "warnings": gate.get("warnings", []),
            "orchestrator_guidance": gate.get("orchestrator_guidance", ""),
            "carried_flags": [
                {
                    "flag_id": item.get("flag_id", ""),
                    "concern_brief": item.get("concern", ""),
                    "rationale_brief": item.get("rationale", ""),
                }
                for item in gate.get("flag_resolutions", [])
                if isinstance(item, dict) and item.get("action") == "accept_tradeoff"
            ],
            "iteration": gate.get("iteration"),
            "produced_at": gate.get("produced_at"),
        }
    return {
        "summary": "No gate phase ran for this robustness level; continue from the approved plan.",
        "recommendation": "proceed",
        "flags": [],
    }


def _gate_audit_or_skipped(plan_dir: Path) -> dict[str, object]:
    gate_path = plan_dir / "gate.json"
    if gate_path.exists():
        return read_json(gate_path)
    return {
        "summary": "No gate phase ran for this robustness level; continue from the approved plan.",
        "recommendation": "proceed",
        "flags": [],
    }


def _grouped_debt_for_prompt(
    plan_dir: Path, root: Path | None
) -> dict[str, list[dict[str, object]]]:
    registry = load_debt_registry(_resolve_prompt_root(plan_dir, root))
    grouped_entries = debt_by_subsystem(registry)
    return {
        subsystem: [
            {
                "id": entry["id"],
                "concern": entry["concern"],
                "occurrence_count": entry["occurrence_count"],
                "plan_ids": entry["plan_ids"],
            }
            for entry in entries
        ]
        for subsystem, entries in sorted(grouped_entries.items())
    }


def _escalated_debt_for_prompt(
    plan_dir: Path, root: Path | None
) -> list[dict[str, object]]:
    registry = load_debt_registry(_resolve_prompt_root(plan_dir, root))
    return [
        {
            "subsystem": subsystem,
            "total_occurrences": total,
            "plan_count": len(
                {plan_id for entry in entries for plan_id in entry["plan_ids"]}
            ),
            "entries": [
                {
                    "id": entry["id"],
                    "concern": entry["concern"],
                    "occurrence_count": entry["occurrence_count"],
                    "plan_ids": entry["plan_ids"],
                }
                for entry in entries
            ],
        }
        for subsystem, total, entries in escalated_subsystems(registry)
    ]


def _debt_watch_lines(plan_dir: Path, root: Path | None) -> list[str]:
    lines: list[str] = []
    for subsystem, entries in sorted(_grouped_debt_for_prompt(plan_dir, root).items()):
        for entry in entries:
            lines.append(
                f"[DEBT] {subsystem}: {entry['concern']} "
                f"(flagged {entry['occurrence_count']} times across {len(entry['plan_ids'])} plans)"
            )
    return lines


def _planning_debt_block(plan_dir: Path, root: Path | None) -> str:
    return textwrap.dedent(
        f"""
        Known accepted debt grouped by subsystem:
        {json_dump(_grouped_debt_for_prompt(plan_dir, root)).strip()}

        Escalated debt subsystems:
        {json_dump(_escalated_debt_for_prompt(plan_dir, root)).strip()}

        Debt guidance:
        - These are known accepted limitations. Do not re-flag them unless the current plan makes them worse, broadens them, or fails to contain them.
        - Prefix every new concern with a subsystem tag followed by a colon, for example `Timeout recovery: retry backoff remains brittle`.
        - When a concern is recurring debt that still needs to be flagged, prefix it with `Recurring debt:` after the subsystem tag, for example `Timeout recovery: Recurring debt: retry backoff remains brittle`.
        """
    ).strip()


def _gate_debt_block(plan_dir: Path, root: Path | None) -> str:
    return textwrap.dedent(
        f"""
        Known accepted debt grouped by subsystem:
        {json_dump(_grouped_debt_for_prompt(plan_dir, root)).strip()}

        Escalated debt subsystems:
        {json_dump(_escalated_debt_for_prompt(plan_dir, root)).strip()}

        Debt guidance:
        - Treat recurring debt as decision context, not background noise.
        - If the current unresolved flags overlap an escalated subsystem, prefer recommending holistic redesign over another point fix.
        """
    ).strip()


def _finalize_debt_block(plan_dir: Path, root: Path | None) -> str:
    watch_lines = _debt_watch_lines(plan_dir, root)
    return textwrap.dedent(
        f"""
        Debt watch items (do not make these worse):
        {json_dump(watch_lines).strip()}
        """
    ).strip()



def _render_prep_block(plan_dir: Path) -> tuple[str, str]:
    prep_path = plan_dir / "prep.json"
    if not prep_path.exists():
        return "", ""
    prep = read_json(prep_path)
    # If prep decided to skip (task was simple enough), return empty —
    # downstream phases will use the original task description as-is
    if prep.get("skip", False):
        return "", ""
    prep = read_json(prep_path)

    def _cell(value: object) -> str:
        if isinstance(value, list):
            value = ", ".join(str(item).strip() for item in value if str(item).strip())
        text = str(value).strip()
        if not text:
            return "-"
        return text.replace("|", "\\|").replace("\n", " ")

    task_summary = (
        str(prep.get("task_summary", "")).strip() or "No task summary provided."
    )

    evidence_items = prep.get("key_evidence", [])
    if isinstance(evidence_items, list) and evidence_items:
        evidence_lines = []
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            point = str(item.get("point", "")).strip() or "Unspecified evidence"
            source = str(item.get("source", "")).strip() or "unspecified source"
            relevance = (
                str(item.get("relevance", "")).strip() or "unspecified relevance"
            )
            evidence_lines.append(
                f"- {point} (source: {source}; relevance: {relevance})"
            )
        evidence_block = (
            "\n".join(evidence_lines)
            if evidence_lines
            else "- No key evidence captured."
        )
    else:
        evidence_block = "- No key evidence captured."

    relevant_code_items = prep.get("relevant_code", [])
    if isinstance(relevant_code_items, list) and relevant_code_items:
        code_lines = [
            "| File | Functions | Why |",
            "| --- | --- | --- |",
        ]
        for item in relevant_code_items:
            if not isinstance(item, dict):
                continue
            code_lines.append(
                f"| {_cell(item.get('file_path', ''))} | {_cell(item.get('functions', []))} | {_cell(item.get('why', ''))} |"
            )
        relevant_code_block = (
            "\n".join(code_lines)
            if len(code_lines) > 2
            else "- No directly relevant code captured."
        )
    else:
        relevant_code_block = "- No directly relevant code captured."

    test_expectation_items = prep.get("test_expectations", [])
    if isinstance(test_expectation_items, list) and test_expectation_items:
        test_lines = []
        for item in test_expectation_items:
            if not isinstance(item, dict):
                continue
            test_id = str(item.get("test_id", "")).strip() or "unnamed test"
            status = str(item.get("status", "")).strip() or "unknown"
            what_it_checks = (
                str(item.get("what_it_checks", "")).strip()
                or "No description provided."
            )
            test_lines.append(f"- [{status}] {test_id}: {what_it_checks}")
        test_expectations_block = (
            "\n".join(test_lines)
            if test_lines
            else "- No explicit test expectations captured."
        )
    else:
        test_expectations_block = "- No explicit test expectations captured."

    constraints = prep.get("constraints", [])
    if isinstance(constraints, list) and constraints:
        constraint_lines = [
            f"- {str(item).strip()}" for item in constraints if str(item).strip()
        ]
        constraints_block = (
            "\n".join(constraint_lines)
            if constraint_lines
            else "- No explicit constraints captured."
        )
    else:
        constraints_block = "- No explicit constraints captured."

    suggested_approach = (
        str(prep.get("suggested_approach", "")).strip()
        or "No suggested approach provided."
    )

    prep_block = textwrap.dedent(
        f"""
        Engineering brief produced from the codebase and task details:

        ### Task Summary
        {task_summary}

        ### Key Evidence
        {evidence_block}

        ### Relevant Code
        {relevant_code_block}

        ### Test Expectations
        {test_expectations_block}

        ### Constraints
        {constraints_block}

        ### Suggested Approach
        {suggested_approach}
        """
    ).strip()
    prep_instruction = (
        "The engineering brief above is evidence gathered from the codebase. "
        "Treat it as the default working context, challenge its conclusions when the code disagrees, "
        "and only do targeted repository lookups when a concrete gap remains."
    )
    return prep_block, prep_instruction
