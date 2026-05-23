"""Compile the canonical planning :class:`Pipeline`.

The planning pipeline is keyed by phase name:
``prep / plan / critique / gate / revise / finalize / execute / review /
tiebreaker``. Gate recommendations are represented as typed
``kind="gate"`` edges on the ``gate`` stage. User-facing override
command labels remain as normal fallback edges because the live gate
handler still emits and reports those commands.
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


def compile_planning_pipeline() -> Pipeline:
    """Return the canonical, runnable planning :class:`Pipeline`.

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

    from megaplan._pipeline.stages.prep import PrepStep
    from megaplan._pipeline.stages.plan import PlanStep
    from megaplan._pipeline.stages.critique import CritiqueStep
    from megaplan._pipeline.stages.gate import GateStep
    from megaplan._pipeline.stages.revise import ReviseStep
    from megaplan._pipeline.stages.finalize import FinalizeStep
    from megaplan._pipeline.stages.execute import ExecuteStep
    from megaplan._pipeline.stages.review import ReviewStep
    from megaplan._pipeline.stages.tiebreaker import TiebreakerStep

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
        # Verdict with a typed recommendation. The three kind='gate' edges
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
