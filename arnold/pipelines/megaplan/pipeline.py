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

import dataclasses

from arnold.pipelines.megaplan.pipeline_contracts import (
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
from arnold.pipelines.megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from arnold.pipelines.megaplan._pipeline.types import (
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
from arnold.pipelines.megaplan.routing import (
    PLANNING_DECISIONS,
    PLAN_ESCALATE,
    PLAN_ITERATE,
    PLAN_PROCEED,
    tiebreaker_edges,
)

# ── Native pipeline decorators ────────────────────────────────────────────
from arnold.pipeline.native.decorators import decision, phase, pipeline
from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipeline.native.graph_projection import project_graph
from arnold.pipeline.topology import compute_topology_hash


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


def _build_legacy_graph_pipeline() -> Pipeline:
    """Return the hand-built Megaplan planning :class:`Pipeline`.

    This is the legacy hand-built implementation that serves as the
    fallback when the native-derived pipeline's topology hash does not
    match the Step 3 baseline.  It is identical to the pre-M4
    ``build_pipeline()`` and is preserved as a stable reference.

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


# ── Canonical M4 native pipeline declaration ───────────────────────────────
# The @pipeline("megaplan") generator function is the canonical source of
# truth for the Megaplan control flow.  It is compiled via compile_pipeline()
# and projected via project_graph(key_mode="phase") to derive the Pipeline
# graph.  When the derived topology hash matches the Step 3 baseline,
# build_pipeline() returns the native-derived Pipeline; otherwise it falls
# back to _build_legacy_graph_pipeline().

# Step 3 baseline topology hash — the gold standard for graph parity.
_EXPECTED_TOPOLOGY_HASH = (
    "sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30"
)

_LEGACY_STAGE_ORDER: tuple[str, ...] = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "finalize",
    "execute",
    "review",
    "tiebreaker",
)


@pipeline("megaplan")
def megaplan(ctx: dict):
    """Megaplan planning pipeline — canonical native declaration.

    Encodes the Megaplan control flow using the M4 compiler grammar::

        prep → plan → critique → gate
        while gate == 'iterate': revise → critique → gate
        if gate == 'tiebreaker': tiebreaker
        finalize → execute → review
    """
    yield _native_prep(ctx)
    yield _native_plan(ctx)
    yield _native_critique(ctx)
    yield _native_gate(ctx)
    while _native_gate_decision(ctx) == 'iterate':
        yield _native_revise(ctx)
        yield _native_critique(ctx)
        yield _native_gate(ctx)
    if _native_gate_decision(ctx) == 'override abort':
        return
    if _native_gate_decision(ctx) == 'tiebreaker':
        yield _native_tiebreaker(ctx)
        if _native_tiebreaker_decision(ctx) == 'iterate':
            yield _native_critique(ctx)
            yield _native_gate(ctx)
            while _native_gate_decision(ctx) == 'iterate':
                yield _native_revise(ctx)
                yield _native_critique(ctx)
                yield _native_gate(ctx)
            if _native_gate_decision(ctx) == 'override abort':
                return
            if _native_gate_decision(ctx) == 'tiebreaker':
                yield _native_tiebreaker(ctx)
    yield _native_finalize(ctx)
    yield _native_execute(ctx)
    yield _native_review(ctx)


def build_pipeline() -> Pipeline:
    """Return the canonical Megaplan planning :class:`Pipeline`.

    Compiles the native ``@pipeline("megaplan")`` declaration via
    :func:`compile_pipeline`, projects it through phase-keyed
    :func:`project_graph`, and checks the topology hash against the
    Step 3 baseline.  If the native-derived hash matches, the native
    Pipeline is returned; otherwise the hand-built
    :func:`_build_legacy_graph_pipeline` is used as a stable fallback.

    Stage layout::

        prep → plan → critique → gate
                                  ├─ proceed → finalize → execute → review → halt
                                  ├─ iterate → revise → critique  (loop)
                                  ├─ tiebreaker → tiebreaker → critique
                                  └─ escalate → (override edges)
    """
    program = compile_pipeline(megaplan)
    native_pipeline = project_graph(program, key_mode="phase")
    ordered_stages = {
        name: native_pipeline.stages[name]
        for name in _LEGACY_STAGE_ORDER
        if name in native_pipeline.stages
    }
    native_pipeline = dataclasses.replace(
        native_pipeline,
        stages=ordered_stages,
        resource_bundles=_LEGACY_STAGE_ORDER,
    )
    native_hash = compute_topology_hash(native_pipeline)
    if native_hash != _EXPECTED_TOPOLOGY_HASH:
        raise RuntimeError(
            "Megaplan native topology hash mismatch: "
            f"expected {_EXPECTED_TOPOLOGY_HASH}, got {native_hash}"
        )
    return native_pipeline



# ── Port metadata for native phase declarations ─────────────────────────
# These are computed once at import time from production_planning_contracts()
# so every native @phase wrapper carries the same typed ports as the
# corresponding Stage in build_pipeline().

_NATIVE_CONTRACTS = production_planning_contracts()
_NATIVE_PREP_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_PREP_PAYLOAD]
_NATIVE_PLAN_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_PLAN_PAYLOAD]
_NATIVE_CRITIQUE_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_CRITIQUE_PAYLOAD]
_NATIVE_GATE_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_GATE_PAYLOAD]
_NATIVE_REVISE_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_REVISE_PAYLOAD]
_NATIVE_FINALIZE_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_FINALIZE_PAYLOAD]
_NATIVE_EXECUTE_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_EXECUTE_PAYLOAD]
_NATIVE_REVIEW_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_REVIEW_PAYLOAD]
_NATIVE_TIEBREAKER_CONTRACT = _NATIVE_CONTRACTS[LOGICAL_TIEBREAKER_PAYLOAD]

# ── Per-phase port tuples (canonical — must match build_pipeline()) ─────
_PREP_PRODUCES: tuple = (_NATIVE_PREP_CONTRACT.producer_port("prep_payload"),)
_PREP_CONSUMES: tuple = ()

_PLAN_PRODUCES: tuple = (_NATIVE_PLAN_CONTRACT.producer_port("plan_payload"),)
_PLAN_CONSUMES: tuple = (_NATIVE_PREP_CONTRACT.consumer_port("prep_payload"),)

_CRITIQUE_PRODUCES: tuple = (_NATIVE_CRITIQUE_CONTRACT.producer_port("critique_payload"),)
_CRITIQUE_CONSUMES: tuple = (
    _NATIVE_PLAN_CONTRACT.consumer_port("plan_payload"),
    _NATIVE_REVISE_CONTRACT.consumer_port("revise_payload"),
    _NATIVE_TIEBREAKER_CONTRACT.consumer_port("tiebreaker_payload"),
)

_GATE_PRODUCES: tuple = (_NATIVE_GATE_CONTRACT.producer_port("gate_payload"),)
_GATE_CONSUMES: tuple = (_NATIVE_CRITIQUE_CONTRACT.consumer_port("critique_payload"),)

_REVISE_PRODUCES: tuple = (_NATIVE_REVISE_CONTRACT.producer_port("revise_payload"),)
_REVISE_CONSUMES: tuple = (_NATIVE_GATE_CONTRACT.consumer_port("gate_payload"),)

_FINALIZE_PRODUCES: tuple = (_NATIVE_FINALIZE_CONTRACT.producer_port("finalize_payload"),)
_FINALIZE_CONSUMES: tuple = (_NATIVE_GATE_CONTRACT.consumer_port("gate_payload"),)

_EXECUTE_PRODUCES: tuple = (_NATIVE_EXECUTE_CONTRACT.producer_port("execute_payload"),)
_EXECUTE_CONSUMES: tuple = (_NATIVE_FINALIZE_CONTRACT.consumer_port("finalize_payload"),)

_REVIEW_PRODUCES: tuple = (_NATIVE_REVIEW_CONTRACT.producer_port("review_payload"),)
_REVIEW_CONSUMES: tuple = (_NATIVE_EXECUTE_CONTRACT.consumer_port("execute_payload"),)

_TIEBREAKER_PRODUCES: tuple = (_NATIVE_TIEBREAKER_CONTRACT.producer_port("tiebreaker_payload"),)
_TIEBREAKER_CONSUMES: tuple = (_NATIVE_GATE_CONTRACT.consumer_port("gate_payload"),)

# ── Decision vocabularies ────────────────────────────────────────────────
_GATE_DECISION_VOCABULARY: frozenset[str] = frozenset(PLANNING_DECISIONS)
_GATE_RUNTIME_DECISION_VOCABULARY: frozenset[str] = frozenset(
    set(_GATE_DECISION_VOCABULARY) | {"override abort", "override force-proceed"}
)
_TIEBREAKER_DECISION_VOCABULARY: frozenset[str] = frozenset(
    {PLAN_ITERATE, PLAN_PROCEED, PLAN_ESCALATE}
)

# ── Native Megaplan phase wrappers ──────────────────────────────────────
# These wrapper functions accept a dict context (as passed by the native
# runtime via run_native_pipeline) and delegate to the existing step
# classes through a single dict-context → StepContext adapter.  They are
# the building blocks for a native @pipeline declaration of the Megaplan
# planning pipeline and leave build_pipeline() behaviour unchanged.
#
# Each wrapper:
#   1. Receives a lightweight dict with ``state``, ``inputs``,
#      ``artifact_root``, and optionally ``contract_results``.
#   2. Converts it to a megaplan StepContext via :func:`_dict_to_step_context`.
#   3. Delegates to the corresponding step class (PrepStep, PlanStep, …).
#   4. Returns the StepResult, which the native runtime normalises via
#      _normalize_phase_result (extracting outputs, contract_result, and
#      envelope).


def _dict_to_step_context(ctx: dict) -> "StepContext":
    """Convert a native runtime dict context to a megaplan StepContext.

    The native runtime passes a lightweight dict with ``state``,
    ``inputs``, ``artifact_root``, and optionally ``contract_results``.
    This adapter constructs the richer megaplan StepContext that the
    existing step classes (PrepStep, PlanStep, etc.) expect.

    Args:
        ctx: The dict context from the native runtime.

    Returns:
        A megaplan :class:`~arnold.pipelines.megaplan._pipeline.types.StepContext`
        suitable for passing to ``Step.run()``.
    """
    from pathlib import Path

    from arnold.pipelines.megaplan._pipeline.types import (
        StepContext as MegaStepContext,
    )
    from arnold.runtime.envelope import EMPTY_ENVELOPE

    if isinstance(ctx, MegaStepContext):
        return ctx
    if hasattr(ctx, "plan_dir") and hasattr(ctx, "state") and hasattr(ctx, "profile"):
        return ctx

    if isinstance(ctx, dict):
        _ctx: dict = ctx
        state: dict = dict(_ctx.get("state") or {})
        raw_inputs: dict = dict(_ctx.get("inputs") or {})
        artifact_root: str = str(_ctx.get("artifact_root", "."))
        envelope = _ctx.get("envelope") or EMPTY_ENVELOPE
    else:
        state = dict(getattr(ctx, "state", {}) or {})
        raw_inputs = dict(getattr(ctx, "inputs", {}) or {})
        artifact_root = str(getattr(ctx, "artifact_root", "."))
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE

    plan_dir = Path(artifact_root)

    # ── derive profile from state config ──────────────────────────
    config: dict = state.get("config", {}) if isinstance(state, dict) else {}
    profile: dict = {
        "root": plan_dir,
        "project_dir": config.get("project_dir", str(plan_dir)),
    }
    mode: str = config.get("mode", "code") if isinstance(config, dict) else "code"

    # ── coerce input values to Path where possible ────────────────
    inputs: dict = {}
    for k, v in raw_inputs.items():
        if isinstance(v, str):
            inputs[k] = Path(v)
        elif isinstance(v, Path):
            inputs[k] = v
        else:
            inputs[k] = v

    return MegaStepContext(
        plan_dir=plan_dir,
        state=state,
        profile=profile,
        mode=mode,
        inputs=inputs,
        envelope=envelope,
    )


@phase(name="prep", produces=_PREP_PRODUCES, consumes=_PREP_CONSUMES)
def _native_prep(ctx: dict):
    """Native phase wrapper for **prep** — delegates to :class:`PrepStep`."""
    return PrepStep().run(_dict_to_step_context(ctx))


@phase(name="plan", produces=_PLAN_PRODUCES, consumes=_PLAN_CONSUMES)
def _native_plan(ctx: dict):
    """Native phase wrapper for **plan** — delegates to :class:`PlanStep`."""
    return PlanStep().run(_dict_to_step_context(ctx))


@phase(name="critique", produces=_CRITIQUE_PRODUCES, consumes=_CRITIQUE_CONSUMES)
def _native_critique(ctx: dict):
    """Native phase wrapper for **critique** — delegates to :class:`CritiqueStep`."""
    return CritiqueStep().run(_dict_to_step_context(ctx))


@phase(name="gate", produces=_GATE_PRODUCES, consumes=_GATE_CONSUMES)
def _native_gate(ctx: dict):
    """Native phase wrapper for **gate** — delegates to :class:`GateStep`."""
    return GateStep().run(_dict_to_step_context(ctx))



@phase(name="revise", produces=_REVISE_PRODUCES, consumes=_REVISE_CONSUMES)
def _native_revise(ctx: dict):
    """Native phase wrapper for **revise** — delegates to :class:`ReviseStep`."""
    return ReviseStep().run(_dict_to_step_context(ctx))


@phase(name="finalize", produces=_FINALIZE_PRODUCES, consumes=_FINALIZE_CONSUMES)
def _native_finalize(ctx: dict):
    """Native phase wrapper for **finalize** — delegates to :class:`FinalizeStep`."""
    return FinalizeStep().run(_dict_to_step_context(ctx))


@phase(name="execute", produces=_EXECUTE_PRODUCES, consumes=_EXECUTE_CONSUMES)
def _native_execute(ctx: dict):
    """Native phase wrapper for **execute** — delegates to :class:`ExecuteStep`."""
    return ExecuteStep().run(_dict_to_step_context(ctx))


@phase(name="review", produces=_REVIEW_PRODUCES, consumes=_REVIEW_CONSUMES)
def _native_review(ctx: dict):
    """Native phase wrapper for **review** — delegates to :class:`ReviewStep`."""
    return ReviewStep().run(_dict_to_step_context(ctx))


@phase(name="tiebreaker", produces=_TIEBREAKER_PRODUCES, consumes=_TIEBREAKER_CONSUMES)
def _native_tiebreaker(ctx: dict):
    """Native phase wrapper for **tiebreaker** — delegates to :class:`TiebreakerStep`."""
    return TiebreakerStep().run(_dict_to_step_context(ctx))



# ── Native decision wrappers ─────────────────────────────────────────────
# Gate and tiebreaker are the two decision points in the Megaplan pipeline.
# Their vocabularies match the decision_vocabulary fields on the
# corresponding Stage objects in build_pipeline().


@decision(name="gate", vocabulary=_GATE_RUNTIME_DECISION_VOCABULARY)
def _native_gate_decision(ctx: dict) -> str:
    """Native decision wrapper for **gate** decisions.

    The gate decision vocabulary mirrors the four planning decisions
    (proceed, iterate, tiebreaker, escalate) declared on the gate
    Stage in :func:`build_pipeline`.

    Returns one of the vocabulary labels based on the gate result.
    """
    state = _extract_runtime_state(ctx)

    last_gate = state.get("last_gate")
    if isinstance(last_gate, dict):
        rec = _normalize_gate_recommendation(last_gate.get("recommendation"))
        if rec is not None:
            return rec

    gate_payload = state.get("gate_payload")
    if isinstance(gate_payload, dict):
        rec = _normalize_gate_recommendation(gate_payload.get("recommendation"))
        if rec is not None:
            return rec
        mapped_next = _map_gate_next_label(gate_payload.get("next"))
        if mapped_next is not None:
            return mapped_next

    contract_result = _contract_result_payload(state, "gate")
    if isinstance(contract_result, dict):
        metadata = contract_result.get("metadata")
        if isinstance(metadata, dict):
            verdict = metadata.get("verdict")
            if isinstance(verdict, dict):
                rec = _normalize_gate_recommendation(verdict.get("recommendation"))
                if rec is not None:
                    return rec

    if state.get("current_state") == "aborted":
        return "override abort"
    return "proceed"


@decision(name="tiebreaker", vocabulary=_TIEBREAKER_DECISION_VOCABULARY)
def _native_tiebreaker_decision(ctx: dict) -> str:
    """Native decision wrapper for **tiebreaker** decisions.

    The tiebreaker decision vocabulary mirrors the three tiebreaker
    decisions (iterate, proceed, escalate) declared on the tiebreaker
    Stage in :func:`build_pipeline`.

    Returns one of the vocabulary labels based on the tiebreaker result.
    """
    state = _extract_runtime_state(ctx)

    recommendation = state.get("subloop:tiebreaker:recommendation")
    if recommendation in _TIEBREAKER_DECISION_VOCABULARY:
        return str(recommendation)

    tiebreaker_payload = state.get("tiebreaker_payload")
    if isinstance(tiebreaker_payload, dict):
        rec = tiebreaker_payload.get("recommendation")
        if rec in _TIEBREAKER_DECISION_VOCABULARY:
            return str(rec)

    contract_result = _contract_result_payload(state, "tiebreaker")
    if isinstance(contract_result, dict):
        metadata = contract_result.get("metadata")
        if isinstance(metadata, dict):
            verdict = metadata.get("verdict")
            if isinstance(verdict, dict):
                rec = verdict.get("recommendation")
                if rec in _TIEBREAKER_DECISION_VOCABULARY:
                    return str(rec)

    current_state = state.get("current_state")
    if current_state == "critiqued":
        return "iterate"
    if current_state == "aborted":
        return "escalate"
    return "proceed"


def _extract_runtime_state(ctx: object) -> dict:
    if isinstance(ctx, dict):
        state = ctx.get("state")
        return dict(state) if isinstance(state, dict) else {}
    state = getattr(ctx, "state", None)
    return dict(state) if isinstance(state, dict) else {}


def _normalize_gate_recommendation(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    mapping = {
        "iterate": "iterate",
        "proceed": "proceed",
        "tiebreaker": "tiebreaker",
        "escalate": "escalate",
        "override abort": "override abort",
        "override-abort": "override abort",
        "override force-proceed": "override force-proceed",
        "override-force-proceed": "override force-proceed",
    }
    return mapping.get(normalized)


def _map_gate_next_label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    mapping = {
        "revise": "iterate",
        "tiebreaker": "tiebreaker",
        "gate": "proceed",
        "override force-proceed": "override force-proceed",
        "override abort": "override abort",
    }
    return mapping.get(value)


def _contract_result_payload(state: dict, stage_name: str) -> dict | None:
    published = state.get("__contract_results__")
    if not isinstance(published, dict):
        return None
    contract_result = published.get(stage_name)
    payload = getattr(contract_result, "payload", None)
    if not isinstance(payload, dict):
        return None
    envelope_payload = payload.get("payload")
    return envelope_payload if isinstance(envelope_payload, dict) else payload


def _set_projection_metadata(
    fn: object,
    *,
    stage_name: str,
    edges: tuple[object, ...] | None = None,
    decision_vocabulary: frozenset[str] | None = None,
    loop_condition: object | None = None,
    merge_stage: bool = True,
    skip_stage: bool = False,
    disable_binding_map: bool = True,
) -> None:
    setattr(fn, "__native_projection_stage_name__", stage_name)
    setattr(fn, "__native_projection_merge_stage__", merge_stage)
    setattr(fn, "__native_projection_skip_stage__", skip_stage)
    setattr(fn, "__native_projection_disable_binding_map__", disable_binding_map)
    if edges is not None:
        setattr(fn, "__native_projection_edges__", edges)
    if decision_vocabulary is not None:
        setattr(fn, "__native_projection_decision_vocabulary__", decision_vocabulary)
    if loop_condition is not None:
        setattr(fn, "__native_projection_loop_condition__", loop_condition)


_set_projection_metadata(
    _native_prep,
    stage_name="prep",
    edges=(
        Edge(label="pass", target="plan"),
        Edge(label="fail", target="halt"),
        Edge(label="plan", target="plan"),
    ),
)
_set_projection_metadata(_native_plan, stage_name="plan")
_set_projection_metadata(
    _native_critique,
    stage_name="critique",
    edges=(
        Edge(label="gate_unset:gate", target="gate"),
        Edge(label="gate", target="gate"),
    ),
)
_set_projection_metadata(
    _native_gate,
    stage_name="gate",
    edges=(
        Edge(label="proceed", target="finalize", kind="decision"),
        Edge(label="iterate", target="revise", kind="decision"),
        Edge(label="tiebreaker", target="tiebreaker", kind="decision"),
        Edge(label="escalate", target="finalize", kind="decision"),
        Edge(label="revise", target="revise"),
        Edge(label="gate", target="finalize"),
        Edge(label="override force-proceed", target="finalize"),
        Edge(label="override abort", target="halt"),
    ),
    decision_vocabulary=_GATE_DECISION_VOCABULARY,
    loop_condition=_planning_loop_should_halt,
)
_set_projection_metadata(_native_revise, stage_name="revise")
_set_projection_metadata(_native_finalize, stage_name="finalize")
_set_projection_metadata(_native_execute, stage_name="execute")
_set_projection_metadata(
    _native_review,
    stage_name="review",
    edges=(
        Edge(label="review", target="halt"),
        Edge(label="halt", target="halt"),
    ),
)
_set_projection_metadata(
    _native_tiebreaker,
    stage_name="tiebreaker",
    edges=tiebreaker_edges(
        on_iterate="critique",
        on_proceed="finalize",
        on_escalate="finalize",
    ),
    decision_vocabulary=_TIEBREAKER_DECISION_VOCABULARY,
)
_set_projection_metadata(
    _native_gate_decision,
    stage_name="gate",
    skip_stage=True,
)
_set_projection_metadata(
    _native_tiebreaker_decision,
    stage_name="tiebreaker",
    skip_stage=True,
)
_native_gate_decision.__native_runtime_emit_stage_complete__ = False
_native_tiebreaker_decision.__native_runtime_emit_stage_complete__ = False


# Backwards-compatible alias so callers importing ``compile_planning_pipeline``
# from this package get the canonical implementation directly.
compile_planning_pipeline = build_pipeline
