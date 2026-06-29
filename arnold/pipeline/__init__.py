"""Arnold pipeline primitives — neutral, opinion-free data shapes.

This sub-package holds the pure-dataclass / Protocol types that define
a pipeline without reference to Megaplan-specific semantics:

* ``Pipeline``          — named DAG of stages and edges.
* ``Stage``             — a single-step stage with labelled edges.
* ``ParallelStage``     — a fan-out stage whose steps run concurrently.
* ``Edge``              — materialised dependency between two stages.
* ``Step``              — Protocol for executable units.
* ``StepContext``       — runtime context passed to every step.
* ``StepResult``        — result of executing a single step.
* ``PipelineVerdict``   — recommendation / override for pipeline control flow.
* ``StateDelta``        — ordered multi-patch container.
* ``apply_delta``       — apply StateDelta patches to a state value.
* ``Port``              — typed content port.
* ``PortCardinality``   — singleton / collection / reserved stream vocabulary.
* ``PortRef``           — reference to a named port.
* ``RoutingKey``        — content-type–qualified routing key.
* ``ContentTypeRegistry`` — map content-type names → schema digests.
* ``ReduceResult``      — structured output of reduce-kind step.
* ``SelectionResult``   — structured output of selection/tournament reduce.
* ``ContractResult``    — single shared seam primitive (Step-IO + Evidence-First).
* ``ContractStatus``    — 3-status discriminant for ``ContractResult``.
* ``Suspension``        — typed interaction envelope (``status == SUSPENDED``);
  ``HumanSuspension``    — canonical name; ``Suspension`` is a backward-compatible alias.
* ``EvidenceArtifactRef`` — evidence-by-reference primitive.
* ``Provenance``        — lineage sub-record of ``ContractResult``.
* ``Freshness``         — TTL sub-record of ``ContractResult``.
* ``CONTRACT_RESULT_SCHEMA_VERSION`` — SHA-256 hex digest of the contract shape.
* ``ValidationResult``  — aggregate structural validation outcome.
* ``ValidationDiagnostic`` — single deterministic validation failure.
* ``ContractSchemaRegistry`` — neutral retained schema storage with hash-first lookup.
* ``AcceptedVersionRange``   — inclusive logical-type history bounds for a consumer.
* ``ContentValidatorRegistry`` — instance-local validator registry keyed by content_type.
* ``select_audit_mode`` — deterministic full/manifest audit-mode selector.

Sub-modules:

* ``types``           — core dataclasses and structural types.
* ``cost_types``      — ``CostStatus``, ``CostSource``, ``CostResult``,
  ``CanonicalUsage`` (neutral).
* ``state``           — ``StateDelta`` (loose multi-patch container) and helpers.
* ``contracts``       — ContractLedger and legal-coercion table.
* ``pattern_select``  — tournament selection primitives (top_1, top_k, threshold).
* ``pattern_stops``   — loop-stop predicates (plateau, max_iters, etc.).
* ``pattern_types``   — PromoteFn / JoinFn type aliases.
* ``contract_validation`` — pure structural validation of ContractResult.payload.
* ``schema_registry`` — neutral file-backed schema registry with atomic writes.
* ``content_validation`` — content-type keyed validation hooks for blob metadata.
* ``audit_policy``    — deterministic audit-mode selection for size-threshold seams.
* ``native``          — canonical native program compilation, projection, and execution
  entrypoints re-exported here for convenience.

All public names are re-exported here.  Import from ``arnold.pipeline``:

    from arnold.pipeline import Pipeline, StepContext, StateDelta
    from arnold.pipeline import NativeProgram, compile_pipeline, run_native_pipeline

No Megaplan re-exports appear here; this is the neutral surface.
"""

