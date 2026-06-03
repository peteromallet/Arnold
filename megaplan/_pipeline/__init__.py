"""Deprecated re-export bridge for megaplan._pipeline.

The pipeline primitives have moved to :mod:`arnold.pipeline`.
Import from there directly.  This module exists only for backward
compatibility and will be removed in a future release.

This bridge preserves the megaplan DAG types (Edge, Pipeline, Stage,
StepContext, StepResult, PipelineVerdict, Step) with their megaplan-
specific fields (plan_dir, profile, budget, recommendation, etc.) and
re-exports neutral carriers (Port, PortRef, RoutingKey, etc.) from
arnold.pipeline.types.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline is deprecated; use arnold.pipeline instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Megaplan DAG types (keep local — carry extra fields) ──────────────
from megaplan._pipeline.types import (  # noqa: E402
    Edge,
    Overlay,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    Step,
    StepContext,
    StepResult,
    StepMixin,
    StepMixinProperty,
)

# ── Neutral carriers re-exported from arnold.pipeline.types ───────────
from arnold.pipeline.types import (  # noqa: E402
    ContentRoutingKey,
    ContentTypeRegistry,
    Port,
    PortRef,
    ReduceResult,
    RoutingKey,
    RoutingKeyKind,
    SelectionResult,
    _canonical_json_dumps,
    register_schema,
)

# ── Neutral feature flags ─────────────────────────────────────────────
from arnold.pipeline.flags import typed_ports_on  # noqa: E402
from arnold.pipeline.feature_flags import arnold_unified_dispatch_on  # noqa: E402

# ── State delta ───────────────────────────────────────────────────────
from arnold.pipeline.state import StateDelta, apply_delta  # noqa: E402

# ── judge_manifest / judge_manifest_discovery (may not exist) ─────────
try:
    from megaplan._pipeline.judge_manifest import (  # noqa: E402
        EVALUAND_RECORD_CONTENT_TYPE,
        JUDGE_MANIFEST_SCHEMA,
        JudgeManifestPort,
        JudgePieceManifest,
        compute_judge_version,
        compute_piece_version,
        compute_rubric_hash,
        dump_judge_manifest,
        load_judge_manifest,
        make_judge_manifest,
    )
except ImportError:
    EVALUAND_RECORD_CONTENT_TYPE = None  # type: ignore[assignment]
    JUDGE_MANIFEST_SCHEMA = None  # type: ignore[assignment]

try:
    from megaplan._pipeline.judge_manifest_discovery import (  # noqa: E402
        JudgeManifestDiagnostics,
        JudgeManifestMatch,
        discover_judge_manifests,
        find_judge_manifest,
        manifest_to_binder_ports,
        validate_manifest_bindings,
        validate_judge_manifest,
    )
except ImportError:
    pass

__all__ = [
    # Megaplan DAG types
    "Edge",
    "Overlay",
    "ParallelStage",
    "Pipeline",
    "PipelineVerdict",
    "Stage",
    "Step",
    "StepContext",
    "StepResult",
    "StepMixin",
    "StepMixinProperty",
    # Neutral carriers
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
    # Flags
    "typed_ports_on",
    "arnold_unified_dispatch_on",
    # State
    "StateDelta",
    "apply_delta",
]
