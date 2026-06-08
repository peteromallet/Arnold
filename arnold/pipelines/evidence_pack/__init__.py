"""Evidence-pack pipeline - model-less verification of persisted JSON artifacts."""

from arnold.pipelines.evidence_pack.pipelines import (
    build_continuation_pipeline,
    build_initial_pipeline,
)

name = "evidence-pack"
description = "Model-less verification of persisted evidence-pack JSON artifacts."
driver = "in_process"
entrypoint = "arnold.pipelines.evidence_pack:build_pipeline"
arnold_api_version = "1.0"
capabilities = ("artifact-verification", "evidence-pack")

build_pipeline = build_initial_pipeline

__all__ = [
    "arnold_api_version",
    "build_continuation_pipeline",
    "build_initial_pipeline",
    "build_pipeline",
    "capabilities",
    "description",
    "driver",
    "entrypoint",
    "name",
]
