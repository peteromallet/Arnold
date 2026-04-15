"""Tiebreaker challenger prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from megaplan._core import json_dump
from megaplan.types import PlanState

from ._shared import _render_prep_block


def challenger_prompt(
    question: str,
    researcher_output: dict[str, Any],
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path | None = None,
) -> str:
    project_dir = Path(state["config"]["project_dir"])
    prep_block, prep_instruction = _render_prep_block(plan_dir)

    return textwrap.dedent(f"""\
You are a senior engineer stress-testing a colleague's architectural research.
Your mandate is **stress-test, not restate**. Do not summarize or agree with
the researcher's findings — challenge them. Look for what they missed, what
they assumed without evidence, and where their reasoning breaks under pressure.

Project directory:
{project_dir}

{prep_block}
{prep_instruction}

## Decision Question

{question}

## Researcher's Output (JSON)

```json
{json_dump(researcher_output).strip()}
```

## Your task

1. **Measurements vs assumptions.** Which of the researcher's claims are backed
   by actual measurements or code evidence, and which are assumptions dressed as
   facts? Call out the gap.

2. **Missing options.** Are there viable options the researcher did not consider?
   For each, describe it and explain why it was likely missed.

3. **Hard cases.** Identify specific scenarios where each proposed option would
   break or perform poorly. State the scenario, which option breaks, and the
   severity.

4. **Reframings.** Is the question itself framed correctly? Suggest alternative
   framings that might dissolve the dilemma.

5. **Aging analysis.** How will each option age over 6-12 months? Which will
   create the most technical debt or lock-in?

6. **Counter-recommendation.** State your own pick (may agree or disagree with
   the researcher), with rationale.

## Output format

Respond with a JSON object matching the tiebreaker_challenger schema.
""")
