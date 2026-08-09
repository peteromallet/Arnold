"""Native runtime package for Arnold pipelines.

Native execution is canonical by default.  The public surface here focuses on
native program compilation, graph projection, runtime execution, and explicit
legacy fallback helpers.

Ownership:
    Native ``.pypeline`` modules and named native subworkflows own the
    source-visible product topology.  Boundary contracts and boundary
    receipts declare and check durable effects only — they do not define,
    route, or own workflow topology.
"""

from __future__ import annotations

from arnold.pipeline.native.checkpoint import (
    CursorUpgradeError,
    CursorUpgradeResult,
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    persist_native_cursor,
    read_native_cursor,
    upgrade_graph_cursor_to_native,
)
from arnold.pipeline.native.compiler import (
    NativeCompileError,
    compile_pipeline,
)
from arnold.pipeline.native.context import (
    NativeRuntimeDisabledError,
    require_native_runtime,
)
from arnold.pipeline.native.effect_taxonomy import (
    EffectClass,
    Operation,
    derive_idempotency_key,
    is_valid_effect_class,
    is_valid_operation,
)
from arnold.pipeline.native.decorators import (
    decision,
    get_decision_meta,
    get_phase_meta,
    get_pipeline_meta,
    get_step_meta,
    get_workflow_meta,
    is_decision,
    is_phase,
    is_pipeline,
    is_step,
    is_workflow,
    native_panel,
    parallel,
    parallel_map,
    phase,
    pipeline,
    step,
    workflow,
)
from arnold.pipeline.native.flags import force_legacy_runtime, native_runtime_enabled
from arnold.pipeline.native.graph_projection import derive_topology, project_graph
from arnold.pipeline.native.hooks import (
    EffectLedgerHooks,
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import (
    CompositionEdge,
    CompositionNode,
    CompositionNodeKind,
    DerivedGraph,
    DynamicMapMetadata,
    NativeCompositionGraph,
    NativeDecision,
    NativeInstruction,
    NativeInvocable,
    NativeLoopGuard,
    NativePhase,
    NativePipeline,
    NativeProgram,
    NativeTopology,
    PATH_DELIMITER,
    ParallelInstruction,
    ParallelMapInstruction,
    PathSegment,
    ROOT_PATH,
    TopologyEdge,
    TopologyNode,
)
from arnold.pipeline.native.runtime import (
    NativeExecutionResult,
    NativeRuntimeError,
    run_native_pipeline,
)
from arnold.pipeline.native.reconcile import (
    ACTION_TABLE,
    ReconcileActionTableEntry,
    ReconcileDecision,
    ReconcileMetadata,
    action_entry,
    reconcile_file_write,
    reconcile_git_branch_create,
    reconcile_git_commit,
    reconcile_git_worktree,
)
from arnold.pipeline.native.start_from_path import start_from_trace
from arnold.pipeline.native.audit import AuditHooks, resolved_versions_by_stable_id_for_run
from arnold.pipeline.native.pack_index import (
    DependentRecord,
    PackReverseIndex,
)
from arnold.pipeline.native.pack_metadata import (
    DependencySpec,
    ExportEntry,
    LockfileEntry,
    PackLockfile,
    PackManifest,
    compute_interface_hash,
)
from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    LegacyArtifactBinding,
    NativePersistenceBackend,
    NativePersistenceScope,
    OrderedPersistenceRow,
    ResolvedResumeSurface,
    ResumeSurfaceObservation,
    TypedResumeMetadata,
    bind_legacy_artifact_root,
    legacy_scope_for_artifact_root,
)
from arnold.pipeline.native.postgres_persistence import PostgresNativePersistenceBackend
from arnold.pipeline.native.pack_diff import (
    DiffEntry,
    DiffReport,
    diff_pack_exports,
    diff_pack_manifests,
)
from arnold.pipeline.native.pack_registry import (
    PackRegistry,
    RegisteredPackExport,
    ResolvedPackExport,
)
from arnold.pipeline.native.pack_validation import (
    PACK_CLOSURE_MAX_DEPTH,
    PackClosureValidationError,
    validate_shared_pack_closure,
)
from arnold.pipeline.native.pack_upgrade import (
    PackUpgradeError,
    PackUpgradePlan,
    TransitiveImpact,
    apply_pack_repin,
    plan_pack_repin,
)
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold.pipeline.native.validator import (
    RoutingPurityDiagnostic,
    RoutingPurityReport,
    validate_decision_body,
    validate_pipeline_purity,
)

