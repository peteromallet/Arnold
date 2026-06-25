"""Canonical registry surface for the Megaplan Arnold plugin.

This module exposes the pipeline registry and operation dispatch helpers that
code under ``arnold.pipelines.megaplan`` needs. During M7 it is implemented as
a compatibility shim over the legacy ``arnold.pipelines.megaplan._pipeline.registry``
module so that existing behavior is preserved while the canonical import path
is established.
"""

from __future__ import annotations

from arnold.pipelines.megaplan._pipeline.registry import (
    CANONICAL_BUILTIN_PIPELINE,
    LEGACY_PIPELINE_ALIASES,
    ArnoldPipelineRegistry,
    BLESSED_ALLOWLIST,
    Disposition,
    NullOperationRegistry,
    OperationRegistry,
    OperationResult,
    PipelineRegistry,
    canonical_pipeline_name,
    control_status_result_from_operation_result,
    describe_pipeline,
    discover_python_pipelines,
    dispatch_operation_for,
    get_pipeline,
    make_megaplan_registry,
    operation_registry_for,
    override_catalog_for,
    phase_tuple_from_operation_result,
    pipeline_disposition,
    pipeline_metadata,
    pipeline_registration_kind,
    read_pipeline_skill_md,
    register_pipeline,
    registered_pipelines,
    rejected_pipeline_dispositions,
    resume_result_from_operation_result,
    run_pipeline_by_name,
    scan_python_pipelines,
    supported_operations_for,
)

__all__ = [
    "ArnoldPipelineRegistry",
    "BLESSED_ALLOWLIST",
    "CANONICAL_BUILTIN_PIPELINE",
    "Disposition",
    "LEGACY_PIPELINE_ALIASES",
    "NullOperationRegistry",
    "OperationRegistry",
    "OperationResult",
    "PipelineRegistry",
    "canonical_pipeline_name",
    "control_status_result_from_operation_result",
    "describe_pipeline",
    "discover_python_pipelines",
    "dispatch_operation_for",
    "get_pipeline",
    "make_megaplan_registry",
    "operation_registry_for",
    "override_catalog_for",
    "phase_tuple_from_operation_result",
    "pipeline_disposition",
    "pipeline_metadata",
    "pipeline_registration_kind",
    "read_pipeline_skill_md",
    "register_pipeline",
    "registered_pipelines",
    "rejected_pipeline_dispositions",
    "resume_result_from_operation_result",
    "run_pipeline_by_name",
    "scan_python_pipelines",
    "supported_operations_for",
]
