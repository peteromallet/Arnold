"""Arnold pipeline primitives — neutral, opinion-free data shapes.

This sub-package holds the pure-dataclass / Protocol types that define
a pipeline without reference to Megaplan-specific semantics:

* ``Pipeline``          — named DAG of stages and edges.
* ``Stage``             — a set of steps gated by a pre-condition.
* ``ParallelStage``     — a fan-out stage whose steps run concurrently.
* ``Edge``              — materialised dependency between two stages.
* ``Step``              — Protocol for executable units.
* ``StepContext``       — runtime context passed to every step.
* ``StepResult``        — result of executing a single step.
* ``PipelineVerdict``   — recommendation / override for pipeline control flow.
* ``StateDelta``        — ordered multi-patch container.
* ``apply_delta``       — apply StateDelta patches to a state value.
* ``Port``              — a named typed port with content-type and taint.
* ``PortRef``           — a reference to a named port with content type.
* ``RoutingKey``        — dispatch routing key with ``name`` and ``kind``.
* ``RoutingKeyKind``    — literal kind values for ``RoutingKey``.
* ``ContentRoutingKey`` — content-type–qualified routing key.
* ``ContentTypeRegistry`` — map content-type names → schema SHA-256 digests.
* ``ReduceResult``      — structured output of a reduce-kind step.
* ``SelectionResult``   — structured output of a selection/tournament reduce.

Sub-modules:

* ``types``           — core dataclasses and structural types.
* ``state``           — ``StateDelta`` (loose multi-patch container) and helpers.
* ``flags``           — neutral feature flags (always default-off).
* ``feature_flags``   — feature flags for Arnold pipeline unification.
* ``contracts``       — ContractLedger and typed-port binding machinery.
* ``envelope``        — RunEnvelope and subprocess envelope handshake.
* ``registry``        — PipelineRegistry and pipeline discovery.
* ``subloop``         — SubloopStep primitive for nested sub-pipelines.
* ``step_helpers``    — shared helpers for Step implementations.
* ``receipt``         — ReceiptDecorator for step invocation receipts.
* ``faults``          — FaultRegistry for tracking findings across iterations.
* ``patterns``        — composed topology, join, and dynamic pattern functions.
* ``pattern_types``   — PromoteFn / JoinFn type aliases.
* ``pattern_joins``   — majority_vote, weighted_vote join functions.
* ``pattern_dynamic`` — dynamic fanout and iteration primitives.
* ``pattern_topology`` — neutral topology builders (panel_parallel, etc.).
* ``discovery``       — manifest-first, non-executing pipeline discovery.

All public names are re-exported here.  Import from ``arnold.pipeline``:

    from arnold.pipeline import Pipeline, Stage, StepContext, StateDelta

No Megaplan re-exports appear here; this is the neutral surface.
"""

# ── Core DAG types ────────────────────────────────────────────────────
from arnold.pipeline.types import (
    ContentRoutingKey,
    ContentTypeRegistry,
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Port,
    PortRef,
    ReduceResult,
    RoutingKey,
    RoutingKeyKind,
    SelectionResult,
    Stage,
    Step,
    StepContext,
    StepResult,
    _canonical_json_dumps,
    register_schema,
)

# ── State delta ───────────────────────────────────────────────────────
from arnold.pipeline.state import StateDelta, apply_delta

# ── Executor ──────────────────────────────────────────────────────────
from arnold.pipeline.executor import run_pipeline

# ── Feature flags ─────────────────────────────────────────────────────
from arnold.pipeline.flags import typed_ports_on
from arnold.pipeline.feature_flags import arnold_unified_dispatch_on

# ── Contracts and envelope ────────────────────────────────────────────
from arnold.pipeline.contracts import (
    BindResult,
    ContractLedger,
    PortBindError,
    RepairGradient,
    bind,
    coerce,
    is_legal_coercion,
)
from arnold.pipeline.envelope import (
    EMPTY_ENVELOPE,
    ENVELOPE_ENV_VAR,
    ENVELOPE_IN_FILENAME,
    ENVELOPE_OUT_FILENAME,
    ENVELOPE_STDERR_TAG,
    EnvelopeDroppedError,
    LeaseIdConflict,
    RunEnvelope,
    consume_envelope_in,
    current_envelope,
    format_envelope_stderr_tag,
    make_envelope,
    parse_envelope_stderr_tag,
    read_envelope_out,
    write_envelope_in,
    write_envelope_out,
)

# ── Registry ──────────────────────────────────────────────────────────
from arnold.pipeline.registry import (
    CANONICAL_BUILTIN_PIPELINE,
    Disposition,
    PipelineBuilder,
    PipelineRegistry,
    canonical_pipeline_name,
    control_status_result_from_operation_result,
    describe_pipeline,
    discover_python_pipelines,
    dispatch_operation_for,
    get_pipeline,
    operation_registry_for,
    override_catalog_for,
    phase_tuple_from_operation_result,
    pipeline_metadata,
    read_pipeline_skill_md,
    register_pipeline,
    registered_pipelines,
    resume_result_from_operation_result,
    run_pipeline_by_name,
    scan_python_pipelines,
    supported_operations_for,
)

