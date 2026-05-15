"""Sprint 4 Chunk E acceptance — Pipeline is the source; WORKFLOW is the view.

Proves the structural inversion: starting from the compiled
:class:`Pipeline`, ``workflow_dict_from_pipeline`` reconstructs the
legacy ``WORKFLOW`` dict byte-for-byte. This means the Pipeline is
sufficient to derive the legacy state machine — a future sprint can
delete the WORKFLOW dict literal and replace it with the derivation
without breaking any consumer.
"""

from __future__ import annotations

from megaplan._core.workflow_data import WORKFLOW
from megaplan._pipeline.planning import (
    compile_planning_pipeline,
    workflow_dict_from_pipeline,
)


def test_workflow_dict_from_pipeline_round_trips_against_workflow() -> None:
    pipeline = compile_planning_pipeline()
    derived = workflow_dict_from_pipeline(pipeline)

    assert set(derived.keys()) == set(WORKFLOW.keys())
    for state_name, expected_transitions in WORKFLOW.items():
        actual = derived[state_name]
        assert len(actual) == len(expected_transitions), (
            state_name, [t.condition for t in actual],
            [t.condition for t in expected_transitions],
        )
        for actual_t, expected_t in zip(actual, expected_transitions):
            assert actual_t.next_step == expected_t.next_step, (state_name, actual_t, expected_t)
            assert actual_t.next_state == expected_t.next_state, (state_name, actual_t, expected_t)
            assert actual_t.condition == expected_t.condition, (state_name, actual_t, expected_t)


def test_workflow_dict_from_pipeline_handles_collision_bucket() -> None:
    """The STATE_CRITIQUED gate_escalate fan-out (3 transitions) must
    round-trip through the collision-bucket path: kind="normal" edges
    with bare next_step labels."""

    pipeline = compile_planning_pipeline()
    derived = workflow_dict_from_pipeline(pipeline)

    critiqued = derived["critiqued"]
    escalate_transitions = [t for t in critiqued if t.condition == "gate_escalate"]
    assert len(escalate_transitions) == 3
    next_steps = sorted(t.next_step for t in escalate_transitions)
    assert next_steps == ["override abort", "override add-note", "override force-proceed"]