from arnold.pipeline.audit_policy import AuditMode, AuditPolicyHook, select_audit_mode
from arnold.pipeline.content_validation import (
    ContentValidator,
    ContentValidatorRegistry,
    no_op_content_validator,
)
from arnold.pipeline.contract_validation import (
    ValidationDiagnostic,
    ValidationResult,
    validate_contract_result,
    validate_payload_against_schema,
)
from arnold.pipeline.contract_reduce import ReducePolicy, reduce_contract_results
from arnold.pipeline.contracts import ContractLedger, coerce, is_legal_coercion, legal_coercions
from arnold.pipeline.cost_types import CanonicalUsage, CostResult, CostSource, CostStatus
from arnold.pipeline.media_content import register_media_content_validators
from arnold.pipeline.native import (
    CursorUpgradeError,
    CursorUpgradeResult,
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    NativeExecutionResult,
    NativeProgram,
    NativeRuntimeDisabledError,
    NativeRuntimeError,
    NativeRuntimeHooks,
    NativeTraceHooks,
    NullNativeRuntimeHooks,
    compile_pipeline,
    force_legacy_runtime,
    native_runtime_enabled,
    persist_native_cursor,
    project_graph,
    read_native_cursor,
    require_native_runtime,
    run_native_pipeline,
    upgrade_graph_cursor_to_native,
)
from arnold.pipeline.llm_json import parse_llm_json
from arnold.pipeline.pattern_joins import aggregate_panel_join, majority_vote, weighted_vote
from arnold.pipeline.pattern_select import select, threshold, top_1, top_k
from arnold.pipeline.pattern_stops import LoopState, max_iters, no_improvement, plateau, threshold_reached
from arnold.pipeline.pattern_types import JoinFn, PromoteFn
from arnold.pipeline.pipeline_id_registry import (
    PipelineIdRegistry,
    PipelineIdRegistryError,
    RegistryRuntimeIdentity,
    load_pipeline_id_registry,
    load_pipeline_id_registries,
    resolve_registry_runtime_identity,
)
from arnold.pipeline.suite_delta import SuiteDelta, SuiteRunProtocol, compute_delta
from arnold.pipeline.schema_registry import (
    AcceptedVersionRange,
    ContractSchemaRegistry,
    SchemaRegistryError,
    accepts_version,
    canonical_schema_bytes,
    canonical_schema_json,
    normalize_schema_version,
    schema_version_for,
)
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOContractDecision,
    StepIODiagnostic,
    StepIOEnvelope,
    StepIOOperation,
    classify_step_io_contract,
    decide_step_io_read,
    decide_step_io_write,
    is_step_io_envelope,
)
from arnold.pipeline.step_io_handoff import StepIOHandoffResult, evaluate_step_io_handoff
from arnold.pipeline.step_io_policy import (
    STEP_IO_POLICY_FILENAME,
    StepIOPolicy,
    decision_blocks_read,
    decision_blocks_write,
    is_step_io_enforcement_eligible,
    has_step_io_self_validation_marker,
    load_step_io_policy,
    policy_for_envelope,
    record_step_io_self_validation_marker,
    resolve_step_io_policy,
    write_step_io_policy,
)
from arnold.pipeline.step_io_seams import SeamId, SeamResolution, resolve_seam_from_binding_map
from arnold.pipeline.step_io_telemetry import (
    TELEMETRY_FILENAME,
    StepIOViolationRecord,
    append_violation_record,
    emit_decision_telemetry,
    read_violation_records,
)
from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.resume import (
    COMPOSITE_RESUME_CURSOR_FILENAME,
    RESUME_CURSOR_FILENAME,
    persist_composite_resume_cursor,
    persist_resume_cursor,
    read_composite_resume_cursor,
    read_resume_cursor,
)
from arnold.pipeline.resume_validation import (
    RESUME_REVERIFY_DECLARATION_KEY,
    RESUME_REVERIFY_EXTENSION_KEY,
    ResumeReverifyDeclaration,
    ResumeReverifyResult,
    parse_resume_reverify_declaration,
    resolve_resume_reverify_artifact,
    reverify_resume_produces,
)
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    CONTENT_TYPES,
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContentTypeRegistry,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    EvidenceStatus,
    Freshness,
    HumanSuspension,
    Pipeline,
    PipelineVerdict,
    Port,
    PortCardinality,
    PortRef,
    Provenance,
    ReadRef,
    WriteRef,
    ReduceResult,
    RoutingKey,
    SelectionResult,
    Step,
    StepContext,
    StepResult,
    Suspension,
    TrustClass,
    register_schema,
)


# Re-exports from arnold.runtime for downstream consumers
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef
from arnold.execution.driver import AdvanceOutcome, CheckpointOutcome
from arnold.pipeline.driver import StepwiseDriver