# ── Subloop ───────────────────────────────────────────────────────────
from arnold.pipeline.subloop import SubloopStep

# ── Step helpers ──────────────────────────────────────────────────────
from arnold.pipeline.step_helpers import (
    interpolate_inputs,
    latest_artifact,
    next_version,
    resolve_inputs,
    resolve_prompt_text,
)

# ── Receipt ───────────────────────────────────────────────────────────
from arnold.pipeline.receipt import ReceiptDecorator

# ── Faults ────────────────────────────────────────────────────────────
from arnold.pipeline.faults import (
    Fault,
    FaultIterationEntry,
    FaultRegistry,
    FaultSeverity,
    FaultStatus,
)

# ── Patterns ──────────────────────────────────────────────────────────
from arnold.pipeline.pattern_types import JoinFn, PromoteFn
from arnold.pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipeline.pattern_topology import (
    alternating_turns,
    iterate_until,
    panel_parallel,
    subpipeline_call,
)
from arnold.pipeline.pattern_dynamic import (
    dynamic_fanout,
    iterate_until_consensus,
    paired_round,
    panel_from_artifact,
)
from arnold.pipeline.patterns import (
    arnold_api_version,
    get_node_metadata,
    iter_node_metadata,
)

# ── Discovery ─────────────────────────────────────────────────────────
from arnold.pipeline.discovery import (  # isort: skip
    BLESSED_ALLOWLIST,
    KNOWN_CAPABILITIES,
    Manifest,
    ManifestError,
    TrustTier,
    check_capabilities,
    classify,
    read_manifest,
)

__all__ = [
    # ── Core DAG types from types.py ──
    "Edge",
    "ParallelStage",
    "Pipeline",
    "PipelineVerdict",
    "Stage",
    "Step",
    "StepContext",
    "StepResult",
    # ── Port / routing types ──
    "Port",
    "PortRef",
    "ContentRoutingKey",
    "ContentTypeRegistry",
    "ReduceResult",
    "SelectionResult",
    "RoutingKey",
    "RoutingKeyKind",
    "_canonical_json_dumps",
    "register_schema",
    # ── State ──
    "StateDelta",
    "apply_delta",
    # ── Executor ──
    "run_pipeline",
    # ── Feature flags ──
    "typed_ports_on",
    "arnold_unified_dispatch_on",
    # ── Contracts ──
    "ContractLedger",
    "PortBindError",
    "BindResult",
    "RepairGradient",
    "bind",
    "coerce",
    "is_legal_coercion",
    # ── Envelope ──
    "RunEnvelope",
    "EMPTY_ENVELOPE",
    "ENVELOPE_ENV_VAR",
    "ENVELOPE_IN_FILENAME",
    "ENVELOPE_OUT_FILENAME",
    "ENVELOPE_STDERR_TAG",
    "EnvelopeDroppedError",
    "LeaseIdConflict",
    "consume_envelope_in",
    "current_envelope",
    "format_envelope_stderr_tag",
    "make_envelope",
    "parse_envelope_stderr_tag",
    "read_envelope_out",
    "write_envelope_in",
    "write_envelope_out",
    # ── Registry ──
    "CANONICAL_BUILTIN_PIPELINE",
    "Disposition",
    "PipelineBuilder",
    "PipelineRegistry",
    "canonical_pipeline_name",
    "control_status_result_from_operation_result",
    "describe_pipeline",
    "discover_python_pipelines",
    "dispatch_operation_for",
    "get_pipeline",
    "operation_registry_for",
    "override_catalog_for",
    "phase_tuple_from_operation_result",
    "pipeline_metadata",
    "read_pipeline_skill_md",
    "register_pipeline",
    "registered_pipelines",
    "resume_result_from_operation_result",
    "run_pipeline_by_name",
    "scan_python_pipelines",
    "supported_operations_for",
    # ── Subloop ──
    "SubloopStep",
    # ── Step helpers ──
    "interpolate_inputs",
    "latest_artifact",
    "next_version",
    "resolve_inputs",
    "resolve_prompt_text",
    # ── Receipt ──
    "ReceiptDecorator",
    # ── Faults ──
    "Fault",
    "FaultIterationEntry",
    "FaultRegistry",
    "FaultSeverity",
    "FaultStatus",
    # ── Pattern types ──
    "PromoteFn",
    "JoinFn",
    # ── Pattern joins ──
    "majority_vote",
    "weighted_vote",
    # ── Pattern topology ──
    "alternating_turns",
    "iterate_until",
    "panel_parallel",
    "subpipeline_call",
    # ── Pattern dynamic ──
    "dynamic_fanout",
    "iterate_until_consensus",
    "paired_round",
    "panel_from_artifact",
    # ── Patterns (node metadata) ──
    "arnold_api_version",
    "get_node_metadata",
    "iter_node_metadata",
    # ── Discovery ──
    "Manifest",
    "ManifestError",
    "read_manifest",
    "TrustTier",
    "BLESSED_ALLOWLIST",
    "KNOWN_CAPABILITIES",
    "classify",
    "check_capabilities",
]
