"""T6: tests for megaplan._pipeline.planning_bindings."""

from __future__ import annotations

from megaplan._pipeline.planning_bindings import (
    EVALUAND_GATE_ARTIFACT_KEY,
    planning_promote,
    planning_reduce,
)
from megaplan._pipeline.types import ReduceResult


def test_planning_promote_matches_legacy_mapping():
    assert planning_promote({"current_state": "critiqued"}) == "iterate"
    assert planning_promote({"current_state": "aborted"}) == "escalate"
    assert planning_promote({"current_state": "in_progress"}) == "proceed"
    assert planning_promote({}) == "proceed"


def test_planning_reduce_uses_label_when_literal():
    agg = ReduceResult(value=None, label="iterate", tally={"iterate": 3})
    assert planning_reduce(agg) == "iterate"


def test_planning_reduce_falls_back_to_tally_majority():
    agg = ReduceResult(value=None, tally={"proceed": 1, "escalate": 4})
    assert planning_reduce(agg) == "escalate"


def test_planning_reduce_non_literal_returns_proceed():
    # A non-planning lambda emitting a non-literal Any (e.g. a free-form
    # label) collapses to the safe "proceed" default.
    agg = ReduceResult(value=42, label="winner_alpha", tally={})
    assert planning_reduce(agg) == "proceed"


def test_planning_gate_result_evaluand_artifact_touchpoint_is_explicit():
    assert EVALUAND_GATE_ARTIFACT_KEY == "evaluand"
