"""Doc-pipeline ``critique`` prompt builder.

Single-pass critique over the assembled per-section drafts. No
iterate/proceed/tiebreaker/escalate verdicts — the doc pipeline drops
the legacy gate loop (0.23.0 CHANGELOG notes the topology change).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import intent_and_notes_block
from megaplan.types import PlanState


def _critique_doc_prompt(
    state: PlanState, plan_dir: Path, root: Path | None = None
) -> str:
    del root
    project_dir = Path(state["config"]["project_dir"])
    drafts_dir = plan_dir / "section_drafts"
    return textwrap.dedent(
        f"""
        Critique the per-section drafts under:
        {drafts_dir}

        Project directory:
        {project_dir}

        {intent_and_notes_block(state)}

        Requirements:
        - Read each section draft and flag concrete problems:
          buried ledes, vague verbs, audience mismatch, missing
          structure, factual gaps.
        - Be specific — quote the offending sentence and name the
          fix shape.
        - Output JSON: {{"flags": [{{"section_id": str, "issue": str,
          "fix_shape": str}}, ...]}}.
        - Do NOT emit iterate/proceed/tiebreaker verdicts — this
          pipeline is linear single-pass; the revise stage consumes
          your flags directly.
        """
    ).strip()


def build_critique_doc_prompt(state: PlanState, plan_dir: Path) -> str:
    return _critique_doc_prompt(state, plan_dir)


__all__ = ["_critique_doc_prompt", "build_critique_doc_prompt"]
