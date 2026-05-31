"""Python composition of the first-class ``planning`` pipeline.

The planning pipeline is the built-in megaplan plan-production substrate:

    prep → plan → critique ↔ gate ↔ revise (loop) → finalize
                                ↓ tiebreaker (on tie)
                                ↓ execute (optional, on proceed)
                                ↓ review  (optional, after execute)

Gate verdicts route the loop:

* ``proceed``    — gate approved; continue to finalize (or execute).
* ``iterate``    — gate rejected; re-enter critique → revise loop.
* ``tiebreaker`` — evaluators split; hand off to tiebreaker stage.
* ``escalate``   — escalate to a higher-complexity model tier.

Robustness levels control the depth of the critique/gate loop:

* ``bare``     — single-pass, no gate loop.
* ``light``    — one critique+revise round, minimal gate.
* ``full``     — standard gate loop (default).
* ``thorough`` — extended gate loop with stricter criteria.
* ``extreme``  — maximum depth, all evaluators enabled.

Driver substrate: ``subprocess_isolated`` for execute/review stages;
``graph+loop-node`` for the critique→gate→revise subloop.

This package is the canonical ``planning`` built-in — it is registered
programmatically via ``_planning_builder`` in ``registry.py`` (not
discovered). ``build_pipeline()`` owns the full stage wiring;
``megaplan._pipeline.planning`` is a thin shim that re-exports
``compile_planning_pipeline`` for backwards compatibility.
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


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

description: str = (
    "Built-in planning pipeline: prep → plan → critique/gate/revise loop "
    "→ finalize → execute → review. Gate verdicts: proceed / iterate / "
    "tiebreaker / escalate. Robustness levels: bare / light / full / "
    "thorough / extreme."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("plan",)
driver: tuple[str, str] = ("subprocess_isolated", "graph+loop-node")
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("plan",)


# ── Pipeline assembly ──────────────────────────────────────────────────


def build_pipeline(**kwargs) -> Pipeline:  # type: ignore[no-untyped-def]
    """Return the canonical planning :class:`Pipeline`.

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


# Backwards-compatible alias: callers importing compile_planning_pipeline
# from this package get the canonical implementation directly.
compile_planning_pipeline = build_pipeline


__all__ = [
    "build_pipeline",
    "compile_planning_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "arnold_api_version",
    "capabilities",
]
