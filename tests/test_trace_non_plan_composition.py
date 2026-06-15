"""M4 T25 — trace runs on a non-plan composition without plan_dir."""
from __future__ import annotations

import os

from arnold.pipelines.megaplan.observability.composition_obs import (
    InMemoryCompositionObs,
    trace_from_composition,
)


def test_non_plan_composition_emits_all_beats():
    obs = InMemoryCompositionObs()
    obs.step_boundary(name="prep", kind="enter")
    obs.decision(name="gate", rationale="under-budget")
    obs.retry(retry_class="external")
    obs.budget_delta(kind="model_spend", delta_usd=0.42)
    obs.piece_identity(piece_id="execute@v1")
    obs.step_boundary(name="prep", kind="exit")

    events = trace_from_composition(obs)
    kinds = [e["kind"] for e in events]
    assert kinds == [
        "step_boundary",
        "decision",
        "retry",
        "budget_delta",
        "piece_identity",
        "step_boundary",
    ]
    assert events[3]["payload"]["delta_usd"] == 0.42


def test_legacy_plan_scoped_trace_path_still_importable():
    """Flag-OFF (default): legacy read_events + find_plan_dir is unchanged."""
    assert "MEGAPLAN_UNIFIED_EMIT" not in os.environ or os.environ.get(
        "MEGAPLAN_UNIFIED_EMIT"
    ) in (None, "", "0")
    from arnold.pipelines.megaplan.observability import read_events  # noqa: F401
    from arnold.pipelines.megaplan._core import find_plan_dir  # noqa: F401
