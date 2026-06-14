"""Deliberation example pipeline: draft → critique → human_review → revise.

A four-stage linear pipeline demonstrating the Arnold pipeline authoring
surface with a reusable human-review gate from
:mod:`arnold.pipelines.evidence_pack.steps`.

The pipeline graph::

    draft ──done──→ critique ──done──→ human_review ──emit──→ revise ──done──→ halt
                                        │
                                        └──failed──→ halt

The *draft*, *critique*, and *revise* stages use
:class:`~arnold.pipeline.steps.agent.AgentStep`.  The *human_review* stage
uses :class:`~arnold.pipelines.evidence_pack.steps.HumanReviewStep`, which
returns ``next='suspended'`` on first run (caught by
:class:`~arnold.pipelines._deliberation_example._hooks.DeliberationHooks`
before edge resolution) and ``next='emit'`` or ``next='failed'`` on resume.
"""

from __future__ import annotations

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.steps.agent import AgentStep
from arnold.pipeline.types import Edge, Pipeline, Stage
from arnold.pipelines.evidence_pack.steps import HumanReviewStep


def build_pipeline(
    name: str = "deliberation-example",
    description: str = "",
) -> Pipeline:
    """Build the deliberation example pipeline.

    Parameters
    ----------
    name:
        Pipeline name (default ``"deliberation-example"``).
    description:
        Optional override for the pipeline description.

    Returns
    -------
    Pipeline
        A fully assembled :class:`Pipeline` with four sequential stages:
        *draft*, *critique* (both :class:`AgentStep`), *human_review*
        (:class:`HumanReviewStep`), and *revise* (:class:`AgentStep`).
    """
    builder = PipelineBuilder(
        name=name,
        description=description or (
            "Deliberation example pipeline: "
            "draft → critique → human_review → revise"
        ),
    )

    # ── Stage 1: draft ────────────────────────────────────────────────
    draft_step = AgentStep(name="draft")
    draft_stage = Stage(
        name="draft",
        step=draft_step,
        edges=(Edge(label="done", target="critique"),),
    )
    builder.add_stage(draft_stage)

    # ── Stage 2: critique ─────────────────────────────────────────────
    critique_step = AgentStep(name="critique")
    critique_stage = Stage(
        name="critique",
        step=critique_step,
        edges=(Edge(label="done", target="human_review"),),
    )
    builder.add_stage(critique_stage)

    # ── Stage 3: human_review ─────────────────────────────────────────
    human_review_step = HumanReviewStep()
    human_review_stage = Stage(
        name="human_review",
        step=human_review_step,
        edges=(
            Edge(label="emit", target="revise"),
            Edge(label="failed", target="halt"),
        ),
    )
    builder.add_stage(human_review_stage)

    # ── Stage 4: revise ───────────────────────────────────────────────
    revise_step = AgentStep(name="revise")
    revise_stage = Stage(
        name="revise",
        step=revise_step,
        edges=(Edge(label="done", target="halt"),),
    )
    builder.add_stage(revise_stage)

    return builder.build()
