"""Doc-pipeline ``revise`` prompt builder.

Consumes the critique flags from the prior stage and rewrites each
flagged section. Single-pass — no gate-loop iteration.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from arnold_pipelines.megaplan._core import intent_and_notes_block
from arnold_pipelines.megaplan.types import PlanState


def _revise_doc_prompt(
    state: PlanState, plan_dir: Path, root: Path | None = None
) -> str:
    del root
    project_dir = Path(state["config"]["project_dir"])
    drafts_dir = plan_dir / "section_drafts"
    revise_dir = plan_dir / "revise"
    return textwrap.dedent(
        f"""
        Revise the per-section drafts in light of the critique.

        Project directory:
        {project_dir}

        {intent_and_notes_block(state)}

        Input drafts:
        {drafts_dir}

        Output revisions to:
        {revise_dir}

        Requirements:
        - For each flag in the critique JSON, rewrite the offending
          passage in the named section. Preserve voice and structure
          elsewhere.
        - Do NOT introduce new sections — the outline is locked.
        - Emit one revised file per touched section, named
          ``<section_id>.md``.
        """
    ).strip()


def build_revise_doc_prompt(state: PlanState, plan_dir: Path) -> str:
    return _revise_doc_prompt(state, plan_dir)


__all__ = ["_revise_doc_prompt", "build_revise_doc_prompt"]
