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
* ``PortRef``           — reference to a named port.
* ``RoutingKey``        — content-type–qualified routing key.
* ``ContentTypeRegistry`` — map content-type names → schema digests.
* ``ReduceResult``      — structured output of reduce-kind step.
* ``SelectionResult``   — structured output of selection/tournament reduce.
* ``ContractResult``    — single shared seam primitive (Step-IO + Evidence-First).
* ``ContractStatus``    — 3-status discriminant for ``ContractResult``.
* ``Suspension``        — typed interaction envelope (``status == SUSPENDED``).
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
from arnold.pipeline.contracts import ContractLedger, coerce, is_legal_coercion, legal_coercions
from arnold.pipeline.discovery import Manifest, ManifestError, TrustTier, classify, derive_tenant_id, read_manifest
from arnold.pipeline.executor import (
    DEFAULT_PARALLEL_SAFE,
    ParallelSafePredicate,
    run_pipeline,
)
from arnold.pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipeline.pattern_select import select, threshold, top_1, top_k
from arnold.pipeline.pattern_stops import LoopState, max_iters, no_improvement, plateau, threshold_reached
from arnold.pipeline.pattern_types import JoinFn, PromoteFn
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
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    CONTENT_TYPES,
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContentTypeRegistry,
    ContractResult,
    ContractStatus,
    Edge,
    EvidenceArtifactRef,
    Freshness,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Port,
    PortRef,
    Provenance,
    ReduceResult,
    RoutingKey,
    SelectionResult,
    Stage,
    Step,
    StepContext,
    StepResult,
    Suspension,
    register_schema,
)

__all__ = [
    "AcceptedVersionRange",
    "AuditMode",
    "AuditPolicyHook",
    "CONTENT_TYPES",
    "CONTRACT_RESULT_SCHEMA_VERSION",
    "ContentValidator",
    "ContentValidatorRegistry",
    "ContentTypeRegistry",
    "ContractLedger",
    "ContractResult",
    "ContractSchemaRegistry",
    "ContractStatus",
    "DEFAULT_PARALLEL_SAFE",
    "Edge",
    "EvidenceArtifactRef",
    "Freshness",
    "JoinFn",
    "LoopState",
    "Manifest",
    "ManifestError",
    "ParallelSafePredicate",
    "ParallelStage",
    "Pipeline",
    "PipelineBuilder",
    "PipelineRegistry",
    "PipelineVerdict",
    "ProfileLoadError",
    "Port",
    "PortRef",
    "PromoteFn",
    "Provenance",
    "ReduceResult",
    "RoutingKey",
    "SelectionResult",
    "Stage",
    "StateDelta",
    "Step",
    "StepContext",
    "StepResult",
    "Suspension",
    "SchemaRegistryError",
    "TrustTier",
    "ValidationDiagnostic",
    "ValidationResult",
    "apply_delta",
    "accepts_version",
    "canonical_schema_bytes",
    "canonical_schema_json",
    "classify",
    "coerce",
    "derive_tenant_id",
    "is_legal_coercion",
    "legal_coercions",
    "load_profile_metadata",
    "load_profile_sources",
    "load_profiles",
    "majority_vote",
    "max_iters",
    "merge_profile_layers",
    "no_improvement",
    "no_op_content_validator",
    "normalize_schema_version",
    "parse_agent_spec_shape",
    "parse_profiles_doc",
    "plateau",
    "read_manifest",
    "register_schema",
    "resolve_default_profile",
    "run_pipeline",
    "schema_version_for",
    "select",
    "select_audit_mode",
    "threshold",
    "threshold_reached",
    "top_1",
    "top_k",
    "validate_contract_result",
    "validate_declared_stage_keys",
    "validate_payload_against_schema",
    "weighted_vote",
    "AgentSpecShape",
]
