"""Doc-pipeline ``outline`` prompt builder.

Renders the prompt for the first stage of the new ``doc`` pipeline:
turn the user's brief into a list of section specs (each a JSON
object with at least ``section_id`` and ``section_title``). The
downstream ``section_drafts`` stage's :func:`dynamic_fanout`
SubloopStep consumes that list and fans out per-section drafts.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import intent_and_notes_block
from megaplan.types import PlanState


def _outline_doc_prompt(
    state: PlanState, plan_dir: Path, root: Path | None = None
) -> str:
    del root
    project_dir = Path(state["config"]["project_dir"])
    sections_path = plan_dir / "outline" / "sections.json"
    return textwrap.dedent(
        f"""
        Plan the document outline.

        Project directory:
        {project_dir}

        {intent_and_notes_block(state)}

        Emit the section list as JSON at:
        {sections_path}

        Each section must be a JSON object with at least:
          - "section_id": a short kebab-case identifier (e.g. "introduction")
          - "section_title": a human-readable title

        Optional fields:
          - "summary": one-sentence purpose of the section
          - "depends_on": list of section_ids this section assumes

        Output the JSON array exactly as written to disk.
        """
    ).strip()


def build_outline_doc_prompt(state: PlanState, plan_dir: Path) -> str:
    """Public builder name matching the T5 ``build_*_prompt`` convention."""
    return _outline_doc_prompt(state, plan_dir)


__all__ = ["_outline_doc_prompt", "build_outline_doc_prompt"]
