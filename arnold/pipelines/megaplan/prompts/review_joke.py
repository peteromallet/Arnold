"""Joke-mode review prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core import (
    intent_brief_reference,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    read_json,
)
from arnold.pipelines.megaplan.types import PlanState

from ._shared import _gate_summary_or_skipped
from .review import _settled_decisions_block, _settled_decisions_instruction

# TODO(M6a): _review_joke_prompt and _review_doc_prompt share significant
# structural similarity (data loading, flag reverify construction, pre-check
# blocks, extra_sections assembly, criteria priority rules, rework_items
# shape) but have intentional semantic differences that prevent a shared
# helper with byte-identical output: (a) artifact terminology ("Approved
# scene canvas" / "Output scene content" vs "Approved plan" / "Output
# document content"), (b) the full JSON example block (criteria names,
# evidence text, task/sense-check verdicts, summary), (c) the
# primary-criterion section present only in joke mode, (d) the
# flag-reverify instruction text ("scene" vs "document"), and (e) the
# requirements intro sentence.  The duplication is intentionally retained
# until a future milestone provides a cleaner parameterization boundary.


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    if isinstance(criterion, str) and criterion.strip():
        return criterion.strip()
    return "[missing primary criterion]"


def _review_joke_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    review_intro: str,
    criteria_guidance: str,
    task_guidance: str,
    sense_check_guidance: str,
    pre_check_flags: list[dict[str, Any]] | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    output_path = state["config"].get("output_path", "output.md")
    primary_criterion = _primary_criterion(state)
    resolved_output = Path(project_dir) / output_path
    if resolved_output.exists():
        try:
            output_content = resolved_output.read_text(encoding="utf-8")
        except OSError:
            output_content = "(could not read output file)"
    else:
        output_content = "(output file does not exist yet)"

    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    execution = read_json(plan_dir / "execution.json")
    gate = _gate_summary_or_skipped(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    settled_decisions_block = _settled_decisions_block(gate)
    settled_decisions_instruction = _settled_decisions_instruction(gate)

    flag_reverify_items: list[dict[str, str]] = []
    for flag in load_flag_registry(plan_dir).get("flags", []):
        if not isinstance(flag, dict):
            continue
        status = str(flag.get("status", "open"))
        if status not in {"open", "addressed", "verified", "disputed"}:
            continue
        flag_reverify_items.append(
            {
                "id": str(flag.get("id", "")),
                "concern": str(flag.get("concern", "")),
                "severity": str(flag.get("severity") or flag.get("severity_hint") or "uncertain"),
                "status": status,
            }
        )
    flag_reverify_block = ""
    if flag_reverify_items:
        flag_reverify_block = textwrap.dedent(
            f"""
            Critique flags to re-verify against the output scene:
            {json_dump(flag_reverify_items).strip()}

            For each flag above, verify whether the final scene actually resolves the concern while preserving the primary criterion.
            Add resolved flag IDs to `verified_flag_ids`.
            For any unresolved flag, add a `rework_items` entry with `task_id: "REVIEW"`, `issue`, `expected`, `actual`, `evidence_file`, `flag_id`, and `source: "review_flag_reverify"`.
            """
        ).strip()
    pre_check_block = ""
    if pre_check_flags:
        pre_check_block = textwrap.dedent(
            f"""
            Advisory mechanical pre-check flags:
            {json_dump(pre_check_flags).strip()}

            Copy this list verbatim into the output `pre_check_flags` field.
            """
        ).strip()
    extra_sections = ""
    if flag_reverify_block:
        extra_sections += f"\n\n{flag_reverify_block}"
    if pre_check_block:
        extra_sections += f"\n\n{pre_check_block}"

    return textwrap.dedent(
        f"""
        {review_intro}

        Project directory:
        {project_dir}

        Output file path:
        {output_path}

        Primary criterion:
        {primary_criterion}

        {intent_brief_reference(state)}

        Approved scene canvas:
        {latest_plan}

        Execution tracking state (`finalize.json`):
        {json_dump(finalize_data).strip()}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {settled_decisions_block}{extra_sections}

        Execution summary:
        {json_dump(execution).strip()}

        Output scene content:
        {output_content}

        Requirements:
        - Read the output file above and judge it first against the declared primary criterion, then against the remaining success criteria and the approved scene canvas.
        - {criteria_guidance}
        - Trust executor evidence by default. Dig deeper only where the scene text or vague notes make a claim ambiguous.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion (any priority) cannot be verified in this context, mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or the scene prose is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
        {settled_decisions_instruction}
        - {task_guidance}
        - {sense_check_guidance}
        - Follow this JSON shape exactly:
        ```json
        {{
          "review_verdict": "approved",
          "criteria": [
            {{
              "name": "Scene serves the declared primary criterion",
              "priority": "must",
              "pass": "pass",
              "evidence": "The final scene preserves the intended comic engine from opening through button."
            }}
          ],
          "issues": [],
          "rework_items": [],
          "summary": "Approved. The scene meets the brief and the primary criterion.",
          "task_verdicts": [
            {{
              "task_id": "T1",
              "reviewer_verdict": "Pass. The written scene beats align with the planned canvas and primary criterion.",
              "evidence_files": []
            }}
          ],
          "sense_check_verdicts": [
            {{
              "sense_check_id": "SC1",
              "verdict": "Confirmed. The final scene still serves the declared primary criterion."
            }}
          ]
        }}
        ```
        - `rework_items` must be an array of structured rework directives. When `review_verdict` is `needs_rework`, populate one entry per issue.
        - `issues` must still be populated as a flat one-line-per-item summary derived from `rework_items`.
        - When approved, both `issues` and `rework_items` should be empty arrays.
        """
    ).strip()


__all__ = ["_review_joke_prompt"]
