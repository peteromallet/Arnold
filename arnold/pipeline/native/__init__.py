"""Native runtime package for Arnold pipelines."""

from __future__ import annotations

from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    persist_native_cursor,
    read_native_cursor,
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
    is_decision,
    is_phase,
    is_pipeline,
    parallel,
    phase,
    pipeline,
)
from arnold.pipeline.native.flags import native_runtime_enabled
from arnold.pipeline.native.graph_projection import project_graph
from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import (
    NativeDecision,
    NativeInstruction,
    NativeLoopGuard,
    NativePhase,
    NativePipeline,
    NativeProgram,
    ParallelInstruction,
)
from arnold.pipeline.native.runtime import (
    NativeExecutionResult,
    NativeRuntimeError,
    run_native_pipeline,
)
from arnold.pipeline.native.trace import NativeTraceHooks

__all__ = [
    "NATIVE_CURSOR_VERSION",
    "NativeCompileError",
    "NativeDecision",
    "NativeExecutionResult",
    "NativeInstruction",
    "NativeLoopGuard",
    "NativePhase",
    "NativePipeline",
    "NativeProgram",
    "NativeRuntimeDisabledError",
    "NativeRuntimeError",
    "NativeRuntimeHooks",
    "NativeTraceHooks",
    "NullNativeRuntimeHooks",
    "ParallelInstruction",
    "compile_pipeline",
    "decision",
    "get_decision_meta",
    "get_phase_meta",
    "get_pipeline_meta",
    "is_decision",
    "is_phase",
    "is_pipeline",
    "native_runtime_enabled",
    "parallel",
    "persist_native_cursor",
    "phase",
    "pipeline",
    "project_graph",
    "read_native_cursor",
    "require_native_runtime",
    "run_native_pipeline",
]
