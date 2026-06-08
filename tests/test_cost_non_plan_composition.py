"""M4 T27 — cost._aggregate runs on a non-plan composition: an
in-memory event list with no plan_dir on disk."""
from __future__ import annotations

from arnold.pipelines.megaplan.observability import cost
from arnold.pipelines.megaplan.observability.events import EventKind


def test_aggregate_runs_without_plan_dir():
    events = [
        {
            "kind": EventKind.COST_RECORDED,
            "payload": {"model": "gpt-5", "cost_usd": 2.5},
            "phase": "execute",
        },
        {
            "kind": EventKind.LLM_CALL_END,
            "payload": {
                "model": "gpt-5",
                "tokens_in": 100,
                "tokens_out": 200,
            },
            "phase": "execute",
        },
    ]
    agg = cost._aggregate(events, meta_cost=0.0)
    assert agg["total_cost"] == 2.5
    assert agg["total_tokens"] == 300
    assert agg["cost_by_vendor"]["codex"] == 2.5
