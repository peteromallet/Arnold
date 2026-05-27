"""Sprint 4 Chunk D follow-up — TiebreakerStep as a single SubloopStep.

Pins the elegance commitment: the legacy two-state tiebreaker pair
collapses into one Step that wraps a child Pipeline. From the outside,
tiebreaker is now a single node with a typed PipelineVerdict — no more
intermediate ``tiebreaker_pending`` / ``tiebreaker_ready`` state names
the parent flow has to thread.
"""

from __future__ import annotations

from megaplan._pipeline.stages.tiebreaker import (
    TiebreakerStep,
    _build_tiebreaker_child_pipeline,
    _promote_from_child_state,
)
from megaplan._pipeline.types import Pipeline, Step


def test_tiebreaker_step_satisfies_step_protocol() -> None:
    step = TiebreakerStep()
    assert isinstance(step, Step)
    assert step.kind == "subloop"


def test_tiebreaker_child_pipeline_has_run_and_decide() -> None:
    child = _build_tiebreaker_child_pipeline()
    assert isinstance(child, Pipeline)
    assert set(child.stages.keys()) == {"run", "decide"}
    assert child.entry == "run"


def test_promote_maps_states_to_typed_recommendation() -> None:
    assert _promote_from_child_state({"current_state": "critiqued"}) == "iterate"
    assert _promote_from_child_state({"current_state": "aborted"}) == "escalate"
    assert _promote_from_child_state({"current_state": "anything_else"}) == "proceed"


def test_tiebreaker_is_one_node_not_two() -> None:
    """The post-collapse compiled view exposes tiebreaker as a single
    node. Compared to today's compiled planning pipeline which has
    two states (tiebreaker_pending, tiebreaker_ready), this Step is
    one node with a typed PipelineVerdict — that's the elegance gain."""
    step = TiebreakerStep()
    # one Step, not two.
    assert isinstance(step, Step)
    # When wired into a parent pipeline, parent.stages["tiebreaker"] is
    # a single Stage. The two child stages live inside child_pipeline,
    # not on the parent graph.
    from megaplan._pipeline.subloop import SubloopStep
    subloop = SubloopStep(
        name="tiebreaker",
        child_pipeline=_build_tiebreaker_child_pipeline(),
        promote=_promote_from_child_state,
    )
    assert subloop.kind == "subloop"
    assert subloop.child_pipeline is not None
    assert len(subloop.child_pipeline.stages) == 2
