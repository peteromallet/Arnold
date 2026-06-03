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

Sub-modules:

* ``types``           — core dataclasses and structural types.
* ``state``           — ``StateDelta`` (loose multi-patch container) and helpers.
* ``contracts``       — ContractLedger and legal-coercion table.
* ``pattern_select``  — tournament selection primitives (top_1, top_k, threshold).
* ``pattern_stops``   — loop-stop predicates (plateau, max_iters, etc.).
* ``pattern_types``   — PromoteFn / JoinFn type aliases.

All public names are re-exported here.  Import from ``arnold.pipeline``:

    from arnold.pipeline import Pipeline, Stage, StepContext, StateDelta

No Megaplan re-exports appear here; this is the neutral surface.
"""

from arnold.pipeline.builder import PipelineBuilder
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
from arnold.pipeline.registry import PipelineRegistry
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    CONTENT_TYPES,
    ContentTypeRegistry,
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Port,
    PortRef,
    ReduceResult,
    RoutingKey,
    SelectionResult,
    Stage,
    Step,
    StepContext,
    StepResult,
    register_schema,
)

__all__ = [
    "CONTENT_TYPES",
    "ContentTypeRegistry",
    "ContractLedger",
    "DEFAULT_PARALLEL_SAFE",
    "Edge",
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
    "Port",
    "PortRef",
    "PromoteFn",
    "ReduceResult",
    "RoutingKey",
    "SelectionResult",
    "Stage",
    "StateDelta",
    "Step",
    "StepContext",
    "StepResult",
    "TrustTier",
    "apply_delta",
    "classify",
    "coerce",
    "derive_tenant_id",
    "is_legal_coercion",
    "legal_coercions",
    "majority_vote",
    "max_iters",
    "no_improvement",
    "plateau",
    "read_manifest",
    "register_schema",
    "run_pipeline",
    "select",
    "threshold_reached",
    "threshold",
    "top_1",
    "top_k",
    "weighted_vote",
]
