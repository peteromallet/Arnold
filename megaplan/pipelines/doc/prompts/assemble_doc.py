"""Doc-pipeline ``assembly`` prompt builder.

Terminal stage: stitch the revised per-section drafts into the final
document at the configured output path. The Step's ``run()`` returns
``next='halt'`` directly (executor.py:218-220) — no halt edge.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from megaplan._core import intent_and_notes_block
from megaplan.types import PlanState


def _assemble_doc_prompt(
    state: PlanState, plan_dir: Path, root: Path | None = None
) -> str:
    del root
    project_dir = Path(state["config"]["project_dir"])
    output_path = state["config"].get("output_path", "output.md")
    return textwrap.dedent(
        f"""
        Assemble the final document.

        Project directory:
        {project_dir}

        Output path (write the full document here):
        {output_path}

        {intent_and_notes_block(state)}

        Requirements:
        - Concatenate the revised per-section drafts in outline order.
        - Preserve section headings as they appear in the per-section
          files. Add a top-level title if the outline calls for one.
        - Do not introduce new content — assembly is mechanical.
        - The output path is AUTHORITATIVE; ignore any alternate
          filename suggested by the plan or per-section files.
        """
    ).strip()


def build_assemble_doc_prompt(state: PlanState, plan_dir: Path) -> str:
    return _assemble_doc_prompt(state, plan_dir)


__all__ = ["_assemble_doc_prompt", "build_assemble_doc_prompt"]
