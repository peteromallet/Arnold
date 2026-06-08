"""Compile the canonical planning :class:`Pipeline`.

The planning pipeline is keyed by phase name:
``prep / plan / critique / gate / revise / finalize / execute / review /
tiebreaker``. Gate recommendations are represented as typed
``kind=\"decision\"`` edges on the ``gate`` stage. User-facing override
command labels remain as normal fallback edges because the live gate
handler still emits and reports those commands.
"""

from __future__ import annotations

import os
from arnold.pipelines.megaplan._pipeline.types import Pipeline


def _discovered_planning_enabled() -> bool:
    """Whether the planning compiler should route through the discovered package."""

    return os.environ.get("MEGAPLAN_M6_DISCOVERED_PLANNING", "1") == "1"


def compile_planning_pipeline() -> Pipeline:
    """Return the canonical, runnable planning :class:`Pipeline`."""

    if _discovered_planning_enabled():
        from arnold.pipelines.megaplan.pipelines.planning import build_pipeline

        return build_pipeline()
    return _compile_legacy_planning_pipeline()


def _compile_legacy_planning_pipeline() -> Pipeline:
    """Return the legacy compiler entrypoint via the canonical builder.

    The legacy flag path still exists for rollout compatibility, but the
    stage declarations now come from the single canonical
    ``arnold.pipelines.megaplan.pipeline.build_pipeline`` implementation so
    ports, edges, loop metadata, and future stage-shape changes cannot
    drift between two hand-written builders.
    """

    from arnold.pipelines.megaplan.pipeline import build_pipeline

    return build_pipeline()
