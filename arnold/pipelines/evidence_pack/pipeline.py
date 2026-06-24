"""Native-first evidence-pack pipeline declaration.

M4 migrates the evidence-pack verifier from a hand-built graph to a
``@pipeline("evidence_pack")`` native generator.  The existing step classes in
:mod:`arnold.pipelines.evidence_pack.steps` are reused unchanged; thin
``@phase`` wrappers bridge the native runtime's dict context into the
``StepContext`` those steps expect.

Control flow::

    ingest → content_validators (parallel fan-out) → reduce
    if verdict == FAIL:
        human_review  (phase-level SUSPENDED on first run)
        if approved: emit_attestation
    else:
        emit_attestation

The human-review gate is implemented as a normal ``@phase`` that returns
``ContractStatus.SUSPENDED`` when no ``human_input`` is present.  The native
runtime was extended in M4 to persist a resume cursor when a phase returns
``SUSPENDED`` and to merge caller-provided resume input into the restored
state on resume.  This keeps the existing ``human_input = {"approved": bool,
"comment": str}`` resume contract without requiring a dedicated
``@decision(human_gate=True)`` (which would suspend before the decision body
and change the evidence-pack semantics).

Judgment calls (see inline comments):

* Phase-level suspension is preferred over ``@decision(human_gate=True)``
  because the evidence-pack gate should only suspend when the verdict is
  FAIL, not unconditionally before a decision body.
* The projected graph still exposes a ``ParallelStage`` named
  ``content_validators`` so graph-conformance tests pass unchanged.
* ``@decision`` wrappers are marked ``skip_stage``; their only job is to
  route the native runtime.  Graph routing is carried by custom edges
  attached to the preceding ``@phase`` functions via projection metadata.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    ContractStatus,
    Edge,
    Port,
    PortRef,
    StepContext,
    StepResult,
)
from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    parallel,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)

# ---------------------------------------------------------------------------
# Typed port declarations (mirror the legacy graph shape)
# ---------------------------------------------------------------------------

EVIDENCE_PACK_PORT = Port(name="evidence_pack", content_type="application/json")
EVIDENCE_PACK_PORT_REF = PortRef(
    port_name="evidence_pack", content_type="application/json"
)
CHECKPOINTS_PORT = Port(
    name="checkpoints",
    content_type="application/json",
    cardinality="collection",
)
CHECKPOINTS_PORT_REF = PortRef(
    port_name="checkpoints",
    content_type="application/json",
    cardinality="collection",
)
VERDICT_PORT = Port(name="verdict", content_type="application/json")
VERDICT_PORT_REF = PortRef(port_name="verdict", content_type="application/json")
ATTESTATION_PORT = Port(name="attestation", content_type="application/json")

# ---------------------------------------------------------------------------
# Context adapter
# ---------------------------------------------------------------------------


def _dict_to_step_context(ctx: object) -> StepContext:
    """Adapt native-runtime dict contexts (or graph ``StepContext``) to ``StepContext``.

    The evidence-pack steps read ``ctx.artifact_root`` and ``ctx.inputs``.
    When the graph executor runs the projected pipeline it passes a real
    ``StepContext`` straight through; the native runtime passes a lightweight
    dict that we convert here.
    """
    if isinstance(ctx, StepContext):
        return ctx

    ctx_dict: dict[str, Any] = ctx if isinstance(ctx, dict) else {}
    return StepContext(
        artifact_root=str(ctx_dict.get("artifact_root", ".")),
        state=dict(ctx_dict.get("state", {})),
        inputs=dict(ctx_dict.get("inputs", {})),
    )


# ---------------------------------------------------------------------------
# Phase wrappers
# ---------------------------------------------------------------------------


@phase(name="ingest", produces=(EVIDENCE_PACK_PORT,))
def _native_ingest(ctx: dict[str, Any]) -> StepResult:
    """Ingest and validate the externally supplied evidence pack."""
    return IngestStep().run(_dict_to_step_context(ctx))


@phase(
    name="validator_structural_audit",
    produces=(CHECKPOINTS_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF,),
)
def _native_validator_structural_audit(ctx: dict[str, Any]) -> StepResult:
    return ContentValidatorStep(
        name="validator_structural_audit",
        checkpoint_kind="structural_audit",
    ).run(_dict_to_step_context(ctx))


@phase(
    name="validator_budget_enforcement",
    produces=(CHECKPOINTS_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF,),
)
def _native_validator_budget_enforcement(ctx: dict[str, Any]) -> StepResult:
    return ContentValidatorStep(
        name="validator_budget_enforcement",
        checkpoint_kind="budget_enforcement",
    ).run(_dict_to_step_context(ctx))


@phase(
    name="validator_suspension_propagation",
    produces=(CHECKPOINTS_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF,),
)
def _native_validator_suspension_propagation(ctx: dict[str, Any]) -> StepResult:
    return ContentValidatorStep(
        name="validator_suspension_propagation",
        checkpoint_kind="suspension_propagation",
    ).run(_dict_to_step_context(ctx))


@phase(
    name="validator_by_ref_validation",
    produces=(CHECKPOINTS_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF,),
)
def _native_validator_by_ref_validation(ctx: dict[str, Any]) -> StepResult:
    return ContentValidatorStep(
        name="validator_by_ref_validation",
        checkpoint_kind="by_ref_validation",
    ).run(_dict_to_step_context(ctx))


@phase(
    name="validator_human_review_gate",
    produces=(CHECKPOINTS_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF,),
)
def _native_validator_human_review_gate(ctx: dict[str, Any]) -> StepResult:
    return ContentValidatorStep(
        name="validator_human_review_gate",
        checkpoint_kind="human_review_gate",
    ).run(_dict_to_step_context(ctx))


@phase(
    name="reduce",
    produces=(VERDICT_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF, CHECKPOINTS_PORT_REF),
)
def _native_reduce(ctx: dict[str, Any]) -> StepResult:
    """Aggregate validator checkpoint results into a binary verdict."""
    return ReduceStep().run(_dict_to_step_context(ctx))


@phase(
    name="human_review",
    produces=(),
    consumes=(EVIDENCE_PACK_PORT_REF, VERDICT_PORT_REF),
)
def _native_human_review(ctx: dict[str, Any]) -> StepResult:
    """Suspend for human review or resume with human input.

    This phase returns ``ContractStatus.SUSPENDED`` when ``human_input`` is
    absent.  The native runtime's phase-suspension support persists a resume
    cursor and stops execution before advancing to the routing decision.
    """
    return HumanReviewStep().run(_dict_to_step_context(ctx))


@phase(
    name="emit_attestation",
    produces=(ATTESTATION_PORT,),
    consumes=(EVIDENCE_PACK_PORT_REF, VERDICT_PORT_REF),
)
def _native_emit_attestation(ctx: dict[str, Any]) -> StepResult:
    """Emit the final signed attestation artifact."""
    return EmitAttestationStep().run(_dict_to_step_context(ctx))


# ---------------------------------------------------------------------------
# Routing decisions (native runtime only — graph routing uses custom edges)
# ---------------------------------------------------------------------------


@decision(name="verdict_is_fail", vocabulary=frozenset({"fail", "pass"}))
def _native_verdict_is_fail(ctx: dict[str, Any]) -> str:
    """Return ``fail`` when the reduce verdict is FAIL, otherwise ``pass``."""
    state = ctx.get("state", {})

    # Prefer the published contract result from the reduce phase.
    published = state.get("__contract_results__")
    if isinstance(published, dict):
        contract_result = published.get("reduce")
        payload = getattr(contract_result, "payload", None)
        if isinstance(payload, dict) and payload.get("verdict") == "FAIL":
            return "fail"

    # Fallback: read the verdict artifact directly from its persisted path.
    verdict_path = state.get("verdict")
    if isinstance(verdict_path, str):
        try:
            data = json.loads(Path(verdict_path).read_text(encoding="utf-8"))
            if data.get("verdict") == "FAIL":
                return "fail"
        except (OSError, json.JSONDecodeError):
            pass

    return "pass"


@decision(name="human_review_decision", vocabulary=frozenset({"emit", "failed"}))
def _native_human_review_decision(ctx: dict[str, Any]) -> str:
    """Route to ``emit`` when human_input approves, else ``failed``."""
    human_input = ctx.get("state", {}).get("human_input")
    if isinstance(human_input, dict) and human_input.get("approved"):
        return "emit"
    return "failed"


# ---------------------------------------------------------------------------
# Parallel validator join
# ---------------------------------------------------------------------------


def _join_validators(results: list[Any], ctx: Any) -> StepResult:
    """Barrier-join for the five content validators.

    Collects each validator's checkpoint outputs into a single merged dict.
    The native M5a baseline executes branches sequentially and merges their
    outputs directly into working state, so this reducer is primarily used by
    the projected ``ParallelStage`` for graph-conformance checks.
    """
    del ctx  # reserved for future join context use
    outputs: dict[str, Any] = {}
    for r in results:
        if isinstance(r, dict):
            outputs.update(r)
        elif getattr(r, "outputs", None):
            outputs.update(r.outputs)
    return StepResult(outputs=outputs, next="completed")


# ---------------------------------------------------------------------------
# Native pipeline generator
# ---------------------------------------------------------------------------


@pipeline("evidence_pack")
def evidence_pack_native(ctx: dict[str, Any]) -> Any:
    """Native evidence-pack verifier: ingest → validators → reduce → gate → emit."""
    state = yield _native_ingest(ctx)
    for branch in parallel(
        [
            _native_validator_structural_audit,
            _native_validator_budget_enforcement,
            _native_validator_suspension_propagation,
            _native_validator_by_ref_validation,
            _native_validator_human_review_gate,
        ],
        reducer=_join_validators,
        name="content_validators",
    ):
        state = yield branch(ctx)
    state = yield _native_reduce(ctx)
    if _native_verdict_is_fail(ctx) == "fail":
        state = yield _native_human_review(ctx)
        if _native_human_review_decision(ctx) == "emit":
            state = yield _native_emit_attestation(ctx)
    else:
        state = yield _native_emit_attestation(ctx)
    return state


# ---------------------------------------------------------------------------
# Graph-projection metadata
# ---------------------------------------------------------------------------


def _set_projection_metadata(
    fn: object,
    *,
    stage_name: str,
    edges: tuple[Edge, ...] | None = None,
    decision_vocabulary: frozenset[str] | None = None,
    loop_condition: object | None = None,
    merge_stage: bool = True,
    skip_stage: bool = False,
    disable_binding_map: bool = False,
) -> None:
    """Attach metadata used by :func:`project_graph` when key_mode="phase"."""
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
    _native_ingest,
    stage_name="ingest",
    edges=(Edge(label="validators", target="content_validators"),),
)
_set_projection_metadata(
    _native_reduce,
    stage_name="reduce",
    edges=(
        Edge(label="human_review", target="human_review"),
        Edge(label="emit", target="emit_attestation"),
    ),
)
_set_projection_metadata(
    _native_human_review,
    stage_name="human_review",
    edges=(
        Edge(label="emit", target="emit_attestation"),
        Edge(label="failed", target="halt"),
    ),
)
_set_projection_metadata(
    _native_emit_attestation,
    stage_name="emit_attestation",
    edges=(Edge(label="halt", target="halt"),),
)
_set_projection_metadata(
    _native_verdict_is_fail,
    stage_name="reduce",
    skip_stage=True,
)
_set_projection_metadata(
    _native_human_review_decision,
    stage_name="human_review",
    skip_stage=True,
)

# Suppress stage-complete emission for the routing decisions; they are not
# public stages and should not appear in the completed stage sequence.
_native_verdict_is_fail.__native_runtime_emit_stage_complete__ = False  # type: ignore[attr-defined]
_native_human_review_decision.__native_runtime_emit_stage_complete__ = False  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------


def build_pipeline(name: str = "evidence_pack") -> "Pipeline":
    """Return the canonical native-backed evidence-pack :class:`Pipeline`.

    Compiles the ``@pipeline("evidence_pack")`` declaration and projects it
    through phase-keyed graph projection.  The returned shell carries the
    compiled ``native_program`` so the native runtime can execute it directly.
    """
    from arnold.pipeline import Pipeline

    program = compile_pipeline(evidence_pack_native)
    native_pipeline = project_graph(program, key_mode="phase")
    return replace(
        native_pipeline,
        native_program=program,
        resource_bundles=(),
    )
