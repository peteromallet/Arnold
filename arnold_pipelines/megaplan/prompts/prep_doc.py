"""Doc-mode prep prompt builder."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Mapping

from arnold_pipelines.megaplan.types import PlanState


def _prep_doc_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    contract_context: Mapping[str, Any] | None = None,
) -> str:
    del contract_context
    del root
    project_dir = Path(state["config"]["project_dir"])
    output_path = plan_dir / "prep.json"
    return textwrap.dedent(
        f"""
        Prepare a concise engineering brief for the document authoring task below. This brief will be the primary context for all subsequent planning and execution.

        Task:
        {state["idea"]}

        Project: {project_dir}
        Output file: {output_path}

        First, assess: does this task need investigation?

        Set "skip": true if ALL of these are true:
        - The document's scope and audience are clearly specified
        - No research or prior-art review is needed
        - The sections and structure are obvious from the task description

        Set "skip": false if ANY of these are true:
        - The task references prior art, existing docs, or related work to review
        - Multiple structural approaches seem possible
        - The task involves concepts, terminology, or domain knowledge you'd need to look up
        - The task references repository code that informs the document's content

        If skipping, leave everything else empty. The original task description will be used directly.
        If not skipping, fill in the brief:
        1. Identify what sources, prior art, and related documents should inform this document.
        2. If the project directory contains relevant code, docs, or config that the document should reference, search for them.
        3. Extract evidence from the task description — audience, purpose, constraints, deliverable format.
        4. Check whether similar documents already exist in the project that could serve as templates or that this document should reference.
        5. If the task describes a problem or decision to document, trace the full context — what alternatives exist, what constraints apply, who the stakeholders are.
        6. Identify the key questions the document must answer for its audience.

        Brief fields:
        - skip: true if no investigation needed, false if brief has useful content.
        - task_summary: What the document should accomplish, in 2-3 sentences.
        - key_evidence: Facts from the task description and project that inform the document's content.
        - relevant_code: File paths and key structures in the project that the document should reference or describe. Use this to capture source material, not code to change.
        - test_expectations: For doc mode, use this to list key claims or sections that reviewers should verify. Each entry's test_id is a section name, status is "expected", and what_it_checks describes what the section must cover.
        - constraints: Audience, tone, length limits, format requirements, or content that must be included.
        - suggested_approach: A concrete document outline or structural approach grounded in what you found.

        """
    ).strip()
