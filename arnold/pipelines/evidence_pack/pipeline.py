"""Native-first ``evidence_pack`` pipeline entrypoint and metadata."""

from __future__ import annotations

from typing import Any, Mapping

from arnold.pipeline import Pipeline
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)

from arnold.pipelines.evidence_pack.steps import EvidencePackStep


name: str = "evidence-pack"
description: str = "Model-less verification of persisted evidence-pack JSON artifacts."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "verify")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("artifact-verification", "evidence-pack")


def _stage(
    stage_name: str,
    next_label: str,
    *,
    produces: tuple[Port, ...] = (),
    consumes: tuple[PortRef, ...] = (),
) -> Stage:
    """Build a projected Stage shell for *stage_name* with typed ports and an outgoing edge."""
    edges = () if next_label == "halt" else (Edge(label=next_label, target=next_label),)
    return Stage(
        name=stage_name,
        step=EvidencePackStep(name=stage_name, next_label=next_label),
        edges=edges,
        produces=produces,
        consumes=consumes,
    )


def _join_validators(
    results: list[StepResult],
    ctx: StepContext | None = None,
) -> StepResult:
    """Barrier-join reducer for the *content_validators* fanout.

    Merges all validator outputs and emits a ``StepResult`` that routes
    to ``reduce``.  Mirrors the reducer attached to the native
    ``parallel(..., name="content_validators", reducer=_join_validators)``
    block so the projected shell's join signature matches the native
    topology.
    """
    _ = ctx
    merged: dict[str, Any] = {}
    checkpoint_paths: list[str] = []

    for result in results:
        if isinstance(result, StepResult):
            merged.update(result.outputs)
            from pathlib import Path

            checkpoint_paths.extend(
                str(value)
                for value in result.outputs.values()
                if isinstance(value, (str, Path))
            )
        elif isinstance(result, Mapping):
            merged.update({str(key): value for key, value in result.items()})

    if checkpoint_paths:
        merged["checkpoints"] = tuple(checkpoint_paths)

    return StepResult(outputs=merged, next="reduce")


def _build_projected_pipeline(name: str = "evidence_pack_verifier") -> Pipeline:
    """Build the projected (native-shell) pipeline graph.

    Returns a Pipeline whose stages mirror the evidence-pack topology::

        ingest → content_validators (fanout) → reduce → human_review → emit_attestation

    The native program is *not* attached here — that happens in
    :func:`build_pipeline` so the projected shell and native compilation
    stay independently testable.
    """
    if name != "evidence_pack_verifier":
        return Pipeline(
            stages={
                "manifest_introspection": Stage(
                    name="manifest_introspection",
                    step=EvidencePackStep(name="manifest_introspection", next_label="halt"),
                    edges=(),
                )
            },
            entry="manifest_introspection",
        )

    # ------------------------------------------------------------------
    # Typed port declarations (mirrors native.py phase signatures)
    # ------------------------------------------------------------------
    evidence_pack_port = Port("evidence_pack", "application/json")
    evidence_pack_ref = PortRef("evidence_pack", "application/json")
    checkpoints_port = Port("checkpoints", "application/json", cardinality="collection")
    checkpoints_ref = PortRef("checkpoints", "application/json", cardinality="collection")
    verdict_port = Port("verdict", "application/json")
    verdict_ref = PortRef("verdict", "application/json")
    attestation_port = Port("attestation", "application/json")

    # -- content_validators fanout --------------------------------------
    validator_step_names = (
        "validator_structural_audit",
        "validator_budget_enforcement",
        "validator_suspension_propagation",
        "validator_by_ref_validation",
        "validator_human_review_gate",
    )
    validator_steps = tuple(
        EvidencePackStep(name=vn, next_label="reduce") for vn in validator_step_names
    )

    stages: dict[str, Stage | ParallelStage] = {
        "ingest": _stage(
            "ingest",
            "content_validators",
            produces=(evidence_pack_port,),
        ),
        "content_validators": ParallelStage(
            name="content_validators",
            steps=validator_steps,
            join=_join_validators,
            consumes=(evidence_pack_ref,),
            produces=(checkpoints_port,),
            edges=(Edge(label="reduce", target="reduce"),),
        ),
        "reduce": _stage(
            "reduce",
            "human_review",
            produces=(verdict_port,),
            consumes=(evidence_pack_ref, checkpoints_ref),
        ),
        "human_review": _stage(
            "human_review",
            "emit_attestation",
            consumes=(evidence_pack_ref, verdict_ref),
        ),
        "emit_attestation": _stage(
            "emit_attestation",
            "halt",
            produces=(attestation_port,),
            consumes=(evidence_pack_ref, verdict_ref),
        ),
    }

    return Pipeline(stages=stages, entry="ingest")


def build_pipeline(name: str = "evidence_pack_verifier", **_: object) -> Pipeline:
    """Return the canonical native-backed evidence-pack pipeline.

    Attaches a compiled native program to the projected shell. The native
    program encodes the full ingest→validators→reduce→human_review→attestation
    topology including fanout, suspension metadata, and human-gate decision
    choices.
    """
    from arnold.pipelines.evidence_pack.native import build_native_program

    projected = _build_projected_pipeline(name=name)
    native_prog = build_native_program()
    return Pipeline(
        stages=projected.stages,
        entry=projected.entry,
        resource_bundles=(),
        native_program=native_prog,
    )


__all__ = [
    "EvidencePackStep",
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
