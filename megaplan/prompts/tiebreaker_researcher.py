"""Tiebreaker researcher prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from megaplan._core import (
    intent_brief_reference,
    json_dump,
    latest_plan_path,
    read_json,
)
from megaplan.types import PlanState


def researcher_prompt(
    question: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    plan_text = ""
    try:
        plan_path = latest_plan_path(plan_dir, state)
        plan_text = plan_path.read_text(encoding="utf-8")
    except Exception:
        pass

    critique_block = ""
    critique_path = plan_dir / "critique.json"
    if critique_path.exists():
        critique_data = read_json(critique_path)
        critique_block = f"\nCritique history:\n{json_dump(critique_data).strip()}\n"

    return textwrap.dedent(f"""\
You are a senior engineer researching an architectural/design decision.
Your mandate is **evidence over opinion**. Every claim you make must cite
specific file paths, measurements, or documented patterns from the codebase.
Do not speculate — if you cannot find evidence, say so explicitly.

Project directory:
{project_dir}

{intent_brief_reference(state)}

Current plan (if any):
{plan_text or "(no plan yet)"}
{critique_block}
## Decision Question

{question}

## Your task

1. **Gather evidence.** Search the codebase for code, patterns, measurements,
   and documentation relevant to the question. For each piece of evidence,
   record the claim, evidence type (code/measurement/pattern/doc), the file
   paths where you found it, and a representative quote.

2. **Enumerate options.** List every viable option you can identify. For each,
   describe it, state its assumptions, and list its costs.

3. **Make a preliminary pick.** Choose the option you believe is strongest,
   explain your rationale, and state what you are least sure about.

## Output format

Respond with a JSON object matching the tiebreaker_researcher schema.
Always cite file paths relative to the project root.
""")
