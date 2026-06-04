"""Canonical Megaplan planning :class:`Pipeline` assembly.

This module is the **single source of truth** for the Megaplan planning
pipeline graph.  It imports stage implementations from the plugin-local
``arnold.pipelines.megaplan.stages`` package and uses routing helpers
from ``arnold.pipelines.megaplan.routing`` so every dependency stays
inside the Arnold plugin boundary.

Stage layout::

    prep → plan → critique → gate
                              ├─ proceed → finalize → execute → review → halt
                              ├─ iterate → revise → critique  (loop)
                              ├─ tiebreaker → tiebreaker → critique
                              └─ escalate → (override edges)

No feedback stage — exactly 9 stages:
``prep / plan / critique / gate / revise / finalize / execute / review /
tiebreaker``.
"""

from __future__ import annotations

from megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
)

# ── Local stage imports ──────────────────────────────────────────────────
from arnold.pipelines.megaplan.stages.prep import PrepStep
from arnold.pipelines.megaplan.stages.plan import PlanStep
from arnold.pipelines.megaplan.stages.critique import CritiqueStep
from arnold.pipelines.megaplan.stages.gate import GateStep
from arnold.pipelines.megaplan.stages.revise import ReviseStep
from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
from arnold.pipelines.megaplan.stages.execute import ExecuteStep
from arnold.pipelines.megaplan.stages.review import ReviewStep
from arnold.pipelines.megaplan.stages.tiebreaker import TiebreakerStep


def build_pipeline() -> Pipeline:
    """Return the canonical Megaplan planning :class:`Pipeline`.

    Sprint 5 Chunk A: this is the only canonical compile target. Stage
    keys are phase names (``prep / plan / critique / gate / revise /
    finalize / execute / review / tiebreaker``); the gate Step's
    recommendation edges sit directly on the ``gate`` stage so the
    executor's typed-verdict dispatch resolves cleanly.

    Stage layout::

        prep → plan → critique → gate
                                  ├─ proceed → finalize → execute → review → halt
                                  ├─ iterate → revise → critique  (loop)
                                  ├─ tiebreaker → tiebreaker → critique
                                  └─ escalate → (override edges)
    """

    # Phase 0: prep gate via patterns.phase_zero_gate.
    prep_stage = phase_zero_gate(
        PrepStep(),
        name="prep",
        on_pass="plan",
        on_fail="halt",
    )

    # critique → gate → revise cycle assembled via the pattern library.
    # gate_extra_edges carry the non-recommendation fallback/override
    # labels that the live gate handler reports; critique_fallback_edges
    # carry the label-fallback edges the existing CritiqueStep emits.
    cycle = critique_revise_gate_loop(
        CritiqueStep(),
        GateStep(),
        ReviseStep(),
        on_proceed="finalize",
        on_iterate="revise",
        on_tiebreaker="tiebreaker",
        on_escalate="finalize",
        critique_fallback_edges=(
            Edge(label="gate_unset:gate", target="gate"),
            Edge(label="gate", target="gate"),
        ),
        gate_extra_edges=(
            Edge(label="revise", target="revise"),
            Edge(label="gate", target="finalize"),
            Edge(label="override force-proceed", target="finalize"),
            Edge(label="override abort", target="halt"),
        ),
        revise_target="critique",
    )

    stages: dict[str, Stage] = {
        "prep": prep_stage,
        "plan": Stage(
            name="plan", step=PlanStep(),
            edges=(Edge(label="critique", target="critique"),),
        ),
        "critique": cycle["critique"],
        "gate": cycle["gate"],
        "revise": cycle["revise"],
        "finalize": Stage(
            name="finalize", step=FinalizeStep(),
            edges=(Edge(label="execute", target="execute"),),
        ),
        "execute": Stage(
            name="execute", step=ExecuteStep(),
            edges=(Edge(label="review", target="review"),),
        ),
        "review": Stage(
            name="review", step=ReviewStep(),
            edges=(Edge(label="review", target="halt"),
                   Edge(label="halt", target="halt")),
        ),
        # T11 LOAD-BEARING: TiebreakerStep is a SubloopStep that emits a
        # PipelineVerdict with a typed recommendation. The three kind='gate' edges
        # below replace the legacy label-only edges; the legacy 'escalate
        # folds into the finalize branch' semantics are preserved via
        # escalate→finalize (anti-scope: no new pipeline branches this
        # sprint).
        "tiebreaker": Stage(
            name="tiebreaker", step=TiebreakerStep(),
            edges=(
                Edge(label="", target="critique", kind="gate", recommendation="iterate"),
                Edge(label="", target="finalize", kind="gate", recommendation="proceed"),
                Edge(label="", target="finalize", kind="gate", recommendation="escalate"),
            ),
        ),
    }
    return Pipeline(stages=stages, entry="prep")


# Backwards-compatible alias so callers importing ``compile_planning_pipeline``
# from this package get the canonical implementation directly.
compile_planning_pipeline = build_pipeline