__all__ = [
    "AcceptedVersionRange",
    "account_media_cost_from_result",
    "AdvanceOutcome",
    "CheckpointOutcome",
    "AuditMode",
    "AuditPolicyHook",
    "BillingRoute",
    "CAPABILITY_ALIASES",
    "CONTENT_TYPES",
    "CONTRACT_RESULT_SCHEMA_VERSION",
    "COMPOSITE_RESUME_CURSOR_FILENAME",
    "ContentValidator",
    "ContentValidatorRegistry",
    "ContentTypeRegistry",
    "ContractLedger",
    "ContractResult",
    "ContractSchemaRegistry",
    "ContractStatus",
    "CursorUpgradeError",
    "CursorUpgradeResult",
    "CanonicalUsage",
    "CostResult",
    "CostSource",
    "CostStatus",
    "DEFAULT_MEDIA_PRICING",
    "DEFAULT_PARALLEL_SAFE",
    "DEFAULT_PRICING",
    "Edge",
    "ExecutorHooks",
    "EvidenceArtifactRef",
    "EvidenceStatus",
    "Freshness",
    "HumanSuspension",
    "JoinFn",
    "LoopState",
    "Manifest",
    "ManifestError",
    "MediaCostAccumulator",
    "MediaPricingEntry",
    "MediaUsage",
    "MODEL_RESOURCE_CAPABILITIES",
    "NativeExecutionResult",
    "NativeProgram",
    "NativeCursorCorruptError",
    "NativeRuntimeDisabledError",
    "NativeRuntimeError",
    "NativeRuntimeHooks",
    "NativeTraceHooks",
    "NATIVE_CURSOR_VERSION",
    "NullNativeRuntimeHooks",
    "ParallelSafePredicate",
    "ParallelStage",
    "Pipeline",
    "PipelineBuilder",
    "PipelineIdRegistry",
    "PipelineIdRegistryError",
    "PipelineRegistry",
    "PipelineVerdict",
    "ProfileLoadError",
    "Port",
    "PortCardinality",
    "PortRef",
    "PricingEntry",
    "PromoteFn",
    "Provenance",
    "RegistryRuntimeIdentity",
    "ReduceResult",
    "ReadRef",
    "ResumeCursorRef",
    "RoutingKey",
    "ReducePolicy",
    "RuntimeEnvelope",
    "SelectionResult",
    "Stage",
    "StateDelta",
    "SuiteDelta",
    "SuiteRunProtocol",
    "Step",
    "StepIOClassification",
    "StepIOContractContext",
    "StepIOContractDecision",
    "StepIODiagnostic",
    "StepIOEnvelope",
    "StepIOHandoffResult",
    "StepIOOperation",
    "StepIOPolicy",
    "StepInvocation",
    "StepInvocationAdapter",
    "StepInvocationAdapterRegistry",
    "StepInvocationResult",
    "StepContext",
    "StepResult",
    "StepwiseDriver",
    "Suspension",
    "SchemaRegistryError",
    "SeamId",
    "SeamResolution",
    "TrustClass",
    "TrustGrade",
    "CapabilityEvidence",
    "CapabilityProof",
    "ValidationDiagnostic",
    "ValidationResult",
    "apply_delta",
    "accepts_version",
    "canonical_schema_bytes",
    "canonical_schema_json",
    "classify",
    "classify_step_io_contract",
    "compute_delta",
    "UsageExtraction",
    "compile_pipeline",
    "compute_media_cost",
    "coerce",
    "decide_step_io_read",
    "decide_step_io_write",
    "derive_binding_map",
    "derive_tenant_id",
    "decision_blocks_read",
    "decision_blocks_write",
    "estimate_cost_usd",
    "estimate_usage_cost",
    "force_legacy_runtime",
    "is_legal_coercion",
    "is_step_io_envelope",
    "is_step_io_enforcement_eligible",
    "evaluate_step_io_handoff",
    "has_step_io_self_validation_marker",
    "has_known_pricing",
    "legal_coercions",
    "load_step_io_policy",
    "load_profile_metadata",
    "load_profile_sources",
    "load_pipeline_id_registry",
    "load_pipeline_id_registries",
    "load_profiles",
    "majority_vote",
    "max_iters",
    "media_usage_from_hook_metadata",
    "merge_profile_layers",
    "no_improvement",
    "NullExecutorHooks",
    "no_op_content_validator",
    "normalize_schema_version",
    "normalize_usage",
    "normalize_usage_extraction",
    "native_runtime_enabled",
    "register_media_content_validators",
    "parse_agent_spec_shape",
    "parse_llm_json",
    "parse_profiles_doc",
    "persist_native_cursor",
    "persist_resume_cursor",
    "persist_composite_resume_cursor",
    "plateau",
    "project_graph",
    "prove_invocation_capabilities",
    "prove_stage_required_capabilities",
    "read_manifest",
    "read_native_cursor",
    "read_composite_resume_cursor",
    "read_resume_cursor",
    "reduce_contract_results",
    "register_schema",
    "resolve_default_profile",
    "resolve_registry_runtime_identity",
    "resolve_billing_route",
    "RESUME_CURSOR_FILENAME",
    "RESUME_REVERIFY_DECLARATION_KEY",
    "RESUME_REVERIFY_EXTENSION_KEY",
    "ResumeReverifyDeclaration",
    "ResumeReverifyResult",
    "parse_resume_reverify_declaration",
    "resolve_resume_reverify_artifact",
    "reverify_resume_produces",
    "ModelAdapterNotImplementedError",
    "get_default_adapter_registry",
    "get_pricing",
    "get_pricing_entry",
    "resolve_step_io_policy",
    "record_step_io_self_validation_marker",
    "resolve_seam_from_binding_map",
    "require_native_runtime",
    "run_pipeline",
    "run_pipeline_resume",
    "run_native_pipeline",
    "schema_version_for",
    "select",
    "select_audit_mode",
    "threshold",
    "threshold_reached",
    "top_1",
    "top_k",
    "unwrap_step_invocation_result",
    "upgrade_graph_cursor_to_native",
    "validate_contract_result",
    "validate_declared_stage_keys",
    "validate_payload_against_schema",
    "WriteRef",
    "weighted_vote",
    "policy_for_envelope",
    "write_step_io_policy",
    "STEP_IO_POLICY_FILENAME",
    "AgentSpecShape",
    "aggregate_panel_join",
    "StepIOViolationRecord",
    "append_violation_record",
    "emit_decision_telemetry",
    "read_violation_records",
    "TELEMETRY_FILENAME",
]
