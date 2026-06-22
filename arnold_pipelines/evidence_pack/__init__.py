"""Evidence-pack verifier pipeline.

Model-less verification of persisted evidence-pack JSON artifacts. This is the
M5 migrated home for the former ``arnold/pipelines/evidence_pack`` package; the
legacy package remains in place only until M6 deletion.

Topology:

    ingest -> content_validators (fanout) -> reduce -> human_review -> emit_attestation
"""

from __future__ import annotations

from arnold.manifest import FanoutPolicy, ReducerRef, SuspensionRoute, WorkflowPolicy
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


name: str = "evidence-pack"
description: str = "Model-less verification of persisted evidence-pack JSON artifacts."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("in_process", "verify")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("artifact-verification", "evidence-pack")


_VALIDATOR_KINDS: tuple[str, ...] = (
    "structural_audit",
    "budget_enforcement",
    "suspension_propagation",
    "by_ref_validation",
    "human_review_gate",
)


def build_pipeline(name: str = "evidence_pack_verifier") -> Pipeline:
    """Return the canonical evidence-pack verification pipeline."""

    ingest = Step(
        id="ingest",
        kind="agent",
        label="Ingest evidence pack",
        inputs=(Input(name="evidence_pack"),),
        outputs=(Output(name="evidence_pack_payload"),),
        capabilities=(Capability(id="artifact-verification", route="ingest"),),
        metadata={"stage": "ingest"},
    )
    content_validators = Step(
        id="content_validators",
        kind="fanout",
        label="Parallel checkpoint validators",
        inputs=(Input(name="evidence_pack_payload", value_ref="ingest.evidence_pack_payload"),),
        outputs=(Output(name="checkpoint_results"),),
        capabilities=(Capability(id="artifact-verification", route="validate"),),
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(
                mode="static",
                width=len(_VALIDATOR_KINDS),
                reducer_ref="evidence_pack:join_validators",
            ),
            reducers=(
                ReducerRef(
                    reducer_id="evidence_pack:join_validators",
                    input_ref="checkpoint_results",
                    output_ref="checkpoint_results",
                ),
            ),
        ),
        metadata={
            "validator_kinds": _VALIDATOR_KINDS,
            "stage": "content_validators",
        },
    )
    reduce_step = Step(
        id="reduce",
        kind="agent",
        label="Reduce validator results to verdict",
        inputs=(
            Input(name="evidence_pack_payload", value_ref="ingest.evidence_pack_payload"),
            Input(name="checkpoint_results", value_ref="content_validators.checkpoint_results"),
        ),
        outputs=(Output(name="verdict"),),
        capabilities=(Capability(id="artifact-verification", route="reduce"),),
        metadata={"stage": "reduce"},
    )
    human_review = Step(
        id="human_review",
        kind="human_gate",
        label="Human review gate",
        inputs=(
            Input(name="evidence_pack_payload", value_ref="ingest.evidence_pack_payload"),
            Input(name="verdict", value_ref="reduce.verdict"),
        ),
        outputs=(Output(name="human_decision"),),
        capabilities=(Capability(id="human", route="review"),),
        policy=WorkflowPolicy(
            suspension_routes=(
                SuspensionRoute(route_id="human_review:gate", capability_id="human:review"),
            ),
        ),
        metadata={"stage": "human_review"},
    )
    emit_attestation = Step(
        id="emit_attestation",
        kind="emit",
        label="Emit signed attestation",
        inputs=(
            Input(name="evidence_pack_payload", value_ref="ingest.evidence_pack_payload"),
            Input(name="verdict", value_ref="reduce.verdict"),
            Input(name="human_decision", value_ref="human_review.human_decision"),
        ),
        outputs=(Output(name="attestation"),),
        capabilities=(Capability(id="artifact-verification", route="attest"),),
        metadata={"stage": "emit_attestation", "terminal": True},
    )

    return Pipeline(
        id=name,
        version="m5-phase3",
        steps=(ingest, content_validators, reduce_step, human_review, emit_attestation),
        routes=(
            Route(id="ingest:content_validators", source="ingest", target="content_validators", label="validators"),
            Route(id="content_validators:reduce", source="content_validators", target="reduce", label="completed"),
            Route(id="reduce:human_review", source="reduce", target="human_review", label="human_review"),
            Route(id="human_review:emit_attestation", source="human_review", target="emit_attestation", label="completed"),
        ),
        capabilities=(
            Capability(id="artifact-verification", route="default"),
            Capability(id="human", route="review", required=False),
        ),
        metadata={
            "name": name,
            "description": description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
        },
    )


def build_continuation_pipeline(name: str = "evidence_pack_continuation") -> Pipeline:
    """Return the continuation pipeline that resumes from ``human_review``."""

    human_review = Step(
        id="human_review",
        kind="human_gate",
        label="Human review gate (continuation)",
        inputs=(
            Input(name="evidence_pack_payload"),
            Input(name="verdict"),
        ),
        outputs=(Output(name="human_decision"),),
        capabilities=(Capability(id="human", route="review"),),
        metadata={"stage": "human_review", "continuation": True},
    )
    emit_attestation = Step(
        id="emit_attestation",
        kind="emit",
        label="Emit signed attestation",
        inputs=(
            Input(name="evidence_pack_payload"),
            Input(name="verdict"),
            Input(name="human_decision", value_ref="human_review.human_decision"),
        ),
        outputs=(Output(name="attestation"),),
        capabilities=(Capability(id="artifact-verification", route="attest"),),
        metadata={"stage": "emit_attestation", "terminal": True},
    )

    return Pipeline(
        id=name,
        version="m5-phase3",
        steps=(human_review, emit_attestation),
        routes=(
            Route(id="human_review:emit_attestation", source="human_review", target="emit_attestation", label="emit"),
        ),
        capabilities=(
            Capability(id="artifact-verification", route="default"),
            Capability(id="human", route="review", required=False),
        ),
        metadata={
            "name": name,
            "description": "Evidence-pack continuation from human_review",
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
        },
    )


__all__ = [
    "build_continuation_pipeline",
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
