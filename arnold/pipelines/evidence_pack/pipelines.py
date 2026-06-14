"""Evidence-pack pipeline construction — initial and continuation shapes.

Both pipeline shapes are assembled with the neutral
:class:`arnold.pipeline.builder.PipelineBuilder` using typed
:class:`Port` / :class:`PortRef` bindings, direct :class:`ReadRef` /
:class:`WriteRef` imports, and :meth:`add_parallel_stage` for the
content-validator fan-out.

The **initial** pipeline runs::

    ingest → validators (parallel fan-out) → reduce → human_review → emit_attestation

The **continuation** pipeline resumes from ``human_review``::

    human_review → emit_attestation

Both shapes pass :func:`arnold.pipeline.validator.validate`.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline import ParallelStage, Pipeline, PipelineBuilder, Port, PortRef, ReadRef, Stage, WriteRef
from arnold.pipeline.step_invocation import StepInvocation

from arnold.pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)

# ---------------------------------------------------------------------------
# Shared typed declarations
# ---------------------------------------------------------------------------

EVIDENCE_PACK_READ = ReadRef(name="evidence_pack", external=True)
"""Read-ref for the externally-supplied evidence-pack JSON artifact."""

EVIDENCE_PACK_PORT = Port(name="evidence_pack", content_type="application/json")
EVIDENCE_PACK_PORT_REF = PortRef(port_name="evidence_pack", content_type="application/json")
CHECKPOINTS_PORT = Port(name="checkpoints", content_type="application/json", cardinality="collection")
CHECKPOINTS_PORT_REF = PortRef(
    port_name="checkpoints", content_type="application/json", cardinality="collection"
)
CHECKPOINT_WRITE = WriteRef(name="checkpoint")
VERDICT_PORT = Port(name="verdict", content_type="application/json")
_VERDICT_PORT_REF = PortRef(port_name="verdict", content_type="application/json")
ATTESTATION_PORT = Port(name="attestation", content_type="application/json")

# ---------------------------------------------------------------------------
# Initial pipeline
# ---------------------------------------------------------------------------


def build_initial_pipeline(name: str = "evidence_pack_verifier") -> Pipeline:
    """Build the initial evidence-pack verification pipeline.

    Stages
    ------
    * ``ingest`` — load + validate the evidence pack JSON artifact.
    * ``content_validators`` — parallel fan-out of 5 checkpoint validators.
    * ``reduce`` — aggregate validator results into a binary verdict.
    * ``human_review`` — suspend for human gate on FAIL; resume/resolve on PASS.
    * ``emit_attestation`` — write final signed attestation artifact.

    Returns
    -------
    Pipeline
        A fully assembled :class:`Pipeline` ready for execution.
    """
    builder = PipelineBuilder(name=name, description="Evidence-pack verification pipeline")

    # ── 1. Ingest ──────────────────────────────────────────────────────
    ingest_step = IngestStep()
    ingest_stage = Stage(
        name="ingest",
        step=ingest_step,
        reads=(EVIDENCE_PACK_READ,),
        writes=(EVIDENCE_PACK_PORT,),
        consumes=(),
        produces=(EVIDENCE_PACK_PORT,),
    )
    builder.add_stage(ingest_stage, emit_label="validators")

    # ── 2. Content validators (parallel fan-out) ───────────────────────
    validator_kinds = [
        "structural_audit",
        "budget_enforcement",
        "suspension_propagation",
        "by_ref_validation",
        "human_review_gate",
    ]
    validator_steps = tuple(
        ContentValidatorStep(
            name=f"validator_{kind}",
            checkpoint_kind=kind,
        )
        for kind in validator_kinds
    )

    def _join_validators(results: list[Any], ctx: Any) -> Any:
        """Barrier-join for parallel content validators.

        Returns a StepResult whose ``next`` label is ``completed`` so the
        executor routes to the reduce stage, regardless of individual
        validator outcomes (the reduce stage handles aggregation).
        """
        from arnold.pipeline import ContractStatus, StepResult

        outputs: dict[str, Any] = {}
        for r in results:
            if getattr(r, "outputs", None):
                outputs.update(r.outputs)
        return StepResult(
            outputs=outputs,
            next="completed",
            contract_result=None,
        )

    validators_stage = ParallelStage(
        name="content_validators",
        steps=validator_steps,
        join=_join_validators,
        invocation=StepInvocation.with_adapter_config(
            kind="tool",
            adapter_config={
                "tool": "evidence-pack-checkpoint-validator",
                "mode": "local-deterministic",
            },
        ),
        reads=(EVIDENCE_PACK_PORT_REF,),
        writes=(CHECKPOINTS_PORT,),
        consumes=(EVIDENCE_PACK_PORT_REF,),
        produces=(CHECKPOINTS_PORT,),
    )
    builder.add_parallel_stage(validators_stage, emit_label="completed")

    # ── 3. Reduce ─────────────────────────────────────────────────────
    reduce_step = ReduceStep()
    reduce_stage = Stage(
        name="reduce",
        step=reduce_step,
        invocation=StepInvocation.with_adapter_config(
            kind="model",
            adapter_config={
                "model": "evidence-pack-verdict-summarizer",
                "mode": "metadata-only",
            },
        ),
        reads=(EVIDENCE_PACK_PORT_REF, CHECKPOINTS_PORT_REF),
        writes=(VERDICT_PORT,),
        consumes=(EVIDENCE_PACK_PORT_REF, CHECKPOINTS_PORT_REF),
        produces=(VERDICT_PORT,),
    )
    builder.add_stage(reduce_stage, emit_label="human_review")

    # ── 4. Human review ───────────────────────────────────────────────
    human_review_step = HumanReviewStep()
    review_stage = Stage(
        name="human_review",
        step=human_review_step,
        reads=(EVIDENCE_PACK_PORT_REF, _VERDICT_PORT_REF),
        writes=(CHECKPOINT_WRITE,),
        consumes=(EVIDENCE_PACK_PORT_REF, _VERDICT_PORT_REF),
        produces=(),
    )
    builder.add_stage(review_stage, emit_label="completed")

    # ── 5. Emit attestation ───────────────────────────────────────────
    emit_step = EmitAttestationStep()
    emit_stage = Stage(
        name="emit_attestation",
        step=emit_step,
        reads=(EVIDENCE_PACK_PORT_REF, _VERDICT_PORT_REF),
        writes=(ATTESTATION_PORT,),
        consumes=(EVIDENCE_PACK_PORT_REF, _VERDICT_PORT_REF),
        produces=(ATTESTATION_PORT,),
    )
    builder.add_stage(emit_stage)

    return builder.build(derive_bindings=True)


# ---------------------------------------------------------------------------
# Continuation pipeline
# ---------------------------------------------------------------------------


CONTINUATION_EVIDENCE_PACK_READ = ReadRef(name="evidence_pack", external=True, optional=True)
CONTINUATION_VERDICT_READ = ReadRef(name="verdict", external=True, optional=True)
"""Read-refs for externally-supplied artifacts in the continuation pipeline."""


def build_continuation_pipeline(name: str = "evidence_pack_continuation") -> Pipeline:
    """Build the continuation pipeline that resumes from ``human_review``.

    This is invoked as a fresh pipeline with ``entry='human_review'`` after
    the initial pipeline suspends at the human-gate stage.  The human review
    step reads ``human_input`` from ``ctx.inputs``, resolves the gate, and
    either routes to ``emit`` (if approved) or ``failed``.

    External inputs (evidence_pack, verdict) arrive via ``ReadRef``\u2019d
    persisted artifacts and are surfaced in ``ctx.inputs``.  They are NOT
    declared as typed ``PortRef`` consumes because there is no upstream
    producer in this fresh pipeline.

    Returns
    -------
    Pipeline
        A fully assembled continuation :class:`Pipeline`.
    """
    builder = PipelineBuilder(name=name, description="Evidence-pack continuation from human_review")

    # ── Human review (resume) ─────────────────────────────────────────
    human_review_step = HumanReviewStep()
    review_stage = Stage(
        name="human_review",
        step=human_review_step,
        reads=(CONTINUATION_VERDICT_READ, CONTINUATION_EVIDENCE_PACK_READ),
        writes=(CHECKPOINT_WRITE,),
    )
    builder.add_stage(review_stage, emit_label="emit")

    # ── Emit attestation ──────────────────────────────────────────────
    emit_step = EmitAttestationStep()
    emit_stage = Stage(
        name="emit_attestation",
        step=emit_step,
        reads=(CONTINUATION_EVIDENCE_PACK_READ, CONTINUATION_VERDICT_READ),
        writes=(ATTESTATION_PORT,),
        produces=(ATTESTATION_PORT,),
    )
    builder.add_stage(emit_stage)

    return builder.build(derive_bindings=True)
