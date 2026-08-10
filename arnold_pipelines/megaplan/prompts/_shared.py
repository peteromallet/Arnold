"""Shared prompt helpers used across megaplan phases."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import json_dump, read_json
from arnold_pipelines.megaplan.prep_payload import render_suggested_approach
from arnold_pipelines.megaplan.schema_projection import (
    project_schema_owned_fields,
    require_schema_fields,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS


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
            require_schema_fields(
                carry,
                SCHEMAS["gate.json"],
                contract="gate carry prompt consumption",
            )
            normalized = dict(carry)
            recommendation = normalized.get("recommendation") or normalized.get("verdict")
            if recommendation is not None:
                normalized["recommendation"] = recommendation
            return normalized
        return carry

    gate_path = plan_dir / "gate.json"
    if gate_path.exists():
        gate = read_json(gate_path)
        require_schema_fields(
            gate,
            SCHEMAS["gate.json"],
            contract="gate prompt fallback consumption",
        )
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
            **project_schema_owned_fields(
                gate,
                SCHEMAS["gate.json"],
                contract="gate prompt fallback consumption",
            ),
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


def _resolve_contract_context(
    state: Mapping[str, Any],
    contract_context: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    if contract_context is not None:
        return contract_context
    meta = state.get("meta")
    if not isinstance(meta, Mapping):
        return None
    chain_policy = meta.get("chain_policy")
    if not isinstance(chain_policy, Mapping):
        return None
    resolved = chain_policy.get("contract_context")
    return resolved if isinstance(resolved, Mapping) else None


def _render_contracts_block(
    contract_context: Mapping[str, Any] | None,
    *,
    audience: str,
) -> str:
    if not isinstance(contract_context, Mapping):
        return ""
    if contract_context.get("plan_only") is not True:
        return ""

    upstream_contracts = contract_context.get("upstream_contracts")
    if isinstance(upstream_contracts, Mapping):
        contracts = [
            {"milestone_label": label, **(value if isinstance(value, Mapping) else {})}
            for label, value in upstream_contracts.items()
            if isinstance(label, str)
        ]
    elif isinstance(upstream_contracts, list):
        contracts = [item for item in upstream_contracts if isinstance(item, Mapping)]
    else:
        contracts = []
    if not contracts:
        return ""

    intro_map = {
        "plan": (
            "Planning-pass upstream contract context. These interfaces are planned upstream surfaces, "
            "not executed evidence; plan against them without assuming they already exist in the repo."
        ),
        "prep": (
            "Planning-pass upstream contract context. Use these planned upstream interfaces to guide prep "
            "and cross-reference work; they are expected future surfaces, not missing-file defects."
        ),
        "prep-triage": (
            "Planning-pass upstream contract context. Factor these upstream planned interfaces into the "
            "research-area split when they materially shape what the downstream milestone must investigate."
        ),
        "prep-distill": (
            "Planning-pass upstream contract context. Preserve these upstream planned interfaces in the "
            "final prep view only when they materially affect the downstream implementation plan."
        ),
        "critique": (
            "Deferred-verification planning-pass contract context. These upstream-provided interfaces are "
            "planned dependency surfaces, not executed code. Do NOT flag missing files, missing symbols, "
            "or unresolved references to these interfaces as defects — verification is deferred until the "
            "upstream milestone executes. Treat these as interface contracts the plan should honor, "
            "not as missing-code gaps."
        ),
        "critique_evaluator": (
            "Deferred-verification planning-pass contract context. These upstream interfaces are planned "
            "surfaces from dependency milestones that have not yet executed. When assigning critique lenses, "
            "do not route existence/availability checks against these interfaces — verification is deferred. "
            "The plan is a contract consumer, not an implementer of these surfaces."
        ),
        "gate": (
            "Deferred-verification planning-pass contract context. These upstream-provided interfaces are "
            "commitments from dependency milestones, not executed artifacts. Do not treat missing upstream "
            "files, symbols, or artifacts as blocking defects — the gate decision is about THIS milestone's "
            "plan quality, not upstream completion status."
        ),
        "generic": (
            "Planning-pass upstream contract context. These interfaces are planned dependency surfaces, "
            "not executed evidence."
        ),
    }
    intro = intro_map.get(audience, intro_map["generic"])
    lines = ["Planning-pass upstream contract context:", intro, ""]

    for item in contracts:
        label = str(item.get("milestone_label") or item.get("label") or "?").strip() or "?"
        lines.append(f"- Milestone `{label}`")
        provides = item.get("provides", [])
        if not provides and isinstance(item.get("contract"), Mapping):
            provides = item["contract"].get("provides", [])
        if not isinstance(provides, list):
            provides = []
        emitted = False
        for provide in provides:
            if not isinstance(provide, Mapping):
                continue
            name = str(provide.get("name", "")).strip() or "Unnamed provide"
            description = str(provide.get("description", "")).strip()
            details = f": {description}" if description else ""
            lines.append(f"  - `{name}`{details}")
            interfaces = provide.get("interfaces", [])
            if not isinstance(interfaces, list):
                interfaces = []
            for interface in interfaces:
                if not isinstance(interface, Mapping):
                    continue
                symbol = str(interface.get("symbol", "")).strip() or "<unnamed>"
                path = str(interface.get("path", "")).strip() or "<unknown path>"
                signature = str(interface.get("signature", "")).strip()
                rendered = f"    - `{symbol}` at `{path}`"
                if signature:
                    rendered += f" with signature `{signature}`"
                lines.append(rendered)
                emitted = True
        if not emitted:
            lines.append("  - No upstream interfaces recorded.")
    return "\n".join(lines)



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

    suggested_approach = render_suggested_approach(prep.get("suggested_approach", ""))
    if not suggested_approach:
        suggested_approach = "No suggested approach provided."

    open_questions = prep.get("open_questions", [])
    open_questions_section = ""
    if isinstance(open_questions, list) and open_questions:
        oq_lines = []
        for item in open_questions:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "")).strip()
            question = str(item.get("question", "")).strip()
            assumption = str(item.get("assumption", "")).strip()
            if not question:
                continue
            if severity == "assume_and_proceed" and assumption:
                oq_lines.append(f"- [{severity}] {question} _(assumption: {assumption})_")
            else:
                oq_lines.append(f"- [{severity}] {question}")
        if oq_lines:
            open_questions_section = "\n### Open Questions\n" + "\n".join(oq_lines)

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
        {open_questions_section}
        """
    ).strip()
    prep_instruction = (
        "The engineering brief above is evidence gathered from the codebase. "
        "Treat it as the default working context, challenge its conclusions when the code disagrees, "
        "and only do targeted repository lookups when a concrete gap remains."
    )
    return prep_block, prep_instruction
