"""Canonical Megaplan planning :class:`Pipeline` assembly.

This module is the **single source of truth** for the Megaplan planning
pipeline graph.  It imports stage implementations from the plugin-local
``arnold_pipelines.megaplan.stages`` package and uses routing helpers
from ``arnold_pipelines.megaplan.routing`` so every dependency stays
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

import dataclasses

from arnold_pipelines.megaplan.pipeline_contracts import (
    LOGICAL_CRITIQUE_PAYLOAD,
    LOGICAL_EXECUTE_PAYLOAD,
    LOGICAL_FINALIZE_PAYLOAD,
    LOGICAL_GATE_PAYLOAD,
    LOGICAL_PLAN_PAYLOAD,
    LOGICAL_PREP_PAYLOAD,
    LOGICAL_REVISE_PAYLOAD,
    LOGICAL_REVIEW_PAYLOAD,
    LOGICAL_TIEBREAKER_PAYLOAD,
    production_planning_contracts,
)
from arnold_pipelines.megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from arnold_pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
)

# ── Local stage imports ──────────────────────────────────────────────────
from arnold_pipelines.megaplan.stages.prep import PrepStep
from arnold_pipelines.megaplan.stages.plan import PlanStep
from arnold_pipelines.megaplan.stages.critique import CritiqueStep
from arnold_pipelines.megaplan.stages.gate import GateStep
from arnold_pipelines.megaplan.stages.revise import ReviseStep
from arnold_pipelines.megaplan.stages.finalize import FinalizeStep
from arnold_pipelines.megaplan.stages.execute import ExecuteStep
from arnold_pipelines.megaplan.stages.review import ReviewStep
from arnold_pipelines.megaplan.stages.tiebreaker import TiebreakerStep
from arnold_pipelines.megaplan.routing import (
    PLANNING_DECISIONS,
    PLAN_ESCALATE,
    PLAN_ITERATE,
    PLAN_PROCEED,
    tiebreaker_edges,
)


def _planning_loop_should_halt(loop_state: object) -> bool:
    """Return whether an explicitly capped planning loop should stop."""

    state = getattr(loop_state, "state", {}) or {}
    config = state.get("config", {}) if isinstance(state, dict) else {}
    raw_limit = None
    if isinstance(state, dict):
        raw_limit = state.get("max_gate_iterations") or state.get("max_iterations")
    if raw_limit is None and isinstance(config, dict):
        raw_limit = config.get("max_gate_iterations") or config.get("max_iterations")
    if raw_limit in (None, ""):
        return False
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return False
    if limit <= 0:
        return False
    return int(getattr(loop_state, "iteration", 0) or 0) >= limit


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

    contracts = production_planning_contracts()
    prep_contract = contracts[LOGICAL_PREP_PAYLOAD]
    plan_contract = contracts[LOGICAL_PLAN_PAYLOAD]
    critique_contract = contracts[LOGICAL_CRITIQUE_PAYLOAD]
    gate_contract = contracts[LOGICAL_GATE_PAYLOAD]
    revise_contract = contracts[LOGICAL_REVISE_PAYLOAD]
    finalize_contract = contracts[LOGICAL_FINALIZE_PAYLOAD]
    execute_contract = contracts[LOGICAL_EXECUTE_PAYLOAD]
    review_contract = contracts[LOGICAL_REVIEW_PAYLOAD]
    tiebreaker_contract = contracts[LOGICAL_TIEBREAKER_PAYLOAD]

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
    prep_stage = dataclasses.replace(
        prep_stage,
        produces=(prep_contract.producer_port("prep_payload"),),
    )
    cycle["critique"] = dataclasses.replace(
        cycle["critique"],
        consumes=(
            plan_contract.consumer_port("plan_payload"),
            revise_contract.consumer_port("revise_payload"),
            tiebreaker_contract.consumer_port("tiebreaker_payload"),
        ),
        produces=(critique_contract.producer_port("critique_payload"),),
    )
    cycle["gate"] = dataclasses.replace(
        cycle["gate"],
        consumes=(critique_contract.consumer_port("critique_payload"),),
        produces=(gate_contract.producer_port("gate_payload"),),
    )
    cycle["revise"] = dataclasses.replace(
        cycle["revise"],
        consumes=(gate_contract.consumer_port("gate_payload"),),
        produces=(revise_contract.producer_port("revise_payload"),),
    )

    stages: dict[str, Stage] = {
        "prep": prep_stage,
        "plan": Stage(
            name="plan",
            step=PlanStep(),
            edges=(Edge(label="critique", target="critique"),),
            consumes=(prep_contract.consumer_port("prep_payload"),),
            produces=(plan_contract.producer_port("plan_payload"),),
        ),
        "critique": cycle["critique"],
        "gate": cycle["gate"],
        "revise": cycle["revise"],
        "finalize": Stage(
            name="finalize",
            step=FinalizeStep(),
            edges=(Edge(label="execute", target="execute"),),
            consumes=(gate_contract.consumer_port("gate_payload"),),
            produces=(finalize_contract.producer_port("finalize_payload"),),
        ),
        "execute": Stage(
            name="execute",
            step=ExecuteStep(),
            edges=(Edge(label="review", target="review"),),
            consumes=(finalize_contract.consumer_port("finalize_payload"),),
            produces=(execute_contract.producer_port("execute_payload"),),
        ),
        "review": Stage(
            name="review",
            step=ReviewStep(),
            edges=(Edge(label="review", target="halt"),
                   Edge(label="halt", target="halt")),
            consumes=(execute_contract.consumer_port("execute_payload"),),
            produces=(review_contract.producer_port("review_payload"),),
        ),
        # T11 LOAD-BEARING: TiebreakerStep is a SubloopStep that emits a
        # PipelineVerdict with a typed recommendation. The three decision edges
        # preserve the legacy "escalate folds into finalize" semantics via
        # escalate→finalize.
        "tiebreaker": Stage(
            name="tiebreaker",
            step=TiebreakerStep(),
            edges=tiebreaker_edges(
                on_iterate="critique",
                on_proceed="finalize",
                on_escalate="finalize",
            ),
            consumes=(gate_contract.consumer_port("gate_payload"),),
            produces=(tiebreaker_contract.producer_port("tiebreaker_payload"),),
            decision_vocabulary=frozenset(
                {PLAN_ITERATE, PLAN_PROCEED, PLAN_ESCALATE}
            ),
        ),
    }
    stages["gate"] = dataclasses.replace(
        stages["gate"],
        decision_vocabulary=frozenset(PLANNING_DECISIONS),
        loop_condition=_planning_loop_should_halt,
    )
    return Pipeline(
        stages=stages,
        entry="prep",
        resource_bundles=(
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "finalize",
            "execute",
            "review",
            "tiebreaker",
        ),
    )


# Backwards-compatible alias so callers importing ``compile_planning_pipeline``
# from this package get the canonical implementation directly.
compile_planning_pipeline = build_pipeline
