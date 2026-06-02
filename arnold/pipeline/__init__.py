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

Sub-modules:

* ``types``  — core dataclasses and structural types.
* ``state``  — ``StateDelta`` (loose multi-patch container) and helpers.

All public names are re-exported here.  Import from ``arnold.pipeline``:

    from arnold.pipeline import Pipeline, Stage, StepContext, StateDelta

No Megaplan re-exports appear here; this is the neutral surface.
"""

from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    Step,
    StepContext,
    StepResult,
)

__all__ = [
    "Edge",
    "ParallelStage",
    "Pipeline",
    "PipelineVerdict",
    "Stage",
    "StateDelta",
    "Step",
    "StepContext",
    "StepResult",
    "apply_delta",
]
