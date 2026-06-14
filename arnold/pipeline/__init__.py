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
* ``media_cost``      — ``MediaUsage``, ``MediaPricingEntry``, ``compute_media_cost``,
  ``media_usage_from_hook_metadata`` (neutral).
* ``token_cost``      — ``PricingEntry``, ``estimate_usage_cost``,
  ``normalize_usage`` (neutral).
* ``state``           — ``StateDelta`` (loose multi-patch container) and helpers.
* ``contracts``       — ContractLedger and legal-coercion table.
* ``pattern_select``  — tournament selection primitives (top_1, top_k, threshold).
* ``pattern_stops``   — loop-stop predicates (plateau, max_iters, etc.).
* ``pattern_types``   — PromoteFn / JoinFn type aliases.
* ``contract_validation`` — pure structural validation of ContractResult.payload.
* ``schema_registry`` — neutral file-backed schema registry with atomic writes.
* ``content_validation`` — content-type keyed validation hooks for blob metadata.
* ``audit_policy``    — deterministic audit-mode selection for size-threshold seams.

All public names are re-exported here.  Import from ``arnold.pipeline``:

    from arnold.pipeline import Pipeline, Stage, StepContext, StateDelta

No Megaplan re-exports appear here; this is the neutral surface.
"""

from arnold.pipeline.audit_policy import AuditMode, AuditPolicyHook, select_audit_mode
from arnold.pipeline.builder import PipelineBuilder
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
from arnold.pipeline.media_cost import (
    DEFAULT_MEDIA_PRICING,
    MediaPricingEntry,
    MediaUsage,
    UsageExtraction,
    compute_media_cost,
    media_usage_from_hook_metadata,
    normalize_usage_extraction,
)
from arnold.pipeline.token_cost import (
    DEFAULT_PRICING,
    BillingRoute,
    PricingEntry,
    estimate_cost_usd,
    estimate_usage_cost,
    get_pricing,
    get_pricing_entry,
    has_known_pricing,
    normalize_usage,
    resolve_billing_route,
)
from arnold.pipeline.discovery import Manifest, ManifestError, TrustGrade, classify, derive_tenant_id, read_manifest
from arnold.pipeline.executor import (
    DEFAULT_PARALLEL_SAFE,
    MediaCostAccumulator,
    ParallelSafePredicate,
    run_pipeline,
    run_pipeline_resume,
)
from arnold.pipeline.hooks import ExecutorHooks, NullExecutorHooks, account_media_cost_from_result
from arnold.pipeline.model_resource_capabilities import (
    CAPABILITY_ALIASES,
    MODEL_RESOURCE_CAPABILITIES,
    CapabilityEvidence,
    CapabilityProof,
    prove_invocation_capabilities,
    prove_stage_required_capabilities,
)
from arnold.pipeline.llm_json import parse_llm_json
from arnold.pipeline.pattern_joins import aggregate_panel_join, majority_vote, weighted_vote
from arnold.pipeline.pattern_select import select, threshold, top_1, top_k
from arnold.pipeline.pattern_stops import LoopState, max_iters, no_improvement, plateau, threshold_reached
from arnold.pipeline.pattern_types import JoinFn, PromoteFn
from arnold.pipeline.pipeline_id_registry import (
    PipelineIdRegistry,
    PipelineIdRegistryError,
    load_pipeline_id_registry,
    load_pipeline_id_registries,
)
from arnold.pipeline.profiles import (
    AgentSpecShape,
    ProfileLoadError,
    load_profile_metadata,
    load_profile_sources,
    load_profiles,
    merge_profile_layers,
    parse_agent_spec_shape,
    parse_profiles_doc,
    resolve_default_profile,
    validate_declared_stage_keys,
)
from arnold.pipeline.registry import PipelineRegistry
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
from arnold.pipeline.step_invocation import (
    ModelAdapterNotImplementedError,
    StepInvocation,
    StepInvocationAdapter,
    StepInvocationAdapterRegistry,
    StepInvocationResult,
    get_default_adapter_registry,
    unwrap_step_invocation_result,
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
from arnold.pipeline.resume import persist_resume_cursor
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    CONTENT_TYPES,
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContentTypeRegistry,
    ContractResult,
    ContractStatus,
    Edge,
    EvidenceArtifactRef,
    EvidenceStatus,
    Freshness,
    HumanSuspension,
    ParallelStage,
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
    Stage,
    Step,
    StepContext,
    StepResult,
    Suspension,
    TrustClass,
    register_schema,
)

__all__ = [
    "AcceptedVersionRange",
    "account_media_cost_from_result",
    "AuditMode",
    "AuditPolicyHook",
    "BillingRoute",
    "CAPABILITY_ALIASES",
    "CONTENT_TYPES",
    "CONTRACT_RESULT_SCHEMA_VERSION",
    "ContentValidator",
    "ContentValidatorRegistry",
    "ContentTypeRegistry",
    "ContractLedger",
    "ContractResult",
    "ContractSchemaRegistry",
    "ContractStatus",
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
    "ReduceResult",
    "ReadRef",
    "RoutingKey",
    "ReducePolicy",
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
    "parse_agent_spec_shape",
    "parse_llm_json",
    "parse_profiles_doc",
    "persist_resume_cursor",
    "plateau",
    "prove_invocation_capabilities",
    "prove_stage_required_capabilities",
    "read_manifest",
    "reduce_contract_results",
    "register_schema",
    "resolve_default_profile",
    "resolve_billing_route",
    "ModelAdapterNotImplementedError",
    "get_default_adapter_registry",
    "get_pricing",
    "get_pricing_entry",
    "resolve_step_io_policy",
    "record_step_io_self_validation_marker",
    "resolve_seam_from_binding_map",
    "run_pipeline",
    "run_pipeline_resume",
    "schema_version_for",
    "select",
    "select_audit_mode",
    "threshold",
    "threshold_reached",
    "top_1",
    "top_k",
    "unwrap_step_invocation_result",
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