__all__ = [
    "ACTION_TABLE",
    "AuditHooks",
    "resolved_versions_by_stable_id_for_run",
    "DependencySpec",
    "EffectClass",
    "EffectLedgerHooks",
    "ExportEntry",
    "FileNativePersistenceBackend",
    "LockfileEntry",
    "LegacyArtifactBinding",
    "NATIVE_CURSOR_VERSION",
    "NativeCompileError",
    "NativeCursorCorruptError",
    "NativePersistenceBackend",
    "NativePersistenceScope",
    "CursorUpgradeError",
    "CursorUpgradeResult",
    "CompositionEdge",
    "CompositionNode",
    "CompositionNodeKind",
    "DiffEntry",
    "DiffReport",
    "DependentRecord",
    "DerivedGraph",
    "DynamicMapMetadata",
    "NativeCompositionGraph",
    "NativeDecision",
    "NativeExecutionResult",
    "NativeInstruction",
    "NativeInvocable",
    "NativeLoopGuard",
    "NativePhase",
    "NativePipeline",
    "NativeProgram",
    "NativeRuntimeDisabledError",
    "NativeRuntimeError",
    "NativeRuntimeHooks",
    "NativeTopology",
    "NativeTraceHooks",
    "PATH_DELIMITER",
    "PackLockfile",
    "PackManifest",
    "PackReverseIndex",
    "PackRegistry",
    "PostgresNativePersistenceBackend",
    "PackUpgradeError",
    "PackUpgradePlan",
    "PACK_CLOSURE_MAX_DEPTH",
    "ParallelInstruction",
    "ParallelMapInstruction",
    "PackClosureValidationError",
    "PathSegment",
    "ROOT_PATH",
    "RegisteredPackExport",
    "ResolvedPackExport",
    "ResolvedResumeSurface",
    "ResumeSurfaceObservation",
    "RoutingPurityDiagnostic",
    "RoutingPurityReport",
    "ReconcileActionTableEntry",
    "ReconcileDecision",
    "ReconcileMetadata",
    "NullNativeRuntimeHooks",
    "Operation",
    "OrderedPersistenceRow",
    "TopologyEdge",
    "TopologyNode",
    "TransitiveImpact",
    "TypedResumeMetadata",
    "action_entry",
    "apply_pack_repin",
    "bind_legacy_artifact_root",
    "compile_pipeline",
    "compute_interface_hash",
    "decision",
    "derive_idempotency_key",
    "derive_topology",
    "diff_pack_exports",
    "diff_pack_manifests",
    "force_legacy_runtime",
    "get_decision_meta",
    "get_phase_meta",
    "get_pipeline_meta",
    "get_step_meta",
    "get_workflow_meta",
    "is_decision",
    "is_phase",
    "is_pipeline",
    "is_step",
    "is_valid_effect_class",
    "is_valid_operation",
    "legacy_scope_for_artifact_root",
    "is_workflow",
    "native_runtime_enabled",
    "native_panel",
    "parallel",
    "parallel_map",
    "persist_native_cursor",
    "phase",
    "pipeline",
    "plan_pack_repin",
    "project_graph",
    "read_native_cursor",
    "reconcile_file_write",
    "reconcile_git_branch_create",
    "reconcile_git_commit",
    "reconcile_git_worktree",
    "require_native_runtime",
    "run_native_pipeline",
    "start_from_trace",
    "step",
    "upgrade_graph_cursor_to_native",
    "validate_shared_pack_closure",
    "validate_decision_body",
    "validate_pipeline_purity",
    "workflow",
]
