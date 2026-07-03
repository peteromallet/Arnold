"""Native runtime package for Arnold pipelines.

Native execution is canonical by default.  The public surface here focuses on
native program compilation, graph projection, runtime execution, and explicit
legacy fallback helpers.
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
from arnold.pipeline.native.graph_projection import project_graph
from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import (
    CompositionEdge,
    CompositionNode,
    CompositionNodeKind,
    NativeCompositionGraph,
    NativeDecision,
    NativeInstruction,
    NativeInvocable,
    NativeLoopGuard,
    NativePhase,
    NativePipeline,
    NativeProgram,
    ParallelInstruction,
    ParallelMapInstruction,
)
from arnold.pipeline.native.runtime import (
    NativeExecutionResult,
    NativeRuntimeError,
    run_native_pipeline,
)
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold.pipeline.native.validator import (
    RoutingPurityDiagnostic,
    RoutingPurityReport,
    validate_decision_body,
    validate_pipeline_purity,
)

__all__ = [
    "NATIVE_CURSOR_VERSION",
    "NativeCompileError",
    "NativeCursorCorruptError",
    "CursorUpgradeError",
    "CursorUpgradeResult",
    "CompositionEdge",
    "CompositionNode",
    "CompositionNodeKind",
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
    "NativeTraceHooks",
    "RoutingPurityDiagnostic",
    "RoutingPurityReport",
    "NullNativeRuntimeHooks",
    "ParallelInstruction",
    "ParallelMapInstruction",
    "compile_pipeline",
    "decision",
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
    "is_workflow",
    "native_runtime_enabled",
    "native_panel",
    "parallel",
    "parallel_map",
    "persist_native_cursor",
    "phase",
    "pipeline",
    "project_graph",
    "read_native_cursor",
    "require_native_runtime",
    "run_native_pipeline",
    "step",
    "upgrade_graph_cursor_to_native",
    "validate_decision_body",
    "validate_pipeline_purity",
    "workflow",
]
