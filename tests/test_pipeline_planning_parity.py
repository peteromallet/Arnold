"""Sprint 2 acceptance test — compiled planning Pipeline matches WORKFLOW.

Stops short of byte-identical artifact parity (Sprint 3 work — requires
porting handlers into Steps and running auto end-to-end). What this test
asserts today: the compiled :class:`Pipeline` shape matches the existing
``WORKFLOW`` + robustness overrides + with_prep/with_feedback overlays
exactly. If anyone edits ``WORKFLOW`` and forgets to update the
compilation, this test fails — that's the parity contract we can enforce
without rewriting the runtime.
"""

from __future__ import annotations

import pytest

from megaplan._core.workflow import WORKFLOW, _workflow_for_robustness
from megaplan._pipeline.planning import (
    compile_pipeline_for,
    compile_planning_pipeline,
)


_GATE_RECS = {
    "gate_proceed": "proceed",
    "gate_iterate": "iterate",
    "gate_tiebreaker": "tiebreaker",
    "gate_escalate": "escalate",
}


def _stage_edge_pairs(pipeline, state_name):
    return [(edge.label, edge.target) for edge in pipeline.stages[state_name].edges]


def _expected_edge_pairs(workflow_dict, state_name):
    """Mirror megaplan._pipeline.planning._edges_from_transitions."""
    import collections

    transitions = workflow_dict[state_name]
    gate_counts: collections.Counter = collections.Counter()
    for t in transitions:
        if t.condition in _GATE_RECS:
            gate_counts[t.condition] += 1

    pairs = []
    for t in transitions:
        cond = t.condition
        if cond == "always":
            pairs.append((t.next_step, t.next_state))
        elif cond in _GATE_RECS and gate_counts[cond] == 1:
            pairs.append((_GATE_RECS[cond], t.next_state))
        elif cond in _GATE_RECS and gate_counts[cond] > 1:
            pairs.append((t.next_step, t.next_state))
        else:
            pairs.append((f"{cond}:{t.next_step}", t.next_state))
    return pairs


def test_base_pipeline_stage_set_matches_workflow() -> None:
    pipeline = compile_planning_pipeline()
    assert set(pipeline.stages.keys()) == set(WORKFLOW.keys())
    assert pipeline.entry == "initialized"


def test_base_pipeline_edges_match_workflow() -> None:
    pipeline = compile_planning_pipeline()
    for state_name in WORKFLOW:
        actual = _stage_edge_pairs(pipeline, state_name)
        expected = _expected_edge_pairs(WORKFLOW, state_name)
        assert actual == expected, (state_name, actual, expected)


@pytest.mark.parametrize(
    "robustness",
    ["tiny", "light", "standard", "robust", "superrobust"],
)
def test_robustness_overlay_matches_runtime(robustness: str) -> None:
    pipeline = compile_pipeline_for(robustness=robustness)
    runtime = _workflow_for_robustness(robustness)
    for state_name in runtime:
        actual = _stage_edge_pairs(pipeline, state_name)
        expected = _expected_edge_pairs(runtime, state_name)
        assert actual == expected, (robustness, state_name, actual, expected)


def test_with_prep_overlay_forces_prep_transition() -> None:
    pipeline = compile_pipeline_for(
        robustness="standard",
        state_payload={"config": {"with_prep": True}},
    )
    edges = _stage_edge_pairs(pipeline, "initialized")
    assert edges == [("prep", "prepped")], edges


def test_with_feedback_overlay_splices_feedback_stage() -> None:
    pipeline = compile_pipeline_for(
        robustness="standard",
        state_payload={"config": {"with_feedback": True}},
    )
    assert _stage_edge_pairs(pipeline, "executed") == [("review", "reviewed")]
    assert _stage_edge_pairs(pipeline, "reviewed") == [("feedback", "done")]


def test_with_feedback_runtime_matches_overlay() -> None:
    runtime = _workflow_for_robustness("standard", with_feedback=True)
    pipeline = compile_pipeline_for(
        robustness="standard",
        state_payload={"config": {"with_feedback": True}},
    )
    for state_name in ("executed", "reviewed"):
        actual = _stage_edge_pairs(pipeline, state_name)
        expected = _expected_edge_pairs(runtime, state_name)
        assert actual == expected, (state_name, actual, expected)
