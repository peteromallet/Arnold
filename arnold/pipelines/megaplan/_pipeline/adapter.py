"""Megaplan → canonical pipeline adapter (Step 4 / T5).

Thin conversion layer that bridges the two type hierarchies without
requiring either side to know about the other at import time.

Canonical pass-through schema for ``hook_extensions`` keys
----------------------------------------------------------

When a Megaplan :class:`~arnold.pipelines.megaplan._pipeline.types.StepContext`
is converted via :func:`to_canonical_step_context`, the following keys are
packed into ``ctx.hook_extensions``:

* ``plan_dir`` — ``Path`` → ``str`` (canonical ``artifact_root``).
* ``profile`` — opaque profile object (passed through unchanged).
* ``budget`` — opaque budget object (passed through unchanged).
* ``envelope`` — ``RunEnvelope`` instance (passed through unchanged).

:func:`from_canonical_step_context` reconstructs the Megaplan context and
**raises** :class:`KeyError` if any of these four keys is missing — silent
miss would corrupt downstream Megaplan code that destructures the rich ctx.

Envelope-type bridge
--------------------

Any caller that passes a Megaplan ``RunEnvelope`` to the canonical
``run_pipeline`` is responsible for the result envelope also being a
``RunEnvelope``.  The canonical executor treats envelopes as opaque
``Any`` and routes them exclusively through
:meth:`~arnold.pipeline.hooks.ExecutorHooks.join_envelope`.

Boundary discipline: this module imports from **both** the canonical
``arnold.pipeline`` surface and the Megaplan ``_pipeline`` internals.
That is intentional — the adapter IS the bridge point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline.types import (
    Edge as CanonicalEdge,
    ParallelStage as CanonicalParallelStage,
    Pipeline as CanonicalPipeline,
    Stage as CanonicalStage,
    StepContext as CanonicalStepContext,
)
from arnold.pipelines.megaplan._pipeline.types import (
    Edge as MegaplanEdge,
    ParallelStage as MegaplanParallelStage,
    Pipeline as MegaplanPipeline,
    Stage as MegaplanStage,
    StepContext as MegaplanStepContext,
)

__all__ = [
    "to_canonical_pipeline",
    "to_canonical_step_context",
    "from_canonical_step_context",
]

# Canonical hook_extensions keys documented at module top.
_REQUIRED_HOOK_KEYS: frozenset[str] = frozenset({"plan_dir", "profile", "budget", "envelope"})


# ---------------------------------------------------------------------------
# Pipeline conversion
# ---------------------------------------------------------------------------


def to_canonical_pipeline(mp_pipeline: MegaplanPipeline) -> CanonicalPipeline:
    """Convert a Megaplan :class:`Pipeline` to a canonical :class:`~arnold.pipeline.types.Pipeline`.

    * Stages / ParallelStages are mapped field-for-field (the wrapped step
      reference rides unchanged — the canonical ``Step`` Protocol is
      structurally satisfied by Megaplan steps).
    * ``overlays`` is dropped (overlays are a Megaplan opinion applied at
      build time before the adapter runs).
    * ``binding_map`` is carried through unchanged.
    """
    canonical_stages: dict[str, CanonicalStage | CanonicalParallelStage] = {}
    for name, stage in mp_pipeline.stages.items():
        canonical_stages[name] = _convert_stage(stage)

    return CanonicalPipeline(
        stages=canonical_stages,
        entry=mp_pipeline.entry,
        binding_map=mp_pipeline.binding_map,
        resource_bundles=mp_pipeline.resource_bundles,
    )


def _convert_stage(
    stage: MegaplanStage | MegaplanParallelStage,
) -> CanonicalStage | CanonicalParallelStage:
    """Convert a single Megaplan stage to its canonical equivalent."""
    if isinstance(stage, MegaplanParallelStage):
        return CanonicalParallelStage(
            name=stage.name,
            steps=stage.steps,  # Step refs ride unchanged
            join=stage.join,
            edges=tuple(_convert_edge(e) for e in stage.edges),
            max_workers=stage.max_workers,
            decision_vocabulary=stage.decision_vocabulary,
            override_vocabulary=stage.override_vocabulary,
            reads=stage.reads,
            writes=stage.writes,
            produces=stage.produces,
            consumes=stage.consumes,
            invocation=stage.invocation,
            required_capabilities=stage.required_capabilities,
        )
    return CanonicalStage(
        name=stage.name,
        step=stage.step,  # Step ref rides unchanged
        edges=tuple(_convert_edge(e) for e in stage.edges),
        decision_vocabulary=stage.decision_vocabulary,
        override_vocabulary=stage.override_vocabulary,
        reads=stage.reads,
        writes=stage.writes,
        produces=stage.produces,
        consumes=stage.consumes,
        invocation=stage.invocation,
        required_capabilities=stage.required_capabilities,
        loop_condition=stage.loop_condition,
    )


def _convert_edge(edge: MegaplanEdge) -> CanonicalEdge:
    """Convert a Megaplan Edge to a canonical Edge (kind is widened to str)."""
    return CanonicalEdge(
        label=edge.label,
        target=edge.target,
        kind=edge.kind,  # Megaplan Literal["normal","decision","override"] → str
        recommendation=edge.recommendation,
    )


# ---------------------------------------------------------------------------
# StepContext conversion
# ---------------------------------------------------------------------------


def to_canonical_step_context(mp_ctx: MegaplanStepContext) -> CanonicalStepContext:
    """Pack a Megaplan :class:`StepContext` into a canonical :class:`StepContext`.

    The Megaplan-specific fields ``plan_dir``, ``profile``, ``budget``, and
    ``envelope`` are stored in ``hook_extensions`` under their own names.

    ``artifact_root`` is set to ``str(mp_ctx.plan_dir)``.
    """
    return CanonicalStepContext(
        artifact_root=str(mp_ctx.plan_dir),
        state=mp_ctx.state,
        mode=mp_ctx.mode,
        inputs=dict(mp_ctx.inputs),
        hook_extensions={
            "plan_dir": mp_ctx.plan_dir,
            "profile": mp_ctx.profile,
            "budget": mp_ctx.budget,
            "envelope": mp_ctx.envelope,
        },
    )


def from_canonical_step_context(ctx: CanonicalStepContext) -> MegaplanStepContext:
    """Rebuild a Megaplan :class:`StepContext` from a canonical one.

    Reads ``hook_extensions['plan_dir' | 'profile' | 'budget' | 'envelope']``
    and asserts every key is present — raises :class:`KeyError` loudly on
    miss (silent miss would corrupt downstream Megaplan code).

    The ``plan_dir`` value is coerced to :class:`~pathlib.Path` if it is a
    string.
    """
    he = ctx.hook_extensions
    missing = _REQUIRED_HOOK_KEYS - frozenset(he)
    if missing:
        raise KeyError(
            f"from_canonical_step_context: missing required hook_extensions keys: "
            f"{sorted(missing)}.  Available keys: {sorted(he)}"
        )

    plan_dir = he["plan_dir"]
    if isinstance(plan_dir, str):
        plan_dir = Path(plan_dir)

    return MegaplanStepContext(
        plan_dir=plan_dir,
        state=ctx.state,
        profile=he["profile"],
        mode=ctx.mode,
        inputs={k: Path(v) if isinstance(v, str) else v for k, v in ctx.inputs.items()},
        budget=he["budget"],
        envelope=he["envelope"],
    )
